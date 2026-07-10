"""路径与字体:week06 全模块共用的少量常量,不放业务逻辑。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_DIR / "input"
ASSETS_DIR = INPUT_DIR / "assets"
OUTPUT_DIR = PROJECT_DIR / "output"
DEMO_DIR = OUTPUT_DIR / "demo"

ASSETS_JSON = OUTPUT_DIR / "assets.json"
SCRIPT_JSON = OUTPUT_DIR / "script.json"
STORYBOARD_JSON = OUTPUT_DIR / "storyboard.json"
VOICE_DIR = OUTPUT_DIR / "voice"
FINAL_MP4 = OUTPUT_DIR / "final.mp4"
DEMO_REPORT = OUTPUT_DIR / "demo-report.html"

# 成片规格(改这里 = 改视频规格)
W, H, FPS = 1080, 1920, 30

# 字幕/占位帧的中文字体候选:macOS → Linux → Windows,一个能中文的就行
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]


def find_font(config: dict[str, Any] | None = None) -> str:
    """config 的 font_paths 优先,系统候选兜底;找不到返回空串。"""
    extra = list((config or {}).get("font_paths") or [])
    for candidate in [*extra, *FONT_CANDIDATES]:
        if candidate and Path(candidate).exists():
            return candidate
    return ""
