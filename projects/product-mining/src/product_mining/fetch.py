"""真实采集:只保留纯 HTTP 可达、不需要密钥的两个源,全部标准库 urllib。

- Reddit 公开 JSON:search.json 搜帖子 + 帖子 .json 拿高票评论
- Amazon 差评:Woot Reviews JSON(源项目验证过,能拿 Amazon US written reviews)

Google Trends(易限流)、TikTok 评论(要登录态/Playwright)、PRAW 不迁,
见 README「进阶:更多数据源」指路源项目。外部源偶发 403/429 是对方的脾气,不是项目坏了。
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib import error, parse, request

from camp_core import now_iso

FRIENDLY_HINT = ("外部源偶发 403/429/超时(风控或网络),不是你的环境坏了;"
                 "稍后重跑,或先把手动复制的原话贴进 input/ 再 analyze")

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) sct-camp-product-mining/0.1"}


def _get_json(url: str, referer: str = "") -> Any:
    headers = {**_HEADERS, **({"Referer": referer} if referer else {})}
    with request.urlopen(request.Request(url, headers=headers), timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _expr(source: str, context: str, votes: Any, text: str, url: str) -> dict[str, Any]:
    return {"id": f"{source}-{abs(hash(text)) % 10**8}", "source": source, "context": context,
            "votes": int(votes or 0), "text": " ".join(str(text).split())[:1200],
            "url": url, "fetched_at": now_iso()}


def _top_comments(permalink: str, limit: int) -> list[dict[str, Any]]:
    data = _get_json(permalink.rstrip("/") + f".json?limit={limit}&sort=top")
    if not isinstance(data, list) or len(data) < 2:
        return []
    out = []
    for node in data[1].get("data", {}).get("children", []):
        item = node.get("data", {})
        if node.get("kind") == "t1" and item.get("body"):
            out.append(item)
    return out[:limit]


def fetch_reddit(keyword: str, limit: int, comments_per_post: int = 5) -> list[dict[str, Any]]:
    """Reddit 公开 JSON:关键词搜帖 → 帖子正文 + 高票评论,一条原话一条表达。"""
    url = f"https://www.reddit.com/search.json?q={parse.quote(keyword)}&limit={limit}&sort=relevance"
    data = _get_json(url)
    expressions: list[dict[str, Any]] = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        link = "https://www.reddit.com" + post.get("permalink", "")
        context = f"r/{post.get('subreddit', '')} · 帖子"
        text = f"{post.get('title', '')}. {post.get('selftext', '')}".strip(". ")
        expressions.append(_expr("reddit", context, post.get("score"), text, link))
        try:
            for comment in _top_comments(link, comments_per_post):
                expressions.append(_expr("reddit", f"r/{post.get('subreddit', '')} · 评论",
                                         comment.get("score"), comment.get("body", ""), link))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            pass  # 单帖评论拿不到不拖垮整轮
        time.sleep(0.5)
    return expressions


def fetch_amazon_bad_reviews(asin: str, limit: int) -> list[dict[str, Any]]:
    """Woot Reviews JSON:按 1-3 星逐档拉 Amazon US 差评。"""
    expressions: list[dict[str, Any]] = []
    for star in (1, 2, 3):
        if len(expressions) >= limit:
            break
        params = parse.urlencode({"filter": star, "isVerified": "false", "sort": 0, "page": 1})
        url = f"https://www.woot.com/review/Reviews/{asin}?{params}"
        payload = _get_json(url, referer=f"https://www.woot.com/review/{asin}")
        for review in payload.get("Reviews", []):
            text = f"{review.get('Title', '')}. {review.get('Text', '')}".strip(". ")
            expressions.append(_expr("amazon", f"{star}★ 差评 · ASIN {asin}",
                                     review.get("HelpfulVotes"), text,
                                     f"https://www.amazon.com/dp/{asin}"))
        time.sleep(0.3)
    return expressions[:limit]
