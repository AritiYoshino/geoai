from dataclasses import asdict, dataclass


@dataclass
class ExperimentConfig:
    use_critic: bool = True
    use_evolution: bool = True
    use_experience_retrieval: bool = True
    use_code_agent: bool = True
    use_context_manager: bool = True
    use_real_ace: bool = False
    mock_mode: bool = True

    def to_dict(self):
        return asdict(self)


BASELINE_DESCRIPTIONS = {
    "direct_llm": {
        "name": "Direct LLM",
        "meaning": "只让大模型直接回答或给出 GIS 操作建议，不调用工具，不读取或写入经验库，也不进行 ACE 诊断和演化。",
    },
    "react_agent": {
        "name": "ReAct Agent",
        "meaning": "采用 Reason + Act 的工具调用流程，可调用固定 GIS 工具，但不读取 ACE 经验库，也不把错误沉淀为经验。",
    },
    "codeact_agent": {
        "name": "CodeAct Agent",
        "meaning": "允许生成并执行受控 GeoPandas / Python 代码，可根据报错做有限自修复，但不使用 ACE 经验检索与演化机制。",
    },
    "ace_webgis": {
        "name": "ACE-WebGIS",
        "meaning": "完整使用 CoordinatorAgent、SpatialAnalystAgent、CodeAgent、CriticAgent、EvolutionAgent、ContextManager 和 ExperienceLibrary，形成任务执行、诊断、经验沉淀与复用闭环。",
    },
}


EXPERIMENTS = {
    "exp1": {
        "id": "exp1",
        "name": "总体任务成功率对比",
        "task_file": "data/experiments/exp1_workbook.json",
        "outputs": ["exp1_main_comparison.json", "exp1_main_comparison.csv"],
    },
    "exp2": {
        "id": "exp2",
        "name": "连续任务学习实验",
        "task_file": "data/experiments/exp2_workbook.json",
        "outputs": ["exp2_continual_learning.json", "exp2_continual_learning.csv"],
    },
    "exp3": {
        "id": "exp3",
        "name": "ACE 模块消融实验",
        "task_file": "data/experiments/exp3_workbook.json",
        "outputs": ["exp3_ablation.json", "exp3_ablation.csv"],
    },
    "exp4": {
        "id": "exp4",
        "name": "Context Collapse 稳定性实验",
        "task_file": "data/experiments/exp4_workbook.json",
        "outputs": ["exp4_context_stability.json", "exp4_context_stability.csv"],
    },
}
