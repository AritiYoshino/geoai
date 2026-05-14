import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

from dotenv import load_dotenv

from core.jsonl_logger import log_error


def startup_log(message):
    print(f"[startup] {message}", flush=True)


def startup_timing(label, start):
    startup_log(f"[timing] {label}: {time.perf_counter() - start:.3f}s")


def _kill_listeners_on_port(port):
    if os.getenv("GEOAI_KILL_STARTUP_PORT", "1").strip().lower() in {"0", "false", "no"}:
        startup_log(f"startup port cleanup disabled for {port}")
        return

    try:
        output = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception as exc:
        startup_log(f"could not inspect port {port}: {exc}")
        return

    current_pid = os.getpid()
    pids = set()
    markers = (f"127.0.0.1:{port}", f"0.0.0.0:{port}", f"[::]:{port}", f"::1:{port}")
    for line in output.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if not any(marker in line for marker in markers):
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid and pid != current_pid:
            pids.add(pid)

    if not pids:
        startup_log(f"port {port} has no stale listener")
        return

    for pid in sorted(pids):
        startup_log(f"killing stale listener on port {port}: pid={pid}")
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            startup_log(f"failed to kill pid={pid} on port {port}: {exc}")


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

STATE = None
REPORT_LOCK = threading.Lock()


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

    def _content_type_for(self, path, default="application/octet-stream"):
        ext = os.path.splitext(path)[1].lower()
        explicit_types = {
            ".js": "text/javascript; charset=utf-8",
            ".mjs": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".geojson": "application/geo+json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".png": "image/png",
        }
        return explicit_types.get(ext, mimetypes.guess_type(path)[0] or default)

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
            elif parsed.path.startswith("/exports/"):
                self._send_export_file(parsed.path.removeprefix("/exports/"), download=bool(query.get("download")))
            elif parsed.path.startswith("/experiment-reports/"):
                self._send_experiment_report_file(parsed.path.removeprefix("/experiment-reports/"), download=bool(query.get("download")))
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
            elif parsed.path == "/api/experiment/list":
                self._handle_experiment_list()
            elif parsed.path == "/api/experiment/runs":
                self._handle_experiment_runs(query)
            elif parsed.path == "/api/experiment/reports":
                self._handle_experiment_reports(query)
            elif parsed.path.startswith("/api/experiment/result/"):
                self._handle_experiment_result(parsed.path)
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
            elif parsed.path == "/api/experiment/run":
                self._handle_experiment_run(data)
            elif parsed.path == "/api/experiment/report":
                self._handle_experiment_report(data)
            elif parsed.path == "/api/experiment/run/rename":
                self._handle_experiment_run_rename(data)
            elif parsed.path == "/api/experiment/run/delete":
                self._handle_experiment_run_delete(data)
            elif parsed.path == "/api/experiment/report/rename":
                self._handle_experiment_report_rename(data)
            elif parsed.path == "/api/experiment/report/delete":
                self._handle_experiment_report_delete(data)
            else:
                self.send_error(404, "Not found")
        except Exception as exc:
            log_error({"source": "http_post", "path": parsed.path, "error": str(exc)})
            self._send_json({"error": str(exc)}, status=500)

    def _send_experiment_removed(self):
        self._send_json({"status": "removed", "message": "实验模块已移除，界面入口暂时保留。"}, status=410)

    def _handle_experiment_list(self):
        from experiments.runner import list_experiments

        self._send_json({"experiments": list_experiments()})

    def _handle_experiment_runs(self, query):
        from experiments.runner import list_experiment_runs

        exp_id = (query.get("experiment_id") or query.get("exp") or [""])[0] or None
        self._send_json({"runs": list_experiment_runs(exp_id)})

    def _handle_experiment_reports(self, query):
        from experiments.reporting import list_reports

        exp_id = (query.get("experiment_id") or query.get("exp") or [""])[0] or None
        run_id = (query.get("run_id") or [""])[0] or None
        self._send_json({"reports": list_reports(run_id=run_id, exp_id=exp_id)})

    def _handle_experiment_run(self, data):
        from experiments.config import ExperimentConfig

        exp_id = data.get("experiment_id") or data.get("exp") or "exp1"
        config = ExperimentConfig(
            use_critic=bool(data.get("use_critic", True)),
            use_evolution=bool(data.get("use_evolution", True)),
            use_experience_retrieval=bool(data.get("use_experience_retrieval", True)),
            use_code_agent=bool(data.get("use_code_agent", True)),
            use_context_manager=bool(data.get("use_context_manager", True)),
            use_real_ace=bool(data.get("use_real_ace", False)),
            mock_mode=not bool(data.get("use_real_ace", False)),
        )
        startup_log(f"experiment run request started: exp_id={exp_id}, real_ace={config.use_real_ace}")
        try:
            if config.use_real_ace:
                from experiments.runner import run_experiment

                result = run_experiment(exp_id, config=config, app_state=STATE)
            else:
                result = self._run_experiment_isolated(exp_id, config)
            if result.get("run_id"):
                from experiments.runner import LOG_ROOT, write_json

                with REPORT_LOCK:
                    result["report"] = self._generate_experiment_report_isolated(result["run_id"], include_ai_summary=False)
                write_json(LOG_ROOT / result["run_id"] / "result.json", result)
            startup_log(f"experiment run completed: run_id={result.get('run_id', exp_id)}")
        except BaseException as exc:
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            log_error({"source": "experiment_run", "exp_id": exp_id, "error": str(exc), "traceback": detail})
            startup_log(f"experiment run failed: {exc}")
            self._send_json({"error": f"实验运行失败：{exc}"}, status=500)
            return
        self._send_json({"result": result})

    def _run_experiment_isolated(self, exp_id, config):
        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"
        env["PYTHONIOENCODING"] = "utf-8"
        env["GEOAI_REPORT_SKIP_CHARTS"] = "1"
        command = [
            sys.executable,
            "-m",
            "experiments.run_worker",
            str(exp_id),
            json.dumps(config.to_dict(), ensure_ascii=False),
        ]
        completed = subprocess.run(
            command,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=900,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(detail or f"experiment worker exited with code {completed.returncode}")
        output = (completed.stdout or "").strip().splitlines()
        if not output:
            raise RuntimeError("experiment worker did not return a result payload")
        return json.loads(output[-1])

    def _handle_experiment_result(self, path):
        from experiments.runner import get_result

        result_id = unquote(path.rsplit("/", 1)[-1])
        self._send_json({"result": get_result(result_id)})

    def _handle_experiment_report(self, data):
        from experiments.runner import LOG_ROOT, get_result, write_json

        result_id = data.get("run_id") or data.get("experiment_id") or data.get("exp") or "exp1"
        include_ai_summary = bool(data.get("include_ai_summary", False))
        startup_log(f"experiment report request started: result_id={result_id}, ai_summary={include_ai_summary}")
        try:
            result = get_result(result_id)
            startup_log(f"experiment report result loaded: run_id={result.get('run_id')}")
            with REPORT_LOCK:
                report = self._generate_experiment_report_isolated(result_id, include_ai_summary)
            startup_log(f"experiment report generated: {report.get('html_url')}")
            result["report"] = report
            if result.get("run_id"):
                write_json(LOG_ROOT / result["run_id"] / "result.json", result)
                startup_log(f"experiment report metadata saved: run_id={result.get('run_id')}")
        except BaseException as exc:
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            log_error({"source": "experiment_report", "result_id": result_id, "error": str(exc), "traceback": detail})
            startup_log(f"experiment report failed: {exc}")
            self._send_json({"error": f"报告生成失败：{exc}"}, status=500)
            return
        self._send_json({"report": report})

    def _generate_experiment_report_isolated(self, result_id, include_ai_summary):
        try:
            return self._run_experiment_report_worker(result_id, include_ai_summary, skip_charts=False)
        except RuntimeError as exc:
            startup_log(f"experiment report worker failed, retrying without charts: {exc}")
            return self._run_experiment_report_worker(result_id, include_ai_summary, skip_charts=True)

    def _run_experiment_report_worker(self, result_id, include_ai_summary, skip_charts=False):
        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"
        env["PYTHONIOENCODING"] = "utf-8"
        command = [
            sys.executable,
            "-m",
            "experiments.report_worker",
            str(result_id),
            "1" if include_ai_summary else "0",
        ]
        if skip_charts:
            command.append("--skip-charts")
            env["GEOAI_REPORT_SKIP_CHARTS"] = "1"
        completed = subprocess.run(
            command,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=180,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(detail or f"report worker exited with code {completed.returncode}")
        output = (completed.stdout or "").strip().splitlines()
        if not output:
            raise RuntimeError("report worker did not return a report payload")
        return json.loads(output[-1])

    def _handle_experiment_run_rename(self, data):
        from experiments.runner import rename_experiment_run

        result = rename_experiment_run(data["run_id"], data.get("name", ""))
        self._send_json({"run": {"run_id": result.get("run_id"), "name": result.get("display_name") or result.get("name")}})

    def _handle_experiment_run_delete(self, data):
        from experiments.runner import delete_experiment_run

        self._send_json(delete_experiment_run(data["run_id"]))

    def _handle_experiment_report_rename(self, data):
        from experiments.reporting import rename_report

        self._send_json({"report": rename_report(data["run_id"], data.get("title", ""))})

    def _handle_experiment_report_delete(self, data):
        from experiments.reporting import delete_report
        from experiments.runner import LOG_ROOT, get_result, write_json

        payload = delete_report(data["run_id"], data.get("report_id"))
        try:
            result = get_result(data["run_id"])
            result.pop("report", None)
            write_json(LOG_ROOT / data["run_id"] / "result.json", result)
        except Exception:
            pass
        self._send_json(payload)

    def _handle_thesis_evidence(self):
        from experiments.runner import get_result

        evidence = {}
        for exp_id in ("exp1", "exp2", "exp3", "exp4"):
            try:
                evidence[exp_id] = get_result(exp_id)
            except Exception:
                evidence[exp_id] = None
        self._send_json({"evidence": evidence})

    def _send_download(self, abs_path, filename):
        if not os.path.exists(abs_path):
            self.send_error(404, "File not found")
            return
        with open(abs_path, "rb") as f:
            body = f.read()
        encoded_name = quote(filename)
        self.send_response(200)
        self.send_header("Content-Type", self._content_type_for(abs_path))
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
        self.send_header("Content-Type", self._content_type_for(abs_path, "application/json"))
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
        export_info = STATE.ai_handler.consume_last_export()
        self._send_json(
            {
                "answer": answer,
                "trace": STATE.ai_handler.get_trace_text(),
                "ace_panel": STATE.ai_handler.get_ace_panel(),
                "experience": STATE.ai_handler.get_experience_summary(),
                "session": STATE.ai_handler.get_current_session(),
                "sessions": STATE.ai_handler.list_sessions(),
                "highlights": STATE.map_handler.highlights_geojson(),
                "exports": [export_info] if export_info else [],
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
        self.send_header("Content-Type", self._content_type_for(path))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_export_file(self, name, download=False):
        export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "exports"))
        path = os.path.abspath(os.path.join(export_dir, unquote(name)))
        if os.path.commonpath([export_dir, path]) != export_dir or not os.path.exists(path):
            self.send_error(404, "Export file not found")
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", self._content_type_for(path, "application/octet-stream"))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        if download:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(os.path.basename(path))}")
        self.end_headers()
        self.wfile.write(body)

    def _send_experiment_report_file(self, name, download=False):
        report_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "experiments"))
        parts = unquote(name).replace("\\", "/").split("/")
        if len(parts) < 2:
            self.send_error(404, "Report file not found")
            return
        run_id = parts[0]
        relative_name = "/".join(parts[1:])
        path = os.path.abspath(os.path.join(report_root, run_id, "reports", relative_name))
        if os.path.commonpath([report_root, path]) != report_root or not os.path.exists(path):
            self.send_error(404, "Report file not found")
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", self._content_type_for(path, "application/octet-stream"))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        if download:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(os.path.basename(path))}")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("[web]", format % args)


def _read_idle_shutdown_seconds(default=3600):
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
            startup_log(f"idle for {int(idle_for)}s; shutting down and releasing port")
            server.shutdown()
            break

    thread = threading.Thread(target=watch_idle, name="idle-shutdown-watcher", daemon=True)
    thread.start()
    startup_log(f"idle auto-shutdown enabled after {seconds}s without requests")


def run(host="127.0.0.1", port=8000, max_port=8010):
    global STATE
    startup_log("starting GeoAI WebGIS")
    _kill_listeners_on_port(port)
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
    startup_log("HTTP server loop is active; keep this terminal/debug session running while using the browser")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        startup_log("received Ctrl+C; stopping GeoAI WebGIS")
    except Exception as exc:
        startup_log(f"HTTP server loop crashed: {exc}")
        raise
    finally:
        server.server_close()
        startup_log("server stopped; port released")

