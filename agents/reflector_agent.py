import re

from core.critic import CriticAgent
from core.evolution import EvolutionManager
from core.jsonl_logger import log_evolution


class ReflectorAgent:
    """Evaluates tool feedback and closes the ACE evolution loop."""

    def __init__(self, experience_library):
        self.critic = CriticAgent()
        self.evolution_manager = EvolutionManager(experience_library)

    def evaluate(self, user_input, task_type, tool_name, tool_args, result, trace):
        if not self._should_reflect(result):
            trace.add("Reflector Agent", "未检测到需要反思的结构化错误模式，跳过反思。")
            return None

        code = tool_args.get("code", "") if isinstance(tool_args, dict) else ""
        diagnosis = self.critic.diagnose(
            user_input,
            task_type,
            tool_name,
            tool_args,
            result,
            code=code,
        )
        evolution = self.evolution_manager.evolve(
            diagnosis=diagnosis,
            task_type=task_type,
            error_text=result,
            code=code,
            trigger=f"tool={tool_name}; args={tool_args}",
        )
        reflection = self._build_reflection_text(tool_name, diagnosis, evolution)
        payload = {
            "reflection": reflection,
            "diagnosis": diagnosis,
            "evolution": evolution,
        }
        trace.add("Reflector Agent", reflection)
        trace.add("Reflector Agent / Diagnosis", diagnosis)
        trace.add("Reflector Agent / Evolution", evolution)
        return payload

    def record_exception(self, task_type, trigger, error_text, trace):
        diagnosis = self.critic.diagnose(
            task=trigger,
            task_type=task_type,
            tool_name="exception",
            tool_args={"trigger": trigger},
            result=error_text,
            code="",
        )
        evolution = self.evolution_manager.evolve(
            diagnosis=diagnosis,
            task_type=task_type,
            error_text=error_text,
            code="",
            trigger=trigger,
        )
        reflection = self._build_reflection_text("exception", diagnosis, evolution)
        payload = {
            "reflection": reflection,
            "diagnosis": diagnosis,
            "evolution": evolution,
        }
        trace.add("Reflector Agent", reflection)
        trace.add("Reflector Agent / Diagnosis", diagnosis)
        trace.add("Reflector Agent / Evolution", evolution)
        return payload

    def learn_from_user_feedback(self, feedback_type, task_type, user_task, assistant_answer, correction=""):
        if feedback_type == "correct":
            category = "用户正反馈"
            problem = f"用户确认该任务结果正确。任务: {user_task[:120]}"
            strategy = "类似任务可优先复用本次上下文解析、工具选择和回答组织方式。"
            outcome = "success"
        elif feedback_type == "incorrect":
            category = "用户负反馈"
            problem = (
                f"用户认为结果不正确。任务: {user_task[:120]} "
                f"原回答摘要: {assistant_answer[:180]}"
            )
            strategy = "类似任务需要重新检查上下文指代、图层选择、字段条件和空间分析参数，不要直接沿用上一轮回答。"
            outcome = "failure"
        else:
            category = "用户纠正"
            problem = (
                f"用户对结果给出纠正。任务: {user_task[:120]} "
                f"原回答摘要: {assistant_answer[:160]}"
            )
            strategy = f"遇到类似任务时优先遵循用户纠正: {correction[:240]}"
            outcome = "neutral"

        exp, created = self.evolution_manager.library.add_or_update(
            category=category,
            task_type=task_type,
            trigger=f"用户反馈类型={feedback_type}; 用户任务={user_task[:120]}",
            problem=problem,
            strategy=strategy,
            source="user_feedback",
            outcome=outcome,
        )
        log_evolution(
            {
                "task_type": task_type,
                "trigger": f"user_feedback:{feedback_type}",
                "updated": True,
                "action": "add" if created else "update",
                "experience_id": exp.get("id", ""),
                "category": category,
                "source": "user_feedback",
            }
        )
        return exp, created

    def _should_reflect(self, result):
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

    def _build_reflection_text(self, tool_name, diagnosis, evolution):
        if not diagnosis:
            return "ReflectorAgent 未能生成结构化诊断，经验库未更新。"
        return (
            f"ReflectorAgent 已完成对 {tool_name} 的反思诊断，"
            f"错误类型为 {diagnosis['error_type']}；建议策略：{diagnosis['strategy']}；"
            f"经验演化动作：{evolution['action']}。"
        )
