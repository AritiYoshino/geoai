# ai_handler.py - 多智能体版本（字段验证优化）
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools import create_tools

class AIHandler:
    def __init__(self, api_key, map_handler):
        self.map_handler = map_handler
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.7,
            api_key=api_key,
            timeout=30,
            max_retries=2,
        )
        self.tools = create_tools(self)
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        schema_info = self._get_schema_info()
        self.system_message = SystemMessage(content=f"""
你是一个GIS多智能体地理信息助手。你可以调用以下工具帮助用户分析地理数据：

1. **search_poi** - 关键词搜索POI（兴趣点），在所有文本字段中模糊匹配
2. **query_poi_by_conditions** - 按属性条件精确查询POI，需指定图层和条件表达式
3. **find_nearby** - 图层间邻近分析
4. **find_nearby_point** - 以单个要素为中心的邻近搜索

## 可用数据图层及字段（必须严格使用以下字段名，禁止猜测）：
{schema_info}

## 特别说明 - 住宿服务图层字段：
住宿服务图层包含字段：name, type, address, lng, lat, province, city, district
当用户查询特定行政区的住宿时，必须使用 district 字段，例如：district=='锦江区'

## 使用规则：
- **优先使用 query_poi_by_conditions** 处理涉及属性筛选的查询（如“锦江区的酒店”）。条件表达式中的列名必须完全匹配上面列出的字段名。
- 若条件查询返回错误提示“不存在的字段名”，请仔细阅读错误中提供的可用字段列表，修正后重试。
- 仅在不确定字段名或需要全文搜索时才使用 search_poi。
- 当用户询问“某个具体地点附近的设施”时，分两步：先 search_poi 定位参考点，再 find_nearby_point。
- 回答要简洁明了，并在返回结果后提示“已在地图上高亮显示匹配要素”。
""")

    def _get_schema_info(self):
        info_lines = []
        for gdf, name in zip(self.map_handler.gdfs, self.map_handler.layer_names):
            cols = gdf.select_dtypes(include=['object', 'number']).columns.tolist()
            if 'geometry' in cols:
                cols.remove('geometry')
            # 显示前12个字段，让AI有更多信息
            info_lines.append(f"  - {name}: {', '.join(cols[:12])}" + ("..." if len(cols) > 12 else ""))
        return "\n".join(info_lines) if info_lines else "无图层信息"

    def _store_highlights(self, highlight_infos):
        self._last_highlights = highlight_infos

    def _clear_highlights(self):
        if hasattr(self, '_last_highlights'):
            delattr(self, '_last_highlights')

    def process_message(self, user_input, highlight_callback):
        messages = [self.system_message, HumanMessage(content=user_input)]
        max_iterations = 5
        final_answer = ""

        try:
            for iteration in range(max_iterations):
                total_chars = sum(len(str(msg)) for msg in messages)
                if total_chars > 80000:
                    final_answer = "返回的结果过多，为避免超出系统限制，已在地图上高亮显示所有匹配要素。请尝试缩小查询范围。"
                    break

                try:
                    response = self.llm_with_tools.invoke(messages)
                except Exception as e:
                    final_answer = f"调用AI服务失败（可能超时或网络问题）: {str(e)}"
                    break

                messages.append(response)

                if response.content and not (hasattr(response, 'tool_calls') and response.tool_calls):
                    final_answer = response.content
                    break

                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['args']
                        tool_func = next((t for t in self.tools if t.name == tool_name), None)
                        if tool_func:
                            try:
                                result = tool_func.invoke(tool_args)
                                if hasattr(self, '_last_highlights') and self._last_highlights:
                                    highlight_callback(self._last_highlights)
                                    self._clear_highlights()
                            except Exception as e:
                                result = f"工具执行出错: {str(e)}"
                            if len(result) > 2000:
                                result = result[:2000] + "...(结果已截断，完整数据已在地图上高亮)"
                            messages.append(ToolMessage(content=result, tool_call_id=tool_call['id']))
                        else:
                            messages.append(ToolMessage(content=f"未知工具: {tool_name}", tool_call_id=tool_call['id']))
                    continue
                else:
                    final_answer = "抱歉，我无法处理这个请求。"
                    break
            else:
                try:
                    final_response = self.llm.invoke(messages)
                    final_answer = final_response.content
                except Exception as e:
                    final_answer = f"生成最终回答时出错: {str(e)}"
        except Exception as e:
            final_answer = f"处理过程中发生异常: {str(e)}"
            import traceback
            traceback.print_exc()

        return final_answer