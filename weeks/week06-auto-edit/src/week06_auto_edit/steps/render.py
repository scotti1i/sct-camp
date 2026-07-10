"""⑤ 出口①:storyboard.json 渲染成片(1080x1920 竖屏 + 字幕 + 配音 + 可选 BGM)。

字幕方案(硬性约定,别改):Pillow 把每条字幕画成透明 PNG,ffmpeg overlay 按时间叠上去。
不依赖 ffmpeg 是否编译了 libass/drawtext——学员机上最稳的一条路,实测踩过坑。

三步,每步产物都能打开检查:
1. 每个分镜段落 → 统一规格的中间片段(output/segments/)
2. 片段拼接 → output/rough.mp4(无字幕粗剪)
3. 叠字幕 + 混配音 BGM → output/final.mp4
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from camp_core import read_json
from camp_core.proc import command_exists

from week06_auto_edit.base import (
    FINAL_MP4, FPS, H, OUTPUT_DIR, PROJECT_DIR, STORYBOARD_JSON, VOICE_DIR, W, find_font,
)

HIGHLIGHT = (255, 233, 75, 255)  # 关键词高亮黄


def _run(cmd: list[str]) -> None:
    """跑一条 ffmpeg;统一 cwd=项目根 + 相对路径(双平台约定)。"""
    result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("ffmpeg 命令失败:\n " + " ".join(cmd) + "\n" + result.stderr[-1200:])


def parse_marks(text: str) -> list[tuple[str, bool]]:
    """把 "*秒吸收*" 的星号标记解析成 [(字, 是否高亮)] 列表。"""
    chars, highlight = [], False
    for ch in text:
        if ch == "*":
            highlight = not highlight
            continue
        chars.append((ch, highlight))
    return chars


def draw_caption(text: str, role: str, out_path: Path, font_path: str) -> None:
    """一条字幕 → 一张 1080x1920 透明 PNG。hook 上部大字,其余下三分之一;*词* 画高亮黄。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = 84 if role == "hook" else 64
    font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)

    # 按像素宽度贪心断行(基于去掉标记的字符流)
    lines: list[list[tuple[str, bool]]] = []
    line: list[tuple[str, bool]] = []
    for ch, hl in parse_marks(text):
        if draw.textlength("".join(c for c, _ in line) + ch, font=font) > W - 140:
            lines.append(line)
            line = [(ch, hl)]
        else:
            line.append((ch, hl))
    lines.append(line)

    line_h = size + 18
    y = 340 if role == "hook" else H - 480 - line_h * len(lines)
    for ln in lines:
        plain = "".join(c for c, _ in ln)
        x = (W - draw.textlength(plain, font=font)) / 2
        for ch, hl in ln:
            draw.text((x, y), ch, font=font,
                      fill=HIGHLIGHT if hl else (255, 255, 255, 255),
                      stroke_width=8, stroke_fill=(0, 0, 0, 220))
            x += draw.textlength(ch, font=font)
        y += line_h
    img.save(out_path)


def _cut_segments(segments: list[dict[str, Any]]) -> None:
    """1/3 每个分镜 → 统一规格中间片段(裁 9:16,去原声)+ 拼接清单。"""
    (OUTPUT_DIR / "segments").mkdir(parents=True, exist_ok=True)
    concat_lines = []
    for i, seg in enumerate(segments, 1):
        out = f"output/segments/seg-{i:02d}.mp4"
        _run([
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(seg["in"]), "-to", str(seg["out"]),
            "-i", f"input/assets/{seg['asset']}",
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            out,
        ])
        concat_lines.append(f"file 'segments/seg-{i:02d}.mp4'")
        print(f"   seg-{i:02d} ← {seg['asset']} [{seg['in']}-{seg['out']}s]")
    (OUTPUT_DIR / "concat.txt").write_text("\n".join(concat_lines), encoding="utf-8")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", "output/concat.txt", "-c", "copy", "output/rough.mp4"])


def _compose_final(segments: list[dict[str, Any]], config: dict[str, Any], font_path: str) -> int:
    """3/3 rough.mp4 + 字幕 PNG overlay + 配音 adelay + BGM,混成 final.mp4;返回配音段数。"""
    (OUTPUT_DIR / "captions").mkdir(parents=True, exist_ok=True)
    inputs = ["-i", "output/rough.mp4"]
    input_idx = 0
    overlays: list[str] = []
    voice_jobs: list[tuple[int, int]] = []  # (输入序号, 延迟毫秒)
    clock, n = 0.0, 0
    for i, seg in enumerate(segments, 1):
        duration = seg["out"] - seg["in"]
        if seg.get("caption"):
            png = f"output/captions/cap-{i:02d}.png"
            draw_caption(seg["caption"], seg.get("role", ""), PROJECT_DIR / png, font_path)
            inputs += ["-i", png]
            input_idx += 1
            n += 1
            src = "[0:v]" if n == 1 else f"[v{n - 1}]"
            overlays.append(
                f"{src}[{input_idx}:v]overlay=0:0:enable='between(t,{clock:.2f},{clock + duration:.2f})'[v{n}]"
            )
        voice = VOICE_DIR / f"seg-{i:02d}.mp3"
        if seg.get("voiceover") and voice.exists():
            inputs += ["-i", f"output/voice/seg-{i:02d}.mp3"]
            input_idx += 1
            voice_jobs.append((input_idx, int(clock * 1000)))
        clock += duration

    bgm = str(config.get("bgm") or "")
    has_bgm = bool(bgm) and (PROJECT_DIR / bgm).exists()
    if has_bgm:
        inputs += ["-stream_loop", "-1", "-i", bgm]
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    input_idx += 1

    # 音频图:BGM(有配音时压低)+ 每段配音按时间线偏移,混成一轨
    bgm_vol = (0.16 if voice_jobs else 0.7) if has_bgm else 1.0
    audio_chains = [f"[{input_idx}:a]volume={bgm_vol}[bgm]"]
    mix_srcs = "[bgm]"
    for k, (idx, delay_ms) in enumerate(voice_jobs, 1):
        audio_chains.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[vo{k}]")
        mix_srcs += f"[vo{k}]"
    audio_chains.append(f"{mix_srcs}amix=inputs={len(voice_jobs) + 1}:normalize=0[aout]")

    cmd = ["ffmpeg", "-y", "-v", "error", *inputs,
           "-filter_complex", ";".join(overlays + audio_chains),
           "-map", f"[v{n}]" if overlays else "0:v", "-map", "[aout]", "-shortest",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "output/final.mp4"]
    _run(cmd)
    return len(voice_jobs)


def render(config: dict[str, Any]) -> Path:
    """storyboard.json → output/final.mp4。"""
    if not command_exists("ffmpeg"):
        raise SystemExit("缺 ffmpeg:先跑 uv run week06 doctor 看安装命令(demo 不需要它)")
    board = read_json(STORYBOARD_JSON)
    if not board:
        raise SystemExit(f"缺少 {STORYBOARD_JSON}:先跑 uv run week06 script(或 demo 看流程)")
    segments = board["segments"]
    font_path = find_font(config)

    print("1/3 切分镜片段……")
    _cut_segments(segments)
    print("2/3 拼接粗剪 → output/rough.mp4")
    print("3/3 叠字幕 + 配音配乐 → output/final.mp4")
    voiced = _compose_final(segments, config, font_path)

    total = sum(s["out"] - s["in"] for s in segments)
    print(f"OK final={FINAL_MP4}({total:.1f} 秒,{len(segments)} 段,配音 {voiced} 段)")
    if not voiced:
        print("提示:还没配音。uv run week06 voice 一步生成,再重跑 render")
    print("不满意:改 output/storyboard.json 后重跑;想精修:uv run week06 jianying")
    return FINAL_MP4
