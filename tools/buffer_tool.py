import geopandas as gpd
from langchain_core.tools import tool

from .advanced_common import (
    distance_to_meters,
    find_layer,
    highlight_indices,
    preview_frame,
    store_generated_result,
)
from .utils_geo import reproject_to_meters


def create_buffer_analysis_tool(handler):
    map_h = handler.map_handler

    @tool
    def buffer_analysis(layer_name: str, distance: float, unit: str = "m", dissolve: bool = False) -> str:
        """Create buffers around one layer and store the derived result for later export."""
        layer_idx, gdf, real_name = find_layer(map_h, layer_name)
        if gdf is None:
            return f"错误：未找到图层 '{layer_name}'。"

        distance_m = distance_to_meters(distance, unit)
        projected = reproject_to_meters(gdf.copy())
        buffered = projected.copy()
        buffered["geometry"] = projected.geometry.buffer(distance_m)
        if dissolve:
            buffered = gpd.GeoDataFrame(geometry=[buffered.unary_union], crs=projected.crs)

        result = buffered.to_crs(gdf.crs) if gdf.crs else buffered
        result_name = f"{real_name}_buffer_{distance}{unit}"
        store_generated_result(handler, result_name, result)
        highlight_indices(handler, layer_idx, gdf.index)
        return (
            f"已完成缓冲区分析，生成结果图层 {result_name}，共 {len(result)} 条记录。\n"
            f"原始图层: {real_name}\n"
            f"距离: {distance}{unit}\n"
            f"预览:\n{preview_frame(result)}"
        )

    return buffer_analysis
