from .agents import commit_pending_experiences, initial_state, run_structured_agent_task
from .constants import AGENT_DESCRIPTIONS, AGENT_ORDER, PROJECT_ROOT, REFERENCE_PATH, WORKBOOK_PATH
from .data import capability_coverage, expand_batches, flatten_batches, load_reference, load_workbook
from .evaluation import batch_summary, summarize_rows


def run_exp2(config=None, app_state=None):
    workbook = load_workbook()
    reference = load_reference()
    batches = expand_batches(workbook)
    all_tasks = flatten_batches(batches)
    traces = []
    states = {agent_type: initial_state(agent_type) for agent_type in AGENT_ORDER}

    for batch in batches:
        for agent_type in AGENT_ORDER:
            for task in batch.get("tasks", []):
                ref = reference["answers"][task.get("reference_id") or task["id"]]
                traces.append(run_structured_agent_task(task, ref, agent_type, states[agent_type], reference))
        if batch.get("batch_id") == 2:
            committed = commit_pending_experiences(states["ace_agent"])
            for trace in reversed(traces):
                if trace.get("batch_id") == 2 and trace.get("agent_type") == "ace_agent":
                    trace.setdefault("execution_trace", []).append(
                        {
                            "step": "stage_end_experience_commit",
                            "detail": [item.get("id") for item in committed],
                        }
                    )
                    break

    groups = {}
    for agent_type in AGENT_ORDER:
        rows = [row for row in traces if row.get("agent_type") == agent_type]
        groups[agent_type] = summarize_rows(rows)

    batch_metrics = []
    for batch in batches:
        batch_id = batch.get("batch_id")
        row = {"batch_id": batch_id}
        for agent_type in AGENT_ORDER:
            rows = [trace for trace in traces if trace.get("batch_id") == batch_id and trace.get("agent_type") == agent_type]
            summary = batch_summary(rows)
            prefix = _batch_prefix(agent_type)
            row[f"{prefix}_success_rate"] = summary["task_success_rate"]
            row[f"{prefix}_experience_reuse_rate"] = summary["experience_reuse_rate"]
            row[f"{prefix}_new_experience_count"] = summary["new_experience_count"]
            if agent_type == "ace_agent":
                row["repeated_error_rate"] = summary["repeated_error_rate"]
                row["repair_success_rate"] = summary["repair_success_rate"]
                row["experience_reuse_rate"] = summary["experience_reuse_rate"]
                row["average_turns"] = summary["average_turns"]
                row["new_experience_count"] = summary["new_experience_count"]
        row["baseline_success_rate"] = row.get("base_success_rate", 0)
        row["ace_success_rate"] = row.get("ace_success_rate", 0)
        batch_metrics.append(row)

    return {
        "frameworks": AGENT_DESCRIPTIONS,
        "dataset": {
            "workbook": str(WORKBOOK_PATH.relative_to(PROJECT_ROOT)),
            "reference_answers": str(REFERENCE_PATH.relative_to(PROJECT_ROOT)),
            "task_count": len(all_tasks),
            "batch_count": len(batches),
            "success_threshold": reference.get("success_threshold", 0.86),
            "capability_coverage": capability_coverage(all_tasks),
            "reference_system": reference.get("reference_system", {}),
        },
        "groups": groups,
        "batch_metrics": batch_metrics,
        "traces": traces,
    }


def _batch_prefix(agent_type):
    return {"base_agent": "base", "rag_agent": "rag", "ace_agent": "ace"}[agent_type]
