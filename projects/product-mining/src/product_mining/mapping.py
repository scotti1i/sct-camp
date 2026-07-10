"""需求地图渲染:analysis dict → camp-report 一页 HTML。

工作台页面复用这里的片段函数(overview_card / opportunities_table / evidence_sections),
保证网页和报告长一个样。每个机会点都带用户原话证据——没有证据链的结论不许出现。
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from camp_report import kv_card, save_report, table


def overview_card(analysis: dict[str, Any]) -> str:
    breakdown = " / ".join(f"{k} {v}" for k, v in analysis.get("source_breakdown", {}).items())
    return kv_card("本轮概览", [
        ("生成时间", analysis.get("generated_at", "")),
        ("数据来源", analysis.get("source", "")),
        ("用户表达", analysis.get("expression_count", 0)),
        ("命中痛点", analysis.get("matched_count", 0)),
        ("表达分布", breakdown or "-"),
        ("机会点", len(analysis.get("opportunities", []))),
    ])


def opportunities_table(analysis: dict[str, Any]) -> str:
    rows = []
    for opp in analysis.get("opportunities", []):
        rows.append([
            opp["rank"], opp["cluster"], opp["count"],
            "、".join(opp["sources"]), "、".join(opp["scenes"]) or "-",
            opp["avg_intensity"], opp["score"], opp["innovation"],
        ])
    if not rows:
        return "<p>没有形成机会点:表达太少或太散。先补材料(fetch 或往 input/ 里贴原话),再跑 analyze。</p>"
    return table(["#", "痛点簇", "频次", "来源", "高频场景", "情绪", "得分", "微创新提示"], rows)


def evidence_sections(analysis: dict[str, Any]) -> str:
    parts = []
    for opp in analysis.get("opportunities", []):
        rows = [[e.get("source", ""), e.get("context", ""), e.get("votes", ""),
                 e.get("text", "")] for e in opp.get("evidence", [])]
        parts.append(f"<h2>#{opp['rank']} {_html.escape(opp['cluster'])} · 用户原话证据</h2>"
                     + table(["来源", "出处", "票数", "原话"], rows))
    return "".join(parts)


def next_steps_card(analysis: dict[str, Any]) -> str:
    top = [o["cluster"] for o in analysis.get("opportunities", [])[:3]]
    pairs: list[tuple[str, Any]] = [
        ("1. 交叉验证", f"优先深挖:{'、'.join(top) or '先补材料'}(拿地图问 AI,提示词见 README)"),
        ("2. 拿样验证", "每个机会点找 1-2 个供应商打样,确认微创新在供应链上做得出来"),
        ("3. 内容测试", "把证据里的用户原话拍成 15-60 秒前后对比短视频,用播放/评论测真需求"),
    ]
    return kv_card("下一步(最小成本验证)", pairs)


def write_map(analysis: dict[str, Any], path: Path) -> Path:
    body = (
        overview_card(analysis)
        + "<h2>机会点排序(按得分)</h2>" + opportunities_table(analysis)
        + evidence_sections(analysis)
        + next_steps_card(analysis)
    )
    return save_report(path, "选品挖掘 · 需求地图", body, subtitle=str(analysis.get("source", "")))
