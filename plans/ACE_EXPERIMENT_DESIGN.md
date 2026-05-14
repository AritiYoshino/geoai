# ACE-WebGIS 对比实验设计

## 1. 实验设计总览

本实验模块用于验证 ACE（Agentic Context Engineering）框架相较普通 Agent 在地理空间问答和空间分析任务中的优势。实验代码集中放在 `experiments/` 包中，采用统一任务接口、统一 trace 结构和规则化评估指标，支持 mock 模式稳定复现实验，也保留真实 ACE 流程调用入口。

命令行入口为 `python -m experiments.runner --exp exp1`，也可以将 `exp1` 替换为 `exp2`、`exp3`、`exp4` 或 `all`。

四组实验分别对应主系统能力、online adaptation、机制消融和 GeoAI context collapse 稳定性：

- Exp1：总体任务成功率对比
- Exp2：Online Adaptation 在线适应实验
- Exp3：ACE 机制消融实验
- Exp4：GeoAI Context Collapse 稳定性实验

## 2. 四组实验说明

### Exp1 总体任务成功率对比

比较 Direct LLM、ReAct Agent、CodeAct Agent 和 ACE-WebGIS 在多类型 GIS 任务上的表现。任务覆盖 POI 检索、属性查询、邻近分析、缓冲区、叠加、空间连接、聚类、热点、统计和导出。

主要输出：

- `logs/experiments/exp1_main_comparison.json`
- `logs/experiments/exp1_main_comparison.csv`

### Exp2 Online Adaptation 在线适应实验

将任务划分为 3 个 batch，共 90 个展开任务。Batch 1 验证 RAG/ACE 共享静态经验库相对 BASE 的优势；Batch 2 投放静态 RAG 库没有的新错误模式，观察 ACE 是否能通过在线反馈形成新经验；Batch 3 主要复测新增经验，验证 ACE 的在线适应收益是否能迁移到后续任务。

主要观察：

- 成功率是否随 batch 提升
- 重复错误率是否下降
- 经验复用率和修复成功率是否提高
- 静态 RAG 面对新增错误模式时是否停滞
- ACE 新增经验在最终迁移小测中的命中率

### Exp3 ACE 机制消融实验

在 27 个 GeoAI 中高难度任务上比较完整 ACE 与以下消融组。题干保持自然，模块需求由评测侧 `requires_modules` 和 `ablation_groups` 标注，不直接依赖题干泄漏。

- full_ace
- without_context_manager
- without_experience_retrieval
- without_code_agent
- without_critic
- without_evolution
- without_reflector_refinement
- append_only_memory
- monolithic_rewrite

任务集中包含 CRS 距离、字段名不一致、空结果恢复、图层歧义、上下文锚点、边界谓词、导出元数据、时间字段、跨图层校验、多指标排名和需要 GeoPandas 代码的任务。

### Exp4 GeoAI Context Collapse 稳定性实验

构造 100 步 GeoAI 连续 online adaptation 过程。每一步先用当前上下文完成任务，再基于工具结果、代码执行结果、验证报告或空结果信号更新上下文。任务覆盖字段核对、CRS 距离、空结果恢复、GeoPandas 密度计算、边界谓词、时间字段、跨图层校验、导出元数据、上下文锚点和多指标排名等 10 类能力。

比较六种上下文/记忆方式：

- base_no_adaptation：无上下文更新，作为无适应下限。
- rag_static_memory：使用静态经验检索，但不吸收在线反馈。
- monolithic_rewrite：周期性把长上下文重写为短摘要，观察是否遗忘早期技能。
- dynamic_cheatsheet：维护一个动态速查表，把近期任务规则压缩为短条目，观察容量受限时是否覆盖早期能力。
- append_only_memory：只追加新经验，不去重、不合并，观察冗余、延迟和成本增长。
- ace_grow_and_refine：增量写入、合并同类经验、去冗余并保留核心技能。

每个 adaptation step 记录 `step_accuracy`、`rolling_accuracy`、`context_token_count`、`context_item_count`、`helpful_item_count`、`harmful_item_count`、`duplicate_item_ratio`、`deleted_item_count`、`retrieved_experience_hit_rate`、`adaptation_latency_ms`、`token_cost_estimate` 和 `collapse_event_count`。若相邻 step 中上一轮 token 数处于高位，下一轮骤降到前一轮的 35% 以下，同时准确率下降至少 0.12，则判定为一次 context collapse。若 ACE 的 grow-and-refine 导致 token 温和下降，但 rolling accuracy 下降不超过 0.03 且重复率下降，则记为正常 refinement event。

## 3. Baseline 设置

Direct LLM：
仅生成自然语言回答或 GIS 操作建议，不调用工具、不读写经验库。

ReAct Agent：
使用 Reason + Act 工具调用流程，可以调用固定 GIS 工具，但不读取或写入 ACE 经验库。

CodeAct Agent：
允许生成并执行受控 GeoPandas / Python 代码，可基于报错自修复，但不读取 ACE 经验库。

ACE-WebGIS：
使用 CoordinatorAgent、SpatialAnalystAgent、CodeAgent、CriticAgent、EvolutionAgent、ContextManager 和 ExperienceLibrary 的完整闭环。

## 4. 指标定义

- task_success_rate：任务整体成功比例。
- tool_selection_accuracy：实际选择工具与预期工具的重合比例。
- execution_success_rate：无未处理异常且执行链完成的比例。
- result_correctness：按规则化检查估计结果是否满足预期。
- average_turns：平均推理 / 工具调用轮次。
- average_runtime：平均运行耗时。
- repeated_error_rate：同类错误重复出现比例。
- repair_success_rate：触发修复后的成功比例。
- experience_reuse_rate：任务执行时检索到经验的比例。
- knowledge_retention_rate：早期关键经验在后期仍被保留的比例。
- redundancy_rate：经验库中高相似经验对的比例。
- context_token_count：经验库上下文近似 token 数。
- context_item_count：上下文中的经验条目数。
- duplicate_item_ratio：高相似经验条目的重复比例。
- retrieved_experience_hit_rate：检索到的经验与当前任务需求匹配的比例。
- adaptation_latency_ms：单步上下文更新耗时。
- token_cost_estimate：上下文注入和更新的 token 成本估计。
- collapse_event_count：高位 context token 数骤降到低位且准确率同步下降的事件数。

没有人工标注时，实验采用规则化评估：检查是否生成地图图层、是否返回非空结果、是否调用预期工具、是否无未处理异常、回答是否非空以及是否包含必要统计字段。

## 5. 预期结论

Exp1 预期 ACE-WebGIS 在成功率、工具选择准确率和结果正确性上高于 Direct LLM、ReAct 和 CodeAct。

Exp2 预期 ACE-WebGIS 在 online adaptation 中随 batch 增加表现逐步改善，重复错误率下降，新增经验命中率和最终迁移表现高于静态 RAG。

Exp3 预期移除 CriticAgent、EvolutionAgent、经验检索、CodeAgent、ContextManager、Reflector refinement 或 grow-and-refine 都会导致成功率、修复率、经验质量、延迟或上下文稳定性下降。

Exp4 预期 ACE grow-and-refine 的上下文长度呈平稳增长或阶段性温和精简，准确率随经验积累提升或保持稳定，collapse 事件数低于整体重写和 Dynamic Cheatsheet；append-only memory 预期 token、重复率和延迟持续上升。

## 6. 可写入论文的实验假设

H1：
与 Direct LLM、ReAct Agent 和 CodeAct Agent 相比，ACE-WebGIS 在多类型空间分析任务上具有更高的任务成功率和结果正确率。

H2：
ACE-WebGIS 能够在 online adaptation 中通过执行反馈、错误诊断和经验沉淀实现持续改进，随着任务批次增加，成功率提高、重复错误率下降。

H3：
CriticAgent、EvolutionAgent、经验检索、CodeAgent、ContextManager、Reflector refinement 和 grow-and-refine 均对系统性能或稳定性有贡献，移除任一机制都会导致任务成功率、修复能力、经验质量或上下文稳定性下降。

H4：
相比整体重写或 Dynamic Cheatsheet，ACE 的增量式 grow-and-refine 机制能在连续在线学习中更稳定地控制上下文长度，降低 context collapse 和经验遗忘风险。
