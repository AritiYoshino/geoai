import geopandas as gpd
from langchain_core.tools import tool

from .advanced_common import distance_to_meters, find_layer, highlight_indices, preview_frame
from .utils_geo import reproject_to_meters


def create_nearest_neighbor_tool(handler):
    map_h = handler.map_handler

    @tool
    def nearest_neighbor_search(
        reference_layer: str,
        reference_index: int,
        target_layer: str,
        top_k: int = 5,
        max_distance: float = 0,
        unit: str = "m",
    ) -> str:
        """Find nearest neighbors from a single reference feature to a target layer."""
        _, ref_gdf, ref_name = find_layer(map_h, reference_layer)
        target_idx, target_gdf, target_name = find_layer(map_h, target_layer)
        if ref_gdf is None:
            return f"错误：未找到图层 '{reference_layer}'。"
        if target_gdf is None:
            return f"错误：未找到图层 '{target_layer}'。"

        ref_row = ref_gdf.loc[reference_index] if reference_index in ref_gdf.index else ref_gdf.iloc[reference_index]
        ref_one = gpd.GeoDataFrame([ref_row], geometry="geometry", crs=ref_gdf.crs)
        base_target = target_gdf.to_crs(ref_gdf.crs) if target_gdf.crs != ref_gdf.crs else target_gdf.copy()
        ref_proj = reproject_to_meters(ref_one)
        target_proj = reproject_to_meters(base_target)

        ref_geom = ref_proj.geometry.iloc[0]
        distances = target_proj.geometry.distance(ref_geom)
        ranked = target_gdf.copy()
        ranked["distance_m"] = distances.values
        ranked = ranked.sort_values("distance_m").head(max(1, int(top_k)))
        if max_distance and max_distance > 0:
            ranked = ranked[ranked["distance_m"] <= distance_to_meters(max_distance, unit)]

        if ranked.empty:
            return f"未找到满足条件的最近邻要素。参考图层={ref_name}，目标图层={target_name}。"

        highlight_indices(handler, target_idx, ranked.index.tolist())
        return (
            f"已完成最近邻分析。参考图层={ref_name}，目标图层={target_name}。\n"
            f"返回数量: {len(ranked)}\n"
            f"预览:\n{preview_frame(ranked)}"
        )

    return nearest_neighbor_search
