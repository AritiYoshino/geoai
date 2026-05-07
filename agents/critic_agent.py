import re

from core.critic import CriticAgent as CoreCriticAgent


class CriticAgent:
    """Diagnoses tool, code, and runtime failures in the ACE loop."""

    def __init__(self):
        self.diagnosis_engine = CoreCriticAgent()

    def diagnose_tool_result(self, user_input, task_type, tool_name, tool_args, result, trace):
        if not self.should_diagnose(result):
            trace.add("Critic Agent", "未检测到需要诊断的结构化错误模式，跳过错误诊断。")
            return None

        code = tool_args.get("code", "") if isinstance(tool_args, dict) else ""
        diagnosis = self.diagnosis_engine.diagnose(
            task=user_input,
            task_type=task_type,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
            code=code,
        )
        trace.add("Critic Agent / Diagnosis", diagnosis)
        trace.add("Critic Agent", self._build_diagnosis_text(tool_name, diagnosis))
        return diagnosis

    def diagnose_exception(self, task_type, trigger, error_text, trace):
        diagnosis = self.diagnosis_engine.diagnose(
            task=trigger,
            task_type=task_type,
            tool_name="exception",
            tool_args={"trigger": trigger},
            result=error_text,
            code="",
        )
        trace.add("Critic Agent / Diagnosis", diagnosis)
        trace.add("Critic Agent", self._build_diagnosis_text("exception", diagnosis))
        return diagnosis

    def should_diagnose(self, result):
        text = str(result or "")
        if not text.strip():
            return False
        return bool(
            re.search(
                r"error|exception|traceback|failed|timeout|empty|0 results|not found|未找到|为空|找不到|没有找到|错误|异常|失败",
                text,
                re.I,
            )
        )

    def _build_diagnosis_text(self, tool_name, diagnosis):
        if not diagnosis:
            return "CriticAgent 未能生成结构化诊断。"
        return (
            f"CriticAgent 已完成对 {tool_name} 的错误诊断，"
            f"错误类型为 {diagnosis['error_type']}；原因：{diagnosis['reason']}；"
            f"建议策略：{diagnosis['strategy']}。"
        )
