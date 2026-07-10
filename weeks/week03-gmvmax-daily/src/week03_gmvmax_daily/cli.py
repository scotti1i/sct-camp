"""week03 命令行:GMV Max 投流诊断日报机器人。

子命令:
  demo    零密钥,用自带脱敏样例走通 分析 → 4 张模块图 → HTML 日报
  doctor  体检本周依赖(openpyxl / Pillow / 中文字体 / 样例数据)
  analyze 清洗真实导出表,产出 output/clean.csv + analysis.json
  render  按 analysis.json 出模块图 + manifest + HTML 日报
  send    把最近一次模块图卡片发到 config.json 的 chat_id
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from camp_core import load_config, read_json, write_json
from camp_core.doctor import Check, core_checks, run_checks
from camp_lark import send_card, upload_image
from camp_report import kv_card, save_report, table

from week03_gmvmax_daily.analyze import analyze, write_clean
from week03_gmvmax_daily.render import find_font, render_modules

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "output"
SAMPLE_ADS = PROJECT_DIR / "data" / "sample" / "gmv-max-ads-export-sanitized.csv"
SAMPLE_SETTINGS = PROJECT_DIR / "data" / "sample" / "gmv-max-settings-sanitized.csv"
ANALYSIS_JSON = OUTPUT_DIR / "analysis.json"
MANIFEST_JSON = OUTPUT_DIR / "module-manifest.json"


def _resolve(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _run_analyze(input_path: Path, settings_path: Path | None, target_roi: float) -> dict:
    """分析 + 落盘,demo/analyze 共用的唯一入口。"""
    result, clean_rows = analyze(input_path, settings_path, target_roi)
    clean_path = write_clean(clean_rows, OUTPUT_DIR / "clean.csv")
    write_json(ANALYSIS_JSON, result)
    print(f"OK clean={clean_path}")
    print(f"OK analysis={ANALYSIS_JSON}")
    return result


def _run_render(result: dict, config: dict, report_name: str, report_date: str) -> dict:
    """出图 + HTML 日报,demo/render 共用的唯一入口。"""
    manifest = render_modules(result, OUTPUT_DIR / "modules", report_date, config.get("font_paths"))
    for module in manifest["modules"]:
        print(f"OK module={module['file']}")
    report_path = _write_html_report(result, OUTPUT_DIR / report_name)
    print(f"OK report={report_path}")
    return manifest


def _write_html_report(result: dict, path: Path) -> Path:
    """camp_report 一页日报:KPI kv_card + 建议动作 table + Top 计划 table。"""
    totals = result["totals"]
    kpis = kv_card("核心指标", [
        ("数据区间", result["data_range"]),
        ("总消耗", f"{totals['spend']:.2f}"),
        ("总 GMV", f"{totals['gmv']:.2f}"),
        ("整体 ROI", f"{totals['roi']:.2f}(目标 {result['target_roi']:.2f})"),
        ("订单数", int(totals["orders"])),
        ("平均下单成本 CPO", f"{totals['cpo']:.2f}"),
        ("点击到订单转化率", f"{totals['click_to_order']:.2%}"),
    ])
    actions = table(["对象", "建议动作"], [[a["who"], a["what"]] for a in result["actions"]])
    campaigns = table(
        ["计划", "消耗", "GMV", "ROI", "目标", "订单", "阶段", "判断"],
        [[c["name"], f"{c['spend']:.0f}", f"{c['gmv']:.0f}", f"{c['roi']:.2f}",
          f"{c['target_roi']:.2f}", c["orders"], c["stage"], c["verdict"]]
         for c in result["campaigns"][:10]],
    )
    body = kpis + "<h2>今日动作</h2>" + actions + "<h2>计划诊断(按消耗 Top 10)</h2>" + campaigns
    return save_report(path, "GMV Max 投流诊断日报", body, subtitle=f"数据源:{result['source']}")


# ---------- 子命令 ----------

def cmd_demo(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    target_roi = float(config.get("target_roi") or 2.0)
    result = _run_analyze(SAMPLE_ADS, SAMPLE_SETTINGS, target_roi)
    _run_render(result, config, "demo-report.html", args.report_date)
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
    _run_analyze(input_path, settings_path, target_roi)


def cmd_render(args: argparse.Namespace) -> None:
    config = load_config(PROJECT_DIR)
    result = read_json(ANALYSIS_JSON)
    if not result:
        raise SystemExit(f"缺少 {ANALYSIS_JSON}:先跑 uv run week03 analyze(或 demo)")
    _run_render(result, config, "daily-report.html", args.report_date)


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

def main() -> None:
    parser = argparse.ArgumentParser(prog="week03", description="GMV Max 投流诊断日报机器人")
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
