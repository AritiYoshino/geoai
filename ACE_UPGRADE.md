# ACE 多智能体 WebGIS 原型说明

本项目从基础 GIS AI 助手升级为基于 ACE（Agentic Context Engineering）的多智能体协同自进化 WebGIS 原型。

## 目录结构

```text
geoai/
  agents/
    coordinator_agent.py        # 协调者：意图理解、计划生成、任务调度
    spatial_analyst_agent.py    # 空间分析者：调用工具或执行空间代码
    reflector_agent.py          # 反思者：质量评估、错误诊断、经验演化

  core/
    ace_core.py                 # 任务分类、轨迹记录、诊断与演化
    context_manager.py          # 会话上下文、POI 记忆、schema 汇总
    experience_bank_manager.py  # 多经验库管理
    experience_library.py       # 经验库检索、写入、更新
    session_store.py            # 会话持久化

  tools/
    search.py                   # POI 搜索
    query.py                    # 属性查询
    nearby.py                   # 邻近分析
    detail.py                   # 按 layer/index 获取 POI 详情
    code_executor.py            # 受控 GeoPandas/Pandas 空间代码执行

  web_app/
    server.py                   # 标准库 HTTP 后端，提供 Agent 与 GeoJSON API
    web_map_handler.py          # 浏览器 WebGIS 地图状态
    static/index.html           # WebGIS 主页面
    static/app.js               # MapLibre、聊天、会话、经验库交互逻辑
    static/styles.css           # 前端样式

  data/
    ace_experience_library.json # 默认动态经验库
    experience_banks.json       # 经验库索引
    experience_libraries/       # 用户新建经验库
    sessions.json               # 会话历史与上下文记忆

  ai_handler.py                 # 多智能体系统装配入口
  main_web.py                   # 浏览器 WebGIS 启动入口
  main.py                       # 保留的 Tkinter/matplotlib 旧入口
```

## 协同自进化流程

1. 用户在 Web 页面输入自然语言地理分析任务。
2. `CoordinatorAgent` 识别任务类型，生成执行计划。
3. `ContextManager` 提供会话上下文、最近 POI、图层 schema。
4. `ExperienceLibrary` 检索当前经验库中的相关经验。
5. `SpatialAnalystAgent` 调用固定 GIS 工具，或在工具不足时调用 `execute_spatial_code`。
6. 工具结果或代码 traceback 交给 `ReflectorAgent` 评估。
7. 反思者将错误、风险或用户反馈沉淀为经验，写入当前选用的经验库。
8. 用户可通过“正确 / 不正确 / 纠正”反馈结果，参与经验库演化。

## WebGIS 可视化层

浏览器端采用：

```text
MapLibre GL JS
  -> OSM 底图
  -> GeoJSON 图层
  -> 图层开关
  -> Popup 属性查看
  -> 查询结果高亮
```

Python 后端仍复用原有 Agent 与工具接口，高亮协议保持为：

```python
[(layer_idx, feature_idx), ...]
```

## 空间代码生成

当固定工具无法覆盖任务时，系统可使用 `tools/code_executor.py` 中的 `execute_spatial_code`。

可用对象：

```python
layers              # dict[str, GeoDataFrame]
layer_names
pd, gpd, np
Point
reproject_to_meters
```

约束：

- 禁止 `import`
- 禁止文件读写、系统命令、网络请求
- 禁止 `eval/exec/open`
- 最终结果必须赋值给 `RESULT`
- 可选 `HIGHLIGHTS=[("图层名", 要素索引), ...]` 用于地图高亮

该功能适合论文中的 Spatial Code Generation 实验，例如：

```text
统计每家酒店 300 米内餐饮数量并排序
计算各行政区酒店密度
找出餐饮数量最多的酒店周边区域
```

## 多经验库对比

Web 页面“经验库”页签支持：

- 选择已有经验库
- 新建空白经验库，用于 Zero-shot / 无经验条件对比
- 用默认模板新建经验库，用于基础 ACE 条件对比
- 复制当前经验库，用于保留某一阶段经验后继续演化

这可以用于论文实验：

```text
无经验库
初始经验库
用户反馈演化后的经验库
```

## 运行方式

确保 `.env` 中存在：

```text
DEEPSEEK_API_KEY=你的密钥
```

启动 WebGIS 原型：

```bash
python main_web.py
```

浏览器打开：

```text
http://127.0.0.1:8000
```

旧 Tkinter 版本仍可运行：

```bash
python main.py
```
