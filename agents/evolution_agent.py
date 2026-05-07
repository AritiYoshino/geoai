from core.evolution import EvolutionManager
from core.jsonl_logger import log_evolution


class EvolutionAgent:
    """Turns critic diagnoses and user feedback into reusable experience."""

    def __init__(self, experience_library):
        self.evolution_manager = EvolutionManager(experience_library)
        self.library = experience_library

    def evolve_from_diagnosis(
        self,
        diagnosis,
        task_type,
        error_text="",
        code="",
        trigger="",
        trace=None,
    ):
        evolution = self.evolution_manager.evolve(
            diagnosis=diagnosis,
            task_type=task_type,
            error_text=error_text,
            code=code,
            trigger=trigger,
        )
        if trace is not None:
            trace.add("Evolution Agent / Experience Update", evolution)
            trace.add("Evolution Agent", self._build_evolution_text(diagnosis, evolution))
        return evolution

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

        exp, created = self.library.add_or_update(
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

    def _build_evolution_text(self, diagnosis, evolution):
        if not diagnosis:
            return "EvolutionAgent 未收到有效诊断，经验库未更新。"
        return (
            f"EvolutionAgent 已处理 {diagnosis.get('error_type', 'UNKNOWN_ERROR')} 诊断，"
            f"经验演化动作：{evolution.get('action', 'skip')}；"
            f"{evolution.get('message', '')}"
        )
