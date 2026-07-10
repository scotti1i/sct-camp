"""日报渲染:analysis dict → camp-report 一页 HTML(概览 + 优先级表 + 视频清单)。

serve 看板复用这里的片段函数(overview_card / actions_table / videos_table),
保证网页和日报长一个样。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from camp_report import kv_card, save_report, table

from week04_competitor_watch.core import to_int


def _fmt_delta(row: dict[str, Any]) -> str:
    delta = row.get("view_delta")
    if delta is None:
        return "首次入库"
    return f"+{delta:,}" if delta >= 0 else f"{delta:,}"


def overview_card(analysis: dict[str, Any]) -> str:
    return kv_card("本轮概览", [
        ("生成时间", analysis.get("generated_at", "")),
        ("数据来源", analysis.get("source", "")),
        ("账号数", analysis.get("account_count", 0)),
        ("视频数", analysis.get("video_count", 0)),
        ("命中规则", analysis.get("matched_count", 0)),
    ])


def actions_table(analysis: dict[str, Any]) -> str:
    rows = []
    for idx, row in enumerate(analysis.get("actions", []), 1):
        rows.append([
            idx, f"@{row.get('handle', '')}", row.get("title", ""),
            f"{to_int(row.get('view_count')):,}", _fmt_delta(row),
            f"{float(row.get('engagement_rate') or 0):.2%}", row.get("priority_score", 0),
            row.get("format_guess", ""), row.get("suggested_action", ""),
            row.get("publish_deadline", ""),
        ])
    if not rows:
        return "<p>本轮没有命中规则的视频:放宽 config.json 的 rules,或先跑 uv run week04 fetch 换一批数据。</p>"
    return table(["#", "账号", "标题", "播放", "涨幅", "互动率", "优先级", "类型判断", "建议动作", "发布期限"], rows)


def videos_table(videos: list[dict[str, Any]]) -> str:
    rows = []
    for row in videos:
        rows.append([
            f"@{row.get('handle', '')}", row.get("title", ""),
            str(row.get("published_at", ""))[:10], f"{to_int(row.get('view_count')):,}",
            to_int(row.get("like_count")), to_int(row.get("comment_count")),
            to_int(row.get("share_count")), to_int(row.get("save_count")),
            f"{to_int(row.get('duration'))}s", row.get("webpage_url", ""),
        ])
    return table(["账号", "标题", "发布", "播放", "点赞", "评论", "转发", "收藏", "时长", "链接"], rows)


def write_report(analysis: dict[str, Any], path: Path) -> Path:
    body = (
        overview_card(analysis)
        + "<h2>优先拆解(按优先级排序)</h2>" + actions_table(analysis)
        + "<h2>本轮视频清单</h2>" + videos_table(analysis.get("videos", []))
    )
    return save_report(path, "TikTok 竞品视频监控日报", body, subtitle=str(analysis.get("source", "")))
