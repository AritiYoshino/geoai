import json
import os
from datetime import datetime


DEFAULT_EXPERIENCES = [
    {
        "id": "gis-crs-001",
        "category": "坐标系冲突",
        "task_types": ["nearby", "overlay", "mapping"],
        "trigger": "距离、附近、缓冲区、叠加分析前需要确认 CRS。",
        "problem": "在经纬度坐标系中直接计算距离会得到角度单位，导致范围分析错误。",
        "strategy": "执行距离分析前统一投影到米制 CRS；若数据缺少 CRS，先按 WGS84 设置并记录假设。",
        "source": "initial",
        "success_count": 0,
        "created_at": "2026-04-27T00:00:00",
    },
    {
        "id": "gis-field-001",
        "category": "字段验证",
        "task_types": ["query", "search"],
        "trigger": "用户提出行政区、类型、名称等属性筛选。",
        "problem": "LLM 容易猜测中文字段名，导致 query 使用不存在的列。",
        "strategy": "查询前读取图层字段清单，条件表达式必须使用真实字段名；字段错误时根据工具返回的可用字段重试。",
        "source": "initial",
        "success_count": 0,
        "created_at": "2026-04-27T00:00:00",
    },
    {
        "id": "gis-result-001",
        "category": "结果规模控制",
        "task_types": ["search", "query", "nearby"],
        "trigger": "模糊搜索或宽泛条件可能返回大量 POI。",
        "problem": "过多结果会挤占上下文并降低回答质量。",
        "strategy": "工具结果只摘要展示前若干条，但地图高亮保留完整匹配集合，并提醒用户缩小范围。",
        "source": "initial",
        "success_count": 0,
        "created_at": "2026-04-27T00:00:00",
    },
]


class ExperienceLibrary:
    """JSON-backed ACE experience library."""

    def __init__(self, path=os.path.join("data", "ace_experience_library.json")):
        self.path = path
        self.experiences = []
        self.load()

    def switch_path(self, path):
        self.path = path
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.experiences = json.load(f)
        else:
            self.experiences = list(DEFAULT_EXPERIENCES)
            self.save()

    def save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.experiences, f, ensure_ascii=False, indent=2)

    def retrieve(self, task, task_type, top_k=4):
        terms = set(task.lower().replace("，", " ").replace("。", " ").split())
        scored = []
        for exp in self.experiences:
            score = 0
            if task_type in exp.get("task_types", []):
                score += 4
            haystack = " ".join(
                str(exp.get(key, "")) for key in ("category", "trigger", "problem", "strategy")
            ).lower()
            score += sum(1 for term in terms if term and term in haystack)
            score += min(int(exp.get("success_count", 0)), 3)
            if score > 0:
                scored.append((score, exp))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [exp for _, exp in scored[:top_k]]

    def add_or_update(self, category, task_type, trigger, problem, strategy, source="critic"):
        fingerprint = f"{category}|{task_type}|{problem[:40]}"
        for exp in self.experiences:
            existing = f"{exp.get('category')}|{task_type}|{exp.get('problem', '')[:40]}"
            if existing == fingerprint:
                exp["success_count"] = int(exp.get("success_count", 0)) + 1
                exp["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self.save()
                return exp, False

        exp = {
            "id": f"ace-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.experiences) + 1}",
            "category": category,
            "task_types": [task_type],
            "trigger": trigger,
            "problem": problem,
            "strategy": strategy,
            "source": source,
            "success_count": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.experiences.append(exp)
        self.save()
        return exp, True

    def format_for_prompt(self, experiences):
        if not experiences:
            return "本次任务没有命中特定经验，请优先遵循通用 GIS 防御性编程规范。"
        lines = []
        for idx, exp in enumerate(experiences, 1):
            lines.append(
                f"{idx}. [{exp['category']}] 触发: {exp['trigger']} 策略: {exp['strategy']}"
            )
        return "\n".join(lines)

    def summary(self, limit=12):
        items = self.experiences[-limit:]
        return "\n".join(
            f"- {exp['id']} | {exp['category']} | {', '.join(exp.get('task_types', []))} | {exp['strategy']}"
            for exp in items
        )

    def clone_default_experiences(self):
        return json.loads(json.dumps(DEFAULT_EXPERIENCES, ensure_ascii=False))
