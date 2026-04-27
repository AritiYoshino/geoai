import ast
import contextlib
import io
import traceback

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


def create_execute_spatial_code_tool(handler):
    map_h = handler.map_handler

    @tool
    def execute_spatial_code(task_description: str, code: str) -> str:
        """
        在受控环境中执行 LLM 生成的 GeoPandas/Pandas 空间分析代码。

        适合现有固定工具无法完成的分析，例如分组统计、批量缓冲区计数、
        自定义空间关系计算等。代码不能 import，不能读写文件，不能调用系统命令。

        可用变量：
        - layers: dict[str, GeoDataFrame]，键为图层名
        - layer_names: list[str]
        - pd, gpd, np, Point, reproject_to_meters

        代码必须把最终结果赋值给 RESULT。
        可选：把需要地图高亮的要素赋值给 HIGHLIGHTS，格式为
        [(layer_name, feature_index), ...] 或 [(layer_idx, feature_index), ...]。
        """
        if len(code) > MAX_CODE_CHARS:
            return f"代码过长，已拒绝执行。最大允许 {MAX_CODE_CHARS} 字符。"

        try:
            _validate_code(code)
        except CodeSafetyError as exc:
            return f"代码安全检查未通过: {str(exc)}"

        layers = {
            name: gdf.copy()
            for name, gdf in zip(map_h.layer_names, map_h.gdfs)
        }
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
            return (
                "代码执行失败，traceback 如下：\n"
                + traceback.format_exc(limit=8)
            )

        highlights = _normalize_highlights(local_env.get("HIGHLIGHTS", []), map_h.layer_names)
        if highlights:
            handler._store_highlights(highlights)

        result_text = _format_result(local_env.get("RESULT"))
        stdout_text = stdout.getvalue().strip()
        parts = [f"任务: {task_description}"]
        if stdout_text:
            parts.append(f"stdout:\n{stdout_text[:MAX_OUTPUT_CHARS]}")
        parts.append(f"RESULT:\n{result_text}")
        if highlights:
            parts.append(f"已生成 {len(highlights)} 个地图高亮要素。")
        return "\n\n".join(parts)[:MAX_OUTPUT_CHARS]

    return execute_spatial_code


def _validate_code(code):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CodeSafetyError("不允许 import；请使用系统已提供的 pd/gpd/np/layers。")
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise CodeSafetyError(f"不允许使用名称: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise CodeSafetyError("不允许访问双下划线属性。")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_NAMES:
                raise CodeSafetyError(f"不允许调用: {func.id}")
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
                raise CodeSafetyError(f"不允许调用可能写文件的方法: {func.attr}")


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
        suffix = "" if len(result) <= 30 else f"\n... 共 {len(result)} 项，仅显示前 30 项"
        return "\n".join(str(item) for item in values) + suffix
    return str(result)
