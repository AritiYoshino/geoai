# GeoAI ACE WebGIS

GeoAI ACE WebGIS 是一个面向地理空间问答与空间分析的多 Agent WebGIS 原型系统。项目以 ACE（Agentic Context Engineering）机制为核心，把自然语言任务、GIS 工具调用、受控空间代码执行、错误诊断、经验沉淀和 WebGIS 可视化组织成一个可执行、可追踪、可演化的闭环。

当前系统支持 POI 检索、属性查询、邻近分析、缓冲区分析、叠加分析、空间连接、聚类分析、热点分析、统计汇总、结果导出、地图高亮、会话管理、经验库管理，以及四组 ACE 对比实验。

## 当前状态

- 后端入口：`python main.py`
- 默认访问：`http://127.0.0.1:8000`
- 端口占用时自动尝试 `8001` 到 `8010`
- 首页：`/`
- 地理智能系统：`/gis`
- 对比实验系统：`/experiment`
- 默认 GeoJSON 数据目录：`data/geodata/`

## 项目结构

```text
geoai/
├── agents/                 # 多 Agent 协同层
│   ├── __init__.py
│   ├── coordinator_agent.py
│   ├── spatial_analyst_agent.py
│   ├── code_agent.py
│   ├── critic_agent.py
│   └── evolution_agent.py
├── core/                   # ACE、上下文、经验库、诊断、日志
│   ├── __init__.py
│   ├── ace_core.py
│   ├── context_manager.py
│   ├── experience_library.py
│   ├── experience_bank_manager.py
│   ├── critic.py
│   ├── evolution.py
│   ├── session_store.py
│   └── jsonl_logger.py
├── tools/                  # GIS 工具集合
│   ├── __init__.py
│   ├── advanced_common.py
│   ├── buffer_tool.py
│   ├── clustering_tool.py
│   ├── code_executor.py
│   ├── detail.py
│   ├── export_tool.py
│   ├── nearby.py
│   ├── overlay_tool.py
│   ├── proximity_tool.py
│   ├── query.py
│   ├── search.py
│   ├── statistics_tool.py
│   └── utils_geo.py
├── web_app/                # HTTP 服务与前端静态页面
│   ├── __init__.py
│   ├── server.py
│   ├── web_map_handler.py
│   └── static/
│       ├── index.html
│       ├── gis.html
│       ├── experiment.html
│       ├── app.js
│       ├── experiment.js
│       ├── styles.css
│       ├── experiment.css
│       └── js/
│           ├── gis/
│           │   ├── api.js
│           │   ├── layers.js
│           │   ├── map_view.js
│           │   └── panels.js
│           └── experiment/
│               ├── chart_setup.js
│               ├── logic.js
│               ├── main.js
│               └── state.js
├── experiments/            # 对比实验后端模块
│   ├── __init__.py
│   ├── runner.py
│   ├── baselines.py
│   ├── config.py
│   ├── metrics.py
│   ├── exp1/
│   ├── exp2/
│   ├── exp3/
│   └── exp4/
├── data/
│   ├── geodata/            # GeoJSON 空间数据
│   ├── experience_libraries/ # 用户创建的经验库
│   ├── exports/            # 导出文件
│   ├── ace_experience_library.json
│   ├── experience_banks.json
│   └── sessions.json
├── logs/                   # JSONL 运行日志
├── plans/                  # 方案、分析和论文草稿
├── .env.example
├── ai_handler.py
├── main.py
├── requirements.txt
├── utils.py
├── README.md
├── SYSTEM_ARCHITECTURE.md
├── ACE_UPGRADE.md
```

## 核心流程

1. 用户在前端输入自然语言地理分析任务。
2. `AIHandler` 组织 LLM、上下文、经验库、工具和 Agent。
3. `CoordinatorAgent` 识别任务类型，检索会话上下文和经验库，生成执行计划。
4. `SpatialAnalystAgent` 选择固定 GIS 工具，或触发 `CodeAgent` 执行受控 GeoPandas 代码。
5. `CriticAgent` 在错误、空结果或用户纠正时进行结构化诊断，`EvolutionAgent` 将诊断沉淀为经验。
6. 前端展示自然语言回答、Trace、ACE 面板、经验库摘要和地图高亮结果。

## GIS 工具能力

当前 [`tools/__init__.py`](tools/__init__.py) 的 `create_tools()` 注册的工具包括：

| 工具 | 实现文件 | 说明 |
|---|---|---|
| `search_poi` | [`tools/search.py`](tools/search.py) | 跨图层 POI 检索 |
| `query_poi_by_conditions` | [`tools/query.py`](tools/query.py) | 按属性条件查询 POI |
| `get_poi_by_index` | [`tools/detail.py`](tools/detail.py) | 按索引查看 POI 详情 |
| `find_nearby` | [`tools/nearby.py`](tools/nearby.py) | 图层间邻近分析 |
| `find_nearby_point` | [`tools/nearby.py`](tools/nearby.py) | 以单个点为中心的邻近分析 |
| `find_nearby_point_filtered` | [`tools/nearby.py`](tools/nearby.py) | 带关键词过滤的邻近分析 |
| `buffer_analysis` | [`tools/buffer_tool.py`](tools/buffer_tool.py) | 缓冲区分析 |
| `overlay_layers` | [`tools/overlay_tool.py`](tools/overlay_tool.py) | 图层叠加分析 |
| `spatial_join` | [`tools/overlay_tool.py`](tools/overlay_tool.py) | 空间连接 |
| `nearest_neighbor` | [`tools/proximity_tool.py`](tools/proximity_tool.py) | 最近邻分析 |
| `dbscan` | [`tools/clustering_tool.py`](tools/clustering_tool.py) | DBSCAN 聚类 |
| `hotspot` | [`tools/clustering_tool.py`](tools/clustering_tool.py) | 热点分析 |
| `statistics` | [`tools/statistics_tool.py`](tools/statistics_tool.py) | 图层统计汇总 |
| `export` | [`tools/export_tool.py`](tools/export_tool.py) | 分析结果导出 |
| `execute_spatial_code` | [`tools/code_executor.py`](tools/code_executor.py) | 受控空间代码执行 |

## Web API

### 页面

- `GET /`：统一入口首页
- `GET /gis`：地理智能系统
- `GET /experiment`：对比实验系统
- `GET /static/*`：静态资源

### 地图与问答

- `GET /api/layers`：图层元信息
- `GET /api/layer_data?layer_name=...&bbox=minx,miny,maxx,maxy&zoom=...`：按视野加载 GeoJSON
- `GET /api/highlights`：当前地图高亮结果
- `POST /api/highlights/clear`：清空高亮
- `POST /api/chat`：发送自然语言任务
- `POST /api/feedback`：兼容旧版按钮式反馈
- `GET /api/trace`：最新 Trace
- `GET /api/ace-panel`：ACE 面板

### 会话与经验库

- `GET /api/sessions`
- `POST /api/sessions/new`
- `POST /api/sessions/switch`
- `POST /api/sessions/rename`
- `POST /api/sessions/delete`
- `GET /api/experience`
- `GET /api/experience-banks`
- `POST /api/experience-banks/switch`
- `POST /api/experience-banks/create`
- `POST /api/experience-banks/rename`
- `POST /api/experience-banks/delete`

### 实验系统

四组实验均支持任务集读取、历史结果、运行、重命名、删除和导出。统一入口为 `/experiment`，命令行入口为 `python -m experiments.runner --exp exp1`，也可以将 `exp1` 替换为 `exp2`、`exp3`、`exp4` 或 `all`。

| 实验 | 当前定位 | 主要配置 |
|---|---|---|
| `exp1` | GeoAI 主系统能力评测，对比 Base/RAG/ACE 在 GIS 工具调用、空间分析、记忆、经验检索、经验新增、代码执行和结果校验上的差异 | `data/experiments/exp1_workbook.json` + `data/experiments/exp1_reference_answers.json` |
| `exp2` | Online Adaptation 在线适应实验，三批连续任务验证静态经验、在线新经验写入和最终迁移效果 | `data/experiments/exp2_workbook.json` + `data/experiments/exp2_reference_answers.json` |
| `exp3` | ACE 机制消融实验，对比完整 ACE、移除单模块、无 Reflector 精炼、append-only memory 和 monolithic rewrite 等机制差异 | `data/experiments/exp3_workbook.json` + `data/experiments/exp3_reference_answers.json` |
| `exp4` | GeoAI Context Collapse 稳定性实验，100 步连续 online adaptation 中比较上下文增长、精炼、整体重写和 collapse 事件 | `data/experiments/exp4_workbook.json` + `data/experiments/exp4_evaluation_config.json` |


## 运行方式

### 1. 准备环境

```bash
pip install -r requirements.txt
```

在 `.env` 中配置：

```text
DEEPSEEK_API_KEY=你的密钥
```

### 2. 启动服务

```bash
python main.py
```

启动后访问：

```text
http://127.0.0.1:8000
```

### 3. VS Code 调试

项目提供 `.vscode/launch.json`，默认调试入口为 `main.py`。

## 日志与可追踪性

- `logs/task_log.jsonl`：用户任务、有效任务、回答摘要、任务类型
- `logs/code_log.jsonl`：代码执行、重试、错误摘要
- `logs/evolution_log.jsonl`：经验新增、更新和跳过记录
- `logs/error_log.jsonl`：运行异常

## 实验模块

项目新增 ACE 对比实验模块，用于验证 ACE-WebGIS 在空间分析任务中的优势。实验二采用 `BASE / RAG / ACE` 三组 online adaptation 对比：BASE 表示无记忆基线，RAG 表示静态经验检索，ACE 表示带 Critic、Evolution、经验检索和上下文记忆的在线适应闭环。实验入口为：

- 页面入口：`/experiment`
- 命令行入口：`python -m experiments.runner --exp exp1`
- API 入口：`GET /api/experiment/list`、`POST /api/experiment/run`、`GET /api/experiment/result/{experiment_id}`

四组实验包括：

| 实验 | 目标 | 任务集 |
|---|---|---|
| `exp1` | GeoAI 主系统能力评测 | `data/experiments/exp1_workbook.json` + `data/experiments/exp1_reference_answers.json` |
| `exp2` | Online Adaptation 在线适应实验：验证 ACE 在线经验更新相对静态 RAG 的收益 | `data/experiments/exp2_workbook.json` + `data/experiments/exp2_reference_answers.json` |
| `exp3` | ACE 机制消融：单模块移除、无 Reflector、append-only、整体重写 | `data/experiments/exp3_workbook.json` + `data/experiments/exp3_reference_answers.json` |
| `exp4` | GeoAI Context Collapse 稳定性：100 步连续 online adaptation | `data/experiments/exp4_workbook.json` + `data/experiments/exp4_evaluation_config.json` |

当前任务集通过 `repeat_multiplier`、`variants` 或 `total_steps` 模板扩容：Exp1 为 52 个任务，Exp2 为 3 个 batch / 90 个展开任务，Exp3 为 27 个消融任务，Exp4 为 100 个 adaptation step。

实验四已经对齐 GeoAI 场景，任务覆盖字段核对、CRS 距离、空结果恢复、GeoPandas 密度计算、边界谓词、时间字段、跨图层校验、导出元数据、上下文锚点和多指标排名。若某一步 `context_token_count` 从高位骤降到低位，同时 rolling accuracy 明显下降，则记为 context collapse；ACE 的正常 grow-and-refine 去重若准确率基本稳定，则记为 refinement event。

实验二中的三组对比含义：
- `BASE Agent`：复用 GIS 工具和受控代码执行能力，但不使用经验检索、经验写入和上下文记忆；用于衡量无 RAG / 无 ACE 的基线表现。
- `RAG Agent`：使用预置静态经验库进行检索，能解决已知错误模式，但不会把本轮失败诊断沉淀为新经验；用于衡量静态检索相对 BASE 的收益。
- `ACE Agent`：完整启用 Critic 诊断、Evolution 经验沉淀、经验库检索、上下文记忆和工具/代码执行；数据集后半段包含 RAG 静态库外的新模式，用于体现 online adaptation 相对静态 RAG 的优势。

实验一中的框架含义：

- `Direct LLM`：只让大模型直接回答或给出 GIS 操作建议，不调用工具，不读取或写入经验库。
- `ReAct Agent`：采用 Reason + Act 工具调用流程，可调用固定 GIS 工具，但不使用 ACE 经验库。
- `CodeAct Agent`：允许生成并执行受控 GeoPandas / Python 代码，可基于报错做有限自修复，但不使用 ACE 经验检索和演化。
- `ACE-WebGIS`：完整使用 CoordinatorAgent、SpatialAnalystAgent、CodeAgent、CriticAgent、EvolutionAgent、ContextManager 和 ExperienceLibrary，形成执行、诊断、经验沉淀与复用闭环。

命令行运行：

```bash
python -m experiments.runner --exp exp1
python -m experiments.runner --exp exp2
python -m experiments.runner --exp exp3
python -m experiments.runner --exp exp4
python -m experiments.runner --exp all
```

默认使用 mock / 规则化评估模式，保证没有真实 LLM 服务时也能完整生成实验结果。后端 API 可通过 `use_real_ace=true` 调用真实 ACE 流程。

实验输出位置：

- 每次运行：`logs/experiments/{run_id}/`
- Exp1 汇总：`logs/experiments/exp1_main_comparison.json`、`logs/experiments/exp1_main_comparison.csv`
- Exp2 汇总：`logs/experiments/exp2_continual_learning.json`、`logs/experiments/exp2_continual_learning.csv`
- Exp3 汇总：`logs/experiments/exp3_ablation.json`、`logs/experiments/exp3_ablation.csv`
- Exp4 汇总：`logs/experiments/exp4_context_stability.json`、`logs/experiments/exp4_context_stability.csv`

核心指标包括任务成功率、工具选择准确率、执行成功率、结果正确率、平均轮数、平均耗时、用户干预次数、错误数、重复错误率、修复成功率、经验复用率、知识保留率、冗余率、上下文 token 数、经验条目数、重复条目比例、经验命中率、适应延迟、token 成本估计和 collapse 事件数。

## 相关文档

- [`ACE_UPGRADE.md`](ACE_UPGRADE.md)：ACE 自进化机制说明
- [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)：系统架构与模块关系
- [`plans/project_analysis.md`](plans/project_analysis.md)：项目分析报告
- [`plans/ACE_EXPERIMENT_DESIGN.md`](plans/ACE_EXPERIMENT_DESIGN.md)：ACE 对比实验设计
- [`plans/thesis_initial_draft.md`](plans/thesis_initial_draft.md)：论文初稿
- [`plans/upgrade_landing_page.md`](plans/upgrade_landing_page.md)：统一入口首页升级记录
