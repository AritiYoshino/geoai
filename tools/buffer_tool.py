from typing import Optional

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
    def buffer_analysis(
        layer_name: str,
        distance: float,
        unit: str = "m",
        dissolve: bool = False,
        feature_index: Optional[int] = None,
        feature_indices: Optional[list[int]] = None,
    ) -> str:
        """Create buffers around a whole layer, one feature, or selected features."""
        layer_idx, gdf, real_name = find_layer(map_h, layer_name)
        if gdf is None:
            return f"错误：未找到图层 '{layer_name}'。"

        source_gdf = gdf
        target_desc = f"图层 {real_name}"
        target_indices = gdf.index
        selected_indices = []
        if feature_indices:
            selected_indices = list(feature_indices)
        elif feature_index is not None:
            selected_indices = [feature_index]

        if selected_indices:
            try:
                rows = []
                real_indices = []
                for idx in selected_indices:
                    if idx in gdf.index:
                        row = gdf.loc[idx]
                        real_index = idx
                    else:
                        row = gdf.iloc[int(idx)]
                        real_index = row.name
                    rows.append(row)
                    real_indices.append(real_index)

                source_gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=gdf.crs)
                target_indices = real_indices
                if len(real_indices) == 1:
                    target_desc = f"{real_name} 索引 {real_indices[0]} 的单个 POI"
                else:
                    target_desc = f"{real_name} 中指定的 {len(real_indices)} 个 POI"
            except Exception as exc:
                return f"错误：无法获取 {real_name} 中指定索引 {selected_indices} 的要素: {str(exc)}"

        distance_m = distance_to_meters(distance, unit)
        projected = reproject_to_meters(source_gdf.copy())
        buffered = projected.copy()
        buffered["geometry"] = projected.geometry.buffer(distance_m)
        if dissolve:
            buffered = gpd.GeoDataFrame(geometry=[buffered.unary_union], crs=projected.crs)

        result = buffered.to_crs(gdf.crs) if gdf.crs else buffered
        distance_label = f"{float(distance):g}"
        if selected_indices and len(target_indices) == 1:
            suffix = f"_{int(target_indices[0])}"
        elif selected_indices:
            suffix = f"_selected_{len(target_indices)}"
        else:
            suffix = ""
        result_name = f"{real_name}{suffix}_buffer_{distance_label}{unit}"
        store_generated_result(handler, result_name, result)
        if hasattr(map_h, "add_generated_layer"):
            map_h.add_generated_layer(
                result_name,
                result,
                visualization_style={
                    "kind": "buffer",
                    "fill_color": "#2563eb",
                    "fill_opacity": 0.28,
                    "line_color": "#1d4ed8",
                    "line_opacity": 0.85,
                    "line_width": 2,
                },
                auto_visible=True,
            )
        highlight_indices(handler, layer_idx, target_indices)
        return (
            f"已完成缓冲区分析，生成结果图层 {result_name}，共 {len(result)} 条记录。\n"
            f"分析对象: {target_desc}\n"
            f"距离: {distance}{unit}\n"
            f"预览:\n{preview_frame(result)}"
        )

    return buffer_analysis
