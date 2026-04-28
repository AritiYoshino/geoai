from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage


class CoordinatorAgent:
    """Understands intent, builds plans, dispatches work, and manages the loop."""

    def __init__(self, context_manager, experience_library, spatial_agent, reflector_agent):
        self.context_manager = context_manager
        self.experience_library = experience_library
        self.spatial_agent = spatial_agent
        self.reflector_agent = reflector_agent

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
            answer = self._answer_help_request(user_input, messages, trace)
            self.context_manager.set_trace(trace)
            return answer

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
        if task_type == "help":
            return True
        help_markers = ["怎么用", "如何用", "介绍", "说明", "解释", "有哪些功能", "可以做什么", "能做什么"]
        lowered = str(user_input).lower()
        return any(marker in lowered for marker in help_markers)

    def _answer_help_request(self, user_input, messages, trace):
        trace.add("Coordinator Agent", "识别为说明型请求，直接生成回答，不进入工具调用循环。")
        messages[0] = SystemMessage(
            content=(
                str(messages[0].content)
                + "\n## 说明型问题附加规则\n"
                + "- 如果用户是在询问某种分析能力怎么用、适合什么场景、需要哪些参数，请直接回答。\n"
                + "- 不要调用任何工具，不要执行代码，不要进入多轮调度。\n"
                + "- 优先给出：适用场景、输入参数、典型问法、结果解读、注意事项。\n"
                + "- 回答使用简洁中文。"
            )
        )
        try:
            response = self.spatial_agent.llm.invoke(messages)
            content = getattr(response, "content", "") or "我可以继续为你说明这个分析能力的适用场景、参数和示例问法。"
            trace.add("Coordinator Agent / Final", str(content)[:500])
            return content
        except Exception as exc:
            answer = f"说明请求生成失败：{str(exc)}"
            trace.add("Reflector Agent", answer)
            self.reflector_agent.record_exception("help", "llm.invoke", str(exc), trace)
            return answer

    def _make_plan(self, user_input, task_type, conversation_context):
        base = [
            "1. 解析用户意图、距离单位、目标类别和可能省略的参考 POI。",
            "2. 读取会话上下文；若存在“最可能指代的上一轮 POI”，优先使用它。",
            "3. 检索经验库，确定字段验证、CRS、防御性查询等约束。",
            "4. 调度空间分析智能体调用工具，必要时先定位参考点，再执行空间分析。",
            "5. 将工具反馈交给反思者智能体评估，发现错误则更新经验库并继续优化。",
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
        elif task_type in {"query", "search"}:
            base.insert(4, "4a. 属性查询前必须确认图层字段，避免猜测列名。")
        return "\n".join(base)

    def _dispatch_loop(self, user_input, task_type, messages, trace, highlight_callback):
        max_iterations = 6
        for iteration in range(1, max_iterations + 1):
            if sum(len(str(msg)) for msg in messages) > 80000:
                trace.add("Coordinator Agent", "上下文过长，停止调度并要求缩小范围。")
                return "返回结果过大，已保留地图高亮。请缩小查询范围后继续分析。"

            try:
                response = self.spatial_agent.think(messages, trace, iteration)
            except Exception as exc:
                answer = f"调用 AI 服务失败：{str(exc)}"
                trace.add("Reflector Agent", answer)
                self.reflector_agent.record_exception(task_type, "llm.invoke", str(exc), trace)
                return answer

            messages.append(response)
            tool_calls = getattr(response, "tool_calls", None)
            if response.content and not tool_calls:
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

                self.reflector_agent.evaluate(
                    user_input=user_input,
                    task_type=task_type,
                    tool_name=execution.name,
                    tool_args=execution.args,
                    result=execution.result,
                    trace=trace,
                )

                tool_result = execution.result
                if len(tool_result) > 2000:
                    tool_result = tool_result[:2000] + "...(结果已截断，完整匹配已在地图上高亮)"
                messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

        trace.add("Coordinator Agent", "达到最大协同轮次，停止调度。")
        return "已达到最大协同轮次，请缩小任务范围或补充更明确的地点、图层、距离条件。"
