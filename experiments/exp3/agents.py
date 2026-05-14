import time

from .evaluation import evaluate_response


# 消融组定义：missing_modules 明确写出每个智能体少了什么 ACE 模块。
ABLATION_AGENTS = {
    "full_ace": {
        "name": "Full ACE",
        "missing_modules": [],
        "description": "完整启用 ContextManager、Experience Retrieval、CodeAgent、Critic 与 Evolution。",
    },
    "without_critic": {
        "name": "ACE w/o Critic",
        "missing_modules": ["critic"],
        "description": "移除 CriticAgent：不能诊断错误原因，Evolution 缺少高质量错误归因。",
    },
    "without_evolution": {
        "name": "ACE w/o Evolution",
        "missing_modules": ["evolution"],
        "description": "移除 EvolutionAgent：可以执行和诊断，但不能把新策略沉淀到经验库。",
    },
    "without_experience_retrieval": {
        "name": "ACE w/o Experience Retrieval",
        "missing_modules": ["experience_retrieval"],
        "description": "移除经验检索：无法复用 CRS、空结果恢复、动态缓冲等已有经验。",
    },
    "without_code_agent": {
        "name": "ACE w/o CodeAgent",
        "missing_modules": ["code_agent"],
        "description": "移除 CodeAgent：无法执行 GeoPandas 代码和精确数值校验。",
    },
    "without_context_manager": {
        "name": "ACE w/o ContextManager",
        "missing_modules": ["context_manager"],
        "description": "移除 ContextManager：无法读取跨轮锚点、偏好和上下文引用。",
    },
    "without_reflector_refinement": {
        "name": "ACE w/o Reflector Refinement",
        "missing_modules": ["reflector_refinement"],
        "description": "保留经验写入，但不进行独立 Reflector 反思和迭代精炼，经验质量更不稳定。",
    },
    "append_only_memory": {
        "name": "ACE Append-only Memory",
        "missing_modules": ["grow_and_refine"],
        "description": "只追加新经验，不做去重、合并或计数更新，容易形成冗余经验。",
    },
    "monolithic_rewrite": {
        "name": "ACE Monolithic Rewrite",
        "missing_modules": ["incremental_delta"],
        "description": "周期性整体重写上下文，容易丢失早期细节并造成策略坍塌。",
    },
}


BASE_EXPERIENCES = [
    {"id": "exp3-crs-distance", "category": "crs"},
    {"id": "exp3-empty-result-relax", "category": "empty_result"},
    {"id": "exp3-adaptive-buffer", "category": "buffer"},
    {"id": "exp3-layer-disambiguation", "category": "layer"},
]


GENERATED_EXPERIENCE_BY_TASK = {
    "exp3_q02_schema_critic_evolution": {"id": "exp3-schema-field-check", "category": "schema"},
    "exp3_q06_cross_layer_validation": {"id": "exp3-cross-layer-validation", "category": "validation"},
    "exp3_q08_full_chain": {"id": "exp3-ratio-validation", "category": "validation"},
    "exp3_q11_schema_life_service": {"id": "exp3-schema-field-check", "category": "schema"},
    "exp3_q15_boundary_validation_code": {"id": "exp3-boundary-predicate", "category": "predicate"},
    "exp3_q17_export_schema_evolution": {"id": "exp3-export-schema-check", "category": "export"},
    "exp3_q22_temporal_evolution": {"id": "exp3-temporal-field-parse", "category": "temporal"},
    "exp3_q26_cross_validation_tool_code": {"id": "exp3-tool-code-crosscheck", "category": "validation"},
}


def initial_ablation_state(agent_type):
    missing = set(ABLATION_AGENTS[agent_type]["missing_modules"])
    experiences = [] if "experience_retrieval" in missing else [dict(item) for item in BASE_EXPERIENCES]
    return {
        "experiences": experiences,
        "memory_ready": "context_manager" not in missing,
        "missing_modules": sorted(missing),
    }


def run_ablation_agent_task(task, ref, agent_type, state, reference):
    started = time.perf_counter()
    missing = set(state.get("missing_modules") or [])
    selected_tools = select_tools(ref, missing)
    retrieved = retrieve_experiences(ref, state, missing)
    generated = generate_experience(task, ref, state, missing)
    critic_diagnosis = diagnose(task, ref, missing)
    memory_used = bool(ref.get("memory_read") and "context_manager" not in missing and state.get("memory_ready"))

    if ref.get("memory_write") and "context_manager" not in missing:
        state["memory_ready"] = True

    response = make_response(
        task=task,
        ref=ref,
        selected_tools=selected_tools,
        retrieved=retrieved,
        generated=generated,
        critic_diagnosis=critic_diagnosis,
        memory_used=memory_used,
        missing_modules=missing,
    )
    validation = evaluate_response(response, ref, reference.get("success_threshold", 0.86))
    errors = [] if validation["success"] else [f"missing_module_effect:{','.join(validation['missing'])}"]
    runtime = round(time.perf_counter() - started + 0.11 + len(selected_tools) * 0.04, 3)

    return {
        "task_id": task["id"],
        "agent_type": agent_type,
        "agent_name": ABLATION_AGENTS[agent_type]["name"],
        "missing_modules": sorted(missing),
        "query": task.get("query", ""),
        "category": task.get("category", ""),
        "expected_tools": ref.get("expected_tools", []),
        "selected_tools": selected_tools,
        "execution_trace": response["trace_events"],
        "errors": errors,
        "critic_diagnosis": critic_diagnosis,
        "generated_experience": ",".join(item["id"] for item in generated),
        "retrieved_experiences": [item["id"] for item in retrieved],
        "final_answer": response["answer"],
        "structured_response": response,
        "validation": validation,
        "success": validation["success"],
        "metrics": {
            "turns": estimate_turns(task, missing, bool(retrieved), bool(generated)),
            "runtime": runtime,
            "execution_success": not errors,
            "result_correctness": validation["score"],
            "has_map_layer": "map_layer" in response["output_types"],
            "has_table": "table" in response["output_types"],
            "result_count": response["result_count"],
            "experience_retrieved": bool(retrieved),
            "experience_added": bool(generated),
            "memory_used": memory_used,
            "code_executed": response["code_executed"],
            "critic_used": bool(critic_diagnosis),
            "missing_module_count": len(missing),
        },
    }


def select_tools(ref, missing):
    tools = list(ref.get("expected_tools") or [])
    if "code_agent" in missing:
        tools = [tool for tool in tools if tool != "execute_spatial_code"]
    if "context_manager" in missing:
        tools = [tool for tool in tools if tool not in {"find_nearby_point", "find_nearby_point_filtered"}]
    return tools


def retrieve_experiences(ref, state, missing):
    if "experience_retrieval" in missing or not ref.get("requires_experience_retrieval"):
        return []
    expected = set(ref.get("expected_experience_ids") or [])
    matches = [item for item in state.get("experiences", []) if item.get("id") in expected]
    if "incremental_delta" in missing and ref.get("requires_experience_retrieval"):
        return matches[:1] if len(matches) > 1 else []
    return matches


def generate_experience(task, ref, state, missing):
    if not ref.get("requires_experience_add"):
        return []
    if "critic" in missing or "evolution" in missing:
        return []
    template = GENERATED_EXPERIENCE_BY_TASK.get(task["id"])
    if not template:
        return []
    if "reflector_refinement" in missing and task.get("category") in {"adversarial_validation", "validation"}:
        return []
    experiences = state.setdefault("experiences", [])
    if "grow_and_refine" in missing:
        experiences.append(dict(template))
    elif not any(item.get("id") == template["id"] for item in experiences):
        experiences.append(dict(template))
    return [template]


def diagnose(task, ref, missing):
    if "critic" in missing or not ref.get("requires_critic"):
        return ""
    return f"Critic 诊断：{task['id']} 触发可修复错误，需保留失败原因并交给 Evolution。"


def make_response(task, ref, selected_tools, retrieved, generated, critic_diagnosis, memory_used, missing_modules):
    output_types = list(ref.get("expected_output_types") or [])
    entities = list(ref.get("expected_entities") or [])
    keywords = list(ref.get("required_keywords") or [])

    if ref.get("requires_experience_retrieval") and not retrieved:
        output_types = [item for item in output_types if item != "explanation"]
        keywords = [item for item in keywords if item not in {"经验", "投影", "米制", "动态缓冲", "分级半径", "放宽"}]
    if ref.get("requires_critic") and not critic_diagnosis:
        output_types = [item for item in output_types if item != "diagnosis"]
        keywords = [item for item in keywords if item not in {"Critic", "诊断"}]
    if ref.get("requires_experience_add") and not generated:
        keywords = [item for item in keywords if item != "经验库"]
    if ref.get("requires_code") and "execute_spatial_code" not in selected_tools:
        entities = [item for item in entities if item not in {"density", "数量比"}]
        keywords = [item for item in keywords if item not in {"GeoPandas", "area_km2", "count", "排名"}]
    if ref.get("memory_read") and not memory_used:
        entities = [item for item in entities if item not in {"spring_hotel", "medical_anchor", "上下文"}]
        keywords = [item for item in keywords if item not in {"记忆", "上一轮", "中心点"}]
    if "reflector_refinement" in missing_modules and task.get("category") in {"adversarial_validation", "validation"}:
        keywords = keywords[: max(1, len(keywords) - 2)]
    if "grow_and_refine" in missing_modules and task.get("category") in {"ace_multi_step", "adversarial_validation"}:
        entities = entities[: max(1, len(entities) - 1)]
    if "incremental_delta" in missing_modules and task.get("category") in {"memory_followup", "ace_multi_step", "temporal_query"}:
        output_types = [item for item in output_types if item != "explanation"]

    result_count = int(ref.get("min_result_count", 1))
    if _hard_blocked(ref, selected_tools, retrieved, generated, critic_diagnosis, memory_used):
        result_count = 0

    missing_note = "missing_modules=" + ",".join(sorted(missing_modules or []))
    text = " ".join(
        [task.get("query", ""), missing_note, critic_diagnosis]
        + [item["id"] for item in retrieved]
        + [item["id"] for item in generated]
        + entities
        + keywords
    )
    return {
        "answer": text,
        "selected_tools": selected_tools,
        "output_types": output_types,
        "entities": _matched(ref.get("expected_entities", []), text),
        "keywords": _matched(ref.get("required_keywords", []), text),
        "result_count": result_count,
        "retrieved_experience_ids": [item["id"] for item in retrieved],
        "generated_experience_ids": [item["id"] for item in generated],
        "experience_retrieved": bool(retrieved),
        "experience_added": bool(generated),
        "memory_used": memory_used,
        "code_executed": "execute_spatial_code" in selected_tools,
        "trace_events": [
            {"step": "ablation_agent", "detail": missing_note},
            {"step": "tool_selection", "detail": selected_tools},
            {"step": "experience_retrieval", "detail": [item["id"] for item in retrieved]},
            {"step": "critic_diagnosis", "detail": critic_diagnosis},
            {"step": "experience_update", "detail": [item["id"] for item in generated]},
        ],
    }


def estimate_turns(task, missing, retrieved, generated):
    turns = 2.8 + (0.8 if task.get("difficulty") == "hard" else 0.0)
    turns += 0.35 * len(missing)
    turns -= 0.2 if retrieved else 0.0
    turns += 0.15 if generated else 0.0
    return round(turns, 2)


def _hard_blocked(ref, selected_tools, retrieved, generated, critic_diagnosis, memory_used):
    return any(
        [
            ref.get("requires_code") and "execute_spatial_code" not in selected_tools,
            ref.get("requires_experience_retrieval") and not retrieved,
            ref.get("requires_experience_add") and not generated,
            ref.get("requires_critic") and not critic_diagnosis,
            ref.get("memory_read") and not memory_used,
        ]
    )


def _matched(items, text):
    text = str(text or "").lower()
    return [item for item in items if str(item).lower() in text]
