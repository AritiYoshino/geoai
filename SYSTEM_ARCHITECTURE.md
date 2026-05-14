# System Architecture

GeoAI ACE WebGIS 由 Web 前端、HTTP 服务、多 Agent 协同层、ACE 核心层、GIS 工具层、实验系统和数据日志层组成。

## 总体分层

```text
用户
 ↓
Web 前端：index.html / gis.html / experiment.html
 ↓
HTTP 服务：web_app/server.py
 ↓
AIHandler：LLM、上下文、经验库、Agent、工具装配
 ↓
多 Agent 协同：Coordinator / SpatialAnalyst / CodeAgent / CriticAgent / EvolutionAgent
 ↓
ACE 核心：ContextManager / ExperienceLibrary / CriticAgent / EvolutionAgent / SessionStore / Logger
 ↓
GIS 工具：查询、邻近、缓冲区、叠加、空间连接、聚类、热点、统计、导出、受控代码执行
 ↓
数据与日志：GeoJSON、Shapefile、经验库、会话、JSONL 日志、实验输出
```

## 关键模块

### `web_app/`

- [`server.py`](web_app/server.py)：基于 `http.server` 的线程化 HTTP 服务，负责页面路由、API 分发、实验运行和导出。
- [`web_map_handler.py`](web_app/web_map_handler.py)：读取图层元信息，按 `bbox + zoom` 返回视野内 GeoJSON，并维护地图高亮。
- `static/` 静态资源：
  - [`index.html`](web_app/static/index.html)：统一入口首页。
  - [`gis.html`](web_app/static/gis.html)：地理智能系统页面。
  - [`experiment.html`](web_app/static/experiment.html)：对比实验系统页面。
  - [`app.js`](web_app/static/app.js)：地图、聊天、ACE 面板、会话、经验库和图层联动逻辑。
  - [`experiment.js`](web_app/static/experiment.js)：实验运行、结果管理、图表展示和导出逻辑。
  - [`styles.css`](web_app/static/styles.css)、[`experiment.css`](web_app/static/experiment.css)：样式文件。
  - `js/gis/`：GIS 页面拆分模块
    - [`api.js`](web_app/static/js/gis/api.js)：地图 API 请求封装
    - [`layers.js`](web_app/static/js/gis/layers.js)：图层面板管理
    - [`map_view.js`](web_app/static/js/gis/map_view.js)：地图容器初始化与交互
    - [`panels.js`](web_app/static/js/gis/panels.js)：ACE 面板、Trace 面板、会话面板

### `ai_handler.py`

应用级装配入口，负责：

- 读取并清理运行环境。
- 初始化 `ChatDeepSeek`。
- 初始化经验库、上下文、工具和各 Agent。
- 处理用户消息、反馈和偏好记忆。
- 提供会话、经验库、Trace 和 ACE 面板接口。

### `agents/`

- `CoordinatorAgent`：任务分类、上下文组织、经验检索、执行计划和多轮调度。
- `SpatialAnalystAgent`：根据任务调用 GIS 工具，或触发空间代码执行。
- `CodeAgent`：生成、执行和修复受控 GeoPandas/Pandas 代码。
- `CriticAgent`：错误诊断智能体，识别字段、CRS、空结果、几何和执行错误。
- `EvolutionAgent`：经验演化进化智能体，将诊断和用户反馈写入经验库。

### `core/`

- [`ace_core.py`](core/ace_core.py)：ACE 核心协调，组装上下文、经验库、Agent 流程。
- [`context_manager.py`](core/context_manager.py)：会话上下文、最近 POI、用户偏好、ACE 面板和 Trace。
- [`experience_library.py`](core/experience_library.py)：经验加载、检索、去重、置信度更新。
- [`experience_bank_manager.py`](core/experience_bank_manager.py)：多经验库管理。
- [`critic.py`](core/critic.py)：结构化错误诊断。
- [`evolution.py`](core/evolution.py)：错误和反馈到经验条目的转换。
- [`session_store.py`](core/session_store.py)：会话持久化。
- [`jsonl_logger.py`](core/jsonl_logger.py)：任务、代码、经验和错误日志。

### `tools/`

工具由 [`tools/__init__.py`](tools/__init__.py) 的 `create_tools(handler)` 统一注册，当前包含 15 个工具，对应实现文件如下：

| 工具 | 实现文件 |
|---|---|
| `search_poi` | [`tools/search.py`](tools/search.py) |
| `query_poi_by_conditions` | [`tools/query.py`](tools/query.py) |
| `get_poi_by_index` | [`tools/detail.py`](tools/detail.py) |
| `find_nearby` | [`tools/nearby.py`](tools/nearby.py) |
| `find_nearby_point` | [`tools/nearby.py`](tools/nearby.py) |
| `find_nearby_point_filtered` | [`tools/nearby.py`](tools/nearby.py) |
| `buffer_analysis` | [`tools/buffer_tool.py`](tools/buffer_tool.py) |
| `overlay_layers` | [`tools/overlay_tool.py`](tools/overlay_tool.py) |
| `spatial_join` | [`tools/overlay_tool.py`](tools/overlay_tool.py) |
| `nearest_neighbor` | [`tools/proximity_tool.py`](tools/proximity_tool.py) |
| `dbscan` | [`tools/clustering_tool.py`](tools/clustering_tool.py) |
| `hotspot` | [`tools/clustering_tool.py`](tools/clustering_tool.py) |
| `statistics` | [`tools/statistics_tool.py`](tools/statistics_tool.py) |
| `export` | [`tools/export_tool.py`](tools/export_tool.py) |
| `execute_spatial_code` | [`tools/code_executor.py`](tools/code_executor.py) |

其他辅助工具模块：

| 文件 | 作用 |
|---|---|
| [`tools/advanced_common.py`](tools/advanced_common.py) | 高级空间分析通用工具函数 |
| [`tools/utils_geo.py`](tools/utils_geo.py) | 地理空间工具函数集 |

### `experiments/`

- `runner.py`：统一实验入口，支持 `exp1`、`exp2`、`exp3`、`exp4` 和 `all`。
- `config.py`：四组实验的 workbook、reference/config 和输出文件配置。
- `baselines.py`、`metrics.py`：实验基线和通用指标计算。
- `exp1/`：GeoAI 主系统能力评测。
- `exp2/`：Online Adaptation 在线适应实验。
- `exp3/`：ACE 机制消融实验。
- `exp4/`：GeoAI Context Collapse 稳定性实验。

## 主系统调用链

1. 前端通过 `POST /api/chat` 发送用户任务。
2. `WebGISRequestHandler._handle_chat()` 调用 `AIHandler.process_message()`。
3. `AIHandler` 处理内联反馈和偏好记忆，并写入上下文。
4. `CoordinatorAgent` 识别任务类型并组织执行计划。
5. `SpatialAnalystAgent` 调用一个或多个 GIS 工具。
6. 复杂任务可触发 `CodeAgent` 执行受控空间代码。
7. 异常、空结果或用户纠正会进入 `CriticAgent` 进行诊断。
8. `EvolutionAgent` 根据诊断结果生成经验，经验库更新。
9. 后端返回回答、Trace、ACE 面板、经验摘要、会话状态和地图高亮。

## 地图数据链路

启动阶段：

1. `main.py` 调用 `web_app.server.run()`。
2. `WebGISAppState` 加载 `.env`。
3. `BrowserMapHandler` 从 `data/geodata/*.geojson` 读取图层元信息。
4. 后端只缓存图层名称、字段、几何类型、要素数、bbox 和 CRS 等元信息。

交互阶段：

1. 前端调用 `/api/layers` 获取图层列表。
2. 用户勾选图层后，前端调用 `/api/layer_data`。
3. 请求带上 `layer_name`、`bbox` 和 `zoom`。
4. 后端仅返回当前视野范围内的要素，降低大图层加载压力。
5. 分析结果通过 `/api/highlights` 或 `/api/chat` 返回的 `highlights` 显示在地图上。

## ACE 自进化链路

```text
Analyze：CoordinatorAgent + ContextManager
 ↓
Act：SpatialAnalystAgent + GIS Tools + CodeAgent
 ↓
Critic：agents/critic_agent.py + core/critic.py
 ↓
Evolve：core/evolution.py + ExperienceLibrary
 ↓
Reuse：后续任务检索并注入高置信经验
```

## 实验调用链

1. 前端或命令行选择 `exp1`、`exp2`、`exp3`、`exp4` 或 `all`。
2. 后端启动对应实验 runner，并读取 `data/experiments/` 下的 workbook、reference 或 evaluation config。
3. runner 按实验协议执行 mock / 规则化评估，或在 `use_real_ace=true` 时调用真实 ACE 流程。
4. 结果目录写入 `summary.json`、`results.csv`、报告和可选图表。
5. 实验页读取历史结果，用于图表展示、重命名、删除和导出。

## 可追踪日志

- `task_log.jsonl`：记录用户任务、有效任务、回答摘要和任务类型。
- `code_log.jsonl`：记录代码执行、重试和失败信息。
- `evolution_log.jsonl`：记录经验新增、更新、跳过和命中。
- `error_log.jsonl`：记录 HTTP、AIHandler 和运行期异常。
