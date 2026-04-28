import geopandas as gpd
from langchain_core.tools import tool

from .advanced_common import find_layer, highlight_indices, preview_frame, store_generated_result


def create_overlay_layers_tool(handler):
    map_h = handler.map_handler

    @tool
    def overlay_layers(input_layer: str, overlay_layer: str, how: str = "intersection") -> str:
        """Run overlay analysis between two layers. how supports intersection/union/identity/symmetric_difference/difference."""
        _, left, left_name = find_layer(map_h, input_layer)
        _, right, right_name = find_layer(map_h, overlay_layer)
        if left is None:
            return f"错误：未找到图层 '{input_layer}'。"
        if right is None:
            return f"错误：未找到图层 '{overlay_layer}'。"

        if left.crs != right.crs:
            right = right.to_crs(left.crs or "EPSG:4326")
        result = gpd.overlay(left, right, how=how)
        result_name = f"{left_name}_{how}_{right_name}"
        store_generated_result(handler, result_name, result)
        return (
            f"已完成空间叠加分析：{left_name} {how} {right_name}。\n"
            f"结果记录数: {len(result)}\n"
            f"预览:\n{preview_frame(result)}"
        )

    return overlay_layers


def create_spatial_join_tool(handler):
    map_h = handler.map_handler

    @tool
    def spatial_join_layers(
        target_layer: str,
        join_layer: str,
        predicate: str = "intersects",
        how: str = "inner",
    ) -> str:
        """Run spatial join between two layers."""
        target_idx, target, target_name = find_layer(map_h, target_layer)
        _, join_gdf, join_name = find_layer(map_h, join_layer)
        if target is None:
            return f"错误：未找到图层 '{target_layer}'。"
        if join_gdf is None:
            return f"错误：未找到图层 '{join_layer}'。"

        if target.crs != join_gdf.crs:
            join_gdf = join_gdf.to_crs(target.crs or "EPSG:4326")
        result = gpd.sjoin(target, join_gdf, how=how, predicate=predicate)
        result_name = f"{target_name}_sjoin_{join_name}"
        store_generated_result(handler, result_name, result)
        highlight_indices(handler, target_idx, result.index.unique().tolist())
        return (
            f"已完成空间连接分析：{target_name} 与 {join_name}，谓词 {predicate}。\n"
            f"结果记录数: {len(result)}\n"
            f"预览:\n{preview_frame(result)}"
        )

    return spatial_join_layers
