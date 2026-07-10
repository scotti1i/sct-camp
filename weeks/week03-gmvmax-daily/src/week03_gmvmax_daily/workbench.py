"""Week 3 工作台:`uv run week03` 的默认入口(CLI 子命令是管线,给 AI agent 用)。

页面:/ 总览(跑一遍 Demo)· /analysis 核心指标 · /report 最新日报直出。
run_analyze / run_render / run_demo 是 CLI 与页面共用的唯一产物入口。
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from camp_core import load_config, read_json, write_json
from camp_report import kv_card, save_report, table
from camp_workbench import Workbench, button

from week03_gmvmax_daily import ANALYSIS_JSON, OUTPUT_DIR, PROJECT_DIR, SAMPLE_ADS, SAMPLE_SETTINGS
from week03_gmvmax_daily.analyze import analyze, write_clean
from week03_gmvmax_daily.render import render_modules

PORT = 8703

wb = Workbench("Week 3 · GMV Max 投流日报", "后台导出表 → 诊断 → 模块图 + 日报")


# ---------- 产物流水线(CLI 与页面共用) ----------

def run_analyze(input_path: Path, settings_path: Path | None, target_roi: float) -> dict:
    """分析 + 落盘,demo/analyze 共用的唯一入口。"""
    result, clean_rows = analyze(input_path, settings_path, target_roi)
    clean_path = write_clean(clean_rows, OUTPUT_DIR / "clean.csv")
    write_json(ANALYSIS_JSON, result)
    print(f"OK clean={clean_path}")
    print(f"OK analysis={ANALYSIS_JSON}")
    return result


def run_render(result: dict, config: dict, report_name: str, report_date: str) -> dict:
    """出图 + HTML 日报,demo/render 共用的唯一入口。"""
    manifest = render_modules(result, OUTPUT_DIR / "modules", report_date, config.get("font_paths"))
    for module in manifest["modules"]:
        print(f"OK module={module['file']}")
    report_path = save_report(OUTPUT_DIR / report_name, "GMV Max 投流诊断日报",
                              report_body(result), subtitle=f"数据源:{result['source']}")
    print(f"OK report={report_path}")
    return manifest


def run_demo(report_date: str = "") -> dict:
    """零密钥 demo:脱敏样例 → 分析 → 4 张模块图 + HTML 日报。"""
    config = load_config(PROJECT_DIR)
    target_roi = float(config.get("target_roi") or 2.0)
    result = run_analyze(SAMPLE_ADS, SAMPLE_SETTINGS, target_roi)
    run_render(result, config, "demo-report.html", report_date or date.today().isoformat())
    return result


def report_body(result: dict) -> str:
    """KPI kv_card + 建议动作 table + Top 计划 table,日报与 /analysis 页共用。"""
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
    return kpis + "<h2>今日动作</h2>" + actions + "<h2>计划诊断(按消耗 Top 10)</h2>" + campaigns


# ---------- 页面 ----------

def _latest_report() -> Path | None:
    candidates = [p for p in (OUTPUT_DIR / "demo-report.html", OUTPUT_DIR / "daily-report.html") if p.exists()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


@wb.route("/", nav="总览")
def home(_query: dict) -> str:
    parts = [
        "<p>把 GMV Max 后台导出表变成一份投流诊断:整体 ROI、每个计划的判断、今日动作、"
        "4 张可直接发群的模块图。Demo 用自带脱敏样例,零密钥。</p>",
        button("跑一遍 Demo", "/run-demo", large=True),
    ]
    result = read_json(ANALYSIS_JSON)
    if result:
        totals = result["totals"]
        parts.append(kv_card("上次运行", [
            ("数据区间", result["data_range"]),
            ("总消耗", f"{totals['spend']:.2f}"),
            ("总 GMV", f"{totals['gmv']:.2f}"),
            ("整体 ROI", f"{totals['roi']:.2f}(目标 {result['target_roi']:.2f})"),
            ("订单数", int(totals["orders"])),
            ("运行时间", _mtime(ANALYSIS_JSON)),
        ]))
    else:
        parts.append('<p class="muted">还没跑过:点上面的按钮,几秒出结果。</p>')
    if _latest_report():
        parts.append('<p><a href="/report">打开最新报告 →</a></p>')
    return "".join(parts)


@wb.route("/analysis", nav="核心指标")
def analysis_page(_query: dict) -> str:
    result = read_json(ANALYSIS_JSON)
    if not result:
        return "<p>还没有分析结果:回「总览」跑一遍 Demo。</p>"
    return report_body(result)


@wb.route("/report")
def report_page(_query: dict) -> str | tuple[bytes, str]:
    path = _latest_report()
    if path is None:
        return "<p>还没有报告:回「总览」跑一遍 Demo。</p>"
    return path.read_bytes(), "text/html; charset=utf-8"


@wb.action("/run-demo")
def run_demo_action(_form: dict) -> tuple[str, str]:
    result = run_demo()
    totals = result["totals"]
    return "/", (f"Demo 跑完了:整体 ROI {totals['roi']:.2f}(目标 {result['target_roi']:.2f}),"
                 f"订单 {int(totals['orders'])} 单,模块图和日报已更新")


def serve(port: int = 0, open_browser: bool = True) -> None:
    wb.serve(port or PORT, open_browser=open_browser)
