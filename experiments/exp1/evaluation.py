def evaluate_structured_response(response, ref, threshold):
    missing = []
    scores = []

    expected_tools = set(ref.get("expected_tools") or [])
    selected_tools = set(response.get("selected_tools") or [])
    if expected_tools:
        tool_score = len(expected_tools & selected_tools) / len(expected_tools)
        if tool_score <= 0 and not any(tool in selected_tools for tool in expected_tools):
            missing.append("expected_tools")
        scores.append(("tools", tool_score, 0.24))

    expected_outputs = set(ref.get("expected_output_types") or [])
    output_types = set(response.get("output_types") or [])
    if expected_outputs:
        output_score = len(expected_outputs & output_types) / len(expected_outputs)
        if output_score < 1:
            missing.append("output_types")
        scores.append(("outputs", output_score, 0.18))

    entities = ref.get("expected_entities") or []
    entity_hits = set(response.get("entities") or [])
    if entities:
        entity_score = len(entity_hits) / len(entities)
        if entity_score < 0.55:
            missing.append("entities")
        scores.append(("entities", entity_score, 0.16))

    keywords = ref.get("required_keywords") or []
    keyword_hits = set(response.get("keywords") or [])
    if keywords:
        keyword_score = len(keyword_hits) / len(keywords)
        if keyword_score < 0.5:
            missing.append("keywords")
        scores.append(("keywords", keyword_score, 0.12))

    result_ok = response.get("result_count", 0) >= int(ref.get("min_result_count", 0))
    if not result_ok:
        missing.append("result_count")
    scores.append(("result_count", 1.0 if result_ok else 0.0, 0.1))

    for key, label in (
        ("memory_read", "memory_used"),
        ("memory_write", "memory_written"),
        ("requires_experience_retrieval", "experience_retrieved"),
        ("requires_experience_add", "experience_added"),
        ("requires_code", "code_executed"),
    ):
        if ref.get(key):
            ok = bool(response.get(label))
            if not ok:
                missing.append(label)
            scores.append((label, 1.0 if ok else 0.0, 0.2))

    total_weight = sum(weight for _, _, weight in scores) or 1
    score = sum(value * weight for _, value, weight in scores) / total_weight
    details = {name: round(value, 3) for name, value, _ in scores}
    return {
        "score": round(score, 3),
        "success": score >= float(threshold),
        "threshold": float(threshold),
        "missing": missing,
        "details": details,
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
        "memory_success_rate": _conditional_rate(rows, "memory_used"),
        "experience_retrieval_rate": _conditional_rate(rows, "experience_retrieved"),
        "experience_add_rate": _conditional_rate(rows, "experience_added"),
        "code_execution_success_rate": _conditional_rate(rows, "code_executed"),
        "user_intervention_count": 0,
        "error_count": sum(len(row.get("errors") or []) for row in rows),
    }


def _average(values):
    rows = list(values)
    return sum(float(value or 0) for value in rows) / len(rows) if rows else 0.0


def _conditional_rate(rows, metric_name):
    relevant = [row for row in rows if row.get("metrics", {}).get(metric_name) or _reference_requires(row, metric_name)]
    if not relevant:
        return 0.0
    return sum(1 for row in relevant if row.get("metrics", {}).get(metric_name)) / len(relevant)


def _reference_requires(row, metric_name):
    missing = set(row.get("validation", {}).get("missing") or [])
    mapping = {
        "memory_used": "memory_used",
        "experience_retrieved": "experience_retrieved",
        "experience_added": "experience_added",
        "code_executed": "code_executed",
    }
    return mapping.get(metric_name) in missing
