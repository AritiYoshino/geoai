import os

from langchain_core.tools import tool

from .advanced_common import ensure_export_dir, find_layer


def create_export_tool(handler):
    map_h = handler.map_handler

    @tool
    def export_analysis_result(
        source_type: str = "last_result",
        layer_name: str = "",
        export_format: str = "geojson",
        output_name: str = "",
    ) -> str:
        """Export the last generated result or an existing layer to GeoJSON or CSV."""
        source_type = str(source_type).lower()
        export_format = str(export_format).lower()

        if source_type == "last_result":
            last_result = getattr(handler, "_last_generated_result", None)
            if not last_result:
                return "错误：当前没有可导出的分析结果，请先执行缓冲区、叠加、空间连接、聚类或热点分析。"
            gdf = last_result["gdf"].copy()
            base_name = output_name or last_result["name"]
        else:
            _, gdf, real_name = find_layer(map_h, layer_name)
            if gdf is None:
                return f"错误：未找到图层 '{layer_name}'。"
            base_name = output_name or real_name

        export_dir = ensure_export_dir()
        if export_format == "geojson":
            path = os.path.abspath(os.path.join(export_dir, f"{base_name}.geojson"))
            export_gdf = gdf.to_crs("EPSG:4326") if gdf.crs and gdf.crs.to_string() != "EPSG:4326" else gdf
            export_gdf.to_file(path, driver="GeoJSON")
        elif export_format == "csv":
            path = os.path.abspath(os.path.join(export_dir, f"{base_name}.csv"))
            export_df = gdf.copy()
            if "geometry" in export_df.columns:
                export_df["geometry_wkt"] = export_df.geometry.to_wkt()
                export_df = export_df.drop(columns=["geometry"], errors="ignore")
            export_df.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            return f"错误：不支持导出格式 '{export_format}'，仅支持 geojson 或 csv。"

        return f"导出成功：{path}"

    return export_analysis_result
