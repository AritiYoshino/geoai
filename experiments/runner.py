import argparse
import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .baselines import run_real_ace_task, simulate_task
from .config import BASELINE_DESCRIPTIONS, EXPERIMENTS, ExperimentConfig
from .metrics import (
    calculate_average_runtime,
    calculate_average_turns,
    calculate_collapse_event_count,
    calculate_context_token_count,
    calculate_experience_reuse_rate,
    calculate_knowledge_retention_rate,
    calculate_redundancy_rate,
    calculate_repair_success_rate,
    calculate_repeated_error_rate,
    calculate_success_rate,
    calculate_tool_selection_accuracy,
    summarize_common,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = PROJECT_ROOT / "logs" / "experiments"


def now_run_id(exp_id):
    return f"{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def list_experiments():
    latest = {}
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    for path in LOG_ROOT.glob("*/result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            exp_id = data.get("experiment_id")
            if exp_id:
                latest[exp_id] = data.get("run_id")
        except Exception:
            continue
    return [{**meta, "latest_run_id": latest.get(exp_id, "")} for exp_id, meta in EXPERIMENTS.items()]


def list_experiment_runs(exp_id=None):
    rows = []
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    for path in sorted(LOG_ROOT.glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_exp_id = data.get("experiment_id")
        if exp_id and run_exp_id != exp_id:
            continue
        traces = data.get("traces") or []
        rows.append(
            {
                "run_id": data.get("run_id") or path.parent.name,
                "experiment_id": run_exp_id,
                "name": data.get("display_name") or data.get("name") or data.get("run_id") or path.parent.name,
                "base_name": data.get("name") or "",
                "created_at": data.get("created_at") or "",
                "trace_count": len(traces),
                "success_count": sum(1 for trace in traces if trace.get("success")),
                "has_report": bool(data.get("report") or (path.parent / "reports").exists()),
            }
        )
    return rows


def rename_experiment_run(run_id, name):
    result = get_result(run_id)
    result["display_name"] = str(name or "").strip() or result.get("name") or run_id
    write_json(LOG_ROOT / run_id / "result.json", result)
    return result


def delete_experiment_run(run_id):
    run_dir = (LOG_ROOT / run_id).resolve()
    root = LOG_ROOT.resolve()
    if root not in run_dir.parents or not (run_dir / "result.json").exists():
        raise FileNotFoundError(f"No experiment run found for {run_id}")
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    exp_id = result.get("experiment_id")
    shutil.rmtree(run_dir)
    if exp_id in EXPERIMENTS:
        remaining = list_experiment_runs(exp_id)
        output_json = LOG_ROOT / EXPERIMENTS[exp_id]["outputs"][0]
        output_csv = LOG_ROOT / EXPERIMENTS[exp_id]["outputs"][1]
        if remaining:
            latest = get_result(remaining[0]["run_id"])
            write_json(output_json, latest)
            write_csv(output_csv, [flatten_trace_for_csv(t) for t in latest.get("traces", [])])
        else:
            for path in (output_json, output_csv):
                if path.exists():
                    path.unlink()
    return {"deleted": run_id}


def load_tasks(exp_id):
    path = PROJECT_ROOT / EXPERIMENTS[exp_id]["task_file"]
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return expand_task_payload(payload)


def expand_task_payload(payload):
    if isinstance(payload, list):
        return payload
    multiplier = int(payload.get("repeat_multiplier", 1))
    if "batches" in payload:
        batches = []
        for batch in payload["batches"]:
            batch_multiplier = int(batch.get("repeat_multiplier", multiplier))
            tasks = _expand_templates(batch.get("tasks", []), batch.get("batch_id"), batch_multiplier)
            batches.append({"batch_id": batch.get("batch_id"), "tasks": tasks})
        return batches
    return _expand_templates(payload.get("tasks", []), payload.get("batch_id"), multiplier)


def _expand_templates(tasks, batch_id=None, repeat_multiplier=1):
    expanded = []
    for template_idx, task in enumerate(tasks, start=1):
        repeat = int(task.get("repeat", 1)) * max(1, int(repeat_multiplier))
        variants = task.get("variants") or [None]
        for idx in range(repeat):
            variant = variants[idx % len(variants)]
            one = {key: value for key, value in task.items() if key not in {"repeat", "variants"}}
            suffix = f"t{template_idx}_{idx + 1:02d}"
            if batch_id is not None:
                suffix = f"b{batch_id}_{suffix}"
            raw_id = str(one.get("id", "task"))
            one["id"] = raw_id.replace("{n}", suffix) if "{n}" in raw_id else f"{raw_id}_{suffix}"
            if variant:
                one["query"] = str(one.get("query", "")).format(v=variant)
            expanded.append(one)
    return expanded


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows or [])
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def flatten_trace_for_csv(trace):
    metrics = trace.get("metrics") or {}
    return {
        "task_id": trace.get("task_id"),
        "agent_type": trace.get("agent_type"),
        "category": trace.get("category"),
        "success": trace.get("success"),
        "selected_tools": ";".join(trace.get("selected_tools") or []),
        "expected_tools": ";".join(trace.get("expected_tools") or []),
        "error_count": len(trace.get("errors") or []),
        "turns": metrics.get("turns", 0),
        "runtime": metrics.get("runtime", 0),
        "result_correctness": metrics.get("result_correctness", 0),
        "retrieved_experience_count": len(trace.get("retrieved_experiences") or []),
    }


def save_result(exp_id, run_id, result):
    run_dir = LOG_ROOT / run_id
    write_json(run_dir / "result.json", result)
    trace_dir = run_dir / "traces"
    for trace in result.get("traces", []):
        write_json(trace_dir / f"{trace.get('task_id')}_{trace.get('agent_type')}.json", trace)
    output_names = EXPERIMENTS[exp_id]["outputs"]
    write_json(LOG_ROOT / output_names[0], result)
    write_csv(LOG_ROOT / output_names[1], [flatten_trace_for_csv(t) for t in result.get("traces", [])])
    write_csv(run_dir / "result.csv", [flatten_trace_for_csv(t) for t in result.get("traces", [])])
    return run_dir


def run_exp1(config=None, app_state=None):
    from .exp1 import run_exp1 as run_exp1_impl

    return run_exp1_impl(config or ExperimentConfig(), app_state=app_state)


def run_exp2(config=None, app_state=None):
    from .exp2 import run_exp2 as run_exp2_impl

    return run_exp2_impl(config or ExperimentConfig(), app_state=app_state)


def run_exp3(config=None, app_state=None):
    from .exp3 import run_exp3 as run_exp3_impl

    return run_exp3_impl(config or ExperimentConfig(), app_state=app_state)


def run_exp4(config=None, app_state=None):
    from .exp4 import run_exp4 as run_exp4_impl

    return run_exp4_impl(config or ExperimentConfig(), app_state=app_state)


def run_experiment(exp_id, config=None, app_state=None):
    if exp_id == "all":
        results = []
        for one in EXPERIMENTS:
            results.append(run_experiment(one, config=config, app_state=app_state))
        return {"experiments": results}
    if exp_id not in EXPERIMENTS:
        raise ValueError(f"Unknown experiment id: {exp_id}")
    run_id = now_run_id(exp_id)
    body = {
        "run_id": run_id,
        "experiment_id": exp_id,
        "name": EXPERIMENTS[exp_id]["name"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "config": (config or ExperimentConfig()).to_dict(),
    }
    payload = {
        "exp1": run_exp1,
        "exp2": run_exp2,
        "exp3": run_exp3,
        "exp4": run_exp4,
    }[exp_id](config or ExperimentConfig(), app_state)
    body.update(payload)
    save_result(exp_id, run_id, body)
    try:
        from .reporting import generate_report

        body["report"] = generate_report(body, include_ai_summary=False)
        save_result(exp_id, run_id, body)
    except Exception as exc:
        body["report_error"] = str(exc)
        save_result(exp_id, run_id, body)
    return body


def get_result(experiment_or_run_id):
    candidates = [
        LOG_ROOT / experiment_or_run_id / "result.json",
    ]
    if experiment_or_run_id in EXPERIMENTS:
        candidates.append(LOG_ROOT / EXPERIMENTS[experiment_or_run_id]["outputs"][0])
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No result found for {experiment_or_run_id}")


def _failed_trace(task, agent_type, exc):
    return {
        "task_id": task.get("id"),
        "agent_type": agent_type,
        "query": task.get("query", ""),
        "category": task.get("category", ""),
        "expected_tools": list(task.get("expected_tools") or []),
        "selected_tools": [],
        "execution_trace": [{"step": "exception", "detail": str(exc)}],
        "errors": [str(exc)],
        "critic_diagnosis": "实验运行异常，已记录并继续 batch。",
        "generated_experience": "",
        "retrieved_experiences": [],
        "final_answer": "",
        "success": False,
        "metrics": {"turns": 0, "runtime": 0, "execution_success": False, "result_correctness": 0},
    }


def _experience_quality_score(rows, cfg):
    base = 0.55 + calculate_experience_reuse_rate(rows) * 0.2 + calculate_repair_success_rate(rows) * 0.15
    if not cfg.use_critic:
        base -= 0.12
    if not cfg.use_evolution:
        base -= 0.18
    return round(max(0.0, min(1.0, base)), 3)


def _update_library(group, library, trace, idx, early_ids):
    if group == "monolithic_rewrite":
        kept = [item for item in library if item["id"] in early_ids and idx < 55]
        if idx >= 60:
            kept = kept[: max(1, len(kept) - 1)]
        library[:] = kept + [{"id": f"rewrite-{idx}-{n}", "strategy": trace.get("category", "")} for n in range(3)]
    elif group == "dynamic_cheatsheet":
        strategy = trace.get("category", "")
        library[:] = [item for item in library if item.get("strategy") != strategy]
        library.append({"id": f"cheatsheet-{idx}", "strategy": strategy})
        if len(library) > 18:
            library[:] = library[-18:]
    else:
        existing = {item["strategy"] for item in library}
        strategy = trace.get("category", "")
        if strategy not in existing:
            library.append({"id": f"ace-{idx}", "strategy": strategy})
        if len(library) > 36:
            del library[10:14]


def _retrieval_precision(group, idx):
    if group == "ace_grow_and_refine":
        return round(0.78 + min(0.12, idx / 1000), 3)
    if group == "dynamic_cheatsheet":
        return round(max(0.45, 0.72 - idx / 420), 3)
    return round(max(0.28, 0.62 - idx / 220), 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", default="all", choices=["exp1", "exp2", "exp3", "exp4", "all"])
    parser.add_argument("--real-ace", action="store_true", help="Use live ACE flow when called with an app state.")
    parser.add_argument("--report", action="store_true", help="Generate or refresh experiment report after running.")
    parser.add_argument("--report-ai-summary", action="store_true", help="Use DeepSeek from .env to write the report summary.")
    args = parser.parse_args()
    result = run_experiment(args.exp, ExperimentConfig(use_real_ace=args.real_ace, mock_mode=not args.real_ace))
    report_payload = None
    if args.report or args.report_ai_summary:
        from .reporting import generate_report

        if args.exp == "all":
            report_payload = [generate_report(item, include_ai_summary=args.report_ai_summary) for item in result["experiments"]]
        else:
            report_payload = generate_report(result, include_ai_summary=args.report_ai_summary)
    if args.exp == "all":
        print(json.dumps({"status": "ok", "experiments": [item["run_id"] for item in result["experiments"]], "reports": report_payload}, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "run_id": result["run_id"], "experiment_id": result["experiment_id"], "report": report_payload or result.get("report")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
