"""Week 4 工作台:`uv run week04` 的默认入口(CLI 子命令是管线,给 AI agent 用)。

页面:/ 总览(跑一遍 Demo + 优先拆解)· /videos 视频清单 · /report 最新日报直出。
run_analysis / run_demo 是 CLI 与页面共用的唯一产物入口。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from camp_core import load_config, read_json, write_json
from camp_workbench import Workbench, button

from week04_competitor_watch import ANALYSIS_JSON, OUTPUT_DIR, PROJECT_DIR, SAMPLE_JSON
from week04_competitor_watch.core import build_analysis
from week04_competitor_watch.reports import actions_table, overview_card, videos_table, write_report

PORT = 8704

wb = Workbench("Week 4 · TikTok 竞品监控", "竞品账号 → 打分 → 优先拆解清单")


# ---------- 产物流水线(CLI 与页面共用) ----------

def run_analysis(snapshots: list[dict[str, Any]], config: dict[str, Any],
                 report_name: str, source_label: str) -> dict[str, Any]:
    """打分 + 落盘,demo/analyze 共用的唯一入口。"""
    analysis = build_analysis(snapshots, config, source_label)
    write_json(ANALYSIS_JSON, analysis)
    report_path = write_report(analysis, OUTPUT_DIR / report_name)
    print(f"OK analysis={ANALYSIS_JSON}")
    print(f"OK report={report_path}")
    print(f"OK 视频 {analysis['video_count']} 条,命中规则 {analysis['matched_count']} 条,"
          f"进拆解清单 {len(analysis['actions'])} 条")
    return analysis


def run_demo() -> dict[str, Any]:
    """零密钥零网络:自带演示快照 → 打分 → demo-report.html。"""
    config = load_config(PROJECT_DIR)
    sample = read_json(SAMPLE_JSON, {})
    snapshots = sample.get("snapshots", [])
    if not snapshots:
        raise RuntimeError(f"演示数据缺失:{SAMPLE_JSON}(试试 git checkout weeks/week04-competitor-watch/data/sample)")
    return run_analysis(snapshots, config, "demo-report.html", "data/sample 演示数据(数字虚构)")


# ---------- 页面 ----------

def _latest_report() -> Path | None:
    candidates = [p for p in (OUTPUT_DIR / "demo-report.html", OUTPUT_DIR / "daily-report.html") if p.exists()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


@wb.route("/", nav="总览")
def home(_query: dict) -> str:
    parts = [
        "<p>盯一批 TikTok 竞品账号:采最新公开视频 → 按播放/互动率打分 → 给出优先拆解清单。"
        "Demo 用自带演示快照,零密钥零网络。</p>",
        button("跑一遍 Demo", "/run-demo", large=True),
    ]
    analysis = read_json(ANALYSIS_JSON)
    if analysis:
        parts.append(overview_card(analysis))
        parts.append("<h2>优先拆解(按优先级排序)</h2>" + actions_table(analysis))
    else:
        parts.append('<p class="muted">还没跑过:点上面的按钮,几秒出结果。</p>')
    if _latest_report():
        parts.append('<p><a href="/report">打开最新报告 →</a></p>')
    return "".join(parts)


@wb.route("/videos", nav="视频清单")
def videos_page(_query: dict) -> str:
    analysis = read_json(ANALYSIS_JSON)
    if not analysis:
        return "<p>还没有分析结果:回「总览」跑一遍 Demo。</p>"
    return "<h2>本轮视频清单</h2>" + videos_table(analysis.get("videos", []))


@wb.route("/report")
def report_page(_query: dict) -> str | tuple[bytes, str]:
    path = _latest_report()
    if path is None:
        return "<p>还没有报告:回「总览」跑一遍 Demo。</p>"
    return path.read_bytes(), "text/html; charset=utf-8"


@wb.action("/run-demo")
def run_demo_action(_form: dict) -> tuple[str, str]:
    analysis = run_demo()
    return "/", (f"Demo 跑完了:视频 {analysis['video_count']} 条,命中规则 {analysis['matched_count']} 条,"
                 f"进拆解清单 {len(analysis['actions'])} 条,日报已更新")


def serve(port: int = 0, open_browser: bool = True) -> None:
    config = load_config(PROJECT_DIR)
    wb.serve(port or int(config.get("serve_port") or PORT), open_browser=open_browser)
