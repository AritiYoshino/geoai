# tools/search.py
from langchain_core.tools import tool
import pandas as pd

MAX_RESULTS = 20  # 最大返回结果数

def create_search_poi_tool(handler):
    map_h = handler.map_handler

    @tool
    def search_poi(keyword: str) -> str:
        """
        在所有图层中搜索包含指定关键词的POI。关键词会匹配所有文本字段。
        参数 keyword: 搜索关键词，如 "学校"、"星巴克"。
        """
        results = []
        highlights = []
        for layer_idx, (gdf, name) in enumerate(zip(map_h.gdfs, map_h.layer_names)):
            text_cols = gdf.select_dtypes(include=['object', 'string']).columns.tolist()
            if not text_cols:
                continue
            mask = pd.Series([False] * len(gdf))
            for col in text_cols:
                if col == 'geometry':
                    continue
                mask |= gdf[col].astype(str).str.contains(keyword, case=False, na=False, regex=False)
            matched = gdf[mask]
            if not matched.empty:
                for idx in matched.index:
                    info = {col: matched.loc[idx, col] for col in text_cols if col != 'geometry' and pd.notna(matched.loc[idx, col])}
                    info_str = ", ".join([f"{k}: {v}" for k, v in info.items()])
                    results.append(f"[{name}] 索引:{idx} | {info_str}")
                    highlights.append((layer_idx, idx))

        total = len(results)
        if total == 0:
            return f"未找到任何包含 '{keyword}' 的POI。"

        # 截断返回结果，避免上下文过长
        if total > MAX_RESULTS:
            results = results[:MAX_RESULTS]
            summary = f"找到 {total} 个匹配项，仅显示前 {MAX_RESULTS} 条:\n" + "\n".join(results)
        else:
            summary = "找到以下匹配项:\n" + "\n".join(results)

        handler._store_highlights(highlights)  # 高亮全部（不截断）
        return summary

    return search_poi