"""yt-dlp 采集:竞品账号 → 最新公开视频元数据快照(移植自源项目 tm_core.scan)。

只拿元数据(--skip-download),不下载视频。TikTok 偶发 503 / 超时是外部源的脾气,
不是项目坏了:每个账号自动重试 3 次,还不行就把友好解释写进 errors,继续跑下一个。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from camp_core import now_iso, run_cmd

from week04_competitor_watch.core import to_int

FRIENDLY_HINT = "TikTok 对公开元数据接口偶发 503/超时,不是你的环境坏了;稍后重跑 uv run week04 fetch,或减少账号数"

_TSV_KEYS = [
    "id", "uploader", "title", "timestamp", "view_count", "like_count",
    "comment_count", "repost_count", "save_count", "duration", "webpage_url", "thumbnail",
]
_PRINT_FIELDS = "\t".join(f"%({key})s" for key in _TSV_KEYS)


def clean_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ")
    return " ".join(text.split())[:limit]


def clean_handle(value: str) -> str:
    value = value.strip().replace("@", "")
    value = value.replace("https://www.tiktok.com/", "").strip("/")
    return value.split("/")[0]


def parse_tsv_lines(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == len(_TSV_KEYS) and parts[0].isdigit():
            rows.append(dict(zip(_TSV_KEYS, parts)))
    return rows


def run_yt_dlp_once(handle: str, limit: int) -> tuple[list[dict[str, str]], str]:
    cmd = [
        "yt-dlp", "--no-update", "--skip-download", "--ignore-errors",
        "--playlist-end", str(limit), "--print", _PRINT_FIELDS,
        f"https://www.tiktok.com/@{handle}",
    ]
    try:
        code, output = run_cmd(cmd, timeout=140)
    except Exception as exc:  # 超时等,统一按外部源失败处理
        return [], str(exc)
    return parse_tsv_lines(output), "" if code == 0 else output[-800:]


def run_yt_dlp(handle: str, limit: int) -> tuple[list[dict[str, str]], str]:
    """重试 3 次;拿到数据立刻返回,否则带回最后一次错误尾巴。"""
    last_error = ""
    for attempt in range(3):
        rows, error = run_yt_dlp_once(handle, limit)
        if rows:
            return rows, ""
        last_error = error
        time.sleep(1 + attempt)
    return [], last_error


def normalize_video(raw: dict[str, str], source: dict[str, Any], pulled_at: str) -> dict[str, Any]:
    ts = to_int(raw.get("timestamp"))
    published = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
    title = clean_text(raw.get("title"), 160)
    video_id = str(raw.get("id") or "")
    handle = clean_handle(str(source.get("handle") or ""))
    return {
        "video_id": video_id,
        "handle": handle,
        "title": title,
        "description": title,
        "webpage_url": f"https://www.tiktok.com/@{handle}/video/{video_id}",
        "published_at": published,
        "view_count": to_int(raw.get("view_count")),
        "like_count": to_int(raw.get("like_count")),
        "comment_count": to_int(raw.get("comment_count")),
        "share_count": to_int(raw.get("repost_count")),
        "save_count": to_int(raw.get("save_count")),
        "duration": to_int(raw.get("duration")),
        "niche": clean_text(source.get("niche"), 80),
        "why_watch": clean_text(source.get("why_watch"), 160),
        "pulled_at": pulled_at,
        "thumbnail_url": clean_text(raw.get("thumbnail"), 600),
    }


def fetch_all(sources: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """逐账号采集,返回 (本轮快照, 失败清单)。单账号失败不拖垮整轮。"""
    pulled_at = now_iso()
    limit = int(config.get("max_videos_per_account") or 3)
    sleep_seconds = float(config.get("fetch", {}).get("sleep_seconds_between_accounts", 2))
    videos: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for source in sources:
        handle = clean_handle(str(source.get("handle") or ""))
        if not handle:
            continue
        raw_rows, error = run_yt_dlp(handle, limit)
        videos.extend(normalize_video(raw, source, pulled_at) for raw in raw_rows if raw.get("id"))
        if error:
            errors.append({"handle": handle, "hint": FRIENDLY_HINT, "detail": error})
        print(f"{'OK ' if raw_rows else 'FAIL'} @{handle}: {len(raw_rows)} 条视频")
        time.sleep(sleep_seconds)
    return videos, errors
