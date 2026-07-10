"""打分与规则:竞品视频快照 → 优先级排序 + 建议动作(移植自源项目 tm_core)。

输入是快照列表(同一 video_id 可能出现在多轮 pulled_at 里,用来算播放涨幅),
输出 analysis dict。只做纯计算,不碰网络不碰磁盘 —— demo 和真实数据走同一条路。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from camp_core import now_iso

WINDOW_DAYS = {"1d": 1, "7d": 7, "30d": 30}


def to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------- 快照轮次 ----------

def latest_round(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """取最近一轮 pulled_at 的快照,按播放量降序。"""
    if not snapshots:
        return []
    latest = max(str(row.get("pulled_at") or "") for row in snapshots)
    rows = [dict(row) for row in snapshots if str(row.get("pulled_at") or "") == latest]
    rows.sort(key=lambda row: to_int(row.get("view_count")), reverse=True)
    return rows


def previous_counts(snapshots: list[dict[str, Any]], video_id: str, pulled_at: str) -> dict[str, Any] | None:
    """同一视频在更早轮次的快照(最近的那一次),没有则视为新视频。"""
    earlier = [
        row for row in snapshots
        if str(row.get("video_id")) == video_id and str(row.get("pulled_at") or "") < pulled_at
    ]
    if not earlier:
        return None
    return max(earlier, key=lambda row: str(row.get("pulled_at") or ""))


# ---------- 单条视频的判断 ----------

def engagement_rate(row: dict[str, Any]) -> float:
    views = max(to_int(row.get("view_count")), 1)
    total = to_int(row.get("like_count")) + to_int(row.get("comment_count")) + to_int(row.get("share_count"))
    return round(total / views, 4)


def guess_format(row: dict[str, Any]) -> str:
    text = f"{row.get('title', '')} {row.get('description', '')}".lower()
    if any(word in text for word in ["how to", "tips", "guide", "tutorial"]):
        return "教学/方法型"
    if any(word in text for word in ["new", "launch", "drop", "out now"]):
        return "新品/发布型"
    if any(word in text for word in ["sale", "deal", "discount", "free"]):
        return "促销/转化型"
    if "#" in text:
        return "标签/热点型"
    return "品牌/故事型"


def suggested_action(row: dict[str, Any], engagement: float, delta: int | None) -> str:
    if delta and delta > 5000:
        return "优先拆开头 3 秒和封面,判断为什么涨得快"
    if engagement >= 0.06:
        return "拆评论触发点,改成自己的产品痛点表达"
    if to_int(row.get("view_count")) >= 10000:
        return "加入下周选题池,复刻结构但换产品和场景"
    return "保留观察,先不要直接模仿"


def priority_score(row: dict[str, Any], engagement: float, delta: int | None, rules: dict[str, Any]) -> int:
    score = 2 if delta is None else 0
    if to_int(row.get("view_count")) >= int(rules.get("min_views_for_priority", 10000)):
        score += 3
    if engagement >= float(rules.get("min_engagement_for_priority", 0.04)):
        score += 3
    if delta and delta > 0:
        score += min(3, max(1, delta // 1000))
    if to_int(row.get("comment_count")) >= int(rules.get("comment_signal_threshold", 20)):
        score += 1
    return score


def publish_deadline(config: dict[str, Any]) -> str:
    deadline = config.get("deadline", {})
    fixed = str(deadline.get("campaign_publish_by") or "").strip()
    if fixed:
        return fixed
    days = int(deadline.get("action_due_days") or 7)
    return (datetime.now().date() + timedelta(days=days)).isoformat()


def copy_text(row: dict[str, Any]) -> str:
    """一键复制的选题卡文案(看板/飞书里直接粘走)。"""
    return "\n".join([
        f"账号:@{row.get('handle', '')}",
        f"标题:{row.get('title', '')}",
        f"链接:{row.get('webpage_url', '')}",
        f"数据:播放 {row.get('view_count', 0)} / 点赞 {row.get('like_count', 0)}"
        f" / 评论 {row.get('comment_count', 0)} / 转发 {row.get('share_count', 0)}",
        f"建议动作:{row.get('suggested_action', '')}",
    ])


def passes_rules(row: dict[str, Any], rules: dict[str, Any]) -> bool:
    if to_int(row.get("view_count")) < int(rules.get("min_views", 0)):
        return False
    if float(row.get("engagement_rate") or 0) < float(rules.get("min_engagement_rate", 0)):
        return False
    if to_int(row.get("priority_score")) < int(rules.get("min_priority_score", 0)):
        return False
    if rules.get("only_new") and not row.get("is_new"):
        return False
    published = parse_dt(str(row.get("published_at") or ""))
    window_days = WINDOW_DAYS.get(str(rules.get("time_window") or ""))
    if published and window_days:
        if published < datetime.now(timezone.utc) - timedelta(days=window_days):
            return False
    return True


def enrich(row: dict[str, Any], snapshots: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    previous = previous_counts(snapshots, str(row.get("video_id")), str(row.get("pulled_at") or ""))
    delta = to_int(row.get("view_count")) - to_int(previous.get("view_count")) if previous else None
    engagement = engagement_rate(row)
    item = dict(row)
    item.update({
        "is_new": previous is None,
        "view_delta": delta,
        "engagement_rate": engagement,
        "priority_score": priority_score(row, engagement, delta, config.get("rules", {})),
        "format_guess": guess_format(row),
        "suggested_action": suggested_action(row, engagement, delta),
        "publish_deadline": publish_deadline(config),
    })
    item["copy_text"] = copy_text(item)
    return item


# ---------- 聚合 ----------

def group_videos(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("handle") or ""), []).append(row)
    return [{"handle": handle, "videos": videos, "count": len(videos)} for handle, videos in groups.items()]


def build_analysis(snapshots: list[dict[str, Any]], config: dict[str, Any], source_label: str = "") -> dict[str, Any]:
    """唯一数据源:report / serve / sync 都只消费这份结果,不许各自再算一遍。"""
    rules = config.get("rules", {})
    rows = [enrich(row, snapshots, config) for row in latest_round(snapshots)]
    rows.sort(key=lambda row: (row["priority_score"], to_int(row.get("view_count"))), reverse=True)
    filtered = [row for row in rows if passes_rules(row, rules)]
    actions = filtered[: int(rules.get("max_action_items", 5))]
    return {
        "generated_at": now_iso(),
        "source": source_label,
        "account_count": len({str(row.get("handle")) for row in rows}),
        "video_count": len(rows),
        "matched_count": len(filtered),
        "videos": rows,
        "actions": actions,
        "groups": group_videos(rows),
        "rules": rules,
    }
