# tools/__init__.py
import time


def _startup_timing(label, start):
    print(f"[startup][timing] {label}: {time.perf_counter() - start:.3f}s", flush=True)


_module_start = time.perf_counter()
_step = time.perf_counter()
from .buffer_tool import create_buffer_analysis_tool
_startup_timing("import tools.buffer_tool", _step)
_step = time.perf_counter()
from .clustering_tool import create_dbscan_tool, create_hotspot_tool
_startup_timing("import tools.clustering_tool", _step)
_step = time.perf_counter()
from .code_executor import create_execute_spatial_code_tool
_startup_timing("import tools.code_executor", _step)
_step = time.perf_counter()
from .detail import create_get_poi_by_index_tool
_startup_timing("import tools.detail", _step)
_step = time.perf_counter()
from .export_tool import create_export_tool
_startup_timing("import tools.export_tool", _step)
_step = time.perf_counter()
from .overlay_tool import create_overlay_layers_tool, create_spatial_join_tool
_startup_timing("import tools.overlay_tool", _step)
_step = time.perf_counter()
from .proximity_tool import create_nearest_neighbor_tool
_startup_timing("import tools.proximity_tool", _step)
_step = time.perf_counter()
from .query import create_query_poi_by_conditions_tool
_startup_timing("import tools.query", _step)
_step = time.perf_counter()
from .nearby import (
    create_find_nearby_tool,
    create_find_nearby_point_filtered_tool,
    create_find_nearby_point_tool,
)
_startup_timing("import tools.nearby", _step)
_step = time.perf_counter()
from .search import create_search_poi_tool
_startup_timing("import tools.search", _step)
_step = time.perf_counter()
from .statistics_tool import create_statistics_tool
_startup_timing("import tools.statistics_tool", _step)
_startup_timing("import tools package total", _module_start)

def create_tools(handler):
    tools = []
    for name, factory in (
        ("execute_spatial_code", create_execute_spatial_code_tool),
        ("get_poi_by_index", create_get_poi_by_index_tool),
        ("search_poi", create_search_poi_tool),
        ("query_poi_by_conditions", create_query_poi_by_conditions_tool),
        ("find_nearby", create_find_nearby_tool),
        ("find_nearby_point", create_find_nearby_point_tool),
        ("find_nearby_point_filtered", create_find_nearby_point_filtered_tool),
        ("buffer_analysis", create_buffer_analysis_tool),
        ("overlay_layers", create_overlay_layers_tool),
        ("spatial_join", create_spatial_join_tool),
        ("nearest_neighbor", create_nearest_neighbor_tool),
        ("dbscan", create_dbscan_tool),
        ("hotspot", create_hotspot_tool),
        ("statistics", create_statistics_tool),
        ("export", create_export_tool),
    ):
        start = time.perf_counter()
        tools.append(factory(handler))
        _startup_timing(f"create tool {name}", start)
    return tools
