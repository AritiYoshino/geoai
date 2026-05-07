# 统一入口首页升级记录

## 目标

为项目增加统一入口首页，把地理智能系统和对比实验系统作为两个清晰入口，避免所有功能都挤在同一个默认首页里。

## 当前路由

| 路径 | 页面 | 说明 |
|---|---|---|
| `/` | `web_app/static/index.html` | 统一入口首页 |
| `/gis` | `web_app/static/gis.html` | GeoAI WebGIS 主系统 |
| `/experiment` | `web_app/static/experiment.html` | 对比实验系统 |
| `/static/*` | 静态资源 | CSS、JS 等资源 |
| `/api/*` | 后端 API | 地图、问答、会话、经验库、实验接口 |

## 已完成内容

- 新增统一入口首页。
- 保留原 GIS 系统页面，并通过 `/gis` 访问。
- 实验系统页面通过 `/experiment` 访问。
- `server.py` 已支持 `/`、`/gis`、`/experiment` 三个页面路由。
- 实验页已经不是占位页，而是连接了四组实验的运行、结果和导出 API。

## 相关文件

- [`web_app/server.py`](web_app/server.py)
- [`web_app/static/index.html`](web_app/static/index.html)
- [`web_app/static/gis.html`](web_app/static/gis.html)
- [`web_app/static/experiment.html`](web_app/static/experiment.html)
- [`web_app/static/styles.css`](web_app/static/styles.css)
- [`web_app/static/experiment.css`](web_app/static/experiment.css)
- [`web_app/static/app.js`](web_app/static/app.js)
- [`web_app/static/experiment.js`](web_app/static/experiment.js)
- `web_app/static/js/gis/`：
  - [`api.js`](web_app/static/js/gis/api.js)
  - [`layers.js`](web_app/static/js/gis/layers.js)
  - [`map_view.js`](web_app/static/js/gis/map_view.js)
  - [`panels.js`](web_app/static/js/gis/panels.js)
- `web_app/static/js/experiment/`：
  - [`chart_setup.js`](web_app/static/js/experiment/chart_setup.js)
  - [`logic.js`](web_app/static/js/experiment/logic.js)
  - [`main.js`](web_app/static/js/experiment/main.js)
  - [`state.js`](web_app/static/js/experiment/state.js)

## 当前前端职责

### 首页

首页承担系统导航职责，展示：

- 地理智能系统入口。
- 对比实验系统入口。
- 项目名称和简要定位。

### GIS 页面

GIS 页面承担主要业务交互：

- MapLibre 地图。
- 图层列表和按需加载。
- 自然语言问答。
- ACE 面板和 Trace。
- 会话管理。
- 经验库管理。
- 地图高亮。

### 实验页面

实验页面承担实验验证：

- 四组实验运行入口。
- 任务集查看。
- 运行结果列表。
- 指标图表。
- 结果重命名、删除和导出。

## 后续优化建议

- 继续统一首页、GIS 页和实验页的视觉语言。
- 为实验页增加“论文证据”区域，直接展示 `/api/thesis/evidence` 的关键摘要。
- 修复代码和部分数据文件里的中文编码错乱，避免 UI 文案和反馈识别受影响。
- 增加移动端布局检查，确保首页入口和实验图表在小屏可读。
