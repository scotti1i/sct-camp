"""Week 2 工作台:`uv run week02` 的默认入口(CLI 子命令是管线,给 AI agent 用)。

页面:/ 总览(跑一遍 Demo)· /tasks 任务表 · /report 最新 HTML 报告直出。
run_demo 是 CLI 与页面共用的唯一 demo 流水线入口。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from camp_core import load_config, now_iso
from camp_report import kv_card, save_report, table
from camp_workbench import Workbench, button

from week02_video_factory import pipeline

PORT = 8702
REPORT_HTML = pipeline.OUTPUT_DIR / "demo-report.html"

wb = Workbench("Week 2 · 批量视频工厂", "一个产品信息 → 一批短视频生成任务")


# ---------- demo 流水线(CLI 与页面共用) ----------

def run_demo(count: int = 8) -> dict[str, Any]:
    """零密钥 mock 流水线:脚本 → prompt → 提交 → 轮询 → HTML 报告。"""
    config = load_config(pipeline.PROJECT_DIR)
    tasks = pipeline.generate_scripts(config, count)
    print(f"[1/4] 已生成 {len(tasks)} 条脚本")
    pipeline.generate_prompts(config)
    print(f"[2/4] 已生成 {len(tasks)} 条分镜 prompt")
    submitted, _ = pipeline.submit_tasks(config, "mock")
    print(f"[3/4] 已 mock 提交 {submitted} 条任务")
    success, tasks = pipeline.poll_tasks(config)
    print(f"[4/4] 轮询完成,{success} 条生成成功")
    report = _demo_report(config, tasks, success)
    return {"tasks": len(tasks), "success": success, "report": report}


def _demo_report(config: dict[str, Any], tasks: list[dict[str, Any]], success: int) -> str:
    audience = config.get("product", {}).get("audience", "")
    rows = [
        [t["任务编号"], t["产品名"], audience, t["分镜 prompt"][:80] + "…", t["状态"]]
        for t in tasks
    ]
    body = kv_card("本次 demo", [
        ("任务数", len(tasks)),
        ("provider", "mock"),
        ("生成成功", success),
        ("生成时间", now_iso()),
    ])
    body += table(["任务编号", "产品", "人群", "分镜 prompt", "状态"], rows)
    path = save_report(REPORT_HTML, "Week 2 批量视频工厂", body, subtitle="demo 结果报告(mock 流水线)")
    return str(path)


# ---------- 页面 ----------

def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


@wb.route("/", nav="总览")
def home(_query: dict) -> str:
    parts = [
        "<p>把一个产品信息变成一批短视频生成任务:脚本 → 分镜 prompt → 提交生成 → 轮询结果。"
        "Demo 走零密钥 mock 流水线,十几秒出一份结果报告。</p>",
        button("跑一遍 Demo", "/run-demo", large=True),
    ]
    tasks = pipeline.load_tasks()
    if tasks:
        success = sum(1 for t in tasks if t.get("状态") == "生成成功")
        parts.append(kv_card("上次运行", [
            ("任务数", len(tasks)),
            ("生成成功", success),
            ("运行时间", _mtime(pipeline.TASKS_FILE)),
        ]))
    else:
        parts.append('<p class="muted">还没跑过:点上面的按钮,十几秒出结果。</p>')
    if REPORT_HTML.exists():
        parts.append('<p><a href="/report">打开最新报告 →</a></p>')
    return "".join(parts)


@wb.route("/tasks", nav="任务表")
def tasks_page(_query: dict) -> str:
    tasks = pipeline.load_tasks()
    if not tasks:
        return "<p>还没有任务:回「总览」跑一遍 Demo。</p>"
    rows = [
        [t["任务编号"], t["产品名"], t["参考结构"].split(":")[0], t["脚本"][:60] + "…", t["状态"]]
        for t in tasks
    ]
    return "<h2>任务表(output/tasks.json)</h2>" + table(["任务编号", "产品", "结构", "脚本", "状态"], rows)


@wb.route("/report")
def report_page(_query: dict) -> str | tuple[bytes, str]:
    if not REPORT_HTML.exists():
        return "<p>还没有报告:回「总览」跑一遍 Demo。</p>"
    return REPORT_HTML.read_bytes(), "text/html; charset=utf-8"


@wb.action("/run-demo")
def run_demo_action(_form: dict) -> tuple[str, str]:
    result = run_demo()
    return "/", f"Demo 跑完了:{result['tasks']} 条任务,{result['success']} 条生成成功,报告已更新"


def serve(port: int = 0, open_browser: bool = True) -> None:
    wb.serve(port or PORT, open_browser=open_browser)
