"""
实验入口脚本。

用法：
    python -m experiments.runner          # 运行所有实验
    python -m experiments.runner --exp 1  # 只运行实验一
    python -m experiments.runner --mode base  # 只运行Base模式
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime


DEFAULT_OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "experiment_outputs")
DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT
EXP1_DIR = os.path.join(os.path.dirname(__file__), "exp1")


def output_dir_for_exp(output_root, exp_name):
    normalized = os.path.normpath(output_root)
    if os.path.basename(normalized) == "experiment_outputs":
        return os.path.join(output_root, exp_name)
    return output_root


def run_exp1(ai_handler=None, map_handler=None, mode="both", output_dir=DEFAULT_OUTPUT_DIR, use_preset=True):
    """
    运行实验一。

    返回一个合并后的 summary dict，结构如下：
    {
        "experiment": "实验一：基线对比实验",
        "timestamp": "...",
        "total_tasks": 15,
        "base": { ... },
        "ace": { ... },
        "improvements": { ... },
        "base_by_difficulty": { ... },
        "ace_by_difficulty": { ... },
        "task_details": [ ... ]
    }
    兼容前端 renderExperiment1() 的直接消费。

    Parameters
    ----------
    use_preset : bool
        如果为 True（默认），ACE 模式加载 exp1_experience_library.json 预设经验库。
        如果为 False，使用当前活跃的经验库（由 Web 前端选择）。
    """
    from experiments.exp1.exp1_analyzer import Exp1MetricsCollector

    merged = None

    if mode in ("both", "base"):
        if ai_handler is None:
            print("[Exp1] 警告：未提供 ai_handler，跳过 Base LLM 运行")
        else:
            merged = run_exp1_sync(ai_handler, map_handler, "base", output_dir_for_exp(output_dir, "exp1"), use_preset=use_preset)

    if mode in ("both", "ace"):
        if ai_handler is None:
            print("[Exp1] 警告：未提供 ai_handler，跳过 ACE 运行")
        else:
            ace_summary = run_exp1_sync(ai_handler, map_handler, "ace", output_dir_for_exp(output_dir, "exp1"), use_preset=use_preset)

            if merged is None:
                merged = ace_summary
            else:
                # 合并 base 和 ace 的汇总
                merged["ace"] = ace_summary.get("ace", {})
                merged["ace_by_difficulty"] = ace_summary.get("ace_by_difficulty", {})
                # 合并 task_details
                base_details = merged.get("task_details", [])
                ace_details = ace_summary.get("task_details", [])
                merged["task_details"] = base_details + ace_details
                # 重新计算 improvements
                from experiments.exp1.exp1_analyzer import Exp1MetricsCollector as _MC
                temp = _MC()
                temp.results = merged["task_details"]
                merged["improvements"] = temp.summarize().get("improvements", {})

                # 当 mode="both" 时，将合并后的结果保存到统一的运行目录
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                exp1_output_dir = output_dir_for_exp(output_dir, "exp1")
                merged_run_dir = os.path.join(exp1_output_dir, f"exp1_both_{timestamp}")
                os.makedirs(merged_run_dir, exist_ok=True)
                merged["run_dir"] = os.path.relpath(os.path.abspath(merged_run_dir))
                merged["run_name"] = datetime.strptime(timestamp, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                merged_json_path = os.path.join(merged_run_dir, "summary.json")
                with open(merged_json_path, "w", encoding="utf-8") as f:
                    json.dump(merged, f, ensure_ascii=False, indent=2)
                print(f"[Exp1] 合并结果已保存至: {merged_run_dir}")

    return merged or {}


def run_exp1_sync(ai_handler, map_handler, mode, output_dir, use_preset=True):
    """同步运行实验一（单个模式）。"""
    from experiments.exp1.exp1_runner import Exp1Runner
    from experiments.exp1.exp1_analyzer import Exp1MetricsCollector

    # ---- ACE 模式：加载经验库 ----
    restored_experiences = None
    if mode == "ace" and ai_handler is not None:
        if use_preset:
            # 加载实验一预设经验库（默认行为）
            exp_preset_path = os.path.join(EXP1_DIR, "exp1_experience_library.json")
            if os.path.exists(exp_preset_path):
                restored_experiences = list(ai_handler.experience_library.experiences)
                with open(exp_preset_path, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                ai_handler.experience_library.experiences = presets
                ai_handler.experience_library.save()
                print(f"[Exp1] 已加载预设经验库: {len(presets)} 条经验")
        else:
            # 使用当前活跃经验库（由 Web 前端通过 bank_id 切换）
            print(f"[Exp1] 使用当前活跃经验库: {ai_handler.experience_library.path}")

    runner = Exp1Runner(ai_handler, map_handler, mode=mode)
    collector = Exp1MetricsCollector()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(output_dir, f"exp1_{mode}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    suite_path = os.path.join(EXP1_DIR, "exp1_suite.json")
    with open(suite_path, "r", encoding="utf-8") as f:
        suite = json.load(f)

    mode_label = "ACE" if mode == "ace" else "Base LLM"
    print(f"\n{'='*60}")
    print(f"[Exp1] 运行模式: {mode_label}")
    print(f"[Exp1] 任务总数: {len(suite['tasks'])}")
    print(f"[Exp1] 输出目录: {run_dir}")
    print(f"{'='*60}")

    for task_data in suite["tasks"]:
        task_id = task_data["id"]
        task_text = task_data["task"]
        task_type = task_data["task_type"]
        print(f"  [{mode_label}] 任务 #{task_id} [{task_type}]: {task_text[:50]}...", end=" ")

        start_time = time.time()
        try:
            output = runner.run_task(task_data)
            output["start_time"] = start_time
            output["end_time"] = time.time()
        except Exception as e:
            import traceback
            output = {
                "answer": "",
                "trace_entries": [],
                "ace_panel": {},
                "tool_calls": [],
                "code_executions": [],
                "start_time": start_time,
                "end_time": time.time(),
                "error": f"{str(e)}\n{traceback.format_exc()[:300]}",
            }
            print(f"❌ 异常: {str(e)[:60]}")

        record = collector.record_task(task_id, mode, task_data, output)
        status = "✓" if record["accuracy"] else "✗"
        print(f"{status} acc={record['accuracy']}, time={record['response_time']:.1f}s")

    summary = collector.summarize()
    summary["run_dir"] = os.path.relpath(os.path.abspath(run_dir))
    summary["run_name"] = datetime.strptime(timestamp, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    collector.export_csv(os.path.join(run_dir, "results.csv"))
    collector.export_json(os.path.join(run_dir, "summary.json"))

    # ---- 恢复原始经验库 ----
    if restored_experiences is not None:
        ai_handler.experience_library.experiences = restored_experiences
        ai_handler.experience_library.save()
        bank_name = getattr(ai_handler.experience_library, 'path', '?')
        print(f"[Exp1] 已恢复原始经验库: {len(restored_experiences)} 条经验 ({bank_name})")

    acc = summary.get(mode, {}).get("accuracy_rate", 0)
    print(f"\n  [{mode_label}] 准确率: {acc:.1f}%")
    print(f"  结果已保存至: {run_dir}\n")

    return summary


def main():
    parser = argparse.ArgumentParser(description="GeoAI Experiment Runner")
    parser.add_argument("--exp", type=int, default=1, help="实验编号（默认：1）")
    parser.add_argument("--mode", choices=["base", "ace", "both"], default="both",
                        help="运行模式")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    args = parser.parse_args()

    if args.exp == 1:
        print("=" * 60)
        print("  实验一：基线对比实验 - Base LLM vs ACE")
        print("=" * 60)

        # 尝试从已有日志加载模拟数据
        # 实际运行时需要提供 ai_handler 实例
        print("\n注意：实际运行需要 AIHandler 实例。")
        print("请通过 Web 服务或导入方式提供 ai_handler。\n")
    elif args.exp == 2:
        from experiments.exp2.exp2_runner import run_exp2

        print("=" * 60)
        print("  实验二：消融实验 - ACE 模块必要性验证")
        print("=" * 60)
        summary = run_exp2(output_dir=output_dir_for_exp(args.output, "exp2"))
        print(f"\n结果已保存至: {summary.get('run_dir', args.output)}")
        print("模块贡献排名:")
        for idx, item in enumerate(summary.get("contributions", []), 1):
            print(f"  {idx}. {item['module']} - {item['contribution_score']}")
    elif args.exp == 3:
        from experiments.exp3.exp3_runner import run_exp3

        print("=" * 60)
        print("  实验三：抗退化实验 - Base LLM vs ACE")
        print("=" * 60)
        summary = run_exp3(output_dir=output_dir_for_exp(args.output, "exp3"))
        print(f"\n结果已保存至: {summary.get('run_dir', args.output)}")
        for key, item in summary.get("systems", {}).items():
            print(f"  {item['name']}: recall={item['memory_recall_rate']}%, robustness={item['robustness_score']}")
    elif args.exp == 4:
        from experiments.exp4.exp4_runner import run_exp4

        print("=" * 60)
        print("  实验四：长上下文扩展场景对比实验")
        print("=" * 60)
        summary = run_exp4(output_dir=output_dir_for_exp(args.output, "exp4"))
        print(f"\n结果已保存至: {summary.get('run_dir', args.output)}")
        for key, item in summary.get("systems", {}).items():
            print(f"  {item['name']}: accuracy={item['long_sequence_accuracy']}%, robustness={item['robustness_score']}")
    else:
        print(f"实验 {args.exp} 尚未实现。")


if __name__ == "__main__":
    main()
