from math import floor

import geopandas as gpd
import numpy as np
import pandas as pd
from langchain_core.tools import tool
from shapely.geometry import box

from .advanced_common import (
    distance_to_meters,
    find_layer,
    highlight_indices,
    preview_frame,
    store_generated_result,
)
from .utils_geo import reproject_to_meters


def _run_dbscan(points_xy, eps, min_samples):
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
        store_generated_result(handler, f"{real_name}_dbscan", result)

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
    def hotspot_analysis(layer_name: str, cell_size: float, unit: str = "m", top_n: int = 10) -> str:
        """Run a simple grid-based hotspot analysis for point-like layers."""
        layer_idx, gdf, real_name = find_layer(map_h, layer_name)
        if gdf is None:
            return f"错误：未找到图层 '{layer_name}'。"
        if gdf.empty:
            return f"图层 '{layer_name}' 为空。"

        projected = reproject_to_meters(gdf.copy())
        size_m = distance_to_meters(cell_size, unit)
        centroids = projected.geometry.centroid
        xs = centroids.x.to_numpy()
        ys = centroids.y.to_numpy()
        minx, miny = xs.min(), ys.min()

        cell_x = np.array([floor((x - minx) / size_m) for x in xs], dtype=int)
        cell_y = np.array([floor((y - miny) / size_m) for y in ys], dtype=int)
        keys = [f"{ix}_{iy}" for ix, iy in zip(cell_x, cell_y)]

        working = gdf.copy()
        working["hotspot_cell"] = keys
        summary = (
            working.groupby("hotspot_cell")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(max(1, int(top_n)))
        )

        cells = []
        for _, row in summary.iterrows():
            ix, iy = [int(part) for part in row["hotspot_cell"].split("_")]
            x0 = minx + ix * size_m
            y0 = miny + iy * size_m
            cells.append(
                {
                    "hotspot_cell": row["hotspot_cell"],
                    "count": int(row["count"]),
                    "geometry": box(x0, y0, x0 + size_m, y0 + size_m),
                }
            )
        hotspot_gdf = gpd.GeoDataFrame(cells, geometry="geometry", crs=projected.crs).to_crs(gdf.crs)
        store_generated_result(handler, f"{real_name}_hotspots", hotspot_gdf)

        top_cells = set(summary["hotspot_cell"].tolist())
        highlight_indices(handler, layer_idx, working[working["hotspot_cell"].isin(top_cells)].index.tolist())

        return (
            f"已完成热点分析。图层={real_name}，网格大小={cell_size}{unit}。\n"
            f"热点网格统计:\n{summary.to_string(index=False)}"
        )

    return hotspot_analysis
