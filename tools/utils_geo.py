# tools/utils_geo.py
import pandas as pd
import geopandas as gpd
import warnings

def parse_conditions(conditions_str, gdf):
    """将条件字符串转换为pandas查询"""
    if not conditions_str:
        return None
    dangerous = ['__', 'exec', 'eval', 'lambda', 'globals', 'locals']
    for d in dangerous:
        if d in conditions_str.lower():
            raise ValueError(f"条件中包含非法关键字: {d}")
    try:
        for col in gdf.columns:
            if col in conditions_str and col not in gdf.columns:
                raise ValueError(f"列名 '{col}' 不存在")
        return conditions_str
    except Exception as e:
        raise ValueError(f"条件解析失败: {e}")

def reproject_to_meters(gdf):
    """
    将 GeoDataFrame 转换为合适的投影坐标系（米制）。
    若输入为地理坐标系，自动选择 UTM 投影带。
    若输入已为投影坐标系，则直接返回。
    """
    if gdf.crs is None:
        # 假设为 WGS84 经纬度
        gdf = gdf.set_crs('EPSG:4326', allow_override=True)
    
    if gdf.crs.is_geographic:
        # 计算数据范围中心经纬度
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
            # 使用总边界框中心，避免逐个几何计算
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            lon = (bounds[0] + bounds[2]) / 2
            lat = (bounds[1] + bounds[3]) / 2
        utm_zone = int((lon + 180) // 6) + 1
        epsg = 32600 + utm_zone if lat >= 0 else 32700 + utm_zone
        return gdf.to_crs(epsg=epsg)
    else:
        # 已经是投影坐标系，直接返回
        return gdf