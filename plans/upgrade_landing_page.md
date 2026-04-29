# 统一入口首页升级方案

## 目标

为项目添加一个美观、现代的统一入口首页，包含两个系统入口：
1. **地理智能系统** — 跳转至现有 GeoAI WebGIS 系统
2. **对比实验系统** — 跳转至一个占位空白页面（后续开发）

## 现有架构分析

- [`web_app/server.py`](../web_app/server.py) — Python HTTP 服务器，基于 `http.server`
  - 路由 `/` → [`index.html`](../web_app/static/index.html)（现有 GeoAI 系统）
  - 路由 `/static/` → 静态资源
  - 路由 `/api/*` → API 接口
- [`web_app/static/index.html`](../web_app/static/index.html) — 当前 GeoAI WebGIS 完整界面（地图+侧栏+Agent面板）
- [`web_app/static/styles.css`](../web_app/static/styles.css) — 现有样式
- [`web_app/static/app.js`](../web_app/static/app.js) — 现有前端 JS（地图初始化、聊天、图层等）

## 改造方案

### 路由规划

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 统一入口首页（新） | 两个入口卡片，浅色主题 |
| `/gis` | 地理智能系统（原首页） | 现有 GeoAI 系统 |
| `/experiment` | 对比实验系统（新） | 占位页面 |
| `/static/*` | 静态资源 | 保持不变 |

### 文件改动清单

#### 1. 重命名现有主页
- **操作**: 将 [`web_app/static/index.html`](../web_app/static/index.html) 复制为 [`web_app/static/gis.html`](../web_app/static/gis.html)
- **说明**: 保留原文件（index.html 将被新首页替换）

#### 2. 创建新首页 [`web_app/static/index.html`](../web_app/static/index.html) ✨
- **设计风格**: 现代、简洁、美观、**浅色主题**
- **布局**:
  - 全屏渐变背景（浅蓝/白色调）
  - 中央区域：大标题 + 副标题
  - 两个大号卡片式按钮，带有图标、标题、简短描述
  - 底部页脚
  - 悬停动效（scale + glow + 阴影增强）
- **配色**: 浅色渐变背景 + 玻璃态（glassmorphism）卡片 + 蓝色调强调色

#### 3. 创建占位页面 [`web_app/static/experiment.html`](../web_app/static/experiment.html)
- 简洁的占位页面，显示"对比实验系统"标题
- 包含返回首页的链接
- 风格与首页一致（浅色主题）

#### 4. 更新路由 [`web_app/server.py`](../web_app/server.py)
修改 `do_GET` 方法中的路由逻辑：

```python
if parsed.path == "/":
    self._send_static("index.html")  # 新首页
elif parsed.path == "/gis":
    self._send_static("gis.html")     # 地理智能系统
elif parsed.path == "/experiment":
    self._send_static("experiment.html")  # 对比实验系统（占位）
```

#### 5. 更新样式 [`web_app/static/styles.css`](../web_app/static/styles.css)
- 新增首页专用样式（浅色主题）
- 新增实验页样式
- 注意命名空间隔离，避免与现有 GIS 页面样式冲突

### 页面设计细节

#### 首页设计（浅色主题）

```
┌─────────────────────────────────────────┐
│  ████████████████████████████████████████│
│  ██        浅蓝渐变背景                ██│
│  ██         🌍 GeoAI 平台              ██│
│  ██     地理智能系统 · 对比实验         ██│
│  ██                                    ██│
│  ██   ┌─────────────────┐ ┌──────────┐ ██│
│  ██   │  🗺️              │ │  🔬      │ ██│
│  ██   │  地理智能系统     │ │ 对比实验 │ ██│
│  ██   │  多智能体地理分析  │ │ 系统     │ ██│
│  ██   │  助手             │ │ 建设中...│ ██│
│  ██   └─────────────────┘ └──────────┘ ██│
│  ██                                    ██│
│  ██       © 2026 GeoAI Platform        ██│
│  ██                                    ██│
│  ████████████████████████████████████████│
└─────────────────────────────────────────┘
```

#### 首页交互效果
- 卡片悬停时轻微上浮 + 阴影增强 + 边框发光
- 平滑过渡动画（transition: all 0.3s ease）
- 页面加载时卡片淡入（可选）

### 实施步骤

1. **备份** — 备份现有 [`index.html`](../web_app/static/index.html)
2. **复制** — 将 [`index.html`](../web_app/static/index.html) 复制为 [`gis.html`](../web_app/static/gis.html)
3. **创建新首页** — 编写新的 [`index.html`](../web_app/static/index.html)（浅色主题）
4. **创建实验页** — 编写 [`experiment.html`](../web_app/static/experiment.html)
5. **更新路由** — 修改 [`server.py`](../web_app/server.py) 路由
6. **更新样式** — 在 [`styles.css`](../web_app/static/styles.css) 中新增样式
7. **测试** — 启动服务验证所有页面可正常访问

### 不需要改动的内容
- [`app.js`](../web_app/static/app.js) — 地理智能系统的 JS 逻辑不受影响
- API 路由 — 所有 `/api/*` 路由保持不变
- 后端逻辑 — 无需修改任何 Python 业务逻辑
