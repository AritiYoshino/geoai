import os

import geopandas as gpd
from langchain_core.tools import tool

from .advanced_common import ensure_export_dir, find_layer, preview_frame, store_generated_result


def _has_geom_type(gdf, geom_keyword):
    return gdf.geometry.geom_type.fillna("").str.contains(geom_keyword, case=False).any()


def _safe_shp_name(name):
    unsafe = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in unsafe else ch for ch in str(name))
    return cleaned[:80] or "overlay_result"


def _write_shapefile(gdf, result_name):
    path = os.path.join(ensure_export_dir(), f"{_safe_shp_name(result_name)}.shp")
    gdf.to_file(path, driver="ESRI Shapefile", encoding="utf-8")
    return os.path.abspath(path)


def _build_polygon_count_result(point_gdf, polygon_gdf, point_name, polygon_name, predicate):
    working_points = point_gdf
    working_polygons = polygon_gdf
    if working_points.crs != working_polygons.crs:
        working_polygons = working_polygons.to_crs(working_points.crs or "EPSG:4326")

    joined = gpd.sjoin(
        working_points,
        working_polygons[["geometry"]],
        how="inner",
        predicate=predicate,
    )
    counts = joined["index_right"].value_counts()
    result = working_polygons.copy()
    result["poi_count"] = result.index.map(lambda idx: int(counts.get(idx, 0)))
    result["source_poi_layer"] = point_name
    result["polygon_layer"] = polygon_name
    if polygon_gdf.crs and result.crs != polygon_gdf.crs:
        result = result.to_crs(polygon_gdf.crs)
    return result


def _add_choropleth_layer(map_h, result_name, result):
    max_count = int(result["poi_count"].max()) if not result.empty else 1
    if hasattr(map_h, "add_generated_layer"):
        map_h.add_generated_layer(
            result_name,
            result,
            visualization_style={
                "kind": "choropleth",
                "value_field": "poi_count",
                "max_count": max_count,
                "fill_opacity": 0.72,
                "line_color": "#475569",
                "line_opacity": 0.9,
                "line_width": 1.2,
            },
            auto_visible=True,
        )
    return max_count


def _summary_table(result):
    cols = [col for col in ("NAME", "name", "district", "poi_count") if col in result.columns]
    if "poi_count" not in cols:
        cols.append("poi_count")
    return result[cols].sort_values("poi_count", ascending=False).head(20).to_string(index=False)


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
        if hasattr(map_h, "add_generated_layer"):
            map_h.add_generated_layer(result_name, result, auto_visible=True)
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
        """Run spatial join between two layers.

        If one layer is points and the other is polygons, output a polygon choropleth
        layer with poi_count instead of highlighting all POI points.
        """
        _, target, target_name = find_layer(map_h, target_layer)
        _, join_gdf, join_name = find_layer(map_h, join_layer)
        if target is None:
            return f"错误：未找到图层 '{target_layer}'。"
        if join_gdf is None:
            return f"错误：未找到图层 '{join_layer}'。"

        target_is_point = _has_geom_type(target, "Point")
        target_is_polygon = _has_geom_type(target, "Polygon")
        join_is_point = _has_geom_type(join_gdf, "Point")
        join_is_polygon = _has_geom_type(join_gdf, "Polygon")

        if target_is_point and join_is_polygon:
            result = _build_polygon_count_result(target, join_gdf, target_name, join_name, predicate)
            result_name = f"{join_name}_{target_name}_poi_count"
            store_generated_result(handler, result_name, result)
            max_count = _add_choropleth_layer(map_h, result_name, result)
            shp_path = _write_shapefile(result, result_name)
            return (
                f"已完成点-面叠加统计：{target_name} 落入 {join_name}。\n"
                f"输出结果为面图层，几何与 {join_name} 一致，字段 poi_count 表示每个区域内的 POI 数量；未高亮 POI 点。\n"
                f"地图已按 poi_count 从浅到深着色。\n"
                f"Shapefile 已保存: {shp_path}\n"
                f"面要素数: {len(result)}，最大 POI 数: {max_count}\n"
                f"统计预览:\n{_summary_table(result)}"
            )

        if target_is_polygon and join_is_point:
            result = _build_polygon_count_result(join_gdf, target, join_name, target_name, predicate)
            result_name = f"{target_name}_{join_name}_poi_count"
            store_generated_result(handler, result_name, result)
            max_count = _add_choropleth_layer(map_h, result_name, result)
            shp_path = _write_shapefile(result, result_name)
            return (
                f"已完成点-面叠加统计：{join_name} 落入 {target_name}。\n"
                f"输出结果为面图层，几何与 {target_name} 一致，字段 poi_count 表示每个区域内的 POI 数量；未高亮 POI 点。\n"
                f"地图已按 poi_count 从浅到深着色。\n"
                f"Shapefile 已保存: {shp_path}\n"
                f"面要素数: {len(result)}，最大 POI 数: {max_count}\n"
                f"统计预览:\n{_summary_table(result)}"
            )

        if target.crs != join_gdf.crs:
            join_gdf = join_gdf.to_crs(target.crs or "EPSG:4326")
        result = gpd.sjoin(target, join_gdf, how=how, predicate=predicate)
        result_name = f"{target_name}_sjoin_{join_name}"
        store_generated_result(handler, result_name, result)
        if hasattr(map_h, "add_generated_layer"):
            map_h.add_generated_layer(result_name, result, auto_visible=True)
        return (
            f"已完成空间连接分析：{target_name} 与 {join_name}，谓词 {predicate}。\n"
            f"结果记录数: {len(result)}\n"
            f"预览:\n{preview_frame(result)}"
        )

    return spatial_join_layers
