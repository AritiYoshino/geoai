import json
import os
import re
from datetime import datetime


class ExperienceBankManager:
    """Manages multiple selectable experience-library JSON files."""

    def __init__(self, index_path=os.path.join("data", "experience_banks.json")):
        self.index_path = index_path
        self.base_dir = os.path.join("data", "experience_libraries")
        self.legacy_default_path = os.path.join("data", "ace_experience_library.json")
        self.data = {"active_id": "default", "banks": []}
        self.load()

    def load(self):
        os.makedirs(self.base_dir, exist_ok=True)
        if os.path.exists(self.index_path):
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

        if not self.data.get("banks"):
            self.data = {
                "active_id": "default",
                "banks": [
                    {
                        "id": "default",
                        "name": "默认经验库",
                        "path": self.legacy_default_path,
                        "read_only": True,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                ],
            }
            self.save()
            return

        changed = False
        for bank in self.data.get("banks", []):
            if bank.get("id") == "default" and bank.get("read_only") is not True:
                bank["read_only"] = True
                changed = True
        if changed:
            self.save()

    def save(self):
        directory = os.path.dirname(self.index_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def list_banks(self):
        return [self._decorate(bank) for bank in self.data.get("banks", [])]

    def active_bank(self):
        active_id = self.data.get("active_id")
        for bank in self.data.get("banks", []):
            if bank.get("id") == active_id:
                return self._decorate(bank)
        bank = self.data["banks"][0]
        self.data["active_id"] = bank["id"]
        self.save()
        return self._decorate(bank)

    def active_path(self):
        active_id = self.data.get("active_id")
        for bank in self.data.get("banks", []):
            if bank.get("id") == active_id:
                return bank["path"]
        return self.data["banks"][0]["path"]

    def switch(self, bank_id):
        for bank in self.data.get("banks", []):
            if bank.get("id") == bank_id:
                self.data["active_id"] = bank_id
                self.save()
                return self._decorate(bank)
        raise ValueError(f"未找到经验库: {bank_id}")

    def create_bank(self, name, template="empty", source_experiences=None):
        safe_name = self._safe_name(name)
        bank_id = f"{safe_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        path = os.path.join(self.base_dir, f"{bank_id}.json")
        experiences = source_experiences if source_experiences is not None else []
        with open(path, "w", encoding="utf-8") as f:
            json.dump(experiences, f, ensure_ascii=False, indent=2)

        bank = {
            "id": bank_id,
            "name": name,
            "path": path,
            "template": template,
            "read_only": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.data.setdefault("banks", []).append(bank)
        self.data["active_id"] = bank_id
        self.save()
        return self._decorate(bank)

    def rename_bank(self, bank_id, name):
        bank = self._get_bank(bank_id)
        if bank is None:
            raise ValueError(f"未找到经验库: {bank_id}")
        if self._is_read_only(bank):
            raise ValueError("默认经验库不允许重命名")
        name = (name or "").strip()
        if not name:
            raise ValueError("经验库名称不能为空")
        bank["name"] = name[:60]
        self.save()
        return self._decorate(bank)

    def delete_bank(self, bank_id):
        bank = self._get_bank(bank_id)
        if bank is None:
            raise ValueError(f"未找到经验库: {bank_id}")
        if self._is_read_only(bank):
            raise ValueError("默认经验库不允许删除")

        self.data["banks"] = [item for item in self.data.get("banks", []) if item.get("id") != bank_id]
        if self.data.get("active_id") == bank_id:
            self.data["active_id"] = "default"
        self.save()

        path = bank.get("path", "")
        if path and os.path.exists(path):
            abs_path = os.path.abspath(path)
            abs_base = os.path.abspath(self.base_dir)
            if abs_path.startswith(abs_base):
                os.remove(abs_path)

        return self.active_bank()

    def _get_bank(self, bank_id):
        for bank in self.data.get("banks", []):
            if bank.get("id") == bank_id:
                return bank
        return None

    def _decorate(self, bank):
        return dict(bank, read_only=self._is_read_only(bank))

    def _is_read_only(self, bank):
        return bank.get("id") == "default" or bank.get("read_only", False)

    def _safe_name(self, name):
        cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", name.strip())
        return cleaned[:32] or "experience_bank"
