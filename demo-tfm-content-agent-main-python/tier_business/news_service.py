import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
import httpx
import re

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl={lang}&gl={gl}&ceid={ceid}"

LANG_CONFIG = {
    "es": {"gl": "ES", "ceid": "ES:es"},
    "en": {"gl": "US", "ceid": "US:en"},
}


async def fetch_news_rss(niche: str, lang: str = "es") -> list[dict[str, Any]]:
    cfg = LANG_CONFIG.get(lang, LANG_CONFIG["es"])
    url = GOOGLE_NEWS_RSS.format(
        query=niche.replace(" ", "+"),
        lang=lang,
        gl=cfg["gl"],
        ceid=cfg["ceid"],
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        xml_text = resp.text

    return _parse_rss(xml_text)


def fetch_news_rss_sync(niche: str, lang: str = "es") -> list[dict[str, Any]]:
    return asyncio.run(fetch_news_rss(niche, lang))


def _parse_rss(xml_text: str) -> list[dict[str, Any]]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    channel = root.find("channel")
    if channel is None:
        return items

    for item in channel.findall("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        source_el = item.find("source")

        title = title_el.text if title_el is not None else ""
        link = link_el.text if link_el is not None else ""
        pub_date = pub_el.text if pub_el is not None else ""
        source_name = source_el.text if source_el is not None else ""

        title = _clean_text(title)
        if not title:
            continue

        published_at = _parse_date(pub_date)

        items.append({
            "title": title,
            "source_url": link,
            "source_name": source_name,
            "published_at": published_at,
            "summary": "",
            "topic": "otro",
        })

    return items[:20]


def _clean_text(text: str) -> str:
    text = re.sub(r"\s*-\s*[\w\s]+$", "", text)
    return text.strip()


def _parse_date(date_str: str) -> str:
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return datetime.now(timezone.utc).isoformat()


def rank_news(items: list[dict], topic_scores: dict[str, float]) -> list[dict]:
    now = datetime.now(timezone.utc)
    scored = []
    for item in items:
        topic = item.get("topic", "otro")
        topic_score = topic_scores.get(topic, 0.0)

        published_at = item.get("published_at", "")
        recency_score = 0.0
        if published_at:
            try:
                pub_dt = datetime.fromisoformat(published_at)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                hours_old = (now - pub_dt).total_seconds() / 3600
                recency_score = max(0.0, 1.0 - hours_old / 72)
            except ValueError:
                pass

        score = (topic_score * 1.5) + recency_score
        scored.append({**item, "_score": score})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    for item in scored:
        item.pop("_score", None)
    return scored


def get_top_topics(topic_scores: dict[str, float], n: int = 5) -> list[str]:
    sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
    return [t for t, _ in sorted_topics[:n]]


def build_boost_prompt(top_topics: list[str]) -> str:
    if not top_topics:
        return ""
    topics_str = ", ".join(top_topics)
    return (
        f"El usuario muestra interés especial en: {topics_str}. "
        "Prioriza ángulos relacionados con estos temas cuando sea relevante."
    )
