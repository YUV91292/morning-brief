"""
News fetcher — parses RSS feeds using stdlib xml.etree + requests.
No feedparser dependency required.
"""
import re
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

log = logging.getLogger(__name__)

RSS_NS = {
    "dc":      "http://purl.org/dc/elements/1.1/",
    "media":   "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom":    "http://www.w3.org/2005/Atom",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DailyDigestBot/1.0; "
        "+https://github.com/news-digest)"
    ),
    "Accept": "application/rss+xml,application/xml,text/xml,*/*",
}

def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(date_str[:19])])
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None

def _extract_image_from_item(item) -> Optional[str]:
    for tag in ("media:content", "media:thumbnail"):
        el = item.find(tag, RSS_NS)
        if el is not None:
            url = el.get("url")
            if url and url.startswith("http"):
                return url
    enc = item.find("enclosure")
    if enc is not None:
        url = enc.get("url", "")
        if url.startswith("http") and any(
            url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")
        ):
            return url
    desc = item.findtext("description") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if m:
        url = m.group(1)
        if url.startswith("http"):
            return url
    return None

def fetch_feed(name: str, url: str, max_age_hours: int = 36) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("Feed %s failed: %s", name, exc)
        return []
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        log.warning("Feed %s XML parse error: %s", name, exc)
        return []
    items = root.findall(".//item") or root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    articles = []
    for item in items:
        title = _clean(
            item.findtext("title")
            or item.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        )
        if not title:
            continue
        link = (
            item.findtext("link")
            or (item.find("{http://www.w3.org/2005/Atom}link") or {}).get("href", "")
            or ""
        ).strip()
        desc = _clean(
            item.findtext("description")
            or item.findtext("{http://www.w3.org/2005/Atom}summary")
            or item.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        )[:800]
        pub_str = (
            item.findtext("pubDate")
            or item.findtext("{http://www.w3.org/2005/Atom}published")
            or item.findtext("{http://www.w3.org/2005/Atom}updated")
            or item.findtext("dc:date", namespaces=RSS_NS)
        )
        pub_dt = _parse_date(pub_str)
        if pub_dt and pub_dt < cutoff:
            continue
        image_url = _extract_image_from_item(item)
        articles.append({
            "source": name,
            "title": title,
            "link": link,
            "summary": desc,
            "published": pub_dt.isoformat() if pub_dt else "",
            "image_url": image_url or "",
        })
    log.info("Feed %-25s → %d articles", name, len(articles))
    return articles


def fetch_all_feeds(feeds: dict[str, str], max_age_hours: int = 36) -> list[dict]:
    all_articles: list[dict] = []
    for name, url in feeds.items():
        articles = fetch_feed(name, url, max_age_hours=max_age_hours)
        all_articles.extend(articles)
        time.sleep(0.5)
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for art in all_articles:
        key = re.sub(r"[^a-z0-9]", "", art["title"].lower())[:60]
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(art)
    log.info("Total unique articles: %d (from %d raw)", len(deduped), len(all_articles))
    return deduped


def fetch_market_data() -> dict:
    tickers = {
        "S&P 500":    "^GSPC",
        "Dow Jones":  "^DJI",
        "NASDAQ":     "^IXIC",
        "FTSE 100":   "^FTSE",
        "Nikkei 225": "^N225",
        "Gold":       "GC=F",
        "Oil (WTI)":  "CL=F",
        "USD/INR":    "INR=X",
        "USD/AED":    "AED=X",
        "Bitcoin":    "BTC-USD",
    }
    results = {}
    for label, symbol in tickers.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice") or meta.get("previousClose", 0)
            prev  = meta.get("previousClose") or meta.get("chartPreviousClose", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            results[label] = {
                "price": price,
                "change_pct": round(change_pct, 2),
                "currency": meta.get("currency", "USD"),
            }
        except Exception as exc:
            log.debug("Market fetch for %s failed: %s", label, exc)
    return results
