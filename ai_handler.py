import os
import re
import time

_MODULE_START = time.perf_counter()


def _startup_timing(label, start):
    print(f"[startup][timing] {label}: {time.perf_counter() - start:.3f}s", flush=True)


_step = time.perf_counter()
from langchain_deepseek import ChatDeepSeek
_startup_timing("import langchain_deepseek.ChatDeepSeek", _step)

_step = time.perf_counter()
from agents import CodeAgent, CoordinatorAgent, CriticAgent, EvolutionAgent, SpatialAnalystAgent
_startup_timing("import agents", _step)

_step = time.perf_counter()
from core.context_manager import ContextManager
from core.experience_bank_manager import ExperienceBankManager
from core.experience_library import ExperienceLibrary
from core.jsonl_logger import log_error, log_task
_startup_timing("import core AI dependencies", _step)

_step = time.perf_counter()
from tools import create_tools
_startup_timing("import tools", _step)
_startup_timing("import ai_handler module total", _MODULE_START)


class AIHandler:
    """Application-facing facade that wires the multi-agent system together."""

    POSITIVE_ONLY_PATTERN = re.compile(
        r"^\s*(好|好的|可以|没问题|对|对的|正确|没错|是的|明白了|收到|ok|okay|yes)\s*[!！。.\s]*$",
        re.I,
    )
    NEGATIVE_PREFIX_PATTERN = re.compile(
        r"^\s*(不对|不正确|错了|错的|有误|不是这个|不是这样|不太对|不行|不对劲)[,，:：!！。\s]*",
        re.I,
    )

    def __init__(self, api_key, map_handler):
        init_start = time.perf_counter()
        self.map_handler = map_handler
        step = time.perf_counter()
        self._disable_broken_proxy_env()
        _startup_timing("AIHandler disable proxy env", step)

        step = time.perf_counter()
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.3,
            api_key=api_key,
            timeout=30,
            max_retries=2,
        )
        _startup_timing("AIHandler create ChatDeepSeek", step)

        step = time.perf_counter()
        self.experience_bank_manager = ExperienceBankManager()
        _startup_timing("AIHandler create ExperienceBankManager", step)

        step = time.perf_counter()
        self.experience_library = ExperienceLibrary(self.experience_bank_manager.active_path())
        _startup_timing("AIHandler create ExperienceLibrary", step)

        step = time.perf_counter()
        self.context_manager = ContextManager(map_handler)
        _startup_timing("AIHandler create ContextManager", step)

        step = time.perf_counter()
        self.tools = create_tools(self)
        _startup_timing("AIHandler create tools", step)

        step = time.perf_counter()
        self.code_agent = CodeAgent(self.llm, self)
        _startup_timing("AIHandler create CodeAgent", step)

        step = time.perf_counter()
        self.spatial_agent = SpatialAnalystAgent(self.llm, self.tools, self, code_agent=self.code_agent)
        _startup_timing("AIHandler create SpatialAnalystAgent", step)

        step = time.perf_counter()
        self.critic_agent = CriticAgent()
        _startup_timing("AIHandler create CriticAgent", step)

        step = time.perf_counter()
        self.evolution_agent = EvolutionAgent(self.experience_library)
        _startup_timing("AIHandler create EvolutionAgent", step)

        step = time.perf_counter()
        self.coordinator_agent = CoordinatorAgent(
            context_manager=self.context_manager,
            experience_library=self.experience_library,
            spatial_agent=self.spatial_agent,
            critic_agent=self.critic_agent,
            evolution_agent=self.evolution_agent,
        )
        _startup_timing("AIHandler create CoordinatorAgent", step)
        _startup_timing("AIHandler init total", init_start)

    def _disable_broken_proxy_env(self):
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            os.environ.pop(key, None)

    def _store_highlights(self, highlight_infos):
        self._last_highlights = highlight_infos

    def _store_generated_result(self, name, gdf):
        self._last_generated_result = {"name": name, "gdf": gdf}

    def consume_last_export(self):
        export = getattr(self, "_last_export", None)
        if hasattr(self, "_last_export"):
            delattr(self, "_last_export")
        return export

    def process_message(self, user_input, highlight_callback):
        preference_note, should_continue = self._apply_preference_message(user_input)
        feedback_note, task_input = self._handle_inline_feedback(user_input)
        self.context_manager.add_message("user", user_input)

        try:
            if task_input is None or not should_continue:
                answer = "\n\n".join(
                    part
                    for part in [preference_note, feedback_note, "已记录你的反馈或偏好，并同步更新经验库。"]
                    if part
                )
            else:
                answer = self.coordinator_agent.run(task_input, highlight_callback)
                prefix = "\n\n".join(part for part in [preference_note, feedback_note] if part)
                if prefix:
                    answer = f"{prefix}\n\n{answer}"

            self.context_manager.add_message("assistant", answer)
            log_task(
                {
                    "session_id": self.get_current_session().get("id", ""),
                    "user_input": user_input,
                    "effective_task": task_input,
                    "answer_preview": answer[:500],
                    "task_type": self.context_manager.classify_intent(task_input or user_input),
                }
            )
            return answer
        except Exception as exc:
            log_error(
                {
                    "source": "ai_handler.process_message",
                    "session_id": self.get_current_session().get("id", ""),
                    "user_input": user_input,
                    "error": str(exc),
                }
            )
            raise

    def _handle_inline_feedback(self, user_input):
        user_task, assistant_answer = self.context_manager.get_last_exchange()
        if not user_task or not assistant_answer:
            return "", user_input

        parsed = self._parse_feedback_message(user_input)
        if not parsed:
            return "", user_input

        task_type = self.context_manager.classify_intent(user_task)
        exp, created = self.evolution_agent.learn_from_user_feedback(
            feedback_type=parsed["feedback_type"],
            task_type=task_type,
            user_task=user_task,
            assistant_answer=assistant_answer,
            correction=parsed["correction"],
        )
        self.context_manager.add_feedback(
            parsed["feedback_type"],
            user_task,
            assistant_answer,
            parsed["correction"],
        )
        self._store_preference_from_text(parsed["correction"] or user_input)
        action = "新增经验" if created else "更新经验"
        note = f"已记录你的反馈，并{action}：[{exp['category']}] {exp['strategy']}"
        return note, parsed["followup_task"]

    def _apply_preference_message(self, user_input):
        note = self._store_preference_from_text(user_input)
        if not note:
            return "", True
        parsed_feedback = self._parse_feedback_message(user_input)
        if parsed_feedback:
            return note, True
        if self._looks_like_standalone_preference(user_input):
            return note, False
        return note, True

    def _parse_feedback_message(self, user_input):
        text = (user_input or "").strip()
        if not text:
            return None

        if self.POSITIVE_ONLY_PATTERN.fullmatch(text):
            return {
                "feedback_type": "correct",
                "correction": "",
                "followup_task": None,
            }

        negative_match = self.NEGATIVE_PREFIX_PATTERN.match(text)
        if not negative_match:
            return None

        remainder = text[negative_match.end():].strip()
        correction = self._extract_correction_text(remainder)
        followup_task = correction or remainder or None
        feedback_type = "correction" if correction else "incorrect"

        if followup_task:
            followup_task = followup_task.strip("，,。；;：:!！ ")
            if not followup_task:
                followup_task = None

        return {
            "feedback_type": feedback_type,
            "correction": correction or remainder,
            "followup_task": followup_task,
        }

    def _extract_correction_text(self, text):
        if not text:
            return ""
        starters = [
            "应该改成",
            "应该改为",
            "应该是",
            "应该",
            "要改成",
            "改成",
            "改为",
            "请改成",
            "请改为",
            "我的意思是",
            "我是说",
            "要怎么改",
        ]
        for starter in starters:
            if starter in text:
                return text.split(starter, 1)[1].strip("，,。；;：:!！ ")
        return text.strip("，,。；;：:!！ ")

    def _store_preference_from_text(self, text):
        text = (text or "").strip()
        if not text:
            return ""

        notes = []
        if (
            ("行政区" in text or "区的shp" in text or "区 shp" in text or "面图层" in text)
            and ("不是点" in text or "不高亮点" in text or "只高亮" in text or "不要高亮部分餐馆位置" in text)
        ):
            self.context_manager.set_user_preference("highlight_mode", "admin_polygon_only")
            self.context_manager.set_user_preference("avoid_partial_poi_highlight", True)
            self.context_manager.set_user_preference("preferred_highlight_layer", "成都行政区")
            notes.append("已记住本会话高亮偏好：统计区级结果时只高亮行政区面图层，不高亮餐馆点。")
        elif "不高亮部分餐馆位置" in text or "不要高亮部分餐馆位置" in text or "不要高亮餐馆点" in text:
            self.context_manager.set_user_preference("avoid_partial_poi_highlight", True)
            notes.append("已记住本会话偏好：不要高亮部分餐馆位置。")

        return "\n".join(notes)

    def _looks_like_standalone_preference(self, text):
        text = (text or "").strip()
        if not text:
            return False
        markers = [
            "不高亮部分餐馆位置",
            "不要高亮部分餐馆位置",
            "不要高亮餐馆点",
            "高亮的是行政区",
            "只高亮行政区",
            "不是点shp",
            "不是点 shp",
        ]
        return any(marker in text for marker in markers)

    def get_trace_text(self):
        return self.context_manager.get_trace_text()

    def get_ace_panel(self):
        return self.context_manager.get_ace_panel()

    def get_experience_summary(self):
        active = self.experience_bank_manager.active_bank()
        body = self.experience_library.summary() or "经验库为空。"
        return f"当前经验库: {active['name']} ({active['path']})\n\n{body}"

    def list_sessions(self):
        return self.context_manager.list_sessions()

    def new_session(self):
        return self.context_manager.new_session()

    def switch_session(self, session_id):
        return self.context_manager.switch_session(session_id)

    def rename_session(self, session_id, title):
        return self.context_manager.rename_session(session_id, title)

    def delete_session(self, session_id):
        return self.context_manager.delete_session(session_id)

    def get_current_session(self):
        return self.context_manager.get_current_session()

    def submit_feedback(self, feedback_type, correction=""):
        user_task, assistant_answer = self.context_manager.get_last_exchange()
        if not user_task or not assistant_answer:
            return "还没有可评价的上一轮结果。"

        task_type = self.context_manager.classify_intent(user_task)
        exp, created = self.evolution_agent.learn_from_user_feedback(
            feedback_type=feedback_type,
            task_type=task_type,
            user_task=user_task,
            assistant_answer=assistant_answer,
            correction=correction,
        )
        self.context_manager.add_feedback(feedback_type, user_task, assistant_answer, correction)
        action = "新增经验" if created else "强化已有经验"
        return f"{action}: [{exp['category']}] {exp['strategy']}"

    def list_experience_banks(self):
        return self.experience_bank_manager.list_banks()

    def get_active_experience_bank(self):
        return self.experience_bank_manager.active_bank()

    def switch_experience_bank(self, bank_id):
        bank = self.experience_bank_manager.switch(bank_id)
        self.experience_library.switch_path(bank["path"])
        return bank

    def create_experience_bank(self, name, template="empty"):
        if template == "default":
            source = self.experience_library.clone_default_experiences()
        elif template == "copy_current":
            source = self.experience_library.experiences
        else:
            source = []
        bank = self.experience_bank_manager.create_bank(name, template, source)
        self.experience_library.switch_path(bank["path"])
        return bank

    def rename_experience_bank(self, bank_id, name):
        return self.experience_bank_manager.rename_bank(bank_id, name)

    def delete_experience_bank(self, bank_id):
        bank = self.experience_bank_manager.delete_bank(bank_id)
        self.experience_library.switch_path(self.experience_bank_manager.active_path())
        return bank
