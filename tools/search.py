from langchain_core.tools import tool
import pandas as pd


MAX_RESULTS = 20


def create_search_poi_tool(handler):
    map_h = handler.map_handler

    @tool
    def search_poi(keyword: str, layer_name: str = "", field_name: str = "") -> str:
        """
        在所有图层或指定图层中搜索包含指定关键词的 POI。关键词会匹配所有文本字段。

        参数 keyword: 搜索关键词，如 "学校"、"星巴克"。
        参数 layer_name: 可选。指定后只在该图层中搜索，如 "住宿服务"。
        参数 field_name: 可选。指定后只匹配该文本字段，如 "name"。
        """
        requested_layer = str(layer_name or "").strip()
        requested_field = str(field_name or "").strip()
        layer_items = list(enumerate(zip(map_h.gdfs, map_h.layer_names)))
        if requested_layer:
            layer_items = [
                (idx, (gdf, name))
                for idx, (gdf, name) in layer_items
                if name == requested_layer
            ]
            if not layer_items:
                return f"错误：未找到图层 '{requested_layer}'。可用图层：{', '.join(map_h.layer_names)}"

        results = []
        highlights = []
        pois = []
        for layer_idx, (gdf, name) in layer_items:
            text_cols = gdf.select_dtypes(include=["object", "string"]).columns.tolist()
            if requested_field:
                if requested_field not in gdf.columns:
                    continue
                text_cols = [requested_field]
            if not text_cols:
                continue
            mask = pd.Series([False] * len(gdf), index=gdf.index)
            for col in text_cols:
                if col == "geometry":
                    continue
                mask |= gdf[col].astype(str).str.contains(keyword, case=False, na=False, regex=False)
            matched = gdf[mask]
            if matched.empty:
                continue

            for idx in matched.index:
                info = {
                    col: matched.loc[idx, col]
                    for col in text_cols
                    if col != "geometry" and pd.notna(matched.loc[idx, col])
                }
                info_str = ", ".join([f"{key}: {value}" for key, value in info.items()])
                results.append(f"[{name}] 索引:{idx} | {info_str}")
                highlights.append((layer_idx, idx))
                pois.append({
                    "layer": name,
                    "index": int(idx),
                    "name": str(matched.loc[idx, "name"]) if "name" in matched.columns and pd.notna(matched.loc[idx, "name"]) else "",
                    "type": str(matched.loc[idx, "type"]) if "type" in matched.columns and pd.notna(matched.loc[idx, "type"]) else "",
                    "address": str(matched.loc[idx, "address"]) if "address" in matched.columns and pd.notna(matched.loc[idx, "address"]) else "",
                    "district": str(matched.loc[idx, "district"]) if "district" in matched.columns and pd.notna(matched.loc[idx, "district"]) else "",
                })

        total = len(results)
        scope = f"（仅搜索图层：{requested_layer}）" if requested_layer else ""
        field_scope = f"（仅匹配字段：{requested_field}）" if requested_field else ""
        if total == 0:
            return f"未找到任何包含 '{keyword}' 的 POI{scope}{field_scope}。"

        shown_results = results[:MAX_RESULTS]
        if total > MAX_RESULTS:
            summary = f"找到 {total} 个匹配项{scope}{field_scope}，仅显示前 {MAX_RESULTS} 条\n" + "\n".join(shown_results)
        else:
            summary = f"找到以下匹配项{scope}{field_scope}:\n" + "\n".join(shown_results)

        handler._last_pois = pois
        handler._store_highlights(highlights)
        return summary

    return search_poi
