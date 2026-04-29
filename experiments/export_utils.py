"""
实验图片导出工具。
负责从 summary.json 生成 matplotlib 可视化图表，提供中文标签、完整的前端可视化映射和美观样式。
"""

import json
import os
import zipfile
from collections import OrderedDict
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import numpy as np

# ── 全局中文字体配置 ──────────────────────────────────────────────
# 优先使用 SimHei（黑体），若不可用则回退到其他中文字体
_CHINESE_FONTS = [
    "SimHei",
    "Microsoft YaHei",
    "DengXian",
    "STHeiti",
    "Source Han Sans SC",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
    "AR PL UMing CN",
]

_FONT_NAME = "sans-serif"
for _fname in _CHINESE_FONTS:
    try:
        _fp = fm.findfont(_fname, fallback_to_default=False)
        _FONT_NAME = _fname
        break
    except Exception:
        continue

# 全局 matplotlib rc 参数
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [_FONT_NAME, "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.dpi": 160,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.15,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "grid.linewidth": 0.5,
    }
)

# ── 调色板 ────────────────────────────────────────────────────────
COLORS = {
    "base": "#e74c3c",  # Base LLM 红
    "ace": "#27ae60",  # ACE 绿
    "improve": "#3498db",  # 改进 蓝
    "full_ace": "#2ecc71",
    "wo_critic": "#e67e22",
    "wo_evolution": "#9b59b6",
    "wo_experience": "#f1c40f",
    "wo_context": "#e74c3c",
}

COLOR_LIST = [
    "#2ecc71",
    "#e67e22",
    "#9b59b6",
    "#f1c40f",
    "#e74c3c",
    "#3498db",
    "#1abc9c",
    "#34495e",
]

FIGURE_DIR_NAME = "figures"
EXPORT_DIR_NAME = "exports"


# ══════════════════════════════════════════════════════════════════
#  对外接口
# ══════════════════════════════════════════════════════════════════


def build_export_zip(run_dir):
    """构建导出 zip 包（包含 summary.json, results.csv, 所有图片）。"""
    run_dir = os.path.abspath(run_dir)
    summary_path = os.path.join(run_dir, "summary.json")
    if not os.path.exists(summary_path):
        raise FileNotFoundError(f"summary.json not found: {summary_path}")

    figure_paths = ensure_matplotlib_exports(run_dir)
    export_dir = os.path.join(run_dir, EXPORT_DIR_NAME)
    os.makedirs(export_dir, exist_ok=True)

    run_name = os.path.basename(run_dir)
    zip_path = os.path.join(export_dir, f"{run_name}_export.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename in ("summary.json", "results.csv", ".run_name"):
            path = os.path.join(run_dir, filename)
            if os.path.exists(path):
                zf.write(path, arcname=filename)
        for path in figure_paths:
            zf.write(path, arcname=os.path.join(FIGURE_DIR_NAME, os.path.basename(path)))
        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_run": os.path.relpath(run_dir),
            "tables": [n for n in ("summary.json", "results.csv") if os.path.exists(os.path.join(run_dir, n))],
            "figures": [os.path.join(FIGURE_DIR_NAME, os.path.basename(p)) for p in figure_paths],
        }
        zf.writestr("export_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return zip_path


def ensure_matplotlib_exports(run_dir):
    """根据运行目录名自动派发到对应实验的绘图函数。"""
    run_dir = os.path.abspath(run_dir)
    with open(os.path.join(run_dir, "summary.json"), "r", encoding="utf-8") as f:
        summary = json.load(f)

    figure_dir = os.path.join(run_dir, FIGURE_DIR_NAME)
    os.makedirs(figure_dir, exist_ok=True)

    name = os.path.basename(run_dir)
    dispatcher = {
        "exp1": _plot_exp1,
        "exp2": _plot_exp2,
        "exp3": _plot_exp3,
        "exp4": _plot_exp4,
    }
    for prefix, func in dispatcher.items():
        if name.startswith(prefix):
            return func(summary, figure_dir)
    return _plot_generic(summary, figure_dir)


# ══════════════════════════════════════════════════════════════════
#  实验一：基线对比实验
# ══════════════════════════════════════════════════════════════════


def _plot_exp1(summary, figure_dir):
    paths = []
    paths.append(_plot_exp1_metrics_bar(summary, figure_dir))
    paths.append(_plot_exp1_response_time(summary, figure_dir))
    paths.append(_plot_exp1_radar(summary, figure_dir))
    paths.append(_plot_exp1_heatmap(summary, figure_dir))
    return [p for p in paths if p]


def _plot_exp1_metrics_bar(summary, figure_dir):
    """指标对比柱状图（带提升百分比标注）。"""
    base = summary.get("base", {})
    ace = summary.get("ace", {})
    impr = summary.get("improvements", {})

    metrics = [
        ("任务完成率", "task_completion_rate"),
        ("工具成功率", "tool_success_rate"),
        ("代码成功率", "code_success_rate"),
        ("结果准确率", "accuracy_rate"),
    ]

    labels = [m[0] for m in metrics]
    base_vals = [_num(base.get(m[1])) for m in metrics]
    ace_vals = [_num(ace.get(m[1])) for m in metrics]
    impr_vals = [_num(impr.get(f"{m[1]}_pct")) for m in metrics]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(labels))
    w = 0.32

    bars1 = ax.bar(x - w / 2, base_vals, w, label="Base LLM", color=COLORS["base"], edgecolor="white", linewidth=0.6)
    bars2 = ax.bar(x + w / 2, ace_vals, w, label="ACE 增强", color=COLORS["ace"], edgecolor="white", linewidth=0.6)

    # 在 ACE 柱上标注提升百分比
    for i, (bv, av, iv) in enumerate(zip(base_vals, ace_vals, impr_vals)):
        if av > bv:
            ax.annotate(
                f"+{iv:.1f}%",
                (x[i] + w / 2, av),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=9,
                color=COLORS["improve"],
                fontweight="bold",
            )

    _finish_bar(ax, labels, "实验一：Base LLM vs ACE 指标对比", "得分 / 率 (%)")
    ax.legend(fontsize=10, loc="upper right", frameon=True, facecolor="white", edgecolor="#ddd")
    return _save(fig, figure_dir, "exp1_metric_comparison.png")


def _plot_exp1_response_time(summary, figure_dir):
    """各任务响应时间对比（分组柱状图）。"""
    details = summary.get("task_details", [])
    if not details:
        return ""

    # 按 task_id 和 mode 分组
    grouped = {}
    for row in details:
        tid = row.get("task_id")
        mode = row.get("mode", "unknown")
        rt = _num(row.get("response_time"))
        grouped.setdefault(tid, {})[mode] = rt

    task_ids = sorted(grouped.keys())
    base_times = [grouped[tid].get("base", 0) for tid in task_ids]
    ace_times = [grouped[tid].get("ace", 0) for tid in task_ids]
    labels = [f"#{tid}" for tid in task_ids]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))
    w = 0.32

    ax.bar(x - w / 2, base_times, w, label="Base LLM", color=COLORS["base"], edgecolor="white", linewidth=0.6)
    ax.bar(x + w / 2, ace_times, w, label="ACE 增强", color=COLORS["ace"], edgecolor="white", linewidth=0.6)

    # 在柱顶标注数值
    for i in range(len(labels)):
        if base_times[i] > 0:
            ax.text(x[i] - w / 2, base_times[i] + 0.3, f"{base_times[i]:.1f}s", ha="center", fontsize=7.5, color=COLORS["base"])
        if ace_times[i] > 0:
            ax.text(x[i] + w / 2, ace_times[i] + 0.3, f"{ace_times[i]:.1f}s", ha="center", fontsize=7.5, color=COLORS["ace"])

    _finish_bar(ax, labels, "实验一：各任务响应时间对比", "响应时间 (秒)", ylim=None)
    ax.legend(fontsize=10, loc="upper right", frameon=True, facecolor="white", edgecolor="#ddd")
    return _save(fig, figure_dir, "exp1_response_time.png")


def _plot_exp1_radar(summary, figure_dir):
    """六维能力雷达图（与前端 renderRadarChart 对应）。"""
    base = summary.get("base", {})
    ace = summary.get("ace", {})

    dimensions = [
        ("任务完成率", "task_completion_rate"),
        ("工具成功率", "tool_success_rate"),
        ("代码成功率", "code_success_rate"),
        ("结果准确率", "accuracy_rate"),
        ("经验命中率", "experience_hit_rate"),
        ("错误恢复率", "error_recovery_rate"),
    ]

    labels = [d[0] for d in dimensions]
    base_vals = [_num(base.get(d[1])) for d in dimensions]
    ace_vals = [_num(ace.get(d[1])) for d in dimensions]

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # 闭合

    base_vals_closed = base_vals + base_vals[:1]
    ace_vals_closed = ace_vals + ace_vals[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    ax.fill(angles, base_vals_closed, alpha=0.08, color=COLORS["base"])
    ax.plot(angles, base_vals_closed, "o-", linewidth=2, label="Base LLM", color=COLORS["base"], markersize=5)

    ax.fill(angles, ace_vals_closed, alpha=0.1, color=COLORS["ace"])
    ax.plot(angles, ace_vals_closed, "o-", linewidth=2, label="ACE 增强", color=COLORS["ace"], markersize=5)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="gray")
    ax.set_title("实验一：六维能力雷达图", fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    return _save(fig, figure_dir, "exp1_radar.png")


def _plot_exp1_heatmap(summary, figure_dir):
    """任务级通过矩阵热力图（与前端 renderHeatmap 对应）。"""
    details = summary.get("task_details", [])
    if not details:
        return ""

    base_items = sorted([d for d in details if d.get("mode") == "base"], key=lambda x: x.get("task_id", 0))
    ace_items = sorted([d for d in details if d.get("mode") == "ace"], key=lambda x: x.get("task_id", 0))

    if not base_items and not ace_items:
        return ""

    items = base_items or ace_items
    task_ids = [str(it.get("task_id", "")) for it in items]

    metrics_def = [
        ("任务完成", "task_completed"),
        ("工具成功", "tool_success"),
        ("代码成功", "code_success"),
        ("结果准确", "accuracy"),
    ]

    n_metrics = len(metrics_def)
    n_tasks = len(task_ids)

    # 构建 2 层矩阵：0=Base, 1=ACE
    data = np.zeros((2, n_metrics, n_tasks))
    for layer_idx, layer_items in enumerate([base_items, ace_items]):
        if not layer_items:
            continue
        for ti, item in enumerate(layer_items):
            for mi, (_, key) in enumerate(metrics_def):
                data[layer_idx, mi, ti] = 100 if item.get(key) else 0

    fig, axes = plt.subplots(1, 2, figsize=(max(8, n_tasks * 1.0 + 3), 4.5), sharey=True)

    titles = ["Base LLM", "ACE 增强"]
    cmap_colors = ["#e74c3c", "#27ae60"]

    for idx, ax in enumerate(axes):
        mat = data[idx]
        if mat.sum() == 0 and idx == 0:
            # Base 无数据时显示占位
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=12, color="gray", transform=ax.transAxes)
            ax.set_title(titles[idx], fontsize=11, fontweight="bold", color=cmap_colors[idx])
            continue

        im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100)
        ax.set_xticks(range(n_tasks))
        ax.set_xticklabels(task_ids, fontsize=8, rotation=0)
        ax.set_yticks(range(n_metrics))
        ax.set_yticklabels([m[0] for m in metrics_def], fontsize=9)
        ax.set_title(titles[idx], fontsize=11, fontweight="bold", color=cmap_colors[idx])

        # 在格子中标注通过/不通过（使用中文，避免字体不支持 Unicode 符号）
        for mi in range(n_metrics):
            for ti in range(n_tasks):
                val = mat[mi, ti]
                text = "通过" if val >= 100 else "失败"
                color = "white" if val >= 100 else "#aaa"
                ax.text(ti, mi, text, ha="center", va="center", fontsize=9, color=color, fontweight="bold")

    fig.suptitle("实验一：任务级通过矩阵", fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, figure_dir, "exp1_heatmap.png")


# ══════════════════════════════════════════════════════════════════
#  实验二：消融实验
# ══════════════════════════════════════════════════════════════════


def _plot_exp2(summary, figure_dir):
    paths = []
    paths.append(_plot_exp2_metrics_bar(summary, figure_dir))
    paths.append(_plot_exp2_contribution_bar(summary, figure_dir))
    paths.append(_plot_exp2_error_analysis(summary, figure_dir))
    return [p for p in paths if p]


def _plot_exp2_metrics_bar(summary, figure_dir):
    """各变体指标分组柱状图（与前端 renderExp2MetricsChart 对应）。"""
    variants = summary.get("variants", {})
    if not variants:
        return ""
    names = [item.get("name", key) for key, item in variants.items()]
    x = np.arange(len(names))
    w = 0.22

    groups = [
        ("结果准确率", "accuracy_rate", COLORS["ace"]),
        ("工具成功率", "tool_success_rate", "#3498db"),
        ("多轮一致性", "multi_turn_consistency_rate", "#9b59b6"),
    ]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for offset, (label, key, color) in enumerate(groups):
        values = [_num(item.get(key)) for item in variants.values()]
        ax.bar(x + (offset - 1) * w, values, w, label=label, color=color, edgecolor="white", linewidth=0.5)

    _finish_bar(ax, names, "实验二：各变体消融指标对比", "率 (%)")
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    return _save(fig, figure_dir, "exp2_ablation_metrics.png")


def _plot_exp2_contribution_bar(summary, figure_dir):
    """模块贡献度横向柱状图（与前端 renderExp2ContributionChart 对应）。"""
    contributions = summary.get("contributions", [])
    if not contributions:
        return ""
    modules = [item.get("module", "") for item in contributions]
    scores = [_num(item.get("contribution_score")) for item in contributions]
    rels = [_num(item.get("relative_contribution")) for item in contributions]

    colors_module = [COLOR_LIST[i % len(COLOR_LIST)] for i in range(len(modules))]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(modules, scores, color=colors_module, edgecolor="white", linewidth=0.6)
    ax.invert_yaxis()

    # 在柱右侧标注数值和占比
    for i, (bar, score, rel) in enumerate(zip(bars, scores, rels)):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.1f}  ({rel:.1f}%)",
            va="center",
            fontsize=9,
            color="#555",
        )

    ax.set_title("实验二：ACE 模块贡献度排名", fontsize=13, fontweight="bold")
    ax.set_xlabel("综合贡献度", fontsize=10)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    fig.tight_layout()
    return _save(fig, figure_dir, "exp2_module_contribution.png")


def _plot_exp2_error_analysis(summary, figure_dir):
    """错误恢复分析折线图（与前端 renderExp2ErrorChart 对应）。"""
    variants = summary.get("variants", {})
    if not variants:
        return ""
    names = [item.get("name", key) for key, item in variants.items()]

    recovery_rates = [_num(item.get("error_recovery_rate")) for item in variants.values()]
    prop_depths = [_num(item.get("avg_error_propagation_depth")) for item in variants.values()]

    fig, ax1 = plt.subplots(figsize=(9, 5))

    color1 = COLORS["ace"]
    color2 = COLORS["base"]

    line1 = ax1.plot(names, recovery_rates, "o-", color=color1, linewidth=2.5, markersize=7, label="错误恢复率 (%)")
    ax1.set_ylabel("错误恢复率 (%)", fontsize=10, color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_ylim(-5, 105)

    # 在点上标注数值
    for i, v in enumerate(recovery_rates):
        ax1.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8.5, color=color1)

    ax2 = ax1.twinx()
    line2 = ax2.plot(names, prop_depths, "s--", color=color2, linewidth=2, markersize=7, label="错误传播深度")
    ax2.set_ylabel("平均错误传播深度 (轮)", fontsize=10, color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(-0.1, max(prop_depths) + 1 if prop_depths else 3)

    for i, v in enumerate(prop_depths):
        ax2.annotate(f"{v:.1f}", (i, v), textcoords="offset points", xytext=(0, -12), ha="center", fontsize=8.5, color=color2)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left", fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")

    ax1.set_title("实验二：错误恢复与传播分析", fontsize=13, fontweight="bold")
    ax1.set_xlabel("变体", fontsize=10)
    ax1.grid(axis="y", alpha=0.2, linestyle="--")
    fig.tight_layout()
    return _save(fig, figure_dir, "exp2_error_analysis.png")


# ══════════════════════════════════════════════════════════════════
#  实验三：抗退化实验
# ══════════════════════════════════════════════════════════════════


def _plot_exp3(summary, figure_dir):
    paths = []
    paths.append(_plot_exp3_decay_curve(summary, figure_dir))
    paths.append(_plot_exp3_system_metrics(summary, figure_dir))
    paths.append(_plot_exp3_pollution(summary, figure_dir))
    return [p for p in paths if p]


def _plot_exp3_decay_curve(summary, figure_dir):
    """记忆衰减曲线（与前端 renderExp3DecayChart 对应）。"""
    curve = summary.get("decay_curve", [])
    if not curve:
        return ""
    gaps = [_num(item.get("gap")) for item in curve]

    fig, ax = plt.subplots(figsize=(9, 5.2))

    systems_lines = [
        ("base_llm", "Base LLM", COLORS["base"], "o"),
        ("ace_dynamic", "ACE 动态", COLORS["ace"], "s"),
    ]

    for key, label, color, marker in systems_lines:
        values = [_num(item.get(key)) for item in curve]
        ax.plot(gaps, values, marker=marker, linewidth=2.5, markersize=7, label=label, color=color, markerfacecolor=color, markeredgecolor="white", markeredgewidth=1)

    # 添加数值标注
    for key, color in [(k, c) for k, _, c, _ in systems_lines]:
        vals = [_num(item.get(key)) for item in curve]
        for g, v in zip(gaps, vals):
            ax.annotate(f"{v:.1f}%", (g, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7.5, color=color, alpha=0.8)

    ax.set_title("实验三：记忆衰减曲线", fontsize=13, fontweight="bold")
    ax.set_xlabel("参考间隔 (轮次)", fontsize=10)
    ax.set_ylabel("召回率 (%)", fontsize=10)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    return _save(fig, figure_dir, "exp3_memory_decay.png")


def _plot_exp3_system_metrics(summary, figure_dir):
    """系统指标分组柱状图（与前端 renderExp3MemoryChart 对应）。"""
    systems = summary.get("systems", {})
    if not systems:
        return ""

    metrics = [
        ("POI召回率", "poi_recall_rate"),
        ("偏好持久率", "preference_persistence_rate"),
        ("经验复用率", "experience_reuse_rate"),
        ("鲁棒性得分", "robustness_score"),
    ]

    return _grouped_system_bar(systems, metrics, figure_dir, "exp3_system_metrics.png", "实验三：系统能力指标对比")


def _plot_exp3_pollution(summary, figure_dir):
    """上下文污染与压缩分析（与前端 renderExp3PollutionChart 对应）。"""
    systems = summary.get("systems", {})
    if not systems:
        return ""

    labels = ["上下文污染率", "平均压缩率", "记忆半衰期"]
    base = systems.get("base_llm", {})
    ace = systems.get("ace_dynamic", {})

    base_vals = [_num(base.get("context_pollution_rate")), _num(base.get("avg_compression_rate")), _num(base.get("memory_half_life_rounds"))]
    ace_vals = [_num(ace.get("context_pollution_rate")), _num(ace.get("avg_compression_rate")), _num(ace.get("memory_half_life_rounds"))]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(labels))
    w = 0.32

    ax.bar(x - w / 2, base_vals, w, label="Base LLM", color=COLORS["base"], edgecolor="white", linewidth=0.6)
    ax.bar(x + w / 2, ace_vals, w, label="ACE 动态", color=COLORS["ace"], edgecolor="white", linewidth=0.6)

    for i in range(len(labels)):
        ax.text(x[i] - w / 2, base_vals[i] + 0.5, f"{base_vals[i]:.1f}", ha="center", fontsize=8, color=COLORS["base"])
        ax.text(x[i] + w / 2, ace_vals[i] + 0.5, f"{ace_vals[i]:.1f}", ha="center", fontsize=8, color=COLORS["ace"])

    _finish_bar(ax, labels, "实验三：上下文污染与压缩分析", "值", ylim=None)
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    return _save(fig, figure_dir, "exp3_pollution.png")


# ══════════════════════════════════════════════════════════════════
#  实验四：长上下文扩展实验
# ══════════════════════════════════════════════════════════════════


def _plot_exp4(summary, figure_dir):
    paths = []
    paths.append(_plot_exp4_accuracy_curve(summary, figure_dir))
    paths.append(_plot_exp4_system_metrics(summary, figure_dir))
    paths.append(_plot_exp4_reference_chart(summary, figure_dir))
    paths.append(_plot_exp4_compression_chart(summary, figure_dir))
    return [p for p in paths if p]


def _plot_exp4_accuracy_curve(summary, figure_dir):
    """长上下文准确率曲线（与前端 renderExp4AccuracyChart 对应）。"""
    intervals = summary.get("interval_stats", [])
    if not intervals:
        return ""
    labels = [item.get("interval", "") for item in intervals]

    fig, ax = plt.subplots(figsize=(9.5, 5.2))

    systems_lines = [
        ("base_full", "Base 完整", "#e74c3c", "o"),
        ("base_truncated", "Base 截断", "#f39c12", "s"),
        ("ace_compressed", "ACE 压缩", "#27ae60", "D"),
    ]

    for key, label, color, marker in systems_lines:
        values = [_num(item.get(key, {}).get("accuracy")) for item in intervals]
        ax.plot(
            range(len(labels)),
            values,
            marker=marker,
            linewidth=2.5,
            markersize=7,
            label=label,
            color=color,
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=1,
        )
        for i, v in enumerate(values):
            ax.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7.5, color=color, alpha=0.85)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_title("实验四：长上下文准确率变化趋势", fontsize=13, fontweight="bold")
    ax.set_xlabel("轮次间隔", fontsize=10)
    ax.set_ylabel("准确率 (%)", fontsize=10)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    return _save(fig, figure_dir, "exp4_accuracy_curve.png")


def _plot_exp4_system_metrics(summary, figure_dir):
    """系统指标分组柱状图（与前端 renderExp4SystemMetrics 对应）。"""
    systems = summary.get("systems", {})
    if not systems:
        return ""

    metrics = [
        ("长序列准确率", "long_sequence_accuracy"),
        ("跨轮引用准确率", "cross_turn_reference_accuracy"),
        ("任务完成率", "completion_rate"),
        ("鲁棒性得分", "robustness_score"),
    ]

    return _grouped_system_bar(systems, metrics, figure_dir, "exp4_system_metrics.png", "实验四：系统能力指标对比")


def _plot_exp4_reference_chart(summary, figure_dir):
    """跨轮引用分析柱状图（与前端 renderExp4ReferenceChart 对应）。"""
    systems = summary.get("systems", {})
    if not systems:
        return ""
    names = [item.get("name", key) for key, item in systems.items()]

    ref_acc = [_num(item.get("cross_turn_reference_accuracy")) for item in systems.values()]
    long_acc = [_num(item.get("long_sequence_accuracy")) for item in systems.values()]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(names))
    w = 0.32

    ax.bar(x - w / 2, ref_acc, w, label="跨轮引用准确率", color="#3498db", edgecolor="white", linewidth=0.6)
    ax.bar(x + w / 2, long_acc, w, label="长序列准确率", color="#2ecc71", edgecolor="white", linewidth=0.6)

    for i in range(len(names)):
        ax.text(x[i] - w / 2, ref_acc[i] + 0.8, f"{ref_acc[i]:.1f}%", ha="center", fontsize=8, color="#3498db")
        ax.text(x[i] + w / 2, long_acc[i] + 0.8, f"{long_acc[i]:.1f}%", ha="center", fontsize=8, color="#2ecc71")

    _finish_bar(ax, names, "实验四：跨轮引用分析", "准确率 (%)")
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    return _save(fig, figure_dir, "exp4_reference.png")


def _plot_exp4_compression_chart(summary, figure_dir):
    """压缩与污染分析柱状图（与前端 renderExp4CompressionChart 对应）。"""
    systems = summary.get("systems", {})
    if not systems:
        return ""
    names = [item.get("name", key) for key, item in systems.items()]

    comp_rates = [_num(item.get("context_compression_rate")) for item in systems.values()]
    poll_rates = [_num(item.get("context_pollution_rate")) for item in systems.values()]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(names))
    w = 0.32

    ax.bar(x - w / 2, comp_rates, w, label="上下文压缩率", color="#9b59b6", edgecolor="white", linewidth=0.6)
    ax.bar(x + w / 2, poll_rates, w, label="污染率", color="#e74c3c", edgecolor="white", linewidth=0.6)

    for i in range(len(names)):
        ax.text(x[i] - w / 2, comp_rates[i] + 0.8, f"{comp_rates[i]:.1f}%", ha="center", fontsize=8, color="#9b59b6")
        ax.text(x[i] + w / 2, poll_rates[i] + 0.8, f"{poll_rates[i]:.1f}%", ha="center", fontsize=8, color="#e74c3c")

    _finish_bar(ax, names, "实验四：上下文压缩与污染分析", "率 (%)")
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="#ddd")
    return _save(fig, figure_dir, "exp4_compression.png")


# ══════════════════════════════════════════════════════════════════
#  通用 / 辅助函数
# ══════════════════════════════════════════════════════════════════


def _plot_generic(summary, figure_dir):
    """兜底：当无法匹配任何实验时显示简要信息。"""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axis("off")
    ax.text(0.5, 0.75, summary.get("experiment", "实验导出"), fontsize=16, weight="bold", ha="center", transform=ax.transAxes)
    ax.text(
        0.5,
        0.55,
        f"生成时间: {summary.get('run_name') or summary.get('timestamp') or 'summary.json'}",
        fontsize=11,
        ha="center",
        transform=ax.transAxes,
        color="gray",
    )
    ax.text(0.5, 0.38, "未匹配到专门的图表模板，已导出原始数据。", fontsize=11, ha="center", transform=ax.transAxes, color="#888")
    return [_save(fig, figure_dir, "experiment_summary.png")]


def _grouped_system_bar(systems, metrics, figure_dir, filename, title):
    """通用分组柱状图：多个系统之间按指标分组对比。"""
    if not systems:
        return ""
    names = [item.get("name", key) for key, item in systems.items()]
    n_systems = len(systems)
    n_metrics = len(metrics)

    x = np.arange(n_metrics)
    w = min(0.22, 0.7 / max(n_systems, 1))

    fig, ax = plt.subplots(figsize=(9.5, 5.2))

    for offset, (system_id, item) in enumerate(systems.items()):
        positions = x + (offset - (n_systems - 1) / 2) * w
        values = [_num(item.get(metric_key)) for _, metric_key in metrics]
        color = COLOR_LIST[offset % len(COLOR_LIST)]
        bars = ax.bar(positions, values, w, label=_system_label(system_id, item.get("name")), color=color, edgecolor="white", linewidth=0.5)

        # 在柱顶标注数值
        for pi, (pos, val) in enumerate(zip(positions, values)):
            if val > 0:
                ax.text(pos, val + 1, f"{val:.1f}", ha="center", fontsize=7.5, color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([m[0] for m in metrics], fontsize=10)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("得分 / 率 (%)", fontsize=10)
    ax.set_ylim(0, 110)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, frameon=True, facecolor="white", edgecolor="#ddd")
    fig.tight_layout()
    return _save(fig, figure_dir, filename)


def _finish_bar(ax, labels, title, ylabel, ylim=(0, 110)):
    """设置柱状图的通用样式。"""
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.set_axisbelow(True)
    ax.figure.tight_layout()


def _save(fig, figure_dir, filename):
    """保存图片到指定目录。"""
    path = os.path.join(figure_dir, filename)
    fig.savefig(path, dpi=160, bbox_inches="tight", pad_inches=0.15, facecolor="white")
    plt.close(fig)
    return path


def _num(value):
    """安全转换为浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _system_label(system_id, fallback=None):
    """系统 ID 到中文标签的映射。"""
    labels = {
        "base_llm": "Base LLM",
        "ace_dynamic": "ACE 动态",
        "ace_static": "ACE 静态",
        "base_full": "Base 完整",
        "base_truncated": "Base 截断",
        "ace_compressed": "ACE 压缩",
    }
    return labels.get(system_id, fallback or system_id)
