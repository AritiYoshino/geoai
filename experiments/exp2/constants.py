from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = PROJECT_ROOT / "data" / "experiments" / "exp2_workbook.json"
REFERENCE_PATH = PROJECT_ROOT / "data" / "experiments" / "exp2_reference_answers.json"


AGENT_DESCRIPTIONS = {
    "base_agent": {
        "name": "BASE Agent (无记忆基线)",
        "meaning": "复用主系统 GIS 工具和受控代码执行能力，但**无经验检索、无经验沉淀、无上下文记忆**，每次任务独立执行，用于衡量无 ACE / 无 RAG 的基础表现。",
    },
    "rag_agent": {
        "name": "RAG Agent (静态经验检索)",
        "meaning": "拥有**预置静态经验库**（覆盖 6 类已知 GIS 错误模式），可检索但**无法沉淀新经验**，用于衡量静态检索相对 BASE 的收益以及相对 ACE 连续学习的不足。",
    },
    "ace_agent": {
        "name": "ACE Agent (连续学习)",
        "meaning": "完整启用任务执行、Critic 诊断、Evolution 经验沉淀、经验库检索和上下文记忆，形成连续学习闭环，用于衡量动态经验积累与自适应能力。",
    },
}


AGENT_ORDER = ["base_agent", "rag_agent", "ace_agent"]


AGENT_CAPABILITIES = {
    "base_agent": {"retrieval": False, "evolution": False, "memory": False, "code": True},
    "rag_agent": {"retrieval": True, "evolution": False, "memory": False, "code": True},
    "ace_agent": {"retrieval": True, "evolution": True, "memory": True, "code": True},
}


SEED_EXPERIENCES = [
    {"id": "seed-layer-schema", "category": "schema", "strategy": "查询前优先读取图层字段，避免把自然语言类别误当作真实字段。"},
    {"id": "seed-basic-export", "category": "export", "strategy": "导出结果时同时保留结果表摘要和地图图层引用。"},
]


# ── RAG Agent 静态知识库 ────────────────────────────────────────────
# 覆盖 6 类已知 GIS 错误模式，用于模拟"预置经验库的 RAG 系统"
RAG_STATIC_EXPERIENCES = [
    {"id": "exp2-crs-distance", "category": "crs", "strategy": "距离、缓冲、热点网格和聚类前先确认 CRS，并统一到米制投影。"},
    {"id": "exp2-schema-check", "category": "schema", "strategy": "属性查询和分组统计前先读取 schema，字段缺失时寻找语义等价字段。"},
    {"id": "exp2-geometry-predicate", "category": "geometry", "strategy": "空间连接前确认点、线、面几何类型，并选择 within/intersects 等合适谓词。"},
    {"id": "exp2-empty-result-relax", "category": "empty_result", "strategy": "空结果时按专名、类别词、核心关键词逐级放宽检索条件。"},
    {"id": "exp2-density-area", "category": "code", "strategy": "密度计算必须使用投影后面积，并输出 count、area_km2 和 density 字段。"},
    {"id": "exp2-dbscan-params", "category": "clustering", "strategy": "DBSCAN 前将点投影到米制坐标，并记录 eps、min_samples 和噪声点比例。"},
]


# ── 所有经验模板（ACE 通过学习生成的完整经验集） ─────────────────
# RAG_STATIC_EXPERIENCES 是它的子集 — 前者不包含 B5-B6 的新模式
EXPERIENCE_TEMPLATES = {
    # ── 基础 6 类（也存在于 RAG 静态库） ──
    "crs_distance": {"id": "exp2-crs-distance", "category": "crs", "strategy": "距离、缓冲、热点网格和聚类前先确认 CRS，并统一到米制投影。"},
    "field_name_mismatch": {"id": "exp2-schema-check", "category": "schema", "strategy": "属性查询和分组统计前先读取 schema，字段缺失时寻找语义等价字段。"},
    "geometry_type": {"id": "exp2-geometry-predicate", "category": "geometry", "strategy": "空间连接前确认点、线、面几何类型，并选择 within/intersects 等合适谓词。"},
    "empty_result": {"id": "exp2-empty-result-relax", "category": "empty_result", "strategy": "空结果时按专名、类别词、核心关键词逐级放宽检索条件。"},
    "density_area": {"id": "exp2-density-area", "category": "code", "strategy": "密度计算必须使用投影后面积，并输出 count、area_km2 和 density 字段。"},
    "parameter_selection": {"id": "exp2-dbscan-params", "category": "clustering", "strategy": "DBSCAN 前将点投影到米制坐标，并记录 eps、min_samples 和噪声点比例。"},
    # ── 新增 4 类（RAG 静态库中不存在，仅 ACE 可学习） ──
    "temporal_query": {"id": "exp2-temporal-query", "category": "temporal", "strategy": "时间字段查询前先确认字段类型和格式，必要时做日期解析和范围过滤。"},
    "multi_criteria_rank": {"id": "exp2-multi-criteria", "category": "ranking", "strategy": "多条件综合排名时先归一化各指标权重，再计算综合得分排序。"},
    "cross_layer_validation": {"id": "exp2-cross-validation", "category": "validation", "strategy": "跨图层空间一致性校验时，确认几何类型匹配并检查属性字段可连接性。"},
    "adaptive_buffer": {"id": "exp2-adaptive-buffer", "category": "buffer", "strategy": "动态缓冲半径按要素类别分级设定，并在输出中注明各级缓冲距."},
}
