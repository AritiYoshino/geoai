import os


MAX_PREVIEW_ROWS = 20
MAX_HIGHLIGHTS = 50


def find_layer(map_handler, layer_name):
    for idx, (gdf, name) in enumerate(zip(map_handler.gdfs, map_handler.layer_names)):
        if name == layer_name:
            return idx, gdf, name
    return None, None, None


def distance_to_meters(distance, unit):
    return distance * 1000 if str(unit).lower() == "km" else distance


def preview_frame(gdf):
    if gdf is None or gdf.empty:
        return "空结果"
    safe = gdf.drop(columns=["geometry"], errors="ignore").head(MAX_PREVIEW_ROWS)
    return safe.to_string(index=True)


def ensure_export_dir():
    export_dir = os.path.join("data", "exports")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def store_generated_result(handler, name, gdf):
    handler._store_generated_result(name, gdf.copy())


def highlight_indices(handler, layer_idx, indices):
    picked = [(layer_idx, int(idx)) for idx in list(indices)[:MAX_HIGHLIGHTS]]
    if picked:
        handler._store_highlights(picked)
