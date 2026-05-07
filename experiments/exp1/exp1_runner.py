"""
实验一运行器：支持 Base LLM 和 ACE 两种模式的任务执行。
"""

import re
import time

from core.ace_core import TraceRecorder


class Exp1Runner:
    """
    实验一任务运行器。

    负责以 Base LLM（无 ACE）或 ACE（完整管道）模式执行单个测试任务，
    并记录执行过程中的所有可度量信息。
    """

    def __init__(self, ai_handler, map_handler, mode="ace"):
        """
        Parameters
        ----------
        ai_handler : AIHandler
            已初始化的 AIHandler 实例（用于 ACE 模式）
        map_handler : BrowserMapHandler
            地图处理器
        mode : str
            'base' - 无 ACE，直接调用 LLM
            'ace' - 完整 ACE 管道
        """
        self.ai_handler = ai_handler
        self.map_handler = map_handler
        self.mode = mode
        self.llm = ai_handler.llm if ai_handler else None

    def run_task(self, task_data):
        """
        执行单个测试任务。

        Parameters
        ----------
        task_data : dict
            任务定义（来自 exp1_suite.json）

        Returns
        -------
        dict
            {
                "answer": str,
                "trace_entries": list,
                "ace_panel": dict,
                "tool_calls": list,
                "code_executions": list,
                "error": str | None
            }
        """
        task_text = task_data["task"]
        task_type = task_data["task_type"]

        if self.mode == "base":
            return self._run_base(task_text, task_type)
        else:
            return self._run_ace(task_text, task_type)

    def _run_base(self, task_text, task_type):
        """
        以 Base LLM 模式运行（无 ACE 机制，但支持工具调用）。

        使用 SpatialAnalystAgent.think()+execute_tool() 进行单轮工具调用。
        跳过所有 ACE 机制：
        - ❌ ExperienceLibrary.retrieve() — 无经验检索
        - ❌ ContextManager.format_conversation_context() — 无会话上下文
        - ❌ CriticAgent/EvolutionAgent — 无错误诊断和经验演化
        - ❌ _dispatch_loop 多轮循环 — 仅单轮 LLM 调用
        """
        output = {
            "answer": "",
            "trace_entries": [],
            "ace_panel": {},
            "tool_calls": [],
            "code_executions": [],
            "error": None,
        }

        try:
            from tools import create_tools
            from agents.spatial_analyst_agent import SpatialAnalystAgent
            from core.ace_core import TraceRecorder

            schema_info = self._get_schema_text()
            tools = create_tools(self.ai_handler)
            spatial_agent = SpatialAnalystAgent(self.llm, tools, self.ai_handler)
            trace = TraceRecorder(task=task_text, task_type=task_type)

            # 系统提示：告知工具能力，但强调无记忆/上下文
            system_prompt = f"""你是一个 GIS 分析助手，可以调用工具完成地理分析任务。

可用的数据图层：
{schema_info}

你可以使用以下地理分析工具：
- 搜索/查询：search_poi（按名称搜索）, query_poi_by_conditions（按条件筛选）, get_poi_by_index（按索引获取）
- 邻近分析：find_nearby（查找某点附近）, find_nearby_point（查找 POI 附近的其他 POI）
- 缓冲区分析：buffer_analysis（创建缓冲区）
- 叠加分析：overlay_layers（图层叠加）, spatial_join（空间连接）
- 聚类分析：cluster_points_dbscan（DBSCAN 聚类）, hotspot_analysis（热点分析）
- 统计分析：summarize_layer_statistics（图层统计）
- 邻近查找：nearest_neighbor（最近邻查找）
- 代码执行：execute_spatial_code（执行 Python 空间分析代码）
- 数据导出：export_analysis_result（导出结果）

注意：
- 这是独立的一次性调用，没有之前的对话上下文和记忆。
- 请根据问题选择合适的工具并调用。
- 说明你的分析思路和最终结论。"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"问题：{task_text}"}
            ]

            # 单轮工具调用（无多轮循环）
            response = spatial_agent.think(messages, trace, 1)
            tool_calls_collected = []
            code_execs_collected = []

            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tc = {
                        "name": tool_call["name"],
                        "args": tool_call.get("args", {}),
                        "status": "success",
                    }
                    execution = spatial_agent.execute_tool(tool_call, trace)
                    if "出错" in execution.result or "未知工具" in execution.result:
                        tc["status"] = "error"
                        tc["error"] = execution.result[:200]
                    tool_calls_collected.append(tc)

                    # 检测代码执行工具
                    if tool_call["name"] == "execute_spatial_code":
                        code_execs_collected.append({
                            "code": str(tool_call.get("args", {}).get("code", ""))[:200],
                            "status": tc["status"],
                        })

            answer = response.content if hasattr(response, 'content') else str(response)

            # 在回答末尾附加工具调用摘要
            if tool_calls_collected:
                tool_summary = "\n\n[工具调用摘要]\n" + "\n".join(
                    f"  ✅ {tc['name']}" if tc['status'] == 'success'
                    else f"  ❌ {tc['name']}: {tc.get('error', '执行失败')}"
                    for tc in tool_calls_collected
                )
                answer += tool_summary

            output["answer"] = answer
            output["tool_calls"] = tool_calls_collected
            output["code_executions"] = code_execs_collected
            output["trace_entries"] = [
                {"time": time.strftime("%H:%M:%S"), "role": "Base LLM", "content": answer[:300]}
            ]

        except Exception as e:
            import traceback
            output["error"] = f"{str(e)}\n{traceback.format_exc()[:500]}"
            output["answer"] = f"Base执行出错: {e}"

        return output

    def _run_ace(self, task_text, task_type):
        """
        以完整 ACE 模式运行。

        使用 AIHandler 的完整多智能体管道。
        从 Trace 文本中提取工具调用信息以支持准确率评估。
        """
        output = {
            "answer": "",
            "trace_entries": [],
            "ace_panel": {},
            "tool_calls": [],
            "code_executions": [],
            "error": None,
        }

        try:
            # 通过 coordinator 运行完整 ACE 管道
            # 不需要页面高亮回调（实验模式）
            coordinator = self.ai_handler.coordinator_agent
            answer = coordinator.run(task_text, lambda highlights: None)

            # 收集 ACE 面板信息和 Trace 文本
            ace_panel = self.ai_handler.get_ace_panel()
            trace_text = self.ai_handler.get_trace_text() or ""

            # ---- 从 Trace 文本中提取工具调用和代码执行信息 ----
            tool_calls_collected = []
            code_execs_collected = []

            # Trace 中包含 SpatialAnalystAgent.execute_tool() 添加的条目：
            #   "调用工具 query_poi_by_conditions，参数：{'layer_name': '餐饮', ...}"
            if trace_text:
                # 1) 提取工具名：匹配 "调用工具 <tool_name>" 模式
                tool_pattern = r'调用工具\s+(\w+)'
                for match in re.finditer(tool_pattern, trace_text):
                    tool_name = match.group(1)
                    # 去重（同一工具可能在多轮中被调用）
                    if not any(tc.get("name") == tool_name for tc in tool_calls_collected):
                        tool_calls_collected.append({
                            "name": tool_name,
                            "status": "success",
                        })

                # 2) 从 Tool Feedback 中检测实际工具执行错误
                #    仅当工具抛出异常时（SpatialAnalystAgent.execute_tool() 捕获），
                #    result 会设为 "工具执行出错: {exc}" 或 "未知工具: {tool_name}"
                #    此时 Tool Feedback 内容包含这些精确模式
                error_tool_pattern = r'调用工具\s+(\w+)，参数：[^\n]*\n(?:.*?工具执行出错|.*?未知工具)'
                for match in re.finditer(error_tool_pattern, trace_text, re.DOTALL):
                    err_tool = match.group(1)
                    for tc in tool_calls_collected:
                        if tc["name"] == err_tool:
                            tc["status"] = "error"
                            tc["error"] = "工具执行过程中抛出异常"

                # 3) 从 ACE panel 的 tool_feedbacks 中提取工具名（备选方案）
                tool_feedbacks = ace_panel.get("tool_feedbacks", [])
                for fb in tool_feedbacks:
                    # 有时反馈中直接包含工具名
                    for exp_tool in re.findall(r'\b(\w+_tool|\w+_by_\w+)\b', fb):
                        if not any(tc.get("name") == exp_tool for tc in tool_calls_collected):
                            tool_calls_collected.append({
                                "name": exp_tool,
                                "status": "success",
                            })

            # ---- 从 ACE panel 中提取代码执行信息 ----
            generated_code = ace_panel.get("generated_code", "")
            execution_status = ace_panel.get("execution_status", "")

            if generated_code:
                code_execs_collected.append({
                    "code": generated_code[:200],
                    "status": "success" if "错误" not in execution_status and "失败" not in execution_status else "error",
                })

            # 如果 panel 中有错误状态但尚未被 tool_calls 捕获，补充记录
            if execution_status and ("错误" in execution_status or "失败" in execution_status):
                if not any(tc.get("status") == "error" for tc in tool_calls_collected):
                    tool_calls_collected.append({
                        "name": "unknown_tool",
                        "status": "error",
                        "error": execution_status[:200],
                    })

            output["answer"] = answer
            output["trace_entries"] = self._parse_trace_entries(trace_text)
            output["ace_panel"] = ace_panel
            output["tool_calls"] = tool_calls_collected
            output["code_executions"] = code_execs_collected

        except Exception as e:
            import traceback
            output["error"] = f"{str(e)}\n{traceback.format_exc()[:500]}"
            output["answer"] = f"ACE执行出错: {e}"

        return output

    def _get_schema_text(self):
        """获取图层 schema 的文本描述。"""
        try:
            return self.ai_handler.context_manager.get_schema_info()
        except Exception:
            return "无法获取图层信息"

    def _parse_trace_entries(self, trace_text):
        """从 Trace 文本中解析出结构化条目。"""
        entries = []
        if not trace_text:
            return entries

        pattern = r'\[(\d{2}:\d{2}:\d{2})\]\s*(.+?)\n(.*?)(?=\n\[\d{2}:\d{2}:\d{2}\]|\Z)'
        for match in re.finditer(pattern, trace_text, re.DOTALL):
            entries.append({
                "time": match.group(1),
                "role": match.group(2).strip(),
                "content": match.group(3).strip()[:200],
            })

        if not entries:
            # 退化：整段作为一条
            entries.append({
                "time": time.strftime("%H:%M:%S"),
                "role": "ACE System",
                "content": trace_text[:300],
            })

        return entries
