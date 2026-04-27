from core.ace_core import CriticAgent, EvolutionManager


class ReflectorAgent:
    """Evaluates tool feedback and closes the ACE evolution loop."""

    def __init__(self, experience_library):
        self.critic = CriticAgent()
        self.evolution_manager = EvolutionManager(experience_library)

    def evaluate(self, user_input, task_type, tool_name, tool_args, result, trace):
        diagnostic = self.critic.diagnose(user_input, task_type, tool_name, tool_args, result)
        if not diagnostic:
            trace.add("Reflector Agent", "工具反馈未发现需要沉淀的错误模式。")
            return None

        exp, created = self.evolution_manager.evolve(diagnostic, task_type)
        action = "新增经验" if created else "强化已有经验"
        trace.add("Reflector Agent", f"{action}: [{exp['category']}] {exp['strategy']}")
        return exp

    def record_exception(self, task_type, trigger, error_text, trace):
        diagnostic = {
            "category": "工具执行异常",
            "trigger": trigger,
            "problem": f"执行过程中发生异常: {error_text[:160]}",
            "strategy": "记录异常摘要；下一轮优先检查网络、模型服务、工具参数和数据 schema。",
        }
        exp, created = self.evolution_manager.evolve(diagnostic, task_type)
        action = "新增经验" if created else "强化已有经验"
        trace.add("Reflector Agent", f"{action}: {exp['strategy']}")
        return exp

    def learn_from_user_feedback(self, feedback_type, task_type, user_task, assistant_answer, correction=""):
        if feedback_type == "correct":
            category = "用户正反馈"
            problem = f"用户确认该任务结果正确。任务: {user_task[:120]}"
            strategy = "类似任务可优先复用本次上下文解析、工具选择和回答组织方式。"
        elif feedback_type == "incorrect":
            category = "用户负反馈"
            problem = (
                f"用户认为结果不正确。任务: {user_task[:120]} "
                f"原回答摘要: {assistant_answer[:180]}"
            )
            strategy = "类似任务需要重新检查上下文指代、图层选择、字段条件和空间分析参数，不要直接沿用上一次回答。"
        else:
            category = "用户纠正"
            problem = (
                f"用户对结果给出纠正。任务: {user_task[:120]} "
                f"原回答摘要: {assistant_answer[:160]}"
            )
            strategy = f"遇到类似任务时优先遵循用户纠正: {correction[:240]}"

        return self.evolution_manager.library.add_or_update(
            category=category,
            task_type=task_type,
            trigger=f"用户反馈类型={feedback_type}; 用户任务={user_task[:120]}",
            problem=problem,
            strategy=strategy,
            source="user_feedback",
        )
