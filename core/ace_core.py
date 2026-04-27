import re
from dataclasses import dataclass, field
from datetime import datetime


TASK_KEYWORDS = {
    "nearby": ["附近", "周边", "距离", "km", "公里", "米", "缓冲", "near"],
    "query": ["筛选", "查询", "属于", "类型", "行政区", "district", "type", "where"],
    "search": ["搜索", "查找", "找", "包含", "名字", "名称", "search"],
    "mapping": ["地图", "高亮", "显示", "制图", "可视化"],
    "overlay": ["叠加", "相交", "覆盖", "裁剪", "overlay", "intersect"],
}


def classify_task(text):
    lowered = text.lower()
    scores = {
        task_type: sum(1 for keyword in keywords if keyword in lowered)
        for task_type, keywords in TASK_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


@dataclass
class TraceRecorder:
    task: str
    task_type: str
    entries: list = field(default_factory=list)

    def add(self, role, content):
        self.entries.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "role": role,
                "content": content,
            }
        )

    def render(self):
        lines = [f"任务类型: {self.task_type}", f"用户任务: {self.task}", ""]
        for entry in self.entries:
            lines.append(f"[{entry['time']}] {entry['role']}")
            lines.append(str(entry["content"]))
            lines.append("")
        return "\n".join(lines).strip()


class CriticAgent:
    """Rule-based critic that converts tool feedback into reusable diagnostics."""

    ERROR_PATTERNS = [
        ("字段验证", r"不存在的字段|not in index|UndefinedVariableError|字段"),
        ("坐标系冲突", r"CRS|坐标|投影|Cannot transform|geographic CRS"),
        ("结果为空", r"未找到|没有找到|empty|0 个|0个"),
        ("工具执行异常", r"出错|错误|Traceback|Exception|失败"),
        ("结果规模控制", r"仅显示前|结果已截断|过多"),
    ]

    def diagnose(self, task, task_type, tool_name, tool_args, result):
        text = str(result)
        for category, pattern in self.ERROR_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    "category": category,
                    "trigger": f"任务类型={task_type}, 工具={tool_name}, 参数={tool_args}",
                    "problem": self._problem(category, text),
                    "strategy": self._strategy(category),
                }
        return None

    def _problem(self, category, text):
        snippet = text.replace("\n", " ")[:160]
        defaults = {
            "字段验证": "工具反馈显示字段或条件表达式可能不匹配数据 schema。",
            "坐标系冲突": "空间距离或投影处理存在 CRS 风险。",
            "结果为空": "当前检索条件过窄、图层选择错误或地名表达与数据不一致。",
            "工具执行异常": "工具运行中出现异常，需要把错误信息转化为下一轮约束。",
            "结果规模控制": "返回结果规模过大，需要摘要输出并保留地图高亮。",
        }
        return f"{defaults.get(category, '发现可复用问题。')} 原始反馈: {snippet}"

    def _strategy(self, category):
        return {
            "字段验证": "重新读取图层字段，使用真实列名构造条件；优先让工具错误中的可用字段清单指导重试。",
            "坐标系冲突": "距离分析统一转为米制投影，并在回答中说明距离单位和 CRS 假设。",
            "结果为空": "先用 search_poi 做宽松定位，再用精确查询或邻近分析逐步收窄。",
            "工具执行异常": "保留 traceback 摘要，调整参数、图层名或字段名后再次调用工具。",
            "结果规模控制": "回答只展示摘要和代表样本，地图端继续高亮全部匹配结果。",
        }.get(category, "将本次问题整理成下一轮提示约束。")


class EvolutionManager:
    def __init__(self, library):
        self.library = library

    def evolve(self, diagnostic, task_type):
        return self.library.add_or_update(
            category=diagnostic["category"],
            task_type=task_type,
            trigger=diagnostic["trigger"],
            problem=diagnostic["problem"],
            strategy=diagnostic["strategy"],
        )
