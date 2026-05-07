"""
实验一：基线对比实验
Base LLM vs ACE 核心性能增益验证

负责：
1. 加载测试任务集
2. 分别用 Base LLM 模式和 ACE 模式运行所有任务
3. 收集各项指标
4. 输出汇总结果
"""

import csv
import json
import os
import re
import time
from datetime import datetime


class Exp1MetricsCollector:
    """收集并汇总实验一的各项性能指标。"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.results = []  # 每个任务的详细结果
        self.summary = {}

    def record_task(self, task_id, mode, task_data, output):
        """
        记录一个任务的执行结果。

        Parameters
        ----------
        task_id : int
            任务ID
        mode : str
            'base' 或 'ace'
        task_data : dict
            测试任务定义
        output : dict
            系统输出，包含:
            - answer: str, 模型回答
            - trace_entries: list[dict], Trace条目
            - ace_panel: dict, ACE面板
            - tool_calls: list[str], 调用的工具名列表
            - code_executions: list[dict], 代码执行记录
            - start_time: float
            - end_time: float
            - error: str|None
        """
        checks = task_data.get("metric_checks", {})
        trace_entries = output.get("trace_entries", [])
        ace_panel = output.get("ace_panel", {})
        answer = output.get("answer", "")
        tool_calls = output.get("tool_calls", [])
        code_execs = output.get("code_executions", [])
        error = output.get("error")
        start_t = output.get("start_time", 0)
        end_t = output.get("end_time", 0)

        # --- 指标计算 ---

        # 1. 任务完成率：成功产出回答（无异常崩溃）
        task_completed = error is None and bool(answer and answer.strip())

        # 2. 工具调用成功率
        tool_invoked = len(tool_calls) > 0
        tool_success = True
        tool_failures = 0
        for call_info in tool_calls:
            if isinstance(call_info, dict):
                if call_info.get("status") == "error" or call_info.get("error"):
                    tool_success = False
                    tool_failures += 1
            elif isinstance(call_info, str) and "失败" in call_info:
                tool_success = False
                tool_failures += 1

        # 3. 代码执行成功率
        code_executed = len(code_execs) > 0
        code_success = True
        for exec_info in code_execs:
            if isinstance(exec_info, dict):
                if exec_info.get("status") != "success" and "error" in exec_info:
                    code_success = False
                    break

        # 4. 结果准确率（基于规则判断，模式感知）
        accuracy = self._check_accuracy(task_data, answer, tool_calls, trace_entries, mode=mode)

        # 5. ACE特有：经验命中率
        experience_hit = False
        if mode == "ace":
            retrieved = ace_panel.get("retrieved_experiences", "")
            experience_hit = bool(retrieved and retrieved.strip()
                                  and "没有命中" not in retrieved
                                  and "没有相关经验" not in retrieved)

        # 6. ACE特有：错误恢复率
        # 检测 CriticAgent 是否被触发且任务最终完成
        # ace_panel["error_diagnosis"] 非空 = Critic 检测到问题并产生诊断
        # task_completed = True = 系统从问题中恢复，成功产出回答
        error_recovered = False
        if mode == "ace":
            diagnosis = ace_panel.get("error_diagnosis", "")
            if diagnosis and task_completed:
                error_recovered = True

        # 7. 响应时间
        response_time = end_t - start_t if end_t > start_t else 0

        # 8. 偏好记忆（用于第13-14轮测试）
        preference_applied = False
        if mode == "ace" and task_data.get("id") == 14:
            # 检查是否只高亮了行政区
            preference_applied = (
                "行政区" in answer and "高亮" in answer
            )

        record = {
            "task_id": task_id,
            "mode": mode,
            "task": task_data["task"],
            "task_type": task_data["task_type"],
            "difficulty": task_data["difficulty"],
            "task_completed": task_completed,
            "tool_invoked": tool_invoked,
            "tool_success": tool_success,
            "tool_failures": tool_failures,
            "code_executed": code_executed,
            "code_success": code_success,
            "accuracy": accuracy,
            "experience_hit": experience_hit,
            "error_recovered": error_recovered,
            "response_time": round(response_time, 2),
            "preference_applied": preference_applied,
            "has_error": error is not None,
            "answer_preview": (answer or "")[:200],
            "tool_calls": tool_calls,
            "error": str(error) if error else "",
        }
        self.results.append(record)
        return record

    def _check_accuracy(self, task_data, answer, tool_calls, trace_entries, mode="ace"):
        """基于规则判断回答是否准确。（模式感知）"""
        if not answer or not answer.strip():
            return False

        checks = task_data.get("metric_checks", {})
        task_type = task_data["task_type"]
        expected_keywords = task_data.get("expected_keywords", [])
        expected_tools = task_data.get("expected_tools", [])

        # 统一转小写用于比对
        answer_lower = answer.lower()

        # help型：需要是文字说明，不应该调用工具
        if task_type == "help":
            if checks.get("requires_no_tool_call") and len(tool_calls) > 0:
                return False
            return any(kw.lower() in answer_lower for kw in expected_keywords)

        # feedback型
        if task_type == "feedback":
            return checks.get("requires_feedback_recognition", False)

        # memory型：依赖偏好记忆
        if task_type == "memory":
            return checks.get("requires_preference_applied", False)

        # --- 工具调用型任务 ---
        # Base 和 ACE 模式现在都会实际调用工具，统一判断逻辑
        if checks.get("requires_tool_call"):
            if not tool_calls:
                return False
            # 检查是否调用了期望的工具
            tool_names = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    tool_names.append(tc.get("name", ""))
                elif isinstance(tc, str):
                    tool_names.append(tc)
            has_expected = any(
                exp_tool in " ".join(tool_names)
                for exp_tool in expected_tools
            )
            if not has_expected and expected_tools:
                return False

        # 关键词匹配前做空格归一化（处理 "500米" vs "500 米" 的差异）
        def _normalize_space(text):
            return text.replace(" ", "").replace("\u00A0", "")

        # 检查关键信息（大小写不敏感，支持空格归一化）
        if expected_keywords:
            answer_normalized = _normalize_space(answer_lower)
            has_keywords = all(
                kw.lower() in answer_lower
                or _normalize_space(kw.lower()) in answer_normalized
                for kw in expected_keywords
            )
            if not has_keywords:
                return False

        return True

    def summarize(self):
        """汇总所有指标，生成summary dict。"""
        if not self.results:
            return {}

        base_results = [r for r in self.results if r["mode"] == "base"]
        ace_results = [r for r in self.results if r["mode"] == "ace"]

        def _calc(records):
            n = len(records) or 1
            return {
                "task_completion_rate": sum(1 for r in records if r["task_completed"]) / n * 100,
                "tool_success_rate": sum(1 for r in records if r["tool_success"]) / n * 100,
                "tool_invocation_rate": sum(1 for r in records if r["tool_invoked"]) / n * 100,
                "code_execution_rate": sum(1 for r in records if r["code_executed"]) / n * 100,
                "code_success_rate": sum(1 for r in records if r["code_success"]) / n * 100,
                "accuracy_rate": sum(1 for r in records if r["accuracy"]) / n * 100,
                "error_rate": sum(1 for r in records if r["has_error"]) / n * 100,
            }

        def _calc_ace_only(records):
            n = len(records) or 1
            return {
                "experience_hit_rate": sum(1 for r in records if r["experience_hit"]) / n * 100,
                "error_recovery_rate": sum(1 for r in records if r["error_recovered"]) / n * 100,
                "preference_persistence_rate": sum(1 for r in records if r.get("preference_applied")) / max(sum(1 for r in records if r["task_id"] in (13, 14)), 1) * 100,
            }

        base_summary = _calc(base_results)
        ace_summary = _calc(ace_results)
        ace_extra = _calc_ace_only(ace_results)

        # 计算提升
        improvements = {}
        for key in base_summary:
            bv = base_summary[key] or 0
            av = ace_summary.get(key, 0) or 0
            if bv != 0:
                improvements[key] = round(av - bv, 2)
                improvements[f"{key}_pct"] = round((av - bv) / bv * 100, 1)
            else:
                improvements[key] = round(av, 2)
                improvements[f"{key}_pct"] = 100.0 if av > 0 else 0

        # 按难度统计
        def _by_difficulty(records):
            diff_stats = {}
            for r in records:
                d = r["difficulty"]
                if d not in diff_stats:
                    diff_stats[d] = {"count": 0, "accuracy_sum": 0, "tool_success_sum": 0}
                diff_stats[d]["count"] += 1
                diff_stats[d]["accuracy_sum"] += 1 if r["accuracy"] else 0
                diff_stats[d]["tool_success_sum"] += 1 if r["tool_success"] else 0
            for d in diff_stats:
                c = diff_stats[d]["count"] or 1
                diff_stats[d]["accuracy_rate"] = round(diff_stats[d]["accuracy_sum"] / c * 100, 1)
                diff_stats[d]["tool_success_rate"] = round(diff_stats[d]["tool_success_sum"] / c * 100, 1)
            return diff_stats

        self.summary = {
            "experiment": "实验一：基线对比实验",
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(self.results) // 2,
            "base": base_summary,
            "ace": {**ace_summary, **ace_extra},
            "improvements": improvements,
            "base_by_difficulty": _by_difficulty(base_results),
            "ace_by_difficulty": _by_difficulty(ace_results),
            "task_details": self.results,
        }
        return self.summary

    def export_csv(self, path):
        """导出详细结果到CSV。"""
        if not self.results:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fields = [
            "task_id", "mode", "task_type", "difficulty",
            "task_completed", "tool_success", "code_success",
            "accuracy", "experience_hit", "error_recovered",
            "response_time", "has_error",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)

    def export_json(self, path):
        """导出完整汇总到JSON。"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=2)


DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "experiment_outputs", "exp1"))


def run_exp1(ai_handler, map_handler, mode="ace", output_dir=DEFAULT_OUTPUT_DIR):
    """
    运行实验一。

    Parameters
    ----------
    ai_handler : AIHandler
        系统的AI处理器（用于ACE模式）
    map_handler : BrowserMapHandler
        地图处理器
    mode : str
        'base' 或 'ace'
    output_dir : str
        输出目录

    Returns
    -------
    dict
        实验汇总结果
    """
    from experiments.exp1.exp1_runner import Exp1Runner

    runner = Exp1Runner(ai_handler, map_handler, mode=mode)
    collector = Exp1MetricsCollector()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(output_dir, f"exp1_{mode}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # 加载测试套件
    suite_path = os.path.join(os.path.dirname(__file__), "exp1_suite.json")
    with open(suite_path, "r", encoding="utf-8") as f:
        suite = json.load(f)

    print(f"[Exp1] 运行模式: {'ACE' if mode == 'ace' else 'Base LLM'}")
    print(f"[Exp1] 任务总数: {len(suite['tasks'])}")
    print(f"[Exp1] 输出目录: {run_dir}")
    print("-" * 60)

    for task_data in suite["tasks"]:
        task_id = task_data["id"]
        task_text = task_data["task"]
        print(f"[Exp1] 运行任务 #{task_id}: {task_text[:40]}...", end=" ")

        start_time = time.time()
        try:
            output = runner.run_task(task_data)
            output["start_time"] = start_time
            output["end_time"] = time.time()
        except Exception as e:
            output = {
                "answer": "",
                "trace_entries": [],
                "ace_panel": {},
                "tool_calls": [],
                "code_executions": [],
                "start_time": start_time,
                "end_time": time.time(),
                "error": str(e),
            }
            print(f"❌ 异常: {str(e)[:60]}")
            import traceback
            traceback.print_exc()

        record = collector.record_task(task_id, mode, task_data, output)
        status = "✓" if record["accuracy"] else "✗"
        print(f"{status} (准确率={record['accuracy']}, 耗时={record['response_time']:.1f}s)")

    summary = collector.summarize()
    summary["run_dir"] = os.path.relpath(os.path.abspath(run_dir))
    summary["run_name"] = datetime.strptime(timestamp, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")

    # 导出结果
    collector.export_csv(os.path.join(run_dir, "results.csv"))
    collector.export_json(os.path.join(run_dir, "summary.json"))

    print("-" * 60)
    print(f"[Exp1] 实验完成！结果已保存至: {run_dir}")
    mode_key = mode if mode in summary else list(summary.keys())[0] if summary else mode
    mode_label = "ACE" if mode == "ace" else "Base LLM"
    acc = summary.get(mode_key, {}).get("accuracy_rate", 0)
    print(f"[Exp1] {mode_label} 准确率: {acc:.1f}%")

    return summary
