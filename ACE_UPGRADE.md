# ACE Upgrade

本项目保留 `ReflectorAgent` 作为统一入口，并在其内部接入：

- `CriticAgent`：负责结构化错误诊断
- `EvolutionManager`：负责经验抽取、去重、质量更新与写库

因此论文和文档中的角色对应关系为：

- `ReflectorAgent = Critic Agent + Evolution Manager` 的轻量实现

## 闭环流程

1. `CoordinatorAgent` 识别任务意图并组织上下文。
2. `SpatialAnalystAgent` 调用 GIS 工具或受控代码执行。
3. 若工具报错、结果为空或代码失败，`ReflectorAgent` 调用 `core/critic.py` 输出结构化诊断。
4. `ReflectorAgent` 再调用 `core/evolution.py` 将诊断沉淀为经验，并更新经验库。
5. 高置信经验会在后续任务中重新注入 prompt，形成 ACE 自进化闭环。

## 经验质量控制

经验库不再只是“新增”，还支持：

- 相似经验去重
- `confidence` 置信度
- `success_count / fail_count`
- `last_used_at`
- 按任务类型检索
- 低置信经验不注入 prompt

## 用户反馈演化

前端不再依赖“正确 / 不正确 / 纠正”按钮。

用户可以直接在会话里说：

- `对`
- `不对`
- `不对，应该高亮行政区 shp，不是餐馆点`

系统会将这类反馈写入经验库，并在需要时同步更新会话偏好。

## 新增可追溯日志

项目新增以下 JSONL 日志：

- `logs/task_log.jsonl`
- `logs/code_log.jsonl`
- `logs/evolution_log.jsonl`
- `logs/error_log.jsonl`

可用于实验复现、错误回放与论文附录说明。
