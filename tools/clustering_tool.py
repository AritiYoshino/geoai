import os
from math import ceil, floor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from langchain_core.tools import tool
from shapely.geometry import box
from shapely.ops import unary_union
try:
    from sklearn.cluster import DBSCAN as SklearnDBSCAN
except Exception:
    SklearnDBSCAN = None

try:
    import rasterio
    from rasterio.transform import from_bounds as rasterio_from_bounds
    HAS_RASTERIO = True
except Exception:
    HAS_RASTERIO = False

from .advanced_common import (
    distance_to_meters,
    find_layer,
    highlight_indices,
    preview_frame,
    store_generated_result,
)
from .utils_geo import reproject_to_meters


def _run_dbscan(points_xy, eps, min_samples):
    if SklearnDBSCAN is not None:
        return SklearnDBSCAN(eps=eps, min_samples=min_samples, n_jobs=1).fit_predict(points_xy)

    n = len(points_xy)
    labels = np.full(n, -99, dtype=int)
    cluster_id = 0

    def region_query(i):
        diffs = points_xy - points_xy[i]
        dist = np.sqrt((diffs ** 2).sum(axis=1))
        return np.where(dist <= eps)[0].tolist()

    for i in range(n):
        if labels[i] != -99:
            continue
        neighbors = region_query(i)
        if len(neighbors) < min_samples:
            labels[i] = -1
            continue
        labels[i] = cluster_id
        seeds = [idx for idx in neighbors if idx != i]
        while seeds:
            current = seeds.pop()
            if labels[current] == -1:
                labels[current] = cluster_id
            if labels[current] != -99:
                continue
            labels[current] = cluster_id
            current_neighbors = region_query(current)
            if len(current_neighbors) >= min_samples:
                for nb in current_neighbors:
                    if nb not in seeds:
                        seeds.append(nb)
        cluster_id += 1
    return labels


def _find_admin_boundary(map_h):
    preferred_names = ["成都行政区", "成都市行政区", "成都行政边界", "成都市行政边界"]
    layer_names = getattr(map_h, "layer_names", [])
    for name in preferred_names:
        if name in layer_names:
            admin = map_h.get_gdf(name)
            if admin is not None and not admin.empty:
                return name, admin

    for name in layer_names:
        if "行政" not in str(name):
            continue
        try:
            admin = map_h.get_gdf(name)
        except Exception:
            continue
        if admin is not None and not admin.empty and admin.geometry.geom_type.str.contains("Polygon").any():
            return name, admin
    return None, None


def _generate_hotspot_geotiff(
    counts_dict,
    minx,
    miny,
    maxx,
    maxy,
    size_m,
    cols,
    rows,
    admin_boundary,
    crs,
    output_path,
    nodata=-9999,
):
    """
    将热点网格计数生成真正的 GeoTIFF 栅格文件。

    Parameters
    ----------
    counts_dict : dict
        {"ix_iy": count} 字典，记录了每个有 POI 的网格单元的计数值。
    minx, miny, maxx, maxy : float
        行政边界在投影坐标系下的外包矩形范围。
    size_m : float
        网格单元大小（米）。
    cols, rows : int
        网格列数和行数。
    admin_boundary : shapely.geometry
        行政边界的投影几何（用于裁剪栅格范围）。
    crs : pyproj.CRS
        投影坐标参考系统。
    output_path : str
        输出的 GeoTIFF 文件路径。
    nodata : float
        NoData 值（默认 -9999）。
    """
    from shapely import box as shapely_box

    # 初始化二维数组（行 × 列），用 nodata 填充
    raster_data = np.full((rows, cols), nodata, dtype=np.float32)

    # 填充有 POI 计数的网格
    for key, count in counts_dict.items():
        parts = key.split("_")
        ix, iy = int(parts[0]), int(parts[1])
        if 0 <= ix < cols and 0 <= iy < rows:
            raster_data[iy, ix] = float(count)

    # 将行政边界外的网格置为 nodata（使用栅格化 mask）
    # 构建每个网格单元的矢量掩膜，判断是否与行政边界相交
    mask = np.zeros((rows, cols), dtype=bool)
    for ix in range(cols):
        x0 = minx + ix * size_m
        for iy in range(rows):
            y0 = miny + iy * size_m
            cell_box = shapely_box(x0, y0, x0 + size_m, y0 + size_m)
            if not cell_box.intersects(admin_boundary):
                mask[iy, ix] = True

    raster_data[mask] = nodata

    # 构建地理变换参数: (左上角x, x分辨率, 旋转, 左上角y, 旋转, y分辨率(负值))
    # rasterio 使用标准 GDAL geotransform
    transform = rasterio_from_bounds(
        minx, miny, maxx, maxy, cols, rows
    )

    # 写入 GeoTIFF
    profile = {
        "driver": "GTiff",
        "height": rows,
        "width": cols,
        "count": 1,
        "dtype": rasterio.float32,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(raster_data, 1)
        dst.set_band_description(1, "POI Count")

    return output_path


def create_dbscan_tool(handler):
    map_h = handler.map_handler

    @tool
    def cluster_points_dbscan(layer_name: str, eps: float, min_samples: int = 5, unit: str = "m") -> str:
        """Cluster point-like features with DBSCAN."""
        layer_idx, gdf, real_name = find_layer(map_h, layer_name)
        if gdf is None:
            return f"错误：未找到图层 '{layer_name}'。"
        if gdf.empty:
            return f"图层 '{layer_name}' 为空。"

        projected = reproject_to_meters(gdf.copy())
        coords = np.array([[geom.centroid.x, geom.centroid.y] for geom in projected.geometry])
        labels = _run_dbscan(coords, distance_to_meters(eps, unit), int(min_samples))

        result = gdf.copy()
        result["cluster_id"] = labels
        cluster_counts = (
            pd.Series(labels)
            .value_counts()
            .rename_axis("cluster_id")
            .reset_index(name="count")
            .sort_values(["cluster_id"])
        )
        eps_label = f"{float(eps):g}"
        result_name = f"{real_name}_dbscan_{eps_label}{unit}_min{int(min_samples)}"
        store_generated_result(handler, result_name, result)
        if hasattr(map_h, "add_generated_layer"):
            map_h.add_generated_layer(
                result_name,
                result,
                visualization_style={
                    "kind": "dbscan",
                    "cluster_field": "cluster_id",
                    "color": "#2563eb",
                },
                auto_visible=True,
            )

        non_noise = result[result["cluster_id"] >= 0]
        if not non_noise.empty:
            dominant = non_noise["cluster_id"].value_counts().idxmax()
            highlight_indices(handler, layer_idx, non_noise[non_noise["cluster_id"] == dominant].index.tolist())

        return (
            f"已完成 DBSCAN 聚类分析。图层={real_name}，eps={eps}{unit}，min_samples={min_samples}。\n"
            f"聚类统计:\n{cluster_counts.to_string(index=False)}\n"
            f"结果预览:\n{preview_frame(result)}"
        )

    return cluster_points_dbscan


def create_hotspot_tool(handler):
    map_h = handler.map_handler

    @tool
    def hotspot_analysis(
        layer_name: str,
        cell_size: float,
        unit: str = "m",
        top_n: int = 10,
        as_raster: bool = True,
    ) -> str:
        """Create a Chengdu admin-boundary grid hotspot layer for point-like layers.
        支持输出矢量网格 (SHP-like) 和/或真正的 GeoTIFF 栅格。

        Args:
            layer_name: POI 点图层名称。
            cell_size: 网格单元大小（数值）。
            unit: 单位，支持 "m"（米，默认）或 "km"（千米）。
            top_n: 显示 Top N 热点网格。
            as_raster: 是否同时输出 GeoTIFF 栅格文件（默认 True）。
        """
        gdf, real_name = find_layer(map_h, layer_name)[1:]
        if gdf is None:
            return f"错误：未找到图层 '{layer_name}'。"
        if gdf.empty:
            return f"图层 '{layer_name}' 为空。"

        admin_name, admin_gdf = _find_admin_boundary(map_h)
        if admin_gdf is None:
            return "错误：未找到成都市行政区边界图层，无法按行政范围生成热点栅格。请确认存在 '成都行政区' 图层。"

        projected = reproject_to_meters(gdf.copy())
        admin_projected = admin_gdf.to_crs(projected.crs)
        admin_boundary = unary_union(admin_projected.geometry)
        if admin_boundary.is_empty:
            return f"错误：行政区图层 '{admin_name}' 边界为空。"

        size_m = distance_to_meters(cell_size, unit)
        if size_m <= 0:
            return "错误：网格大小必须大于 0。"

        centroids = projected.geometry.centroid
        in_admin = centroids.within(admin_boundary)
        working_projected = projected[in_admin].copy()
        if working_projected.empty:
            return f"图层 '{real_name}' 在行政区图层 '{admin_name}' 范围内没有可统计的点。"

        minx, miny, maxx, maxy = admin_boundary.bounds
        cols = int(ceil((maxx - minx) / size_m))
        rows = int(ceil((maxy - miny) / size_m))

        working_centroids = working_projected.geometry.centroid
        cell_x = np.array([floor((x - minx) / size_m) for x in working_centroids.x.to_numpy()], dtype=int)
        cell_y = np.array([floor((y - miny) / size_m) for y in working_centroids.y.to_numpy()], dtype=int)
        keys = [f"{ix}_{iy}" for ix, iy in zip(cell_x, cell_y)]
        counts = pd.Series(keys).value_counts().to_dict()

        # --- 构建矢量网格（始终生成，用于地图显示和摘要） ---
        cells = []
        for ix in range(cols):
            x0 = minx + ix * size_m
            for iy in range(rows):
                y0 = miny + iy * size_m
                cell = box(x0, y0, x0 + size_m, y0 + size_m)
                if not cell.intersects(admin_boundary):
                    continue
                clipped = cell.intersection(admin_boundary)
                if clipped.is_empty:
                    continue
                cell_key = f"{ix}_{iy}"
                count = int(counts.get(cell_key, 0))
                cells.append(
                    {
                        "hotspot_cell": cell_key,
                        "count": count,
                        "density": count / ((size_m / 1000) ** 2),
                        "cell_size_m": float(size_m),
                        "geometry": clipped,
                    }
                )

        hotspot_gdf = gpd.GeoDataFrame(cells, geometry="geometry", crs=projected.crs).to_crs(gdf.crs)
        summary = (
            hotspot_gdf[hotspot_gdf["count"] > 0][["hotspot_cell", "count", "density"]]
            .sort_values("count", ascending=False)
            .head(max(1, int(top_n)))
        )
        cell_label = f"{float(cell_size):g}"
        result_name = f"{real_name}_hotspot_grid_{cell_label}{unit}_chengdu"
        store_generated_result(handler, result_name, hotspot_gdf)
        if hasattr(map_h, "add_generated_layer"):
            max_count = int(hotspot_gdf["count"].max()) if not hotspot_gdf.empty else 1
            map_h.add_generated_layer(
                result_name,
                hotspot_gdf,
                visualization_style={
                    "kind": "hotspot",
                    "value_field": "count",
                    "max_count": max_count,
                    "fill_color": "#ef4444",
                    "line_color": "#991b1b",
                    "fill_opacity": 0.58,
                    "line_opacity": 0.9,
                    "line_width": 1.6,
                },
                auto_visible=True,
            )

        # --- 生成 GeoTIFF 栅格 ---
        raster_path = None
        if as_raster:
            if not HAS_RASTERIO:
                raster_msg = "警告：rasterio 库未安装，无法输出 GeoTIFF。请执行 `pip install rasterio`。"
            else:
                try:
                    export_dir = Path("data") / "exports"
                    export_dir.mkdir(parents=True, exist_ok=True)
                    raster_filename = f"{result_name}.tif"
                    raster_path = str(export_dir / raster_filename)

                    _generate_hotspot_geotiff(
                        counts_dict=counts,
                        minx=minx,
                        miny=miny,
                        maxx=maxx,
                        maxy=maxy,
                        size_m=size_m,
                        cols=cols,
                        rows=rows,
                        admin_boundary=admin_boundary,
                        crs=projected.crs,
                        output_path=raster_path,
                    )
                    raster_msg = f"GeoTIFF 栅格已保存: {raster_path}"
                except Exception as exc:
                    raster_msg = f"GeoTIFF 生成失败: {str(exc)}"
        else:
            raster_msg = "未输出 GeoTIFF 栅格（as_raster=False）。"

        # --- 构建返回信息 ---
        lines = [
            f"已完成热点分析。POI图层={real_name}，研究范围={admin_name}，网格大小={cell_size}{unit}。",
            f"输出矢量网格数={len(hotspot_gdf)}，有POI的网格数={int((hotspot_gdf['count'] > 0).sum())}，最大单元计数={int(hotspot_gdf['count'].max()) if not hotspot_gdf.empty else 0}。",
            f"{raster_msg}",
            f"热点 Top {top_n}:",
            summary.to_string(index=False),
        ]
        return "\n".join(lines)

    return hotspot_analysis
