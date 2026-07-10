"""① 扫描素材:ffprobe 读时长/分辨率 → output/assets.json。

note(画面描述)决定 AI 选段质量:
- 首次运行生成骨架,note 为空;input/asset-notes.json 里的种子描述会自动带入
- 你在 output/assets.json 里写过的 note 重扫不会被覆盖
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from camp_core import read_json, run_cmd, write_json
from camp_core.proc import command_exists

from week06_auto_edit.base import ASSETS_DIR, ASSETS_JSON, INPUT_DIR

VIDEO_EXTS = (".mp4", ".mov")


def probe(path: Path) -> dict[str, Any]:
    """ffprobe 读一条素材的技术元数据。"""
    code, out = run_cmd([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    if code != 0:
        raise SystemExit(f"ffprobe 读取失败:{path.name}\n{out[-400:]}")
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "duration": round(float(data.get("format", {}).get("duration", 0)), 2),
        "width": video.get("width"),
        "height": video.get("height"),
        "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
    }


def _old_notes() -> dict[str, str]:
    """note 优先级:output/assets.json 里写过的 > input/asset-notes.json 种子。"""
    notes: dict[str, str] = dict(read_json(INPUT_DIR / "asset-notes.json", {}))
    for asset in read_json(ASSETS_JSON, {"assets": []}).get("assets", []):
        if asset.get("note"):
            notes[asset["file"]] = asset["note"]
    return notes


def scan_assets() -> list[dict[str, Any]]:
    """扫描 input/assets/,写 output/assets.json,返回素材清单。"""
    if not command_exists("ffprobe"):
        raise SystemExit("缺 ffprobe(随 ffmpeg 安装):先跑 uv run week06 doctor 看安装命令")
    if not ASSETS_DIR.is_dir() or not any(ASSETS_DIR.iterdir()):
        raise SystemExit(f"{ASSETS_DIR} 里没有素材:放 5-8 段产品片段(.mp4/.mov)再来")

    notes = _old_notes()
    assets = []
    for path in sorted(ASSETS_DIR.iterdir()):
        if path.suffix.lower() not in VIDEO_EXTS:
            continue
        info = probe(path)
        info["file"] = path.name
        info["note"] = notes.get(path.name, "")
        assets.append(info)
        mark = f"「{info['note']}」" if info["note"] else "待写描述"
        print(f"  {path.name}  {info['duration']}s  {info['width']}x{info['height']}  {mark}")

    write_json(ASSETS_JSON, {"assets": assets})
    todo = sum(1 for a in assets if not a["note"])
    print(f"OK assets={ASSETS_JSON}(共 {len(assets)} 条,{todo} 条待描述)")
    if todo:
        print("下一步:uv run week06 label 自动打标;或打开 output/assets.json 手写 note(写画面里是什么)")
    return assets
