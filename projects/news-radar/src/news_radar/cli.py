"""radar 命令行:AI 新闻雷达。

无参数 = 默认入口:浏览器打开工作台(点「跑一遍 Demo」出结果,全程不看终端)。
子命令是管线,给 AI agent 和自动化用:
  demo    零密钥零网络:虚构样例 → 双视角打分 → output/demo-report.html
  doctor  体检本项目(源列表 / 样例数据 / 可选 LLM 密钥)
  fetch   真实采集:data/sources.json 全部源 → output/items.json(--limit N 只拉前 N 个源)
  digest  打分最近一轮采集 → output/radar.json + daily-report.html
  send    今日雷达 → 飞书卡片(camp_lark;--dry-run 只写 card-preview.json)
  serve   打开工作台(等价于无参数运行)
"""

from __future__ import annotations

import argparse
import sys

from camp_core import load_config, now_iso, read_json, secret, write_json
from camp_core.doctor import Check, core_checks, run_checks
from camp_lark import send_card

from news_radar import OUTPUT_DIR, PROJECT_DIR, PULL_JSON, RADAR_JSON, SAMPLE_JSON, SOURCES_JSON
from news_radar import workbench
from news_radar.digest import build_card
from news_radar.sources import FRIENDLY_HINT, fetch_all


# ---------- 子命令 ----------

def cmd_demo(_: argparse.Namespace) -> None:
    try:
        workbench.run_demo()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("OK demo 完成。工作台:uv run radar;真实采集:uv run radar fetch")


def project_checks() -> list[Check]:
    def sources_ok() -> tuple[bool, str]:
        data = read_json(SOURCES_JSON, {})
        count = len(data.get("feeds", [])) + len(data.get("github_searches", []))
        return count > 0, "git checkout projects/news-radar/data/sources.json"

    def llm_ok() -> tuple[bool, str]:
        return True, ""  # 可选项永远绿:有 key 走 LLM 摘要,没 key 走纯规则

    return [
        Check("源列表在位(data/sources.json)", sources_ok),
        Check("演示数据在位(demo 需要)",
              lambda: (SAMPLE_JSON.exists(), "git checkout projects/news-radar/data/sample")),
        Check(f"LLM 摘要可选({'已配 LLM_API_KEY,走 LLM' if secret('LLM_API_KEY') else '没配 LLM_API_KEY,走纯规则,不影响使用'})",
              llm_ok),
    ]


def cmd_doctor(_: argparse.Namespace) -> None:
    ok = run_checks(core_checks() + project_checks())
    print("news-radar 环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑。")
    raise SystemExit(0 if ok else 1)


def cmd_fetch(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    sources_cfg = read_json(SOURCES_JSON, {})
    if not sources_cfg:
        raise SystemExit(f"缺少 {SOURCES_JSON}:先 git checkout 恢复源列表")
    items, errors = fetch_all(sources_cfg, config, source_limit=args.limit)
    if not items:
        raise SystemExit(f"这一轮一条都没拿到。{FRIENDLY_HINT}")
    write_json(PULL_JSON, {"fetched_at": now_iso(), "items": items, "errors": errors})
    print(f"OK fetch {len(items)} 条(失败源 {len(errors)} 个)→ {PULL_JSON}")
    print("下一步:uv run radar digest")


def cmd_digest(_: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    pull = read_json(PULL_JSON, {})
    items = pull.get("items", [])
    if not items:
        raise SystemExit(f"缺少 {PULL_JSON}:先跑 uv run radar fetch(或先用 demo 看效果)")
    workbench.run_pipeline(items, pull.get("errors", []), config,
                           "daily-report.html", "output/items.json 真实采集")


def cmd_send(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    analysis = read_json(RADAR_JSON)
    if not analysis:
        raise SystemExit(f"缺少 {RADAR_JSON}:先跑 uv run radar demo(或 fetch + digest)")
    matched = sum(len(p.get("items", [])) for p in analysis.get("profiles", {}).values())
    if matched == 0:
        raise SystemExit("今日雷达是空的,宁可不发,也不要给群里灌水。")
    card = build_card(analysis, str(config.get("title") or "AI 新闻雷达"))
    write_json(OUTPUT_DIR / "card-preview.json", card)
    print(f"OK 卡片预览 → {OUTPUT_DIR / 'card-preview.json'}")
    if args.dry_run:
        print("DRY-RUN 未发送。去掉 --dry-run 真实发送。")
        return
    chat_id = args.chat_id or str(config.get("feishu", {}).get("chat_id") or "")
    if not chat_id:
        raise SystemExit("缺少 chat_id:填 config.json 的 feishu.chat_id,或 --chat-id oc_xxx")
    send_card(chat_id, card)
    print(f"OK 已发送到 {chat_id}")


def cmd_serve(args: argparse.Namespace) -> None:
    workbench.serve(port=args.port, open_browser=not args.no_browser)


# ---------- 入口 ----------

def cmd_workbench(argv: list[str]) -> None:
    """无参数默认入口:浏览器打开工作台;子命令是给 AI agent 和自动化的。"""
    parser = argparse.ArgumentParser(prog="radar", description="AI 新闻雷达(工作台)")
    parser.add_argument("--port", type=int, default=0, help=f"默认 {workbench.PORT}(config.json 的 serve_port 可覆盖)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器(测试用)")
    args = parser.parse_args(argv)
    workbench.serve(port=args.port, open_browser=not args.no_browser)


def main() -> None:
    argv = sys.argv[1:]
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        cmd_workbench(argv)
        return
    parser = argparse.ArgumentParser(
        prog="radar", description="AI 新闻雷达",
        epilog="不带子命令直接运行 = 打开工作台(默认入口);子命令给 AI agent 和自动化用。")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="零密钥零网络:虚构样例 → 双视角打分 → HTML 日报").set_defaults(func=cmd_demo)
    sub.add_parser("doctor", help="体检本项目").set_defaults(func=cmd_doctor)
    fetch = sub.add_parser("fetch", help="真实采集全部源(RSS/Atom + GitHub 搜索)")
    fetch.add_argument("--limit", type=int, default=0, help="只拉前 N 个源(快速验证采集活着)")
    fetch.set_defaults(func=cmd_fetch)
    sub.add_parser("digest", help="打分最近一轮采集并生成今日雷达").set_defaults(func=cmd_digest)
    send = sub.add_parser("send", help="今日雷达发飞书卡片(camp_lark)")
    send.add_argument("--chat-id", default="", help="覆盖 config.json 的 feishu.chat_id")
    send.add_argument("--dry-run", action="store_true", help="只写 output/card-preview.json,不发送")
    send.set_defaults(func=cmd_send)
    serve = sub.add_parser("serve", help="打开工作台(等价于无参数运行)")
    serve.add_argument("--port", type=int, default=0, help="覆盖 config.json 的 serve_port")
    serve.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
