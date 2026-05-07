from core.jsonl_logger import log_evolution


def evolve_from_error(
    experience_library,
    task_type,
    error_text,
    code,
    diagnosis,
    trigger="",
    source="critic",
):
    if not diagnosis:
        payload = {
            "updated": False,
            "action": "skip",
            "experience_id": "",
            "message": "未产生有效诊断结果，因此没有更新经验库。",
        }
        log_evolution(
            {
                "task_type": task_type,
                "trigger": trigger,
                "updated": False,
                "action": "skip",
                "reason": "no_diagnosis",
            }
        )
        return payload

    if not diagnosis.get("experience_candidate", False):
        payload = {
            "updated": False,
            "action": "skip",
            "experience_id": "",
            "message": f"诊断结果 {diagnosis.get('error_type', 'UNKNOWN_ERROR')} 仅作为观察记录，未写入经验库。",
        }
        log_evolution(
            {
                "task_type": task_type,
                "trigger": trigger,
                "updated": False,
                "action": "skip",
                "reason": diagnosis.get("error_type", "UNKNOWN_ERROR"),
            }
        )
        return payload

    trigger_text = trigger or f"task_type={task_type}"
    problem = f"{diagnosis['reason']} 原始错误信息: {str(error_text)[:240]}"
    if code:
        problem += f" 相关代码片段: {str(code)[:240]}"

    strategy = diagnosis["strategy"]
    if diagnosis.get("code_hint"):
        strategy = f"{strategy} 代码提示: {diagnosis['code_hint']}"

    exp, created = experience_library.add_or_update(
        category=diagnosis["error_type"],
        task_type=task_type,
        trigger=trigger_text,
        problem=problem,
        strategy=strategy,
        source=source,
        outcome="failure",
    )
    action = "add" if created else "update"
    payload = {
        "updated": True,
        "action": action,
        "experience_id": exp.get("id", ""),
        "message": f"已针对 {diagnosis['error_type']} 完成经验{('新增' if action == 'add' else '更新')}。",
    }
    log_evolution(
        {
            "task_type": task_type,
            "trigger": trigger_text,
            "updated": True,
            "action": action,
            "experience_id": exp.get("id", ""),
            "error_type": diagnosis["error_type"],
        }
    )
    return payload


class EvolutionManager:
    """Lightweight experience evolution manager used by EvolutionAgent."""

    def __init__(self, library):
        self.library = library

    def evolve(self, diagnosis, task_type, error_text="", code="", trigger="", source="critic"):
        return evolve_from_error(
            experience_library=self.library,
            task_type=task_type,
            error_text=error_text,
            code=code,
            diagnosis=diagnosis,
            trigger=trigger,
            source=source,
        )
