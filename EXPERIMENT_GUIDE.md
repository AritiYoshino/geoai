# Experiment Guide（实验运行指南）

## 运行环境

- Python 3.10+
- `.env` 中配置 `DEEPSEEK_API_KEY`

## 数据准备

当前默认数据目录为：

- `data/geodata/住宿服务.geojson`
- `data/geodata/餐饮.geojson`
- `data/geodata/成都行政区.geojson`

系统启动时只读取图层元信息，不会把所有图层完整转换为 GeoJSON 发给前端。

## 启动方式

```bash
python main_web.py
```

启动后访问：

```text
http://127.0.0.1:8000
```

若 8000 被占用，系统会自动尝试 8001-8010。

---

## 实验系统说明

项目在 [`experiments/`](experiments/) 目录下实现了 4 组对比实验，用于评估 ACE 机制在不同维度上的效果。

### 实验结构

```text
experiments/
├─ __init__.py              # 统一导出所有实验入口
├─ runner.py                # 统一运行入口
├─ export_utils.py          # matplotlib 图表导出工具（中文标签、全可视化、美观样式）
├─ exp1/                    # 实验一：基线对比实验
│  ├─ __init__.py           # 导出 Exp1Runner, Exp1MetricsCollector
│  ├─ exp1_runner.py
│  ├─ exp1_analyzer.py
│  ├─ exp1_suite.json
│  └─ exp1_experience_library.json
├─ exp2/                    # 实验二：消融实验
│  ├─ __init__.py           # 导出 run_exp2
│  ├─ exp2_runner.py
│  ├─ exp2_suite.json
│  └─ exp2_experience_library.json
├─ exp3/                    # 实验三：记忆抗退化实验
│  ├─ __init__.py           # 导出 run_exp3
│  ├─ exp3_runner.py
│  ├─ exp3_suite.json
│  └─ exp3_experience_library.json
├─ exp4/                    # 实验四：长上下文扩展实验
│  ├─ __init__.py           # 导出 run_exp4
│  ├─ exp4_runner.py
│  ├─ exp4_suite.json
│  └─ exp4_experience_library.json
└─ experiment_outputs/      # 运行输出目录
   ├─ exp1/
   ├─ exp2/
   ├─ exp3/
   └─ exp4/
```

### 实验概览

| 实验 | 目录 | 说明 | 关键指标 |
|------|------|------|---------|
| 实验一 | [`exp1/`](experiments/exp1/) | Base LLM vs ACE 增强对比 | 任务完成率、工具成功率、代码成功率、准确率 |
| 实验二 | [`exp2/`](experiments/exp2/) | 模块消融分析（完整/无Critic/无Evolution/无经验库/无上下文记忆） | 准确率、工具成功率、多轮一致性、模块贡献度 |
| 实验三 | [`exp3/`](experiments/exp3/) | 长周期 GIS 对话中的记忆抗退化评估 | POI 召回率、偏好持久率、经验复用率、半衰期 |
| 实验四 | [`exp4/`](experiments/exp4/) | 长上下文扩展场景（完整/截断/压缩） | 长序列准确率、跨轮引用准确率、压缩率、污染率 |

### 运行实验

**方式一：直接运行各实验入口**

```python
from experiments.exp1.exp1_runner import Exp1Runner
from experiments.exp1.exp1_analyzer import Exp1MetricsCollector

runner = Exp1Runner(ai_handler, map_handler, mode="ace")
results = runner.run()
```

**方式二：使用统一运行器**

```bash
python -c "
from experiments.runner import run_exp1
run_exp1(mode='both')
"
```

### 导出图表

每个实验运行后会在输出目录下生成 `summary.json`，可通过 [`export_utils.py`](experiments/export_utils.py) 导出可视化图片：

```python
from experiments.export_utils import ensure_matplotlib_exports

ensure_matplotlib_exports("experiments/experiment_outputs/exp1/exp1_both_20260429-132217")
```

#### 导出图片清单

| 实验 | 图片文件 | 对应前端可视化 | 说明 |
|------|---------|---------------|------|
| exp1 | `exp1_metric_comparison.png` | renderBarChart | 指标对比柱状图（带提升百分比标注） |
| exp1 | `exp1_response_time.png` | renderTimeChart | 各任务响应时间对比 |
| exp1 | `exp1_radar.png` | renderRadarChart | 六维能力雷达图 |
| exp1 | `exp1_heatmap.png` | renderHeatmap | 任务级通过矩阵热力图 |
| exp2 | `exp2_ablation_metrics.png` | renderExp2MetricsChart | 各变体消融指标分组柱状图 |
| exp2 | `exp2_module_contribution.png` | renderExp2ContributionChart | 模块贡献度横向柱状图 |
| exp2 | `exp2_error_analysis.png` | renderExp2ErrorChart | 错误恢复率 + 传播深度双轴图 |
| exp3 | `exp3_memory_decay.png` | renderExp3DecayChart | 记忆衰减曲线 |
| exp3 | `exp3_system_metrics.png` | renderExp3MemoryChart | 系统能力指标分组柱状图 |
| exp3 | `exp3_pollution.png` | renderExp3PollutionChart | 上下文污染与压缩分析 |
| exp4 | `exp4_accuracy_curve.png` | renderExp4AccuracyChart | 长上下文准确率变化趋势 |
| exp4 | `exp4_system_metrics.png` | — | 系统能力指标分组柱状图 |
| exp4 | `exp4_reference.png` | renderExp4ReferenceChart | 跨轮引用分析柱状图 |
| exp4 | `exp4_compression.png` | renderExp4CompressionChart | 上下文压缩与污染分析 |

#### 导出特点

1. **中文标签**：所有标题、坐标轴、图例、数值标注均为中文，自动检测系统字体（SimHei → Microsoft YaHei → DengXian）
2. **全可视化覆盖**：补全了所有前端 Chart.js 可视化对应的 matplotlib 版本
3. **美观样式**：统一调色板、数值标注、网格虚线、移除冗余边框、高 DPI 输出

#### 打包导出

```python
from experiments.export_utils import build_export_zip

zip_path = build_export_zip("experiments/experiment_outputs/exp1/exp1_both_20260429-132217")
# 生成 exports/exp1_both_20260429-132217_export.zip
# 包含: summary.json, results.csv, figures/*.png, export_manifest.json
```

---

## 前端实验页面

实验系统附带一个独立的前端页面 [`web_app/static/experiment.html`](web_app/static/experiment.html)，提供：

- 各实验数据可视化（Chart.js 图表）
- 运行历史管理与对比
- 导出按钮（触发后端 `build_export_zip`）

访问路径：

```text
http://127.0.0.1:8000/experiment
```

## 日志文件

运行后可查看：

- `logs/task_log.jsonl`：任务输入、有效任务、回答摘要
- `logs/code_log.jsonl`：代码执行与重试过程
- `logs/evolution_log.jsonl`：经验新增、更新、跳过
- `logs/error_log.jsonl`：运行异常

## 建议实验案例

1. 说明型问题  
   例：`聚类怎么用`

2. 区域统计  
   例：`哪个区的餐馆数量第二多，并高亮`

3. 用户纠正  
   例：`不对，应该高亮的是行政区 shp，不是点 shp`

4. 偏好延续  
   再次提问：`哪个区的餐馆数量第二多，并高亮`

观察是否只高亮行政区面图层。
