import json
import mimetypes
import os
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from ai_handler import AIHandler
from core.jsonl_logger import log_error
from web_app.web_map_handler import BrowserMapHandler


class WebGISAppState:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("请在 .env 文件中设置 DEEPSEEK_API_KEY")
        self.map_handler = BrowserMapHandler()
        self.map_handler.load_geojson_layers(os.path.join("data", "geodata"))
        self.ai_handler = AIHandler(api_key, self.map_handler)


STATE = None


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class WebGISRequestHandler(SimpleHTTPRequestHandler):
    server_version = "GeoAIWeb/0.2"

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self._send_static("index.html")
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
            else:
                self.send_error(404, "Not found")
        except Exception as exc:
            log_error({"source": "http_get", "path": parsed.path, "error": str(exc)})
            self._send_json({"error": str(exc)}, status=500)

    def do_POST(self):
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
            else:
                self.send_error(404, "Not found")
        except Exception as exc:
            log_error({"source": "http_post", "path": parsed.path, "error": str(exc)})
            self._send_json({"error": str(exc)}, status=500)

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


def run(host="127.0.0.1", port=8000, max_port=8010):
    global STATE
    STATE = WebGISAppState()
    server = None
    selected_port = None
    last_error = None

    for candidate_port in range(port, max_port + 1):
        try:
            server = ExclusiveThreadingHTTPServer((host, candidate_port), WebGISRequestHandler)
            selected_port = candidate_port
            break
        except OSError as exc:
            last_error = exc

    if server is None or selected_port is None:
        raise RuntimeError(
            f"端口 {port}-{max_port} 都已被占用。请先停止旧的 Web 服务后再启动。原始错误: {last_error}"
        ) from last_error

    if selected_port != port:
        print(f"端口 {port} 已被占用，已自动切换到可用端口 {selected_port}。")

    print(f"GeoAI WebGIS running at http://{host}:{selected_port}")
    server.serve_forever()
