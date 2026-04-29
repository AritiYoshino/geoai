# System Architecture

## 总体结构

项目由五层组成：

1. `web_app/`
   - WebGIS 前端（MapLibre GL JS）
   - HTTP 服务
   - 实验前端页面（Chart.js 可视化）
   - 图层按需加载与地图高亮

2. `agents/`
   - `CoordinatorAgent`
   - `SpatialAnalystAgent`
   - `CodeAgent`
   - `ReflectorAgent`

3. `core/`
   - 上下文管理
   - 经验库
   - Critic / Evolution
   - 会话与日志

4. `tools/`
   - 查询
   - 邻近分析
   - 缓冲区、叠加、空间连接
   - 聚类、热点、统计、导出
   - 受控空间代码执行

5. `experiments/`（实验系统）
   - 4 组对比实验（基线对比、消融分析、记忆退化、长上下文）
   - 统一运行器 [`runner.py`](experiments/runner.py)
   - matplotlib 图表导出工具 [`export_utils.py`](experiments/export_utils.py)

## 主要调用链

### 主系统调用链

1. 前端通过 `/api/chat` 发送用户问题
2. `AIHandler` 组织模型、经验库、上下文和工具
3. `CoordinatorAgent` 识别任务类型并规划执行
4. `SpatialAnalystAgent` 选择工具或触发 `CodeAgent`
5. `ReflectorAgent` 在异常或失败时触发诊断与演化
6. 经验库更新后，新的高置信经验参与后续任务

### 实验系统调用链

1. 各实验 runner（`exp1_runner.py` ~ `exp4_runner.py`）执行任务套件
2. 运行输出写入 `experiment_outputs/{expX}/{run_name}/`
   - `summary.json` — 完整指标汇总
   - `results.csv` — 逐任务明细
3. [`export_utils.py`](experiments/export_utils.py) 读取 `summary.json` 并导出
   - 自动匹配实验类型（exp1–exp4）
   - 生成 3–4 张 matplotlib 图片（中文标签）
   - 可选打包为 zip（含 summary.json + results.csv + 图片）

## 地图数据链路

### 启动阶段

- 后端从 `data/geodata/*.geojson` 读取图层元信息
- 只保留：
  - 名称
  - 字段
  - geometry type
  - feature count
  - bbox

### 交互阶段

- 前端调用 `/api/layer_data`
- 请求参数支持：
  - `layer_name`
  - `bbox`
  - `zoom`

- 后端按需加载 GeoJSON 为 GeoDataFrame，并仅返回当前视野内要素

## ACE 自进化链路

### A: Analyze

- `CoordinatorAgent`
- `ContextManager`

### C: Critic

- `ReflectorAgent` 内部调用 `core/critic.py`

### E: Evolve

- `ReflectorAgent` 内部调用 `core/evolution.py`
- 经验写入 `ExperienceLibrary`

## 可追溯日志

系统记录以下日志：

- `task_log.jsonl`
- `code_log.jsonl`
- `evolution_log.jsonl`
- `error_log.jsonl`

这些日志分别覆盖：

- 用户任务与回答
- 代码执行过程
- 经验演化记录
- 运行异常
