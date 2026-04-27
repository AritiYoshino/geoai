from langchain_deepseek import ChatDeepSeek
import os

from agents import CoordinatorAgent, ReflectorAgent, SpatialAnalystAgent
from core.context_manager import ContextManager
from core.experience_bank_manager import ExperienceBankManager
from core.experience_library import ExperienceLibrary
from tools import create_tools


class AIHandler:
    """Application-facing facade that wires the multi-agent system together."""

    def __init__(self, api_key, map_handler):
        self.map_handler = map_handler
        self._disable_broken_proxy_env()
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.3,
            api_key=api_key,
            timeout=30,
            max_retries=2,
        )

        self.experience_bank_manager = ExperienceBankManager()
        self.experience_library = ExperienceLibrary(self.experience_bank_manager.active_path())
        self.context_manager = ContextManager(map_handler)

        # Tools write transient highlights / POI hits onto this facade.
        self.tools = create_tools(self)
        self.spatial_agent = SpatialAnalystAgent(self.llm, self.tools, self)
        self.reflector_agent = ReflectorAgent(self.experience_library)
        self.coordinator_agent = CoordinatorAgent(
            context_manager=self.context_manager,
            experience_library=self.experience_library,
            spatial_agent=self.spatial_agent,
            reflector_agent=self.reflector_agent,
        )

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

    def process_message(self, user_input, highlight_callback):
        self.context_manager.add_message("user", user_input)
        answer = self.coordinator_agent.run(user_input, highlight_callback)
        self.context_manager.add_message("assistant", answer)
        return answer

    def get_trace_text(self):
        return self.context_manager.get_trace_text()

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

    def get_current_session(self):
        return self.context_manager.get_current_session()

    def submit_feedback(self, feedback_type, correction=""):
        user_task, assistant_answer = self.context_manager.get_last_exchange()
        if not user_task or not assistant_answer:
            return "还没有可评价的上一轮结果。"

        task_type = self.context_manager.classify_intent(user_task)
        exp, created = self.reflector_agent.learn_from_user_feedback(
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
