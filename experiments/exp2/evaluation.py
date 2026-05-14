from collections import Counter


def evaluate_response(response, ref, threshold):
    missing = []
    scores = []
    _score_set("tools", response.get("selected_tools"), ref.get("expected_tools"), 0.2, missing, scores)
    _score_set("outputs", response.get("output_types"), ref.get("expected_output_types"), 0.14, missing, scores)
    _score_set("entities", response.get("entities"), ref.get("expected_entities"), 0.12, missing, scores, partial_floor=0.55)
    _score_set("keywords", response.get("keywords"), ref.get("required_keywords"), 0.1, missing, scores, partial_floor=0.5)

    result_ok = response.get("result_count", 0) >= int(ref.get("min_result_count", 0))
    if not result_ok:
        missing.append("result_count")
    scores.append(("result_count", 1.0 if result_ok else 0.0, 0.08))

    if ref.get("requires_experience_retrieval"):
        expected = set(ref.get("expected_experience_ids") or [])
        retrieved = set(response.get("retrieved_experience_ids") or [])
        value = len(expected & retrieved) / len(expected) if expected else float(bool(retrieved))
        if value <= 0:
            missing.append("experience_retrieved")
        scores.append(("experience_retrieved", value, 0.16))

    if ref.get("requires_experience_add"):
        expected = set(ref.get("expected_generated_experience_ids") or [])
        generated = set(response.get("generated_experience_ids") or [])
        value = len(expected & generated) / len(expected) if expected else float(bool(generated))
        if value <= 0:
            missing.append("experience_added")
        scores.append(("experience_added", value, 0.14))

    if ref.get("requires_code"):
        ok = bool(response.get("code_executed"))
        if not ok:
            missing.append("code_executed")
        scores.append(("code_executed", 1.0 if ok else 0.0, 0.12))

    if ref.get("memory_read"):
        ok = bool(response.get("memory_used"))
        if not ok:
            missing.append("memory_used")
        scores.append(("memory_used", 1.0 if ok else 0.0, 0.12))

    total_weight = sum(weight for _, _, weight in scores) or 1.0
    score = sum(value * weight for _, value, weight in scores) / total_weight
    return {
        "score": round(score, 3),
        "success": score >= float(threshold),
        "threshold": float(threshold),
        "missing": missing,
        "details": {name: round(value, 3) for name, value, _ in scores},
    }


def summarize_rows(rows):
    total = len(rows) or 1
    return {
        "task_success_rate": sum(1 for row in rows if row.get("success")) / total,
        "tool_selection_accuracy": _average(row.get("validation", {}).get("details", {}).get("tools", 0) for row in rows),
        "execution_success_rate": sum(1 for row in rows if row.get("metrics", {}).get("execution_success")) / total,
        "result_correctness": _average(row.get("metrics", {}).get("result_correctness", 0) for row in rows),
        "average_turns": _average(row.get("metrics", {}).get("turns", 0) for row in rows),
        "average_runtime": _average(row.get("metrics", {}).get("runtime", 0) for row in rows),
        "experience_reuse_rate": sum(1 for row in rows if row.get("retrieved_experiences")) / total,
        "experience_add_rate": sum(1 for row in rows if row.get("generated_experience")) / total,
        "repair_success_rate": _repair_success_rate(rows),
        "repeated_error_rate": _repeated_error_rate(rows),
        "user_intervention_count": sum(int(row.get("metrics", {}).get("user_intervention_count", 0)) for row in rows),
        "error_count": sum(len(row.get("errors") or []) for row in rows),
    }


def batch_summary(rows):
    summary = summarize_rows(rows)
    summary["new_experience_count"] = len([row for row in rows if row.get("generated_experience")])
    return summary


def _score_set(name, actual, expected, weight, missing, scores, partial_floor=1.0):
    expected = set(expected or [])
    actual = set(actual or [])
    if not expected:
        return
    value = len(expected & actual) / len(expected)
    if value < partial_floor:
        missing.append(name)
    scores.append((name, value, weight))


def _average(values):
    rows = list(values)
    return sum(float(value or 0) for value in rows) / len(rows) if rows else 0.0


def _repair_success_rate(rows):
    repairable = [row for row in rows if row.get("metrics", {}).get("repair_attempted")]
    if not repairable:
        return 0.0
    return sum(1 for row in repairable if row.get("metrics", {}).get("repair_success")) / len(repairable)


def _repeated_error_rate(rows):
    signatures = [tuple(row.get("error_signature") or row.get("errors") or []) for row in rows if row.get("errors")]
    if not signatures:
        return 0.0
    counts = Counter(signatures)
    repeated = sum(count for sig, count in counts.items() if sig and count > 1)
    return repeated / (len(rows) or 1)
