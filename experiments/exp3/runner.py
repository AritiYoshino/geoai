from .agents import ABLATION_AGENTS, initial_ablation_state, run_ablation_agent_task
from .constants import PROJECT_ROOT, REFERENCE_PATH, WORKBOOK_PATH
from .data import capability_coverage, expand_tasks, load_reference, load_workbook
from .evaluation import summarize_rows


def run_exp3(config=None, app_state=None):
    workbook = load_workbook()
    reference = load_reference()
    tasks = expand_tasks(workbook)
    traces = []

    for agent_type in ABLATION_AGENTS:
        state = initial_ablation_state(agent_type)
        for task in tasks:
            ref = reference["answers"][task.get("reference_id") or task["id"]]
            traces.append(run_ablation_agent_task(task, ref, agent_type, state, reference))

    groups = {}
    for agent_type, meta in ABLATION_AGENTS.items():
        rows = [row for row in traces if row.get("agent_type") == agent_type]
        groups[agent_type] = {
            **summarize_rows(rows),
            "name": meta["name"],
            "missing_modules": meta["missing_modules"],
            "description": meta["description"],
        }

    return {
        "frameworks": ABLATION_AGENTS,
        "dataset": {
            "workbook": str(WORKBOOK_PATH.relative_to(PROJECT_ROOT)),
            "reference_answers": str(REFERENCE_PATH.relative_to(PROJECT_ROOT)),
            "task_count": len(tasks),
            "success_threshold": reference.get("success_threshold", 0.86),
            "capability_coverage": capability_coverage(tasks),
            "reference_system": reference.get("reference_system", {}),
        },
        "groups": groups,
        "traces": traces,
    }
