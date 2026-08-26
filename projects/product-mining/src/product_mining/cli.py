"""mining 命令行:选品挖掘(用户表达 → 需求信号 → 需求地图)。

无参数 = 默认入口:浏览器打开工作台(点「跑一遍 Demo」出结果,全程不看终端)。
子命令是管线,给 AI agent 和自动化用:
  demo    零密钥零网络:模拟用户表达 → 信号提取 → output/demo-report.html 需求地图
  doctor  体检(演示数据 / 配置模板 / input 模板)
  fetch   真实采集:Reddit 公开 JSON / Amazon Woot 差评 → output/expressions.jsonl(追加)
  analyze 提取已采集材料(expressions.jsonl + input/ 手贴原话)→ analysis.json + demand-map.html
  map     只重渲染需求地图(analysis.json → demand-map.html)
  serve   打开工作台(等价于无参数运行)
"""

from __future__ import annotations

import argparse
import sys
from urllib import error

from camp_core import append_jsonl, read_json
from camp_core.doctor import Check, core_checks, run_checks

from product_mining import ANALYSIS_JSON, EXPRESSIONS_JSONL, INPUT_DIR, OUTPUT_DIR, PROJECT_DIR, SAMPLE_JSON
from product_mining import workbench
from product_mining.fetch import FRIENDLY_HINT, fetch_amazon_bad_reviews, fetch_reddit
from product_mining.mapping import write_map


# ---------- 子命令 ----------

def cmd_demo(_: argparse.Namespace) -> None:
    try:
        workbench.run_demo()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("OK demo 完成。工作台:uv run mining;真实采集:uv run mining fetch --keyword \"你的品类词\"")


def project_checks() -> list[Check]:
    return [
        Check("演示数据在位(demo 需要)",
              lambda: (bool(read_json(SAMPLE_JSON, {}).get("expressions")),
                       "git checkout projects/product-mining/data/sample")),
        Check("配置模板在位(config.example.json)",
              lambda: ((PROJECT_DIR / "config.example.json").exists(),
                       "git checkout projects/product-mining/config.example.json")),
        Check("input/ 采集模板在位",
              lambda: (any(INPUT_DIR.glob("*.md")), "git checkout projects/product-mining/input")),
    ]


def cmd_doctor(_: argparse.Namespace) -> None:
    ok = run_checks(core_checks() + project_checks())
    print("product-mining 环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑。")
    raise SystemExit(0 if ok else 1)


def cmd_fetch(args: argparse.Namespace) -> None:
    if not args.keyword and not args.asin:
        raise SystemExit('至少给一个目标:--keyword "pet hair remover"(Reddit)或 --asin B0XXXXXXXX(Amazon 差评)')
    expressions = []
    try:
        if args.keyword:
            expressions += fetch_reddit(args.keyword, args.limit)
        if args.asin:
            expressions += fetch_amazon_bad_reviews(args.asin, args.limit * 4)
    except (error.URLError, error.HTTPError, TimeoutError, ValueError) as exc:
        raise SystemExit(f"采集失败:{exc}\n{FRIENDLY_HINT}") from exc
    if not expressions:
        raise SystemExit(f"这一轮一条都没拿到。{FRIENDLY_HINT}")
    append_jsonl(EXPRESSIONS_JSONL, expressions)
    print(f"OK fetch {len(expressions)} 条用户表达 → {EXPRESSIONS_JSONL}")
    print("下一步:uv run mining analyze")


def cmd_analyze(_: argparse.Namespace) -> None:
    expressions = workbench.load_collected()
    if not expressions:
        raise SystemExit("还没有材料:先 uv run mining fetch,或把用户原话以「> 原话」格式贴进 input/*.md"
                         "(想先看效果就跑 uv run mining demo)")
    workbench.run_analysis(expressions, "demand-map.html", "expressions.jsonl + input/ 真实材料")


def cmd_map(_: argparse.Namespace) -> None:
    analysis = read_json(ANALYSIS_JSON)
    if not analysis:
        raise SystemExit(f"缺少 {ANALYSIS_JSON}:先跑 uv run mining demo(或 fetch + analyze)")
    path = write_map(analysis, OUTPUT_DIR / "demand-map.html")
    print(f"OK 需求地图已重渲染 → {path}")


def cmd_serve(args: argparse.Namespace) -> None:
    workbench.serve(port=args.port, open_browser=not args.no_browser)


# ---------- 入口 ----------

def cmd_workbench(argv: list[str]) -> None:
    """无参数默认入口:浏览器打开工作台;子命令是给 AI agent 和自动化的。"""
    parser = argparse.ArgumentParser(prog="mining", description="选品挖掘(工作台)")
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
        prog="mining", description="选品挖掘:海外用户表达 → 需求信号 → 需求地图",
        epilog="不带子命令直接运行 = 打开工作台(默认入口);子命令给 AI agent 和自动化用。")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="零密钥零网络:模拟表达 → 需求地图 demo-report.html").set_defaults(func=cmd_demo)
    sub.add_parser("doctor", help="体检本项目依赖与数据").set_defaults(func=cmd_doctor)
    fetch = sub.add_parser("fetch", help="真实采集:Reddit 公开 JSON / Amazon Woot 差评")
    fetch.add_argument("--keyword", default="", help='Reddit 搜索词,如 "pet hair remover"')
    fetch.add_argument("--asin", default="", help="Amazon ASIN(走 Woot JSON 拉 1-3 星差评)")
    fetch.add_argument("--limit", type=int, default=5, help="Reddit 帖子数(默认 5;Amazon 为 4 倍差评数)")
    fetch.set_defaults(func=cmd_fetch)
    sub.add_parser("analyze", help="提取真实材料 → analysis.json + demand-map.html").set_defaults(func=cmd_analyze)
    sub.add_parser("map", help="只重渲染需求地图(analysis.json → demand-map.html)").set_defaults(func=cmd_map)
    serve = sub.add_parser("serve", help="打开工作台(等价于无参数运行)")
    serve.add_argument("--port", type=int, default=0, help="覆盖 config.json 的 serve_port")
    serve.add_argument("--no-browser", "--no-open", action="store_true", help="不自动打开浏览器")
    serve.set_defaults(func=cmd_serve)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
