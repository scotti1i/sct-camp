"""选品挖掘工作台:`uv run mining` 的默认入口(CLI 子命令是管线,给 AI agent 用)。

页面:/ 总览(跑一遍 Demo + 机会点排序)· /map 需求地图页 · /report 最新报告直出。
run_analysis / run_demo 是 CLI 与页面共用的唯一产物入口。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from camp_core import load_config, read_json, write_json
from camp_workbench import Workbench, button

from product_mining import ANALYSIS_JSON, EXPRESSIONS_JSONL, INPUT_DIR, OUTPUT_DIR, PROJECT_DIR, SAMPLE_JSON
from product_mining.mapping import evidence_sections, next_steps_card, opportunities_table, overview_card, write_map
from product_mining.signals import extract_signals

PORT = 8708

wb = Workbench("选品挖掘 · 需求信号工作台", "海外用户原话 → 痛点聚类 → 需求地图")


# ---------- 材料装载 ----------

def load_sample() -> list[dict[str, Any]]:
    data = read_json(SAMPLE_JSON, {})
    return data.get("expressions", [])


def load_manual_expressions() -> list[dict[str, Any]]:
    """input/*.md 里以 `> ` 开头的行 = 学员手动粘贴的用户原话,一行一条(代码块里的示例不算)。"""
    expressions = []
    for path in sorted(INPUT_DIR.glob("*.md")):
        in_fence = False
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence and text.startswith("> ") and len(text) > 6:
                expressions.append({"id": f"manual-{len(expressions)+1}", "source": "manual",
                                    "context": f"input/{path.name}", "votes": 0, "text": text[2:].strip()})
    return expressions


def load_collected() -> list[dict[str, Any]]:
    """真实材料 = fetch 落盘的 expressions.jsonl + input/ 里手贴的原话。"""
    expressions = []
    if EXPRESSIONS_JSONL.exists():
        for line in EXPRESSIONS_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                expressions.append(json.loads(line))
    return expressions + load_manual_expressions()


# ---------- 产物流水线(CLI 与页面共用) ----------

def run_analysis(expressions: list[dict[str, Any]], report_name: str, source_label: str) -> dict[str, Any]:
    """提取信号 + 落盘,demo/analyze 共用的唯一入口。"""
    config = load_config(PROJECT_DIR)
    analysis = extract_signals(expressions, config, source_label)
    write_json(ANALYSIS_JSON, analysis)
    report_path = write_map(analysis, OUTPUT_DIR / report_name)
    print(f"OK analysis={ANALYSIS_JSON}")
    print(f"OK report={report_path}")
    print(f"OK 用户表达 {analysis['expression_count']} 条,命中痛点 {analysis['matched_count']} 条,"
          f"机会点 {len(analysis['opportunities'])} 个")
    return analysis


def run_demo() -> dict[str, Any]:
    """零密钥零网络:自带模拟用户表达 → 信号提取 → demo-report.html 需求地图。"""
    expressions = load_sample()
    if not expressions:
        raise RuntimeError(f"演示数据缺失:{SAMPLE_JSON}(试试 git checkout projects/product-mining/data/sample)")
    return run_analysis(expressions, "demo-report.html", "data/sample 模拟用户表达(内容虚构)")


# ---------- 页面 ----------

def _latest_report() -> Path | None:
    candidates = [p for p in (OUTPUT_DIR / "demo-report.html", OUTPUT_DIR / "demand-map.html") if p.exists()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


@wb.route("/", nav="总览")
def home(_query: dict) -> str:
    parts = [
        "<p>从海外真实用户表达里挖需求:收集评论/差评原话 → 痛点聚类 → 机会点排序,"
        "每个机会点都带用户原话证据。Demo 用自带模拟表达,零密钥零网络。</p>",
        button("跑一遍 Demo", "/run-demo", large=True),
    ]
    analysis = read_json(ANALYSIS_JSON)
    if analysis:
        parts.append(overview_card(analysis))
        parts.append("<h2>机会点排序(按得分)</h2>" + opportunities_table(analysis))
        parts.append('<p><a href="/map">看完整需求地图(含原话证据)→</a></p>')
    else:
        parts.append('<p class="muted">还没跑过:点上面的按钮,几秒出结果。</p>')
    return "".join(parts)


@wb.route("/map", nav="需求地图")
def map_page(_query: dict) -> str:
    analysis = read_json(ANALYSIS_JSON)
    if not analysis:
        return "<p>还没有分析结果:回「总览」跑一遍 Demo。</p>"
    return (overview_card(analysis)
            + "<h2>机会点排序(按得分)</h2>" + opportunities_table(analysis)
            + evidence_sections(analysis)
            + next_steps_card(analysis))


@wb.route("/report")
def report_page(_query: dict) -> str | tuple[bytes, str]:
    path = _latest_report()
    if path is None:
        return "<p>还没有报告:回「总览」跑一遍 Demo。</p>"
    return path.read_bytes(), "text/html; charset=utf-8"


@wb.action("/run-demo")
def run_demo_action(_form: dict) -> tuple[str, str]:
    analysis = run_demo()
    return "/", (f"Demo 跑完了:用户表达 {analysis['expression_count']} 条,"
                 f"命中痛点 {analysis['matched_count']} 条,机会点 {len(analysis['opportunities'])} 个,需求地图已更新")


def serve(port: int = 0, open_browser: bool = True) -> None:
    config = load_config(PROJECT_DIR)
    wb.serve(port or int(config.get("serve_port") or PORT), open_browser=open_browser)
