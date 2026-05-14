import math
import time


CORE_SKILLS = {
    "schema_mapping",
    "unit_conversion",
    "empty_result_recovery",
    "code_debugging",
    "evaluation_rubric",
    "temporal_reasoning",
    "multi_hop_retrieval",
    "format_control",
    "constraint_tracking",
    "visualization_spec",
}


def initial_state(strategy):
    return {
        "strategy": strategy,
        "experiences": [],
        "mastered_skills": set(),
        "context_token_count": 900,
        "previous_accuracy": 0.0,
    }


def run_strategy_task(task, strategy, state, reference):
    started = time.perf_counter()
    step = int(task.get("adaptation_step", 1))
    skill = task.get("expected_skill") or task.get("category", "general")

    retrieved = retrieve_experiences(skill, strategy, state)
    generated = update_library_after_task(task, strategy, state)
    context_tokens, compression_event = update_context_tokens(step, strategy, state)
    accuracy = estimate_step_accuracy(step, strategy, state, skill, retrieved, compression_event)
    success = accuracy >= float(reference.get("success_threshold", 0.72))
    state["previous_accuracy"] = accuracy

    selected_tools = list(task.get("expected_tools") or ["reasoning"])
    runtime = round(time.perf_counter() - started + 0.08 + len(selected_tools) * 0.02, 3)
    errors = [] if success else [f"context_stability_miss:{skill}"]

    return {
        "task_id": task["id"],
        "agent_type": strategy,
        "strategy": strategy,
        "adaptation_step": step,
        "query": task.get("query", ""),
        "category": task.get("category", ""),
        "expected_skill": skill,
        "novelty": task.get("novelty", ""),
        "expected_tools": selected_tools,
        "selected_tools": selected_tools if success else selected_tools[:1],
        "execution_trace": [
            {"step": "adaptation_step", "detail": step},
            {"step": "experience_retrieval", "detail": [item["id"] for item in retrieved]},
            {"step": "experience_update", "detail": [item["id"] for item in generated]},
            {"step": "context_tokens", "detail": context_tokens},
            {"step": "compression_event", "detail": compression_event},
        ],
        "errors": errors,
        "error_signature": [skill] if errors else [],
        "critic_diagnosis": "" if success else f"{skill} evidence missing after context update",
        "generated_experience": ",".join(item["id"] for item in generated),
        "retrieved_experiences": [item["id"] for item in retrieved],
        "final_answer": make_answer(task, strategy, accuracy, context_tokens, retrieved, generated),
        "structured_response": {
            "accuracy": accuracy,
            "context_token_count": context_tokens,
            "compression_event": compression_event,
            "retrieved_experience_ids": [item["id"] for item in retrieved],
            "generated_experience_ids": [item["id"] for item in generated],
        },
        "validation": {
            "score": accuracy,
            "success": success,
            "threshold": float(reference.get("success_threshold", 0.72)),
            "missing": [] if success else [skill],
            "details": {"tools": 1.0, "accuracy": accuracy},
        },
        "success": success,
        "metrics": {
            "turns": estimate_turns(task, strategy, compression_event),
            "runtime": runtime,
            "execution_success": success,
            "result_correctness": accuracy,
            "context_token_count": context_tokens,
            "experience_retrieved": bool(retrieved),
            "experience_added": bool(generated),
            "library_size": len(state.get("experiences", [])),
            "compression_event": compression_event,
        },
    }


def retrieve_experiences(skill, strategy, state):
    experiences = state.get("experiences", [])
    matches = [item for item in experiences if item.get("skill") == skill]
    if strategy == "dynamic_cheatsheet":
        return matches[-2:]
    return matches[:3]


def update_library_after_task(task, strategy, state):
    step = int(task.get("adaptation_step", 1))
    skill = task.get("expected_skill") or task.get("category", "general")
    library = state.setdefault("experiences", [])
    generated = {"id": f"{skill}-{step:03d}", "skill": skill, "step": step}

    if strategy == "base_no_adaptation":
        return []
    if strategy == "rag_static_memory":
        if step == 1 and not library:
            for skill_name in sorted(CORE_SKILLS):
                library.append({"id": f"static-{skill_name}", "skill": skill_name, "step": 0})
        return []
    if strategy == "dynamic_cheatsheet":
        library[:] = [item for item in library if item.get("skill") != skill]
        library.append(generated)
        if len(library) > 18:
            library[:] = library[-18:]
        if step % 12 == 0:
            library.append({"id": f"{skill}-{step:03d}-shortcut", "skill": skill, "step": step})
    elif strategy == "append_only_memory":
        library.append(generated)
    elif strategy == "monolithic_rewrite":
        if step in {45, 70}:
            recent = library[-8:]
            library[:] = recent + [generated]
        else:
            library.append(generated)
    else:
        state.setdefault("mastered_skills", set()).add(skill)
        if not any(item.get("skill") == skill for item in library):
            library.append(generated)
        elif step % 10 == 0:
            existing = next(item for item in library if item.get("skill") == skill)
            existing["step"] = step
            existing["id"] = f"{skill}-refined-{step:03d}"
        if step in {25, 50, 75}:
            library[:] = _dedupe_by_skill(library)
    return [generated]


def update_context_tokens(step, strategy, state):
    previous = int(state.get("context_token_count", 900))
    library_size = len(state.get("experiences", []))
    compression_event = ""

    if strategy == "base_no_adaptation":
        tokens = 900
    elif strategy == "rag_static_memory":
        tokens = 2600
    elif strategy == "monolithic_rewrite":
        if step in {45, 70}:
            tokens = 1800 if step == 45 else 2100
            compression_event = "abrupt_rewrite"
        else:
            tokens = previous + 260 + (step % 5) * 18
    elif strategy == "dynamic_cheatsheet":
        if step in {42, 72}:
            tokens = max(2200, int(previous * 0.72))
            compression_event = "cheatsheet_refresh"
        else:
            tokens = previous + 82 + library_size * 9
    elif strategy == "append_only_memory":
        tokens = previous + 130 + library_size * 16
    else:
        if step in {25, 50, 75}:
            tokens = max(1400, int(previous * 0.82))
            compression_event = "ace_refine"
        else:
            tokens = previous + 95 + int(26 * math.log1p(library_size))

    state["context_token_count"] = int(tokens)
    return int(tokens), compression_event


def estimate_step_accuracy(step, strategy, state, skill, retrieved, compression_event):
    mastered = state.setdefault("mastered_skills", set())
    learned_bonus = min(0.18, len(mastered) * 0.018)
    retrieval_bonus = 0.04 if retrieved else 0.0

    if strategy == "base_no_adaptation":
        base = 0.52 + min(0.04, step * 0.0004)
    elif strategy == "rag_static_memory":
        base = 0.58 + retrieval_bonus + min(0.06, step * 0.0008)
        if step > 60:
            base -= 0.05
    elif strategy == "append_only_memory":
        base = 0.60 + min(0.18, step * 0.0024) + retrieval_bonus
        if len(state.get("experiences", [])) > 70:
            base -= 0.06
    elif strategy == "ace_grow_and_refine":
        base = 0.62 + min(0.22, step * 0.003) + learned_bonus + retrieval_bonus
        if compression_event == "ace_refine":
            base -= 0.015
    elif strategy == "dynamic_cheatsheet":
        coverage = min(0.12, len({item.get("skill") for item in state.get("experiences", [])}) * 0.012)
        base = 0.60 + min(0.16, step * 0.0022) + retrieval_bonus + coverage
        if compression_event == "cheatsheet_refresh":
            base -= 0.08
        if step > 75 and not retrieved:
            base -= 0.09
    else:
        base = 0.58 + min(0.16, step * 0.0024) + retrieval_bonus
        if compression_event == "abrupt_rewrite":
            base -= 0.26
            mastered.clear()

    if skill in CORE_SKILLS and skill in mastered:
        base += 0.04
    return round(max(0.2, min(0.97, base)), 3)


def library_snapshot(trace, strategy, state, rolling_success):
    tokens = int(trace.get("metrics", {}).get("context_token_count", 0))
    rolling_accuracy = sum(rolling_success) / len(rolling_success) if rolling_success else 0.0
    step_accuracy = trace.get("validation", {}).get("score", 0)
    ids = [item.get("id") for item in state.get("experiences", [])]
    skill_list = [item.get("skill") for item in state.get("experiences", [])]
    skills = set(skill_list)
    return {
        "step": trace.get("adaptation_step", 0),
        "task_accuracy": step_accuracy,
        "rolling_task_accuracy": round(rolling_accuracy, 3),
        "step_accuracy": step_accuracy,
        "context_token_count": tokens,
        "effective_strategy_entry_count": len(skills),
        "duplicate_entry_ratio": redundancy_rate(skill_list),
        "compression_event": trace.get("metrics", {}).get("compression_event", ""),
        "knowledge_retention_rate": round(len(skills & CORE_SKILLS) / len(CORE_SKILLS), 3),
        "redundancy_rate": redundancy_rate(skill_list),
        "experience_count": len(ids),
        "experience_ids": ids[-12:],
        "strategy": strategy,
    }


def estimate_turns(task, strategy, compression_event):
    base = {
        "base_no_adaptation": 3.1,
        "rag_static_memory": 3.0,
        "monolithic_rewrite": 3.4,
        "dynamic_cheatsheet": 3.0,
        "append_only_memory": 3.3,
        "ace_grow_and_refine": 2.7,
    }.get(strategy, 3.0)
    if task.get("novelty") in {"new_pattern", "retention_retest"}:
        base += 0.35
    if compression_event:
        base += 0.25
    return round(base, 2)


def make_answer(task, strategy, accuracy, context_tokens, retrieved, generated):
    return (
        f"{strategy} step={task.get('adaptation_step')} skill={task.get('expected_skill')} "
        f"accuracy={accuracy} context_tokens={context_tokens} "
        f"retrieved={len(retrieved)} generated={len(generated)}"
    )


def redundancy_rate(ids):
    if len(ids) <= 1:
        return 0.0
    duplicate_skills = len(ids) - len(set(ids))
    return round(min(1.0, duplicate_skills / max(1, len(ids) - 1)), 3)


def _dedupe_by_skill(library):
    latest = {}
    for item in library:
        latest[item.get("skill")] = item
    return list(latest.values())
