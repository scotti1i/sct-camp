"""news-radar 工作台:`uv run radar` 的默认入口(CLI 子命令是管线,给 AI agent 用)。

页面:/ 总览(跑一遍 Demo)· /digest 今日雷达 · /report 最新日报直出。
run_pipeline / run_demo 是 CLI 与页面共用的唯一产物入口。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from camp_core import load_config, read_json, write_json
from camp_workbench import Workbench, button

from news_radar import OUTPUT_DIR, PROJECT_DIR, RADAR_JSON, SAMPLE_JSON
from news_radar.digest import add_digests, overview_card, profile_table, write_report
from news_radar.rank import rank_items

PORT = 8707

wb = Workbench("News Radar · AI 新闻雷达", "源列表 → 采集 → 双视角打分 → 今日雷达")


# ---------- 产物流水线(CLI 与页面共用) ----------

def run_pipeline(items: list[dict[str, Any]], errors: list[dict[str, str]],
                 config: dict[str, Any], report_name: str, source_label: str) -> dict[str, Any]:
    """打分 + 摘要 + 落盘,demo/digest 共用的唯一入口。"""
    analysis = add_digests(rank_items(items, config, source_label, errors), config)
    write_json(RADAR_JSON, analysis)
    report_path = write_report(analysis, OUTPUT_DIR / report_name)
    counts = ", ".join(f"{p['label']} {len(p['items'])} 条"
                       for p in analysis["profiles"].values())
    print(f"OK radar={RADAR_JSON}")
    print(f"OK report={report_path}")
    print(f"OK 候选 {analysis['item_count']} 条 → {counts}")
    return analysis


def run_demo() -> dict[str, Any]:
    """零密钥零网络:自带虚构样例 → 双视角打分 → demo-report.html。"""
    config = load_config(PROJECT_DIR)
    sample = read_json(SAMPLE_JSON, {})
    items = sample.get("items", [])
    if not items:
        raise RuntimeError(f"演示数据缺失:{SAMPLE_JSON}(试试 git checkout projects/news-radar/data/sample)")
    return run_pipeline(items, [], config, "demo-report.html", "data/sample 演示数据(内容虚构)")


# ---------- 页面 ----------

def _latest_report() -> Path | None:
    candidates = [p for p in (OUTPUT_DIR / "demo-report.html", OUTPUT_DIR / "daily-report.html") if p.exists()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


@wb.route("/", nav="总览")
def home(_query: dict) -> str:
    parts = [
        "<p>盯一组 AI 信息源(RSS/Atom + GitHub 高星搜索):采集 → 双视角打分 → 每天一页「今日雷达」。"
        "两个视角(选题雷达/学员雷达)的关键词和门槛都在 config.json 的 profiles 里,可以改成你自己的。"
        "Demo 用自带虚构样例,零密钥零网络。</p>",
        button("跑一遍 Demo", "/run-demo", large=True),
    ]
    analysis = read_json(RADAR_JSON)
    if analysis:
        parts.append(overview_card(analysis))
        parts.append('<p><a href="/digest">看今日雷达 →</a></p>')
    else:
        parts.append('<p class="muted">还没跑过:点上面的按钮,几秒出结果。</p>')
    if _latest_report():
        parts.append('<p><a href="/report">打开最新日报 →</a></p>')
    return "".join(parts)


@wb.route("/digest", nav="今日雷达")
def digest_page(_query: dict) -> str:
    analysis = read_json(RADAR_JSON)
    if not analysis:
        return "<p>还没有雷达结果:回「总览」跑一遍 Demo。</p>"
    parts = [overview_card(analysis)]
    for profile in analysis.get("profiles", {}).values():
        note = f'<p class="muted">{profile.get("note")}</p>' if profile.get("note") else ""
        parts.append(f"<h2>{profile.get('label')}</h2>{note}" + profile_table(profile.get("items", [])))
    return "".join(parts)


@wb.route("/report")
def report_page(_query: dict) -> str | tuple[bytes, str]:
    path = _latest_report()
    if path is None:
        return "<p>还没有日报:回「总览」跑一遍 Demo。</p>"
    return path.read_bytes(), "text/html; charset=utf-8"


@wb.action("/run-demo")
def run_demo_action(_form: dict) -> tuple[str, str]:
    analysis = run_demo()
    counts = ",".join(f"{p['label']} {len(p['items'])} 条" for p in analysis["profiles"].values())
    return "/", f"Demo 跑完了:候选 {analysis['item_count']} 条 → {counts},日报已更新"


def serve(port: int = 0, open_browser: bool = True) -> None:
    config = load_config(PROJECT_DIR)
    wb.serve(port or int(config.get("serve_port") or PORT), open_browser=open_browser)
