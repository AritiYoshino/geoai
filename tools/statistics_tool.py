from langchain_core.tools import tool

from .advanced_common import MAX_PREVIEW_ROWS, find_layer


def create_statistics_tool(handler):
    map_h = handler.map_handler

    @tool
    def summarize_layer_statistics(layer_name: str, group_by: str = "", numeric_field: str = "") -> str:
        """Summarize counts and numeric statistics for a layer."""
        _, gdf, real_name = find_layer(map_h, layer_name)
        if gdf is None:
            return f"错误：未找到图层 '{layer_name}'。"

        if group_by:
            if group_by not in gdf.columns:
                return f"错误：图层 '{real_name}' 不存在字段 '{group_by}'。"
            grouped = gdf.groupby(group_by).size().reset_index(name="count").sort_values("count", ascending=False)
            if numeric_field:
                if numeric_field not in gdf.columns:
                    return f"错误：图层 '{real_name}' 不存在数值字段 '{numeric_field}'。"
                stats = (
                    gdf.groupby(group_by)[numeric_field]
                    .agg(["count", "mean", "min", "max", "sum"])
                    .reset_index()
                )
                return f"已完成分组统计。\n{stats.head(MAX_PREVIEW_ROWS).to_string(index=False)}"
            return f"已完成分类计数统计。\n{grouped.head(MAX_PREVIEW_ROWS).to_string(index=False)}"

        numeric_cols = gdf.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_cols:
            return f"图层 '{real_name}' 没有可统计的数值字段。"
        stats = gdf[numeric_cols].describe().transpose().head(MAX_PREVIEW_ROWS)
        return f"已完成图层统计汇总。\n{stats.to_string()}"

    return summarize_layer_statistics
