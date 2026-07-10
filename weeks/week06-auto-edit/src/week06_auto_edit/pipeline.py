"""六步流水线编排:步骤只在这里定义一次,CLI 子命令和工作台按钮共用。

数据流(storyboard.json 是唯一中枢,所有出口只吃它):
input/assets/*.mp4 → ①analyze → ②label → ③script(话术+分镜) → ④voice → ⑤render / ⑥jianying
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from week06_auto_edit import llm
from week06_auto_edit.base import (
    ASSETS_JSON, DEMO_DIR, DEMO_REPORT, FINAL_MP4, PROJECT_DIR,
    SCRIPT_JSON, STORYBOARD_JSON, VOICE_DIR,
)
from week06_auto_edit.steps import analyze, jianying, label, render, script, voice


@dataclass
class Step:
    key: str
    title: str
    desc: str
    command: str
    outputs: list[Path]
    run: Callable[[dict[str, Any]], str]  # 返回一句完成提示


def _run_script(config: dict[str, Any]) -> str:
    mock = not llm.have_llm()
    script.run(config, mock=mock)
    return "话术 + 分镜已生成" + ("(mock 模板,配好 LLM 密钥后是全 AI 流程)" if mock else "")


STEPS: list[Step] = [
    Step("analyze", "① 扫描素材", "ffprobe 读时长/分辨率,生成素材清单",
         "uv run week06 analyze", [ASSETS_JSON],
         lambda config: (analyze.scan_assets(), "素材清单已生成(output/assets.json)")[1]),
    Step("label", "② AI 打标", "抽帧交给视觉模型写画面描述 + 适合角色(需 LLM 密钥;或手写 note)",
         "uv run week06 label", [ASSETS_JSON],
         lambda config: (label.label_assets(config), "打标完成,看一眼描述,不准的手工改")[1]),
    Step("script", "③ 话术 + 分镜", "LLM 出五段话术再配镜头(无密钥自动走 mock 模板)",
         "uv run week06 script", [SCRIPT_JSON, STORYBOARD_JSON], _run_script),
    Step("voice", "④ 配音", "storyboard 每段口播 → mp3(edge-tts 免费 / API TTS 可插拔)",
         "uv run week06 voice", [VOICE_DIR],
         lambda config: f"配音完成 {voice.synth_all(config)} 段(output/voice/)"),
    Step("render", "⑤ 成片", "切片 → 拼接 → 烧字幕混音,出 1080x1920 竖屏 mp4(需 ffmpeg)",
         "uv run week06 render", [FINAL_MP4],
         lambda config: f"成片完成:{render.render(config)}"),
    Step("jianying", "⑥ 剪映草稿", "导出可编辑草稿(字幕是文本轨),在剪映里精修后手动导出",
         "uv run week06 jianying", [],
         lambda config: f"草稿已生成:{jianying.export_draft(config)}"),
]


def step_by_key(key: str) -> Step:
    match = next((s for s in STEPS if s.key == key), None)
    if match is None:
        raise SystemExit(f"没有这一步: {key}")
    return match


def _mtime(path: Path) -> str:
    ts = max((p.stat().st_mtime for p in ([path] if path.is_file() else path.glob("*"))), default=0)
    return dt.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""


def step_states() -> list[dict[str, str]]:
    """工作台步骤页用:每步的产物状态。"""
    states = []
    for step in STEPS:
        done = [p for p in step.outputs if p.exists() and (p.is_file() or any(p.iterdir()))]
        states.append({
            "key": step.key, "title": step.title, "desc": step.desc, "command": step.command,
            "status": "已有产物" if done else ("—" if not step.outputs else "未生成"),
            "detail": " · ".join(f"{p.relative_to(PROJECT_DIR)}({_mtime(p)})" for p in done),
        })
    return states


def artifacts() -> list[tuple[str, Path]]:
    """总览页「上次产物」:存在的才列。"""
    candidates = [
        ("Demo 流程报告", DEMO_REPORT),
        ("Demo 分镜表", DEMO_DIR / "storyboard.json"),
        ("Demo 字幕轨", DEMO_DIR / "subs.ass"),
        ("素材清单", ASSETS_JSON),
        ("话术", SCRIPT_JSON),
        ("分镜表(中枢)", STORYBOARD_JSON),
        ("配音", VOICE_DIR),
        ("成片", FINAL_MP4),
    ]
    return [(name, path) for name, path in candidates
            if path.exists() and (path.is_file() or any(path.iterdir()))]
