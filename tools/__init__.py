# tools/__init__.py
from .code_executor import create_execute_spatial_code_tool
from .detail import create_get_poi_by_index_tool
from .search import create_search_poi_tool
from .query import create_query_poi_by_conditions_tool
from .nearby import (
    create_find_nearby_tool,
    create_find_nearby_point_filtered_tool,
    create_find_nearby_point_tool,
)

def create_tools(handler):
    return [
        create_execute_spatial_code_tool(handler),
        create_get_poi_by_index_tool(handler),
        create_search_poi_tool(handler),
        create_query_poi_by_conditions_tool(handler),
        create_find_nearby_tool(handler),
        create_find_nearby_point_tool(handler),
        create_find_nearby_point_filtered_tool(handler),
    ]
