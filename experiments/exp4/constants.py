from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = PROJECT_ROOT / "data" / "experiments" / "exp4_workbook.json"
EVALUATION_CONFIG_PATH = PROJECT_ROOT / "data" / "experiments" / "exp4_evaluation_config.json"


STRATEGIES = {
    "base_no_adaptation": {
        "name": "Base No Adaptation",
        "description": "不进行上下文更新，作为无在线适应能力的下限基线。",
    },
    "rag_static_memory": {
        "name": "RAG Static Memory",
        "description": "只使用静态经验检索，不吸收在线反馈，面对新模式时提升有限。",
    },
    "monolithic_rewrite": {
        "name": "Periodic Rewrite Baseline",
        "description": "周期性把长上下文压缩为很短摘要，容易在压缩点丢失早期技能并触发 context collapse。",
    },
    "dynamic_cheatsheet": {
        "name": "Dynamic Cheatsheet",
        "description": "维护一个动态速查表，持续把近期任务规则写成短条目；容量受限时会覆盖旧条目，容易丢失早期能力。",
    },
    "append_only_memory": {
        "name": "Append-only Memory",
        "description": "只追加经验，不做去重和合并；准确率可提升，但冗余、token 数和延迟会持续上涨。",
    },
    "ace_grow_and_refine": {
        "name": "ACE Grow-and-Refine",
        "description": "ACE 将任务反馈沉淀为结构化经验，并阶段性合并、去冗余和保留核心技能，使上下文平稳增长或温和精简。",
    },
}


COLLAPSE_TOKEN_HIGH_WATERMARK = 8000
COLLAPSE_TOKEN_DROP_RATIO = 0.35
COLLAPSE_ACCURACY_DROP = 0.12
