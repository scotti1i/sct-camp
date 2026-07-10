"""双雷达打分:同一批条目,按 config.profiles 的每个视角各打一遍分。

源项目的 Scott/学员双视角保留为默认 profiles,但关键词、加权、门槛全部可配:
score = 源 tier + 3×高信号词 + 2×中信号词 − 2×降权词 + bucket 加成 + 高星加成。
打分/难度/筛选只在这个文件,报表与卡片只消费产出,不许再算一遍。
"""

from __future__ import annotations

import re
from typing import Any

from camp_core import now_iso

DIFFICULTY_LADDER = [  # (关键词, 难度标签):从易到难,命中即停
    (["zapier", "n8n", "make.com", "airtable", "notion", "template", "no-code"], "轻配置"),
    (["agent", "mcp", "claude", "codex", "copilot", "api", "github", "framework"], "技术协助"),
]


def has_word(text: str, word: str) -> bool:
    if " " in word or not word.isascii():
        return word in text
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text) is not None


def hits(text: str, words: list[str]) -> list[str]:
    return [word for word in words if has_word(text, str(word).lower())]


def item_text(item: dict[str, Any]) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')} {item.get('source', '')}".lower()


def difficulty_for(text: str) -> str:
    for words, label in DIFFICULTY_LADDER:
        if any(has_word(text, w) for w in words):
            return label
    return "仅观察"


def score_item(item: dict[str, Any], profile: dict[str, Any]) -> tuple[int, list[str]]:
    """一个视角给一条内容打分,返回 (分数, 理由)。"""
    text = item_text(item)
    high = hits(text, profile.get("high", []))
    medium = hits(text, profile.get("medium", []))
    negative = hits(text, profile.get("negative", []))
    score = int(item.get("tier") or 1) + 3 * len(high) + 2 * len(medium) - 2 * len(negative)
    score += int(profile.get("bucket_boosts", {}).get(str(item.get("bucket") or ""), 0))
    stars = int(item.get("stars") or 0)
    if stars:
        score += min(stars // 2000, 3)
    reasons = []
    if high:
        reasons.append("强信号: " + ", ".join(high[:4]))
    if medium:
        reasons.append("相关: " + ", ".join(medium[:3]))
    if stars:
        reasons.append(f"GitHub {stars:,} stars")
    if negative:
        reasons.append("降权: " + ", ".join(negative[:3]))
    return score, reasons or ["仅来源优先级"]


def _select(scored: list[dict[str, Any]], profile: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    """过门槛 → 按分排序 → 单源限量 → 截断。"""
    min_score = int(profile.get("min_score") or 5)
    max_items = int(config.get("max_items_per_profile") or 8)
    max_per_source = int(config.get("max_per_source") or 3)
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for row in sorted(scored, key=lambda r: r["score"], reverse=True):
        if row["score"] < min_score or counts.get(row["source"], 0) >= max_per_source:
            continue
        selected.append(row)
        counts[row["source"]] = counts.get(row["source"], 0) + 1
        if len(selected) >= max_items:
            break
    return selected


def rank_items(items: list[dict[str, Any]], config: dict[str, Any],
               source_label: str, errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """双雷达入口:所有下游(日报/工作台/卡片)只吃这份产出。"""
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("id") or item.get("link") or item.get("title"))
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    profiles_out: dict[str, Any] = {}
    for name, profile in config.get("profiles", {}).items():
        scored = []
        for item in unique:
            score, reasons = score_item(item, profile)
            scored.append({**item, "score": score, "reasons": reasons,
                           "difficulty": difficulty_for(item_text(item))})
        profiles_out[name] = {
            "label": str(profile.get("label") or name),
            "note": str(profile.get("note") or ""),
            "items": _select(scored, profile, config),
        }
    return {
        "generated_at": now_iso(),
        "source": source_label,
        "item_count": len(unique),
        "errors": errors or [],
        "profiles": profiles_out,
    }
