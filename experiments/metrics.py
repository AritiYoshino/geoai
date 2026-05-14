import math
import re
from collections import Counter


def _records(records):
    return list(records or [])


def _safe_div(num, den):
    return float(num) / float(den) if den else 0.0


def _metric(record, name, default=0):
    return (record.get("metrics") or {}).get(name, record.get(name, default))


def calculate_success_rate(records):
    rows = _records(records)
    return _safe_div(sum(1 for row in rows if row.get("success")), len(rows))


def calculate_tool_selection_accuracy(records):
    rows = _records(records)
    scores = []
    for row in rows:
        expected = set(row.get("expected_tools") or [])
        selected = set(row.get("selected_tools") or [])
        if not expected:
            continue
        scores.append(_safe_div(len(expected & selected), len(expected)))
    return sum(scores) / len(scores) if scores else 0.0


def calculate_execution_success_rate(records):
    rows = _records(records)
    return _safe_div(
        sum(1 for row in rows if not row.get("errors") and _metric(row, "execution_success", row.get("success"))),
        len(rows),
    )


def calculate_result_correctness(records):
    rows = _records(records)
    return _safe_div(sum(float(_metric(row, "result_correctness", 0)) for row in rows), len(rows))


def calculate_average_turns(records):
    rows = _records(records)
    return _safe_div(sum(float(_metric(row, "turns", row.get("turns", 1))) for row in rows), len(rows))


def calculate_average_runtime(records):
    rows = _records(records)
    return _safe_div(sum(float(_metric(row, "runtime", row.get("runtime", 0))) for row in rows), len(rows))


def calculate_repeated_error_rate(records):
    rows = _records(records)
    signatures = [tuple(row.get("error_signature") or row.get("errors") or []) for row in rows if row.get("errors")]
    if not signatures:
        return 0.0
    counts = Counter(signatures)
    repeated = sum(count for sig, count in counts.items() if sig and count > 1)
    return _safe_div(repeated, len(rows))


def calculate_repair_success_rate(records):
    rows = _records(records)
    repairable = [row for row in rows if _metric(row, "repair_attempted", False)]
    return _safe_div(sum(1 for row in repairable if _metric(row, "repair_success", False)), len(repairable))


def calculate_experience_reuse_rate(records):
    rows = _records(records)
    return _safe_div(sum(1 for row in rows if row.get("retrieved_experiences")), len(rows))


def calculate_knowledge_retention_rate(snapshots, early_experience_ids=None):
    rows = _records(snapshots)
    if not rows:
        return 0.0
    expected = set(early_experience_ids or rows[0].get("early_experience_ids") or [])
    if not expected:
        return float(rows[-1].get("knowledge_retention_rate", 0.0))
    retained = set(rows[-1].get("experience_ids") or [])
    return _safe_div(len(expected & retained), len(expected))


def calculate_redundancy_rate(experiences):
    rows = _records(experiences)
    if len(rows) < 2:
        return 0.0
    fingerprints = []
    for exp in rows:
        text = " ".join(str(exp.get(key, "")) for key in ("category", "problem", "strategy", "trigger"))
        tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower()))
        fingerprints.append(tokens)
    redundant = 0
    comparisons = 0
    for idx, left in enumerate(fingerprints):
        for right in fingerprints[idx + 1:]:
            comparisons += 1
            union = left | right
            if union and len(left & right) / len(union) >= 0.72:
                redundant += 1
    return _safe_div(redundant, comparisons)


def calculate_context_token_count(text_or_experiences):
    if isinstance(text_or_experiences, str):
        text = text_or_experiences
    else:
        text = " ".join(str(item) for item in _records(text_or_experiences))
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_tokens = len(re.findall(r"[A-Za-z0-9_]+", text))
    punctuation = len(re.findall(r"[^\s\w\u4e00-\u9fff]", text))
    return int(math.ceil(chinese_chars * 0.75 + latin_tokens + punctuation * 0.25))


def calculate_collapse_event_count(snapshots):
    rows = _records(snapshots)
    events = 0
    for prev, cur in zip(rows, rows[1:]):
        prev_tokens = float(prev.get("context_token_count", prev.get("context_tokens", 0.0)))
        cur_tokens = float(cur.get("context_token_count", cur.get("context_tokens", 0.0)))
        accuracy_drop = float(prev.get("task_accuracy", 1.0)) - float(cur.get("task_accuracy", 1.0))
        token_collapse = prev_tokens >= 8000 and cur_tokens <= prev_tokens * 0.35
        if token_collapse and accuracy_drop >= 0.12:
            events += 1
    return events


def summarize_common(records):
    rows = _records(records)
    return {
        "task_success_rate": calculate_success_rate(rows),
        "tool_selection_accuracy": calculate_tool_selection_accuracy(rows),
        "execution_success_rate": calculate_execution_success_rate(rows),
        "result_correctness": calculate_result_correctness(rows),
        "average_turns": calculate_average_turns(rows),
        "average_runtime": calculate_average_runtime(rows),
        "user_intervention_count": sum(int(_metric(row, "user_intervention_count", 0)) for row in rows),
        "error_count": sum(len(row.get("errors") or []) for row in rows),
    }
