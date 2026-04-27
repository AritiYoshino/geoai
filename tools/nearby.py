# tools/nearby.py
from langchain_core.tools import tool
from .utils_geo import reproject_to_meters
import geopandas as gpd
import pandas as pd
import traceback

MAX_NEARBY_RESULTS = 20

def create_find_nearby_tool(handler):
    map_h = handler.map_handler

    @tool
    def find_nearby(target_layer: str, reference_layer: str, distance: float, unit: str = "km") -> str:
        """
        查找参考图层中所有POI附近一定距离内的目标图层POI。
        """
        target_idx = None
        target_gdf = None
        target_name = None
        ref_gdf = None
        ref_name = None
        for idx, (gdf, name) in enumerate(zip(map_h.gdfs, map_h.layer_names)):
            if name == target_layer:
                target_idx = idx
                target_gdf = gdf
                target_name = name
            if name == reference_layer:
                ref_gdf = gdf
                ref_name = name
        if target_gdf is None:
            return f"错误：未找到目标图层 '{target_layer}'。"
        if ref_gdf is None:
            return f"错误：未找到参考图层 '{reference_layer}'。"

        # 统一 CRS
        if ref_gdf.crs != target_gdf.crs:
            ref_gdf = ref_gdf.to_crs('EPSG:4326')
            target_gdf = target_gdf.to_crs('EPSG:4326')

        dist_meters = distance * 1000 if unit == "km" else distance

        try:
            target_proj = reproject_to_meters(target_gdf.copy())
            ref_proj = reproject_to_meters(ref_gdf.copy())
        except Exception as e:
            return f"坐标转换失败: {str(e)}"

        sindex_target = target_proj.sindex
        nearby_indices = set()
        highlights = []

        for ref_idx in ref_proj.index:
            ref_geom = ref_proj.geometry.loc[ref_idx]
            buffer = ref_geom.buffer(dist_meters)
            possible = list(sindex_target.intersection(buffer.bounds))
            for t_idx in possible:
                if target_proj.geometry.loc[t_idx].distance(ref_geom) <= dist_meters:
                    nearby_indices.add(t_idx)

        total = len(nearby_indices)
        if total == 0:
            return f"在 {ref_name} 的 {distance}{unit} 范围内未找到任何 {target_name}。"

        nearby_list = list(nearby_indices)
        if total > MAX_NEARBY_RESULTS:
            nearby_list = nearby_list[:MAX_NEARBY_RESULTS]
            summary = f"在 {ref_name} 的 {distance}{unit} 范围内，找到 {total} 个 {target_name}，仅显示前 {MAX_NEARBY_RESULTS} 个:\n"
        else:
            summary = f"在 {ref_name} 的 {distance}{unit} 范围内，找到 {total} 个 {target_name}:\n"

        results = []
        text_cols = target_gdf.select_dtypes(include=['object', 'string']).columns.tolist()
        for t_idx in nearby_list:
            info = {col: target_gdf.loc[t_idx, col] for col in text_cols if col != 'geometry' and pd.notna(target_gdf.loc[t_idx, col])}
            info_str = ", ".join([f"{k}: {v}" for k, v in info.items()])
            results.append(f"[{target_name}] 要素{t_idx}: {info_str}")
            highlights.append((target_idx, t_idx))

        handler._store_highlights(highlights)
        return summary + "\n".join(results)

    return find_nearby


def create_find_nearby_point_tool(handler):
    map_h = handler.map_handler

    @tool
    def find_nearby_point(reference_layer: str, reference_index: int, target_layer: str, distance: float, unit: str = "km") -> str:
        """
        以参考图层中的某个特定要素为中心，查找目标图层中距离该要素指定范围内的POI。
        """
        print(f"[DEBUG] find_nearby_point: ref_layer={reference_layer}, ref_idx={reference_index}, target={target_layer}, dist={distance}{unit}")

        # 获取图层
        ref_gdf = None
        target_gdf = None
        target_idx_map = None
        target_name = None
        for idx, (gdf, name) in enumerate(zip(map_h.gdfs, map_h.layer_names)):
            if name == reference_layer:
                ref_gdf = gdf
            if name == target_layer:
                target_idx_map = idx
                target_gdf = gdf
                target_name = name

        if ref_gdf is None:
            return f"错误：未找到参考图层 '{reference_layer}'"
        if target_gdf is None:
            return f"错误：未找到目标图层 '{target_layer}'"

        # 获取参考几何
        try:
            if reference_index in ref_gdf.index:
                ref_geom = ref_gdf.geometry.loc[reference_index]
            else:
                ref_geom = ref_gdf.geometry.iloc[reference_index]
        except Exception as e:
            return f"错误：无法获取参考要素几何: {str(e)}"

        if ref_geom is None or ref_geom.is_empty:
            return f"错误：参考要素几何为空。"

        # 统一 CRS
        if ref_gdf.crs != target_gdf.crs:
            print(f"[DEBUG] CRS 不一致，统一转换为 EPSG:4326")
            ref_gdf = ref_gdf.to_crs('EPSG:4326')
            target_gdf = target_gdf.to_crs('EPSG:4326')
            # 重新获取参考几何（因为 ref_gdf 已改变）
            if reference_index in ref_gdf.index:
                ref_geom = ref_gdf.geometry.loc[reference_index]
            else:
                ref_geom = ref_gdf.geometry.iloc[reference_index]

        # 构造参考点 GDF
        ref_point_gdf = gpd.GeoDataFrame(geometry=[ref_geom], crs=ref_gdf.crs)

        # 投影到米制
        try:
            target_proj = reproject_to_meters(target_gdf.copy())
            ref_point_proj = reproject_to_meters(ref_point_gdf)
            ref_point_geom = ref_point_proj.geometry.iloc[0]
        except Exception as e:
            print(f"[ERROR] 投影失败: {e}\n{traceback.format_exc()}")
            return f"坐标投影失败: {str(e)}"

        dist_meters = distance * 1000 if unit == "km" else distance
        print(f"[DEBUG] 投影后参考点: ({ref_point_geom.x:.2f}, {ref_point_geom.y:.2f}), 缓冲区半径: {dist_meters} 米")

        # 空间查询
        sindex_target = target_proj.sindex
        buffer = ref_point_geom.buffer(dist_meters)
        possible = list(sindex_target.intersection(buffer.bounds))
        print(f"[DEBUG] 空间索引候选数量: {len(possible)}")

        # 精确距离过滤
        nearby_indices = []
        for t_idx in possible:
            if target_proj.geometry.iloc[t_idx].distance(ref_point_geom) <= dist_meters:
                nearby_indices.append(t_idx)

        total = len(nearby_indices)
        if total == 0:
            return f"在距离 {reference_layer} 索引 {reference_index} 的 {distance}{unit} 范围内未找到任何 {target_name}。"

        if total > MAX_NEARBY_RESULTS:
            nearby_indices = nearby_indices[:MAX_NEARBY_RESULTS]
            summary = f"在 {reference_layer} 索引 {reference_index} 的 {distance}{unit} 范围内，找到 {total} 个 {target_name}，仅显示前 {MAX_NEARBY_RESULTS} 个:\n"
        else:
            summary = f"在 {reference_layer} 索引 {reference_index} 的 {distance}{unit} 范围内，找到 {total} 个 {target_name}:\n"

        results = []
        highlights = []
        text_cols = target_gdf.select_dtypes(include=['object', 'string']).columns.tolist()
        for t_idx in nearby_indices:
            info = {col: target_gdf.loc[t_idx, col] for col in text_cols if col != 'geometry' and pd.notna(target_gdf.loc[t_idx, col])}
            info_str = ", ".join([f"{k}: {v}" for k, v in info.items()])
            results.append(f"[{target_name}] 要素{t_idx}: {info_str}")
            highlights.append((target_idx_map, t_idx))

        handler._store_highlights(highlights)
        print(f"[DEBUG] 找到 {total} 个邻近要素，返回 {len(results)} 条")
        return summary + "\n".join(results)

    return find_nearby_point


def create_find_nearby_point_filtered_tool(handler):
    map_h = handler.map_handler

    @tool
    def find_nearby_point_filtered(
        reference_layer: str,
        reference_index: int,
        target_layer: str,
        distance: float,
        keyword: str,
        unit: str = "m",
    ) -> str:
        """
        以单个参考要素为中心，查找指定距离内且文本字段包含 keyword 的目标 POI。
        适合“某酒店附近500米内的中餐/火锅/咖啡”等带类别过滤的邻近查询。
        """
        ref_gdf = None
        target_gdf = None
        target_idx_map = None
        target_name = None
        for idx, (gdf, name) in enumerate(zip(map_h.gdfs, map_h.layer_names)):
            if name == reference_layer:
                ref_gdf = gdf
            if name == target_layer:
                target_idx_map = idx
                target_gdf = gdf
                target_name = name

        if ref_gdf is None:
            return f"错误：未找到参考图层 '{reference_layer}'"
        if target_gdf is None:
            return f"错误：未找到目标图层 '{target_layer}'"

        try:
            if reference_index in ref_gdf.index:
                ref_geom = ref_gdf.geometry.loc[reference_index]
            else:
                ref_geom = ref_gdf.geometry.iloc[reference_index]
        except Exception as e:
            return f"错误：无法获取参考要素几何: {str(e)}"

        if ref_geom is None or ref_geom.is_empty:
            return "错误：参考要素几何为空。"

        if ref_gdf.crs != target_gdf.crs:
            ref_gdf = ref_gdf.to_crs("EPSG:4326")
            target_gdf = target_gdf.to_crs("EPSG:4326")
            ref_geom = ref_gdf.geometry.loc[reference_index] if reference_index in ref_gdf.index else ref_gdf.geometry.iloc[reference_index]

        try:
            target_proj = reproject_to_meters(target_gdf.copy())
            ref_point_proj = reproject_to_meters(gpd.GeoDataFrame(geometry=[ref_geom], crs=ref_gdf.crs))
            ref_point_geom = ref_point_proj.geometry.iloc[0]
        except Exception as e:
            return f"坐标投影失败: {str(e)}"

        dist_meters = distance * 1000 if unit == "km" else distance
        buffer = ref_point_geom.buffer(dist_meters)
        possible = list(target_proj.sindex.intersection(buffer.bounds))

        text_cols = target_gdf.select_dtypes(include=["object", "string"]).columns.tolist()
        nearby_indices = []
        for pos in possible:
            geom = target_proj.geometry.iloc[pos]
            if geom.distance(ref_point_geom) > dist_meters:
                continue
            original_idx = target_gdf.index[pos]
            row_text = " ".join(
                str(target_gdf.loc[original_idx, col])
                for col in text_cols
                if col != "geometry" and pd.notna(target_gdf.loc[original_idx, col])
            )
            if keyword in row_text:
                nearby_indices.append(original_idx)

        total = len(nearby_indices)
        if total == 0:
            return (
                f"在距离 {reference_layer} 索引 {reference_index} 的 {distance}{unit} "
                f"范围内未找到包含 '{keyword}' 的 {target_name}。"
            )

        shown_indices = nearby_indices[:MAX_NEARBY_RESULTS]
        summary = (
            f"在 {reference_layer} 索引 {reference_index} 的 {distance}{unit} 范围内，"
            f"找到 {total} 个包含 '{keyword}' 的 {target_name}"
        )
        if total > MAX_NEARBY_RESULTS:
            summary += f"，仅显示前 {MAX_NEARBY_RESULTS} 个"
        summary += ":\n"

        results = []
        highlights = []
        pois = []
        for idx in shown_indices:
            info = {
                col: target_gdf.loc[idx, col]
                for col in text_cols
                if col != "geometry" and pd.notna(target_gdf.loc[idx, col])
            }
            info_str = ", ".join([f"{k}: {v}" for k, v in info.items()])
            results.append(f"[{target_name}] 要素{idx}: {info_str}")
            highlights.append((target_idx_map, idx))
            pois.append({
                "layer": target_name,
                "index": int(idx),
                "name": str(target_gdf.loc[idx, "name"]) if "name" in target_gdf.columns and pd.notna(target_gdf.loc[idx, "name"]) else "",
                "type": str(target_gdf.loc[idx, "type"]) if "type" in target_gdf.columns and pd.notna(target_gdf.loc[idx, "type"]) else "",
                "address": str(target_gdf.loc[idx, "address"]) if "address" in target_gdf.columns and pd.notna(target_gdf.loc[idx, "address"]) else "",
                "district": str(target_gdf.loc[idx, "district"]) if "district" in target_gdf.columns and pd.notna(target_gdf.loc[idx, "district"]) else "",
            })

        handler._last_pois = pois
        handler._store_highlights(highlights)
        return summary + "\n".join(results)

    return find_nearby_point_filtered
