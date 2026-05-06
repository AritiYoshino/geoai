import glob
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime


OUTPUT_ROOT = os.path.join("experiments", "experiment_outputs")
EXP_DIRS = {
    "exp1": os.path.join(OUTPUT_ROOT, "exp1"),
    "exp2": os.path.join(OUTPUT_ROOT, "exp2"),
    "exp3": os.path.join(OUTPUT_ROOT, "exp3"),
    "exp4": os.path.join(OUTPUT_ROOT, "exp4"),
}

BENCHMARK_TASK_TYPES = [
    {"type": "query", "label": "属性查询", "geoanalyst_dimension": "spatial query / attribute filtering"},
    {"type": "search", "label": "POI 检索", "geoanalyst_dimension": "geospatial information retrieval"},
    {"type": "nearby", "label": "邻近分析", "geoanalyst_dimension": "proximity analysis"},
    {"type": "buffer", "label": "缓冲区分析", "geoanalyst_dimension": "buffer workflow"},
    {"type": "overlay", "label": "叠加分析", "geoanalyst_dimension": "overlay / intersection"},
    {"type": "cluster", "label": "聚类分析", "geoanalyst_dimension": "clustering / hotspot"},
    {"type": "statistics", "label": "统计汇总", "geoanalyst_dimension": "spatial statistics"},
    {"type": "mapping", "label": "制图与高亮", "geoanalyst_dimension": "visualization / mapping"},
    {"type": "code", "label": "空间代码生成", "geoanalyst_dimension": "spatial code generation"},
    {"type": "feedback", "label": "错误反馈恢复", "geoanalyst_dimension": "workflow repair"},
]


def build_thesis_evidence():
    exp1 = _latest_summary("exp1")
    exp2 = _latest_summary("exp2")
    exp3 = _latest_summary("exp3")
    exp4 = _latest_summary("exp4")
    experiences = _load_experiences()

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "readiness": _readiness(exp1, exp2, exp3, exp4, experiences),
        "benchmark_alignment": _benchmark_alignment(exp1),
        "baseline_comparison": _baseline_comparison(exp1),
        "experience_analysis": _experience_analysis(experiences),
        "code_evolution": _code_evolution(exp1),
        "ablation_summary": _ablation_summary(exp2, exp3, exp4),
        "source_runs": {
            "exp1": _run_meta(exp1),
            "exp2": _run_meta(exp2),
            "exp3": _run_meta(exp3),
            "exp4": _run_meta(exp4),
        },
        "missing_items": _missing_items(exp1, exp2, exp3, exp4, experiences),
    }


def _latest_summary(exp_name):
    base = EXP_DIRS[exp_name]
    files = sorted(
        glob.glob(os.path.join(base, f"{exp_name}_*", "summary.json")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not files:
        return {}
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("run_dir", os.path.relpath(os.path.dirname(files[0])))
    return data


def _load_experiences():
    paths = [
        os.path.join("data", "ace_experience_library.json"),
        os.path.join("data", "experience_libraries", "*.json"),
        os.path.join("experiments", "exp1", "exp1_experience_library.json"),
        os.path.join("experiments", "exp2", "exp2_experience_library.json"),
        os.path.join("experiments", "exp3", "exp3_experience_library.json"),
        os.path.join("experiments", "exp4", "exp4_experience_library.json"),
    ]
    items = []
    seen = set()
    for pattern in paths:
        for path in glob.glob(pattern):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            for exp in data if isinstance(data, list) else []:
                key = exp.get("id") or "|".join(str(exp.get(k, "")) for k in ("category", "problem", "strategy"))
                scoped_key = f"{path}:{key}"
                if scoped_key in seen:
                    continue
                seen.add(scoped_key)
                item = dict(exp)
                item["_source_path"] = path
                items.append(item)
    return items


def _readiness(exp1, exp2, exp3, exp4, experiences):
    checks = [
        ("GeoAnalystBench 任务对齐", bool(_benchmark_alignment(exp1)["rows"])),
        ("Zero-shot/Base vs ACE 指标对比", bool(exp1.get("base") and exp1.get("ace"))),
        ("经验库分类统计", len(experiences) > 0),
        ("代码演化轨迹样例", bool(_code_evolution(exp1)["items"])),
        ("消融实验汇总", bool(exp2.get("variants") or exp3.get("systems") or exp4.get("systems"))),
    ]
    done = sum(1 for _, ok in checks if ok)
    return {
        "score": round(done / len(checks) * 100, 1),
        "checks": [{"name": name, "completed": ok} for name, ok in checks],
    }


def _benchmark_alignment(exp1):
    tasks = _exp1_tasks(exp1)
    counts = Counter(_normalize_task_type(t.get("task_type", "")) for t in tasks)
    rows = []
    for item in BENCHMARK_TASK_TYPES:
        count = counts.get(item["type"], 0)
        rows.append({
            **item,
            "task_count": count,
            "coverage": "covered" if count else "missing",
            "suggested_min_tasks": 3,
            "gap": max(0, 3 - count),
        })
    covered = sum(1 for row in rows if row["task_count"] > 0)
    return {
        "coverage_rate": round(covered / len(rows) * 100, 1),
        "total_task_types": len(rows),
        "covered_task_types": covered,
        "rows": rows,
    }


def _baseline_comparison(exp1):
    metrics = [
        ("task_completion_rate", "任务完成率"),
        ("tool_success_rate", "工具调用成功率"),
        ("code_success_rate", "代码执行成功率"),
        ("accuracy_rate", "结果准确率"),
        ("error_rate", "错误率"),
    ]
    base = exp1.get("base", {})
    ace = exp1.get("ace", {})
    rows = []
    for key, label in metrics:
        base_value = float(base.get(key, 0) or 0)
        ace_value = float(ace.get(key, 0) or 0)
        delta = ace_value - base_value
        rows.append({
            "metric": key,
            "label": label,
            "base": round(base_value, 2),
            "ace": round(ace_value, 2),
            "delta": round(delta, 2),
            "direction": "lower_is_better" if key == "error_rate" else "higher_is_better",
        })
    for key, label in [
        ("experience_hit_rate", "经验复用命中率"),
        ("error_recovery_rate", "错误恢复率"),
        ("preference_persistence_rate", "偏好保持率"),
    ]:
        rows.append({
            "metric": key,
            "label": label,
            "base": None,
            "ace": round(float(ace.get(key, 0) or 0), 2),
            "delta": None,
            "direction": "ace_only",
        })
    return {"rows": rows, "task_details": exp1.get("task_details", [])[:80]}


def _experience_analysis(experiences):
    category_counts = Counter(_normalize_category(exp.get("category", "")) for exp in experiences)
    task_type_counts = Counter()
    source_counts = Counter()
    quality_rows = []
    for exp in experiences:
        for task_type in exp.get("task_types", []) or ["unknown"]:
            task_type_counts[_normalize_task_type(task_type)] += 1
        source_counts[exp.get("source") or os.path.basename(exp.get("_source_path", "")) or "unknown"] += 1
        quality_rows.append({
            "id": exp.get("id", ""),
            "category": exp.get("category", ""),
            "task_types": exp.get("task_types", []),
            "confidence": float(exp.get("confidence", 0) or 0),
            "success_count": int(exp.get("success_count", 0) or 0),
            "fail_count": int(exp.get("fail_count", 0) or 0),
            "strategy": exp.get("strategy", "")[:160],
            "source_path": exp.get("_source_path", ""),
        })
    quality_rows.sort(key=lambda row: (row["confidence"], row["success_count"] - row["fail_count"]), reverse=True)
    return {
        "total": len(experiences),
        "category_counts": [{"category": k, "count": v} for k, v in category_counts.most_common()],
        "task_type_counts": [{"task_type": k, "count": v} for k, v in task_type_counts.most_common()],
        "source_counts": [{"source": k, "count": v} for k, v in source_counts.most_common()],
        "top_experiences": quality_rows[:20],
    }


def _code_evolution(exp1):
    items = []
    for task in exp1.get("task_details", []) or []:
        calls = task.get("tool_calls", []) or []
        answer = task.get("answer_preview", "")
        has_code = any((c.get("name") == "execute_spatial_code") for c in calls if isinstance(c, dict))
        has_error = task.get("tool_failures", 0) or task.get("has_error")
        if has_code or has_error or task.get("code_executed"):
            items.append({
                "task_id": task.get("task_id"),
                "mode": task.get("mode"),
                "task": task.get("task"),
                "task_type": task.get("task_type"),
                "stage": _infer_code_stage(task),
                "tool_calls": calls,
                "error": task.get("error", ""),
                "answer_preview": answer,
                "code_success": task.get("code_success"),
                "error_recovered": task.get("error_recovered"),
            })
    return {"items": items[:30]}


def _ablation_summary(exp2, exp3, exp4):
    return {
        "module_ablation": {
            "variants": exp2.get("variants", {}),
            "contributions": exp2.get("contributions", []),
        },
        "memory_degradation": {
            "systems": exp3.get("systems", {}),
            "decay_curve": exp3.get("decay_curve", []),
        },
        "long_context": {
            "systems": exp4.get("systems", {}),
            "interval_stats": exp4.get("interval_stats", []),
        },
    }


def _missing_items(exp1, exp2, exp3, exp4, experiences):
    missing = []
    alignment = _benchmark_alignment(exp1)
    for row in alignment["rows"]:
        if row["gap"]:
            missing.append(f"{row['label']} 任务不足：当前 {row['task_count']} 个，建议至少 3 个。")
    if not (exp1.get("base") and exp1.get("ace")):
        missing.append("尚未形成 Base LLM 与 ACE 的同批任务对比结果。")
    if not experiences:
        missing.append("经验库为空，无法支撑经验演化分类分析。")
    if not exp2.get("variants"):
        missing.append("消融实验二尚未生成结果。")
    if not exp3.get("systems"):
        missing.append("记忆抗退化实验三尚未生成结果。")
    if not exp4.get("systems"):
        missing.append("长上下文实验四尚未生成结果。")
    if not _code_evolution(exp1)["items"]:
        missing.append("缺少可展示的代码演化/错误修复样例。")
    return missing


def _exp1_tasks(exp1):
    if exp1.get("suite", {}).get("tasks"):
        return exp1["suite"]["tasks"]
    details = exp1.get("task_details", [])
    unique = {}
    for task in details:
        unique[task.get("task_id")] = task
    if unique:
        return list(unique.values())
    suite_path = os.path.join("experiments", "exp1", "exp1_suite.json")
    if os.path.exists(suite_path):
        with open(suite_path, "r", encoding="utf-8") as f:
            return json.load(f).get("tasks", [])
    return []


def _run_meta(summary):
    if not summary:
        return {"available": False}
    return {
        "available": True,
        "experiment": summary.get("experiment", ""),
        "run_name": summary.get("run_name", ""),
        "run_dir": summary.get("run_dir", ""),
        "timestamp": summary.get("timestamp", ""),
    }


def _normalize_task_type(task_type):
    text = str(task_type).lower()
    mapping = {
        "query+map": "mapping",
        "memory": "feedback",
        "preference_memory": "feedback",
        "context_reference": "feedback",
        "hotspot": "cluster",
        "spatial_code": "code",
    }
    if text in mapping:
        return mapping[text]
    if "cluster" in text or "hotspot" in text:
        return "cluster"
    if "buffer" in text:
        return "buffer"
    if "overlay" in text or "intersect" in text:
        return "overlay"
    if "stat" in text or "统计" in text:
        return "statistics"
    if "map" in text or "mapping" in text:
        return "mapping"
    if "code" in text:
        return "code"
    return text or "unknown"


def _normalize_category(category):
    text = str(category)
    rules = [
        ("字段验证", r"字段|FIELD"),
        ("坐标系冲突", r"CRS|坐标|投影"),
        ("空结果恢复", r"空|empty|未找到"),
        ("结果规模控制", r"规模|过多|截断"),
        ("代码安全与执行", r"代码|import|执行|Traceback"),
        ("上下文记忆", r"记忆|偏好|上下文|指代"),
        ("用户反馈", r"反馈|纠正"),
    ]
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return text or "未分类"


def _infer_code_stage(task):
    if task.get("error_recovered"):
        return "诊断后修复成功"
    if task.get("code_success"):
        return "代码执行成功"
    if task.get("code_executed"):
        return "代码执行失败或待修复"
    if task.get("has_error"):
        return "工具/流程异常"
    return "工具调用样例"
