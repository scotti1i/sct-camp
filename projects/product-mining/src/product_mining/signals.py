"""需求信号提取:用户表达(原话)→ 痛点簇 → 机会点排序。

规则是确定性的词典匹配,不调用 LLM:
- 痛点词典:一条表达命中哪个痛点簇(效果/耐用/清洁/费力/伤材质/耗材)
- 情绪强度:感叹号 + 情绪词,痛得越狠信号越强
- 机会点得分 = 频次 × 平均情绪权重 × 来源多样性(单一来源要打折)

更深的语义聚类交给 AI:把 output/analysis.json 或需求地图喂给 Codex/Claude,
提示词见 README「怎么问 AI」。
"""

from __future__ import annotations

import re
from typing import Any

from camp_core import now_iso

# 痛点簇词典:关键词全部小写;innovation 是给学员的微创新提示,不是结论
PAIN_CLUSTERS: dict[str, dict[str, Any]] = {
    "效果不行": {
        "keywords": ["doesn't work", "does nothing", "no difference", "barely pick", "barely picks",
                     "useless", "waste of money", "did absolutely nothing", "went from weak to zero"],
        "innovation": "先证明效果:一次见效的结构(密齿/静电/湿式),内容用一遍过的前后对比",
    },
    "容易坏": {
        "keywords": ["broke", "broken", "fell apart", "snapped", "stopped working", "flimsy",
                     "cheap plastic", "wore flat", "stopped charging", "died in a month"],
        "innovation": "结构与材质加强(金属轴/加厚握把),把耐用做成卖点:保修承诺 + 拆解视频",
    },
    "清洁麻烦": {
        "keywords": ["hard to clean", "empty the chamber", "emptying", "clogged", "sticky residue",
                     "residue", "gross", "sticks to my fingers", "sticks to the glove",
                     "get it off", "cleaning the fur out"],
        "innovation": "自清洁/一键倒毛仓,毛不过手;清空过程本身就是短视频钩子",
    },
    "费时费力": {
        "keywords": ["takes forever", "arm is sore", "arm was dead", "arm work", "my wrist",
                     "my back", "an hour", "45 minutes", "kills my back", "kneeling",
                     "exhausting", "twice a day", "handle is too short", "longer handle"],
        "innovation": "省力设计:加长杆/宽幅滚头/电动化,内容主打计时实测",
    },
    "伤材质": {
        "keywords": ["scratch", "scratched", "snag", "snagged", "pulled threads", "pulled a thread",
                     "ruined", "track mark", "damage"],
        "innovation": "分材质的软硬度方案(皮质/丝绒/针织),敢在贵的面料上当镜头演示",
    },
    "耗材成本": {
        "keywords": ["refill", "refills", "replacement head", "replacement heads", "sheets cost",
                     "adds up", "whole roll", "reusable", "$80 a year", "the refills are"],
        "innovation": "免耗材可重复使用,把「一年省多少钱」算给用户看",
    },
    "场景不适配": {
        "keywords": ["car seat", "car seats", "stairs", "corners", "corner", "seam", "door pocket",
                     "too big", "one size fits all", "doesn't fit", "in the car", "car needs"],
        "innovation": "补被忽略的场景:车缝隙/楼梯/边角专用头,或一机多头",
    },
}

# 使用场景词典:机会点附带「痛发生在哪」
SCENES: dict[str, list[str]] = {
    "沙发": ["couch", "sofa", "cushion"],
    "汽车": ["car", "seat"],
    "地毯": ["carpet", "rug", "stairs"],
    "衣物/洗衣": ["clothes", "laundry", "dryer", "washer", "leggings", "scrubs", "sweater"],
    "床品/毯子": ["bedding", "blanket", "throw", "bed"],
}

_EMOTION_WORDS = ["hate", "frustrated", "frustrating", "terrible", "awful", "regret", "nightmare",
                  "never again", "give up", "gave up", "crime scene", "ugh", "worse than", "😭"]


def _match_any(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw in text]


def _intensity(text: str) -> float:
    """情绪权重 1.0-2.0:感叹号和情绪词各加一点,封顶翻倍。"""
    hits = len(re.findall(r"[!?]{2,}|!", text)) + sum(text.count(w) for w in _EMOTION_WORDS)
    return round(min(1.0 + hits * 0.25, 2.0), 2)


def tag_expression(expr: dict[str, Any]) -> dict[str, Any]:
    """给一条用户表达打标:命中的痛点簇、场景、情绪强度。"""
    text = str(expr.get("text", "")).lower()
    clusters = [name for name, spec in PAIN_CLUSTERS.items() if _match_any(text, spec["keywords"])]
    scenes = [name for name, words in SCENES.items() if _match_any(text, words)]
    return {**expr, "clusters": clusters, "scenes": scenes, "intensity": _intensity(text)}


def _evidence(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """机会点的证据:按票数×情绪挑最响的几条原话。"""
    ranked = sorted(rows, key=lambda r: (float(r.get("votes") or 0) + 1) * r["intensity"], reverse=True)
    keys = ("id", "source", "context", "votes", "text")
    return [{k: r.get(k, "") for k in keys} for r in ranked[:limit]]


def _build_opportunity(name: str, rows: list[dict[str, Any]], evidence_limit: int) -> dict[str, Any]:
    sources = sorted({str(r.get("source", "")) for r in rows})
    scenes: dict[str, int] = {}
    for row in rows:
        for scene in row["scenes"]:
            scenes[scene] = scenes.get(scene, 0) + 1
    avg_intensity = sum(r["intensity"] for r in rows) / len(rows)
    score = round(len(rows) * avg_intensity * (1 + 0.2 * (len(sources) - 1)), 1)
    return {
        "cluster": name,
        "count": len(rows),
        "sources": sources,
        "scenes": [s for s, _ in sorted(scenes.items(), key=lambda kv: -kv[1])[:3]],
        "avg_intensity": round(avg_intensity, 2),
        "score": score,
        "innovation": PAIN_CLUSTERS[name]["innovation"],
        "evidence": _evidence(rows, evidence_limit),
    }


def extract_signals(expressions: list[dict[str, Any]], config: dict[str, Any],
                    source_label: str) -> dict[str, Any]:
    """表达列表 → 需求地图数据(唯一入口,demo/analyze 共用)。"""
    rules = config.get("rules", {})
    min_count = int(rules.get("min_cluster_count") or 2)
    evidence_limit = int(rules.get("evidence_per_opportunity") or 3)

    tagged = [tag_expression(e) for e in expressions]
    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in tagged:
        for name in row["clusters"]:
            by_cluster.setdefault(name, []).append(row)

    opportunities = [
        _build_opportunity(name, rows, evidence_limit)
        for name, rows in by_cluster.items() if len(rows) >= min_count
    ]
    opportunities.sort(key=lambda o: -o["score"])
    for rank, opp in enumerate(opportunities, 1):
        opp["rank"] = rank

    matched = [r for r in tagged if r["clusters"]]
    return {
        "generated_at": now_iso(),
        "source": source_label,
        "expression_count": len(tagged),
        "matched_count": len(matched),
        "source_breakdown": _count_by(tagged, "source"),
        "opportunities": opportunities,
        "unmatched": [{"id": r.get("id", ""), "text": r.get("text", "")} for r in tagged if not r["clusters"]],
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        name = str(row.get(key) or "unknown")
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
