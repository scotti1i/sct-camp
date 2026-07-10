"""week03 命令行:GMV Max 投流诊断日报机器人。

无参数 = 默认入口:浏览器打开工作台(点「跑一遍 Demo」出结果,全程不看终端)。
子命令是管线,给 AI agent 和自动化用:
  demo    零密钥,用自带脱敏样例走通 分析 → 4 张模块图 → HTML 日报
  doctor  体检本周依赖(openpyxl / Pillow / 中文字体 / 样例数据)
  analyze 清洗真实导出表,产出 output/clean.csv + analysis.json
  render  按 analysis.json 出模块图 + manifest + HTML 日报
  send    把最近一次模块图卡片发到 config.json 的 chat_id
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from camp_core import load_config, read_json, write_json
from camp_core.doctor import Check, core_checks, run_checks
from camp_lark import send_card, upload_image

from week03_gmvmax_daily import ANALYSIS_JSON, MANIFEST_JSON, OUTPUT_DIR, PROJECT_DIR, SAMPLE_ADS
from week03_gmvmax_daily import workbench
from week03_gmvmax_daily.render import find_font


def _resolve(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


# ---------- 子命令 ----------

def cmd_demo(args: argparse.Namespace) -> None:
    workbench.run_demo(args.report_date)
    print("OK demo 完成。产物都在 output/;想发飞书:填好 config.json 的 chat_id 后跑 uv run week03 send")


def cmd_doctor(_: argparse.Namespace) -> None:
    ok = run_checks(core_checks() + week_checks())
    print("week03 环境全绿。" if ok else "按 [FIX] 提示逐条修复后重跑。")
    raise SystemExit(0 if ok else 1)


def week_checks() -> list[Check]:
    def importable(name: str) -> tuple[bool, str]:
        try:
            __import__(name)
            return True, ""
        except ImportError:
            return False, "在仓库根运行 uv sync"

    return [
        Check("openpyxl 可用(读 XLSX 导出)", lambda: importable("openpyxl")),
        Check("Pillow 可用(画模块图)", lambda: importable("PIL")),
        Check("中文字体可用(模块图不出豆腐块)", lambda: (bool(find_font()), "在 config.json 的 font_paths 里填一个中文字体路径")),
        Check("脱敏样例数据在位(demo 需要)", lambda: (SAMPLE_ADS.exists(), "git checkout weeks/week03-gmvmax-daily/data/sample")),
    ]


def cmd_analyze(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    input_path = _resolve(args.input or str(config.get("input") or "")) if (args.input or config.get("input")) else SAMPLE_ADS
    settings_text = args.settings or str(config.get("settings") or "")
    settings_path = _resolve(settings_text) if settings_text else None
    target_roi = args.target_roi or float(config.get("target_roi") or 2.0)
    if not input_path.exists():
        raise SystemExit(f"找不到导出表:{input_path}。用 --input 指定,或先跑 uv run week03 demo")
    workbench.run_analyze(input_path, settings_path, target_roi)


def cmd_render(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    result = read_json(ANALYSIS_JSON)
    if not result:
        raise SystemExit(f"缺少 {ANALYSIS_JSON}:先跑 uv run week03 analyze(或 demo)")
    workbench.run_render(result, config, "daily-report.html", args.report_date)


def cmd_send(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    chat_id = args.chat_id or str(config.get("chat_id") or "")
    if not chat_id or "替换" in chat_id:
        raise SystemExit("缺少 chat_id:把内部测试群的 oc_xxx 填进 config.json(config.example.json 有说明),或用 --chat-id 传入")
    manifest = read_json(MANIFEST_JSON)
    if not manifest:
        raise SystemExit(f"缺少 {MANIFEST_JSON}:先跑 uv run week03 demo(或 analyze + render)")
    uploaded = []
    for module in manifest["modules"]:
        image_key = upload_image(Path(module["file"]))
        uploaded.append({**module, "image_key": image_key})
        print(f"OK upload={Path(module['file']).name} image_key={image_key}")
    response = send_card(chat_id, _build_card(manifest, uploaded))
    write_json(OUTPUT_DIR / "send-result.json", {"chat_id": chat_id, "manifest": manifest["report_date"], "response": response})
    print(f"OK send chat_id={chat_id},回执见 {OUTPUT_DIR / 'send-result.json'}")


def _build_card(manifest: dict, uploaded: list[dict]) -> dict:
    """飞书卡片:标题带整体 ROI,正文 4 张模块图按顺序排。"""
    totals = manifest["totals"]
    roi = float(totals["roi"])
    elements: list[dict] = [
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**数据区间**:{manifest['data_range']}  |  **ROI**:{roi:.2f}  |  **订单**:{int(totals['orders'])}"}},
        {"tag": "hr"},
    ]
    for item in uploaded:
        elements.append({"tag": "img", "img_key": item["image_key"],
                         "alt": {"tag": "plain_text", "content": item["title"]},
                         "mode": "fit_horizontal", "preview": True})
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": item["title"]}]})
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if roi >= float(manifest["target_roi"]) else "red",
            "title": {"tag": "plain_text", "content": f"GMV Max 日报｜ROI {roi:.2f}"},
        },
        "elements": elements,
    }


# ---------- 入口 ----------

def cmd_workbench(argv: list[str]) -> None:
    """无参数默认入口:浏览器打开工作台;子命令是给 AI agent 和自动化的。"""
    parser = argparse.ArgumentParser(prog="week03", description="GMV Max 投流诊断日报(工作台)")
    parser.add_argument("--port", type=int, default=0, help=f"默认 {workbench.PORT}")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器(测试用)")
    args = parser.parse_args(argv)
    workbench.serve(port=args.port, open_browser=not args.no_browser)


def main() -> None:
    argv = sys.argv[1:]
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        cmd_workbench(argv)
        return
    parser = argparse.ArgumentParser(
        prog="week03", description="GMV Max 投流诊断日报机器人",
        epilog="不带子命令直接运行 = 打开工作台(默认入口);子命令给 AI agent 和自动化用。")
    sub = parser.add_subparsers(dest="command", required=True)
    today = date.today().isoformat()

    demo = sub.add_parser("demo", help="零密钥跑通:样例数据 → 模块图 + HTML 日报")
    demo.add_argument("--report-date", default=today)
    demo.set_defaults(func=cmd_demo)

    sub.add_parser("doctor", help="体检本周依赖").set_defaults(func=cmd_doctor)

    analyze_cmd = sub.add_parser("analyze", help="清洗导出表并生成诊断结果")
    analyze_cmd.add_argument("--input", default="", help="广告导出 CSV/XLSX;默认取 config.json 的 input")
    analyze_cmd.add_argument("--settings", default="", help="可选 settings 表(目标 ROI / 阶段 / 预算)")
    analyze_cmd.add_argument("--target-roi", type=float, help="全局目标 ROI;默认取 config.json")
    analyze_cmd.set_defaults(func=cmd_analyze)

    render = sub.add_parser("render", help="按最近一次分析结果出模块图和 HTML 日报")
    render.add_argument("--report-date", default=today)
    render.set_defaults(func=cmd_render)

    send = sub.add_parser("send", help="把最近一次模块图卡片发到飞书群")
    send.add_argument("--chat-id", default="", help="覆盖 config.json 的 chat_id")
    send.set_defaults(func=cmd_send)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
