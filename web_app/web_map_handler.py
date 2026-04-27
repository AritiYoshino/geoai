import json
import os

import geopandas as gpd


class BrowserMapHandler:
    """Backend map state provider for the browser MapLibre frontend."""

    def __init__(self):
        self.gdfs = []
        self.layer_names = []
        self.current_highlights = []

    def load_shapefiles(self, directory="geodata"):
        shp_files = [
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.lower().endswith(".shp")
        ]
        if not shp_files:
            raise FileNotFoundError("当前目录下没有找到任何 shp 文件")

        self.gdfs.clear()
        self.layer_names.clear()
        for path in sorted(shp_files):
            gdf = gpd.read_file(path, encoding="utf-8")
            self.gdfs.append(gdf)
            self.layer_names.append(os.path.splitext(os.path.basename(path))[0])

        if not self.gdfs:
            raise ValueError("没有成功加载任何 Shapefile")

    def plot_all_layers(self):
        return self.layers_payload()

    def layers_payload(self):
        payload = []
        for idx, (gdf, name) in enumerate(zip(self.gdfs, self.layer_names)):
            display_gdf = self._to_wgs84(gdf.copy())
            display_gdf["__feature_index"] = [int(i) for i in gdf.index]
            payload.append(
                {
                    "layer_index": idx,
                    "name": name,
                    "feature_count": int(len(gdf)),
                    "geojson": json.loads(display_gdf.to_json()),
                }
            )
        return payload

    def batch_highlight(self, highlight_infos):
        self.current_highlights = list(highlight_infos or [])

    def highlight_features(self, layer_idx, feature_indices, clear_existing=True):
        infos = [(layer_idx, idx) for idx in feature_indices]
        self.batch_highlight(infos)

    def clear_highlight(self, keep_record=False):
        self.current_highlights = []

    def highlights_geojson(self):
        features = []
        for layer_idx, feat_idx in self.current_highlights:
            if layer_idx < 0 or layer_idx >= len(self.gdfs):
                continue
            gdf = self.gdfs[layer_idx]
            if feat_idx not in gdf.index:
                if 0 <= feat_idx < len(gdf):
                    row = gdf.iloc[feat_idx]
                else:
                    continue
            else:
                row = gdf.loc[feat_idx]
            one = gpd.GeoDataFrame([row], geometry="geometry", crs=gdf.crs)
            one = self._to_wgs84(one)
            one["__feature_index"] = int(feat_idx)
            one["__layer_name"] = self.layer_names[layer_idx]
            features.extend(json.loads(one.to_json()).get("features", []))
        return {"type": "FeatureCollection", "features": features}

    def _to_wgs84(self, gdf):
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326", allow_override=True)
        if gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
