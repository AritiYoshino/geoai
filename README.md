# GeoAI ACE WebGIS

一个基于 ACE（Agentic Context Engineering）机制的多智能体 WebGIS 原型系统。

项目面向地理空间问答、POI 查询、邻近分析、聚类分析、热点分析、统计汇总、地图高亮与经验自进化场景，支持：

- 多智能体协同分析
- GIS 工具调用
- 受控空间代码执行
- Critic / Evolution 轻量闭环
- WebGIS 可视化
- 经验库动态更新

## 1. 项目目标

本项目的核心目标不是单纯做“聊天问答”，而是构建一个可执行、可反思、可演化的 GeoAI 原型：

1. 用户以自然语言提出地理分析任务
2. 系统识别任务类型并调度 GIS 工具
3. 在必要时自动生成并执行受控 GeoPandas 代码
4. 对错误、空结果、字段问题、CRS 风险进行结构化诊断
5. 将经验沉淀到经验库，在后续任务中复用

## 2. 当前数据

当前默认数据目录为：

`data/geodata/`

包含：

- `住宿服务.geojson`
- `餐饮.geojson`
- `成都行政区.geojson`

系统启动时只读取图层元信息，不会把所有图层完整转换成 GeoJSON 发送到前端。

## 3. 项目结构

```text
geoai/
├─ agents/                    # 多智能体层
│  ├─ code_agent.py
│  ├─ coordinator_agent.py
│  ├─ reflector_agent.py
│  ├─ spatial_analyst_agent.py
│  └─ __init__.py
├─ core/                      # 核心引擎
│  ├─ ace_core.py
│  ├─ context_manager.py
│  ├─ critic.py
│  ├─ evolution.py
│  ├─ experience_bank_manager.py
│  ├─ experience_library.py
│  ├─ jsonl_logger.py
│  ├─ session_store.py
│  └─ __init__.py
├─ tools/                     # GIS 工具集
│  ├─ search.py
│  ├─ query.py
│  ├─ nearby.py
│  ├─ detail.py
│  ├─ buffer_tool.py
│  ├─ overlay_tool.py
│  ├─ proximity_tool.py
│  ├─ clustering_tool.py
│  ├─ statistics_tool.py
│  ├─ export_tool.py
│  ├─ code_executor.py
│  ├─ advanced_common.py
│  ├─ utils_geo.py
│  └─ __init__.py
├─ experiments/               # 实验系统
│  ├─ __init__.py             # 统一导出入口
│  ├─ runner.py               # 统一运行器
│  ├─ export_utils.py         # matplotlib 图表导出（中文标签）
│  ├─ exp1/                   # 基线对比实验
│  │  ├─ __init__.py
│  │  ├─ exp1_runner.py
│  │  ├─ exp1_analyzer.py
│  │  ├─ exp1_suite.json
│  │  └─ exp1_experience_library.json
│  ├─ exp2/                   # 消融实验
│  │  ├─ __init__.py
│  │  ├─ exp2_runner.py
│  │  ├─ exp2_suite.json
│  │  └─ exp2_experience_library.json
│  ├─ exp3/                   # 记忆抗退化实验
│  │  ├─ __init__.py
│  │  ├─ exp3_runner.py
│  │  ├─ exp3_suite.json
│  │  └─ exp3_experience_library.json
│  ├─ exp4/                   # 长上下文扩展实验
│  │  ├─ __init__.py
│  │  ├─ exp4_runner.py
│  │  ├─ exp4_suite.json
│  │  └─ exp4_experience_library.json
│  └─ experiment_outputs/     # 运行输出
│      ├─ exp1/
│      ├─ exp2/
│      ├─ exp3/
│      └─ exp4/
├─ web_app/                   # Web 前端
│  ├─ server.py
│  ├─ web_map_handler.py
│  ├─ static/
│  │  ├─ index.html
│  │  ├─ experiment.html
│  │  ├─ experiment.js
│  │  ├─ experiment.css
│  │  ├─ app.js
│  │  └─ styles.css
│  └─ __init__.py
├─ data/                      # 数据
│  ├─ geodata/
│  ├─ exports/
│  ├─ experience_libraries/
│  ├─ ace_experience_library.json
│  ├─ experience_banks.json
│  └─ sessions.json
├─ logs/                      # JSONL 日志
│  ├─ task_log.jsonl
│  ├─ code_log.jsonl
│  ├─ evolution_log.jsonl
│  └─ error_log.jsonl
├─ geodata/                   # Shapefile 数据
├─ .vscode/
│  └─ launch.json
├─ ai_handler.py
├─ main_web.py
├─ geoprc.py
├─ utils.py
├─ ACE_UPGRADE.md
├─ EXPERIMENT_GUIDE.md
├─ SYSTEM_ARCHITECTURE.md
└─ README.md
```

## 4. 各模块功能

### 4.1 agents

- [`agents/coordinator_agent.py`](d:/geoai/agents/coordinator_agent.py:1)
  负责意图识别、任务规划、上下文组织、多轮调度。

- [`agents/spatial_analyst_agent.py`](d:/geoai/agents/spatial_analyst_agent.py:1)
  负责调用 GIS 工具或触发代码执行。

- [`agents/code_agent.py`](d:/geoai/agents/code_agent.py:1)
  负责任务代码执行、失败重试、代码修复，对应任务书中的 `Coder Agent`。

- [`agents/reflector_agent.py`](d:/geoai/agents/reflector_agent.py:1)
  保留原有接口，内部接入 Critic 和 Evolution，对应：
  - `Critic Agent`
  - `Evolution Manager`

### 4.2 core

- [`core/ace_core.py`](d:/geoai/core/ace_core.py:1)
  任务分类、Trace 记录、帮助型问题识别。

- [`core/context_manager.py`](d:/geoai/core/context_manager.py:1)
  会话上下文、最近 POI 记忆、用户偏好、Prompt 组织、ACE 面板整理。

- [`core/critic.py`](d:/geoai/core/critic.py:1)
  结构化错误诊断。

- [`core/evolution.py`](d:/geoai/core/evolution.py:1)
  错误到经验的演化入口。

- [`core/experience_library.py`](d:/geoai/core/experience_library.py:1)
  经验检索、去重、质量更新、置信度控制。

- [`core/experience_bank_manager.py`](d:/geoai/core/experience_bank_manager.py:1)
  多经验库切换、创建、删除、重命名。

- [`core/session_store.py`](d:/geoai/core/session_store.py:1)
  会话持久化、反馈记录、ACE 面板状态保存。

- [`core/jsonl_logger.py`](d:/geoai/core/jsonl_logger.py:1)
  JSONL 日志记录器。

### 4.3 tools

基础工具：

- `search_poi`
- `query_poi_by_conditions`
- `get_poi_by_index`
- `find_nearby`
- `find_nearby_point`
- `find_nearby_point_filtered`

扩展空间分析工具：

- `buffer_analysis`
- `overlay_layers`
- `spatial_join_layers`
- `nearest_neighbor_search`
- `cluster_points_dbscan`
- `hotspot_analysis`
- `summarize_layer_statistics`
- `export_analysis_result`

高级能力：

- `execute_spatial_code`

### 4.4 web_app

- [`web_app/server.py`](d:/geoai/web_app/server.py:1)
  HTTP 服务入口，负责 API 分发。

- [`web_app/web_map_handler.py`](d:/geoai/web_app/web_map_handler.py:1)
  地图数据元信息管理、GeoJSON 按需加载、bbox 裁剪、高亮输出。

- [`web_app/static/app.js`](d:/geoai/web_app/static/app.js:1)
  前端主逻辑：图层按需加载、会话交互、ACE 面板、经验库切换、地图联动。

## 5. 系统运行逻辑

### 5.1 启动阶段

1. 执行 [`main_web.py`](d:/geoai/main_web.py:1)
2. 初始化 [`web_app/server.py`](d:/geoai/web_app/server.py:1)
3. `BrowserMapHandler` 从 `data/geodata` 读取 GeoJSON 图层元信息
4. `AIHandler` 初始化：
   - LLM
   - ContextManager
   - ExperienceLibrary
   - 各类 Agent
   - GIS Tools

### 5.2 前端图层加载逻辑

1. 前端启动时调用 `/api/layers`
2. 只获取图层元信息：
   - 名称
   - 字段
   - geometry_types
   - feature_count
   - bbox
   - crs
3. 用户勾选某个图层时，前端调用 `/api/layer_data`
4. 服务端按 `bbox + zoom` 返回当前视野范围内要素
5. 地图移动结束后，前端用 debounce 重新刷新已选图层
6. 大图层默认不自动全量加载，提示先放大地图

### 5.3 问答与分析逻辑

1. 用户在前端输入问题
2. 前端调用 `/api/chat`
3. `AIHandler.process_message()` 处理用户输入
4. `CoordinatorAgent`：
   - 识别任务类型
   - 检索会话上下文
   - 检索经验库
   - 生成执行计划
5. `SpatialAnalystAgent`：
   - 调用固定 GIS 工具
   - 或触发 `CodeAgent`
6. `ReflectorAgent`：
   - 对错误与异常进行结构化诊断
   - 更新经验库
7. 返回：
   - 自然语言回答
   - ACE 面板
   - Trace
   - 高亮结果

### 5.4 用户反馈与偏好逻辑

系统不再依赖“正确 / 不正确 / 纠正”按钮。

用户可以直接在对话中输入：

- `对`
- `不对`
- `不对，应该高亮行政区 shp，不是点 shp`

系统会：

1. 将其识别为反馈或纠正
2. 写入经验库
3. 必要时更新当前会话偏好
4. 后续任务继续复用这些偏好与经验

## 6. 主要接口说明

### 6.1 图层相关

- `GET /api/layers`
  返回图层元信息列表

- `GET /api/layer_data?layer_name=...&bbox=minx,miny,maxx,maxy&zoom=...`
  返回指定图层在当前视野内的 GeoJSON

- `GET /api/highlights`
  返回当前高亮要素

- `POST /api/highlights/clear`
  清空高亮

### 6.2 问答与分析

- `POST /api/chat`
  发送用户消息，返回：
  - `answer`
  - `trace`
  - `ace_panel`
  - `experience`
  - `session`
  - `sessions`
  - `highlights`

- `GET /api/trace`
  获取最新 Trace

- `GET /api/ace-panel`
  获取 ACE 面板结构化内容

### 6.3 会话相关

- `GET /api/sessions`
- `POST /api/sessions/new`
- `POST /api/sessions/switch`
- `POST /api/sessions/rename`
- `POST /api/sessions/delete`

### 6.4 经验库相关

- `GET /api/experience`
- `GET /api/experience-banks`
- `POST /api/experience-banks/switch`
- `POST /api/experience-banks/create`
- `POST /api/experience-banks/rename`
- `POST /api/experience-banks/delete`

### 6.5 兼容保留接口

- `POST /api/feedback`

当前前端已不再依赖此按钮式反馈接口，但服务端仍保留兼容。

## 7. ACE 自进化机制

当前实现中：

- `CodeAgent` = 代码生成与执行
- `ReflectorAgent` 内部扩展为：
  - `Critic Agent`
  - `Evolution Manager`

即：

`ReflectorAgent = 反思入口 + Critic 模块 + Evolution 模块`

错误闭环如下：

1. 工具调用失败 / 代码执行失败 / 空结果
2. `ReflectorAgent` 调用 `critic.py`
3. 输出结构化诊断：
   - `error_type`
   - `reason`
   - `strategy`
   - `code_hint`
   - `experience_candidate`
4. `ReflectorAgent` 调用 `evolution.py`
5. 将诊断沉淀为经验写回 Experience Library

## 8. 日志与可追溯性

系统会记录以下 JSONL 日志：

- `logs/task_log.jsonl`
  记录用户任务、有效任务、回答摘要

- `logs/code_log.jsonl`
  记录代码执行、重试、错误摘要

- `logs/evolution_log.jsonl`
  记录经验新增、更新、跳过

- `logs/error_log.jsonl`
  记录运行期异常

## 9. 运行方式

### 9.1 环境准备

在 `.env` 中设置：

```text
DEEPSEEK_API_KEY=你的密钥
```

### 9.2 本地启动

```bash
python main_web.py
```

默认访问：

```text
http://127.0.0.1:8000
```

如果 8000 被占用，系统会自动尝试 8001-8010。

### 9.3 公网访问（让别人也能访问你的 Web）

参见 [第 13 节](#13-公网访问部署)。

### 9.4 VS Code 调试

已提供：

[`/.vscode/launch.json`](d:/geoai/.vscode/launch.json:1)

默认调试入口为 `main_web.py`。

## 10. 相关文档

- [`ACE_UPGRADE.md`](d:/geoai/ACE_UPGRADE.md:1)
  ACE 自进化升级说明

- [`EXPERIMENT_GUIDE.md`](d:/geoai/EXPERIMENT_GUIDE.md:1)
  实验运行指南

- [`SYSTEM_ARCHITECTURE.md`](d:/geoai/SYSTEM_ARCHITECTURE.md:1)
  系统架构与模块关系说明

## 11. 实验系统

项目包含 4 组对比实验，位于 [`experiments/`](experiments/)：

| 实验 | 说明 | 评估维度 |
|------|------|---------|
| 实验一 | Base LLM vs ACE 增强对比 | 任务完成率、工具成功率、代码成功率、准确率 |
| 实验二 | 模块消融分析 | 各模块（Critic/Evolution/经验库/上下文）贡献度 |
| 实验三 | 记忆抗退化评估 | POI 召回率、偏好持久率、经验复用率、半衰期 |
| 实验四 | 长上下文扩展对比 | 长序列准确率、跨轮引用准确率、压缩率、污染率 |

### 图表导出

[`experiments/export_utils.py`](experiments/export_utils.py) 提供 matplotlib 图表导出：

- **中文标签**：自动检测系统字体，所有标题/坐标轴/图例均为中文
- **全可视化覆盖**：每个实验导出 3–4 张图片，覆盖所有前端 Chart.js 图表
- **美观样式**：统一调色板、数值标注、网格虚线、高 DPI 输出

```python
from experiments.export_utils import ensure_matplotlib_exports, build_export_zip

# 生成图片
ensure_matplotlib_exports("experiments/experiment_outputs/exp1/exp1_both_20260429-132217")

# 打包导出（summary.json + results.csv + 图片）
build_export_zip("experiments/experiment_outputs/exp1/exp1_both_20260429-132217")
```

## 12. 当前特点

这个版本已经具备：

- WebGIS 前端（MapLibre GL JS）
- GeoJSON 按需加载（bbox + zoom）
- 多智能体协同（Coordinator → SpatialAnalyst/CodeAgent → Reflector）
- GIS 工具调用（查询、邻近、缓冲区、叠加、聚类、热点、统计、导出）
- 受控空间代码执行（沙箱 + AST 安全检查）
- 错误反思与经验演化（Critic + Evolution 闭环）
- 会话级用户偏好记忆
- 4 组对比实验系统（带 matplotlib 图表导出）
- 日志可追溯（JSONL）

如果后续继续演进，比较值得优先推进的方向是：

1. 分析侧图层也进一步做惰性单层加载
2. 高亮策略增加更强的规则约束
3. 文档与前端提示语进一步统一编码与术语

## 13. 公网访问部署

项目支持通过 **ngrok 内网穿透** 将 Web 服务暴露到公网，方便分享给他人访问。

### 13.1 工作原理

```text
用户浏览器  -->  ngrok 隧道 -->  https://xxxx.ngrok-free.dev
                                      |
                              本地 Web 服务器 :8000
```

### 13.2 前置准备

1. 注册 ngrok 账号：https://dashboard.ngrok.com/signup
2. 获取 Authtoken：https://dashboard.ngrok.com/get-started/your-authtoken

### 13.3 一键启动（推荐）

双击项目目录下的 [`start_public.bat`](start_public.bat)，会自动启动 Web 服务器和 ngrok 隧道。

在弹出的 ngrok 窗口中查看公网地址：

```text
Forwarding  https://xxxx.ngrok-free.dev -> http://localhost:8000
```

将 `https://xxxx.ngrok-free.dev` 分享给他人即可访问。

### 13.4 手动启动

**终端 1** — 启动 Web 服务器：

```bash
cd d:\geoai
python main_web.py
```

**终端 2** — 启动 ngrok 隧道：

```bash
C:\Users\CLIENTS\ngrok\ngrok.exe http 8000
```

### 13.5 注意事项

| 项目 | 说明 |
|------|------|
| **服务状态** | 两个终端窗口必须保持打开，关闭即停止服务 |
| **地址变化** | ngrok 免费版每次重启生成的 URL 不同，需重新分享 |
| **本地访问** | 你本地依然通过 `http://127.0.0.1:8000` 访问，不受影响 |
| **速度限制** | 免费版 ngrok 有带宽限制，适合测试和演示 |
| **安全性** | 公网地址任何人都能访问，建议仅用于测试/演示 |

### 13.6 长期方案

如需长期稳定公开访问，建议改用：

1. **Cloudflare Tunnel** — 免费、稳定、可绑定自定义域名
2. **云服务器部署** — 将项目部署到阿里云/腾讯云/AWS
3. **ngrok 付费版** — 固定域名、更高带宽

详细说明参见 [`PUBLIC_ACCESS_GUIDE.md`](PUBLIC_ACCESS_GUIDE.md)。
