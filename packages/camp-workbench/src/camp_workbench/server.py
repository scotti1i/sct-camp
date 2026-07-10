"""统一本地看板壳:标准库 http.server + camp-report 的纸感样式。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from camp_report import page

Handler = Callable[[dict[str, list[str]]], str | dict[str, Any] | bytes]

_NAV = '<p style="font-size:13px;color:var(--ink-soft)">SCT 超级个体营 · 本地工作台 · 数据都在你自己电脑上</p>'


class Workbench:
    def __init__(self, title: str) -> None:
        self.title = title
        self._routes: dict[str, Handler] = {}

    def route(self, path: str) -> Callable[[Handler], Handler]:
        def register(handler: Handler) -> Handler:
            self._routes[path] = handler
            return handler
        return register

    def _respond(self, handler_result: str | dict[str, Any] | bytes) -> tuple[str, bytes]:
        if isinstance(handler_result, bytes):
            return "application/octet-stream", handler_result
        if isinstance(handler_result, dict):
            return "application/json; charset=utf-8", json.dumps(handler_result, ensure_ascii=False).encode()
        html = page(self.title, _NAV + handler_result)
        return "text/html; charset=utf-8", html.encode()

    def serve(self, port: int, open_browser: bool = True) -> None:
        workbench = self

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (http.server 命名约定)
                parsed = urlparse(self.path)
                handler = workbench._routes.get(parsed.path)
                if handler is None:
                    self.send_error(404, "没有这个页面")
                    return
                content_type, body = workbench._respond(handler(parse_qs(parsed.query)))
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: Any) -> None:  # 静音默认访问日志
                pass

        url = f"http://127.0.0.1:{port}"
        print(f"[camp] 工作台已启动: {url} (Ctrl+C 停止)")
        if open_browser:
            import webbrowser

            webbrowser.open(url)
        ThreadingHTTPServer(("127.0.0.1", port), RequestHandler).serve_forever()
