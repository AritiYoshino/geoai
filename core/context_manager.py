import re

from core.ace_core import TraceRecorder, classify_task
from core.session_store import SessionStore


class ContextManager:
    """Owns short-term session context and prompt context for the agents."""

    def __init__(self, map_handler, session_store=None):
        self.map_handler = map_handler
        self.session_store = session_store or SessionStore()
        self.active_session = self.session_store.get_current_session()
        self.recent_pois = list(self.active_session.get("recent_pois", []))
        self.last_trace_text = self.active_session.get("last_trace_text", "尚未执行任务。")

    def classify_intent(self, user_input):
        return classify_task(user_input)

    def create_trace(self, user_input, task_type):
        return TraceRecorder(user_input, task_type)

    def get_schema_info(self):
        info_lines = []
        for gdf, name in zip(self.map_handler.gdfs, self.map_handler.layer_names):
            cols = gdf.select_dtypes(include=["object", "number"]).columns.tolist()
            if "geometry" in cols:
                cols.remove("geometry")
            crs = gdf.crs.to_string() if gdf.crs else "未知 CRS"
            info_lines.append(f"  - {name} ({len(gdf)} 条, {crs}): {', '.join(cols[:16])}")
        return "\n".join(info_lines) if info_lines else "无图层信息"

    def remember_pois(self, pois):
        if not pois:
            return
        existing = {(poi["layer"], poi["index"]) for poi in self.recent_pois}
        for poi in pois:
            key = (poi["layer"], poi["index"])
            if key not in existing:
                self.recent_pois.insert(0, poi)
                existing.add(key)
        self.recent_pois = self.recent_pois[:30]
        self.session_store.update_memory(recent_pois=self.recent_pois)

    def format_conversation_context(self, user_input):
        if not self.recent_pois:
            return "暂无可引用的上一轮 POI。"

        scored = self.score_relevant_pois(user_input)
        lines = []
        if scored and scored[0][0] >= 4:
            top = scored[0][1]
            lines.append(
                "最可能指代的上一轮 POI: "
                f"layer={top['layer']}, index={top['index']}, "
                f"name={top.get('name', '')}, type={top.get('type', '')}, "
                f"address={top.get('address', '')}, district={top.get('district', '')}"
            )
        lines.append("最近可引用 POI（可直接作为查询或邻近分析参考点）:")
        for _, poi in scored[:8]:
            lines.append(
                f"- layer={poi['layer']}, index={poi['index']}, "
                f"name={poi.get('name', '')}, type={poi.get('type', '')}, "
                f"address={poi.get('address', '')}, district={poi.get('district', '')}"
            )
        return "\n".join(lines)

    def select_relevant_pois(self, user_input):
        return [poi for _, poi in self.score_relevant_pois(user_input)]

    def score_relevant_pois(self, user_input):
        text = self._normalize(user_input)
        raw_text = user_input.lower()
        query_terms = self._query_terms(user_input)
        scored = []

        for recency, poi in enumerate(self.recent_pois):
            name = str(poi.get("name", ""))
            address = str(poi.get("address", ""))
            district = str(poi.get("district", ""))
            normalized_fields = self._normalize(" ".join([name, address, district]))
            score = max(0, 3 - recency // 5)

            for token in [name, address, district]:
                if token and token.lower() in raw_text:
                    score += 8

            for piece in self._name_pieces(name):
                normalized_piece = self._normalize(piece)
                if not normalized_piece:
                    continue
                if normalized_piece in text:
                    score += 7
                if text and text in normalized_piece:
                    score += 4

            for term in query_terms:
                if term and term in normalized_fields:
                    score += 5

            scored.append((score, poi))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    def _query_terms(self, user_input):
        normalized = self._normalize(user_input)
        terms = set()
        if normalized:
            terms.add(normalized)
        for match in re.findall(r"([\u4e00-\u9fffA-Za-z0-9]+?)的店", user_input):
            terms.add(self._normalize(match))
        for chunk in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", user_input):
            cleaned = self._normalize(chunk)
            if len(cleaned) >= 2:
                terms.add(cleaned)
        return terms

    def _normalize(self, text):
        text = str(text).lower()
        for token in ["的", "这个", "那个", "它", "其", "附近", "周边", "查询", "查找", "店"]:
            text = text.replace(token, "")
        return re.sub(r"[\s,，。；;:：()（）·\-_/]+", "", text)

    def _name_pieces(self, name):
        pieces = {name}
        bracket_matches = re.findall(r"[（(]([^）)]+)[）)]", name)
        for inside in bracket_matches:
            pieces.add(inside)
            if inside.startswith("成都"):
                pieces.add(inside[2:])
            if inside.endswith("店"):
                pieces.add(inside[:-1])
        for marker in ["店", "酒店", "中心", "祠", "路"]:
            if marker in name:
                for part in re.split(r"[\s（）()·\-_/]+", name):
                    if marker in part:
                        pieces.add(part)
                        pieces.add(part.replace("成都", "").replace("店", ""))
        return pieces

    def build_agent_prompt(self, task_type, plan, experience_text, conversation_context):
        schema_info = self.get_schema_info()
        return f"""
你是一个基于 ACE 机制的多 Agent 地理分析系统中的空间分析执行智能体。
协调者已经完成意图理解、上下文解析和任务调度，你需要按计划选择工具、生成空间分析代码，或生成最终回答。

## 协调者生成的计划
{plan}

## 当前任务类型
{task_type}

## 已激活经验
{experience_text}

## 会话上下文
{conversation_context}

## 可用数据图层及字段
{schema_info}

## 可用工具
1. search_poi(keyword): 跨图层全文搜索 POI。
2. query_poi_by_conditions(layer_name, conditions): 按真实字段名筛选指定图层。
3. find_nearby(target_layer, reference_layer, distance, unit): 查找参考图层附近的目标 POI。
4. find_nearby_point(reference_layer, reference_index, target_layer, distance, unit): 以单个要素为中心做邻近分析。
5. find_nearby_point_filtered(reference_layer, reference_index, target_layer, distance, keyword, unit): 以单个要素为中心做带关键词过滤的邻近分析。
6. get_poi_by_index(layer_name, feature_index): 按上下文解析出的图层和索引获取单个 POI 详情并高亮。
7. execute_spatial_code(task_description, code): 当固定工具不足时，生成并执行受控 GeoPandas/Pandas 空间分析代码。

## 代码生成规则
- 只有固定工具无法完成时才使用 execute_spatial_code。
- 代码不能 import，不能读写文件，不能调用系统命令。
- 可直接使用 layers、layer_names、pd、gpd、np、Point、reproject_to_meters。
- layers 是 dict[str, GeoDataFrame]，键是图层名，例如 layers["住宿服务_6474"]。
- 最终结果必须赋值给 RESULT。
- 如需地图高亮，可赋值 HIGHLIGHTS=[("图层名", 要素索引), ...]。
- 距离/面积分析必须先用 reproject_to_meters 转成米制投影。

## 执行规则
- 属性查询必须使用 schema 中真实存在的字段名，禁止猜字段。
- “它、这个、那个、X 的店、上面那个”等省略表达必须优先参考“最可能指代的上一轮 POI”。
- 如果只是查询上下文中某个店的详情，优先调用 get_poi_by_index。
- 涉及“附近、距离、公里、米”的任务必须考虑 CRS 和米制投影风险。
- 工具返回大量结果时，回答摘要即可，并说明地图已高亮匹配要素。
- 回答要简洁说明分析步骤和结论。
"""

    def set_trace(self, trace):
        self.last_trace_text = trace.render()
        self.session_store.update_memory(
            recent_pois=self.recent_pois,
            last_trace_text=self.last_trace_text,
        )

    def get_trace_text(self):
        return self.last_trace_text

    def add_message(self, role, content):
        self.session_store.add_message(role, content)

    def add_feedback(self, feedback_type, user_task, assistant_answer, correction=""):
        self.session_store.add_feedback(feedback_type, user_task, assistant_answer, correction)

    def get_last_exchange(self):
        messages = self.get_current_session().get("messages", [])
        last_user = ""
        last_assistant = ""
        for message in reversed(messages):
            if not last_assistant and message.get("role") == "assistant":
                last_assistant = message.get("content", "")
            elif not last_user and message.get("role") == "user":
                last_user = message.get("content", "")
            if last_user and last_assistant:
                break
        return last_user, last_assistant

    def list_sessions(self):
        return self.session_store.list_sessions()

    def new_session(self, title=None):
        self.active_session = self.session_store.create_session(title)
        self.recent_pois = []
        self.last_trace_text = self.active_session.get("last_trace_text", "尚未执行任务。")
        return self.active_session

    def switch_session(self, session_id):
        self.active_session = self.session_store.switch_session(session_id)
        self.recent_pois = list(self.active_session.get("recent_pois", []))
        self.last_trace_text = self.active_session.get("last_trace_text", "尚未执行任务。")
        return self.active_session

    def get_current_session(self):
        return self.session_store.get_current_session()
