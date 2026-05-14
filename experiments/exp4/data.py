import json

from .constants import EVALUATION_CONFIG_PATH, WORKBOOK_PATH


def load_workbook():
    return json.loads(WORKBOOK_PATH.read_text(encoding="utf-8"))


def load_evaluation_config():
    if not EVALUATION_CONFIG_PATH.exists():
        return {}
    return json.loads(EVALUATION_CONFIG_PATH.read_text(encoding="utf-8"))


def expand_tasks(workbook):
    total_steps = int(workbook.get("total_steps", 100))
    templates = workbook.get("task_templates") or workbook.get("tasks") or []
    if not templates:
        return []

    tasks = []
    for step in range(1, total_steps + 1):
        template = templates[(step - 1) % len(templates)]
        variant = _variant_for_step(template, step)
        task = {key: value for key, value in template.items() if key != "variants"}
        task["id"] = f"exp4_step_{step:03d}_{template.get('id', 'task')}"
        task["adaptation_step"] = step
        task["query"] = str(template.get("query", "")).format(step=step, variant=variant)
        task["expected_skill"] = template.get("skill")
        task["novelty"] = _novelty(step, template)
        tasks.append(task)
    return tasks


def capability_coverage(tasks):
    counts = {}
    for task in tasks:
        skill = task.get("expected_skill") or task.get("category", "unknown")
        counts[skill] = counts.get(skill, 0) + 1
    return counts


def _variant_for_step(template, step):
    variants = template.get("variants") or [template.get("skill", "general")]
    return variants[(step - 1) % len(variants)]


def _novelty(step, template):
    if step <= 20:
        return "warmup"
    if step <= 60:
        return "transfer"
    if step <= 80:
        return "new_pattern"
    return "retention_retest"
