"""⑥ 出口②:storyboard.json 导出为剪映草稿(在剪映里精修后手动导出)。

兼容性口径(重要):
- 只用「生成草稿」能力,剪映专业版 5 及以上都能打开
- 不用模板模式/自动导出(那些才有版本限制)
- 草稿里素材是绝对路径:生成草稿和打开剪映必须是同一台电脑,项目目录别移动
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from camp_core import read_json

from week06_auto_edit.base import ASSETS_DIR, STORYBOARD_JSON


def detect_draft_root() -> str | None:
    """按平台猜剪映草稿目录;猜不到就让用户在 config.json 里填。"""
    home = os.path.expanduser("~")
    candidates = (
        [os.path.join(os.environ.get("LOCALAPPDATA", ""),
                      "JianyingPro", "User Data", "Projects", "com.lveditor.draft")]
        if platform.system() == "Windows"
        else [
            os.path.join(home, "Movies", "JianyingPro", "User Data", "Projects", "com.lveditor.draft"),
            os.path.join(home, "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft"),
        ]
    )
    return next((c for c in candidates if os.path.isdir(c)), None)


def export_draft(config: dict[str, Any]) -> Path:
    """storyboard.json → 剪映草稿(视频轨 + 可编辑文本轨,字幕不烧录)。"""
    try:
        import pyJianYingDraft as draft
        from pyJianYingDraft import trange
    except ImportError:
        raise SystemExit(
            "缺 pyJianYingDraft(可选依赖,只有剪映出口需要):\n"
            "  uv pip install pyjianyingdraft\n装完重跑本命令。"
        ) from None

    board = read_json(STORYBOARD_JSON)
    if not board:
        raise SystemExit(f"缺少 {STORYBOARD_JSON}:先跑 uv run week06 script")
    segments = board["segments"]

    jy = config.get("jianying", {})
    root = jy.get("draft_root") or detect_draft_root()
    if not root or not os.path.isdir(root):
        raise SystemExit(
            "找不到剪映草稿目录。打开剪映 → 全局设置 → 草稿位置,把路径填进 config.json 的 jianying.draft_root\n"
            "常见位置 Win: C:\\Users\\你\\AppData\\Local\\JianyingPro\\User Data\\Projects\\com.lveditor.draft\n"
            "常见位置 Mac: ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
        )

    name = jy.get("draft_name", "week6-auto-cut")
    folder = draft.DraftFolder(root)
    script = folder.create_draft(name, 1080, 1920, fps=30, allow_replace=True)
    script.add_track(draft.TrackType.video)
    script.add_track(draft.TrackType.text)

    clock = 0.0
    for seg in segments:
        duration = seg["out"] - seg["in"]
        asset = str((ASSETS_DIR / seg["asset"]).resolve())
        script.add_segment(draft.VideoSegment(
            asset,
            trange(f"{clock}s", f"{duration}s"),
            source_timerange=trange(f"{seg['in']}s", f"{duration}s"),
            volume=0.0,
        ))
        if seg.get("caption"):
            is_hook = seg.get("role") == "hook"
            script.add_segment(draft.TextSegment(
                seg["caption"],
                trange(f"{clock}s", f"{duration}s"),
                style=draft.TextStyle(size=13.0 if is_hook else 9.0, bold=True, align=1),
                clip_settings=draft.ClipSettings(transform_y=0.55 if is_hook else -0.62),
                border=draft.TextBorder(width=25.0),
            ))
        clock += duration

    script.save()
    draft_path = Path(root) / name
    print(f"OK draft={draft_path}")
    print("打开剪映 → 草稿列表里找到它 → 加 BGM/转场/贴纸精修 → 手动导出")
    print("(素材是绝对路径,别移动项目文件夹,否则草稿里素材会丢)")
    return draft_path
