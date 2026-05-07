# 基于 ACE 机制的多 Agent 协同自进化地理分析系统设计与实现

> 论文定位：毕业设计论文大纲与初稿骨架。本文应重点突出“系统设计与实现”，实验部分用于验证 ACE 机制有效性，不宜写成纯算法论文。

## 摘要

随着大语言模型在自然语言理解、代码生成和工具调用方面的发展，地理信息系统正在从传统专业软件操作模式转向自然语言驱动的智能分析模式。然而，地理空间分析任务具有明显的专业约束，例如坐标参考系、图层类型、字段名称、空间关系、距离单位、参数尺度和结果可视化方式等。现有大模型智能体在连续 GIS 任务中容易出现空间规则保持不稳定、上下文遗忘、代码执行失败、错误经验无法复用等问题。

针对上述问题，本文设计并实现了一个基于 ACE（Agentic Context Engineering）机制的多 Agent 协同自进化地理分析系统。系统以动态经验库和多 Agent 分工为核心，构建了由任务协调智能体、空间分析智能体、代码执行智能体、Critic 错误诊断智能体、Evolution 经验演化进化智能体和 WebGIS 可视化模块组成的闭环架构，实现了“自然语言任务输入、上下文组织、经验检索、GIS 工具调用、受控空间代码执行、错误诊断、经验写回、地图可视化和后续复用”的完整流程。

系统基于 Python、GeoPandas、MapLibre GL JS、LangChain DeepSeek 接口和 HTTP 服务实现，支持 POI 检索、属性查询、邻近分析、缓冲区分析、空间叠加、空间连接、最近邻分析、DBSCAN 聚类、热点分析、统计汇总、结果导出、地图高亮、会话管理和多经验库管理。本文结合成都餐饮、住宿服务和行政区数据构建实验任务集，设计基线对比、模块消融、记忆抗退化和长上下文扩展四组实验，对系统任务完成率、工具成功率、代码成功率、准确率、经验复用率和多轮一致性进行验证。实验与系统运行结果表明，ACE 机制能够提高地理智能体在复杂空间任务中的稳定性和可复用性，为自然语言驱动的地理空间分析提供了可行的系统实现方案。

**关键词：** Agentic Context Engineering；多 Agent 协同；WebGIS；地理空间分析；经验库；GeoPandas；自进化

## Abstract

With the development of large language models in natural language understanding, code generation, and tool invocation, geographic information systems are shifting from expert-oriented software operation to natural-language-driven intelligent analysis. However, geospatial analysis tasks involve strict domain constraints, such as coordinate reference systems, layer types, field names, spatial relationships, distance units, parameter scales, and visualization strategies. Existing LLM-based agents may suffer from unstable spatial rule retention, context forgetting, code execution failures, and limited reuse of error-handling experience in continuous GIS tasks.

To address these issues, this thesis designs and implements a multi-agent collaborative self-evolving geospatial analysis system based on Agentic Context Engineering (ACE). Centered on a dynamic experience library and multi-agent collaboration, the system consists of a coordinator agent, a spatial analyst agent, a code execution agent, a reflection and diagnosis agent, an evolution module, and a WebGIS visualization module. It forms a closed loop covering natural-language task input, context organization, experience retrieval, GIS tool invocation, controlled spatial code execution, error diagnosis, experience update, map visualization, and later reuse.

The prototype is implemented with Python, GeoPandas, MapLibre GL JS, LangChain DeepSeek, and a lightweight HTTP service. It supports POI search, attribute query, proximity analysis, buffer analysis, overlay analysis, spatial join, nearest-neighbor analysis, DBSCAN clustering, hotspot analysis, statistical summarization, result export, map highlighting, session management, and multi-experience-bank management. Experiments are conducted on local Chengdu restaurant, accommodation, and administrative district data. Four groups of experiments, including baseline comparison, module ablation, memory degradation resistance, and long-context extension, are designed to evaluate task completion rate, tool success rate, code success rate, accuracy, experience reuse, and multi-turn consistency. The results indicate that the ACE mechanism improves the stability and reusability of geospatial agents in complex spatial tasks and provides a feasible implementation path for natural-language-driven geospatial analysis.

**Keywords:** Agentic Context Engineering; Multi-Agent Collaboration; WebGIS; Geospatial Analysis; Experience Library; GeoPandas; Self-evolution

---

# 第 1 章 绪论

## 1.1 研究背景

### 1.1.1 GIS 使用模式的智能化转变

地理信息系统长期依赖专业软件、脚本编程和人工参数设置完成空间数据处理、空间分析和地图制图。随着大语言模型具备自然语言理解、工具调用和代码生成能力，用户可以直接通过自然语言描述空间任务，由智能体完成任务理解、工具选择、代码生成和结果解释。这种方式有助于降低 GIS 使用门槛，提高空间分析自动化水平。

### 1.1.2 地理空间分析任务的专业约束

地理空间任务不同于普通文本问答。系统需要正确处理图层类型、字段名称、坐标参考系、空间谓词、距离单位、几何有效性和结果规模控制。例如，缓冲区分析必须关注米制投影，空间连接必须正确区分点图层与面图层，统计类结果的地图高亮应符合用户对行政区或 POI 图层的展示偏好。

### 1.1.3 大模型地理智能体的稳定性问题

大模型虽然能够生成 GeoPandas 代码和调用 GIS 工具，但在多轮任务中仍可能出现字段幻觉、图层选择错误、CRS 忽略、空结果未诊断、用户纠正未复用等问题。如何把一次任务中的错误和用户反馈转化为后续可复用经验，是提升地理智能体稳定性的关键。

## 1.2 研究目的与意义

### 1.2.1 研究目的

本文目标是设计并实现一个可运行的地理智能分析系统，使其能够：

1. 接收自然语言 GIS 任务。
2. 自动选择封装 GIS 工具或生成受控空间分析代码。
3. 在 WebGIS 地图上展示图层和分析结果。
4. 记录任务执行过程和错误信息。
5. 将错误诊断、用户纠正和成功策略沉淀为经验。
6. 在后续相似任务中复用经验，形成 ACE 自进化闭环。

### 1.2.2 理论意义

本文将 ACE 机制引入地理空间智能体，探索动态上下文、经验库、错误诊断和经验演化在 GIS 任务中的适用性。相比静态 prompt 或普通 RAG，ACE 更强调从实际执行反馈中持续更新上下文策略。

### 1.2.3 实践意义

本文实现的 GeoAI ACE WebGIS 原型系统可让用户通过自然语言完成 POI 查询、邻近分析、缓冲区分析、叠加统计、聚类分析和地图高亮，为智能地图应用、城市 POI 分析和教学实验提供可运行系统。

## 1.3 国内外研究现状

### 1.3.1 大语言模型与智能体研究现状

可综述 LLM 在任务规划、工具调用、代码生成、Agent 架构方面的研究，并指出通用智能体缺少地理空间规则约束。

### 1.3.2 GeoAI 与地理空间代码生成研究现状

可综述 GeoAI、自然语言到 GIS 分析、GeoPandas 代码生成、WebGIS 智能问答等方向，并指出现有方法多关注单次任务完成，较少关注错误经验沉淀和多轮复用。

### 1.3.3 上下文工程与经验库机制研究现状

可说明 prompt engineering、RAG、memory、reflection、self-improvement 等机制，并引出 ACE 的价值：上下文不是静态文本，而是可演化的任务策略集合。

## 1.4 研究内容

本文围绕项目实际实现，主要包括：

1. 基于 ACE 的多 Agent 地理分析总体架构设计。
2. 地图数据管理、按需加载和 WebGIS 可视化设计。
3. GIS 工具集与受控空间代码执行机制设计。
4. 经验库、会话记忆、用户反馈和错误诊断机制设计。
5. 四组实验系统设计与实现。
6. 系统应用展示与实验结果分析。

## 1.5 技术路线

本文技术路线如下：

```text
自然语言任务
 -> 任务分类与上下文组织
 -> 经验库检索
 -> GIS 工具调用或空间代码执行
 -> WebGIS 地图高亮与结果返回
 -> Critic 错误诊断
 -> Evolution 经验演化
 -> 后续任务经验复用
```

对应项目模块：

| 技术环节 | 项目实现 |
|---|---|
| 用户交互 | `web_app/static/gis.html`, `web_app/static/app.js` |
| 后端服务 | `web_app/server.py` |
| 模型与 Agent 装配 | `ai_handler.py` |
| 任务协调 | `agents/coordinator_agent.py` |
| 空间分析 | `agents/spatial_analyst_agent.py`, `tools/` |
| 代码执行 | `agents/code_agent.py`, `tools/code_executor.py` |
| 错误诊断 | `agents/critic_agent.py`, `core/critic.py` |
| 经验演化 | `agents/evolution_agent.py`, `core/evolution.py` |
| 经验库 | `core/experience_library.py`, `core/experience_bank_manager.py` |
| 实验系统 | `experiments/`, `web_app/static/experiment.html` |

## 1.6 论文组织结构

本文共分为八章。第 1 章介绍研究背景、目的、意义和技术路线。第 2 章介绍 ACE、多 Agent、WebGIS 和地理空间分析关键技术。第 3 章进行系统需求分析。第 4 章给出系统总体设计，重点说明项目结构、模块关系、Agent 关系和数据流。第 5 章介绍系统详细实现，重点说明数据与参数如何在前端、后端、Agent 和工具之间传递。第 6 章进行实验设计与结果分析。第 7 章展示系统应用效果。第 8 章总结全文并展望后续工作。

---

# 第 2 章 理论基础与关键技术

## 2.1 Agentic Context Engineering 机制

### 2.1.1 ACE 的基本思想

ACE 将上下文视为可持续更新的任务经验系统，而不是一次性提示词。系统通过记录任务过程、诊断错误、提炼经验和复用经验，使智能体在多轮任务中逐步稳定。

### 2.1.2 ACE 与传统 Prompt / RAG 的区别

传统 prompt 主要依赖预设规则，RAG 主要依赖外部文档检索。本文中的 ACE 还包含任务执行反馈、错误诊断、用户纠正和经验质量控制，更适合需要持续修复和复用规则的 GIS 任务。

### 2.1.3 ACE 在本文系统中的体现

本文系统中的 ACE 包括：

- 任务前：根据任务类型检索经验。
- 任务中：记录工具调用、代码执行和地图高亮。
- 任务后：诊断错误、空结果和用户纠正。
- 后续任务：复用高置信经验和会话偏好。

## 2.2 多 Agent 协同机制

### 2.2.1 多 Agent 分工思想

复杂地理任务需要意图识别、数据选择、方法规划、代码执行、结果解释和错误诊断。多 Agent 分工能降低单个模型在长链路任务中的负担。

### 2.2.2 本文 Agent 角色定义

| 角色 | 功能 |
|---|---|
| Coordinator Agent | 任务分类、上下文组织、经验检索、调度 |
| Spatial Analyst Agent | 选择和调用 GIS 工具 |
| Code Agent | 生成、执行和修复空间分析代码 |
| Critic Agent | 结构化识别错误类型、错误原因和修复策略 |
| Evolution Agent | 将错误诊断和用户反馈沉淀为可复用经验 |

### 2.2.3 多 Agent 与 ACE 的关系

多 Agent 提供角色分工，ACE 提供经验流转机制。两者结合后，系统不仅能完成当前任务，还能把任务反馈变成后续任务的上下文资源。

## 2.3 WebGIS 与空间数据可视化

### 2.3.1 WebGIS 基本架构

WebGIS 通常包括前端地图容器、图层数据接口、地图交互逻辑和后端空间数据服务。本文采用 MapLibre GL JS 作为前端地图引擎，后端提供 GeoJSON 图层元信息和视野内数据加载接口。

### 2.3.2 按需加载策略

项目启动时只读取图层元信息，前端根据当前视野 `bbox` 和缩放级别请求图层数据，避免一次性加载大规模 GeoJSON。

### 2.3.3 地图高亮策略

系统根据分析结果生成高亮要素。对于 POI 查询类任务，高亮点要素；对于统计类任务，可根据用户偏好高亮行政区面图层。

## 2.4 GeoPandas 与空间分析方法

### 2.4.1 GeoPandas 空间数据处理

GeoPandas 支持矢量数据读取、字段筛选、投影转换、空间连接、缓冲区和几何运算，是本文受控代码执行和工具封装的主要基础。

### 2.4.2 本文支持的空间分析类型

包括 POI 检索、属性查询、邻近分析、缓冲区分析、空间叠加、空间连接、最近邻分析、DBSCAN 聚类、热点分析、统计汇总和结果导出。

### 2.4.3 地理空间代码生成风险

重点风险包括：

- 字段名不存在。
- 图层类型选择错误。
- CRS 与距离单位不匹配。
- 空间连接方向错误。
- 空结果未处理。
- 输出规模过大。
- 地图高亮对象与任务语义不一致。

## 2.5 本章小结

本章介绍了 ACE、多 Agent、WebGIS、GeoPandas 和空间分析风险，为后续系统需求、架构设计和实现提供理论基础。

---

# 第 3 章 系统需求分析

## 3.1 业务需求分析

系统面向自然语言驱动的地理空间分析场景，用户无需直接编写 GIS 代码，只需输入任务描述，即可完成数据查询、空间分析和地图展示。

典型任务包括：

```text
搜索名称包含火锅的餐饮 POI
查找武侯区内的住宿服务
哪个区的餐饮数量第二多，并高亮该行政区
在餐饮点周围做 500 米缓冲区分析
对餐饮 POI 做 DBSCAN 聚类
不对，应该高亮行政区 shp，不是餐饮点
```

## 3.2 功能需求

### 3.2.1 地图与图层管理需求

- 展示成都 POI 与行政区图层。
- 获取图层元信息。
- 按视野加载 GeoJSON。
- 支持地图高亮和清空高亮。

### 3.2.2 自然语言地理问答需求

- 支持用户输入自然语言任务。
- 返回自然语言回答。
- 返回工具调用 Trace。
- 返回 ACE 面板信息。
- 支持结果地图高亮。

### 3.2.3 GIS 分析工具需求

系统需支持：

- POI 检索。
- 属性查询。
- 邻近分析。
- 缓冲区分析。
- 空间叠加和空间连接。
- 最近邻分析。
- 聚类和热点分析。
- 统计汇总。
- 结果导出。
- 受控空间代码执行。

### 3.2.4 ACE 自进化需求

- 按任务类型检索经验。
- 记录用户反馈和系统错误。
- 诊断字段、CRS、空结果、几何和执行错误。
- 将诊断沉淀为经验。
- 支持多经验库管理。
- 支持会话级偏好记忆。

### 3.2.5 实验验证需求

- 支持四组实验运行。
- 保存实验结果。
- 展示实验图表。
- 支持结果导出。
- 支持历史实验结果管理，包括结果读取、重命名、删除和打包导出。

## 3.3 非功能需求

### 3.3.1 可用性

系统应提供统一首页、GIS 系统入口和实验系统入口，操作路径清晰。

### 3.3.2 可追踪性

系统应记录任务日志、代码执行日志、经验演化日志和错误日志，方便论文实验复现与问题定位。

### 3.3.3 安全性

受控代码执行应限制危险操作，避免任意文件操作、系统命令和不受控 import。

### 3.3.4 可扩展性

GIS 工具应通过统一工厂函数注册，后续可扩展更多空间分析能力；经验库应支持多库切换，方便实验对比。

## 3.4 数据需求

本文使用数据包括：

| 数据 | 文件 | 类型 | 用途 |
|---|---|---|---|
| 餐饮 POI | `data/geodata/餐饮.geojson` | 点 | POI 检索、统计、聚类 |
| 住宿服务 POI | `data/geodata/住宿服务.geojson` | 点 | 查询和邻近分析 |
| 成都行政区 | `data/geodata/成都行政区.geojson` | 面 | 行政区统计和地图高亮 |
| 原始 Shapefile | `geodata/` | 点/面 | 数据来源与补充说明 |

## 3.5 本章小结

本章从业务、功能、非功能和数据四个角度明确系统需求，为总体设计和详细实现提供依据。

---

# 第 4 章 系统总体设计

## 4.1 总体架构设计

系统由七层组成：

1. 前端交互层：统一首页、GIS 页面、实验页面。
2. HTTP 服务层：页面路由和 REST API。
3. 应用编排层：`AIHandler` 装配模型、Agent、上下文、经验库和工具。
4. 多 Agent 协同层：任务协调、空间分析、代码执行、错误诊断和经验演化。
5. ACE 核心层：上下文管理、经验库、错误诊断、经验演化和日志。
6. GIS 工具层：封装空间查询、分析、统计和导出工具。
7. 数据与实验层：GeoJSON、经验库、会话、日志和实验输出。

建议插图：系统总体架构图。

## 4.2 项目结构设计

本文系统按照前端、后端、Agent、核心机制、GIS 工具、实验系统和数据日志进行目录划分。项目结构如下：

```text
geoai/
├── main.py                     # 系统启动入口
├── ai_handler.py               # LLM、Agent、工具、经验库装配入口
├── utils.py                    # 通用工具函数
├── agents/                     # 多 Agent 协同模块
│   ├── __init__.py
│   ├── coordinator_agent.py     # 任务协调智能体
│   ├── spatial_analyst_agent.py # 空间分析智能体
│   ├── code_agent.py           # 代码执行智能体
│   ├── critic_agent.py         # 错误诊断智能体
│   └── evolution_agent.py      # 经验演化进化智能体
├── core/                       # ACE 核心模块
│   ├── __init__.py
│   ├── ace_core.py             # ACE 核心协调
│   ├── context_manager.py       # 上下文、会话、偏好和 ACE 面板
│   ├── experience_library.py    # 经验库检索、去重和质量控制
│   ├── experience_bank_manager.py # 多经验库管理
│   ├── critic.py               # 结构化错误诊断
│   ├── evolution.py            # 经验演化
│   ├── session_store.py         # 会话持久化
│   └── jsonl_logger.py          # JSONL 日志
├── tools/                      # GIS 工具集合
│   ├── __init__.py             # create_tools() 统一注册入口
│   ├── search.py               # POI 检索
│   ├── query.py                # 条件查询
│   ├── detail.py               # POI 详情
│   ├── nearby.py               # 邻近分析
│   ├── buffer_tool.py          # 缓冲区分析
│   ├── overlay_tool.py         # 叠加分析与空间连接
│   ├── proximity_tool.py       # 最近邻分析
│   ├── clustering_tool.py      # DBSCAN 聚类与热点分析
│   ├── statistics_tool.py      # 统计汇总
│   ├── export_tool.py          # 结果导出
│   ├── code_executor.py        # 受控空间代码执行
│   ├── advanced_common.py      # 高级空间分析通用函数
│   └── utils_geo.py            # 地理空间工具函数
├── web_app/                    # HTTP 服务和 WebGIS 前端
│   ├── __init__.py
│   ├── server.py               # HTTP 路由和 API 分发
│   ├── web_map_handler.py      # 地图数据处理
│   └── static/
│       ├── index.html          # 统一首页
│       ├── gis.html            # GIS 主页面
│       ├── experiment.html     # 实验页面
│       ├── app.js              # GIS 页面主逻辑
│       ├── experiment.js       # 实验页面主逻辑
│       ├── styles.css
│       ├── experiment.css
│       └── js/
│           ├── gis/
│           │   ├── api.js, layers.js, map_view.js, panels.js
│           └── experiment/
│               ├── chart_setup.js, logic.js, main.js, state.js
├── experiments/                # 四组实验
│   ├── __init__.py
│   ├── runner.py               # 统一实验入口
│   ├── export_utils.py         # 图表导出
│   ├── thesis_evidence.py      # 论文证据汇总
│   ├── exp1/ ~ exp4/           # 各组实验
│   └── experiment_outputs/     # 实验输出目录
├── data/                       # 数据存储
│   ├── geodata/                # GeoJSON 空间数据
│   ├── experience_libraries/   # 用户创建的经验库
│   ├── exports/                # 导出文件
│   ├── ace_experience_library.json
│   ├── experience_banks.json
│   └── sessions.json
├── logs/                       # JSONL 运行日志
├── plans/                      # 方案、分析和论文草稿
├── .env.example
├── requirements.txt
├── README.md
├── SYSTEM_ARCHITECTURE.md
├── ACE_UPGRADE.md
└── EXPERIMENT_GUIDE.md
```

该结构的特点是职责边界清晰：`web_app/` 负责用户交互与接口，`ai_handler.py` 负责系统装配，`agents/` 负责智能体协同，`core/` 负责 ACE 机制，`tools/` 负责具体 GIS 运算，`experiments/` 负责系统评估。

## 4.3 模块设计

### 4.3.1 前端模块设计

| 页面 | 文件 | 作用 |
|---|---|---|
| 统一首页 | `web_app/static/index.html` | 系统入口导航 |
| GIS 页面 | `web_app/static/gis.html` | 地图问答与 ACE 面板 |
| 实验页面 | `web_app/static/experiment.html` | 实验运行、结果管理与可视化 |

前端的主要数据传递方式是 HTTP 请求和 JSON 响应。GIS 页面向后端传递用户问题、当前图层请求参数、会话操作参数和经验库操作参数；后端返回回答、Trace、ACE 面板、图层 GeoJSON、高亮结果和会话状态。

### 4.3.2 后端服务模块设计

`web_app/server.py` 负责：

- 页面路由：`/`、`/gis`、`/experiment`。
- 地图 API。
- 问答 API。
- 会话 API。
- 经验库 API。
- 实验 API。

后端服务层不直接执行空间分析，而是把自然语言任务交给 `AIHandler`，把地图数据请求交给 `BrowserMapHandler`，把实验请求交给 `experiments/` 中的 runner。

### 4.3.3 Agent 模块设计

Agent 模块采用分工协同模式：

```text
CoordinatorAgent
 -> SpatialAnalystAgent
 -> GIS Tools / CodeAgent
 -> CriticAgent
 -> EvolutionAgent
```

不同 Agent 之间不是平级随意调用，而是形成主从式执行链：

| Agent | 输入 | 输出 | 下游 |
|---|---|---|---|
| `CoordinatorAgent` | 用户任务、上下文、经验、图层信息 | 任务计划、工具调用意图、最终回答 | `SpatialAnalystAgent`, `CriticAgent` |
| `SpatialAnalystAgent` | 任务计划、工具列表、上下文 | 工具调用请求或分析结果 | GIS 工具、`CodeAgent` |
| `CodeAgent` | 复杂空间分析任务、错误信息、可用数据上下文 | 可执行代码、执行结果、错误信息 | `CriticAgent` |
| `CriticAgent` | 工具结果、错误、空结果、用户反馈 | 结构化诊断结果 | `EvolutionAgent` |
| `EvolutionAgent` | 诊断结果、任务类型、用户反馈 | 经验新增或更新结果 | `ExperienceLibrary` |

### 4.3.4 ACE 核心模块设计

ACE 核心由上下文、经验库、诊断、演化和日志组成。经验条目应包含类别、任务类型、问题、策略、置信度、成功次数、失败次数和更新时间等字段。

各核心模块关系如下：

```text
ContextManager 保存会话、最近 POI、用户偏好和 Trace
ExperienceLibrary 根据任务类型检索经验并更新经验质量
CriticAgent 将错误转化为结构化诊断
EvolutionAgent 将诊断转化为经验条目
JsonlLogger 记录任务、代码、演化和错误日志
```

### 4.3.5 GIS 工具模块设计

工具通过 `tools.create_tools(handler)` 统一注册，便于统一传入地图处理器、经验库和上下文。

工具参数由 `SpatialAnalystAgent` 根据任务语义生成，典型参数包括：

| 工具类型 | 关键参数 | 参数含义 |
|---|---|---|
| POI 检索 | `keyword`, `layer_name`, `limit` | 检索词、目标图层、返回数量 |
| 条件查询 | `layer_name`, `conditions` | 图层名称和属性条件 |
| 邻近分析 | `source_layer`, `target_layer`, `distance` | 源图层、目标图层、距离阈值 |
| 缓冲区分析 | `layer_name`, `distance` | 分析图层和缓冲半径 |
| 叠加/连接 | `left_layer`, `right_layer`, `predicate` | 两个图层和空间谓词 |
| 聚类/热点 | `layer_name`, `eps`, `min_samples` | 点图层和聚类参数 |
| 统计汇总 | `target_layer`, `group_layer`, `stat_field` | 被统计图层、分组图层和字段 |
| 代码执行 | `task`, `code`, `retry_context` | 任务描述、代码和错误修复上下文 |

## 4.4 数据流与参数传递设计

### 4.4.1 地图数据流

```text
data/geodata/*.geojson
 -> BrowserMapHandler 读取图层元信息
 -> /api/layers 返回图层列表
 -> /api/layer_data 按 bbox 返回当前视野要素
 -> 前端地图渲染
```

地图数据请求中的参数传递如下：

| 参数 | 来源 | 传递到 | 作用 |
|---|---|---|---|
| `layer_name` | 前端图层勾选 | `/api/layer_data` | 指定加载哪一个图层 |
| `bbox` | 前端地图视野 | `BrowserMapHandler.layer_data_payload()` | 裁剪当前视野内要素 |
| `zoom` | 前端地图缩放级别 | `BrowserMapHandler.layer_data_payload()` | 控制大图层加载策略 |

### 4.4.2 问答任务流

```text
用户输入
 -> /api/chat
 -> AIHandler
 -> CoordinatorAgent
 -> SpatialAnalystAgent / CodeAgent
 -> 工具结果
 -> CriticAgent
 -> EvolutionAgent
 -> 回答 + Trace + ACE 面板 + 高亮
```

问答任务中的核心参数流如下：

| 阶段 | 输入参数 | 输出数据 |
|---|---|---|
| 前端提交 | `message`, `session_id` | HTTP JSON 请求 |
| `AIHandler` | 用户文本、当前会话、经验库路径 | 有效任务、反馈标记、偏好更新 |
| `CoordinatorAgent` | 任务文本、图层元信息、上下文、经验 | 执行计划、任务类型、工具调用上下文 |
| `SpatialAnalystAgent` | 执行计划、工具列表、模型输出 | 工具名称、工具参数 |
| GIS 工具 | 图层名、字段、距离、空间谓词等 | 文本结果、GeoDataFrame、高亮信息 |
| `CriticAgent` | 错误、空结果、用户反馈 | 诊断结果、经验候选 |
| `EvolutionAgent` | 诊断结果、任务类型、反馈内容 | 经验更新结果 |
| 后端返回 | 回答、Trace、ACE 面板、高亮 | 前端 UI 与地图渲染 |

### 4.4.3 经验演化流

```text
错误或用户反馈
 -> CriticAgent 诊断
 -> EvolutionAgent 提炼经验
 -> ExperienceLibrary 去重和质量更新
 -> 后续任务检索复用
```

经验演化中的参数传递如下：

| 参数 | 含义 | 使用模块 |
|---|---|---|
| `feedback_type` | 正确、错误或纠正 | `AIHandler`, `EvolutionAgent` |
| `task_type` | 查询、邻近、统计、聚类等 | `ContextManager`, `ExperienceLibrary` |
| `user_task` | 原始用户任务 | `EvolutionAgent` |
| `assistant_answer` | 上轮系统回答 | `EvolutionAgent` |
| `correction` | 用户纠正文本 | `ContextManager`, `ExperienceLibrary` |
| `confidence` | 经验置信度 | `ExperienceLibrary` |

## 4.5 Agent 协作关系设计

### 4.5.1 CoordinatorAgent 与上下文管理

`CoordinatorAgent` 是系统的调度中心。它从 `ContextManager` 获取会话历史、用户偏好、最近 POI 和图层元信息，从 `ExperienceLibrary` 检索相关经验，再决定任务属于查询、邻近、统计、绘图、代码执行还是反馈修正。

### 4.5.2 SpatialAnalystAgent 与工具调用

`SpatialAnalystAgent` 接收协调智能体组织后的任务上下文，使用绑定工具列表生成工具调用。它不直接读写经验库，而是专注于选择合适的 GIS 工具并构造工具参数。

### 4.5.3 CodeAgent 与复杂分析

当固定工具难以完成任务时，`SpatialAnalystAgent` 可触发 `CodeAgent`。`CodeAgent` 生成 GeoPandas/Pandas 代码，并把执行结果或错误返回给上游。如果执行失败，错误会作为修复上下文进入重试或反思流程。

### 4.5.4 CriticAgent 与错误诊断

`CriticAgent` 负责把失败、空结果和代码异常转化为结构化诊断。它调用 `core/critic.py` 判断错误类型、错误原因、修复策略和代码提示，为后续经验演化提供输入。

### 4.5.5 EvolutionAgent 与经验演化进化

`EvolutionAgent` 负责根据 `CriticAgent` 的诊断结果更新经验库，也负责把用户自然语言反馈转化为经验条目。它调用 `core/evolution.py` 完成经验新增、更新、跳过和日志记录。

## 4.6 数据库与文件存储设计

本项目采用轻量文件存储：

- `data/sessions.json`：会话数据。
- `data/ace_experience_library.json`：默认经验库。
- `data/experience_banks.json`：经验库索引。
- `data/experience_libraries/*.json`：用户创建的经验库。
- `logs/*.jsonl`：运行日志。
- `experiments/experiment_outputs/`：实验输出。

## 4.7 接口设计

### 4.7.1 地图与问答接口

- `GET /api/layers`
- `GET /api/layer_data`
- `POST /api/chat`
- `GET /api/highlights`
- `POST /api/highlights/clear`
- `GET /api/trace`
- `GET /api/ace-panel`

### 4.7.2 会话与经验库接口

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

### 4.7.3 实验接口

四组实验均支持：

- `GET /api/experiment/expX/data`
- `GET /api/experiment/expX/tasks`
- `GET /api/experiment/expX/results`
- `GET /api/experiment/expX/export`
- `POST /api/experiment/expX/run`
- `POST /api/experiment/expX/rename`
- `POST /api/experiment/expX/delete`

## 4.8 本章小结

本章从总体架构、项目结构、模块关系、Agent 协作关系、数据流、参数传递、文件存储和接口设计等方面完成系统总体设计。

---

# 第 5 章 系统详细实现

## 5.1 开发环境与技术栈

| 类型 | 技术 |
|---|---|
| 后端语言 | Python |
| HTTP 服务 | `http.server`, `ThreadingHTTPServer` |
| LLM 接口 | `langchain-deepseek`, DeepSeek Chat |
| 空间分析 | GeoPandas, Pandas, Shapely, NumPy |
| 前端地图 | MapLibre GL JS |
| 实验图表 | Chart.js, Matplotlib |
| 配置 | `.env`, `python-dotenv` |
| 数据格式 | GeoJSON, Shapefile, JSON, JSONL |

## 5.2 系统启动实现

系统入口为 `main.py`。启动后导入 `web_app.server.run()`，服务会自动加载 `.env`、初始化地图处理器、读取图层元信息并创建 `AIHandler`。若默认端口 `8000` 被占用，系统会尝试 `8001` 到 `8010`。

建议放图：系统启动时序图。

## 5.3 WebGIS 前端实现

### 5.3.1 统一首页实现

首页作为系统入口，将地理智能系统和实验系统分开，提升系统展示清晰度。

### 5.3.2 GIS 页面实现

GIS 页面包括地图容器、图层面板、聊天面板、ACE 面板、Trace、会话管理和经验库管理。

### 5.3.3 实验页面实现

实验页面支持四组实验运行、结果列表、图表展示、结果重命名、删除和导出。

## 5.4 地图数据按需加载实现

`BrowserMapHandler` 启动时读取 `data/geodata` 中的 GeoJSON 元信息，包括图层名称、字段、几何类型、要素数量、bbox 和 CRS。前端在用户勾选图层和地图移动后，调用 `/api/layer_data` 加载当前视野范围内要素。

具体参数传递过程如下：

```text
前端地图状态
 -> layer_name, bbox, zoom
 -> GET /api/layer_data
 -> WebGISRequestHandler._handle_layer_data()
 -> BrowserMapHandler.layer_data_payload()
 -> 返回 GeoJSON FeatureCollection
 -> 前端 MapLibre 图层渲染
```

其中 `bbox` 由当前地图视野生成，`zoom` 用于判断是否需要限制大图层加载，`layer_name` 用于定位 `data/geodata` 中对应的 GeoJSON 文件。

## 5.5 AIHandler 与多 Agent 装配实现

`AIHandler` 是应用级门面，负责初始化：

- `ChatDeepSeek`
- `ExperienceBankManager`
- `ExperienceLibrary`
- `ContextManager`
- GIS 工具集合
- `CodeAgent`
- `SpatialAnalystAgent`
- `CriticAgent`
- `EvolutionAgent`
- `CoordinatorAgent`

### 5.5.1 AIHandler 的输入输出

`AIHandler.process_message()` 是问答流程的核心入口。它接收前端传来的 `user_input` 和地图高亮回调函数，输出自然语言回答，并间接更新 Trace、ACE 面板、会话状态、经验库和地图高亮。

```text
输入：user_input, highlight_callback
处理：反馈识别 -> 偏好记忆 -> 任务调度 -> 日志记录
输出：answer
副作用：更新上下文、经验库、日志和地图高亮
```

### 5.5.2 CoordinatorAgent 的参数组织

`CoordinatorAgent` 从三个来源组织上下文：

| 来源 | 数据 | 用途 |
|---|---|---|
| 用户输入 | 当前自然语言任务 | 判断任务目标 |
| `ContextManager` | 会话历史、用户偏好、最近 POI、Trace | 支持多轮引用和偏好保持 |
| `ExperienceLibrary` | 高置信经验条目 | 提前注入空间规则和修复策略 |

它的主要输出是给 `SpatialAnalystAgent` 的分析上下文，包括任务类型、可用图层、可用工具、相关经验和历史记忆。

### 5.5.3 SpatialAnalystAgent 的工具参数生成

`SpatialAnalystAgent` 通过模型工具调用能力生成具体工具参数。例如用户输入“在餐饮点周围做 500 米缓冲区分析”时，系统需要形成类似参数：

```json
{
  "tool": "buffer_analysis",
  "arguments": {
    "layer_name": "餐饮",
    "distance": 500
  }
}
```

如果用户输入“哪个区的餐饮数量第二多”，系统需要构造统计或空间连接相关参数，例如目标点图层、行政区面图层、空间谓词和排序方式。

### 5.5.4 工具结果回传

GIS 工具执行后通常返回三类内容：

- 文本摘要：用于最终回答。
- 结构化结果：例如统计表、POI 列表、聚类标签。
- 高亮信息：传给 `highlight_callback`，由 `BrowserMapHandler` 转为地图高亮 GeoJSON。

如果工具返回错误或空结果，`CoordinatorAgent` 会先把该结果交给 `CriticAgent` 进行诊断，再把诊断结果交给 `EvolutionAgent` 做经验演化。

## 5.6 GIS 工具实现

当前工具包括：

| 工具 | 实现文件 | 功能 |
|---|---|---|
| `search_poi` | [`tools/search.py`](tools/search.py) | POI 检索 |
| `query_poi_by_conditions` | [`tools/query.py`](tools/query.py) | 条件查询 |
| `get_poi_by_index` | [`tools/detail.py`](tools/detail.py) | POI 详情 |
| `find_nearby` | [`tools/nearby.py`](tools/nearby.py) | 图层邻近分析 |
| `find_nearby_point` | [`tools/nearby.py`](tools/nearby.py) | 以点为中心的邻近分析 |
| `find_nearby_point_filtered` | [`tools/nearby.py`](tools/nearby.py) | 带过滤的邻近分析 |
| `buffer_analysis` | [`tools/buffer_tool.py`](tools/buffer_tool.py) | 缓冲区分析 |
| `overlay_layers` | [`tools/overlay_tool.py`](tools/overlay_tool.py) | 叠加分析 |
| `spatial_join` | [`tools/overlay_tool.py`](tools/overlay_tool.py) | 空间连接 |
| `nearest_neighbor` | [`tools/proximity_tool.py`](tools/proximity_tool.py) | 最近邻 |
| `dbscan` | [`tools/clustering_tool.py`](tools/clustering_tool.py) | DBSCAN 聚类 |
| `hotspot` | [`tools/clustering_tool.py`](tools/clustering_tool.py) | 热点分析 |
| `statistics` | [`tools/statistics_tool.py`](tools/statistics_tool.py) | 统计汇总 |
| `export` | [`tools/export_tool.py`](tools/export_tool.py) | 结果导出 |
| `execute_spatial_code` | [`tools/code_executor.py`](tools/code_executor.py) | 受控代码执行 |

## 5.7 受控空间代码执行实现

受控代码执行用于处理固定工具难以覆盖的复杂空间分析任务。实现重点包括：

- 限制危险 import。
- 限制文件和系统操作。
- 提供 GeoPandas/Pandas/Shapely 等必要对象。
- 捕获异常并进入反思诊断。
- 支持结果返回和地图高亮。

代码执行的数据传递过程如下：

```text
复杂任务描述
 -> CodeAgent 生成 GeoPandas 代码
 -> execute_spatial_code 沙箱执行
 -> 成功：返回结果摘要和可选 GeoDataFrame
 -> 失败：返回异常信息、Traceback 和修复上下文
 -> CriticAgent 诊断或 CodeAgent 重试
 -> EvolutionAgent 写入经验
```

这部分是本文系统区别于普通聊天式 WebGIS 的关键：系统不是只给出解释，而是能够把模型生成的空间分析逻辑落到可执行代码上。

## 5.8 ACE 经验库实现

经验库支持检索、去重、置信度过滤和质量更新。经验来源包括：

- 系统错误诊断。
- 代码执行失败。
- 空结果分析。
- 用户自然语言纠正。
- 实验预置经验。

可在论文中给出经验条目示例：

```json
{
  "category": "CRS_ERROR",
  "task_types": ["buffer", "nearby"],
  "problem": "距离分析前未转换到米制投影",
  "strategy": "执行缓冲区或距离计算前，先将图层转换到适合成都区域的米制 CRS",
  "confidence": 0.8
}
```

## 5.9 用户反馈与偏好记忆实现

系统支持用户直接输入“对”“不对”“不对，应该……”等自然语言反馈。对于统计类地图高亮偏好，系统可以记录“只高亮行政区面图层，不高亮 POI 点图层”等会话偏好，并在后续任务中复用。

反馈参数传递过程如下：

```text
用户反馈文本
 -> AIHandler._parse_feedback_message()
 -> EvolutionAgent.learn_from_user_feedback()
 -> ExperienceLibrary 新增或更新经验
 -> ContextManager.add_feedback()
 -> 后续任务检索经验和偏好
```

例如用户输入“不对，应该高亮行政区 shp，不是餐饮点”后，系统会把该文本拆分为反馈类型、纠正内容和可能的后续任务，并同时更新经验库和当前会话偏好。

## 5.10 日志与可追踪实现

系统写入：

- `task_log.jsonl`
- `code_log.jsonl`
- `evolution_log.jsonl`
- `error_log.jsonl`

这些日志可用于实验复现、错误回放和论文附录说明。

## 5.11 本章小结

本章结合项目代码说明系统关键模块的实现方式，重点体现毕业设计的工程实现工作量和可运行性。

---

# 第 6 章 实验设计与结果分析

## 6.1 实验环境

实验环境可按如下方式描述：

- 操作系统：Windows。
- 开发语言：Python。
- 后端服务：本地 HTTP 服务。
- 地图数据：成都餐饮、住宿服务和行政区 GeoJSON。
- 模型接口：DeepSeek Chat。
- 输出目录：`experiments/experiment_outputs/`。

## 6.2 实验数据与任务集

实验任务覆盖：

- POI 检索。
- 属性查询。
- 邻近分析。
- 缓冲区分析。
- 叠加分析。
- 聚类和热点。
- 统计汇总。
- 地图高亮。
- 用户纠正。
- 长上下文引用。

任务集文件：

- `experiments/exp1/exp1_suite.json`
- `experiments/exp2/exp2_suite.json`
- `experiments/exp3/exp3_suite.json`
- `experiments/exp4/exp4_suite.json`

### 6.2.1 实验数据来源

实验使用项目内置成都本地空间数据。餐饮和住宿服务为点要素，成都行政区为面要素。点面组合能够覆盖 POI 检索、行政区统计、空间连接、邻近分析和地图高亮等常见 WebGIS 任务。

### 6.2.2 实验任务类型

本文实验任务可分为十类：

| 任务类型 | 示例 | 主要验证能力 |
|---|---|---|
| POI 检索 | 搜索名称包含火锅的餐饮 POI | 关键词检索、结果高亮 |
| 属性查询 | 查询某区内住宿服务 | 字段识别、条件过滤 |
| 邻近分析 | 查找某地点附近餐饮 | 距离阈值、空间索引 |
| 缓冲区分析 | 餐饮点 500 米缓冲区 | CRS 和距离单位 |
| 空间叠加 | 餐饮与行政区叠加 | 点面关系、空间谓词 |
| 统计汇总 | 统计各区餐饮数量 | 分组统计、结果排序 |
| 聚类分析 | 对餐饮 POI 做 DBSCAN | 参数选择、聚类输出 |
| 热点分析 | 识别餐饮热点区域 | 网格统计、热点解释 |
| 地图高亮 | 高亮第二多的行政区 | 结果与图层映射 |
| 用户纠正 | 不对，应高亮行政区 | 反馈识别、经验写回 |

### 6.2.3 实验结果输出

每组实验运行后输出到：

```text
experiments/experiment_outputs/{expX}/{run_name}/
```

输出内容包括：

- `summary.json`：实验总体指标。
- `results.csv`：逐任务结果。
- `figures/`：通过 `export_utils.py` 生成的图表。
- 导出 zip：包含 summary、results 和图表文件。

## 6.3 评价指标

| 指标 | 含义 |
|---|---|
| 任务完成率 | 系统是否完成用户目标 |
| 工具成功率 | GIS 工具调用是否成功 |
| 代码成功率 | 受控空间代码是否成功执行 |
| 准确率 | 结果是否符合预期 |
| 错误率 | 是否出现执行错误或明显错误答案 |
| 经验命中率 | 是否检索并使用相关经验 |
| 错误恢复率 | 错误后是否通过诊断恢复 |
| 偏好保持率 | 是否保持用户纠正后的偏好 |
| 上下文污染率 | 长上下文中无关信息干扰程度 |

## 6.4 实验一：基线对比实验

### 6.4.1 实验目的

比较 Base LLM 与 ACE 增强系统在同一 GIS 任务集上的表现，验证 ACE 是否能提升整体稳定性。

### 6.4.2 实验设计

设置两组系统：

- Base LLM：不使用完整 ACE 经验闭环。
- ACE：启用经验库、上下文记忆、Critic 错误诊断和 Evolution 经验演化。

实验流程：

1. 读取 `experiments/exp1/exp1_suite.json` 中的任务集。
2. Base LLM 和 ACE 分别执行同一批任务。
3. 记录每个任务的工具调用、代码执行、错误、回答和高亮结果。
4. 汇总任务完成率、工具成功率、代码成功率、准确率和错误率。
5. 将结果写入 `experiments/experiment_outputs/exp1/`。

### 6.4.3 结果分析写法

应从任务完成率、工具成功率、代码成功率、准确率和错误率分析 ACE 的提升，并结合典型任务说明经验库和诊断机制如何减少重复错误。

建议图表：

- 指标对比柱状图。
- 响应时间对比图。
- 能力雷达图。
- 任务类型热力图。

## 6.5 实验二：模块消融实验

### 6.5.1 实验目的

验证 CriticAgent、EvolutionAgent、Experience Library 和 Context Memory 等模块对系统性能的贡献。

### 6.5.2 实验设计

比较以下变体：

- Full ACE。
- w/o CriticAgent。
- w/o EvolutionAgent。
- w/o Experience Library。
- w/o Context Memory。

每个变体控制一个模块失效，其他执行流程保持一致。实验任务重点选择对模块敏感的场景，例如 CRS 风险、字段风险、用户纠正、跨轮引用和错误恢复任务。

### 6.5.3 结果分析写法

重点说明不同模块影响的任务类型不同：

- 经验库主要影响 CRS、字段、参数和输出策略复用。
- CriticAgent 主要影响错误定位和修复。
- EvolutionAgent 主要影响经验写回。
- Context Memory 主要影响用户偏好和跨轮引用。

## 6.6 实验三：记忆抗退化实验

### 6.6.1 实验目的

验证系统在多轮 GIS 对话中是否能保持历史 POI、用户偏好和空间分析经验。

### 6.6.2 实验设计

构造包含信息注入、干扰任务和延迟召回的多轮任务序列，比较 Base 与 ACE 的记忆召回和偏好保持能力。

任务序列可设计为：

```text
第 1 轮：记住某个 POI 或高亮偏好
第 2-8 轮：执行无关查询、统计和分析任务
第 9 轮：引用前面记录过的 POI 或偏好
第 10 轮：要求系统按之前偏好重新完成统计高亮任务
```

该实验重点验证 `ContextManager` 和 `ExperienceLibrary` 是否能把短期会话信息转成可复用结构化记忆。

### 6.6.3 结果分析写法

重点分析 ACE 如何把临时对话内容转化为结构化记忆，从而降低记忆退化。

## 6.7 实验四：长上下文扩展实验

### 6.7.1 实验目的

验证 ACE 压缩上下文在长任务序列中的鲁棒性。

### 6.7.2 实验设计

比较：

- Base full context。
- Base truncated context。
- ACE compressed context。

实验构造较长任务序列，并逐步增加历史上下文长度。Base full context 保留完整历史，Base truncated context 截断早期历史，ACE compressed context 保留结构化摘要、偏好和经验。对比三者在跨轮引用、复杂任务准确率和上下文污染方面的差异。

### 6.7.3 结果分析写法

应说明简单保留全部上下文可能引入污染，简单截断会丢失早期关键信息，而 ACE 通过结构化经验保留关键规则。

## 6.8 实验结果图表导出

项目通过 `experiments/export_utils.py` 将实验结果导出为论文可用图表。四组实验对应图表如下：

| 实验 | 建议图表 |
|---|---|
| exp1 | 指标对比柱状图、响应时间图、能力雷达图、任务热力图 |
| exp2 | 消融指标图、模块贡献图、错误分析图 |
| exp3 | 记忆衰减曲线、系统能力对比、上下文污染图 |
| exp4 | 长序列准确率曲线、跨轮引用图、上下文压缩与污染图 |

## 6.9 本章小结

本章通过四组实验验证 ACE 机制在地理空间分析中的作用，为系统有效性提供量化依据。

---

# 第 7 章 系统应用展示

## 7.1 系统运行与首页展示

展示系统启动方式和统一入口首页。说明 `/` 用于导航，`/gis` 用于主系统，`/experiment` 用于实验系统。

建议截图：

- 统一入口首页。
- GIS 主页面。
- 实验系统页面。

## 7.2 地图图层加载展示

展示餐饮、住宿服务和行政区图层的加载过程，说明系统按视野加载数据，而不是一次性加载所有要素。

## 7.3 自然语言 POI 查询展示

示例：

```text
搜索名称包含火锅的餐饮 POI
```

展示系统回答、Trace 和地图点高亮。

## 7.4 空间统计与行政区高亮展示

示例：

```text
哪个区的餐饮数量第二多，并高亮该行政区
```

展示系统如何选择行政区面图层进行统计和高亮。

## 7.5 缓冲区、聚类与热点分析展示

展示复杂空间分析任务，说明受控代码执行和封装工具如何协同。

## 7.6 用户纠正与经验复用展示

示例：

```text
不对，应该高亮行政区 shp，不是餐饮点
```

展示系统将纠正写入经验库，并在后续相似任务中复用。

## 7.7 实验结果可视化展示

展示实验页中的指标图表、历史结果和导出功能。

## 7.8 本章小结

本章从用户视角展示系统功能，证明系统不仅完成了算法和后端设计，也具备完整 WebGIS 应用形态。

---

# 第 8 章 总结与展望

## 8.1 工作总结

本文设计并实现了基于 ACE 机制的多 Agent 协同自进化地理分析系统。系统将自然语言交互、WebGIS 可视化、GIS 工具调用、受控空间代码执行、错误诊断、经验演化和实验验证结合起来，形成了可运行、可追踪、可扩展的 GeoAI 原型。

## 8.2 主要成果

1. 实现了自然语言驱动的 WebGIS 地理分析系统。
2. 构建了 Coordinator、SpatialAnalyst、CodeAgent、CriticAgent 和 EvolutionAgent 的多 Agent 协同架构。
3. 封装了 POI 查询、邻近分析、缓冲区、叠加、空间连接、聚类、热点和统计等 GIS 工具。
4. 实现了基于 CriticAgent 和 EvolutionAgent 的 ACE 经验闭环。
5. 支持多会话、多经验库、地图高亮和日志追踪。
6. 实现了四组实验系统、实验结果管理和图表导出功能。

## 8.3 创新点

### 8.3.1 面向地理空间任务的 ACE 经验闭环

本文将执行反馈、错误诊断和用户纠正转化为可复用经验，使地理智能体具备持续改进能力。

### 8.3.2 多 Agent 协同式 GIS 任务执行架构

本文将任务理解、空间分析、代码执行和错误诊断拆分为不同 Agent，提升复杂任务处理的可解释性。

### 8.3.3 WebGIS 与智能体闭环结合

系统不仅返回文本答案，还能把分析结果映射到地图图层和高亮要素上，使智能分析结果可视化。

### 8.3.4 实验系统与结果可视化

系统内置四组实验、历史结果管理和图表导出能力，增强毕业设计论文的实验支撑。

## 8.4 不足

当前系统仍有不足：

- 实验数据主要来自本地成都 POI 和行政区，数据规模有限。
- 与标准 GeoAnalystBench 等公开基准的直接对齐仍需加强。
- 目前主要支持矢量数据，对遥感影像、栅格数据和轨迹数据支持不足。
- 经验库缺少完善的冲突检测、版本回滚和人工审核机制。
- 部分代码中文字符串存在编码错乱，后续需要统一修复。

## 8.5 展望

后续可从以下方向改进：

1. 扩展更多城市和多类型空间数据。
2. 接入标准地理智能体基准任务。
3. 支持栅格、遥感影像和轨迹数据分析。
4. 增强经验库治理能力，包括冲突检测、质量评估和版本回滚。
5. 完善受控代码执行安全策略。
6. 将系统部署为可多人使用的 Web 服务。

---

# 附录建议

## 附录 A：核心 API 列表

整理 `/api/layers`、`/api/chat`、`/api/experiment/expX/*` 等接口。

## 附录 B：实验任务集样例

摘录 `exp1_suite.json` 到 `exp4_suite.json` 中的典型任务。

## 附录 C：经验库条目样例

展示 CRS、字段错误、空结果、用户偏好等经验条目。

## 附录 D：系统运行截图

包括首页、GIS 页面、问答结果、地图高亮、实验图表和导出结果。

## 附录 E：主要代码文件说明

| 文件 | 说明 |
|---|---|
| `main.py` | 系统启动入口 |
| `web_app/server.py` | HTTP 服务和 API 路由 |
| `ai_handler.py` | LLM、Agent、工具和经验库装配 |
| `agents/coordinator_agent.py` | 任务协调 |
| `agents/spatial_analyst_agent.py` | 空间分析调度 |
| `agents/code_agent.py` | 空间代码执行 |
| `agents/critic_agent.py` | 错误诊断智能体 |
| `agents/evolution_agent.py` | 经验演化进化智能体 |
| `core/context_manager.py` | 上下文和会话管理 |
| `core/experience_library.py` | 经验库 |
| `tools/` | GIS 工具集合 |
| `experiments/` | 实验系统 |
