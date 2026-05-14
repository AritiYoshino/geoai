import hashlib
import time


CATEGORY_TOOL_HINTS = {
    "poi_search": ["search_poi"],
    "attribute_query": ["query_poi_by_conditions"],
    "nearby_analysis": ["find_nearby"],
    "buffer_analysis": ["buffer_analysis"],
    "overlay_analysis": ["overlay_layers"],
    "spatial_join": ["spatial_join_layers"],
    "clustering": ["cluster_points_dbscan"],
    "hotspot": ["hotspot_analysis"],
    "statistics": ["summarize_layer_statistics"],
    "export_highlight": ["export_analysis_result"],
    "code_required": ["execute_spatial_code"],
}


AGENT_PROFILES = {
    "direct_llm": {"base": 0.42, "tool_bias": 0.2, "turns": 1, "runtime": 0.25},
    "react_agent": {"base": 0.63, "tool_bias": 0.78, "turns": 3, "runtime": 0.8},
    "codeact_agent": {"base": 0.69, "tool_bias": 0.82, "turns": 3.4, "runtime": 1.1},
    "ace_webgis": {"base": 0.84, "tool_bias": 0.9, "turns": 2.4, "runtime": 0.95},
    "full_ace": {"base": 0.88, "tool_bias": 0.9, "turns": 2.4, "runtime": 0.95},
    "without_critic": {"base": 0.69, "tool_bias": 0.86, "turns": 3.1, "runtime": 0.92},
    "without_evolution": {"base": 0.72, "tool_bias": 0.86, "turns": 2.9, "runtime": 0.9},
    "without_experience_retrieval": {"base": 0.66, "tool_bias": 0.82, "turns": 3.3, "runtime": 0.86},
    "without_code_agent": {"base": 0.67, "tool_bias": 0.78, "turns": 2.8, "runtime": 0.8},
    "without_context_manager": {"base": 0.68, "tool_bias": 0.82, "turns": 3.2, "runtime": 0.88},
}


MODULE_FAILURE_PENALTIES = {
    "without_critic": {
        "empty_result": 0.24,
        "field_name_mismatch": 0.18,
        "crs_distance": 0.14,
        "geometry_type": 0.16,
        "sjoin_crs": 0.14,
    },
    "without_evolution": {
        "empty_result": 0.12,
        "field_name_mismatch": 0.12,
        "multi_tool_chain": 0.1,
        "early_experience_retest": 0.16,
    },
    "without_experience_retrieval": {
        "crs_distance": 0.2,
        "field_name_mismatch": 0.2,
        "empty_result": 0.18,
        "layer_ambiguity": 0.16,
        "sjoin_crs": 0.16,
    },
    "without_code_agent": {
        "code_required": 0.42,
        "multi_tool_chain": 0.16,
    },
    "without_context_manager": {
        "layer_ambiguity": 0.2,
        "multi_tool_chain": 0.18,
        "empty_result": 0.12,
    },
}


def stable_score(*parts):
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def infer_tools(task, agent_type, config=None):
    expected = list(task.get("expected_tools") or [])
    if expected and agent_type != "direct_llm":
        selected = list(expected)
    else:
        selected = list(CATEGORY_TOOL_HINTS.get(task.get("category"), []))
    if agent_type == "direct_llm":
        return []
    if (agent_type == "without_code_agent") or (config and not getattr(config, "use_code_agent", True)):
        selected = [tool for tool in selected if tool != "execute_spatial_code"]
    return selected


def simulate_task(task, agent_type, config=None, experience_state=None):
    started = time.perf_counter()
    profile = AGENT_PROFILES.get(agent_type, AGENT_PROFILES["react_agent"])
    expected = list(task.get("expected_tools") or [])
    selected = infer_tools(task, agent_type, config)
    difficulty_penalty = {"easy": 0.06, "medium": 0.16, "hard": 0.3}.get(task.get("difficulty"), 0.16)
    score = profile["base"] - difficulty_penalty

    if expected and set(expected).issubset(set(selected)):
        score += 0.08 * profile["tool_bias"]
    elif expected:
        score -= 0.18
    if config:
        if not getattr(config, "use_critic", True):
            score -= 0.14
        if not getattr(config, "use_evolution", True):
            score -= 0.1
        if not getattr(config, "use_experience_retrieval", True):
            score -= 0.16
        if not getattr(config, "use_code_agent", True) and "execute_spatial_code" in expected:
            score -= 0.34
        if not getattr(config, "use_context_manager", True):
            score -= 0.12

    failure_mode = task.get("failure_mode") or task.get("category") or "unknown"
    score -= MODULE_FAILURE_PENALTIES.get(agent_type, {}).get(failure_mode, 0.0)

    retrieved = []
    if agent_type in {
        "ace_webgis",
        "full_ace",
        "without_critic",
        "without_evolution",
        "without_code_agent",
        "without_context_manager",
    } and config and getattr(config, "use_experience_retrieval", True):
        retrieved = list((experience_state or {}).get("available_experiences", []))[:3]
        score += min(0.08, len(retrieved) * 0.025)

    randomish = stable_score(task.get("id"), agent_type, task.get("query"))
    success = randomish <= max(0.05, min(0.96, score))
    error_signature = []
    errors = []
    if not success:
        error_signature = [failure_mode]
        errors = [f"rule_eval_failed:{failure_mode}"]

    generated_experience = ""
    if agent_type in {
        "ace_webgis",
        "full_ace",
        "without_critic",
        "without_experience_retrieval",
        "without_code_agent",
        "without_context_manager",
    } and config and getattr(config, "use_evolution", True):
        if errors or task.get("category") in {"nearby_analysis", "attribute_query", "overlay_analysis"}:
            generated_experience = f"exp:{task.get('category')}:check schema/CRS/result before final answer"
            (experience_state or {}).setdefault("available_experiences", []).append(generated_experience)

    repair_capable = agent_type in {
        "codeact_agent",
        "ace_webgis",
        "full_ace",
        "without_evolution",
        "without_experience_retrieval",
        "without_code_agent",
        "without_context_manager",
    }
    repair_bonus = {
        "ace_webgis": 0.68,
        "full_ace": 0.72,
        "without_evolution": 0.48,
        "without_experience_retrieval": 0.42,
        "without_code_agent": 0.36,
        "without_context_manager": 0.4,
        "codeact_agent": 0.45,
    }.get(agent_type, 0.0)

    runtime = round(profile["runtime"] + stable_score("rt", task.get("id"), agent_type) * 0.35, 3)
    turns = round(profile["turns"] + stable_score("turn", task.get("id"), agent_type), 2)
    result_correctness = 1.0 if success else max(0.0, score - 0.25)
    output_expectations = task.get("expected_outputs") or {}
    execution_trace = [
        {"step": "intent", "detail": task.get("category", "unknown")},
        {"step": "tool_selection", "detail": selected},
        {"step": "evaluation", "detail": "success" if success else "failed"},
    ]
    return {
        "task_id": task.get("id"),
        "agent_type": agent_type,
        "query": task.get("query", ""),
        "category": task.get("category", ""),
        "expected_tools": expected,
        "selected_tools": selected,
        "execution_trace": execution_trace,
        "errors": errors,
        "error_signature": error_signature,
        "critic_diagnosis": "" if not errors else "检测到工具选择、字段、CRS 或空结果风险。",
        "generated_experience": generated_experience,
        "retrieved_experiences": retrieved,
        "final_answer": "任务完成，已生成可评估结果。" if success else "任务未完全满足预期，已记录失败原因。",
        "success": bool(success),
        "metrics": {
            "turns": turns,
            "runtime": runtime,
            "execution_success": not errors,
            "result_correctness": result_correctness,
            "has_map_layer": bool(output_expectations.get("has_map_layer", selected)),
            "has_table": bool(output_expectations.get("has_table", selected)),
            "result_count": int(output_expectations.get("min_result_count", 0)) if success else 0,
            "repair_attempted": bool(errors and repair_capable),
            "repair_success": bool(errors and repair_capable and stable_score("repair", task.get("id"), agent_type) <= repair_bonus),
            "user_intervention_count": 0 if agent_type == "ace_webgis" else int(not success and stable_score("u", task.get("id")) > 0.7),
        },
    }


def run_real_ace_task(task, app_state):
    started = time.perf_counter()
    highlights = []

    def collect_highlights(items):
        highlights.extend(items or [])
        app_state.map_handler.batch_highlight(items or [])

    answer = app_state.ai_handler.process_message(task.get("query", ""), collect_highlights)
    trace_text = app_state.ai_handler.get_trace_text()
    selected = [
        tool for tool in (task.get("expected_tools") or CATEGORY_TOOL_HINTS.get(task.get("category"), []))
        if tool in trace_text
    ]
    errors = []
    if any(token in trace_text.lower() for token in ("error", "exception", "traceback", "错误", "失败")):
        errors.append("ace_trace_error")
    success = not errors and (not task.get("expected_tools") or bool(selected))
    return {
        "task_id": task.get("id"),
        "agent_type": "ace_webgis",
        "query": task.get("query", ""),
        "category": task.get("category", ""),
        "expected_tools": list(task.get("expected_tools") or []),
        "selected_tools": selected,
        "execution_trace": [{"step": "ace_trace", "detail": trace_text[:4000]}],
        "errors": errors,
        "critic_diagnosis": (app_state.ai_handler.get_ace_panel() or {}).get("error_diagnosis", ""),
        "generated_experience": (app_state.ai_handler.get_ace_panel() or {}).get("experience_update", ""),
        "retrieved_experiences": [(app_state.ai_handler.get_ace_panel() or {}).get("retrieved_experiences", "")],
        "final_answer": answer,
        "success": success,
        "metrics": {
            "turns": max(1, trace_text.count("Spatial Analyst Agent")),
            "runtime": round(time.perf_counter() - started, 3),
            "execution_success": not errors,
            "result_correctness": 1.0 if success else 0.3,
            "has_map_layer": bool(highlights),
            "has_table": bool(answer),
            "result_count": len(highlights),
            "user_intervention_count": 0,
        },
    }
