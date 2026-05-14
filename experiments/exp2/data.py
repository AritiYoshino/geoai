import json

from .constants import REFERENCE_PATH, WORKBOOK_PATH


def load_workbook():
    return json.loads(WORKBOOK_PATH.read_text(encoding="utf-8"))


def load_reference():
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def expand_batches(workbook):
    multiplier = max(1, int(workbook.get("repeat_multiplier", 1)))
    batches = []
    for batch in workbook.get("batches", []):
        batch_multiplier = max(1, int(batch.get("repeat_multiplier", multiplier)))
        tasks = []
        for task in batch.get("tasks", []):
            variants = task.get("variants") or [None]
            repeat = max(1, int(task.get("repeat", 1))) * batch_multiplier
            for repeat_idx in range(repeat):
                for variant_idx, variant in enumerate(variants):
                    idx = repeat_idx * len(variants) + variant_idx
                    one = {key: value for key, value in task.items() if key not in {"repeat", "variants"}}
                    one["reference_id"] = task["id"]
                    one["batch_id"] = batch.get("batch_id")
                    one["batch_theme"] = batch.get("theme", "")
                    if variant:
                        suffix = str(variant.get("id") or f"v{idx + 1:02d}")
                        one["id"] = f"{task['id']}_{suffix}"
                        values = {key: value for key, value in variant.items() if key != "id"}
                        one["query"] = str(one.get("query", "")).format(**values)
                    elif repeat > 1:
                        one["id"] = f"{task['id']}_r{idx + 1:02d}"
                    tasks.append(one)
        batches.append({"batch_id": batch.get("batch_id"), "theme": batch.get("theme", ""), "tasks": tasks})
    return batches


def flatten_batches(batches):
    return [task for batch in batches for task in batch.get("tasks", [])]


def capability_coverage(tasks):
    counts = {}
    for task in tasks:
        for capability in task.get("capabilities", []):
            counts[capability] = counts.get(capability, 0) + 1
    return counts
