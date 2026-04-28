import json
import os
from datetime import datetime
from uuid import uuid4


class SessionStore:
    """Persistent chat/session memory used by the context manager."""

    def __init__(self, path=os.path.join("data", "sessions.json")):
        self.path = path
        self.data = {"current_session_id": None, "sessions": []}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        if not self.data.get("sessions"):
            self.create_session("默认会话")

    def save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def list_sessions(self):
        return sorted(
            self.data.get("sessions", []),
            key=lambda session: session.get("updated_at", ""),
            reverse=True,
        )

    def get_current_session(self):
        session_id = self.data.get("current_session_id")
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session("默认会话")
        return session

    def get_session(self, session_id):
        for session in self.data.get("sessions", []):
            if session.get("id") == session_id:
                return session
        return None

    def create_session(self, title=None):
        now = datetime.now().isoformat(timespec="seconds")
        session = {
            "id": uuid4().hex[:12],
            "title": title or f"新会话 {datetime.now().strftime('%m-%d %H:%M')}",
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "feedback": [],
            "recent_pois": [],
            "user_preferences": {},
            "last_trace_text": "尚未执行任务。",
            "last_ace_panel": {},
        }
        self.data.setdefault("sessions", []).append(session)
        self.data["current_session_id"] = session["id"]
        self.save()
        return session

    def switch_session(self, session_id):
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"未找到会话 {session_id}")
        self.data["current_session_id"] = session_id
        self.save()
        return session

    def touch(self, session):
        session["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.save()

    def add_message(self, role, content):
        session = self.get_current_session()
        session.setdefault("messages", []).append(
            {
                "role": role,
                "content": content,
                "time": datetime.now().isoformat(timespec="seconds"),
            }
        )
        if role == "user" and len(session["messages"]) <= 1:
            session["title"] = content[:24] or session["title"]
        self.touch(session)
        return session

    def update_memory(self, recent_pois=None, last_trace_text=None, last_ace_panel=None, user_preferences=None):
        session = self.get_current_session()
        if recent_pois is not None:
            session["recent_pois"] = recent_pois
        if last_trace_text is not None:
            session["last_trace_text"] = last_trace_text
        if last_ace_panel is not None:
            session["last_ace_panel"] = last_ace_panel
        if user_preferences is not None:
            session["user_preferences"] = user_preferences
        self.touch(session)
        return session

    def add_feedback(self, feedback_type, user_task, assistant_answer, correction=""):
        session = self.get_current_session()
        session.setdefault("feedback", []).append(
            {
                "type": feedback_type,
                "user_task": user_task,
                "assistant_answer": assistant_answer,
                "correction": correction,
                "time": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self.touch(session)
        return session

    def rename_session(self, session_id, title):
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"未找到会话 {session_id}")
        title = (title or "").strip()
        if not title:
            raise ValueError("会话名称不能为空")
        session["title"] = title[:60]
        self.touch(session)
        return session

    def delete_session(self, session_id):
        sessions = self.data.get("sessions", [])
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"未找到会话 {session_id}")
        if len(sessions) <= 1:
            raise ValueError("至少需要保留一个会话")

        remaining = [item for item in sessions if item.get("id") != session_id]
        self.data["sessions"] = remaining

        if self.data.get("current_session_id") == session_id:
            remaining.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
            self.data["current_session_id"] = remaining[0]["id"]

        self.save()
        return self.get_current_session()
