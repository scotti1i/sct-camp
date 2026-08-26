"""week05 命令行:AI 邮件增长工作台(合规触达,dry-run 优先)。

无参数 = 默认入口:浏览器打开工作台(点「跑一遍 Demo」出结果,全程不看终端)。
子命令是管线,给 AI agent 和自动化用:
  demo    零密钥零外发:自带 demo 名单 → 全部个性化邮件 → output/demo-report.html
  doctor  体检本周依赖(demo 名单 / 邮件模板 / 生成链路 / RESEND_API_KEY 状态)
  preview 按 config.json 的名单生成邮件 → output/emails.json + preview-report.html
  send    默认 dry-run 只写日志;--really 才通过 Resend 真实发送
  serve   打开工作台(等价于无参数运行)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from camp_core import append_jsonl, load_config, now_iso, read_json, secret, write_json
from camp_core.doctor import Check, core_checks, run_checks

from week05_email_growth import EMAILS_JSON, OUTPUT_DIR, PROJECT_DIR, SEND_LOG
from week05_email_growth import compose, resend_api, workbench


def _resolve(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


# ---------- 子命令 ----------

def cmd_demo(args: argparse.Namespace) -> None:
    result = workbench.run_demo(args.limit)
    print(f"OK report={result['report']}")
    print("OK demo 完成:零密钥零外发。dry-run:uv run week05 send;工作台:uv run week05")


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
    summary, emails = workbench.build_batch(config, contacts_path, args.limit)
    report = workbench.write_report(summary, emails, "preview-report.html")
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
    workbench.serve(port=args.port, open_browser=not args.no_browser)


# ---------- 入口 ----------

def cmd_workbench(argv: list[str]) -> None:
    """无参数默认入口:浏览器打开工作台;子命令是给 AI agent 和自动化的。"""
    parser = argparse.ArgumentParser(prog="week05", description="AI 邮件增长工作台")
    parser.add_argument("--port", type=int, default=0, help=f"默认 {workbench.PORT}(config.json 的 serve_port 可覆盖)")
    parser.add_argument("--no-browser", "--no-open", action="store_true", help="不自动打开浏览器(测试用)")
    args = parser.parse_args(argv)
    workbench.serve(port=args.port, open_browser=not args.no_browser)


def main() -> None:
    argv = sys.argv[1:]
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        cmd_workbench(argv)
        return
    parser = argparse.ArgumentParser(
        prog="week05", description="AI 邮件增长工作台(合规触达,dry-run 优先)",
        epilog="不带子命令直接运行 = 打开工作台(默认入口);子命令给 AI agent 和自动化用。")
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

    serve = sub.add_parser("serve", help="打开工作台(等价于无参数运行)")
    serve.add_argument("--port", type=int, default=0, help="默认取 config.json 的 serve_port(8705)")
    serve.add_argument("--no-browser", "--no-open", action="store_true", dest="no_browser", help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
