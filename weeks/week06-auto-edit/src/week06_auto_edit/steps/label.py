"""② AI 打标:每条素材抽 2 帧交给视觉模型,自动写 note(画面描述)+ roles(适合角色)。

没配 LLM 密钥也不拦路:跳过这步,手写 output/assets.json 的 note 一样能走完流水线。
你手工改过的 note 不会被覆盖(--force 才会)。
"""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from camp_core import read_json, write_json

from week06_auto_edit import llm
from week06_auto_edit.base import ASSETS_DIR, ASSETS_JSON

PROMPT = """你在给短视频剪辑素材打标。这是同一段视频里抽出的 2 帧画面。
只输出 JSON,不要解释:
{"note": "一句话画面描述,15-30字,写清主体/动作/背景", "roles": ["适合的角色,从 hook/pain/feature/proof/cta 里选1-3个"]}"""


def grab_frames(video: Path, duration: float) -> list[str]:
    """抽 25% 和 75% 两个时间点的帧,返回 base64 jpg 列表。"""
    frames = []
    for pct in (0.25, 0.75):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as tmp:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", str(duration * pct),
                 "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-2", tmp.name],
                check=True, capture_output=True,
            )
            frames.append(base64.b64encode(Path(tmp.name).read_bytes()).decode())
    return frames


def _label_one(config: dict[str, Any], video: Path, duration: float) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    for b64 in grab_frames(video, duration):
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return llm.chat_json(config, PROMPT, content, vision=True, temperature=0.2)


def label_assets(config: dict[str, Any], force: bool = False) -> list[dict[str, Any]]:
    """给 output/assets.json 里没有 note 的素材打标,返回更新后的清单。"""
    data = read_json(ASSETS_JSON)
    if not data:
        raise SystemExit(f"缺少 {ASSETS_JSON}:先跑 uv run week06 analyze")
    if not llm.have_llm():
        raise SystemExit(
            "自动打标需要视觉模型:在仓库根 .env 填 LLM_API_KEY / LLM_BASE_URL。\n"
            "不配也行:打开 output/assets.json,给每条 note 手写一句画面描述。"
        )

    todo = [a for a in data["assets"] if force or not a.get("note")]
    if not todo:
        print("所有素材都已有描述(要覆盖重打加 --force)")
        return data["assets"]

    print(f"开始打标 {len(todo)} 条(视觉模型)……")
    for asset in todo:
        try:
            result = _label_one(config, ASSETS_DIR / asset["file"], asset["duration"])
            asset["note"] = str(result.get("note", "")).strip()
            asset["roles"] = result.get("roles", [])
            print(f"  OK {asset['file']}「{asset['note']}」适合: {','.join(asset['roles'])}")
        except Exception as err:
            print(f"  FAIL {asset['file']} 打标失败: {err}")

    write_json(ASSETS_JSON, data)
    print(f"OK assets={ASSETS_JSON} 已更新。看一眼描述,不准的手工改。下一步:uv run week06 script")
    return data["assets"]
