import re


ERROR_RULES = [
    (
        "CRS_ERROR",
        re.compile(
            r"\bcrs\b|epsg|projection|projected|geographic crs|cannot transform|to_crs|reproject|坐标|投影",
            re.I,
        ),
        "任务中很可能混用了地理坐标系和投影坐标系，或在重投影前直接进行了距离计算。",
        "重新检查图层 CRS，先统一转换到米制投影坐标系，再做距离或缓冲区分析。",
        "在执行距离、缓冲区、面积等计算前，先使用 reproject_to_meters(...)。",
        True,
    ),
    (
        "DISTANCE_UNIT_ERROR",
        re.compile(r"distance unit|unit mismatch|meters?|kilometers?|缓冲|within .*km|within .*m|米|公里", re.I),
        "任务中很可能混淆了米和公里，或传入了与预期不一致的距离单位。",
        "先确认用户输入单位，内部统一换算为米，并在回答中明确说明单位假设。",
        "先把 km 统一换算为 m，再在同一米制坐标系中做所有距离比较。",
        True,
    ),
    (
        "FIELD_ERROR",
        re.compile(r"field|column|columns|keyerror|not in index|undefinedvariableerror|schema|字段|列名", re.I),
        "查询条件或生成代码引用了目标图层中不存在的字段名。",
        "先读取真实 schema，再仅使用实际存在的字段名重建筛选条件或代码。",
        "优先检查 gdf.columns，不要猜测字段别名或中英文映射。",
        True,
    ),
    (
        "EMPTY_RESULT",
        re.compile(r"not found|no results?|no matching|empty|0 results?|0 matching|未找到|为空|找不到|没有找到", re.I),
        "当前条件可能过严，目标图层选择有误，或者参考 POI 指代解析不正确。",
        "先放宽搜索范围，确认参考 POI 和目标图层，再逐步收紧过滤条件或距离限制。",
        "建议先用 search_poi 或更简单的查询定位，再执行精确筛选。",
        True,
    ),
    (
        "GEOMETRY_ERROR",
        re.compile(r"geometry|topology|invalid geometry|empty geometry|geom|几何", re.I),
        "空间处理中很可能遇到了无效几何、空几何或不受支持的几何对象。",
        "检查几何数据来源，跳过空要素，并在规范化几何处理后重试。",
        "在执行空间运算前，先检查 geometry.is_empty / geometry.is_valid。",
        True,
    ),
    (
        "TIMEOUT_OR_LOOP",
        re.compile(r"timeout|max iterations|loop|context too long|too large|stopped dispatch|超时|循环", re.I),
        "任务可能触发了过大的循环、过长的上下文，或重复重试后仍未收敛。",
        "缩小任务范围，限制结果规模，并拆成更小的步骤后再重试。",
        "优先返回摘要而不是完整结果集，并限制迭代重试次数。",
        True,
    ),
]


def diagnose_error(task_type, tool_name, tool_args, result, code=""):
    text = " ".join(
        str(part)
        for part in (task_type, tool_name, tool_args, result, code)
        if part not in (None, "")
    )
    lowered = text.lower()

    for error_type, pattern, reason, strategy, code_hint, experience_candidate in ERROR_RULES:
        if pattern.search(lowered):
            return {
                "error_type": error_type,
                "reason": reason,
                "strategy": strategy,
                "code_hint": code_hint,
                "experience_candidate": experience_candidate,
            }

    return {
        "error_type": "UNKNOWN_ERROR",
        "reason": "系统检测到了异常工具结果或代码结果，但暂时无法匹配到已知诊断模板。",
        "strategy": "保留 traceback 和任务上下文，并在缩小范围或补充更清晰约束后重试。",
        "code_hint": "记录失败输入，并简化下一轮执行路径。",
        "experience_candidate": False,
    }


class CriticAgent:
    """Lightweight structured diagnosis engine used by the agent layer."""

    def diagnose(self, task, task_type, tool_name, tool_args, result, code=""):
        return diagnose_error(
            task_type=task_type,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
            code=code,
        )
