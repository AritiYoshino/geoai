from .agents import run_main_system_agent_task, run_structured_agent_task
from .constants import AGENT_DESCRIPTIONS, AGENT_ORDER, PROJECT_ROOT, REFERENCE_PATH, WORKBOOK_PATH, seed_experiences
from .data import capability_coverage, expand_tasks, load_reference, load_workbook
from .evaluation import summarize_rows


def run_exp1(config=None, app_state=None):
    workbook = load_workbook()
    reference = load_reference()
    tasks = expand_tasks(workbook)
    traces = []

    for agent_type in AGENT_ORDER:
        state = {
            "recent_task_ids": [],
            "memory_ready": False,
            "experiences": seed_experiences(agent_type),
        }
        for task in tasks:
            ref = reference["answers"][task["id"]]
            if app_state is not None and getattr(config, "use_real_ace", False):
                trace = run_main_system_agent_task(task, ref, agent_type, app_state, state, reference)
            else:
                trace = run_structured_agent_task(task, ref, agent_type, state, reference)
            traces.append(trace)
        state.clear()

    groups = {}
    for agent_type in AGENT_ORDER:
        rows = [row for row in traces if row.get("agent_type") == agent_type]
        groups[agent_type] = summarize_rows(rows)

    return {
        "frameworks": AGENT_DESCRIPTIONS,
        "dataset": {
            "workbook": str(WORKBOOK_PATH.relative_to(PROJECT_ROOT)),
            "reference_answers": str(REFERENCE_PATH.relative_to(PROJECT_ROOT)),
            "task_count": len(tasks),
            "success_threshold": reference.get("success_threshold", 0.72),
            "capability_coverage": capability_coverage(tasks),
        },
        "groups": groups,
        "traces": traces,
    }
