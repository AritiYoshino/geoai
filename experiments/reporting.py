import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .config import BASELINE_DESCRIPTIONS, EXPERIMENTS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = PROJECT_ROOT / "logs" / "experiments"
GEODATA_ROOT = PROJECT_ROOT / "data" / "geodata"


METRIC_GLOSSARY = [
    ("任务成功率", "success_rate / task_success_rate", "成功 trace 数 / trace 总数。success=true 记为 1，否则为 0。"),
    ("工具选择准确率", "tool_selection_accuracy", "对每条 trace 计算 |expected_tools ∩ selected_tools| / |expected_tools|，再对有效 trace 求平均。"),
    ("执行成功率", "execution_success_rate", "无 errors 且 metrics.execution_success=true 的 trace 数 / trace 总数。"),
    ("结果正确率", "result_correctness", "metrics.result_correctness 的算术平均值，取值范围 0-1。"),
    ("平均轮数", "average_turns", "metrics.turns 的算术平均值，用于衡量交互/推理链路长度。"),
    ("平均耗时", "average_runtime / average_latency", "metrics.runtime 的算术平均值，单位为秒。"),
    ("用户干预次数", "user_intervention_count", "所有 trace 的 metrics.user_intervention_count 求和。"),
    ("错误数", "error_count", "所有 trace 的 errors 列表长度求和。"),
    ("重复错误率", "repeated_error_rate", "出现重复 error_signature 的错误 trace 数 / trace 总数。"),
    ("修复成功率", "repair_success_rate / self_repair_rate", "repair_attempted=true 的 trace 中 repair_success=true 的比例。"),
    ("经验复用率", "experience_reuse_rate", "retrieved_experiences 非空的 trace 数 / trace 总数。"),
    ("知识保留率", "knowledge_retention_rate", "Exp4 最终快照中仍保留的早期经验数 / 早期经验总数。"),
    ("冗余率", "redundancy_rate", "经验文本指纹两两 Jaccard 相似度 >= 0.72 的组合数 / 组合总数。"),
    ("上下文 token 数", "context_token_count", "中文字符、英文 token 和标点的近似加权计数，用于观察上下文膨胀。"),
    ("有效策略条目数量", "effective_strategy_entry_count", "Exp4 每步上下文中去重后的有效策略/能力条目数。"),
    ("重复条目比例", "duplicate_entry_ratio", "Exp4 每步上下文中重复经验条目占比，用于观察动态速查表或经验更新策略的冗余累积。"),
    ("上下文突然缩短次数", "context_sudden_shorten_count", "Exp4 中高位上下文 token 数突然缩短到前一步 65% 以下的次数。"),
    ("性能突然下降次数", "performance_sudden_drop_count", "Exp4 中相邻 adaptation step 任务准确率下降 >=0.12 的次数。"),
    ("Collapse 事件数", "collapse_event_count", "Exp4 中相邻 adaptation step 出现高位 token 骤降到低位，且任务准确率同步下降的次数。"),
]


DESIGN_NOTES = {
    "exp1": "实验一采用“习题册 + 参考答案”评测设计，比较 Base Agent、RAG Agent 与 ACE Agent。三组尽量复用主系统工具/代码/Agent 链路，区别在于是否启用历史对话记忆、经验库检索和经验写入；成功率由返回结构与参考答案的匹配分数决定。",
    "exp2": "实验二将任务按“基础阶段、学习阶段、最终小测”三批连续输入。BASE 无经验库，RAG 只能检索静态初始经验库，ACE 在第二阶段收集新错误模式并在阶段结束后统一提交经验，第三阶段再检验这些新增经验是否带来 ACE > RAG > BASE 的性能阶梯。",
    "exp3": "实验三围绕 ACE 的关键模块做消融，对比完整 ACE 与去掉 Critic、Evolution、经验检索、CodeAgent、ContextManager 后的性能变化。",
    "exp4": "实验四采用 100 个任务顺序输入的连续在线学习过程，比较周期性重写、Dynamic Cheatsheet 和 ACE 增长-精炼三种上下文更新策略，重点观察 context token 曲线和准确率曲线是否出现同步坍塌。",
}


TRACE_FIELD_NOTES = [
    ("task_id", "展开后的任务编号；包含模板编号、重复轮次或 batch 信息。"),
    ("agent_type", "执行该 trace 的框架、消融组或经验库策略。"),
    ("query", "自然语言 GIS 任务文本。"),
    ("category", "任务类别，例如 POI 检索、邻近分析、叠加分析、热点分析等。"),
    ("expected_tools", "任务设计时标注的期望工具链，用于计算工具选择准确率。"),
    ("selected_tools", "系统实际选择或模拟选择的工具链。"),
    ("execution_trace", "意图识别、工具选择、执行评估等关键步骤记录。"),
    ("errors / error_signature", "运行中出现的错误及其归一化签名，用于重复错误统计。"),
    ("critic_diagnosis", "CriticAgent 产生的结构化诊断，消融时可为空或弱化。"),
    ("retrieved_experiences", "本次任务检索到的经验条目，用于经验复用率和经验有效性分析。"),
    ("generated_experience", "任务后沉淀的新经验，用于观察 Evolution 是否产生可复用知识。"),
    ("metrics", "单条 trace 的可计算指标，如 turns、runtime、execution_success、result_correctness、repair_success。"),
    ("structured_response", "实验一的新结构化返回，包含 selected_tools、output_types、entities、keywords、memory/experience/code 证据。"),
    ("validation", "实验一按参考答案自动评分的结果，包含总分、阈值、缺失项和分项得分。"),
]


def generate_report(result_or_id, include_ai_summary=False):
    result = _coerce_result(result_or_id)
    exp_id = result.get("experiment_id")
    run_id = result.get("run_id") or f"{exp_id}_report"
    report_dir = LOG_ROOT / run_id / "reports"
    chart_dir = report_dir / "charts"
    report_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    charts = _write_charts(result, chart_dir)
    ai_summary = _generate_ai_summary(result) if include_ai_summary else ""
    sections = _build_sections(result, charts, ai_summary)

    markdown = _render_markdown(sections)
    html_text = _render_html(sections)
    md_path = report_dir / f"{run_id}_report.md"
    html_path = report_dir / f"{run_id}_report.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    return {
        "run_id": run_id,
        "report_id": f"{run_id}_report",
        "title": _report_title(run_id),
        "markdown_path": str(md_path.relative_to(PROJECT_ROOT)),
        "html_path": str(html_path.relative_to(PROJECT_ROOT)),
        "markdown_url": f"/experiment-reports/{run_id}/{md_path.name}?download=1",
        "html_url": f"/experiment-reports/{run_id}/{html_path.name}",
        "charts": [str(path.relative_to(PROJECT_ROOT)) for path in charts],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "ai_summary_enabled": bool(include_ai_summary and ai_summary),
    }


def list_reports(run_id=None, exp_id=None):
    reports = []
    for report_dir in sorted(LOG_ROOT.glob("*/reports"), key=lambda p: p.stat().st_mtime, reverse=True):
        current_run_id = report_dir.parent.name
        try:
            result = _coerce_result(current_run_id)
        except Exception:
            result = {}
        if run_id and current_run_id != run_id:
            continue
        if exp_id and result.get("experiment_id") != exp_id:
            continue
        meta = _read_report_meta(report_dir)
        for html_path in sorted(report_dir.glob("*_report.html"), key=lambda p: p.stat().st_mtime, reverse=True):
            stem = html_path.stem
            md_path = report_dir / f"{stem}.md"
            reports.append(
                {
                    "report_id": stem,
                    "run_id": current_run_id,
                    "experiment_id": result.get("experiment_id", ""),
                    "title": meta.get("title") or stem,
                    "created_at": meta.get("updated_at") or datetime.fromtimestamp(html_path.stat().st_mtime).isoformat(timespec="seconds"),
                    "html_url": f"/experiment-reports/{current_run_id}/{html_path.name}",
                    "markdown_url": f"/experiment-reports/{current_run_id}/{md_path.name}?download=1" if md_path.exists() else "",
                    "html_path": str(html_path.relative_to(PROJECT_ROOT)),
                    "markdown_path": str(md_path.relative_to(PROJECT_ROOT)) if md_path.exists() else "",
                }
            )
    return reports


def rename_report(run_id, title):
    report_dir = _safe_report_dir(run_id)
    meta = _read_report_meta(report_dir)
    meta["title"] = str(title or "").strip() or f"{run_id}_report"
    meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
    (report_dir / "report_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def delete_report(run_id, report_id=None):
    report_dir = _safe_report_dir(run_id)
    if report_id:
        for path in report_dir.glob(f"{report_id}*"):
            if path.is_file():
                path.unlink()
        meta_path = report_dir / "report_meta.json"
        if meta_path.exists():
            meta_path.unlink()
        charts_dir = report_dir / "charts"
        if charts_dir.exists():
            shutil.rmtree(charts_dir)
    else:
        shutil.rmtree(report_dir)
    return {"deleted": report_id or run_id}


def _report_title(run_id):
    report_dir = LOG_ROOT / run_id / "reports"
    return _read_report_meta(report_dir).get("title") or f"{run_id}_report"


def _read_report_meta(report_dir):
    path = report_dir / "report_meta.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_report_dir(run_id):
    report_dir = (LOG_ROOT / run_id / "reports").resolve()
    root = LOG_ROOT.resolve()
    if root not in report_dir.parents or not report_dir.exists():
        raise FileNotFoundError(f"No reports found for {run_id}")
    return report_dir


def _coerce_result(result_or_id):
    if isinstance(result_or_id, dict):
        return result_or_id
    from .runner import get_result

    return get_result(str(result_or_id))


def _write_charts(result, chart_dir):
    if os.getenv("GEOAI_REPORT_SKIP_CHARTS", "").strip().lower() in {"1", "true", "yes"}:
        return []
    exp_id = result.get("experiment_id")
    charts = []
    if exp_id in {"exp1", "exp3"}:
        groups = result.get("groups") or {}
        labels = list(groups.keys())
        values = [groups[key].get("task_success_rate", groups[key].get("success_rate", 0)) for key in labels]
        charts.append(_bar_chart(chart_dir / "success_rate.png", labels, values, "Success rate by group", "Success rate"))
    elif exp_id == "exp2":
        rows = result.get("batch_metrics") or []
        x_labels = [f"B{row.get('batch_id')}" for row in rows]
        series = {
            "BASE": [row.get("base_success_rate", row.get("baseline_success_rate", 0)) for row in rows],
            "RAG": [row.get("rag_success_rate", 0) for row in rows],
            "ACE": [row.get("ace_success_rate", 0) for row in rows],
            "Experience reuse": [row.get("experience_reuse_rate", 0) for row in rows],
        }
        charts.append(_line_chart(chart_dir / "batch_trends.png", x_labels, series, "Continual learning trends"))
    elif exp_id == "exp4":
        snapshots = result.get("snapshots") or {}
        if snapshots:
            first = next(iter(snapshots.values()))
            x_labels = [str(row.get("step")) for row in first]
            accuracy = {name: [row.get("task_accuracy", 0) for row in rows] for name, rows in snapshots.items()}
            context_tokens = {name: [row.get("context_token_count", 0) for row in rows] for name, rows in snapshots.items()}
            charts.append(_line_chart(chart_dir / "context_token_count.png", x_labels, context_tokens, "Context tokens by adaptation step", clamp_unit=False))
            charts.append(_line_chart(chart_dir / "task_accuracy.png", x_labels, accuracy, "Accuracy by adaptation step", clamp_unit=True))
    return [path for path in charts if path]


def _bar_chart(path, labels, values, title, ylabel):
    if not labels:
        return None
    plt = _plotter()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(range(len(labels)), values, color="#1769aa")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 1)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _line_chart(path, labels, series, title, clamp_unit=True):
    if not labels or not series:
        return None
    plt = _plotter()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for name, values in series.items():
        ax.plot(labels, values, marker="o", linewidth=2, label=name)
    ax.set_title(title)
    if clamp_unit:
        ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)
    ax.legend()
    if len(labels) > 12:
        ax.set_xticks(range(0, len(labels), max(1, len(labels) // 10)))
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plotter():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    return plt


def _build_sections(result, charts, ai_summary):
    exp_id = result.get("experiment_id", "")
    task_summary = _task_summary(exp_id)
    geodata = _geodata_summary()
    trace_rows = result.get("traces") or []
    success_count = sum(1 for row in trace_rows if row.get("success"))
    failed_count = len(trace_rows) - success_count

    sections = [
        {
            "title": f"{result.get('name') or exp_id} 实验报告",
            "body": [
                f"Run ID：{result.get('run_id', '')}",
                f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
                f"配置：`{json.dumps(result.get('config') or {}, ensure_ascii=False)}`",
            ],
        },
        {
            "title": "实验设计思路",
            "body": [
                DESIGN_NOTES.get(exp_id, "本实验用于评估 ACE-WebGIS 在空间任务执行、经验复用和上下文稳定性方面的表现。"),
                f"任务展开规模：{task_summary.get('task_count', len(trace_rows))} 个任务单元；本次 trace 数：{len(trace_rows)}；成功 {success_count}，失败 {failed_count}。",
                f"任务文件：`{task_summary.get('task_file', '')}`。",
            ],
        },
        {
            "title": "数据集说明",
            "table": {
                "headers": ["数据层", "要素数", "几何类型", "字段示例"],
                "rows": geodata,
            },
            "body": [
                "实验使用 `data/geodata/` 下的成都 POI 与行政区 GeoJSON 图层，任务集通过自然语言描述调用检索、查询、邻近、缓冲、叠加、空间连接、聚类、热点、统计和导出等 GIS 能力。",
            ],
        },
        {
            "title": "任务集说明",
            "table": {
                "headers": ["类别", "任务数"],
                "rows": [[key, value] for key, value in sorted(task_summary.get("categories", {}).items())],
            },
            "body": [
                _task_dataset_note(exp_id),
            ],
        },
        {
            "title": "Trace 说明",
            "table": {"headers": ["字段", "含义"], "rows": TRACE_FIELD_NOTES},
            "body": [
                "每个 trace 是一次任务在某个框架或消融组下的完整记录。报告中的指标均可由 trace 字段直接复算。",
            ],
        },
        {
            "title": "指标计算方法",
            "table": {"headers": ["指标", "字段", "计算方式"], "rows": METRIC_GLOSSARY},
        },
        {
            "title": "结果指标",
            "table": _result_table(result),
        },
        *(_exp1_detail_sections(result) if exp_id == "exp1" else []),
        {
            "title": "可视化图表",
            "images": [path.relative_to(LOG_ROOT / result.get("run_id") / "reports").as_posix() for path in charts],
            "body": ["图表由当前 result.json 直接生成，便于论文或答辩材料引用。"],
        },
        {
            "title": "总结分析",
            "body": [_deterministic_summary(result), ai_summary or "未启用 DeepSeek 自动总结；可在导出时勾选 AI 总结生成更自然的论文式分析。"],
        },
    ]
    return sections


def _exp1_detail_sections(result):
    traces = result.get("traces") or []
    if not traces:
        return []
    reference = _load_exp1_reference_answers()
    rows = []
    for task_id in _ordered_task_ids(traces):
        task_traces = [row for row in traces if row.get("task_id") == task_id]
        first = task_traces[0]
        ref = reference.get(task_id, {})
        rows.append(
            [
                task_id,
                first.get("category", ""),
                _short_text(first.get("query", ""), 120),
                _format_reference(ref),
                _format_agent_result(task_traces, "base_agent"),
                _format_agent_result(task_traces, "rag_agent"),
                _format_agent_result(task_traces, "ace_agent"),
            ]
        )
    return [
        {
            "title": "实验一任务明细：返回结果与参考答案",
            "body": [
                "本表逐题列出用户任务、参考答案要点以及 Base / RAG / ACE 三类 Agent 的返回摘要与评分结果。"
                "其中参考答案来自 data/experiments/exp1_reference_answers.json，返回结果来自本次 run 的 trace。"
            ],
            "table": {
                "headers": ["任务", "类别", "任务描述", "参考答案要点", "Base 返回结果", "RAG 返回结果", "ACE 返回结果"],
                "rows": rows,
            },
        }
    ]


def _load_exp1_reference_answers():
    path = PROJECT_ROOT / "data" / "experiments" / "exp1_reference_answers.json"
    try:
        return (json.loads(path.read_text(encoding="utf-8")).get("answers") or {})
    except Exception:
        return {}


def _ordered_task_ids(traces):
    seen = []
    for row in traces:
        task_id = row.get("task_id")
        if task_id and task_id not in seen:
            seen.append(task_id)
    return seen


def _format_reference(ref):
    if not ref:
        return ""
    flags = []
    for key, label in [
        ("memory_read", "需读记忆"),
        ("memory_write", "需写记忆"),
        ("requires_experience_retrieval", "需经验检索"),
        ("requires_experience_add", "需经验新增"),
        ("requires_code", "需代码执行"),
        ("requires_export", "需导出"),
    ]:
        if ref.get(key):
            flags.append(label)
    parts = [
        f"工具: {', '.join(ref.get('expected_tools') or []) or '-'}",
        f"输出: {', '.join(ref.get('expected_output_types') or []) or '-'}",
        f"实体: {', '.join(str(item) for item in (ref.get('expected_entities') or [])[:6]) or '-'}",
        f"关键词: {', '.join(str(item) for item in (ref.get('required_keywords') or [])[:6]) or '-'}",
    ]
    if flags:
        parts.append(f"约束: {', '.join(flags)}")
    return "\n".join(parts)


def _format_agent_result(task_traces, agent_type):
    row = next((item for item in task_traces if item.get("agent_type") == agent_type), None)
    if not row:
        return ""
    validation = row.get("validation") or {}
    structured = row.get("structured_response") or {}
    missing = validation.get("missing") or []
    tools = row.get("selected_tools") or structured.get("selected_tools") or []
    outputs = structured.get("output_types") or []
    retrieved = row.get("retrieved_experiences") or []
    generated = row.get("generated_experience") or ""
    answer = row.get("final_answer") or structured.get("answer") or ""
    status = "通过" if row.get("success") else "未通过"
    parts = [
        f"{status} / score={validation.get('score', '')}",
        f"工具: {', '.join(tools) or '-'}",
        f"输出: {', '.join(outputs) or '-'}",
    ]
    if retrieved:
        parts.append(f"检索经验: {', '.join(str(item) for item in retrieved)}")
    if generated:
        parts.append(f"新增经验: {generated}")
    if missing:
        parts.append(f"缺失: {', '.join(str(item) for item in missing)}")
    parts.append(f"回答: {_short_text(answer, 180)}")
    return "\n".join(parts)


def _short_text(value, limit=120):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _task_summary(exp_id):
    if exp_id not in EXPERIMENTS:
        return {"task_file": "", "task_count": 0, "categories": {}}
    task_file = EXPERIMENTS[exp_id]["task_file"]
    if exp_id == "exp2":
        from .exp2.data import expand_batches, load_workbook

        loaded = expand_batches(load_workbook())
    elif exp_id == "exp4":
        from .exp4.data import expand_tasks, load_workbook

        loaded = expand_tasks(load_workbook())
    else:
        from .runner import load_tasks

        loaded = load_tasks(exp_id)
    tasks = []
    if loaded and isinstance(loaded, list) and loaded and isinstance(loaded[0], dict) and "tasks" in loaded[0]:
        for batch in loaded:
            tasks.extend(batch.get("tasks") or [])
    elif isinstance(loaded, list):
        tasks = loaded
    categories = {}
    for task in tasks:
        category = task.get("category", "unknown")
        categories[category] = categories.get(category, 0) + 1
    return {"task_file": task_file, "task_count": len(tasks), "categories": categories}


def _task_dataset_note(exp_id):
    if exp_id == "exp1":
        return (
            "实验一任务集拆成 `exp1_workbook.json` 习题册和 `exp1_reference_answers.json` 参考答案。"
            "习题册给出自然语言任务、难度、能力标签和会话链；参考答案给出期望工具、输出类型、实体/关键词、"
            "是否需要历史记忆、经验检索、经验写入或代码执行。成功率由结构化返回与参考答案的匹配分数计算。"
        )
    if exp_id == "exp4":
        return (
            "实验四任务集拆成 `exp4_workbook.json` 习题册和 `exp4_evaluation_config.json` 评测配置。"
            "习题册定义 10 类通用能力任务模板并展开为 100 个 adaptation step，不局限于 GIS 任务；"
            "参考答案文件记录 collapse 判定阈值：高位 token 骤降到 35% 以下且任务准确率下降至少 0.12。"
        )
    return "任务模板包含 `expected_tools` 和 `expected_outputs`，前者用于评估工具链选择，后者用于判断地图图层、表格结果和最小结果数量是否满足预期。"


def _geodata_summary():
    rows = []
    for path in sorted(GEODATA_ROOT.glob("*.geojson")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            features = data.get("features") or []
            first = features[0] if features else {}
            geometry = (first.get("geometry") or {}).get("type", "")
            props = list((first.get("properties") or {}).keys())[:6]
            rows.append([path.stem, len(features), geometry, ", ".join(props)])
        except Exception as exc:
            rows.append([path.stem, "读取失败", "", str(exc)])
    return rows


def _result_table(result):
    groups = result.get("groups") or {}
    if groups:
        keys = sorted({key for row in groups.values() for key in row.keys()})
        return {
            "headers": ["组别"] + keys,
            "rows": [[name] + [_format_value(groups[name].get(key, "")) for key in keys] for name in groups],
        }
    if result.get("batch_metrics"):
        rows = result.get("batch_metrics") or []
        keys = sorted({key for row in rows for key in row.keys()})
        return {"headers": keys, "rows": [[_format_value(row.get(key, "")) for key in keys] for row in rows]}
    return {"headers": ["指标", "值"], "rows": [["trace_count", len(result.get("traces") or [])]]}


def _format_value(value):
    if isinstance(value, float):
        return f"{value:.3f}"
    return value


def _deterministic_summary(result):
    exp_id = result.get("experiment_id")
    groups = result.get("groups") or {}
    if exp_id == "exp1" and groups:
        ace = groups.get("ace_webgis", {})
        best = max(groups.items(), key=lambda item: item[1].get("task_success_rate", 0))[0]
        return f"实验一中 ACE-WebGIS 的任务成功率为 {_format_value(ace.get('task_success_rate', 0))}，最高组为 {best}；可重点讨论工具链、代码执行和经验闭环带来的差异。"
    if exp_id == "exp2":
        rows = result.get("batch_metrics") or []
        last = rows[-1] if rows else {}
        return (
            "实验二最终 batch 的成功率为 "
            f"ACE={_format_value(last.get('ace_success_rate', 0))}、"
            f"RAG={_format_value(last.get('rag_success_rate', 0))}、"
            f"BASE={_format_value(last.get('base_success_rate', last.get('baseline_success_rate', 0)))}；"
            "可结合经验复用率和新经验数量解释 ACE 连续学习相对静态检索与无记忆基线的优势。"
        )
    if exp_id == "exp3" and groups:
        full = groups.get("full_ace", {})
        return f"实验三中完整 ACE 成功率为 {_format_value(full.get('success_rate', 0))}；各消融组与 full_ace 的差距可用于分析 Critic、Evolution、经验检索、CodeAgent 和 ContextManager 的贡献。"
    if exp_id == "exp4" and groups:
        ace = groups.get("ace_grow_and_refine", {})
        return f"实验四中 ACE grow-and-refine 最终任务准确率为 {_format_value(ace.get('final_task_accuracy', 0))}，最终上下文 token 数为 {_format_value(ace.get('final_context_token_count', 0))}，collapse 事件数为 {_format_value(ace.get('collapse_event_count', 0))}；可用于说明 ACE 在连续在线学习中能避免上下文坍塌。"
    return "本次实验已生成完整 trace 和指标，可据此展开定量对比与误差分析。"


def _generate_ai_summary(result):
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "DeepSeek 总结未生成：.env 中缺少 DEEPSEEK_API_KEY。"
    try:
        from langchain_deepseek import ChatDeepSeek

        compact = {
            "experiment_id": result.get("experiment_id"),
            "name": result.get("name"),
            "groups": result.get("groups"),
            "batch_metrics": result.get("batch_metrics"),
            "trace_count": len(result.get("traces") or []),
        }
        prompt = (
            "你是 GIS 与智能体实验论文写作助手。请基于以下实验结果，用中文写一段 300 字以内的总结分析，"
            "包括主要发现、可能原因、论文中可强调的结论。不要编造未给出的数值。\n"
            f"{json.dumps(compact, ensure_ascii=False)}"
        )
        llm = ChatDeepSeek(model="deepseek-chat", temperature=0.2, api_key=api_key, timeout=40, max_retries=1)
        response = llm.invoke(prompt)
        return getattr(response, "content", str(response)).strip()
    except Exception as exc:
        return f"DeepSeek 总结生成失败：{exc}"


def _render_markdown(sections):
    lines = []
    for idx, section in enumerate(sections):
        prefix = "#" if idx == 0 else "##"
        lines.append(f"{prefix} {section['title']}")
        for text in section.get("body") or []:
            lines.append("")
            lines.append(str(text))
        table = section.get("table")
        if table:
            lines.append("")
            headers = table.get("headers") or []
            lines.append("| " + " | ".join(_md_cell(head) for head in headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for row in table.get("rows") or []:
                lines.append("| " + " | ".join(_md_cell(cell) for cell in row) + " |")
        for image in section.get("images") or []:
            lines.append("")
            lines.append(f"![{image}]({image})")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _md_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|")


def _render_html(sections):
    body = []
    for idx, section in enumerate(sections):
        tag = "h1" if idx == 0 else "h2"
        body.append(f"<{tag}>{html.escape(section['title'])}</{tag}>")
        for text in section.get("body") or []:
            body.append(f"<p>{html.escape(str(text))}</p>")
        table = section.get("table")
        if table:
            body.append("<table><thead><tr>")
            for head in table.get("headers") or []:
                body.append(f"<th>{html.escape(str(head))}</th>")
            body.append("</tr></thead><tbody>")
            for row in table.get("rows") or []:
                body.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>")
            body.append("</tbody></table>")
        for image in section.get("images") or []:
            body.append(f"<figure><img src='{html.escape(image)}' alt='{html.escape(image)}'><figcaption>{html.escape(image)}</figcaption></figure>")
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>实验报告</title><style>"
        "body{font-family:Inter,'Microsoft YaHei',sans-serif;max-width:1120px;margin:0 auto;padding:32px;color:#172033;line-height:1.7}"
        "h1{font-size:30px}h2{margin-top:32px;border-left:4px solid #1769aa;padding-left:10px}"
        "table{width:100%;border-collapse:collapse;margin:14px 0 24px;font-size:14px}th,td{border:1px solid #d8e0ea;padding:8px 10px;text-align:left;vertical-align:top}th{background:#eef5fb}"
        "img{max-width:100%;border:1px solid #d8e0ea;border-radius:8px}figure{margin:18px 0}figcaption{color:#64748b;font-size:13px}"
        "p{margin:10px 0}</style></head><body>"
        + "\n".join(body)
        + "</body></html>"
    )
