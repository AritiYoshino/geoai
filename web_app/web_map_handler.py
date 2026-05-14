import json
import os

import geopandas as gpd


LARGE_LAYER_THRESHOLD = 10000
MIN_ZOOM_FOR_LARGE_LAYER = 12


class BrowserMapHandler:
    """Backend map state provider for the browser MapLibre frontend."""

    def __init__(self):
        self.layer_records = []
        self.raster_records = []
        self.current_highlights = []

    @property
    def layer_names(self):
        return [record["name"] for record in self.layer_records]

    @property
    def gdfs(self):
        return [self.get_gdf(record["name"]) for record in self.layer_records]

    def load_geojson_layers(self, directory=os.path.join("data", "geodata")):
        geojson_files = [
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.lower().endswith(".geojson")
        ]
        if not geojson_files:
            raise FileNotFoundError(f"当前目录 {directory} 下没有找到任何 .geojson 文件")

        self.layer_records.clear()
        for path in sorted(geojson_files):
            meta = self._read_geojson_metadata(path)
            self.layer_records.append(
                {
                    "name": os.path.splitext(os.path.basename(path))[0],
                    "path": path,
                    "feature_count": meta["feature_count"],
                    "fields": meta["fields"],
                    "geometry_types": meta["geometry_types"],
                    "bbox": meta["bbox"],
                    "crs": meta["crs"],
                    "gdf": None,
                }
            )

        if not self.layer_records:
            raise ValueError("没有成功加载任何 GeoJSON 图层元信息。")

    def plot_all_layers(self):
        return self.layers_payload()

    def layers_payload(self):
        payload = []
        for idx, record in enumerate(self.layer_records):
            payload.append(
                {
                    "layer_index": idx,
                    "name": record["name"],
                    "feature_count": int(record["feature_count"]),
                    "fields": list(record["fields"]),
                    "geometry_types": list(record["geometry_types"]),
                    "bbox": list(record["bbox"]) if record["bbox"] else [],
                    "crs": record["crs"],
                    "auto_load_recommended": int(record["feature_count"]) < LARGE_LAYER_THRESHOLD,
                    "is_large_layer": int(record["feature_count"]) >= LARGE_LAYER_THRESHOLD,
                    "min_zoom": MIN_ZOOM_FOR_LARGE_LAYER if int(record["feature_count"]) >= LARGE_LAYER_THRESHOLD else 0,
                    "is_generated": bool(record.get("is_generated")),
                    "auto_visible": bool(record.get("auto_visible")),
                    "visualization_style": dict(record.get("visualization_style") or {}),
                }
            )
        for idx, record in enumerate(self.raster_records, start=len(payload)):
            payload.append(
                {
                    "layer_index": idx,
                    "name": record["name"],
                    "feature_count": 1,
                    "fields": [],
                    "geometry_types": ["Raster"],
                    "bbox": list(record["bbox"]) if record["bbox"] else [],
                    "crs": record.get("crs", "EPSG:4326"),
                    "auto_load_recommended": True,
                    "is_large_layer": False,
                    "min_zoom": 0,
                    "is_generated": True,
                    "auto_visible": bool(record.get("auto_visible")),
                    "visualization_style": dict(record.get("visualization_style") or {}),
                    "layer_type": "raster",
                    "raster_url": record["url"],
                }
            )
        return payload

    def add_generated_layer(self, name, gdf, visualization_style=None, auto_visible=True):
        display_gdf = self._to_wgs84(gdf.copy())
        meta = self._metadata_from_gdf(display_gdf)
        record = {
            "name": name,
            "path": None,
            "feature_count": meta["feature_count"],
            "fields": meta["fields"],
            "geometry_types": meta["geometry_types"],
            "bbox": meta["bbox"],
            "crs": meta["crs"],
            "gdf": display_gdf,
            "is_generated": True,
            "auto_visible": auto_visible,
            "visualization_style": visualization_style or {},
        }

        existing = self._get_record(name)
        if existing is None:
            self.layer_records.append(record)
        else:
            existing.update(record)

    def add_generated_raster_layer(self, name, url, bbox, visualization_style=None, auto_visible=True):
        record = {
            "name": name,
            "url": url,
            "bbox": list(bbox) if bbox else [],
            "crs": "EPSG:4326",
            "is_generated": True,
            "auto_visible": auto_visible,
            "visualization_style": visualization_style or {"kind": "raster"},
        }
        existing = self._get_raster_record(name)
        if existing is None:
            self.raster_records.append(record)
        else:
            existing.update(record)

    def layer_data_payload(self, layer_name, bbox=None, zoom=None):
        record = self._get_record(layer_name)
        if record is None:
            raise ValueError(f"未找到图层 {layer_name}")

        if (
            not record.get("is_generated")
            and record["feature_count"] >= LARGE_LAYER_THRESHOLD
            and zoom is not None
            and float(zoom) < MIN_ZOOM_FOR_LARGE_LAYER
        ):
            return {
                "name": record["name"],
                "geojson": {"type": "FeatureCollection", "features": []},
                "feature_count": int(record["feature_count"]),
                "returned_count": 0,
                "deferred": True,
                "message": f"图层较大，请放大到 {MIN_ZOOM_FOR_LARGE_LAYER} 级后再加载。",
            }

        gdf = self.get_gdf(layer_name)
        filtered = self._filter_by_bbox(gdf, bbox)
        display_gdf = self._to_wgs84(filtered.copy())
        display_gdf["__feature_index"] = [int(i) for i in filtered.index]

        return {
            "name": record["name"],
            "geojson": json.loads(display_gdf.to_json()),
            "feature_count": int(record["feature_count"]),
            "returned_count": int(len(display_gdf)),
            "deferred": False,
            "message": "",
        }

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
            if layer_idx < 0 or layer_idx >= len(self.layer_records):
                continue
            gdf = self.get_gdf(self.layer_records[layer_idx]["name"])
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
            one["__layer_name"] = self.layer_records[layer_idx]["name"]
            features.extend(json.loads(one.to_json()).get("features", []))
        return {"type": "FeatureCollection", "features": features}

    def get_gdf(self, layer_name):
        record = self._get_record(layer_name)
        if record is None:
            raise ValueError(f"未找到图层 {layer_name}")
        if record["gdf"] is None:
            if not record.get("path"):
                raise ValueError(f"鍥惧眰 {layer_name} 娌℃湁鍙鍙栫殑鏁版嵁婧?")
            gdf = gpd.read_file(record["path"])
            record["gdf"] = self._to_wgs84(gdf)
        return record["gdf"]

    def _get_record(self, layer_name):
        for record in self.layer_records:
            if record["name"] == layer_name:
                return record
        return None

    def _get_raster_record(self, layer_name):
        for record in self.raster_records:
            if record["name"] == layer_name:
                return record
        return None

    def _filter_by_bbox(self, gdf, bbox):
        if not bbox:
            return gdf
        minx, miny, maxx, maxy = bbox
        try:
            return gdf.cx[minx:maxx, miny:maxy]
        except Exception:
            return gdf

    def _read_geojson_metadata(self, path):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        features = payload.get("features", [])
        feature_count = len(features)
        bbox = payload.get("bbox") or self._compute_bbox(features)
        fields = []
        geometry_types = []
        seen_fields = set()
        seen_geom = set()

        for feature in features[: min(feature_count, 200)]:
            properties = feature.get("properties", {}) or {}
            geometry = feature.get("geometry", {}) or {}
            geom_type = geometry.get("type", "Unknown")
            if geom_type not in seen_geom:
                seen_geom.add(geom_type)
                geometry_types.append(geom_type)
            for key in properties.keys():
                if key not in seen_fields:
                    seen_fields.add(key)
                    fields.append(key)

        return {
            "feature_count": feature_count,
            "fields": fields,
            "geometry_types": geometry_types or ["Unknown"],
            "bbox": bbox or [0, 0, 0, 0],
            "crs": "EPSG:4326",
        }

    def _metadata_from_gdf(self, gdf):
        fields = [column for column in gdf.columns if column != gdf.geometry.name]
        geometry_types = []
        for geom_type in gdf.geometry.geom_type.dropna().unique().tolist():
            if geom_type not in geometry_types:
                geometry_types.append(geom_type)
        bounds = gdf.total_bounds.tolist() if not gdf.empty else []
        return {
            "feature_count": int(len(gdf)),
            "fields": fields,
            "geometry_types": geometry_types or ["Unknown"],
            "bbox": bounds,
            "crs": gdf.crs.to_string() if gdf.crs else "EPSG:4326",
        }

    def _compute_bbox(self, features):
        minx = miny = maxx = maxy = None
        for feature in features:
            geometry = feature.get("geometry", {}) or {}
            for x, y in self._iter_coords(geometry.get("coordinates", [])):
                minx = x if minx is None else min(minx, x)
                miny = y if miny is None else min(miny, y)
                maxx = x if maxx is None else max(maxx, x)
                maxy = y if maxy is None else max(maxy, y)
        if minx is None:
            return []
        return [minx, miny, maxx, maxy]

    def _iter_coords(self, coords):
        if not isinstance(coords, list):
            return
        if len(coords) >= 2 and all(isinstance(item, (int, float)) for item in coords[:2]):
            yield coords[0], coords[1]
            return
        for item in coords:
            yield from self._iter_coords(item)

    def _to_wgs84(self, gdf):
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326", allow_override=True)
        if gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
