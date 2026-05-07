import ast
import re

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage


_UNPARSEABLE = object()


class CoordinatorAgent:
    """Understands intent, builds plans, dispatches work, and manages the loop."""

    def __init__(self, context_manager, experience_library, spatial_agent, critic_agent, evolution_agent):
        self.context_manager = context_manager
        self.experience_library = experience_library
        self.spatial_agent = spatial_agent
        self.critic_agent = critic_agent
        self.evolution_agent = evolution_agent

    def run(self, user_input, highlight_callback):
        task_type = self.context_manager.classify_intent(user_input)
        trace = self.context_manager.create_trace(user_input, task_type)
        conversation_context = self.context_manager.format_conversation_context(user_input)
        plan = self._make_plan(user_input, task_type, conversation_context)
        experiences = self.experience_library.retrieve(user_input, task_type)
        experience_text = self.experience_library.format_for_prompt(experiences)

        trace.add("Coordinator Agent / Intent", f"识别任务类型: {task_type}")
        trace.add("Coordinator Agent / Plan", plan)
        trace.add("Context Manager", conversation_context)
        trace.add("Experience Library", experience_text)

        system_prompt = self.context_manager.build_agent_prompt(
            task_type, plan, experience_text, conversation_context
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_input)]

        if self._should_answer_directly(task_type, user_input):
            answer = self._answer_direct_request(user_input, task_type, messages, trace)
            self.context_manager.set_trace(trace)
            return answer

        deterministic_answer = self._maybe_run_deterministic_clustering(
            user_input=user_input,
            task_type=task_type,
            trace=trace,
            highlight_callback=highlight_callback,
        )
        if deterministic_answer:
            self.context_manager.set_trace(trace)
            return deterministic_answer

        final_answer = self._dispatch_loop(
            user_input=user_input,
            task_type=task_type,
            messages=messages,
            trace=trace,
            highlight_callback=highlight_callback,
        )
        self.context_manager.set_trace(trace)
        return final_answer

    def _should_answer_directly(self, task_type, user_input):
        if task_type in {"help", "general"}:
            return True
        help_markers = ["怎么用", "如何用", "介绍", "说明", "解释", "有哪些功能", "可以做什么", "能做什么"]
        lowered = str(user_input).lower()
        if any(marker in lowered for marker in help_markers):
            return True

        analysis_markers = [
            "统计",
            "计算",
            "查询",
            "查找",
            "搜索",
            "附近",
            "周边",
            "距离",
            "高亮",
            "显示",
            "地图",
            "筛选",
            "叠加",
            "相交",
            "缓冲",
            "面积",
            "数量",
            "排序",
        ]
        knowledge_markers = [
            "是什么",
            "什么意思",
            "什么关系",
            "关系是什么",
            "为什么",
            "区别",
            "属于",
            "介绍一下",
            "解释一下",
        ]
        asks_for_knowledge = any(marker in lowered for marker in knowledge_markers)
        asks_for_analysis = any(marker in lowered for marker in analysis_markers)
        return asks_for_knowledge and not asks_for_analysis

    def _answer_direct_request(self, user_input, task_type, messages, trace):
        trace.add("Coordinator Agent", "识别为自由问答或说明型请求，交由 DeepSeek 直接回答；必要时追问澄清，不进入工具调用循环。")
        messages[0] = SystemMessage(
            content=(
                str(messages[0].content)
                + "\n## 自由问答 / 澄清规则\n"
                + f"- 当前任务类型识别为：{task_type}。\n"
                + "- 如果用户问的是概念、行政区划关系、术语解释、背景知识、系统能力说明，请直接用常识和已有上下文回答。\n"
                + "- 如果问题缺少必要条件，无法判断用户想做 GIS 分析还是普通问答，请先追问 1 个简短澄清问题。\n"
                + "- 不要调用任何工具，不要执行代码，不要进入多轮调度。\n"
                + "- 回答使用简洁中文；如涉及事实边界，请说明“通常/一般理解”或提醒以官方口径为准。"
            )
        )
        try:
            response = self.spatial_agent.llm.invoke(messages)
            content = getattr(response, "content", "") or "这个问题更像普通问答。你可以补充一下想了解概念关系，还是想在地图数据中做空间分析。"
            trace.add("Coordinator Agent / Final", str(content)[:500])
            return content
        except Exception as exc:
            answer = f"自由问答生成失败：{str(exc)}"
            trace.add("Critic Agent", answer)
            self._diagnose_and_evolve_exception(task_type, "llm.invoke", str(exc), trace)
            return answer

    def _make_plan(self, user_input, task_type, conversation_context):
        base = [
            "1. 解析用户意图、距离单位、目标类别和可能省略的参考 POI。",
            "2. 读取会话上下文；若存在“最可能指代的上一轮 POI”，优先使用它。",
            "3. 检索经验库，确定字段验证、CRS、防御性查询等约束。",
            "4. 调度空间分析智能体调用工具，必要时先定位参考点，再执行空间分析。",
            "5. 将工具反馈交给 Critic 智能体诊断，发现可沉淀经验的问题则交由 Evolution 智能体更新经验库。",
            "6. 输出简洁结论，并同步地图高亮结果。",
        ]
        if "最可能指代的上一轮 POI" in conversation_context:
            base.insert(
                2,
                "2a. 本轮存在省略指代，应把用户问题解释为对该 POI 的继续查询，而不是脱离上下文重新搜索。",
            )
        if task_type == "nearby":
            base.insert(
                4,
                "4a. 若上下文已存在参考 POI，直接使用其 layer/index；若目标有类别词，使用带过滤的邻近分析工具。",
            )
            if "缓冲" in user_input or "buffer" in str(user_input).lower():
                base.insert(
                    5,
                    "4b. 若用户要基于某个 POI 生成缓冲区，必须调用 buffer_analysis 时传 feature_index，只缓冲该 POI；若用户要某类/这些 POI 的缓冲区，先查询命中索引，再传 feature_indices；不要误对整个 POI 图层生成缓冲区。",
                )
        elif task_type in {"query", "search"}:
            base.insert(4, "4a. 属性查询前必须确认图层字段，避免猜测列名。")
        return "\n".join(base)

    def _maybe_run_deterministic_clustering(self, user_input, task_type, trace, highlight_callback):
        text = str(user_input or "")
        lowered = text.lower()
        if task_type != "clustering" and not any(token in lowered for token in ("dbscan", "hotspot")):
            return None

        layer_name = self._extract_layer_name(text)
        if not layer_name:
            return None

        if "热点" in text or "hotspot" in lowered:
            tool_call = {
                "id": "deterministic_hotspot_analysis",
                "name": "hotspot_analysis",
                "args": {
                    "layer_name": layer_name,
                    "cell_size": self._extract_number(text, ["cell_size", "网格", "格网", "边长"], 1000),
                    "unit": self._extract_unit(text, "米"),
                    "top_n": int(self._extract_number(text, ["top_n", "前"], 10)),
                },
            }
        else:
            tool_call = {
                "id": "deterministic_cluster_points_dbscan",
                "name": "cluster_points_dbscan",
                "args": {
                    "layer_name": layer_name,
                    "eps": self._extract_number(text, ["eps", "距离", "半径", "阈值"], 500),
                    "min_samples": int(self._extract_number(text, ["min_samples", "最小样本", "最少样本"], 5)),
                    "unit": self._extract_unit(text, "米"),
                },
            }

        trace.add("Coordinator Agent", f"识别为聚类分析请求，直接调用 {tool_call['name']}。")
        execution = self.spatial_agent.execute_tool(tool_call, trace)
        self.context_manager.remember_pois(execution.pois)
        if execution.highlights:
            highlight_callback(execution.highlights)
        self._diagnose_and_evolve_tool_result(
            user_input=user_input,
            task_type=task_type,
            tool_name=execution.name,
            tool_args=execution.args,
            result=execution.result,
            trace=trace,
        )
        return self._format_single_tool_answer(user_input, execution, trace)

    def _extract_layer_name(self, text):
        names = getattr(self.context_manager.map_handler, "layer_names", [])
        for name in sorted(names, key=lambda item: len(str(item)), reverse=True):
            if str(name) and str(name) in text:
                return str(name)
        return None

    def _extract_number(self, text, markers, default):
        for marker in markers:
            pattern = rf"{re.escape(marker)}\s*[=为:：]?\s*(\d+(?:\.\d+)?)"
            match = re.search(pattern, text, re.I)
            if match:
                return float(match.group(1))
        return float(default)

    def _extract_unit(self, text, default):
        lowered = text.lower()
        if "公里" in text or "千米" in text or "km" in lowered:
            return "km"
        if "米" in text or re.search(r"\bm\b", lowered):
            return "米"
        return default

    def _dispatch_loop(self, user_input, task_type, messages, trace, highlight_callback):
        max_iterations = 6
        tool_feedbacks = []
        for iteration in range(1, max_iterations + 1):
            if sum(len(str(msg)) for msg in messages) > 80000:
                trace.add("Coordinator Agent", "上下文过长，停止调度并要求缩小范围。")
                return "返回结果过大，已保留地图高亮。请缩小查询范围后继续分析。"

            try:
                response = self.spatial_agent.think(messages, trace, iteration)
            except Exception as exc:
                answer = f"调用 AI 服务失败：{str(exc)}"
                trace.add("Critic Agent", answer)
                self._diagnose_and_evolve_exception(task_type, "llm.invoke", str(exc), trace)
                return answer

            messages.append(response)
            tool_calls = getattr(response, "tool_calls", None)
            if response.content and not tool_calls:
                fallback_tool_call = self._extract_inline_tool_call(response.content)
                if fallback_tool_call:
                    trace.add(
                        "Coordinator Agent",
                        "检测到模型在正文中写出了工具调用代码，已转换为真实工具执行。",
                    )
                    execution = self.spatial_agent.execute_tool(fallback_tool_call, trace)
                    self.context_manager.remember_pois(execution.pois)
                    if execution.highlights:
                        highlight_callback(execution.highlights)
                    self._diagnose_and_evolve_tool_result(
                        user_input=user_input,
                        task_type=task_type,
                        tool_name=execution.name,
                        tool_args=execution.args,
                        result=execution.result,
                        trace=trace,
                    )
                    return self._format_single_tool_answer(
                        user_input=user_input,
                        execution=execution,
                        trace=trace,
                    )
                trace.add("Coordinator Agent / Final", response.content[:300])
                return response.content

            if not tool_calls:
                trace.add("Coordinator Agent", "空间分析智能体没有给出工具调用或文本回答。")
                return "抱歉，我无法处理这个请求。"

            for tool_call in tool_calls:
                execution = self.spatial_agent.execute_tool(tool_call, trace)
                self.context_manager.remember_pois(execution.pois)
                if execution.highlights:
                    highlight_callback(execution.highlights)

                self._diagnose_and_evolve_tool_result(
                    user_input=user_input,
                    task_type=task_type,
                    tool_name=execution.name,
                    tool_args=execution.args,
                    result=execution.result,
                    trace=trace,
                )

                tool_result = execution.result
                tool_feedbacks.append(
                    f"工具 {execution.name} 参数 {execution.args}\n结果：{tool_result}"
                )
                if len(tool_result) > 2000:
                    tool_result = tool_result[:2000] + "...(结果已截断，完整匹配已在地图上高亮)"
                messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

        trace.add("Coordinator Agent", "达到最大协同轮次，停止调度。")
        if tool_feedbacks:
            return self._summarize_after_max_iterations(user_input, task_type, tool_feedbacks, trace)
        return "已达到最大协同轮次，请缩小任务范围或补充更明确的地点、图层、距离条件。"

    def _extract_inline_tool_call(self, content):
        text = str(content or "")
        for tool_name in ("cluster_points_dbscan", "hotspot_analysis"):
            pattern = rf"{tool_name}\s*\((.*?)\)"
            match = re.search(pattern, text, re.S)
            if not match:
                continue
            args = self._parse_call_args(tool_name, match.group(1))
            if args is not None:
                return {
                    "id": f"inline_{tool_name}",
                    "name": tool_name,
                    "args": args,
                }
        return None

    def _parse_call_args(self, tool_name, arg_text):
        try:
            parsed = ast.parse(f"f({arg_text})", mode="eval")
        except SyntaxError:
            return None
        if not isinstance(parsed.body, ast.Call):
            return None

        args = {}
        positional = [self._literal_arg(arg) for arg in parsed.body.args]
        if any(value is _UNPARSEABLE for value in positional):
            return None

        positional_names = {
            "cluster_points_dbscan": ["layer_name", "eps", "min_samples", "unit"],
            "hotspot_analysis": ["layer_name", "cell_size", "unit", "top_n"],
        }.get(tool_name, [])
        for name, value in zip(positional_names, positional):
            args[name] = value

        for keyword in parsed.body.keywords:
            if keyword.arg is None:
                return None
            value = self._literal_arg(keyword.value)
            if value is _UNPARSEABLE:
                return None
            args[keyword.arg] = value
        return args

    def _literal_arg(self, node):
        try:
            return ast.literal_eval(node)
        except Exception:
            return _UNPARSEABLE

    def _format_single_tool_answer(self, user_input, execution, trace):
        result = execution.result
        if len(result) > 1800:
            result = result[:1800] + "...(结果已截断，完整结果已写入地图图层)"
        answer = (
            f"已按你的请求实际执行 `{execution.name}`。\n\n"
            f"参数：{execution.args}\n\n"
            f"{result}\n\n"
            "前端会自动刷新生成的分析图层；如果地图没有立刻显示，请手动切换该聚类结果图层。"
        )
        trace.add("Coordinator Agent / Final", answer[:500])
        return answer

    def _summarize_after_max_iterations(self, user_input, task_type, tool_feedbacks, trace):
        trace.add("Coordinator Agent", "已有工具反馈，改由 DeepSeek 基于现有结果直接汇总，避免返回空泛的最大轮次提示。")
        feedback_text = "\n\n".join(tool_feedbacks)[-12000:]
        messages = [
            SystemMessage(
                content=(
                    "你是 GeoAI 的最终回答整理器。调度循环已经达到上限，但已有工具反馈。\n"
                    "请只基于下面的工具反馈总结可确认的结论；不要再要求调用工具。\n"
                    "如果工具反馈之间存在矛盾或不足，要明确说明不确定点，并给出下一步建议。\n"
                    "回答简洁中文。"
                )
            ),
            HumanMessage(
                content=(
                    f"用户问题：{user_input}\n"
                    f"任务类型：{task_type}\n\n"
                    f"已有工具反馈：\n{feedback_text}"
                )
            ),
        ]
        try:
            response = self.spatial_agent.llm.invoke(messages)
            content = getattr(response, "content", "") or ""
            if content:
                trace.add("Coordinator Agent / Final", str(content)[:500])
                return content
        except Exception as exc:
            trace.add("Critic Agent", f"最大轮次兜底总结失败：{str(exc)}")

        return "我已经拿到部分分析结果，但整理最终结论时失败了。请缩小范围或明确你想要的是概念解释、空间包含关系、相邻关系，还是面积/距离计算。"

    def _diagnose_and_evolve_tool_result(self, user_input, task_type, tool_name, tool_args, result, trace):
        diagnosis = self.critic_agent.diagnose_tool_result(
            user_input=user_input,
            task_type=task_type,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
            trace=trace,
        )
        if not diagnosis:
            return None
        code = tool_args.get("code", "") if isinstance(tool_args, dict) else ""
        return self.evolution_agent.evolve_from_diagnosis(
            diagnosis=diagnosis,
            task_type=task_type,
            error_text=result,
            code=code,
            trigger=f"tool={tool_name}; args={tool_args}",
            trace=trace,
        )

    def _diagnose_and_evolve_exception(self, task_type, trigger, error_text, trace):
        diagnosis = self.critic_agent.diagnose_exception(
            task_type=task_type,
            trigger=trigger,
            error_text=error_text,
            trace=trace,
        )
        return self.evolution_agent.evolve_from_diagnosis(
            diagnosis=diagnosis,
            task_type=task_type,
            error_text=error_text,
            code="",
            trigger=trigger,
            trace=trace,
        )
