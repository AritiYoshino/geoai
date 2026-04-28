import re

from core.jsonl_logger import log_code, log_error
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
            trace.add("Code Agent / Status", f"第 {attempt} 次执行空间分析代码。")
            trace.add("Code Agent / Generated Code", current_code or "# 未生成代码")
            run = run_spatial_code(self.tool_state, task_description, current_code)
            last_run = run

            log_code(
                {
                    "task_description": task_description,
                    "attempt": attempt,
                    "success": bool(run.success),
                    "code": current_code,
                    "result_preview": str(run.result_text)[:1000],
                    "error_text": str(run.error_text or "")[:1000],
                }
            )

            if run.highlights:
                self.tool_state._store_highlights(run.highlights)

            if run.success:
                trace.add("Code Agent / Execution", "代码执行成功，结果已返回。")
                return run.result_text

            trace.add("Code Agent / Execution", run.result_text[:1200])
            if attempt > self.max_retries:
                break

            repaired_code = self._repair_code(
                task_description=task_description,
                original_code=current_code,
                error_text=run.error_text or run.result_text,
            )
            if not repaired_code or repaired_code.strip() == current_code.strip():
                trace.add("Code Agent / Status", "未能生成有效修复代码，停止重试。")
                break
            current_code = repaired_code
            trace.add("Code Agent / Status", "已生成修复代码，准备重试。")

        if last_run and not last_run.success:
            log_error(
                {
                    "source": "code_agent.execute",
                    "task_description": task_description,
                    "error": str(last_run.error_text or last_run.result_text)[:1000],
                }
            )
        return last_run.result_text if last_run else "Code Agent 未能执行代码。"

    def _repair_code(self, task_description, original_code, error_text):
        prompt = f"""
你是一个 GeoPandas/Pandas 空间分析代码修复器。请修复下面这段代码。

约束：
- 不允许 import
- 不允许读写文件
- 只能使用 layers, layer_names, pd, gpd, np, Point, reproject_to_meters
- 最终结果必须赋值给 RESULT
- 如需地图高亮，可设置 HIGHLIGHTS
- 只返回 Python 代码，不要返回解释

任务：
{task_description}

原代码：
{original_code}

错误信息：
{error_text}
"""
        try:
            response = self.llm.invoke(prompt)
        except Exception as exc:
            log_error(
                {
                    "source": "code_agent.repair",
                    "task_description": task_description,
                    "error": str(exc),
                }
            )
            return ""
        content = getattr(response, "content", "") or ""
        return self._extract_code(content)

    def _extract_code(self, content):
        fenced = re.search(r"```(?:python)?\s*(.*?)```", content, flags=re.S)
        if fenced:
            return fenced.group(1).strip()
        return content.strip()
