"""Week 5 工作台:`uv run week05` 的默认入口(CLI 子命令是管线,给 AI agent 用)。

页面:/ 总览(跑一遍 Demo)· /emails 邮件预览 · /metrics 发送统计 · /report 最新报告直出。
build_batch / write_report / run_demo 是 CLI 与页面共用的唯一产物入口。
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

from camp_core import load_config, now_iso, read_json, write_json
from camp_report import kv_card, save_report, table
from camp_workbench import Workbench, button

from week05_email_growth import EMAILS_JSON, OUTPUT_DIR, PROJECT_DIR, SEND_LOG, SUMMARY_JSON
from week05_email_growth import compose

PORT = 8705

wb = Workbench("Week 5 · AI 邮件增长工作台", "名单 → 个性化邮件 → dry-run → 真发")


# ---------- 产物流水线(CLI 与页面共用) ----------

def build_batch(config: dict[str, Any], contacts_path: Path, limit: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """名单 → 邮件 → 落盘,demo/preview 共用的唯一入口。"""
    contacts = compose.load_contacts(contacts_path)
    contacts = contacts[:limit] if limit else contacts
    emails = compose.build_emails(contacts, config)
    summary = {
        "generated_at": now_iso(),
        "campaign_name": config.get("campaign", {}).get("name", ""),
        "contacts_csv": str(contacts_path),
        "contacts": len(contacts),
        "ready": sum(1 for email in emails if email["status"] == "ready"),
        "blocked": sum(1 for email in emails if email["status"] == "blocked"),
        "warnings": compose.compliance_warnings(config, contacts),
    }
    write_json(EMAILS_JSON, emails)
    write_json(SUMMARY_JSON, summary)
    print(f"OK emails={EMAILS_JSON}(可发 {summary['ready']} / 拦截 {summary['blocked']})")
    return summary, emails


def write_report(summary: dict[str, Any], emails: list[dict[str, Any]], name: str) -> Path:
    overview = kv_card("本批概览", [
        ("批次名称", summary["campaign_name"] or "-"),
        ("名单来源", summary["contacts_csv"]),
        ("联系人", summary["contacts"]),
        ("可发送(ready)", summary["ready"]),
        ("已拦截(blocked)", summary["blocked"]),
        ("生成时间", summary["generated_at"]),
    ])
    checks = table(["合规检查结果"], [[w] for w in summary["warnings"]] or [["通过:未发现问题"]])
    preview = table(
        ["收件人", "状态", "主题", "正文摘要"],
        [[e["email"], e["status"], e["subject"], excerpt(e["text"])] for e in emails],
    )
    body = overview + "<h2>合规检查</h2>" + checks + "<h2>邮件预览</h2>" + preview
    return save_report(OUTPUT_DIR / name, "AI 邮件增长工作台",
                       body, subtitle="先 dry-run,再发给自己,最后才小批量真发")


def run_demo(limit: int = 0) -> dict[str, Any]:
    """零密钥零外发:demo 名单 → 全部个性化邮件 + HTML 报告。"""
    config = load_config(PROJECT_DIR)
    summary, emails = build_batch(config, compose.DEMO_CSV, limit)
    report = write_report(summary, emails, "demo-report.html")
    return {**summary, "report": str(report)}


def excerpt(text: str, limit: int = 120) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def read_send_log() -> list[dict[str, Any]]:
    if not SEND_LOG.exists():
        return []
    return [json.loads(line) for line in SEND_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------- 页面 ----------

def _latest_report() -> Path | None:
    candidates = [p for p in (OUTPUT_DIR / "demo-report.html", OUTPUT_DIR / "preview-report.html") if p.exists()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _warnings_html(warnings: list[str]) -> str:
    return "".join(
        f'<p style="border:1.5px solid var(--ink);background:#fff7ed;padding:10px 14px">⚠ {_html.escape(w)}</p>'
        for w in warnings
    )


@wb.route("/", nav="总览")
def home(_query: dict) -> str:
    parts = [
        "<p>把一份联系人名单变成一批个性化外联邮件:合规检查 → 逐人生成 → dry-run 预演 → 才谈真发。"
        "Demo 用自带名单,零密钥零外发。</p>",
        button("跑一遍 Demo", "/run-demo", large=True),
    ]
    summary = read_json(SUMMARY_JSON, {})
    if summary:
        parts.append(kv_card("上次运行", [
            ("批次名称", summary.get("campaign_name") or "-"),
            ("联系人", summary.get("contacts", 0)),
            ("可发送(ready)", summary.get("ready", 0)),
            ("已拦截(blocked)", summary.get("blocked", 0)),
            ("生成时间", summary.get("generated_at", "")),
        ]))
    else:
        parts.append('<p class="muted">还没跑过:点上面的按钮,几秒出结果。</p>')
    if _latest_report():
        parts.append('<p><a href="/report">打开最新报告 →</a></p>')
    return "".join(parts)


@wb.route("/emails", nav="邮件预览")
def emails_page(_query: dict) -> str:
    emails = read_json(EMAILS_JSON, [])
    summary = read_json(SUMMARY_JSON, {})
    if not emails:
        return "<p>还没有生成邮件:回「总览」跑一遍 Demo。</p>"
    head = (f"<p>批次「{_html.escape(str(summary.get('campaign_name') or '-'))}」:"
            f"{summary.get('ready', 0)} 封可发 / {summary.get('blocked', 0)} 封拦截</p>")
    rows = [[e["email"], e["status"], e["subject"], excerpt(e["text"])] for e in emails]
    return _warnings_html(summary.get("warnings", [])) + head + table(["收件人", "状态", "主题", "正文摘要"], rows)


@wb.route("/metrics", nav="发送统计")
def metrics_page(_query: dict) -> str:
    emails = read_json(EMAILS_JSON, [])
    log = read_send_log()
    stats = kv_card("发送统计", [
        ("生成邮件", len(emails)),
        ("可发送(ready)", sum(1 for e in emails if e.get("status") == "ready")),
        ("已拦截(blocked)", sum(1 for e in emails if e.get("status") == "blocked")),
        ("dry-run 记录", sum(1 for r in log if r.get("mode") == "dry_run")),
        ("真实发送记录", sum(1 for r in log if r.get("mode") == "real")),
    ])
    recent = table(["时间", "模式", "收件人", "主题"],
                   [[r.get("created_at"), r.get("mode"), r.get("email"), r.get("subject")]
                    for r in reversed(log[-20:])])
    return stats + "<h2>最近 20 条发送日志</h2>" + recent


@wb.route("/report")
def report_page(_query: dict) -> str | tuple[bytes, str]:
    path = _latest_report()
    if path is None:
        return "<p>还没有报告:回「总览」跑一遍 Demo。</p>"
    return path.read_bytes(), "text/html; charset=utf-8"


@wb.action("/run-demo")
def run_demo_action(_form: dict) -> tuple[str, str]:
    result = run_demo()
    return "/", (f"Demo 跑完了:{result['contacts']} 个联系人,{result['ready']} 封可发 / "
                 f"{result['blocked']} 封拦截,报告已更新(零外发)")


def serve(port: int = 0, open_browser: bool = True) -> None:
    config = load_config(PROJECT_DIR)
    wb.serve(port or int(config.get("serve_port") or PORT), open_browser=open_browser)
