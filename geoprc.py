from pathlib import Path
import geopandas as gpd
import re

# 当前目录
base_dir = Path(__file__).resolve().parent

# 输入输出目录
input_dir = base_dir / "geodata"
output_dir = base_dir / "data" / "geodata"

# 创建输出目录
output_dir.mkdir(parents=True, exist_ok=True)

def extract_name(filename):
    """
    提取规则：
    1. 取 '_' 前面的部分
    2. 从中提取中文
    """
    name_before_underscore = filename.split("_")[0]
    
    # 提取中文
    chinese = re.findall(r'[\u4e00-\u9fff]+', name_before_underscore)
    
    if chinese:
        return "".join(chinese)
    else:
        return name_before_underscore  # 没有中文就用原名

# 遍历所有 shp 文件
for shp_file in input_dir.glob("*.shp"):
    try:
        print(f"处理文件: {shp_file.name}")
        
        # 读取
        gdf = gpd.read_file(shp_file)

        # 转换坐标系（可选但推荐）
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # 生成输出文件名
        new_name = extract_name(shp_file.stem)
        output_path = output_dir / f"{new_name}.geojson"

        # 保存
        gdf.to_file(output_path, driver="GeoJSON", encoding="utf-8")

        print(f"✅ 已生成: {output_path.name}")

    except Exception as e:
        print(f"❌ 处理失败: {shp_file.name}，原因: {e}")

print("全部转换完成！")