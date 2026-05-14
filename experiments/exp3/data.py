import json

from .constants import REFERENCE_PATH, WORKBOOK_PATH


def load_workbook():
    return json.loads(WORKBOOK_PATH.read_text(encoding="utf-8"))


def load_reference():
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def expand_tasks(workbook):
    multiplier = max(1, int(workbook.get("repeat_multiplier", 1)))
    tasks = []
    for task in workbook.get("tasks", []):
        for idx in range(multiplier):
            one = dict(task)
            if multiplier > 1:
                one["id"] = f"{task['id']}_r{idx + 1:02d}"
                one["reference_id"] = task["id"]
            tasks.append(one)
    return tasks


def capability_coverage(tasks):
    counts = {}
    for task in tasks:
        for capability in task.get("capabilities", []):
            counts[capability] = counts.get(capability, 0) + 1
    return counts
