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
- Shapefile 原始数据目录：`geodata/`

## 项目结构

```text
geoai/
├── agents/                 # 多 Agent 协同层
│   ├── coordinator_agent.py
│   ├── spatial_analyst_agent.py
│   ├── code_agent.py
│   └── reflector_agent.py
├── core/                   # ACE、上下文、经验库、诊断、日志
│   ├── context_manager.py
│   ├── experience_library.py
│   ├── experience_bank_manager.py
│   ├── critic.py
│   ├── evolution.py
│   ├── session_store.py
│   └── jsonl_logger.py
├── tools/                  # GIS 工具集合
│   ├── search.py
│   ├── query.py
│   ├── nearby.py
│   ├── buffer_tool.py
│   ├── overlay_tool.py
│   ├── proximity_tool.py
│   ├── clustering_tool.py
│   ├── statistics_tool.py
│   ├── export_tool.py
│   └── code_executor.py
├── web_app/                # HTTP 服务与前端静态页面
│   ├── server.py
│   ├── web_map_handler.py
│   └── static/
│       ├── index.html
│       ├── gis.html
│       ├── experiment.html
│       ├── app.js
│       ├── experiment.js
│       ├── styles.css
│       └── experiment.css
├── experiments/            # 四组对比实验与论文证据接口
│   ├── runner.py
│   ├── export_utils.py
│   ├── thesis_evidence.py
│   ├── exp1/
│   ├── exp2/
│   ├── exp3/
│   └── exp4/
├── data/
│   ├── geodata/
│   ├── experience_libraries/
│   ├── ace_experience_library.json
│   ├── experience_banks.json
│   └── sessions.json
├── logs/                   # JSONL 运行日志
├── plans/                  # 方案、分析和论文草稿
├── ai_handler.py
├── main.py
├── requirements.txt
└── README.md
```

## 核心流程

1. 用户在前端输入自然语言地理分析任务。
2. `AIHandler` 组织 LLM、上下文、经验库、工具和 Agent。
3. `CoordinatorAgent` 识别任务类型，检索会话上下文和经验库，生成执行计划。
4. `SpatialAnalystAgent` 选择固定 GIS 工具，或触发 `CodeAgent` 执行受控 GeoPandas 代码。
5. `ReflectorAgent` 在错误、空结果或用户纠正时调用 `core/critic.py` 和 `core/evolution.py`，把诊断沉淀为经验。
6. 前端展示自然语言回答、Trace、ACE 面板、经验库摘要和地图高亮结果。

## GIS 工具能力

当前 `tools.create_tools()` 注册的工具包括：

| 工具 | 说明 |
|---|---|
| `search_poi` | 跨图层 POI 检索 |
| `query_poi_by_conditions` | 按属性条件查询 POI |
| `get_poi_by_index` | 按索引查看 POI 详情 |
| `find_nearby` | 图层间邻近分析 |
| `find_nearby_point` | 以单个点为中心的邻近分析 |
| `find_nearby_point_filtered` | 带关键词过滤的邻近分析 |
| `buffer_analysis` | 缓冲区分析 |
| `overlay_layers` | 图层叠加分析 |
| `spatial_join` | 空间连接 |
| `nearest_neighbor` | 最近邻分析 |
| `dbscan` | DBSCAN 聚类 |
| `hotspot` | 热点分析 |
| `statistics` | 图层统计汇总 |
| `export` | 分析结果导出 |
| `execute_spatial_code` | 受控空间代码执行 |

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

四组实验均支持数据读取、任务集读取、历史结果、运行、重命名、删除和导出：

- `GET /api/experiment/exp1/data`
- `GET /api/experiment/exp1/tasks`
- `GET /api/experiment/exp1/results`
- `GET /api/experiment/exp1/export`
- `POST /api/experiment/exp1/run`
- `POST /api/experiment/exp1/rename`
- `POST /api/experiment/exp1/delete`

`exp2`、`exp3`、`exp4` 使用同样的路径结构。

论文辅助接口：

- `GET /api/thesis/evidence`：汇总实验、经验库和论文证据数据

## 实验系统

| 实验 | 目录 | 目标 |
|---|---|---|
| 实验一 | `experiments/exp1/` | Base LLM 与 ACE 增强系统对比 |
| 实验二 | `experiments/exp2/` | Critic、Evolution、经验库、上下文记忆消融 |
| 实验三 | `experiments/exp3/` | 多轮对话中的记忆抗退化能力 |
| 实验四 | `experiments/exp4/` | 长上下文扩展、压缩和污染控制 |

实验输出保存在 `experiments/experiment_outputs/{expX}/`。`experiments/export_utils.py` 可把 `summary.json` 和 `results.csv` 导出为论文可用图表与 zip 包。

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

## 相关文档

- `ACE_UPGRADE.md`：ACE 自进化机制说明
- `SYSTEM_ARCHITECTURE.md`：系统架构与模块关系
- `EXPERIMENT_GUIDE.md`：实验系统运行指南
- `plans/project_analysis.md`：项目分析报告
- `plans/thesis_initial_draft.md`：论文初稿
- `plans/upgrade_landing_page.md`：统一入口首页升级记录
