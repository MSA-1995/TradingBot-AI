"""
Live in-process news feed for the trading bot.

This replaces the old NewsAnalysisBot -> database -> TradingBot path with a
small memory-first pipeline:
fetch news, detect symbols, score sentiment, update the shared cache.
"""

from __future__ import annotations

import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict, deque
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Iterable

import json, zlib
import requests

try:
    from app_config.config import SYMBOLS
except Exception:
    SYMBOLS = []


RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptonews.com/news/feed/",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://decrypt.co/feed",
    "https://cryptopotato.com/feed/",
    "https://u.today/rss",
]

COIN_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "bnb": "binancecoin",
    "sol": "solana",
    "xrp": "ripple",
    "ada": "cardano",
    "avax": "avalanche-2",
    "uni": "uniswap",
    "dot": "polkadot",
    "link": "chainlink",
    "ltc": "litecoin",
    "algo": "algorand",
    "vet": "vechain",
    "icp": "internet-computer",
    "fil": "filecoin",
    "trx": "tron",
    "etc": "ethereum-classic",
    "xlm": "stellar",
    "theta": "theta-token",
    "hbar": "hedera-hashgraph",
}

SYMBOL_ALIASES = {
    "BTC/USDT": ("btc", "bitcoin"),
    "ETH/USDT": ("eth", "ethereum"),
    "BNB/USDT": ("bnb", "binance"),
    "SOL/USDT": ("sol", "solana"),
    "XRP/USDT": ("xrp", "ripple"),
    "ADA/USDT": ("ada", "cardano"),
    "AVAX/USDT": ("avax", "avalanche"),
    "UNI/USDT": ("uni", "uniswap"),
    "DOT/USDT": ("dot", "polkadot"),
    "LINK/USDT": ("link", "chainlink"),
    "LTC/USDT": ("ltc", "litecoin"),
    "ALGO/USDT": ("algo", "algorand"),
    "VET/USDT": ("vet", "vechain"),
    "ICP/USDT": ("icp", "internet computer"),
    "FIL/USDT": ("fil", "filecoin"),
    "TRX/USDT": ("trx", "tron"),
    "ETC/USDT": ("etc", "ethereum classic"),
    "XLM/USDT": ("xlm", "stellar"),
    "THETA/USDT": ("theta",),
    "HBAR/USDT": ("hbar", "hedera"),
}

POSITIVE_WORDS = {
    "bullish", "surge", "soar", "rally", "pump", "breakout", "recover",
    "rebound", "bounce", "gain", "rise", "growth", "profit", "adoption",
    "partnership", "launch", "upgrade", "mainnet", "integration", "listing",
    "approved", "institutional", "investment", "buy", "accumulate", "staking",
    "confidence", "optimistic", "positive", "strong", "support", "milestone",
    "breakthrough", "promising", "up",
}

NEGATIVE_WORDS = {
    "bearish", "crash", "dump", "plunge", "drop", "fall", "dip", "decline",
    "downtrend", "correction", "sell", "selloff", "liquidation", "loss",
    "hack", "exploit", "scam", "fraud", "rug", "ban", "lawsuit", "sec",
    "regulation", "investigation", "fine", "penalty", "delisting", "panic",
    "uncertain", "volatile", "warning", "risk", "concern", "doubt", "weak",
    "resistance", "down",
}

_lock = threading.RLock()
_events_by_symbol: dict[str, dict] = {}
_processed = OrderedDict()
_processed_max_size = 1500
_news_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mark_processed(news_id: str) -> bool:
    if not news_id:
        return False

    with _lock:
        if news_id in _processed:
            return False
        if len(_processed) >= _processed_max_size:
            _processed.popitem(last=False)
        _processed[news_id] = _now()
        return True


def _strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return unescape(value).strip()


def analyze_news_sentiment(text: str) -> tuple[str, float]:
    text_lower = (text or "").lower()
    if not text_lower.strip():
        return "NEUTRAL", 0.0

    pos = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    neg = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
    total = pos + neg

    if total == 0:
        return "NEUTRAL", 0.0

    score = max(-1.0, min(1.0, (pos - neg) / total))
    if score > 0.1:
        return "POSITIVE", round(score, 4)
    if score < -0.1:
        return "NEGATIVE", round(score, 4)
    return "NEUTRAL", round(score, 4)


def extract_symbols(text: str) -> list[str]:
    found = []
    lowered = f" {(text or '').lower()} "
    active_symbols = SYMBOLS or list(SYMBOL_ALIASES.keys())

    for symbol in active_symbols:
        aliases = SYMBOL_ALIASES.get(symbol)
        if not aliases:
            base = symbol.split("/")[0].lower()
            aliases = (base,)

        for alias in aliases:
            pattern = r"(?<![a-z0-9])" + re.escape(alias.lower()) + r"(?![a-z0-9])"
            if re.search(pattern, lowered):
                found.append(symbol)
                break

    return found


def record_news(symbol: str, title: str, sentiment: str, score: float,
                source: str = "LiveNews", url: str = "") -> None:
    event = {
        "symbol": symbol,
        "title": title[:500],
        "sentiment": sentiment,
        "score": float(score or 0),
        "source": source,
        "url": url,
        "timestamp": _now(),
    }

    with _lock:
        _events_by_symbol[symbol] = zlib.compress(json.dumps(event, default=str).encode())


def process_news_text(text: str, source: str = "Manual", url: str = "",
                      symbols: Iterable[str] | None = None) -> list[dict]:
    title = _strip_html(text)
    if not title:
        return []

    news_id = f"{source}:{url or title.lower()}"
    if not _mark_processed(news_id):
        return []

    detected_symbols = list(symbols) if symbols else extract_symbols(title)
    if not detected_symbols:
        return []

    sentiment, score = analyze_news_sentiment(title)
    recorded = []
    for symbol in detected_symbols:
        record_news(symbol, title, sentiment, score, source, url)
        recorded.append({
            "symbol": symbol,
            "title": title,
            "sentiment": sentiment,
            "score": score,
            "source": source,
            "url": url,
        })
    return recorded


def get_live_news_data(symbol: str | None = None, hours: int = 24) -> dict | None:
    cutoff = _now() - timedelta(hours=hours)

    with _lock:
        if symbol:
            raw = _events_by_symbol.get(symbol)
            event = json.loads(zlib.decompress(raw).decode()) if raw else None
            if event and datetime.fromisoformat(event["timestamp"]) >= cutoff:
                events = [event]
            else:
                _events_by_symbol.pop(symbol, None)
                events = []
        else:
            events = []
            for event_symbol, raw in list(_events_by_symbol.items()):
                if not raw:
                    continue
                event = json.loads(zlib.decompress(raw).decode())
                if datetime.fromisoformat(event["timestamp"]) >= cutoff:
                    events.append(event)
                else:
                    _events_by_symbol.pop(event_symbol, None)

    if not events:
        return None

    positive = sum(1 for e in events if e["sentiment"] == "POSITIVE")
    negative = sum(1 for e in events if e["sentiment"] == "NEGATIVE")
    neutral = sum(1 for e in events if e["sentiment"] == "NEUTRAL")
    score = max(-10.0, min(10.0, sum(float(e["score"]) for e in events)))

    latest = max(events, key=lambda e: e["timestamp"])
    return {
        "news_score": round(score, 2),
        "total": len(events),
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "latest_title": latest.get("title", ""),
        "latest_source": latest.get("source", ""),
    }


def _request_json(url: str, timeout: int = 12) -> dict:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "TradingBot-AI/1.0"})
    response.raise_for_status()
    return response.json()


def _fetch_rss_feed(feed_url: str) -> int:
    response = requests.get(feed_url, timeout=12, headers={"User-Agent": "TradingBot-AI/1.0"})
    response.raise_for_status()

    root = ET.fromstring(response.content)
    count = 0
    for item in root.findall(".//item")[:10]:
        title = _strip_html(item.findtext("title", ""))
        description = _strip_html(item.findtext("description", ""))
        link = item.findtext("link", "") or ""
        guid = item.findtext("guid", "") or link or title
        source = root.findtext(".//channel/title", "RSS")

        text = f"{title} {description}".strip()
        if process_news_text(text, source=source, url=link or guid):
            count += 1
    return count


def _fetch_cryptopanic(symbol: str) -> int:
    api_key = os.getenv("CRYPTOPANIC_KEY", "")
    if not api_key:
        return 0

    coin = symbol.split("/")[0]
    url = (
        "https://cryptopanic.com/api/v1/posts/"
        f"?auth_token={api_key}&currencies={coin}&filter=hot"
    )
    data = _request_json(url)
    count = 0
    for post in data.get("results", [])[:4]:
        title = post.get("title", "")
        link = post.get("url", "")
        votes = post.get("votes", {}) or {}
        positive = votes.get("positive", 0) or 0
        negative = votes.get("negative", 0) or 0

        sentiment, score = analyze_news_sentiment(title)
        if positive > negative * 2:
            sentiment, score = "POSITIVE", max(score, 0.5)
        elif negative > positive * 2:
            sentiment, score = "NEGATIVE", min(score, -0.5)

        news_id = f"cryptopanic:{post.get('id', link or title)}"
        if not _mark_processed(news_id):
            continue
        record_news(symbol, title, sentiment, score, "CryptoPanic", link)
        count += 1
    return count


def _fetch_coingecko_moves() -> int:
    coin_ids = ",".join(sorted(set(COIN_MAP.values())))
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={coin_ids}"
        "&order=market_cap_desc&per_page=100"
        "&sparkline=false&price_change_percentage=24h"
    )
    for attempt in range(3):
        try:
            data = _request_json(url, timeout=15)
            break
        except Exception as exc:
            if "429" in str(exc):
                wait = 60 * (attempt + 1)
                time.sleep(wait)
                if attempt == 2:
                    return 0
            else:
                raise
    id_to_symbol = {coin_id: f"{base.upper()}/USDT" for base, coin_id in COIN_MAP.items()}
    count = 0

    for coin in data:
        symbol = id_to_symbol.get(coin.get("id"))
        if not symbol:
            continue

        change = float(coin.get("price_change_percentage_24h") or 0)
        price = float(coin.get("current_price") or 0)
        if abs(change) < 2:
            continue

        direction = "surged" if change > 0 else "dropped"
        title = f"{symbol.split('/')[0]} {direction} {abs(change):.1f}% in 24h | Price: ${price:,.4f}"
        news_id = f"coingecko:{symbol}:{_now().strftime('%Y%m%d%H')}"
        if not _mark_processed(news_id):
            continue

        sentiment = "POSITIVE" if change > 0 else "NEGATIVE"
        score = max(-1.0, min(1.0, change / 10.0))
        record_news(symbol, title, sentiment, score, "CoinGecko", "")
        count += 1
    return count


def fetch_once() -> int:
    total = 0

    for feed_url in RSS_FEEDS:
        try:
            total += _fetch_rss_feed(feed_url)
        except Exception as exc:
            print(f"News RSS error [{feed_url}]: {exc}")

    for symbol in SYMBOLS:
        try:
            total += _fetch_cryptopanic(symbol)
            time.sleep(0.3)
        except Exception as exc:
            print(f"CryptoPanic error [{symbol}]: {exc}")

    try:
        total += _fetch_coingecko_moves()
    except Exception as exc:
        print(f"CoinGecko news error: {exc}")

    return total


def _run_loop(interval_seconds: int) -> None:
    print(f"Live news feed started (interval {interval_seconds}s)")
    while not _stop_event.is_set():
        try:
            count = fetch_once()
            if count:
                print(f"Live news feed: {count} new item(s) cached")
        except Exception as exc:
            print(f"Live news feed error: {exc}")

        _stop_event.wait(interval_seconds)


def start_live_news_feed(interval_seconds: int | None = None) -> bool:
    global _news_thread

    enabled = os.getenv("LIVE_NEWS_ENABLED", "1").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        print("Live news feed disabled by LIVE_NEWS_ENABLED")
        return False

    if interval_seconds is None:
        interval_seconds = int(os.getenv("NEWS_POLL_INTERVAL", "300") or 300)
    interval_seconds = max(60, int(interval_seconds))

    if _news_thread and _news_thread.is_alive():
        return True

    _stop_event.clear()
    _news_thread = threading.Thread(
        target=_run_loop,
        args=(interval_seconds,),
        name="live-news-feed",
        daemon=True,
    )
    _news_thread.start()
    return True


def stop_live_news_feed() -> None:
    _stop_event.set()
