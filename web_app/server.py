import glob
import json
import mimetypes
import os
import shutil
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from dotenv import load_dotenv

from core.jsonl_logger import log_error


EXPERIMENT_OUTPUT_ROOT = os.path.join("experiments", "experiment_outputs")
EXP1_OUTPUT_DIR = os.path.join(EXPERIMENT_OUTPUT_ROOT, "exp1")
EXP2_OUTPUT_DIR = os.path.join(EXPERIMENT_OUTPUT_ROOT, "exp2")
EXP3_OUTPUT_DIR = os.path.join(EXPERIMENT_OUTPUT_ROOT, "exp3")
EXP4_OUTPUT_DIR = os.path.join(EXPERIMENT_OUTPUT_ROOT, "exp4")


def startup_log(message):
    print(f"[startup] {message}", flush=True)


def startup_timing(label, start):
    startup_log(f"[timing] {label}: {time.perf_counter() - start:.3f}s")


class WebGISAppState:
    def __init__(self):
        state_start = time.perf_counter()
        step = time.perf_counter()
        startup_log("loading .env")
        load_dotenv()
        startup_timing("load .env", step)
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("请在 .env 文件中设置 DEEPSEEK_API_KEY")

        step = time.perf_counter()
        startup_log("importing map handler")
        from web_app.web_map_handler import BrowserMapHandler
        startup_timing("import map handler", step)

        step = time.perf_counter()
        startup_log("initializing map handler")
        self.map_handler = BrowserMapHandler()
        startup_timing("initialize map handler", step)

        step = time.perf_counter()
        startup_log("loading GeoJSON layers from data/geodata")
        self.map_handler.load_geojson_layers(os.path.join("data", "geodata"))
        startup_timing("load GeoJSON layer metadata", step)

        step = time.perf_counter()
        startup_log("importing AI handler and agent modules")
        from ai_handler import AIHandler
        startup_timing("import AI handler and agent modules", step)

        step = time.perf_counter()
        startup_log("initializing AI handler and agents")
        self.ai_handler = AIHandler(api_key, self.map_handler)
        startup_timing("initialize AI handler and agents", step)
        startup_log("application state ready")
        startup_timing("application state total", state_start)
        self._exp1_lock = threading.Lock()
        self._exp1_running = False
        self._exp1_latest = None  # 缓存实验一的最新结果
        self._exp2_running = False
        self._exp2_latest = None  # 缓存实验二的最新结果
        self._exp3_running = False
        self._exp3_latest = None  # 缓存实验三的最新结果
        self._exp4_running = False
        self._exp4_latest = None  # 缓存实验四的最新结果

    def has_running_experiment(self):
        return any(
            (
                self._exp1_running,
                self._exp2_running,
                self._exp3_running,
                self._exp4_running,
            )
        )


STATE = None


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    idle_shutdown_seconds = 0
    last_request_at = None

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def touch(self):
        self.last_request_at = time.monotonic()


class WebGISRequestHandler(SimpleHTTPRequestHandler):
    server_version = "GeoAIWeb/0.2"

    def do_GET(self):
        self.server.touch()
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self._send_static("index.html")
            elif parsed.path == "/gis":
                self._send_static("gis.html")
            elif parsed.path == "/experiment":
                self._send_static("experiment.html")
            elif parsed.path.startswith("/static/"):
                self._send_static(parsed.path.removeprefix("/static/"))
            elif parsed.path == "/api/layers":
                self._send_json({"layers": STATE.map_handler.layers_payload()})
            elif parsed.path == "/api/layer_data":
                self._handle_layer_data(query)
            elif parsed.path == "/api/highlights":
                self._send_json({"geojson": STATE.map_handler.highlights_geojson()})
            elif parsed.path == "/api/trace":
                self._send_json({"trace": STATE.ai_handler.get_trace_text()})
            elif parsed.path == "/api/ace-panel":
                self._send_json({"ace_panel": STATE.ai_handler.get_ace_panel()})
            elif parsed.path == "/api/experience":
                self._send_json({"summary": STATE.ai_handler.get_experience_summary()})
            elif parsed.path == "/api/sessions":
                self._send_json(
                    {
                        "current": STATE.ai_handler.get_current_session(),
                        "sessions": STATE.ai_handler.list_sessions(),
                    }
                )
            elif parsed.path == "/api/experience-banks":
                self._send_json(
                    {
                        "active": STATE.ai_handler.get_active_experience_bank(),
                        "banks": STATE.ai_handler.list_experience_banks(),
                    }
                )
            elif parsed.path == "/api/experiment/exp1/data":
                self._handle_exp1_data(query)
            elif parsed.path == "/api/experiment/exp1/tasks":
                self._send_static_file(os.path.join("experiments", "exp1", "exp1_suite.json"))
            elif parsed.path == "/api/experiment/exp1/results":
                self._handle_exp1_results()
            elif parsed.path == "/api/experiment/exp1/export":
                self._handle_exp_export(query, "exp1_")
            elif parsed.path == "/api/experiment/exp2/data":
                self._handle_exp2_data(query)
            elif parsed.path == "/api/experiment/exp2/tasks":
                self._send_static_file(os.path.join("experiments", "exp2", "exp2_suite.json"))
            elif parsed.path == "/api/experiment/exp2/results":
                self._handle_exp2_results()
            elif parsed.path == "/api/experiment/exp2/export":
                self._handle_exp_export(query, "exp2_")
            elif parsed.path == "/api/experiment/exp3/data":
                self._handle_exp3_data(query)
            elif parsed.path == "/api/experiment/exp3/tasks":
                self._send_static_file(os.path.join("experiments", "exp3", "exp3_suite.json"))
            elif parsed.path == "/api/experiment/exp3/results":
                self._handle_exp3_results()
            elif parsed.path == "/api/experiment/exp3/export":
                self._handle_exp_export(query, "exp3_")
            elif parsed.path == "/api/experiment/exp4/data":
                self._handle_exp4_data(query)
            elif parsed.path == "/api/experiment/exp4/tasks":
                self._send_static_file(os.path.join("experiments", "exp4", "exp4_suite.json"))
            elif parsed.path == "/api/experiment/exp4/results":
                self._handle_exp4_results()
            elif parsed.path == "/api/experiment/exp4/export":
                self._handle_exp_export(query, "exp4_")
            elif parsed.path == "/api/thesis/evidence":
                self._handle_thesis_evidence()
            else:
                self.send_error(404, "Not found")
        except Exception as exc:
            log_error({"source": "http_get", "path": parsed.path, "error": str(exc)})
            self._send_json({"error": str(exc)}, status=500)

    def do_POST(self):
        self.server.touch()
        parsed = urlparse(self.path)
        try:
            data = self._read_json()
            if parsed.path == "/api/chat":
                self._handle_chat(data)
            elif parsed.path == "/api/feedback":
                result = STATE.ai_handler.submit_feedback(
                    data.get("type", "incorrect"),
                    data.get("correction", ""),
                )
                self._send_json({"result": result, "experience": STATE.ai_handler.get_experience_summary()})
            elif parsed.path == "/api/sessions/new":
                session = STATE.ai_handler.new_session()
                STATE.map_handler.clear_highlight()
                self._send_json({"session": session})
            elif parsed.path == "/api/sessions/switch":
                session = STATE.ai_handler.switch_session(data["session_id"])
                STATE.map_handler.clear_highlight()
                self._send_json({"session": session})
            elif parsed.path == "/api/sessions/rename":
                session = STATE.ai_handler.rename_session(data["session_id"], data.get("title", ""))
                self._send_json(
                    {
                        "session": session,
                        "current": STATE.ai_handler.get_current_session(),
                        "sessions": STATE.ai_handler.list_sessions(),
                    }
                )
            elif parsed.path == "/api/sessions/delete":
                session = STATE.ai_handler.delete_session(data["session_id"])
                STATE.map_handler.clear_highlight()
                self._send_json(
                    {
                        "session": session,
                        "current": STATE.ai_handler.get_current_session(),
                        "sessions": STATE.ai_handler.list_sessions(),
                        "trace": STATE.ai_handler.get_trace_text(),
                        "ace_panel": STATE.ai_handler.get_ace_panel(),
                    }
                )
            elif parsed.path == "/api/highlights/clear":
                STATE.map_handler.clear_highlight()
                self._send_json({"geojson": STATE.map_handler.highlights_geojson()})
            elif parsed.path == "/api/experience-banks/switch":
                bank = STATE.ai_handler.switch_experience_bank(data["bank_id"])
                self._send_json({"bank": bank, "summary": STATE.ai_handler.get_experience_summary()})
            elif parsed.path == "/api/experience-banks/create":
                bank = STATE.ai_handler.create_experience_bank(
                    data.get("name", "新经验库"),
                    data.get("template", "empty"),
                )
                self._send_json(
                    {
                        "bank": bank,
                        "banks": STATE.ai_handler.list_experience_banks(),
                        "summary": STATE.ai_handler.get_experience_summary(),
                    }
                )
            elif parsed.path == "/api/experience-banks/rename":
                bank = STATE.ai_handler.rename_experience_bank(data["bank_id"], data.get("name", ""))
                self._send_json(
                    {
                        "bank": bank,
                        "active": STATE.ai_handler.get_active_experience_bank(),
                        "banks": STATE.ai_handler.list_experience_banks(),
                        "summary": STATE.ai_handler.get_experience_summary(),
                    }
                )
            elif parsed.path == "/api/experience-banks/delete":
                bank = STATE.ai_handler.delete_experience_bank(data["bank_id"])
                self._send_json(
                    {
                        "bank": bank,
                        "active": STATE.ai_handler.get_active_experience_bank(),
                        "banks": STATE.ai_handler.list_experience_banks(),
                        "summary": STATE.ai_handler.get_experience_summary(),
                    }
                )
            elif parsed.path == "/api/experiment/exp1/run":
                self._handle_exp1_run(data)
            elif parsed.path == "/api/experiment/exp1/rename":
                self._handle_exp1_rename(data)
            elif parsed.path == "/api/experiment/exp1/delete":
                self._handle_exp1_delete(data)
            elif parsed.path == "/api/experiment/exp2/run":
                self._handle_exp2_run(data)
            elif parsed.path == "/api/experiment/exp2/rename":
                self._handle_exp2_rename(data)
            elif parsed.path == "/api/experiment/exp2/delete":
                self._handle_exp2_delete(data)
            elif parsed.path == "/api/experiment/exp3/run":
                self._handle_exp3_run(data)
            elif parsed.path == "/api/experiment/exp3/rename":
                self._handle_exp3_rename(data)
            elif parsed.path == "/api/experiment/exp3/delete":
                self._handle_exp3_delete(data)
            elif parsed.path == "/api/experiment/exp4/run":
                self._handle_exp4_run(data)
            elif parsed.path == "/api/experiment/exp4/rename":
                self._handle_exp4_rename(data)
            elif parsed.path == "/api/experiment/exp4/delete":
                self._handle_exp4_delete(data)
            else:
                self.send_error(404, "Not found")
        except Exception as exc:
            log_error({"source": "http_post", "path": parsed.path, "error": str(exc)})
            self._send_json({"error": str(exc)}, status=500)

    def _handle_exp1_data(self, query=None):
        """返回实验一的最新汇总数据。"""
        query = query or {}
        requested_run_dir = (query.get("run_dir") or [""])[0]
        if requested_run_dir:
            run_dir = self._resolve_exp1_run_dir(requested_run_dir)
            if not run_dir:
                self._send_json({"error": "实验目录不存在或路径无效"}, status=404)
                return
            data = self._read_exp1_summary(run_dir)
            if data is None:
                self._send_json({"error": "实验结果文件不存在或无法读取"}, status=404)
                return
            STATE._exp1_latest = data
            self._send_json(data)
            return

        # 先检查是否有缓存（线程完成时设置）
        if STATE._exp1_latest:
            self._send_json(STATE._exp1_latest)
            return

        # 如果实验仍在运行中，返回 no_data 让前端继续轮询
        if STATE._exp1_running:
            self._send_json({"status": "no_data", "message": "实验运行中..."})
            return

        # 从 experiments/experiment_outputs/exp1 目录中查找最新结果
        exp1_pattern = os.path.join(EXP1_OUTPUT_DIR, "exp1_*", "summary.json")
        all_files = sorted(glob.glob(exp1_pattern), key=os.path.getmtime, reverse=True)
        if all_files:
            try:
                data = self._read_exp1_summary(os.path.dirname(all_files[0]))
                if data is None:
                    raise ValueError("summary.json 读取失败")
                STATE._exp1_latest = data
                self._send_json(data)
                return
            except Exception:
                pass

        # 返回测试套件信息（无数据时）
        suite_path = os.path.join("experiments", "exp1", "exp1_suite.json")
        if os.path.exists(suite_path):
            with open(suite_path, "r", encoding="utf-8") as f:
                suite = json.load(f)
            self._send_json({
                "experiment": "实验一：基线对比实验",
                "status": "no_data",
                "message": f"尚未运行实验。请点击「运行实验」按钮启动，或检查 {EXP1_OUTPUT_DIR} 目录。",
                "test_suite": suite,
            })
        else:
            self._send_json({"status": "error", "message": "测试套件文件未找到"})

    def _handle_exp1_results(self):
        """返回实验一的所有历史运行结果列表。"""
        exp1_dirs = sorted(
            glob.glob(os.path.join(EXP1_OUTPUT_DIR, "exp1_*")),
            key=os.path.getmtime,
            reverse=True,
        )[:20]
        results = []
        for d in exp1_dirs:
            if os.path.exists(os.path.join(d, "summary.json")):
                try:
                    data = self._read_exp1_summary(d)
                    if data is None:
                        continue
                    results.append(data)
                except Exception:
                    pass
        self._send_json({"runs": results})

    def _handle_exp1_run(self, data):
        """异步运行实验一。"""
        if STATE._exp1_running:
            self._send_json({"status": "running", "message": "实验已在运行中"}, status=400)
            return

        mode = data.get("mode", "both")  # base, ace, both
        bank_id = data.get("bank_id", "")
        STATE._exp1_running = True

        # 保存当前活跃经验库，如果指定了自定义 bank 则切换
        _original_bank_id = None
        _use_preset = True
        if bank_id and bank_id != "default":
            try:
                _original_bank_id = STATE.ai_handler.experience_bank_manager.data.get("active_id", "default")
                STATE.ai_handler.switch_experience_bank(bank_id)
                _use_preset = False
                print(f"[Exp1] 已切换到经验库: {bank_id}")
            except Exception as e:
                print(f"[Exp1] 切换经验库失败: {e}")

        def _run():
            nonlocal _original_bank_id
            try:
                from experiments import run_exp1
                summary = run_exp1(
                    STATE.ai_handler,
                    STATE.map_handler,
                    mode=mode,
                    output_dir=EXP1_OUTPUT_DIR,
                    use_preset=_use_preset,
                )
                STATE._exp1_latest = summary
            except Exception as e:
                import traceback
                STATE._exp1_latest = {
                    "experiment": "实验一：基线对比实验",
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            finally:
                # 恢复原始经验库
                if _original_bank_id:
                    try:
                        STATE.ai_handler.switch_experience_bank(_original_bank_id)
                        print(f"[Exp1] 已恢复经验库: {_original_bank_id}")
                    except Exception as e:
                        print(f"[Exp1] 恢复经验库失败: {e}")
                STATE._exp1_running = False

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        self._send_json({"status": "started", "message": f"实验已启动（模式: {mode}），请稍后刷新查看结果。"})

    def _handle_exp1_rename(self, data):
        """重命名历史实验运行记录。"""
        run_dir = data.get("run_dir", "")
        new_name = data.get("name", "").strip()
        if not run_dir or not new_name:
            self._send_json({"error": "参数不完整"}, status=400)
            return
        abs_dir = self._resolve_exp1_run_dir(run_dir)
        if not abs_dir:
            self._send_json({"error": "实验目录不存在"}, status=404)
            return

        # 将名称写入 .run_name 文件
        name_path = os.path.join(abs_dir, ".run_name")
        clean_name = new_name[:60]
        with open(name_path, "w", encoding="utf-8") as f:
            f.write(clean_name)

        if STATE._exp1_latest and STATE._exp1_latest.get("run_dir") == os.path.relpath(abs_dir):
            STATE._exp1_latest["run_name"] = clean_name

        self._send_json({"status": "ok", "run_dir": os.path.relpath(abs_dir), "name": clean_name})

    def _handle_exp1_delete(self, data):
        """删除历史实验运行记录。"""
        run_dir = data.get("run_dir", "")
        if not run_dir:
            self._send_json({"error": "参数不完整"}, status=400)
            return
        abs_dir = self._resolve_exp1_run_dir(run_dir)
        if not abs_dir:
            self._send_json({"error": "实验目录不存在"}, status=404)
            return

        rel_dir = os.path.relpath(abs_dir)
        shutil.rmtree(abs_dir)
        if STATE._exp1_latest and STATE._exp1_latest.get("run_dir") == rel_dir:
            STATE._exp1_latest = None
        self._send_json({"status": "deleted", "run_dir": rel_dir})

    def _resolve_exp1_run_dir(self, run_dir):
        """Return an absolute exp1 run directory path if it is inside experiments/experiment_outputs/exp1."""
        if not run_dir:
            return ""

        base = os.path.abspath(EXP1_OUTPUT_DIR)
        candidate = run_dir
        if not os.path.isabs(candidate):
            candidate = os.path.join(os.getcwd(), candidate)
        candidate = os.path.abspath(candidate)

        try:
            if os.path.commonpath([base, candidate]) != base:
                return ""
        except ValueError:
            return ""

        if not os.path.isdir(candidate):
            return ""
        if not os.path.basename(candidate).startswith("exp1_"):
            return ""
        return candidate

    def _read_exp1_summary(self, run_dir):
        summary_path = os.path.join(run_dir, "summary.json")
        if not os.path.exists(summary_path):
            return None
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        rel_dir = os.path.relpath(os.path.abspath(run_dir))
        data["run_dir"] = rel_dir

        name_path = os.path.join(run_dir, ".run_name")
        if os.path.exists(name_path):
            with open(name_path, "r", encoding="utf-8") as f:
                data["run_name"] = f.read().strip()
        else:
            dir_name = os.path.basename(run_dir)
            try:
                ts = dir_name.split("_")[-1]
                data["run_name"] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:]}"
            except Exception:
                data["run_name"] = dir_name
        return data

    def _handle_exp2_data(self, query=None):
        """返回实验二的最新或指定历史汇总数据。"""
        query = query or {}
        requested_run_dir = (query.get("run_dir") or [""])[0]
        if requested_run_dir:
            run_dir = self._resolve_exp_run_dir(requested_run_dir, "exp2_")
            if not run_dir:
                self._send_json({"error": "实验目录不存在或路径无效"}, status=404)
                return
            data = self._read_exp_summary(run_dir)
            if data is None:
                self._send_json({"error": "实验结果文件不存在或无法读取"}, status=404)
                return
            STATE._exp2_latest = data
            self._send_json(data)
            return

        if STATE._exp2_latest:
            self._send_json(STATE._exp2_latest)
            return

        exp2_pattern = os.path.join(EXP2_OUTPUT_DIR, "exp2_*", "summary.json")
        all_files = sorted(glob.glob(exp2_pattern), key=os.path.getmtime, reverse=True)
        if all_files:
            try:
                data = self._read_exp_summary(os.path.dirname(all_files[0]))
                if data is None:
                    raise ValueError("summary.json 读取失败")
                STATE._exp2_latest = data
                self._send_json(data)
                return
            except Exception:
                pass

        suite_path = os.path.join("experiments", "exp2", "exp2_suite.json")
        if os.path.exists(suite_path):
            with open(suite_path, "r", encoding="utf-8") as f:
                suite = json.load(f)
            self._send_json({
                "experiment": "实验二：消融实验",
                "status": "no_data",
                "message": f"尚未运行实验二。请点击「运行实验」按钮启动，或检查 {EXP2_OUTPUT_DIR} 目录。",
                "suite": suite,
            })
        else:
            self._send_json({"status": "error", "message": "实验二数据集文件未找到"})

    def _handle_exp2_results(self):
        """返回实验二的历史运行结果列表。"""
        self._send_json({"runs": self._list_exp_runs("exp2_")})

    def _handle_exp2_run(self, data):
        """运行实验二。"""
        if STATE._exp2_running:
            self._send_json({"status": "running", "message": "实验二已在运行中"}, status=400)
            return

        STATE._exp2_running = True
        try:
            from experiments.exp2.exp2_runner import run_exp2
            STATE._exp2_latest = run_exp2(output_dir=EXP2_OUTPUT_DIR)
            self._send_json({"status": "done", "summary": STATE._exp2_latest})
        except Exception as e:
            import traceback
            STATE._exp2_latest = {
                "experiment": "实验二：消融实验",
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
            self._send_json(STATE._exp2_latest, status=500)
        finally:
            STATE._exp2_running = False

    def _handle_exp2_rename(self, data):
        self._rename_exp_run(data, "exp2_", "_exp2_latest")

    def _handle_exp2_delete(self, data):
        self._delete_exp_run(data, "exp2_", "_exp2_latest")

    def _handle_exp3_data(self, query=None):
        """返回实验三的最新或指定历史汇总数据。"""
        query = query or {}
        requested_run_dir = (query.get("run_dir") or [""])[0]
        if requested_run_dir:
            run_dir = self._resolve_exp_run_dir(requested_run_dir, "exp3_")
            if not run_dir:
                self._send_json({"error": "实验目录不存在或路径无效"}, status=404)
                return
            data = self._read_exp_summary(run_dir)
            if data is None:
                self._send_json({"error": "实验结果文件不存在或无法读取"}, status=404)
                return
            STATE._exp3_latest = data
            self._send_json(data)
            return

        if STATE._exp3_latest:
            self._send_json(STATE._exp3_latest)
            return

        exp3_pattern = os.path.join(EXP3_OUTPUT_DIR, "exp3_*", "summary.json")
        all_files = sorted(glob.glob(exp3_pattern), key=os.path.getmtime, reverse=True)
        if all_files:
            data = self._read_exp_summary(os.path.dirname(all_files[0]))
            if data is not None:
                STATE._exp3_latest = data
                self._send_json(data)
                return

        suite_path = os.path.join("experiments", "exp3", "exp3_suite.json")
        if os.path.exists(suite_path):
            with open(suite_path, "r", encoding="utf-8") as f:
                suite = json.load(f)
            self._send_json({
                "experiment": "实验三：抗退化实验",
                "status": "no_data",
                "message": f"尚未运行实验三。请点击「运行实验」按钮启动，或检查 {EXP3_OUTPUT_DIR} 目录。",
                "suite": suite,
            })
        else:
            self._send_json({"status": "error", "message": "实验三数据集文件未找到"})

    def _handle_exp3_results(self):
        self._send_json({"runs": self._list_exp_runs("exp3_")})

    def _handle_exp3_run(self, data):
        """运行实验三。"""
        if STATE._exp3_running:
            self._send_json({"status": "running", "message": "实验三已在运行中"}, status=400)
            return

        STATE._exp3_running = True
        try:
            from experiments.exp3.exp3_runner import run_exp3
            STATE._exp3_latest = run_exp3(output_dir=EXP3_OUTPUT_DIR)
            self._send_json({"status": "done", "summary": STATE._exp3_latest})
        except Exception as e:
            import traceback
            STATE._exp3_latest = {
                "experiment": "实验三：抗退化实验",
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
            self._send_json(STATE._exp3_latest, status=500)
        finally:
            STATE._exp3_running = False

    def _handle_exp3_rename(self, data):
        self._rename_exp_run(data, "exp3_", "_exp3_latest")

    def _handle_exp3_delete(self, data):
        self._delete_exp_run(data, "exp3_", "_exp3_latest")

    def _handle_exp4_data(self, query=None):
        """返回实验四的最新或指定历史汇总数据。"""
        query = query or {}
        requested_run_dir = (query.get("run_dir") or [""])[0]
        if requested_run_dir:
            run_dir = self._resolve_exp_run_dir(requested_run_dir, "exp4_")
            if not run_dir:
                self._send_json({"error": "实验目录不存在或路径无效"}, status=404)
                return
            data = self._read_exp_summary(run_dir)
            if data is None:
                self._send_json({"error": "实验结果文件不存在或无法读取"}, status=404)
                return
            STATE._exp4_latest = data
            self._send_json(data)
            return

        if STATE._exp4_latest:
            self._send_json(STATE._exp4_latest)
            return

        exp4_pattern = os.path.join(EXP4_OUTPUT_DIR, "exp4_*", "summary.json")
        all_files = sorted(glob.glob(exp4_pattern), key=os.path.getmtime, reverse=True)
        if all_files:
            data = self._read_exp_summary(os.path.dirname(all_files[0]))
            if data is not None:
                STATE._exp4_latest = data
                self._send_json(data)
                return

        suite_path = os.path.join("experiments", "exp4", "exp4_suite.json")
        if os.path.exists(suite_path):
            with open(suite_path, "r", encoding="utf-8") as f:
                suite = json.load(f)
            self._send_json({
                "experiment": "实验四：长上下文扩展场景对比实验",
                "status": "no_data",
                "message": f"尚未运行实验四。请点击「运行实验」按钮启动，或检查 {EXP4_OUTPUT_DIR} 目录。",
                "suite": suite,
            })
        else:
            self._send_json({"status": "error", "message": "实验四数据集文件未找到"})

    def _handle_exp4_results(self):
        self._send_json({"runs": self._list_exp_runs("exp4_")})

    def _handle_exp4_run(self, data):
        """运行实验四。"""
        if STATE._exp4_running:
            self._send_json({"status": "running", "message": "实验四已在运行中"}, status=400)
            return

        STATE._exp4_running = True
        try:
            from experiments.exp4.exp4_runner import run_exp4
            STATE._exp4_latest = run_exp4(output_dir=EXP4_OUTPUT_DIR)
            self._send_json({"status": "done", "summary": STATE._exp4_latest})
        except Exception as e:
            import traceback
            STATE._exp4_latest = {
                "experiment": "实验四：长上下文扩展场景对比实验",
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
            self._send_json(STATE._exp4_latest, status=500)
        finally:
            STATE._exp4_running = False

    def _handle_exp4_rename(self, data):
        self._rename_exp_run(data, "exp4_", "_exp4_latest")

    def _handle_exp4_delete(self, data):
        self._delete_exp_run(data, "exp4_", "_exp4_latest")

    def _output_dir_for_prefix(self, prefix):
        if prefix == "exp1_":
            return EXP1_OUTPUT_DIR
        if prefix == "exp2_":
            return EXP2_OUTPUT_DIR
        if prefix == "exp3_":
            return EXP3_OUTPUT_DIR
        if prefix == "exp4_":
            return EXP4_OUTPUT_DIR
        return EXPERIMENT_OUTPUT_ROOT

    def _list_exp_runs(self, prefix):
        output_dir = self._output_dir_for_prefix(prefix)
        exp_dirs = sorted(
            glob.glob(os.path.join(output_dir, f"{prefix}*")),
            key=os.path.getmtime,
            reverse=True,
        )[:20]
        results = []
        for d in exp_dirs:
            if os.path.exists(os.path.join(d, "summary.json")):
                try:
                    data = self._read_exp_summary(d)
                    if data is not None:
                        results.append(data)
                except Exception:
                    pass
        return results

    def _rename_exp_run(self, data, prefix, cache_attr):
        run_dir = data.get("run_dir", "")
        new_name = data.get("name", "").strip()
        if not run_dir or not new_name:
            self._send_json({"error": "参数不完整"}, status=400)
            return
        abs_dir = self._resolve_exp_run_dir(run_dir, prefix)
        if not abs_dir:
            self._send_json({"error": "实验目录不存在"}, status=404)
            return

        clean_name = new_name[:60]
        with open(os.path.join(abs_dir, ".run_name"), "w", encoding="utf-8") as f:
            f.write(clean_name)

        rel_dir = os.path.relpath(abs_dir)
        cached = getattr(STATE, cache_attr, None)
        if cached and cached.get("run_dir") == rel_dir:
            cached["run_name"] = clean_name
        self._send_json({"status": "ok", "run_dir": rel_dir, "name": clean_name})

    def _delete_exp_run(self, data, prefix, cache_attr):
        run_dir = data.get("run_dir", "")
        if not run_dir:
            self._send_json({"error": "参数不完整"}, status=400)
            return
        abs_dir = self._resolve_exp_run_dir(run_dir, prefix)
        if not abs_dir:
            self._send_json({"error": "实验目录不存在"}, status=404)
            return

        rel_dir = os.path.relpath(abs_dir)
        shutil.rmtree(abs_dir)
        cached = getattr(STATE, cache_attr, None)
        if cached and cached.get("run_dir") == rel_dir:
            setattr(STATE, cache_attr, None)
        self._send_json({"status": "deleted", "run_dir": rel_dir})

    def _handle_exp_export(self, query, prefix):
        requested_run_dir = (query.get("run_dir") or [""])[0]
        if requested_run_dir:
            abs_dir = self._resolve_exp_run_dir(requested_run_dir, prefix)
        else:
            runs = self._list_exp_runs(prefix)
            abs_dir = self._resolve_exp_run_dir(runs[0]["run_dir"], prefix) if runs else ""
        if not abs_dir:
            self._send_json({"error": "实验目录不存在或路径无效"}, status=404)
            return

        from experiments.export_utils import build_export_zip

        zip_path = build_export_zip(abs_dir)
        self._send_download(zip_path, os.path.basename(zip_path))

    def _handle_thesis_evidence(self):
        from experiments.thesis_evidence import build_thesis_evidence

        self._send_json(build_thesis_evidence())

    def _resolve_exp_run_dir(self, run_dir, prefix):
        if not run_dir:
            return ""

        base = os.path.abspath(self._output_dir_for_prefix(prefix))
        candidate = run_dir
        if not os.path.isabs(candidate):
            candidate = os.path.join(os.getcwd(), candidate)
        candidate = os.path.abspath(candidate)

        try:
            if os.path.commonpath([base, candidate]) != base:
                return ""
        except ValueError:
            return ""

        if not os.path.isdir(candidate):
            return ""
        if not os.path.basename(candidate).startswith(prefix):
            return ""
        return candidate

    def _read_exp_summary(self, run_dir):
        summary_path = os.path.join(run_dir, "summary.json")
        if not os.path.exists(summary_path):
            return None
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        rel_dir = os.path.relpath(os.path.abspath(run_dir))
        data["run_dir"] = rel_dir

        name_path = os.path.join(run_dir, ".run_name")
        if os.path.exists(name_path):
            with open(name_path, "r", encoding="utf-8") as f:
                data["run_name"] = f.read().strip()
        elif not data.get("run_name"):
            dir_name = os.path.basename(run_dir)
            try:
                ts = dir_name.split("_")[-1]
                data["run_name"] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:]}"
            except Exception:
                data["run_name"] = dir_name
        return data

    def _send_download(self, abs_path, filename):
        if not os.path.exists(abs_path):
            self.send_error(404, "File not found")
            return
        with open(abs_path, "rb") as f:
            body = f.read()
        encoded_name = quote(filename)
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(abs_path)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, relative_path):
        """发送文件系统中的任意静态文件（安全处理）。"""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        abs_path = os.path.abspath(os.path.join(base_dir, relative_path))
        if not abs_path.startswith(base_dir) or not os.path.exists(abs_path):
            self.send_error(404, "File not found")
            return
        with open(abs_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(abs_path)[0] or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_chat(self, data):
        user_input = data.get("message", "").strip()
        if not user_input:
            self._send_json({"error": "消息不能为空"}, status=400)
            return

        def highlight_callback(highlight_infos):
            STATE.map_handler.batch_highlight(highlight_infos)

        answer = STATE.ai_handler.process_message(user_input, highlight_callback)
        self._send_json(
            {
                "answer": answer,
                "trace": STATE.ai_handler.get_trace_text(),
                "ace_panel": STATE.ai_handler.get_ace_panel(),
                "experience": STATE.ai_handler.get_experience_summary(),
                "session": STATE.ai_handler.get_current_session(),
                "sessions": STATE.ai_handler.list_sessions(),
                "highlights": STATE.map_handler.highlights_geojson(),
            }
        )

    def _handle_layer_data(self, query):
        layer_name = (query.get("layer_name") or [""])[0]
        if not layer_name:
            self._send_json({"error": "layer_name 不能为空"}, status=400)
            return

        bbox_text = (query.get("bbox") or [""])[0]
        zoom_text = (query.get("zoom") or [""])[0]
        bbox = None
        if bbox_text:
            parts = [float(part) for part in bbox_text.split(",")]
            if len(parts) == 4:
                bbox = tuple(parts)
        zoom = float(zoom_text) if zoom_text else None

        payload = STATE.map_handler.layer_data_payload(layer_name=layer_name, bbox=bbox, zoom=zoom)
        self._send_json(payload)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name):
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        path = os.path.abspath(os.path.join(static_dir, name))
        if not path.startswith(os.path.abspath(static_dir)) or not os.path.exists(path):
            self.send_error(404, "Static file not found")
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("[web]", format % args)


def _read_idle_shutdown_seconds(default=600):
    raw = os.getenv("GEOAI_IDLE_SHUTDOWN_SECONDS", str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        startup_log(f"invalid GEOAI_IDLE_SHUTDOWN_SECONDS={raw!r}; using {default}s")
        return default
    return max(0, value)


def _start_idle_shutdown_watcher(server):
    seconds = server.idle_shutdown_seconds
    if seconds <= 0:
        startup_log("idle auto-shutdown disabled")
        return

    def watch_idle():
        while True:
            time.sleep(min(max(seconds / 2, 5), 60))
            idle_for = time.monotonic() - server.last_request_at
            if idle_for < seconds:
                continue
            if STATE is not None and STATE.has_running_experiment():
                server.touch()
                continue
            startup_log(f"idle for {int(idle_for)}s; shutting down and releasing port")
            server.shutdown()
            break

    thread = threading.Thread(target=watch_idle, name="idle-shutdown-watcher", daemon=True)
    thread.start()
    startup_log(f"idle auto-shutdown enabled after {seconds}s without requests")


def run(host="127.0.0.1", port=8000, max_port=8010):
    global STATE
    startup_log("starting GeoAI WebGIS")
    STATE = WebGISAppState()
    server = None
    selected_port = None
    last_error = None

    startup_log(f"binding local server on {host}:{port}-{max_port}")
    for candidate_port in range(port, max_port + 1):
        try:
            server = ExclusiveThreadingHTTPServer((host, candidate_port), WebGISRequestHandler)
            server.last_request_at = time.monotonic()
            server.idle_shutdown_seconds = _read_idle_shutdown_seconds()
            selected_port = candidate_port
            break
        except OSError as exc:
            last_error = exc
            startup_log(f"port {candidate_port} unavailable: {exc}")

    if server is None or selected_port is None:
        raise RuntimeError(
            f"端口 {port}-{max_port} 都已被占用。请先停止旧的 Web 服务后再启动。原始错误: {last_error}"
        ) from last_error

    if selected_port != port:
        startup_log(f"port {port} is occupied; switched to {selected_port}")

    startup_log(f"GeoAI WebGIS running locally at http://{host}:{selected_port}")
    _start_idle_shutdown_watcher(server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        startup_log("received Ctrl+C; stopping GeoAI WebGIS")
    finally:
        server.server_close()
        startup_log("server stopped; port released")
