from dataclasses import dataclass, field


@dataclass
class ToolExecution:
    name: str
    args: dict
    result: str
    pois: list = field(default_factory=list)
    highlights: list = field(default_factory=list)


class SpatialAnalystAgent:
    """Runs spatial reasoning by invoking GIS tools through the LLM tool API."""

    def __init__(self, llm, tools, tool_state):
        self.llm = llm
        self.tools = tools
        self.tool_state = tool_state
        self.llm_with_tools = llm.bind_tools(tools)

    def think(self, messages, trace, iteration):
        trace.add("Spatial Analyst Agent", f"第 {iteration} 轮：根据计划选择工具或生成回答。")
        return self.llm_with_tools.invoke(messages)

    def execute_tool(self, tool_call, trace):
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_func = next((tool for tool in self.tools if tool.name == tool_name), None)
        trace.add("Spatial Analyst Agent", f"调用工具 {tool_name}，参数：{tool_args}")

        if not tool_func:
            result = f"未知工具: {tool_name}"
            return ToolExecution(tool_name, tool_args, result)

        try:
            result = tool_func.invoke(tool_args)
        except Exception as exc:
            result = f"工具执行出错: {str(exc)}"

        pois = getattr(self.tool_state, "_last_pois", [])
        highlights = getattr(self.tool_state, "_last_highlights", [])
        if hasattr(self.tool_state, "_last_pois"):
            delattr(self.tool_state, "_last_pois")
        if hasattr(self.tool_state, "_last_highlights"):
            delattr(self.tool_state, "_last_highlights")

        trace.add("Tool Feedback", str(result)[:1200])
        return ToolExecution(tool_name, tool_args, str(result), pois, highlights)
