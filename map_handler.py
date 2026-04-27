# map_handler.py
import os
import glob
import geopandas as gpd
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']  # 或 ['Microsoft YaHei'] 微软雅黑 等
plt.rcParams['axes.unicode_minus'] = False   # 解决负号 '-' 显示为方块的问题
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk

class MapHandler:
    def __init__(self, parent_frame):
        """
        parent_frame: tkinter Frame，用于放置地图画布和工具栏
        """
        self.parent = parent_frame
        self.gdfs = []          # 所有图层的GeoDataFrame
        self.layer_names = []   # 图层名称
        
        # 创建 Matplotlib 图形
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 添加工具栏
        self.toolbar = NavigationToolbar2Tk(self.canvas, parent_frame)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 存储高亮信息（用于清除）
        self.current_highlights = []  # 每个元素为 (layer_idx, [feature_indices])
        
    def load_shapefiles(self, directory='geodata'):
        """加载指定目录下的所有.shp文件"""
        shp_files = glob.glob(os.path.join(directory, "*.shp"))
        if not shp_files:
            raise FileNotFoundError("当前目录下没有找到任何.shp文件")
        
        self.gdfs.clear()
        self.layer_names.clear()
        for file in shp_files:
            try:
                gdf = gpd.read_file(file, encoding='utf-8')
                self.gdfs.append(gdf)
                name = os.path.splitext(os.path.basename(file))[0]
                self.layer_names.append(name)
                print(f"加载图层: {name}, 要素数: {len(gdf)}")
            except Exception as e:
                print(f"读取 {file} 失败: {e}")
        
        if not self.gdfs:
            raise ValueError("没有成功加载任何Shapefile")
    
    def plot_all_layers(self):
        """绘制所有图层"""
        self.ax.clear()
        colors = ['blue', 'green', 'red', 'cyan', 'magenta', 'yellow', 'black', 'orange', 'purple', 'brown']
        for i, (gdf, name) in enumerate(zip(self.gdfs, self.layer_names)):
            color = colors[i % len(colors)]
            geom_type = gdf.geometry.iloc[0].geom_type if len(gdf) > 0 else "Unknown"
            if geom_type == 'Point':
                gdf.plot(ax=self.ax, color=color, markersize=5, label=name, alpha=0.7)
            elif geom_type == 'LineString':
                gdf.plot(ax=self.ax, color=color, linewidth=1, label=name, alpha=0.7)
            else:
                gdf.plot(ax=self.ax, color=color, edgecolor='black', linewidth=0.5, label=name, alpha=0.5)
        
        self.ax.set_title("地理数据地图", fontsize=14)
        self.ax.legend(loc='upper right', fontsize=8)
        self.ax.set_xlabel("经度 / 投影X")
        self.ax.set_ylabel("纬度 / 投影Y")
        self.canvas.draw()
    
    def highlight_features(self, layer_idx, feature_indices, clear_existing=True):
        """高亮指定图层的某些要素（保留原始绘图）"""
        if clear_existing:
            self.clear_highlight(keep_record=False)
        
        if not feature_indices:
            return
        
        gdf = self.gdfs[layer_idx]
        for idx in feature_indices:
            geom = gdf.geometry.iloc[idx]
            if geom.is_empty:
                continue
            if geom.geom_type == 'Point':
                self.ax.scatter(geom.x, geom.y, s=100, facecolor='none', edgecolor='red', linewidth=2, zorder=10)
            elif geom.geom_type == 'LineString':
                x, y = geom.xy
                self.ax.plot(x, y, color='red', linewidth=3, alpha=0.8, zorder=10)
            else:
                x, y = geom.exterior.xy
                self.ax.fill(x, y, facecolor='red', edgecolor='darkred', alpha=0.3, linewidth=2, zorder=10)
        
        self.current_highlights.append((layer_idx, feature_indices))
        self.canvas.draw()
    
    def clear_highlight(self, keep_record=False):
        """清除高亮并重绘地图"""
        self.plot_all_layers()
        if not keep_record:
            self.current_highlights = []
    
    def batch_highlight(self, highlight_infos):
        """
        批量高亮多个要素（来自不同图层）
        highlight_infos: list of (layer_idx, feature_idx)
        """
        self.clear_highlight(keep_record=False)
        from collections import defaultdict
        layer_dict = defaultdict(list)
        for layer_idx, feat_idx in highlight_infos:
            layer_dict[layer_idx].append(feat_idx)
        for layer_idx, indices in layer_dict.items():
            self.highlight_features(layer_idx, indices, clear_existing=False)
