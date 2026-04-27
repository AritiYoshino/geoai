# tools/__init__.py
from .search import create_search_poi_tool
from .query import create_query_poi_by_conditions_tool
from .nearby import create_find_nearby_tool, create_find_nearby_point_tool

def create_tools(handler):
    return [
        create_search_poi_tool(handler),
        create_query_poi_by_conditions_tool(handler),
        create_find_nearby_tool(handler),
        create_find_nearby_point_tool(handler),
    ]