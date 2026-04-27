# ACE 多智能体地理分析原型升级说明

本项目已按任务书要求，从基础 GIS AI 助手升级为基于 ACE（Agentic Context Engineering）的多智能体协同原型。

## 目录结构

```text
geoai/
  agents/
    coordinator_agent.py       # 协调者智能体：意图理解、计划生成、任务调度
    spatial_analyst_agent.py   # 空间分析智能体：调用 GIS 工具或生成分析回答
    reflector_agent.py         # 反思者智能体：质量评估、错误诊断、闭环优化

  core/
    ace_core.py                # ACE 基础能力：任务分类、轨迹记录、诊断与演化
    context_manager.py         # 上下文管理：会话 POI、schema、prompt context、trace
    experience_bank_manager.py # 多经验库管理：新建、切换、记录当前选用库
    experience_library.py      # 动态经验库接口：经验存储、检索、更新
    session_store.py           # 会话持久化：历史消息、当前会话、长期 POI 记忆

  data/
    ace_experience_library.json # 动态经验库数据，运行时会更新
    experience_banks.json      # 经验库索引，记录当前选用的经验库
    experience_libraries/      # 用户新建的经验库文件
    sessions.json              # 会话历史和上下文记忆，运行时会更新

  tools/                       # GIS 工具：搜索、属性查询、邻近分析
    code_executor.py           # 受控空间代码执行：工具不足时执行 GeoPandas/Pandas 代码
  ai_handler.py                # GUI 面向的装配入口，负责组装多智能体系统
  gui.py                       # Tkinter 交互界面
  map_handler.py               # 地图加载、绘制和高亮
```

## 多智能体协同逻辑

1. 协调者智能体读取用户输入，识别任务类型，例如 `search`、`query`、`nearby`。
2. 协调者向 `ContextManager` 请求会话上下文，例如上一轮命中的酒店 POI。
3. `ContextManager` 通过 `SessionStore` 读取当前会话的历史记忆，支持下次运行继续使用。
4. 协调者检索 `ExperienceLibrary`，生成带经验约束的执行计划。
5. 空间分析智能体根据计划调用 GIS 工具，如 `search_poi`、`find_nearby_point_filtered`。
6. 如果固定工具无法覆盖任务，空间分析智能体可调用 `execute_spatial_code` 生成并执行受控 GeoPandas/Pandas 代码。
7. 工具反馈或代码 traceback 交给反思者智能体，由其识别字段错误、CRS 风险、结果为空、结果过大等问题。
8. 用户可通过“👍 正确 / 👎 不正确 / ✍ 纠正”评价结果，反思者会把反馈转成经验。
9. 反思者通过 `EvolutionManager` 将诊断或用户反馈沉淀为可复用经验，更新当前选用的经验库。
10. 协调者继续调度下一轮，直到得到最终回答或达到最大协同轮次。

## 空间代码生成

当固定工具无法完成任务时，系统可使用 `tools/code_executor.py` 中的 `execute_spatial_code`：

- 可访问 `layers`、`layer_names`、`pd`、`gpd`、`np`、`Point`、`reproject_to_meters`。
- 代码必须把最终结果赋值给 `RESULT`。
- 可选 `HIGHLIGHTS=[("图层名", 要素索引), ...]` 用于地图高亮。
- 禁止 `import`、文件读写、系统命令、`eval/exec/open` 等危险操作。
- 代码错误会以 traceback 返回给反思者，用于经验沉淀。

该功能可用于论文中的 Spatial Code Generation 实验，例如“批量统计每个酒店 300 米内餐饮数量并排序”。

## 多经验库对比

GUI 的“经验库”页签支持：

- 选择已有经验库。
- 新建空白经验库，用于 Zero-shot / 无经验条件对比。
- 用默认模板新建经验库，用于基础 ACE 条件对比。
- 复制当前经验库，用于保留某一阶段经验后继续演化。

当前选用的经验库记录在 `data/experience_banks.json`，用户新建的经验库保存在 `data/experience_libraries/`。

## 上下文管理

`core/context_manager.py` 独立负责：

- 保存最近 POI 命中结果。
- 按会话加载和保存历史消息、最近 POI 和 ACE 轨迹。
- 将“春熙路店”“这个酒店”“上面那个”等省略表达解析为可用的 `layer/index` 候选。
- 汇总图层 schema，防止智能体猜字段。
- 生成注入空间分析智能体的上下文提示。
- 保存 ACE 轨迹，供 GUI 的“ACE 轨迹”页签展示。
- 保存用户反馈，支持用户参与式自进化。

## 对任务书的对应关系

- 动态经验库接口：`core/experience_library.py`
- 动态经验库数据：`data/ace_experience_library.json`
- 多经验库实验：`core/experience_bank_manager.py`、`data/experience_banks.json`、`data/experience_libraries/`
- 会话历史记忆：`data/sessions.json`
- 用户反馈驱动进化：GUI 中的“👍 正确 / 👎 不正确 / ✍ 纠正”按钮
- 协调者智能体：`agents/coordinator_agent.py`
- 空间分析/执行智能体：`agents/spatial_analyst_agent.py`
- 评价与诊断/反思者智能体：`agents/reflector_agent.py`
- 上下文工程与会话记忆：`core/context_manager.py`
- 交互式原型展示：`gui.py` 中的“对话 / ACE 轨迹 / 经验库”页签

## 运行方式

确保 `.env` 中存在：

```text
DEEPSEEK_API_KEY=你的密钥
```

然后运行：

```bash
python main.py
```
