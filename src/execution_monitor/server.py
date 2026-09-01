from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .monitor import ExecutionMonitor


STATIC_DIR = Path(__file__).with_name("static")
PUBLIC_STATUS_FIELDS = (
    "mode",
    "overall_status",
    "status_reason",
    "order_stage",
    "execution_phase",
    "safety_checks",
    "reconciliation",
    "records_match",
    "latest_event",
    "latest_event_at",
)


def public_status(snapshot: dict[str, object]) -> dict[str, object]:
    """Return the explicit, identifier-free dashboard contract."""
    return {field: snapshot[field] for field in PUBLIC_STATUS_FIELDS}


def build_server(
    monitor: ExecutionMonitor,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    container_bind_allowed = os.environ.get("EXECUTION_MONITOR_ALLOW_CONTAINER_BIND") == "1"
    if host not in {"127.0.0.1", "localhost"} and not (
        host == "0.0.0.0" and container_bind_allowed
    ):
        raise ValueError("The demonstration server must remain bound to localhost.")

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "ExecutionMonitor/0.1"

        def _headers(self, status: int, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'",
            )
            self.end_headers()

        def _send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8")
            self.wfile.write(body)

        def _send_static(self, filename: str, content_type: str) -> None:
            path = STATIC_DIR / filename
            if not path.exists():
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self._headers(HTTPStatus.OK, content_type)
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler interface
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_static("index.html", "text/html; charset=utf-8")
            elif parsed.path == "/favicon.ico":
                self._headers(HTTPStatus.NO_CONTENT, "image/x-icon")
            elif parsed.path == "/styles.css":
                self._send_static("styles.css", "text/css; charset=utf-8")
            elif parsed.path == "/app.js":
                self._send_static("app.js", "text/javascript; charset=utf-8")
            elif parsed.path == "/api/status":
                self._send_json(public_status(monitor.snapshot()))
            elif parsed.path == "/healthz":
                self._send_json({"status": "ok"})
            else:
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

        def _read_only(self) -> None:
            self._send_json(
                {"error": "read_only", "message": "The dashboard cannot modify trading state."},
                HTTPStatus.METHOD_NOT_ALLOWED,
            )

        do_POST = _read_only
        do_PUT = _read_only
        do_PATCH = _read_only
        do_DELETE = _read_only

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return ThreadingHTTPServer((host, port), DashboardHandler)
