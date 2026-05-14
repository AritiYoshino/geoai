import os
import shutil
from urllib.parse import quote

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
        download: bool = False,
    ) -> str:
        """Export the last generated result or an existing layer to GeoJSON, CSV, Shapefile, or GeoTIFF."""
        source_type = str(source_type).lower()
        export_format = str(export_format).lower()

        if source_type == "last_result":
            last_result = getattr(handler, "_last_generated_result", None)
            last_raster = getattr(handler, "_last_generated_raster", None)
            if export_format in {"tif", "tiff", "geotiff"} and last_raster:
                export_dir = ensure_export_dir()
                base_name = output_name or last_raster["name"]
                path = os.path.abspath(os.path.join(export_dir, f"{base_name}.tif"))
                source_path = os.path.abspath(last_raster["path"])
                if source_path != path:
                    shutil.copyfile(source_path, path)
                return _finish_export(handler, path, export_format, download)
            if not last_result:
                return "错误：当前没有可导出的分析结果，请先执行缓冲区、叠加、空间连接、聚类或热点分析。"
            gdf = last_result["gdf"].copy()
            base_name = output_name or last_result["name"]
        else:
            if export_format in {"tif", "tiff", "geotiff"}:
                return "错误：GeoTIFF 只能导出最近一次热点栅格分析结果，请先执行 hotspot_analysis。"
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
        elif export_format in {"shp", "shapefile"}:
            path = os.path.abspath(os.path.join(export_dir, f"{base_name}.shp"))
            export_gdf = gdf.to_crs("EPSG:4326") if gdf.crs and gdf.crs.to_string() != "EPSG:4326" else gdf
            export_gdf.to_file(path, driver="ESRI Shapefile", encoding="utf-8")
        else:
            return f"错误：不支持导出格式 '{export_format}'，仅支持 geojson、csv、shp 或 geotiff。"

        return _finish_export(handler, path, export_format, download)

    return export_analysis_result


def _finish_export(handler, path, export_format, download):
    filename = os.path.basename(path)
    url = f"/exports/{quote(filename)}"
    download_url = f"{url}?download=1"
    handler._last_export = {
        "path": path,
        "filename": filename,
        "url": url,
        "download_url": download_url,
        "format": export_format,
    }
    message = f"导出成功：{path}"
    if download:
        message += f"\n浏览器下载链接：{download_url}"
    return message
