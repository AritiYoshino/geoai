import re

from tools.code_executor import run_spatial_code


class CodeAgent:
    """Dedicated code agent for custom spatial-analysis programming tasks."""

    def __init__(self, llm, tool_state, max_retries=2):
        self.llm = llm
        self.tool_state = tool_state
        self.max_retries = max_retries

    def execute(self, task_description, code, trace):
        current_code = code
        last_run = None

        for attempt in range(1, self.max_retries + 2):
            trace.add("Code Agent", f"第 {attempt} 次执行空间分析代码。")
            run = run_spatial_code(self.tool_state, task_description, current_code)
            last_run = run

            if run.highlights:
                self.tool_state._store_highlights(run.highlights)

            if run.success:
                trace.add("Code Agent", "代码执行成功，结果已返回。")
                return run.result_text

            trace.add("Code Agent", run.result_text[:1200])
            if attempt > self.max_retries:
                break

            repaired_code = self._repair_code(
                task_description=task_description,
                original_code=current_code,
                error_text=run.error_text or run.result_text,
            )
            if not repaired_code or repaired_code.strip() == current_code.strip():
                trace.add("Code Agent", "未能生成有效修复代码，停止重试。")
                break
            current_code = repaired_code
            trace.add("Code Agent", "已生成修复代码，准备重试。")

        return last_run.result_text if last_run else "Code Agent 未能执行代码。"

    def _repair_code(self, task_description, original_code, error_text):
        prompt = f"""
你是一个专门修复 GeoPandas/Pandas 空间分析代码的编码智能体。
请修复下面的代码，并严格遵守这些约束：
- 不要 import 任何库
- 不要读写文件，不要访问系统命令
- 只能使用 layers, layer_names, pd, gpd, np, Point, reproject_to_meters
- 最终必须给 RESULT 赋值
- 如需高亮，可给 HIGHLIGHTS 赋值
- 只返回可直接执行的 Python 代码，不要解释，不要 Markdown

任务描述：
{task_description}

原始代码：
{original_code}

错误信息：
{error_text}
"""
        response = self.llm.invoke(prompt)
        content = getattr(response, "content", "") or ""
        return self._extract_code(content)

    def _extract_code(self, content):
        fenced = re.search(r"```(?:python)?\s*(.*?)```", content, flags=re.S)
        if fenced:
            return fenced.group(1).strip()
        return content.strip()
