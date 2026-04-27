# tools/query.py
from langchain_core.tools import tool
from .utils_geo import parse_conditions
import pandas as pd
import re

def create_query_poi_by_conditions_tool(handler):
    map_h = handler.map_handler

    @tool
    def query_poi_by_conditions(layer_name: str, conditions: str) -> str:
        """
        在指定图层中按属性条件查询POI。条件使用类似SQL的语法，例如 "district='锦江区' and type='酒店'"。
        参数 layer_name: 图层名称（如 "住宿服务_6474"）
        参数 conditions: 查询条件字符串，支持 and/or/括号/比较运算符(==, !=, >, <, >=, <=)
        """
        target_idx = None
        target_gdf = None
        target_name = None
        for idx, (gdf, name) in enumerate(zip(map_h.gdfs, map_h.layer_names)):
            if name == layer_name:
                target_idx = idx
                target_gdf = gdf
                target_name = name
                break
        if target_gdf is None:
            return f"错误：未找到名为 '{layer_name}' 的图层。可用图层：{', '.join(map_h.layer_names)}"

        # 提取条件中可能的字段名（简单正则提取标识符）
        possible_cols = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', conditions))
        keywords = {'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False'}
        possible_cols = [col for col in possible_cols if col not in keywords]

        # 检查字段是否存在
        invalid_cols = [col for col in possible_cols if col not in target_gdf.columns]
        if invalid_cols:
            # 列出实际可用的文本/数字字段
            available = target_gdf.select_dtypes(include=['object', 'number']).columns.tolist()
            if 'geometry' in available:
                available.remove('geometry')
            available_str = ', '.join(available[:15])
            return f"错误：条件中使用了不存在的字段名 {invalid_cols}。图层 '{layer_name}' 可用的字段有：{available_str}。请修正字段名后重试。"

        try:
            query_str = parse_conditions(conditions, target_gdf)
            if query_str is None:
                return "错误：条件为空"
            result_gdf = target_gdf.query(query_str)
            if result_gdf.empty:
                return f"在图层 '{layer_name}' 中未找到满足条件 '{conditions}' 的要素。"

            results = []
            highlights = []
            text_cols = result_gdf.select_dtypes(include=['object', 'string']).columns.tolist()
            for idx in result_gdf.index:
                info = {col: result_gdf.loc[idx, col] for col in text_cols if col != 'geometry' and pd.notna(result_gdf.loc[idx, col])}
                info_str = ", ".join([f"{k}: {v}" for k, v in info.items()])
                results.append(f"[{target_name}] 要素{idx}: {info_str}")
                highlights.append((target_idx, idx))
            handler._store_highlights(highlights)
            return f"在图层 '{layer_name}' 中找到 {len(result_gdf)} 个满足条件的要素:\n" + "\n".join(results)
        except Exception as e:
            return f"条件查询出错: {str(e)}。请确保条件格式正确，列名存在。示例: district=='锦江区' and type=='酒店'"

    return query_poi_by_conditions