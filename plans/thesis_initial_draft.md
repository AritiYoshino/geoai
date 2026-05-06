# 基于 ACE 机制的多 Agent 协同自进化地理分析系统研究

## 摘要

随着大语言模型在自然语言理解、代码生成和工具调用方面能力的提升，地理信息系统正在从传统专业软件操作模式转向自然语言驱动的智能分析模式。然而，在复杂地理空间分析任务中，现有大模型智能体仍存在空间规则保持不稳定、代码生成逻辑脆弱、错误经验难以复用等问题。缓冲区分析、空间叠加、邻近分析和聚类分析等任务通常依赖坐标参考系、字段名称、几何关系、距离单位和参数尺度等约束，一旦模型忽略这些约束，就容易产生重复错误。

针对上述问题，本文引入 ACE（Agentic Context Engineering）机制，设计并实现一个面向地理空间分析任务的多 Agent 协同自进化系统。系统以动态经验库为核心，由任务协调智能体、空间分析智能体、代码执行智能体、反思诊断智能体和经验演化模块共同组成，形成“任务理解、经验检索、工具调用或空间代码执行、错误诊断、经验写回、后续复用”的闭环流程。系统基于 Python、GeoPandas、WebGIS 前端和大语言模型接口实现，支持 POI 查询、邻近分析、缓冲区分析、叠加统计、DBSCAN 聚类、热点分析、统计汇总、结果导出和地图高亮。

本文结合本地成都 POI 与行政区数据构建实验任务集，设计基线对比实验、模块消融实验、记忆抗退化实验和长上下文扩展实验。实验结果用于验证 ACE 机制对任务准确率、工具成功率、经验复用率、多轮一致性和长上下文鲁棒性的影响。研究表明，ACE 机制能够推动地理智能体从一次性空间代码生成工具，转向具备持续经验积累与自我优化能力的协同式地理分析系统。

**关键词：** Agentic Context Engineering；多 Agent 协同；闭环自进化；地理空间代码生成；经验库；GeoPandas；WebGIS

## Abstract

With the development of large language models in natural language understanding, code generation, and tool invocation, geographic information systems are shifting from expert-oriented software operation to natural-language-driven intelligent analysis. However, current LLM-based geospatial agents still suffer from unstable spatial rule retention, fragile code generation, and limited reuse of execution experience. Spatial tasks such as buffer analysis, overlay statistics, proximity analysis, and clustering require constraints related to coordinate reference systems, field names, geometry relationships, distance units, and parameter scales. Ignoring these constraints often leads to repeated errors.

To address these issues, this thesis introduces the Agentic Context Engineering (ACE) mechanism and designs a multi-agent collaborative self-evolving system for geospatial analysis. The system is centered on a dynamic experience library and consists of a coordinator agent, a spatial analyst agent, a code execution agent, a reflection and diagnosis agent, and an evolution module. It forms a closed loop of task understanding, experience retrieval, tool invocation or spatial code execution, error diagnosis, experience update, and later reuse. The prototype is implemented with Python, GeoPandas, a WebGIS frontend, and large language model APIs. It supports POI query, proximity analysis, buffer analysis, overlay statistics, DBSCAN clustering, hotspot analysis, statistical summarization, result export, and map highlighting.

Experiments are conducted on local Chengdu POI and administrative district data. Four groups of experiments are designed, including baseline comparison, module ablation, memory degradation resistance, and long-context extension. The experimental results are used to evaluate the influence of ACE on task accuracy, tool success rate, experience reuse, multi-turn consistency, and long-context robustness. The study indicates that ACE can transform geospatial agents from one-time spatial code generation tools into collaborative analysis systems with continuous experience accumulation and self-optimization capability.

**Keywords:** Agentic Context Engineering; Multi-Agent Collaboration; Closed-loop Self-evolution; Geospatial Code Generation; Experience Library; GeoPandas; WebGIS

---

# 第 1 章 绪论

## 1.1 研究背景

地理信息系统长期依赖专业软件、脚本编程和人工参数配置完成空间数据处理、分析和制图。随着大语言模型的发展，用户可以通过自然语言描述空间任务，由模型理解需求、选择工具、生成代码并调用 GIS 能力完成分析。这为降低 GIS 使用门槛、提升空间分析自动化水平提供了新的技术路径。

但地理空间任务不同于一般文本问答。空间分析需要处理图层类型、字段名称、坐标参考系、几何关系、距离单位、空间谓词和结果规模等约束。大模型虽然具备较强的代码生成能力，但在连续任务中容易出现上下文遗忘、空间规则遗漏和重复犯错等问题。

因此，如何让地理智能体在执行任务过程中持续积累经验，并将错误转化为后续可复用的知识，是本文关注的核心问题。

## 1.2 研究意义

理论上，本文将 ACE 机制引入地理空间分析任务，探索动态上下文、经验库和闭环自进化机制在 GIS 智能体中的适用性。相比静态 prompt 或普通 RAG 方法，ACE 更强调从执行反馈中提炼经验，适合处理空间任务中的连续错误修复与知识积累。

技术上，本文构建多 Agent 协同框架，将任务协调、空间分析、代码执行、错误诊断和经验演化拆分为不同角色，提高复杂 GIS 任务执行链条的可解释性和可维护性。

应用上，本文实现 WebGIS 原型系统，使用户能够通过自然语言完成 POI 查询、缓冲区分析、空间叠加、聚类分析、统计汇总和地图高亮，降低普通用户使用 GIS 分析能力的门槛。

## 1.3 研究内容

本文主要研究内容包括：

1. 面向地理空间任务的 ACE 动态经验库设计。
2. 多 Agent 协同地理分析框架构建。
3. GIS 工具调用与受控空间代码执行机制。
4. “执行、诊断、演化、复用”的闭环自进化流程。
5. WebGIS 原型系统实现。
6. 基线对比、模块消融、记忆抗退化和长上下文扩展实验设计。

## 1.4 技术路线

系统技术路线如下：

1. 用户输入自然语言地理任务。
2. `CoordinatorAgent` 识别任务类型并组织上下文。
3. `ExperienceLibrary` 根据任务类型检索相关经验。
4. `SpatialAnalystAgent` 选择 GIS 工具或触发 `CodeAgent`。
5. 工具或代码执行后返回结果、异常和地图高亮信息。
6. `ReflectorAgent` 对错误、空结果或用户纠正进行反思。
7. `Critic` 生成结构化诊断。
8. `Evolution` 将诊断沉淀为经验。
9. 后续相似任务复用高置信经验。

---

# 第 2 章 理论基础与关键技术

## 2.1 ACE 机制

ACE 的核心思想是将上下文视为可演化的策略手册，而不是一次性静态提示。传统 prompt 工程通常在任务开始前提供固定规则，任务结束后错误信息不会自动沉淀。ACE 则强调在执行过程中记录反馈、诊断错误、整理经验，并通过增量更新方式持续改进上下文。

在本文系统中，ACE 主要体现在三个环节：

- 经验检索：任务执行前从经验库中寻找相关 GIS 规则。
- 错误诊断：任务执行后分析工具反馈、代码异常、空结果和用户纠正。
- 经验演化：将诊断结果转化为结构化经验并写回经验库。

## 2.2 多 Agent 协同

本文没有将所有能力集中到单个智能体，而是采用多 Agent 分工协同：

- `CoordinatorAgent` 负责全局调度和任务理解。
- `SpatialAnalystAgent` 负责 GIS 工具选择与调用。
- `CodeAgent` 负责空间分析代码生成和执行。
- `ReflectorAgent` 负责反思入口。
- `Critic` 负责错误诊断。
- `Evolution` 负责经验演化。

这种结构能够把复杂空间任务拆成意图理解、方法选择、执行、诊断和经验写回等步骤，降低长链路任务中的遗忘和混乱。

## 2.3 地理空间代码生成

地理空间代码生成是本文系统的重要能力。系统需要根据用户问题生成或调用基于 GeoPandas 的空间分析流程，例如读取图层、筛选字段、转换投影、构建缓冲区、执行空间连接、统计行政区内 POI 数量、进行 DBSCAN 聚类等。

与普通代码生成相比，地理空间代码生成更依赖空间数据语义和 GIS 规则，因此更需要经验库约束。本文关注的风险包括字段名错误、图层选择错误、CRS 不匹配、距离单位错误、空间连接方向错误、空结果未处理和输出规模过大等。

## 2.4 闭环自进化

闭环自进化是本文的核心创新之一。系统不是只回答当前问题，而是将任务执行轨迹、错误反馈和用户纠正转化为后续可用经验。例如，当系统发现缓冲区分析需要先转换到米制投影时，该规则会写入经验库；当用户纠正“统计类任务应高亮行政区面图层而不是餐饮点图层”时，该偏好也会进入上下文记忆和经验库。

---

# 第 3 章 系统设计

## 3.1 总体架构

系统由七个部分组成：

1. Web 前端：统一首页、GIS 页面、实验页面。
2. HTTP 服务：页面路由和 API 分发。
3. AIHandler：模型、Agent、工具、上下文和经验库装配。
4. 多 Agent 层：任务协调、空间分析、代码执行和反思。
5. ACE 核心层：上下文、经验库、诊断、演化、会话和日志。
6. GIS 工具层：查询、邻近、缓冲区、叠加、聚类、热点、统计和导出。
7. 实验层：四组对比实验和论文证据接口。

## 3.2 数据层

系统默认使用成都本地 GeoJSON 数据：

- `data/geodata/餐饮.geojson`
- `data/geodata/住宿服务.geojson`
- `data/geodata/成都行政区.geojson`

同时保留 Shapefile 原始数据：

- `geodata/餐饮_61102.*`
- `geodata/住宿服务_6474.*`
- `geodata/成都行政区__加高新天府东区.*`

## 3.3 前端设计

前端包含三个入口：

- `/`：统一入口首页。
- `/gis`：地理智能系统。
- `/experiment`：对比实验系统。

GIS 页面负责地图展示、图层加载、自然语言问答、ACE 面板、Trace、会话和经验库管理。实验页面负责四组实验的运行、结果查看、图表展示、重命名、删除和导出。

## 3.4 API 设计

核心 API 包括：

- `/api/layers`
- `/api/layer_data`
- `/api/chat`
- `/api/highlights`
- `/api/trace`
- `/api/ace-panel`
- `/api/experience`
- `/api/sessions`
- `/api/experience-banks`
- `/api/experiment/expX/*`
- `/api/thesis/evidence`

## 3.5 日志设计

系统通过 JSONL 文件记录关键过程：

- `task_log.jsonl`：任务记录。
- `code_log.jsonl`：代码执行记录。
- `evolution_log.jsonl`：经验演化记录。
- `error_log.jsonl`：异常记录。

---

# 第 4 章 系统实现

## 4.1 启动流程

系统从 `main.py` 启动，调用 `web_app.server.run()`。`WebGISAppState` 读取 `.env` 中的 `DEEPSEEK_API_KEY`，初始化 `BrowserMapHandler`、加载 GeoJSON 图层元信息，并创建 `AIHandler`。

## 4.2 地图按需加载

系统启动时只读取图层元信息，不把全部 GeoJSON 发送到前端。前端在用户勾选图层后，带上当前地图 `bbox` 和 `zoom` 调用 `/api/layer_data`，后端只返回当前视野范围内要素。

## 4.3 任务处理实现

用户发送消息后，`AIHandler.process_message()` 会先解析内联反馈和偏好，再将有效任务交给 `CoordinatorAgent`。最终返回自然语言回答、Trace、ACE 面板、经验库摘要、会话状态和高亮结果。

## 4.4 经验库实现

经验库支持：

- 按任务类型检索。
- 相似经验去重。
- 置信度过滤。
- 成功和失败计数。
- 多经验库切换。
- 用户反馈经验写入。

## 4.5 实验实现

实验系统位于 `experiments/`，四组实验均有独立 runner 和任务集。实验输出保存到 `experiments/experiment_outputs/`，并可通过 `export_utils.py` 生成论文图表和 zip 包。

---

# 第 5 章 实验设计与结果分析

## 5.1 实验一：基线对比

实验一比较 Base LLM 与 ACE 增强系统在同一任务集上的表现，重点指标包括任务完成率、工具成功率、代码成功率、准确率和错误率。该实验用于回答“ACE 是否比普通大模型工具调用更稳定”。

## 5.2 实验二：模块消融

实验二比较 Full ACE、无 Critic、无 Evolution、无经验库、无上下文记忆等变体，用于分析各模块对系统性能的贡献。该实验重点说明 ACE 的提升来自多个上下文工程模块的协同，而不是单纯增加提示词长度。

## 5.3 实验三：记忆抗退化

实验三构造多轮 GIS 对话，测试系统在较长间隔后是否仍能召回历史 POI、用户偏好和空间分析经验。该实验用于验证结构化经验库和上下文管理对记忆退化的缓解作用。

## 5.4 实验四：长上下文扩展

实验四比较完整上下文、截断上下文和 ACE 压缩上下文，分析长任务序列下的准确率、跨轮引用、上下文污染和压缩效果。该实验用于验证 ACE 在长上下文场景下的鲁棒性。

## 5.5 论文证据整理

系统提供 `/api/thesis/evidence` 接口汇总实验结果、经验库统计、任务覆盖情况、代码演化样例和缺失项。论文写作时可基于该接口生成表格和图表。

---

# 第 6 章 系统应用展示

## 6.1 自然语言查询

用户可以输入：

```text
搜索名称包含火锅的餐饮 POI
查找武侯区内的住宿服务
```

系统会识别查询任务，选择对应 POI 搜索或属性查询工具，并在地图上高亮结果。

## 6.2 空间分析

用户可以输入：

```text
哪个区的餐饮数量第二多，并高亮该行政区
在餐饮点周围做 500 米缓冲区分析
对餐饮 POI 做 DBSCAN 聚类
```

系统会根据任务选择统计、缓冲区、聚类或受控代码执行路径。

## 6.3 用户纠正与经验更新

用户可以直接纠正：

```text
不对，应该高亮行政区 shp，不是餐饮点
以后统计类结果只高亮行政区面图层
```

系统会把纠正写入当前上下文和经验库，后续相似任务会优先复用该偏好。

## 6.4 实验可视化

实验页展示四组实验的结果图表，可用于论文中的系统验证部分，包括指标对比、模块贡献、记忆衰减、上下文污染和压缩效果。

---

# 第 7 章 总结与展望

## 7.1 研究总结

本文围绕地理空间代码生成中的规则遗漏、错误重复和经验缺失问题，引入 ACE 机制，设计并实现多 Agent 协同自进化地理分析系统。系统通过动态经验库、多 Agent 分工、GIS 工具调用、受控代码执行、错误诊断和经验写回，形成闭环自进化流程。

## 7.2 创新点

1. 将 ACE 动态上下文机制引入地理空间分析任务。
2. 构建任务协调、空间分析、代码执行、反思诊断和经验演化分工协同的多 Agent 架构。
3. 实现从错误和用户反馈到经验库更新的闭环自进化流程。
4. 构建 WebGIS 原型和四组实验系统，用于验证 ACE 机制效果。

## 7.3 不足与展望

当前系统仍存在不足：

- 实验数据主要基于本地成都数据，规模和类型仍有限。
- 与标准 GeoAnalystBench 等基准的直接对齐仍需增强。
- 目前主要处理矢量 POI 和行政区数据，对遥感影像、栅格、轨迹和多模态地理数据支持不足。
- 经验库治理仍需完善，包括冲突检测、版本回滚、质量审核和安全审计。
- 代码中部分中文字符串存在编码错乱，需要后续集中修复。

未来可继续扩展标准基准任务、增强多模态空间数据支持、完善经验库治理机制，并进一步提高系统在真实复杂 GIS 工作流中的稳定性。
