import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher


MIN_PROMPT_CONFIDENCE = 0.35


DEFAULT_EXPERIENCES = [
    {
        "id": "gis-crs-001",
        "category": "坐标系统冲突",
        "task_types": ["nearby", "overlay", "mapping"],
        "trigger": "距离、邻近、缓冲区、叠加分析前需要确认 CRS。",
        "problem": "在经纬度坐标系中直接计算距离会得到角度单位，导致范围分析错误。",
        "strategy": "执行距离分析前统一投影到米制 CRS；若数据缺少 CRS，先按 WGS84 设置并记录假设。",
        "source": "initial",
        "success_count": 0,
        "fail_count": 0,
        "confidence": 0.5,
        "created_at": "2026-04-27T00:00:00",
        "updated_at": "2026-04-27T00:00:00",
        "last_used_at": "",
    },
    {
        "id": "gis-field-001",
        "category": "字段验证",
        "task_types": ["query", "search"],
        "trigger": "用户提出行政区、类型、名称等属性筛选。",
        "problem": "LLM 容易猜测字段名，导致 query 使用不存在的列。",
        "strategy": "查询前读取图层字段清单，条件表达式必须使用真实字段名；字段错误时根据工具返回的可用字段重试。",
        "source": "initial",
        "success_count": 0,
        "fail_count": 0,
        "confidence": 0.5,
        "created_at": "2026-04-27T00:00:00",
        "updated_at": "2026-04-27T00:00:00",
        "last_used_at": "",
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
        "fail_count": 0,
        "confidence": 0.5,
        "created_at": "2026-04-27T00:00:00",
        "updated_at": "2026-04-27T00:00:00",
        "last_used_at": "",
    },
]


class ExperienceLibrary:
    """JSON-backed ACE experience library with quality tracking."""

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
            return

        changed = False
        normalized = []
        for exp in self.experiences:
            one, one_changed = self._normalize_experience(exp)
            normalized.append(one)
            changed = changed or one_changed
        self.experiences = normalized
        if changed:
            self.save()

    def save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.experiences, f, ensure_ascii=False, indent=2)

    def retrieve(self, task, task_type, top_k=4, min_confidence=MIN_PROMPT_CONFIDENCE):
        terms = self._task_terms(task)
        scored = []
        now = self._now()

        for exp in self.experiences:
            exp, _ = self._normalize_experience(exp)
            if task_type not in exp.get("task_types", []):
                continue
            if float(exp.get("confidence", 0.0)) < float(min_confidence):
                continue

            score = 4.0
            haystack = " ".join(
                str(exp.get(key, "")) for key in ("category", "trigger", "problem", "strategy")
            ).lower()
            score += sum(1.0 for term in terms if term and term in haystack)
            if exp.get("source") == "user_feedback" and exp.get("category") == "用户纠正":
                score += 2.5
            score += min(float(exp.get("confidence", 0.0)) * 3.0, 3.0)
            score += min(int(exp.get("success_count", 0)), 3)
            if exp.get("last_used_at"):
                score += 0.5
            scored.append((score, exp))

        scored.sort(key=lambda item: item[0], reverse=True)
        picked = [exp for _, exp in scored[:top_k]]
        for exp in picked:
            exp["last_used_at"] = now
        if picked:
            self.save()
        return picked

    def retrieve_by_task_type(self, task_type, top_k=10, min_confidence=MIN_PROMPT_CONFIDENCE):
        candidates = [
            exp for exp in self.experiences
            if task_type in exp.get("task_types", [])
            and float(exp.get("confidence", 0.0)) >= float(min_confidence)
        ]
        candidates.sort(
            key=lambda exp: (
                float(exp.get("confidence", 0.0)),
                int(exp.get("success_count", 0)) - int(exp.get("fail_count", 0)),
                exp.get("updated_at", ""),
            ),
            reverse=True,
        )
        return candidates[:top_k]

    def add_or_update(
        self,
        category,
        task_type,
        trigger,
        problem,
        strategy,
        source="critic",
        outcome="success",
    ):
        now = self._now()
        match = self._find_similar_experience(category, task_type, trigger, problem, strategy)
        if match is not None:
            exp = match
            task_types = set(exp.get("task_types", []))
            task_types.add(task_type)
            exp["task_types"] = sorted(task_types)
            exp["trigger"] = self._prefer_longer_text(exp.get("trigger", ""), trigger)
            exp["problem"] = self._prefer_longer_text(exp.get("problem", ""), problem)
            exp["strategy"] = self._prefer_longer_text(exp.get("strategy", ""), strategy)
            exp["updated_at"] = now
            exp["last_used_at"] = now
            self._apply_outcome(exp, outcome)
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
            "success_count": 0,
            "fail_count": 0,
            "confidence": 0.5,
            "created_at": now,
            "updated_at": now,
            "last_used_at": now,
        }
        self._apply_outcome(exp, outcome)
        self.experiences.append(exp)
        self.save()
        return exp, True

    def format_for_prompt(self, experiences):
        prompt_ready = [
            exp for exp in experiences
            if float(exp.get("confidence", 0.0)) >= MIN_PROMPT_CONFIDENCE
        ]
        if not prompt_ready:
            return "本次任务没有命中高置信经验，请优先遵循通用 GIS 防御性编程规范。"

        lines = []
        for idx, exp in enumerate(prompt_ready, 1):
            lines.append(
                f"{idx}. [{exp['category']}] 触发: {exp['trigger']} "
                f"策略: {exp['strategy']} "
                f"(confidence={float(exp.get('confidence', 0.0)):.2f}, "
                f"success={int(exp.get('success_count', 0))}, fail={int(exp.get('fail_count', 0))})"
            )
        return "\n".join(lines)

    def summary(self, limit=12):
        items = sorted(
            self.experiences,
            key=lambda exp: exp.get("updated_at", exp.get("created_at", "")),
            reverse=True,
        )[:limit]
        return "\n".join(
            f"- {exp['id']} | {exp['category']} | {', '.join(exp.get('task_types', []))} | "
            f"confidence={float(exp.get('confidence', 0.0)):.2f} | "
            f"success={int(exp.get('success_count', 0))} | fail={int(exp.get('fail_count', 0))} | "
            f"last_used={exp.get('last_used_at', '') or '-'}"
            for exp in items
        )

    def clone_default_experiences(self):
        return json.loads(json.dumps(DEFAULT_EXPERIENCES, ensure_ascii=False))

    def _find_similar_experience(self, category, task_type, trigger, problem, strategy):
        candidate_text = self._fingerprint_text(category, task_type, trigger, problem, strategy)
        best_match = None
        best_score = 0.0
        for exp in self.experiences:
            exp, _ = self._normalize_experience(exp)
            if exp.get("category") != category:
                continue
            existing_task_types = set(exp.get("task_types", []))
            if task_type not in existing_task_types and existing_task_types:
                continue
            score = SequenceMatcher(
                None,
                candidate_text,
                self._fingerprint_text(
                    exp.get("category", ""),
                    ",".join(exp.get("task_types", [])),
                    exp.get("trigger", ""),
                    exp.get("problem", ""),
                    exp.get("strategy", ""),
                ),
            ).ratio()
            if score > best_score:
                best_score = score
                best_match = exp
        return best_match if best_score >= 0.72 else None

    def _apply_outcome(self, exp, outcome):
        outcome = (outcome or "success").lower()
        if outcome == "failure":
            exp["fail_count"] = int(exp.get("fail_count", 0)) + 1
        elif outcome == "neutral":
            pass
        else:
            exp["success_count"] = int(exp.get("success_count", 0)) + 1
        exp["confidence"] = self._calc_confidence(
            int(exp.get("success_count", 0)),
            int(exp.get("fail_count", 0)),
        )
        if exp.get("source") == "user_feedback" and exp.get("category") == "用户纠正":
            exp["confidence"] = max(float(exp.get("confidence", 0.0)), 0.5)

    def _calc_confidence(self, success_count, fail_count):
        total = success_count + fail_count
        if total <= 0:
            return 0.5
        return round((success_count + 1) / (total + 2), 3)

    def _normalize_experience(self, exp):
        changed = False
        data = dict(exp)
        if not data.get("task_types"):
            data["task_types"] = ["general"]
            changed = True
        if isinstance(data.get("task_types"), str):
            data["task_types"] = [data["task_types"]]
            changed = True

        for key, default in (
            ("success_count", 0),
            ("fail_count", 0),
            ("trigger", ""),
            ("problem", ""),
            ("strategy", ""),
            ("source", "unknown"),
        ):
            if key not in data:
                data[key] = default
                changed = True

        if data.get("source") == "user_feedback" and data.get("category") == "用户纠正":
            if int(data.get("fail_count", 0)) != 0:
                data["fail_count"] = 0
                changed = True

        if "created_at" not in data:
            data["created_at"] = self._now()
            changed = True
        if "updated_at" not in data:
            data["updated_at"] = data["created_at"]
            changed = True
        if "last_used_at" not in data:
            data["last_used_at"] = ""
            changed = True

        expected_confidence = self._calc_confidence(
            int(data.get("success_count", 0)),
            int(data.get("fail_count", 0)),
        )
        if data.get("source") == "user_feedback" and data.get("category") == "用户纠正":
            expected_confidence = max(expected_confidence, 0.5)
        if data.get("confidence") is None:
            data["confidence"] = expected_confidence
            changed = True
        else:
            try:
                data["confidence"] = float(data["confidence"])
            except Exception:
                data["confidence"] = expected_confidence
                changed = True
        if abs(float(data["confidence"]) - expected_confidence) > 0.001:
            data["confidence"] = expected_confidence
            changed = True
        return data, changed

    def _task_terms(self, task):
        task = str(task or "").lower()
        chunks = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{2,}", task)
        terms = set(chunks)
        for chunk in chunks:
            if re.fullmatch(r"[\u4e00-\u9fff]{3,}", chunk):
                for size in range(2, min(len(chunk), 6) + 1):
                    for start in range(0, len(chunk) - size + 1):
                        terms.add(chunk[start:start + size])
        return {term for term in terms if term}

    def _fingerprint_text(self, category, task_type, trigger, problem, strategy):
        text = " | ".join([str(category), str(task_type), str(trigger), str(problem), str(strategy)]).lower()
        return " ".join(text.split())

    def _prefer_longer_text(self, old_text, new_text):
        old_text = str(old_text or "").strip()
        new_text = str(new_text or "").strip()
        return new_text if len(new_text) > len(old_text) else old_text

    def _now(self):
        return datetime.now().isoformat(timespec="seconds")
