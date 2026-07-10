"""week06 工作台:总览页(一句话 + 跑一遍 Demo + 上次产物)+ 步骤页(六步各自状态)。

界面只用 camp_workbench 的壳;业务逻辑全在 pipeline/steps,这里只是把它们摆上页面。
"""

from __future__ import annotations

import html as _html
from typing import Any

from camp_core import read_json
from camp_report import kv_card, table
from camp_workbench import Workbench, button

from week06_auto_edit import demo, pipeline
from week06_auto_edit.base import DEMO_DIR, DEMO_REPORT, PROJECT_DIR


def _storyboard_table() -> str:
    board = read_json(DEMO_DIR / "storyboard.json") or read_json(
        PROJECT_DIR / "output" / "storyboard.json")
    if not board:
        return ""
    rows = [[i, s["asset"], f"{s['in']}-{s['out']}s", s["role"], s["caption"]]
            for i, s in enumerate(board.get("segments", []), 1)]
    return "<h2>最近一次分镜表</h2>" + table(["#", "镜头", "截取", "角色", "字幕"], rows)


def build(config: dict[str, Any]) -> Workbench:
    wb = Workbench("Week 6 · 自动剪辑流水线",
                   subtitle="素材 → 打标 → 话术分镜 → 配音 → 成片/剪映草稿")

    @wb.route("/", nav="总览")
    def home(_query: dict) -> str:
        intro = (
            '<section class="card"><h2>把产品素材自动剪成 TikTok 竖屏带货视频</h2>'
            '<p class="muted">六步流水线,分镜表(storyboard.json)是唯一中枢。'
            "先点下面的按钮:零密钥、零 ffmpeg,60 秒看懂整条流水线怎么想问题。</p>"
            f'{button("跑一遍 Demo", "/run-demo", large=True)}</section>'
        )
        items = pipeline.artifacts()
        if items:
            rows = [[name, str(path.relative_to(PROJECT_DIR))] for name, path in items]
            produced = "<h2>上次产物</h2>" + table(["产物", "位置(项目目录内)"], rows)
            if DEMO_REPORT.exists():
                produced += '<p><a href="/report">打开 Demo 流程报告 →</a></p>'
        else:
            produced = '<p class="muted">还没有产物:点上面「跑一遍 Demo」。</p>'
        return intro + produced + _storyboard_table()

    @wb.route("/steps", nav="流水线")
    def steps_page(_query: dict) -> str:
        blocks = []
        for state in pipeline.step_states():
            detail = f'<p class="muted">{_html.escape(state["detail"])}</p>' if state["detail"] else ""
            blocks.append(
                f'<section class="card"><h2>{_html.escape(state["title"])}</h2>'
                f'<p class="muted">{_html.escape(state["desc"])}</p>'
                f'<div class="kv"><span>产物状态</span><b>{_html.escape(state["status"])}</b></div>'
                f"{detail}"
                f'{button("运行这一步", f"/run-{state["key"]}")}'
                f'<p class="muted">命令行等价:<b>{_html.escape(state["command"])}</b></p></section>'
            )
        note = kv_card("说明", [
            ("真实素材", "放 input/assets/(5-30 秒竖屏片段),再从 ① 开始"),
            ("零密钥路径", "③ 无 LLM 密钥时自动用 mock 模板;② 可跳过,手写 assets.json 的 note"),
            ("改片子", "直接改 output/storyboard.json,再跑 ④⑤ 即可"),
        ])
        return note + "".join(blocks)

    @wb.route("/report")
    def report_page(_query: dict) -> str | tuple[bytes, str]:
        if not DEMO_REPORT.exists():
            return "<p>还没有报告:回「总览」跑一遍 Demo。</p>"
        return DEMO_REPORT.read_bytes(), "text/html; charset=utf-8"

    @wb.action("/run-demo")
    def run_demo(_form: dict) -> tuple[str, str]:
        demo.run_demo(config)
        return "/", "Demo 完成:分镜表/字幕/流程报告都在 output/demo/(报告 output/demo-report.html)"

    def register(step_key: str) -> None:
        @wb.action(f"/run-{step_key}")
        def run_step(_form: dict) -> tuple[str, str]:
            return "/steps", pipeline.step_by_key(step_key).run(config)

    for step in pipeline.STEPS:
        register(step.key)
    return wb


def serve(config: dict[str, Any], port: int, open_browser: bool = True) -> None:
    build(config).serve(port, open_browser=open_browser)
