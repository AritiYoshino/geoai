"""
将当前目录下所有 xlsx 文件中的 lng/lat 数据转换为 ESRI Shapefile 点数据，
输出到程序所在目录下的 geodata 文件夹。
依赖库：pandas, geopandas, openpyxl
安装命令：pip install pandas geopandas openpyxl
"""

import os
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def excel_to_shp(input_dir='.', output_dir='geodata', lng_col='lng', lat_col='lat', epsg=4326):
    """
    读取 input_dir 下所有 xlsx 文件，转换为 Shapefile 点数据。

    参数:
        input_dir (str): 存放 xlsx 文件的目录，默认为当前目录。
        output_dir (str): 输出 shapefile 的目录，默认为 'geodata'。
        lng_col (str): 经度列名，默认为 'lng'。
        lat_col (str): 纬度列名，默认为 'lat'。
        epsg (int): 坐标系的 EPSG 代码，默认 4326 (WGS84)。
    """
    # 创建输出目录（位于程序运行目录下）
    os.makedirs(output_dir, exist_ok=True)

    # 查找所有 xlsx 文件（包括 .xlsx 和 .XLSX）
    xlsx_files = glob.glob(os.path.join(input_dir, '*.xlsx')) + \
                 glob.glob(os.path.join(input_dir, '*.XLSX'))

    if not xlsx_files:
        print(f"在目录 {input_dir} 中未找到任何 .xlsx 文件。")
        return

    for file_path in xlsx_files:
        file_name = os.path.basename(file_path)
        print(f"正在处理: {file_name}")

        try:
            # 读取 Excel 文件（默认第一个 sheet）
            df = pd.read_excel(file_path, engine='openpyxl')

            # 检查必需的经纬度列是否存在
            if lng_col not in df.columns or lat_col not in df.columns:
                print(f"  跳过 {file_name}: 缺少列 '{lng_col}' 或 '{lat_col}'")
                continue

            # 删除经纬度缺失的行
            original_len = len(df)
            df = df.dropna(subset=[lng_col, lat_col])
            if len(df) == 0:
                print(f"  跳过 {file_name}: 有效经纬度数据为空")
                continue

            # 创建几何列（Point）
            geometry = [Point(x, y) for x, y in zip(df[lng_col], df[lat_col])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=f"EPSG:{epsg}")

            # 输出 shapefile 路径（与 Excel 同名的 .shp）
            base_name = os.path.splitext(file_name)[0]
            output_shp = os.path.join(output_dir, f"{base_name}.shp")

            # 写入 shapefile（字段名自动截断至10字符，符合 shapefile 规范）
            gdf.to_file(output_shp, driver='ESRI Shapefile')

            print(f"  成功生成: {output_shp} (有效记录数: {len(gdf)}, 原始记录: {original_len})")

        except Exception as e:
            print(f"  处理 {file_name} 时出错: {e}")

    print("所有文件处理完成。")

if __name__ == "__main__":
    # 使用示例：处理当前目录下的所有 xlsx 文件，输出到 ./geodata 文件夹
    excel_to_shp(input_dir='.', output_dir='geodata', lng_col='lng', lat_col='lat')