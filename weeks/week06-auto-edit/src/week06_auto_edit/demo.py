"""Demo:零密钥、零 ffmpeg,四步走通流水线的"脑子"。

占位素材(Pillow 现场画,不提交二进制)→ 打标(mock)→ 话术(内置模板)
→ 分镜表(与真实流程同一个规则匹配 + 同一个 validate)→ 字幕 subs.ass。
产物都在 output/demo/,外加一页 output/demo-report.html 流程报告(每步一张卡)。

真实成片(ffmpeg)和配音(edge-tts)是重资产步骤,留给配好环境的人:
uv run week06 voice / render / jianying。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from camp_core import now_iso, write_json
from camp_report import kv_card, save_report, table

from week06_auto_edit import llm
from week06_auto_edit.base import DEMO_DIR, DEMO_REPORT, find_font
from week06_auto_edit.steps import script as script_step

# 5 条占位"素材":文件名 / 假想时长 / 帧上画什么(背景色, 标题)
DEMO_CLIPS = [
    ("demo-01.png", 4.0, ("#8a6f56", "镜头 1 · 产品特写")),
    ("demo-02.png", 3.6, ("#b06f7d", "镜头 2 · 按压取用")),
    ("demo-03.png", 4.2, ("#5c7a8a", "镜头 3 · 护肤流程")),
    ("demo-04.png", 3.8, ("#6f8a5c", "镜头 4 · 上脸按摩")),
    ("demo-05.png", 3.4, ("#8a8a5c", "镜头 5 · 举瓶展示")),
]


def _draw_frame(path: Path, color: str, title: str, font_path: str) -> None:
    """一张 540x960 纯色占位帧:大字标题 + 角标,代替真实素材视频。"""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 540, 960
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    big = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default(size=44)
    small = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default(size=22)
    text = title if font_path else path.stem.upper()  # 没中文字体就退化成文件名
    box = draw.textbbox((0, 0), text, font=big)
    draw.text(((w - box[2]) / 2, (h - box[3]) / 2), text, font=big, fill="#ffffff")
    draw.text((24, h - 56), "week06 demo placeholder", font=small, fill="#ffffffb0")
    img.save(path)


def make_demo_assets() -> list[dict[str, Any]]:
    """① 生成占位素材 + 元数据清单(相当于 analyze 步骤的产物)。"""
    frames_dir = DEMO_DIR / "assets"
    frames_dir.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    assets = []
    for name, duration, (color, title) in DEMO_CLIPS:
        _draw_frame(frames_dir / name, color, title, font_path)
        assets.append({"file": name, "duration": duration, "width": 540, "height": 960,
                       "has_audio": False, "note": "", "roles": []})
    return assets


def label_demo_assets(assets: list[dict[str, Any]]) -> None:
    """② mock 打标:行为与视觉模型一致(往 note/roles 里写),但不联网。"""
    for i, asset in enumerate(assets):
        result = llm.mock_label(i)
        asset["note"] = result["note"]
        asset["roles"] = result["roles"]


def write_ass(board: dict[str, Any], path: Path) -> Path:
    """分镜表 → subs.ass(纯文本字幕轨,*词* 转成 ASS 高亮黄)。"""
    def clock(seconds: float) -> str:
        m, s = divmod(seconds, 60)
        return f"0:{int(m):02d}:{int(s):02d}.{int(round(seconds % 1 * 100)):02d}"

    def styled(caption: str) -> str:
        out, hl = [], False
        for ch in caption:
            if ch == "*":
                hl = not hl
                out.append(r"{\c&H4BE9FF&}" if hl else r"{\c&HFFFFFF&}")
                continue
            out.append(ch)
        return "".join(out)

    lines = [
        "[Script Info]", "Title: week06 demo", "ScriptType: v4.00+",
        "PlayResX: 1080", "PlayResY: 1920", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Outline, Alignment, MarginV",
        "Style: Default,PingFang SC,64,&H00FFFFFF,&H00000000,1,4,2,480", "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    t = 0.0
    for seg in board["segments"]:
        duration = seg["out"] - seg["in"]
        if seg.get("caption"):
            lines.append(f"Dialogue: 0,{clock(t)},{clock(t + duration)},Default,,0,0,0,,{styled(seg['caption'])}")
        t += duration
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _report(config: dict[str, Any], assets: list[dict[str, Any]],
            script: list[dict[str, str]], board: dict[str, Any]) -> Path:
    """每步一张卡(输入 → 输出),流水线长什么样一页看完。"""
    product = config.get("product", {})
    total = sum(s["out"] - s["in"] for s in board["segments"])

    step1 = kv_card("① 素材打标(demo 用 mock 视觉模型)", [
        ("输入", f"{len(assets)} 张占位帧(output/demo/assets/,Pillow 现场生成)"),
        ("输出", "output/demo/assets.json(note 画面描述 + roles 适合角色)"),
        ("真实流程", "uv run week06 analyze + label:ffprobe 读元数据,视觉模型抽帧打标"),
    ]) + table(["素材", "时长", "画面描述", "适合角色"],
               [[a["file"], f"{a['duration']}s", a["note"], ",".join(a["roles"])] for a in assets])

    step2 = kv_card("② 话术生成(demo 用内置模板)", [
        ("输入", f"产品「{product.get('name', '')}」+ 卖点 {len(product.get('selling_points', []))} 条"),
        ("输出", "output/demo/script.json(五段带货结构,hook → pain → feature → proof → cta)"),
        ("真实流程", "uv run week06 script:LLM 按同一套 prompt 生成;--script 可接外部话术"),
    ]) + table(["角色", "口播", "字幕(*高亮*)"],
               [[s["role"], s["voiceover"], s["caption"]] for s in script])

    step3 = kv_card("③ 分镜表(全流程中枢)", [
        ("输入", "话术 × 镜头库(roles 匹配,避免连用同一镜头,时长按口播字数估)"),
        ("输出", f"output/demo/storyboard.json({len(board['segments'])} 段 / {total:.1f} 秒)"),
        ("真实流程", "同一个规则:LLM 出的分镜也要过同一个 validate 守门"),
    ]) + table(["#", "镜头", "截取", "角色", "字幕"],
               [[i, s["asset"], f"{s['in']}-{s['out']}s", s["role"], s["caption"]]
                for i, s in enumerate(board["segments"], 1)])

    step4 = kv_card("④ 字幕轨(文本产物)", [
        ("输入", "storyboard.json 的 caption + 时间线"),
        ("输出", "output/demo/subs.ass(标准 ASS 字幕,任何播放器可加载)"),
        ("真实流程", "成片里字幕由 Pillow 画 PNG + ffmpeg overlay 烧录(不依赖 libass)"),
    ])

    next_steps = kv_card("下一步:重资产出口(demo 不碰)", [
        ("配音", "uv run week06 voice(edge-tts 免费,零 key)"),
        ("成片", "uv run week06 render(需要 ffmpeg → uv run week06 doctor 看安装命令)"),
        ("剪映草稿", "uv run week06 jianying(可编辑文本轨,精修后手动导出)"),
    ])

    body = step1 + step2 + step3 + step4 + next_steps
    return save_report(DEMO_REPORT, "自动剪辑流水线 · Demo 流程报告", body,
                       subtitle=f"零密钥零 ffmpeg · 生成于 {now_iso()}")


def run_demo(config: dict[str, Any]) -> dict[str, Path]:
    """四步 demo 一条龙,CLI 与工作台的「跑一遍 Demo」都走这里。"""
    print("① 生成占位素材(Pillow,不需要 ffmpeg)……")
    assets = make_demo_assets()
    print(f"   {len(assets)} 张 → {DEMO_DIR / 'assets'}")

    print("② mock 打标(不联网,行为与视觉模型一致)……")
    label_demo_assets(assets)
    write_json(DEMO_DIR / "assets.json", {"assets": assets})

    print("③ 内置话术模板 → 规则匹配分镜(与真实流程同一个 validate)……")
    script = llm.mock_script(config.get("product", {}))
    segments = script_step.rule_match(script, assets)
    segments = script_step.validate({"segments": segments}, assets)
    board = script_step.write_outputs(config, script, segments,
                                      script_path=DEMO_DIR / "script.json",
                                      board_path=DEMO_DIR / "storyboard.json")

    print("④ 字幕轨 subs.ass……")
    ass_path = write_ass(board, DEMO_DIR / "subs.ass")
    print(f"OK subs={ass_path}")

    report = _report(config, assets, script, board)
    print(f"OK report={report}")
    print("OK demo 完成:流水线的\"脑子\"全走通了。配音/成片见 uv run week06 voice / render")
    return {"storyboard": DEMO_DIR / "storyboard.json", "subs": ass_path, "report": report}
