import json
from pathlib import Path

from core.experience_library import DEFAULT_EXPERIENCES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = PROJECT_ROOT / "data" / "experiments" / "exp1_workbook.json"
REFERENCE_PATH = PROJECT_ROOT / "data" / "experiments" / "exp1_reference_answers.json"


AGENT_DESCRIPTIONS = {
    "base_agent": {
        "name": "Base Agent",
        "meaning": "复用主系统工具和代码执行接口，但不使用历史对话记忆、经验检索和经验写入，作为无上下文基线。",
    },
    "rag_agent": {
        "name": "RAG Agent",
        "meaning": "复用主系统工具和代码执行接口，并启用经验库检索；不把本轮诊断写回经验库，用于验证检索增强本身的收益。",
    },
    "ace_agent": {
        "name": "ACE Agent",
        "meaning": "完整复用主系统 ACE 链路：上下文记忆、经验检索、工具/代码执行、Critic 诊断和 Evolution 经验写入。",
    },
}


AGENT_CAPABILITIES = {
    "base_agent": {"memory": False, "rag": False, "evolution": False, "code": True, "base_quality": 0.66},
    "rag_agent": {"memory": False, "rag": True, "evolution": False, "code": True, "base_quality": 0.76},
    "ace_agent": {"memory": True, "rag": True, "evolution": True, "code": True, "base_quality": 0.86},
}


AGENT_ORDER = ["base_agent", "rag_agent", "ace_agent"]


def seed_experiences(agent_type):
    if agent_type == "base_agent":
        return []
    return json.loads(json.dumps(DEFAULT_EXPERIENCES, ensure_ascii=False))
