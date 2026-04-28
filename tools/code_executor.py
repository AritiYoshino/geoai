import ast
import contextlib
import io
import traceback
from dataclasses import dataclass, field

import geopandas as gpd
import numpy as np
import pandas as pd
from langchain_core.tools import tool
from shapely.geometry import Point

from .utils_geo import reproject_to_meters


MAX_CODE_CHARS = 8000
MAX_OUTPUT_CHARS = 3000

BANNED_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "locals",
    "open",
    "input",
    "help",
    "dir",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "os",
    "sys",
    "subprocess",
    "socket",
    "requests",
    "shutil",
    "pathlib",
}

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


class CodeSafetyError(ValueError):
    pass


@dataclass
class SpatialCodeRunResult:
    success: bool
    result_text: str
    stdout_text: str = ""
    error_text: str = ""
    result_value: object = None
    highlights: list = field(default_factory=list)
    code: str = ""


def create_execute_spatial_code_tool(handler):
    @tool
    def execute_spatial_code(task_description: str, code: str) -> str:
        """
        Execute constrained GeoPandas/Pandas spatial-analysis code.

        Available variables:
        - layers: dict[str, GeoDataFrame]
        - layer_names: list[str]
        - pd, gpd, np, Point, reproject_to_meters

        The code must assign the final output to RESULT.
        Optional:
        - HIGHLIGHTS = [(layer_name, feature_index), ...]
        """
        run = run_spatial_code(handler, task_description, code)
        if run.highlights:
            handler._store_highlights(run.highlights)
        return run.result_text

    return execute_spatial_code


def run_spatial_code(handler, task_description, code):
    if len(code) > MAX_CODE_CHARS:
        return SpatialCodeRunResult(
            success=False,
            result_text=f"代码过长，已拒绝执行。最大允许 {MAX_CODE_CHARS} 个字符。",
            error_text="code_too_long",
            code=code,
        )

    try:
        _validate_code(code)
    except CodeSafetyError as exc:
        return SpatialCodeRunResult(
            success=False,
            result_text=f"代码安全检查未通过: {str(exc)}",
            error_text=str(exc),
            code=code,
        )

    map_h = handler.map_handler
    layers = {name: gdf.copy() for name, gdf in zip(map_h.layer_names, map_h.gdfs)}
    local_env = {
        "RESULT": None,
        "HIGHLIGHTS": [],
        "layers": layers,
        "layer_names": list(map_h.layer_names),
        "pd": pd,
        "gpd": gpd,
        "np": np,
        "Point": Point,
        "reproject_to_meters": reproject_to_meters,
    }
    global_env = {"__builtins__": SAFE_BUILTINS}

    stdout = io.StringIO()
    try:
        compiled = compile(code, "<llm_spatial_code>", "exec")
        with contextlib.redirect_stdout(stdout):
            exec(compiled, global_env, local_env)
    except Exception:
        error_text = traceback.format_exc(limit=8)
        return SpatialCodeRunResult(
            success=False,
            result_text="代码执行失败，traceback 如下：\n" + error_text,
            stdout_text=stdout.getvalue().strip(),
            error_text=error_text,
            code=code,
        )

    highlights = _normalize_highlights(local_env.get("HIGHLIGHTS", []), map_h.layer_names)
    result_value = local_env.get("RESULT")
    if result_value is None:
        return SpatialCodeRunResult(
            success=False,
            result_text="未设置 RESULT。请在代码中将最终结果赋值给 RESULT。",
            stdout_text=stdout.getvalue().strip(),
            error_text="missing_result",
            highlights=highlights,
            code=code,
        )

    result_text = _compose_result_text(
        task_description=task_description,
        result_value=result_value,
        stdout_text=stdout.getvalue().strip(),
        highlights=highlights,
    )
    return SpatialCodeRunResult(
        success=True,
        result_text=result_text,
        stdout_text=stdout.getvalue().strip(),
        result_value=result_value,
        highlights=highlights,
        code=code,
    )


def _compose_result_text(task_description, result_value, stdout_text, highlights):
    parts = [f"任务: {task_description}"]
    if stdout_text:
        parts.append(f"stdout:\n{stdout_text[:MAX_OUTPUT_CHARS]}")
    parts.append(f"RESULT:\n{_format_result(result_value)}")
    if highlights:
        parts.append(f"已生成 {len(highlights)} 个地图高亮要素。")
    return "\n\n".join(parts)[:MAX_OUTPUT_CHARS]


def _validate_code(code):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CodeSafetyError("不允许 import；请使用系统已提供的 pd/gpd/np/layers。")
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise CodeSafetyError(f"不允许使用名称 {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise CodeSafetyError("不允许访问双下划线属性。")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_NAMES:
                raise CodeSafetyError(f"不允许调用 {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in {
                "remove",
                "unlink",
                "rmdir",
                "mkdir",
                "rename",
                "replace",
                "to_file",
                "to_csv",
                "to_excel",
                "to_json",
                "to_pickle",
            }:
                raise CodeSafetyError(f"不允许调用可能写文件的方法 {func.attr}")


def _normalize_highlights(raw_highlights, layer_names):
    layer_lookup = {name: idx for idx, name in enumerate(layer_names)}
    normalized = []
    for item in raw_highlights or []:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        layer_ref, feature_idx = item
        if isinstance(layer_ref, str):
            layer_idx = layer_lookup.get(layer_ref)
            if layer_idx is None:
                continue
        else:
            layer_idx = int(layer_ref)
        normalized.append((layer_idx, int(feature_idx)))
    return normalized


def _format_result(result):
    if result is None:
        return "未设置 RESULT。请在代码中将最终结果赋值给 RESULT。"
    if isinstance(result, (pd.DataFrame, gpd.GeoDataFrame)):
        if result.empty:
            return "空 DataFrame。"
        safe = result.drop(columns=["geometry"], errors="ignore").head(20)
        return safe.to_string(index=True)
    if isinstance(result, pd.Series):
        return result.head(30).to_string()
    if isinstance(result, (list, tuple, set)):
        values = list(result)[:30]
        suffix = "" if len(result) <= 30 else f"\n... 共 {len(result)} 项，仅显示前 30 项。"
        return "\n".join(str(item) for item in values) + suffix
    return str(result)
