"""采集:RSS/Atom feed + GitHub 仓库搜索,全部标准库。

约定:每个源带超时与重试;单源失败只进 errors,绝不拖垮整轮。
产出统一形状:{id, source, tier, bucket, title, link, summary, published, [stars...]}。
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

USER_AGENT = "sct-camp-news-radar/0.1"
FRIENDLY_HINT = "外部源偶发超时/限流不是项目坏了:重跑一次,或 --limit 3 先少拉几个源。"


# ---------- 文本与时间 ----------

def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def item_id(source: str, title: str, link: str) -> str:
    return hashlib.sha1(f"{source}|{title}|{link}".encode("utf-8")).hexdigest()[:16]


# ---------- HTTP(带重试) ----------

def fetch_url(url: str, timeout: int = 10, retries: int = 2) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/xml",
    })
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1 + attempt)
    raise last_error or RuntimeError(f"fetch failed: {url}")


# ---------- RSS/Atom 解析 ----------

def _text_of(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean_text(found.text)
    for child in node:
        if child.tag.rsplit("}", 1)[-1] in names and child.text:
            return clean_text(child.text)
    return ""


def _link_of(node: ET.Element) -> str:
    direct = _text_of(node, ["link"])
    if direct:
        return direct
    fallback = ""
    for child in node:
        if child.tag.rsplit("}", 1)[-1] != "link":
            continue
        href, rel = child.attrib.get("href", ""), child.attrib.get("rel", "")
        if href and rel == "alternate":
            return href
        if href and not fallback and rel not in ("replies", "self"):
            fallback = href
    return fallback


def parse_feed(source: dict[str, Any], body: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    nodes = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    items: list[dict[str, Any]] = []
    for node in nodes:
        title = _text_of(node, ["title"])
        link = _link_of(node)
        if not title or not link:
            continue
        items.append({
            "id": item_id(str(source["name"]), title, link),
            "source": str(source["name"]),
            "tier": int(source.get("tier") or 1),
            "bucket": str(source.get("bucket") or "feed"),
            "title": title,
            "link": link,
            "summary": _text_of(node, ["description", "summary", "content", "encoded"])[:600],
            "published": _text_of(node, ["pubDate", "published", "updated"]),
        })
    return items


# ---------- GitHub 搜索 ----------

def fetch_github_search(search: dict[str, Any], limit: int, timeout: int, retries: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        "q": str(search["query"]), "sort": "stars", "order": "desc", "per_page": str(limit),
    })
    payload = json.loads(fetch_url(f"https://api.github.com/search/repositories?{query}", timeout, retries))
    items: list[dict[str, Any]] = []
    for repo in payload.get("items", [])[:limit]:
        name, link = str(repo.get("full_name") or ""), str(repo.get("html_url") or "")
        if not name or not link:
            continue
        items.append({
            "id": item_id("github", name, link),
            "source": str(search["name"]),
            "tier": int(search.get("tier") or 4),
            "bucket": str(search.get("bucket") or "github_projects"),
            "title": name,
            "link": link,
            "summary": clean_text(str(repo.get("description") or "")),
            "published": str(repo.get("pushed_at") or repo.get("updated_at") or ""),
            "stars": int(repo.get("stargazers_count") or 0),
            "forks": int(repo.get("forks_count") or 0),
            "language": str(repo.get("language") or ""),
        })
    return items


# ---------- 整轮采集 ----------

def _within_lookback(item: dict[str, Any], cutoff: datetime) -> bool:
    published = parse_date(str(item.get("published") or ""))
    return published is None or published >= cutoff  # 无日期的源不淘汰,交给打分


def fetch_all(sources_cfg: dict[str, Any], config: dict[str, Any],
              source_limit: int = 0) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """跑一整轮采集。source_limit>0 时只拉前 N 个源(快速验证用)。"""
    fetch_cfg = config.get("fetch", {})
    timeout = int(fetch_cfg.get("timeout_seconds") or 10)
    retries = int(fetch_cfg.get("retries") or 2)
    per_source = int(fetch_cfg.get("max_items_per_source") or 8)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=int(config.get("lookback_hours") or 96))

    jobs: list[tuple[str, dict[str, Any]]] = [("feed", s) for s in sources_cfg.get("feeds", [])]
    jobs += [("github", s) for s in sources_cfg.get("github_searches", [])]
    if source_limit > 0:
        jobs = jobs[:source_limit]

    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for kind, source in jobs:
        try:
            if kind == "github":
                rows = fetch_github_search(source, per_source, timeout, retries)
            else:
                body = fetch_url(str(source["url"]), timeout, retries)
                rows = [r for r in parse_feed(source, body) if _within_lookback(r, cutoff)]
            fresh = [r for r in rows[: int(source.get("max_items") or per_source)] if r["id"] not in seen]
            seen.update(r["id"] for r in fresh)
            items.extend(fresh)
            print(f"OK   {source['name']}: {len(fresh)} 条")
        except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError, json.JSONDecodeError) as exc:
            errors.append({"source": str(source.get("name")), "error": str(exc)})
            print(f"WARN {source.get('name')}: 拉取失败({exc})")
    return items, errors
