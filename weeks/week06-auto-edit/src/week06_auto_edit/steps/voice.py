"""④ 配音层(可插拔):storyboard 每段 voiceover → output/voice/seg-XX.mp3。

provider 在 config.json 的 voice 段选:
  edge  免费,不要 key(edge-tts,已随 uv sync 装好)
  api   任何 OpenAI 兼容 TTS(/v1/audio/speech);密钥走 .env 的 TTS_API_KEY / TTS_BASE_URL

想加新 TTS:照着 PROVIDERS 加一个函数 + config.voice 加一段,不要动调用方。
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from camp_core import read_json, secret

from week06_auto_edit.base import STORYBOARD_JSON, VOICE_DIR


def synth_edge(text: str, out_path: Path, conf: dict[str, Any]) -> None:
    import asyncio

    try:
        import edge_tts
    except ImportError:
        raise SystemExit("缺 edge-tts:在仓库根运行 uv sync") from None
    voice = conf.get("voice", "zh-CN-XiaoxiaoNeural")
    asyncio.run(edge_tts.Communicate(text, voice, rate=conf.get("rate", "+12%")).save(str(out_path)))


def synth_api(text: str, out_path: Path, conf: dict[str, Any]) -> None:
    """OpenAI /v1/audio/speech 兼容接口(中转站/ElevenLabs 网关等)。"""
    key = secret("TTS_API_KEY")
    base = secret("TTS_BASE_URL")
    if not key or not base:
        raise SystemExit("voice.provider=api 需要密钥:在仓库根 .env 填 TTS_API_KEY / TTS_BASE_URL")
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/audio/speech",
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        data=json.dumps({
            "model": conf.get("model", "tts-1"),
            "voice": conf.get("voice", "alloy"),
            "input": text,
        }).encode(),
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        audio = resp.read()
    if len(audio) < 1000:
        raise RuntimeError(f"返回音频过小({len(audio)}B),检查 model/voice 配置")
    out_path.write_bytes(audio)


PROVIDERS = {"edge": synth_edge, "api": synth_api}


def synth_all(config: dict[str, Any], voice_override: str = "") -> int:
    """给分镜表每段合成配音,返回合成条数。"""
    board = read_json(STORYBOARD_JSON)
    if not board:
        raise SystemExit(f"缺少 {STORYBOARD_JSON}:先跑 uv run week06 script(或 demo 看流程)")

    vconf = config.get("voice", {})
    provider = vconf.get("provider", "edge")
    if provider not in PROVIDERS:
        raise SystemExit(f"未知 voice.provider: {provider}(可选: {', '.join(PROVIDERS)})")
    conf = dict(vconf.get(provider, {}))
    if voice_override:
        conf["voice"] = voice_override

    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    made = 0
    for i, seg in enumerate(board["segments"], 1):
        text = (seg.get("voiceover") or "").strip()
        out = VOICE_DIR / f"seg-{i:02d}.mp3"
        if not text:
            out.unlink(missing_ok=True)
            continue
        PROVIDERS[provider](text, out, conf)
        made += 1
        print(f"  seg-{i:02d} 「{text}」")

    print(f"OK voice={VOICE_DIR}(共 {made} 段,provider: {provider})")
    print("下一步:uv run week06 render(自动混入配音)")
    return made
