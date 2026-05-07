# Experiment Guide

本文档说明 GeoAI ACE WebGIS 的实验系统、运行方式、输出文件和论文证据整理入口。

## 环境准备

项目依赖 Python 3.10+。安装依赖：

```bash
pip install -r requirements.txt
```

在 `.env` 中配置：

```text
DEEPSEEK_API_KEY=你的密钥
```

启动服务：

```bash
python main.py
```

访问实验页：

```text
http://127.0.0.1:8000/experiment
```

## 实验目录

```text
experiments/
├── __init__.py
├── runner.py               # 统一实验入口
├── export_utils.py         # 图表导出与 zip 打包
├── thesis_evidence.py      # 论文证据汇总
├── exp1/                   # 实验一：基线对比
│   ├── exp1_runner.py
│   ├── exp1_analyzer.py
│   ├── exp1_suite.json
│   └── exp1_experience_library.json
├── exp2/                   # 实验二：模块消融
│   ├── exp2_runner.py
│   ├── exp2_suite.json
│   └── exp2_experience_library.json
├── exp3/                   # 实验三：记忆抗退化
│   ├── exp3_runner.py
│   ├── exp3_suite.json
│   └── exp3_experience_library.json
├── exp4/                   # 实验四：长上下文扩展
│   ├── exp4_runner.py
│   ├── exp4_suite.json
│   └── exp4_experience_library.json
└── experiment_outputs/     # 实验运行输出
    ├── exp1/
    ├── exp2/
    ├── exp3/
    └── exp4/
```

## 四组实验

| 实验 | 目标 | 主要指标 |
|---|---|---|
| 实验一：基线对比 | 比较 Base LLM 与 ACE 增强系统 | 任务完成率、工具成功率、代码成功率、准确率、错误率 |
| 实验二：模块消融 | 比较 Full ACE、无 Critic、无 Evolution、无经验库、无上下文记忆 | 准确率、工具成功率、多轮一致性、模块贡献度 |
| 实验三：记忆抗退化 | 测试多轮 GIS 对话中的 POI、偏好和经验保持 | 记忆召回率、POI 召回率、偏好保持率、经验复用率、污染率 |
| 实验四：长上下文 | 比较 full context、truncated context、ACE compressed | 长序列准确率、跨轮引用准确率、压缩率、上下文污染率 |

## 前端运行

实验页提供：

- 四组实验的运行入口。
- 实验任务集查看。
- 历史运行结果管理。
- Chart.js 可视化。
- 运行结果重命名和删除。
- zip 导出。

相关 API：

```text
GET  /api/experiment/expX/data
GET  /api/experiment/expX/tasks
GET  /api/experiment/expX/results
GET  /api/experiment/expX/export
POST /api/experiment/expX/run
POST /api/experiment/expX/rename
POST /api/experiment/expX/delete
```

其中 `expX` 可替换为 `exp1`、`exp2`、`exp3` 或 `exp4`。

## Python 运行

实验一可通过统一 runner 调用：

```python
from experiments.runner import run_exp1

run_exp1(mode="both", use_preset=True)
```

实验二到实验四可直接调用对应 runner：

```python
from experiments.exp2.exp2_runner import run_exp2
from experiments.exp3.exp3_runner import run_exp3
from experiments.exp4.exp4_runner import run_exp4

run_exp2()
run_exp3()
run_exp4()
```

## 输出文件

每次运行会写入：

```text
experiments/experiment_outputs/{expX}/{run_name}/
├── summary.json
├── results.csv
└── figures/          # 导出图表时生成
```

`summary.json` 保存聚合指标，`results.csv` 保存逐任务结果，`figures/` 保存论文可用图表。

## 图表导出

```python
from experiments.export_utils import ensure_matplotlib_exports, build_export_zip

run_dir = "experiments/experiment_outputs/exp1/exp1_both_20260429-132217"

ensure_matplotlib_exports(run_dir)
zip_path = build_export_zip(run_dir)
```

导出图表包括：

| 实验 | 图表 |
|---|---|
| exp1 | 指标对比、响应时间、能力雷达图、任务热力图 |
| exp2 | 消融指标、模块贡献、错误分析 |
| exp3 | 记忆衰减、系统能力、上下文污染 |
| exp4 | 准确率曲线、系统能力、跨轮引用、压缩与污染 |

## 论文证据接口

后端提供：

```text
GET /api/thesis/evidence
```

该接口会汇总：

- 最近一次四组实验结果。
- GeoAnalystBench 风格任务类型覆盖情况。
- Base 与 ACE 指标对比。
- 经验库分类、来源和质量统计。
- 代码演化或错误恢复样例。
- 消融、记忆和长上下文实验摘要。
- 当前仍缺失的论文证据项。

## 建议实验用例

可以用以下任务验证系统能力：

```text
搜索名称包含火锅的餐饮 POI
哪个区的餐饮数量第二多，并高亮该行政区
在餐饮点周围做 500 米缓冲区分析
对餐饮 POI 做 DBSCAN 聚类
不对，应该高亮行政区 shp，不是餐饮点
再次问：哪个区的餐饮数量第二多，并高亮
```

重点观察：

- 是否正确选择图层。
- 是否处理 CRS 和距离单位。
- 是否把用户纠正写入经验库。
- 后续任务是否复用偏好。
- 地图高亮是否符合任务语义。
