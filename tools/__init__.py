# tools/__init__.py
from .buffer_tool import create_buffer_analysis_tool
from .clustering_tool import create_dbscan_tool, create_hotspot_tool
from .code_executor import create_execute_spatial_code_tool
from .detail import create_get_poi_by_index_tool
from .export_tool import create_export_tool
from .overlay_tool import create_overlay_layers_tool, create_spatial_join_tool
from .proximity_tool import create_nearest_neighbor_tool
from .query import create_query_poi_by_conditions_tool
from .nearby import (
    create_find_nearby_tool,
    create_find_nearby_point_filtered_tool,
    create_find_nearby_point_tool,
)
from .search import create_search_poi_tool
from .statistics_tool import create_statistics_tool

def create_tools(handler):
    return [
        create_execute_spatial_code_tool(handler),
        create_get_poi_by_index_tool(handler),
        create_search_poi_tool(handler),
        create_query_poi_by_conditions_tool(handler),
        create_find_nearby_tool(handler),
        create_find_nearby_point_tool(handler),
        create_find_nearby_point_filtered_tool(handler),
        create_buffer_analysis_tool(handler),
        create_overlay_layers_tool(handler),
        create_spatial_join_tool(handler),
        create_nearest_neighbor_tool(handler),
        create_dbscan_tool(handler),
        create_hotspot_tool(handler),
        create_statistics_tool(handler),
        create_export_tool(handler),
    ]
