from langchain_core.tools import tool
import pandas as pd


def create_get_poi_by_index_tool(handler):
    map_h = handler.map_handler

    @tool
    def get_poi_by_index(layer_name: str, feature_index: int) -> str:
        """
        根据图层名和要素索引获取单个 POI 详情，并在地图上高亮。
        适合处理已由上下文解析出的“它、这个店、武侯祠的店”等指代。
        """
        target_idx = None
        target_gdf = None
        for idx, (gdf, name) in enumerate(zip(map_h.gdfs, map_h.layer_names)):
            if name == layer_name:
                target_idx = idx
                target_gdf = gdf
                break
        if target_gdf is None:
            return f"错误：未找到图层 '{layer_name}'。可用图层：{', '.join(map_h.layer_names)}"

        try:
            if feature_index in target_gdf.index:
                row = target_gdf.loc[feature_index]
                real_index = feature_index
            else:
                row = target_gdf.iloc[feature_index]
                real_index = int(row.name)
        except Exception as exc:
            return f"错误：无法获取 {layer_name} 中索引 {feature_index} 的要素: {str(exc)}"

        text_cols = [
            col for col in target_gdf.select_dtypes(include=["object", "string", "number"]).columns
            if col != "geometry"
        ]
        info = {col: row[col] for col in text_cols if pd.notna(row[col])}
        info_str = "\n".join(f"- {key}: {value}" for key, value in info.items())
        handler._last_pois = [{
            "layer": layer_name,
            "index": int(real_index),
            "name": str(row["name"]) if "name" in target_gdf.columns and pd.notna(row["name"]) else "",
            "type": str(row["type"]) if "type" in target_gdf.columns and pd.notna(row["type"]) else "",
            "address": str(row["address"]) if "address" in target_gdf.columns and pd.notna(row["address"]) else "",
            "district": str(row["district"]) if "district" in target_gdf.columns and pd.notna(row["district"]) else "",
        }]
        handler._store_highlights([(target_idx, int(real_index))])
        return f"[{layer_name}] 要素{real_index} 详情:\n{info_str}"

    return get_poi_by_index
