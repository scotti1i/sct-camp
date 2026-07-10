"""摘要与日报:每条命中内容配一句摘要,再产出 HTML 日报和飞书卡片。

摘要两条腿:默认纯规则(零密钥、离线可跑);.env 里有 LLM_API_KEY 且 config.llm
填了 base_url/model 才走 LLM(OpenAI 兼容 /chat/completions),失败静默退回规则。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from camp_core import secret
from camp_report import kv_card, save_report, table

# ---------- 摘要 ----------

def rule_digest(item: dict[str, Any]) -> str:
    """纯规则摘要:取正文第一句,砍到 110 字。"""
    text = str(item.get("summary") or "").strip()
    if not text:
        return "源里没给正文摘要,点链接看它解决什么问题、给谁用。"
    first = re.split(r"(?<=[。.!?!?])\s+", text, maxsplit=1)[0]
    return first if len(first) <= 110 else first[:110].rstrip() + "..."


def _llm_config(config: dict[str, Any]) -> tuple[str, str, str]:
    llm = config.get("llm", {})
    key = secret(str(llm.get("api_key_env") or "LLM_API_KEY"))
    return str(llm.get("base_url") or ""), str(llm.get("model") or ""), key


def llm_digest(item: dict[str, Any], base_url: str, model: str, key: str) -> str:
    """LLM 摘要一条;任何异常都退回规则摘要,不让日报断在这。"""
    prompt = (
        "用一句不超过60字的中文,说清这条 AI 资讯做了什么、对做内容/电商/自动化的个体创业者有什么用。"
        f"只输出这一句。标题:{item.get('title')}\n正文:{str(item.get('summary'))[:500]}"
    )
    body = json.dumps({"model": model, "max_tokens": 120,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = str(payload["choices"][0]["message"]["content"]).strip()
        return text or rule_digest(item)
    except Exception:
        return rule_digest(item)


def add_digests(analysis: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """给每个视角的命中条目补 digest 字段(同一条目只算一次)。"""
    base_url, model, key = _llm_config(config)
    use_llm = bool(base_url and model and key)
    cache: dict[str, str] = {}
    for profile in analysis.get("profiles", {}).values():
        for item in profile.get("items", []):
            item_key = str(item.get("id"))
            if item_key not in cache:
                cache[item_key] = llm_digest(item, base_url, model, key) if use_llm else rule_digest(item)
            item["digest"] = cache[item_key]
    analysis["digest_engine"] = "llm" if use_llm else "rule"
    return analysis


# ---------- HTML 日报 ----------

def _meta(item: dict[str, Any]) -> str:
    parts = [str(item.get("source") or ""), str(item.get("published") or "")[:10]]
    if item.get("stars"):
        parts.append(f"{int(item['stars']):,} stars")
    return " · ".join(p for p in parts if p)


def profile_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>这个视角今天没有过门槛的内容。宁可空着,也不灌水。</p>"
    rows = [[idx, row.get("title", ""), row.get("digest", ""), row.get("score", 0),
             row.get("difficulty", ""), _meta(row), row.get("link", "")]
            for idx, row in enumerate(items, 1)]
    return table(["#", "标题", "摘要", "分数", "难度", "来源", "链接"], rows)


def overview_card(analysis: dict[str, Any]) -> str:
    pairs: list[tuple[str, Any]] = [
        ("生成时间", analysis.get("generated_at", "")),
        ("数据来源", analysis.get("source", "")),
        ("候选条目", analysis.get("item_count", 0)),
        ("摘要引擎", "LLM" if analysis.get("digest_engine") == "llm" else "纯规则(零密钥)"),
    ]
    for profile in analysis.get("profiles", {}).values():
        pairs.append((f"{profile.get('label')} 命中", len(profile.get("items", []))))
    if analysis.get("errors"):
        pairs.append(("拉取失败源", len(analysis["errors"])))
    return kv_card("今日雷达概览", pairs)


def write_report(analysis: dict[str, Any], path: Path) -> Path:
    body = overview_card(analysis)
    for profile in analysis.get("profiles", {}).values():
        note = f'<p class="muted">{profile.get("note")}</p>' if profile.get("note") else ""
        body += f"<h2>{profile.get('label')}</h2>{note}{profile_table(profile.get('items', []))}"
    return save_report(path, "AI 新闻雷达 · 今日雷达", body, subtitle=str(analysis.get("source", "")))


# ---------- 飞书卡片 ----------

def build_card(analysis: dict[str, Any], title: str) -> dict[str, Any]:
    elements: list[dict[str, Any]] = [{"tag": "div", "text": {"tag": "lark_md", "content":
        f"**{str(analysis.get('generated_at', ''))[:10]}｜候选 {analysis.get('item_count', 0)} 条**"}}]
    for profile in analysis.get("profiles", {}).values():
        items = profile.get("items", [])
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md",
                         "content": f"**{profile.get('label')}({len(items)})**"}})
        for idx, item in enumerate(items, 1):
            lines = [f"**{idx}. {item.get('title')}**", str(item.get("digest") or ""),
                     f"{_meta(item)} / [原文]({item.get('link')})"]
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})
    elements.append({"tag": "note", "elements": [{"tag": "plain_text",
                     "content": "没有过门槛的内容宁可空着;分数口径见项目 config 的 profiles。"}]})
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "blue", "title": {"tag": "plain_text", "content": title}},
        "elements": elements,
    }
