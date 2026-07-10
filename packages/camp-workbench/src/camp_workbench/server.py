"""产品级本地工作台壳:侧栏 + 内容区 + 可点按钮,纸感 + 海军蓝。

页面 = @wb.route("/", nav="总览") 返回 HTML 片段,壳负责侧栏和整页。
动作 = @wb.action("/run-demo") 返回 (跳转路径, 提示消息),壳渲染成按钮可点。
全程标准库,无构建步骤;所有工具用同一个壳 = 所有工具是同一个软件的不同页面。
"""

from __future__ import annotations

import html as _html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlparse

from camp_report.tokens import CSS_VARS

PageHandler = Callable[[dict[str, list[str]]], str | dict[str, Any] | bytes | tuple[bytes, str]]
ActionHandler = Callable[[dict[str, str]], tuple[str, str]]

_SHELL_STYLE = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { display: flex; min-height: 100vh; background: var(--paper); color: var(--ink);
       font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.7; }
aside { width: 232px; background: var(--ink); color: var(--paper); padding: 28px 22px;
        display: flex; flex-direction: column; gap: 20px; flex-shrink: 0; }
aside .brand { font-size: 13px; letter-spacing: 0.08em; color: var(--marker); font-weight: 700; }
aside h1 { font-size: 19px; line-height: 1.4; }
aside .sub { font-size: 12.5px; color: rgba(250, 250, 247, 0.6); }
aside nav { display: flex; flex-direction: column; gap: 2px; margin-top: 8px; }
aside nav a { color: rgba(250, 250, 247, 0.82); text-decoration: none; font-size: 14px;
              padding: 7px 10px; border-left: 2px solid transparent; }
aside nav a:hover, aside nav a.active { color: #fff; border-left-color: var(--marker);
              background: rgba(255, 255, 255, 0.06); }
aside .foot { margin-top: auto; font-size: 11.5px; color: rgba(250, 250, 247, 0.45); line-height: 1.6; }
.main { flex: 1; padding: 40px 48px; max-width: 1080px; display: grid;
        gap: 22px; align-content: start; }
h2 { font-size: 20px; }
.card { border: 1.5px solid var(--ink); background: #fff; padding: 22px 26px; display: grid; gap: 12px; }
.kv { display: flex; justify-content: space-between; border-bottom: 1px solid var(--line);
      padding: 6px 0; font-size: 15px; }
.kv b { font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fff; }
th { text-align: left; border-bottom: 2px solid var(--ink); padding: 8px 10px; }
td { border-bottom: 1px solid var(--line); padding: 8px 10px; }
.btn { display: inline-block; background: var(--navy); color: #fff; border: none; cursor: pointer;
       font-size: 15px; font-weight: 600; padding: 12px 26px; font-family: inherit; }
.btn:hover { background: var(--navy-deep); }
.btn-lg { font-size: 17px; padding: 16px 34px; }
.notice { border: 1.5px solid var(--navy); background: #fff; color: var(--navy);
          padding: 12px 18px; font-size: 14.5px; }
.muted { color: var(--ink-soft); font-size: 14px; }
a { color: var(--navy); }
@media (max-width: 760px) { body { flex-direction: column; } aside { width: 100%; } .main { padding: 24px 18px; } }
"""


def button(label: str, action_path: str, large: bool = False) -> str:
    """渲染一个触发后端动作的按钮(POST 表单)。"""
    cls = "btn btn-lg" if large else "btn"
    return (
        f'<form method="post" action="{_html.escape(action_path)}" style="display:inline">'
        f'<button class="{cls}" type="submit">{_html.escape(label)}</button></form>'
    )


class Workbench:
    def __init__(self, title: str, subtitle: str = "") -> None:
        self.title = title
        self.subtitle = subtitle
        self._pages: dict[str, PageHandler] = {}
        self._nav: list[tuple[str, str]] = []
        self._actions: dict[str, ActionHandler] = {}

    def route(self, path: str, nav: str | None = None) -> Callable[[PageHandler], PageHandler]:
        def register(handler: PageHandler) -> PageHandler:
            self._pages[path] = handler
            if nav:
                self._nav.append((path, nav))
            return handler
        return register

    def action(self, path: str) -> Callable[[ActionHandler], ActionHandler]:
        def register(handler: ActionHandler) -> ActionHandler:
            self._actions[path] = handler
            return handler
        return register

    # ---------- 渲染 ----------

    def _shell(self, content: str, current: str, msg: str) -> str:
        nav = "".join(
            f'<a href="{p}" class="{"active" if p == current else ""}">{_html.escape(label)}</a>'
            for p, label in self._nav
        )
        sub = f'<p class="sub">{_html.escape(self.subtitle)}</p>' if self.subtitle else ""
        notice = f'<div class="notice">{_html.escape(msg)}</div>' if msg else ""
        return (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_html.escape(self.title)}</title><style>{CSS_VARS}{_SHELL_STYLE}</style></head><body>"
            f'<aside><p class="brand">SCT 超级个体营</p><h1>{_html.escape(self.title)}</h1>{sub}'
            f'<nav>{nav}</nav><p class="foot">本地运行 · 数据都在你自己电脑上<br>camp-workbench</p></aside>'
            f'<div class="main">{notice}{content}</div></body></html>'
        )

    def _respond(self, result: str | dict[str, Any] | bytes | tuple[bytes, str],
                 current: str, msg: str) -> tuple[str, bytes]:
        if isinstance(result, tuple):  # (body, content_type):文件直出,壳不包装
            body, content_type = result
            return content_type, body
        if isinstance(result, bytes):
            return "application/octet-stream", result
        if isinstance(result, dict):
            return "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False).encode()
        return "text/html; charset=utf-8", self._shell(result, current, msg).encode()

    # ---------- 服务 ----------

    def serve(self, port: int, open_browser: bool = True) -> None:
        workbench = self

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                handler = workbench._pages.get(parsed.path)
                if handler is None:
                    self.send_error(404, "没有这个页面")
                    return
                query = parse_qs(parsed.query)
                msg = query.pop("msg", [""])[0]
                content_type, body = workbench._respond(handler(query), parsed.path, msg)
                self._send(200, content_type, body)

            def do_POST(self) -> None:  # noqa: N802
                handler = workbench._actions.get(urlparse(self.path).path)
                if handler is None:
                    self.send_error(404, "没有这个动作")
                    return
                length = int(self.headers.get("Content-Length", 0))
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
                try:
                    target, msg = handler(form)
                except Exception as exc:  # 动作失败要显示,不许白屏
                    target, msg = "/", f"出错了: {exc}"
                self.send_response(303)
                self.send_header("Location", f"{target}?msg={quote(msg)}")
                self.end_headers()

            def _send(self, code: int, content_type: str, body: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: Any) -> None:
                pass

        url = f"http://127.0.0.1:{port}"
        print(f"[camp] 工作台已启动: {url} (Ctrl+C 停止)")
        if open_browser:
            import webbrowser

            webbrowser.open(url)
        ThreadingHTTPServer(("127.0.0.1", port), RequestHandler).serve_forever()
