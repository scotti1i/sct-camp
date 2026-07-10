"""极简 HTML 报表:page() 包壳,table()/kv_card() 拼内容。零依赖零 JS。"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from camp_report.tokens import CSS_VARS

_STYLE = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font-family: -apple-system, "PingFang SC",
       "Microsoft YaHei", sans-serif; line-height: 1.7; padding: 48px 24px; }
main { max-width: 860px; margin: 0 auto; display: grid; gap: 24px; }
h1 { font-size: 26px; border-bottom: 2px solid var(--ink); padding-bottom: 12px; }
h1 small { font-size: 13px; color: var(--ink-soft); font-weight: 400; margin-left: 12px; }
h2 { font-size: 18px; }
.card { border: 1.5px solid var(--ink); background: #fff; padding: 20px 24px; display: grid; gap: 10px; }
.kv { display: flex; justify-content: space-between; border-bottom: 1px solid var(--line);
      padding: 6px 0; font-size: 15px; }
.kv b { font-variant-numeric: tabular-nums; }
.accent { color: var(--navy); font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fff; }
th { text-align: left; border-bottom: 2px solid var(--ink); padding: 8px 10px; }
td { border-bottom: 1px solid var(--line); padding: 8px 10px; }
footer { font-size: 12px; color: var(--ink-soft); }
"""


def _esc(value: Any) -> str:
    return _html.escape(str(value))


def page(title: str, body: str, subtitle: str = "") -> str:
    sub = f"<small>{_esc(subtitle)}</small>" if subtitle else ""
    return (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{_esc(title)}</title>"
        f"<style>{CSS_VARS}{_STYLE}</style></head><body><main>"
        f"<h1>{_esc(title)}{sub}</h1>{body}"
        "<footer>SCT 超级个体营 · camp-report 生成</footer></main></body></html>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def kv_card(title: str, pairs: list[tuple[str, Any]]) -> str:
    rows = "".join(f'<div class="kv"><span>{_esc(k)}</span><b>{_esc(v)}</b></div>' for k, v in pairs)
    return f'<section class="card"><h2>{_esc(title)}</h2>{rows}</section>'


def save_report(path: Path, title: str, body: str, subtitle: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page(title, body, subtitle), encoding="utf-8")
    return path
