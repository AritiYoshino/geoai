import json
import os
from datetime import datetime


class JsonlLogger:
    """Very small JSONL logger used for experiment traceability."""

    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir

    def write(self, filename, payload):
        os.makedirs(self.log_dir, exist_ok=True)
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            **dict(payload or {}),
        }
        path = os.path.join(self.log_dir, filename)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


LOGGER = JsonlLogger()


def log_task(payload):
    LOGGER.write("task_log.jsonl", payload)


def log_code(payload):
    LOGGER.write("code_log.jsonl", payload)


def log_evolution(payload):
    LOGGER.write("evolution_log.jsonl", payload)


def log_error(payload):
    LOGGER.write("error_log.jsonl", payload)
