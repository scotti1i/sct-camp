"""week05 命令行:AI 邮件增长工作台(合规触达,dry-run 优先)。

子命令:
  demo    零密钥零外发:自带 demo 名单 → 全部个性化邮件 → output/demo-report.html
  doctor  体检本周依赖(demo 名单 / 邮件模板 / 生成链路 / RESEND_API_KEY 状态)
  preview 按 config.json 的名单生成邮件 → output/emails.json + preview-report.html
  send    默认 dry-run 只写日志;--really 才通过 Resend 真实发送
  serve   camp_workbench 本地看板:/ 邮件预览列表,/metrics 发送统计
"""

from __future__ import annotations

import argparse
import html as _html
import json
from pathlib import Path
from typing import Any

from camp_core import append_jsonl, load_config, now_iso, read_json, secret, write_json
from camp_core.doctor import Check, core_checks, run_checks
from camp_report import kv_card, save_report, table
from camp_workbench import Workbench

from week05_email_growth import compose, resend_api

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
EMAILS_JSON = OUTPUT_DIR / "emails.json"
SUMMARY_JSON = OUTPUT_DIR / "summary.json"
SEND_LOG = OUTPUT_DIR / "send-log.jsonl"


def _resolve(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _build(config: dict[str, Any], contacts_path: Path, limit: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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


def _excerpt(text: str, limit: int = 120) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def _write_report(summary: dict[str, Any], emails: list[dict[str, Any]], name: str) -> Path:
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
        [[e["email"], e["status"], e["subject"], _excerpt(e["text"])] for e in emails],
    )
    body = overview + "<h2>合规检查</h2>" + checks + "<h2>邮件预览</h2>" + preview
    return save_report(OUTPUT_DIR / name, "AI 邮件增长工作台",
                       body, subtitle="先 dry-run,再发给自己,最后才小批量真发")


# ---------- 子命令 ----------

def cmd_demo(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    summary, emails = _build(config, compose.DEMO_CSV, args.limit)
    report = _write_report(summary, emails, "demo-report.html")
    print(f"OK report={report}")
    print("OK demo 完成:零密钥零外发。dry-run:uv run week05 send;本地看板:uv run week05 serve")


def cmd_doctor(_: argparse.Namespace) -> None:
    checks = [check for check in core_checks() if "lark-cli" not in check.label]
    ok = run_checks(checks + week_checks())
    key_state = "已配置" if secret("RESEND_API_KEY") else "未配置(demo/dry-run 不需要;真实发送前按 README 申请)"
    print(f"[i]  RESEND_API_KEY:{key_state}")
    print("week05 环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑。")
    raise SystemExit(0 if ok else 1)


def week_checks() -> list[Check]:
    def render_probe() -> tuple[bool, str]:
        try:
            config = load_config(PROJECT_DIR)
            contacts = compose.load_contacts(compose.DEMO_CSV)
            email = compose.render_email(contacts[0], config, 0)
            return bool(email["subject"] and email["html"]), "生成结果为空,检查 prompts/ 模板"
        except Exception as exc:
            return False, f"生成失败:{exc}"

    return [
        Check("demo 名单在位(data/contacts-demo.csv)",
              lambda: (compose.DEMO_CSV.exists(), "git checkout weeks/week05-email-growth/data")),
        Check("邮件 HTML 模板在位(prompts/outreach-email-template.html)",
              lambda: (compose.TEMPLATE.exists(), "git checkout weeks/week05-email-growth/prompts")),
        Check("邮件生成链路可用(名单 → 个性化邮件)", render_probe),
    ]


def cmd_preview(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    contacts_path = _resolve(args.contacts or str(config.get("contacts_csv") or "data/contacts-demo.csv"))
    summary, emails = _build(config, contacts_path, args.limit)
    report = _write_report(summary, emails, "preview-report.html")
    print(f"OK report={report}")
    for warning in summary["warnings"]:
        print(f"WARN {warning}")


def cmd_send(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    emails = read_json(EMAILS_JSON, [])
    if not emails:
        raise SystemExit(f"缺少 {EMAILS_JSON}:先跑 uv run week05 demo(或 preview)")
    ready = [email for email in emails if email["status"] == "ready"]
    ready = ready[:args.limit] if args.limit else ready
    if not ready:
        raise SystemExit("没有可发送的邮件:联系人都缺少 consent_status/合法来源,补齐后重新 preview")
    if args.really:
        _send_real(ready, config)
    else:
        _send_dry_run(ready)


def _send_dry_run(ready: list[dict[str, Any]]) -> None:
    rows = [{"created_at": now_iso(), "mode": "dry_run", "email": e["email"], "subject": e["subject"]}
            for e in ready]
    append_jsonl(SEND_LOG, rows)
    print(f"OK dry-run:{len(rows)} 封只写了日志({SEND_LOG}),没有发出任何真实邮件")
    print("真实发送:确认 config.json 的退订链接/邮寄地址为真后,加 --really --limit 1 先发给自己")


def _send_real(ready: list[dict[str, Any]], config: dict[str, Any]) -> None:
    blockers = compose.hard_blockers(config)
    if blockers:
        raise SystemExit("已拒绝真实发送(合规红线):\n- " + "\n- ".join(blockers))
    result = resend_api.send_batch(ready, config)
    write_json(OUTPUT_DIR / "send-result.json", result)
    append_jsonl(SEND_LOG, [{"created_at": now_iso(), "mode": "real", "email": e["email"],
                             "subject": e["subject"], "ok": bool(result.get("ok"))} for e in ready])
    if not result.get("ok"):
        raise SystemExit(f"Resend 发送失败,详情见 {OUTPUT_DIR / 'send-result.json'}:{result.get('error', result)}")
    print(f"OK real:{len(ready)} 封已交给 Resend,回执见 {OUTPUT_DIR / 'send-result.json'}")


def cmd_serve(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    workbench = Workbench("Week 5 · AI 邮件增长工作台")

    @workbench.route("/")
    def home(_query: dict) -> str:
        emails = read_json(EMAILS_JSON, [])
        summary = read_json(SUMMARY_JSON, {})
        if not emails:
            return "<p>还没有生成邮件:先跑 <b>uv run week05 demo</b>,再刷新本页。</p>"
        head = (f"<p>批次「{_html.escape(str(summary.get('campaign_name') or '-'))}」:"
                f"{summary.get('ready', 0)} 封可发 / {summary.get('blocked', 0)} 封拦截"
                f" · <a href=\"/metrics\">发送统计 →</a></p>")
        rows = [[e["email"], e["status"], e["subject"], _excerpt(e["text"])] for e in emails]
        return _warnings_html(summary.get("warnings", [])) + head + table(["收件人", "状态", "主题", "正文摘要"], rows)

    @workbench.route("/metrics")
    def metrics(_query: dict) -> str:
        emails = read_json(EMAILS_JSON, [])
        log = _read_send_log()
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
        return '<p><a href="/">← 邮件预览</a></p>' + stats + "<h2>最近 20 条发送日志</h2>" + recent

    port = int(args.port or config.get("serve_port") or 8785)
    workbench.serve(port, open_browser=not args.no_open)


def _read_send_log() -> list[dict[str, Any]]:
    if not SEND_LOG.exists():
        return []
    return [json.loads(line) for line in SEND_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def _warnings_html(warnings: list[str]) -> str:
    return "".join(
        f'<p style="border:1.5px solid var(--ink);background:#fff7ed;padding:10px 14px">⚠ {_html.escape(w)}</p>'
        for w in warnings
    )


# ---------- 入口 ----------

def main() -> None:
    parser = argparse.ArgumentParser(prog="week05", description="AI 邮件增长工作台(合规触达,dry-run 优先)")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="零密钥零外发:demo 名单 → 全部个性化邮件 + HTML 报告")
    demo.add_argument("--limit", type=int, default=0, help="只取名单前 N 个")
    demo.set_defaults(func=cmd_demo)

    sub.add_parser("doctor", help="体检本周依赖").set_defaults(func=cmd_doctor)

    preview = sub.add_parser("preview", help="按 config.json 的名单生成邮件与预览报告")
    preview.add_argument("--contacts", default="", help="名单 CSV;默认取 config.json 的 contacts_csv")
    preview.add_argument("--limit", type=int, default=0)
    preview.set_defaults(func=cmd_preview)

    send = sub.add_parser("send", help="发送最近一次生成的邮件;默认 dry-run 只写日志")
    send.add_argument("--really", action="store_true", help="真实发送(唯一真发开关;先 --limit 1 发给自己)")
    send.add_argument("--limit", type=int, default=0, help="只发前 N 封 ready 邮件")
    send.set_defaults(func=cmd_send)

    serve = sub.add_parser("serve", help="本地看板:/ 邮件预览,/metrics 发送统计")
    serve.add_argument("--port", type=int, default=0, help="默认取 config.json 的 serve_port(8785)")
    serve.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
