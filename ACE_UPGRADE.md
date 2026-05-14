# ACE Upgrade

本文档说明当前项目中的 ACE（Agentic Context Engineering）自进化升级方案。当前实现将原先的统一反思入口拆分为两个显式智能体：

- [`agents/critic_agent.py`](agents/critic_agent.py)：Critic 错误诊断智能体，负责错误类型识别、原因分析、修复策略和经验候选生成。
- [`agents/evolution_agent.py`](agents/evolution_agent.py)：经验演化进化智能体，负责把诊断结果和用户反馈沉淀为经验。
- [`core/critic.py`](core/critic.py)：结构化诊断规则引擎。
- [`core/evolution.py`](core/evolution.py)：经验演化写库管理器。
- [`core/experience_library.py`](core/experience_library.py)：负责经验检索、去重、置信度更新和 prompt 注入过滤。
- [`core/experience_bank_manager.py`](core/experience_bank_manager.py)：负责多经验库创建、切换、重命名和删除。
- [`core/ace_core.py`](core/ace_core.py)：ACE 核心协调模块，组装上下文、经验库与 Agent 流程。
- [`core/context_manager.py`](core/context_manager.py)：会话上下文与 ACE 面板管理。

因此，论文中的角色应直接写为 `CriticAgent` 和 `EvolutionAgent`，即“错误诊断智能体”和“经验演化进化智能体”。

## 闭环流程

1. `CoordinatorAgent` 识别任务意图，组织上下文、图层信息和相关经验。
2. `SpatialAnalystAgent` 调用 GIS 工具，或触发 `CodeAgent` 执行受控空间代码。
3. 当工具报错、代码执行失败、结果为空或用户直接纠正时，`CriticAgent` 启动错误诊断。
4. `core/critic.py` 输出结构化诊断，包括错误类型、原因、修复策略、代码提示和经验候选。
5. `EvolutionAgent` 调用 `core/evolution.py` 将诊断转成经验条目。
6. `ExperienceLibrary` 对经验进行去重、质量更新和置信度控制。
7. 后续相似任务会检索高置信经验，并把经验注入执行上下文。

## 经验质量控制

经验库不是简单追加列表，而是带有质量控制的动态记忆：

- 使用 `confidence` 表示经验置信度。
- 维护 `success_count` 和 `fail_count`。
- 记录 `last_used_at`。
- 按任务类型检索相关经验。
- 相似经验会合并或更新，而不是无限重复追加。
- 低置信经验不会注入 prompt。
- 用户纠正类经验会保留更高初始可信度，便于会话内快速生效。

## 用户反馈演化

前端不再依赖“正确 / 不正确 / 纠正”按钮。用户可以直接在对话里输入：

```text
对
不对
不对，应该高亮行政区 shp，不是餐饮点
以后统计类结果只高亮行政区面图层
```

系统会尝试识别这些输入，并完成三类动作：

1. 写入经验库，作为后续任务的可复用经验。
2. 写入当前会话上下文，作为短期偏好。
3. 必要时把纠正后的内容继续作为新任务执行。

## 当前新增能力

- 多经验库管理：创建、切换、复制当前经验库、从默认经验库初始化。
- 会话级偏好记忆：例如“统计类任务只高亮行政区面图层”。
- JSONL 可追踪日志：任务、代码执行、经验演化和错误均可回放。
- 实验侧已将 Exp2 定义为 Online Adaptation，Exp3 增加 Reflector、append-only memory 与 monolithic rewrite 等机制消融组，Exp4 使用 GeoAI 连续任务追踪 context collapse、refinement event、经验条目数、重复率、延迟和 token 成本。

## 风险与后续方向

当前实现已经具备闭环雏形，但仍有可继续增强的方向：

- 对经验冲突做显式检测，例如同一任务类型下存在互斥策略。
- 增加经验版本、回滚和审核机制。
- 为经验命中和实际任务成功建立更严格的因果关联指标。
- 修复代码中部分中文字符串的编码错乱问题，避免影响用户反馈识别。
