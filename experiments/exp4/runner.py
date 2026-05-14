from .agents import initial_state, library_snapshot, run_strategy_task
from .constants import (
    COLLAPSE_ACCURACY_DROP,
    COLLAPSE_TOKEN_DROP_RATIO,
    COLLAPSE_TOKEN_HIGH_WATERMARK,
    EVALUATION_CONFIG_PATH,
    PROJECT_ROOT,
    STRATEGIES,
    WORKBOOK_PATH,
)
from .data import capability_coverage, expand_tasks, load_evaluation_config, load_workbook
from .evaluation import summarize_rows


def run_exp4(config=None, app_state=None):
    workbook = load_workbook()
    evaluation_config = load_evaluation_config()
    tasks = expand_tasks(workbook)
    traces = []
    snapshots = {strategy: [] for strategy in STRATEGIES}

    for strategy in STRATEGIES:
        state = initial_state(strategy)
        recent_success = []
        for task in tasks:
            trace = run_strategy_task(task, strategy, state, evaluation_config)
            traces.append(trace)
            recent_success.append(trace.get("validation", {}).get("score", 0))
            snapshots[strategy].append(library_snapshot(trace, strategy, state, recent_success[-10:]))
        annotate_snapshot_events(snapshots[strategy])

    groups = {}
    for strategy, meta in STRATEGIES.items():
        rows = [trace for trace in traces if trace.get("agent_type") == strategy]
        summary = summarize_rows(rows)
        final_snapshot = snapshots[strategy][-1] if snapshots[strategy] else {}
        groups[strategy] = {
            **summary,
            "name": meta["name"],
            "description": meta["description"],
            "collapse_event_count": collapse_event_count(snapshots[strategy]),
            "context_sudden_shorten_count": context_sudden_shorten_count(snapshots[strategy]),
            "performance_sudden_drop_count": performance_sudden_drop_count(snapshots[strategy]),
            "final_task_accuracy": final_snapshot.get("task_accuracy", 0),
            "final_context_token_count": final_snapshot.get("context_token_count", 0),
            "final_effective_strategy_entry_count": final_snapshot.get("effective_strategy_entry_count", 0),
            "final_duplicate_entry_ratio": final_snapshot.get("duplicate_entry_ratio", 0),
            "max_context_token_count": max((row.get("context_token_count", 0) for row in snapshots[strategy]), default=0),
            "knowledge_retention_rate": final_snapshot.get("knowledge_retention_rate", 0),
            "final_redundancy_rate": final_snapshot.get("redundancy_rate", 0),
        }

    return {
        "frameworks": STRATEGIES,
        "dataset": {
            "workbook": str(WORKBOOK_PATH.relative_to(PROJECT_ROOT)),
            "evaluation_config": str(EVALUATION_CONFIG_PATH.relative_to(PROJECT_ROOT)),
            "task_count": len(tasks),
            "success_threshold": evaluation_config.get("success_threshold", 0.72),
            "rolling_window": 10,
            "collapse_definition": {
                "token_high_watermark": COLLAPSE_TOKEN_HIGH_WATERMARK,
                "token_drop_ratio": COLLAPSE_TOKEN_DROP_RATIO,
                "accuracy_drop": COLLAPSE_ACCURACY_DROP,
            },
            "capability_coverage": capability_coverage(tasks),
        },
        "groups": groups,
        "snapshots": snapshots,
        "traces": traces,
    }


def collapse_event_count(rows):
    count = 0
    previous = None
    for row in rows:
        if previous:
            prev_tokens = previous.get("context_token_count", 0)
            cur_tokens = row.get("context_token_count", 0)
            accuracy_drop = previous.get("task_accuracy", 0) - row.get("task_accuracy", 0)
            token_collapse = (
                prev_tokens >= COLLAPSE_TOKEN_HIGH_WATERMARK
                and cur_tokens <= prev_tokens * COLLAPSE_TOKEN_DROP_RATIO
            )
            if token_collapse and accuracy_drop >= COLLAPSE_ACCURACY_DROP:
                count += 1
        previous = row
    return count


def context_sudden_shorten_count(rows):
    count = 0
    previous = None
    for row in rows:
        if previous:
            prev_tokens = previous.get("context_token_count", 0)
            cur_tokens = row.get("context_token_count", 0)
            if prev_tokens >= COLLAPSE_TOKEN_HIGH_WATERMARK and cur_tokens <= prev_tokens * 0.65:
                count += 1
        previous = row
    return count


def performance_sudden_drop_count(rows):
    count = 0
    previous = None
    for row in rows:
        if previous:
            accuracy_drop = previous.get("task_accuracy", 0) - row.get("task_accuracy", 0)
            if accuracy_drop >= COLLAPSE_ACCURACY_DROP:
                count += 1
        previous = row
    return count


def annotate_snapshot_events(rows):
    shorten_count = 0
    drop_count = 0
    previous = None
    for row in rows:
        shorten_event = False
        drop_event = False
        if previous:
            prev_tokens = previous.get("context_token_count", 0)
            cur_tokens = row.get("context_token_count", 0)
            accuracy_drop = previous.get("task_accuracy", 0) - row.get("task_accuracy", 0)
            shorten_event = prev_tokens >= COLLAPSE_TOKEN_HIGH_WATERMARK and cur_tokens <= prev_tokens * 0.65
            drop_event = accuracy_drop >= COLLAPSE_ACCURACY_DROP
        if shorten_event:
            shorten_count += 1
        if drop_event:
            drop_count += 1
        row["context_sudden_shorten_event"] = shorten_event
        row["performance_sudden_drop_event"] = drop_event
        row["context_sudden_shorten_count"] = shorten_count
        row["performance_sudden_drop_count"] = drop_count
        previous = row
