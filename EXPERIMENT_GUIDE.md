# Experiment Guide

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

## 前端加载策略

- 首屏只请求 `/api/layers` 获取图层元信息
- 用户勾选图层时，再请求 `/api/layer_data`
- 接口支持 `bbox`，只返回当前视野范围内要素
- 地图移动结束后，前端使用 debounce 自动刷新已勾选图层
- 大图层默认提示用户放大后再加载

## 关键实验入口

可以重点验证以下能力：

1. WebGIS 问答
2. 工具调用与高亮联动
3. 代码执行与修复
4. Reflector/Critic/Evolution 自进化闭环
5. 用户反馈写入经验库
6. 会话偏好在后续轮次中的持续生效

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
