"""
Market Acceptance Macro Advisor

This module avoids calling every bounce a bull market. It asks a harder
question: did the market accept higher prices?
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd


class MacroTrendAdvisor:
    """
    Macro status engine focused on rejecting fake rallies.

    Public API kept compatible with the old bot:
    - get_macro_status() -> str
    - analyze_market_state() -> dict
    - can_aim_high() -> bool
    - get_display_info() -> dict
    - invalidate_cache() -> None
    """

    LEADERS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
    CORE_LEADERS = {"BTC/USDT", "ETH/USDT"}

    CACHE_DURATION = 90
    STATE_MEMORY_SECONDS = 75 * 60
    MIN_BULL_ACCEPTANCE = 75
    RECOVERY_ACCEPTANCE = 58
    BEAR_SCORE_THRESHOLD = 62

    def __init__(self, exchange=None, dl_client=None, storage=None):
        self.exchange = exchange
        self.dl_client = dl_client
        self.db = storage

        self._last_status = "⚪ SIDEWAYS"
        self._last_check_time = 0.0
        self._last_analysis = {}
        self._last_analysis_time = 0.0
        self._display_info = {
            "status": self._last_status,
            "total_bull": 0,
            "total_bear": 0,
            "detail": "Not analyzed yet",
        }

        self._last_bear_time: Optional[float] = None
        self._recovery_started_at: Optional[float] = None
        self._recovery_success_count = 0
        self._recovery_fail_count = 0
        self._status_history = []

        self._external_client = self._load_external_client()
        self._news_analyzer = self._load_news_analyzer()
        self._mtf = self._load_component("multi_timeframe_analyzer", "MultiTimeframeAnalyzer")
        self._fib = self._load_component("fibonacci_analyzer", "FibonacciAnalyzer")
        self._ted = self._load_component("trend_early_detector", "TrendEarlyDetector")
        self._volume_engine = self._load_component("volume_forecast_engine", "VolumeForecastEngine")

    def get_macro_status(self) -> str:
        if not self.exchange:
            return "⚪ SIDEWAYS"

        now = time.time()
        if now - self._last_check_time < self.CACHE_DURATION:
            return self._last_status

        try:
            snapshot = self._build_market_snapshot()
            status = self._resolve_status(snapshot)
            return self._finalize(status, snapshot)
        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor error: {e}")
            return self._last_status or "⚪ SIDEWAYS"

    def can_aim_high(self) -> bool:
        return "BULL_MARKET" in self.get_macro_status()

    def get_display_info(self) -> dict:
        return self._display_info

    def invalidate_cache(self) -> None:
        self._last_check_time = 0.0
        self._last_analysis_time = 0.0
        self._last_analysis = {}

    def analyze_market_state(self) -> dict:
        if not self.exchange:
            return self._empty_state()

        if time.time() - self._last_analysis_time < self.CACHE_DURATION:
            return self._last_analysis or self._empty_state()

        try:
            snapshot = self._build_market_snapshot()
            self._last_analysis = snapshot["state"]
            self._last_analysis_time = time.time()
            return self._last_analysis
        except Exception as e:
            print(f"⚠️ analyze_market_state error: {e}")
            return self._empty_state()

    def _build_market_snapshot(self) -> dict:
        frames = {
            "15m": self._analyze_timeframe("15m", 80),
            "1h": self._analyze_timeframe("1h", 80),
            "4h": self._analyze_timeframe("4h", 80),
        }
        combined = self._combine_timeframes(frames["15m"], frames["1h"], frames["4h"])
        acceptance = self._calculate_acceptance(frames, combined)

        state = {
            "15m": frames["15m"],
            "1h": frames["1h"],
            "4h": frames["4h"],
            "combined": combined,
            "acceptance": acceptance,
        }
        return {"frames": frames, "combined": combined, "acceptance": acceptance, "state": state}

    def _resolve_status(self, snapshot: dict) -> str:
        combined = snapshot["combined"]
        acceptance = snapshot["acceptance"]
        now = time.time()

        direction = combined.get("direction", "NEUTRAL")
        bear_score = combined.get("bear_score", 0)
        acceptance_score = acceptance.get("score", 0)
        fake_rally = acceptance.get("fake_rally", False)

        if direction == "BEARISH" or bear_score >= self.BEAR_SCORE_THRESHOLD:
            self._last_bear_time = now
            self._reset_recovery(failed=True)
            return "🔴 BEAR_MARKET" if combined.get("strength") == "STRONG" else "🔴 MILD_BEAR"

        recent_bear = self._last_bear_time and (now - self._last_bear_time < self.STATE_MEMORY_SECONDS)

        if fake_rally:
            self._reset_recovery(failed=True)
            return "⚪ FAKE_BULL_RISK"

        if acceptance_score >= self.MIN_BULL_ACCEPTANCE and direction == "BULLISH":
            self._recovery_success_count += 1
            if self._recovery_started_at is None:
                self._recovery_started_at = now

            recovery_age = now - self._recovery_started_at
            strong_confirmation = (
                acceptance.get("leader_score", 0) >= 19
                and acceptance.get("breakout_score", 0) >= 13
                and acceptance.get("volume_score", 0) >= 13
            )

            if not recent_bear or (self._recovery_success_count >= 2 and strong_confirmation):
                return "🟢 BULL_MARKET" if acceptance_score >= 84 else "🟢 MILD_BULL"

            if recovery_age >= 20 * 60 and self._recovery_success_count >= 2:
                return "🟢 MILD_BULL"

            return "⚪ RECOVERY_TEST"

        if acceptance_score >= self.RECOVERY_ACCEPTANCE:
            if self._recovery_started_at is None:
                self._recovery_started_at = now
            self._recovery_success_count = max(1, self._recovery_success_count)
            return "⚪ RECOVERY_TEST"

        if recent_bear:
            self._reset_recovery(failed=True)
            return "⚪ BEAR_COOLDOWN"

        self._reset_recovery(failed=False)
        return "⚪ SIDEWAYS"

    def _analyze_timeframe(self, timeframe: str, limit: int) -> dict:
        symbol_results = {}
        total_bull = 0.0
        total_bear = 0.0
        bull_count = 0
        bear_count = 0

        for symbol in self.LEADERS:
            df = self._fetch_df(symbol, timeframe, limit)
            if df is None or len(df) < 30:
                continue

            result = self._analyze_symbol_df(symbol, df)
            symbol_results[symbol] = result
            total_bull += result["bull"]
            total_bear += result["bear"]
            if result["status"] == "BULLISH":
                bull_count += 1
            elif result["status"] == "BEARISH":
                bear_count += 1

        if not symbol_results:
            return {
                "status": "NEUTRAL",
                "confidence": 50,
                "bull_score": 0,
                "bear_score": 0,
                "bull_count": 0,
                "bear_count": 0,
                "symbols": {},
                "reason": f"No data ({timeframe})",
            }

        total = total_bull + total_bear
        bull_pct = total_bull / total * 100 if total > 0 else 50
        bear_pct = total_bear / total * 100 if total > 0 else 50

        btc = symbol_results.get("BTC/USDT", {})
        eth = symbol_results.get("ETH/USDT", {})
        core_bear = btc.get("status") == "BEARISH" and eth.get("status") == "BEARISH"
        core_bull = btc.get("status") == "BULLISH" and eth.get("status") == "BULLISH"

        if bear_count >= 3 or core_bear or bear_pct >= 65:
            status = "STRONG_BEARISH" if bear_pct >= 72 or core_bear else "BEARISH"
            confidence = max(bear_pct, 62)
        elif bull_count >= 3 and (core_bull or btc.get("status") == "BULLISH") and bull_pct >= 60:
            status = "STRONG_BULLISH" if bull_pct >= 74 and core_bull else "BULLISH"
            confidence = max(bull_pct, 60)
        else:
            status = "NEUTRAL"
            confidence = 50

        return {
            "status": status,
            "confidence": round(confidence, 1),
            "bull_score": round(total_bull, 1),
            "bear_score": round(total_bear, 1),
            "bull_count": bull_count,
            "bear_count": bear_count,
            "symbols": symbol_results,
            "reason": f"{status} {timeframe}: bulls {bull_count}/5, bears {bear_count}/5",
        }

    def _analyze_symbol_df(self, symbol: str, df: pd.DataFrame) -> dict:
        close = df["close"]
        volume = df["volume"]

        price = float(close.iloc[-1])
        prev_price = float(close.iloc[-11])
        change_10 = ((price - prev_price) / prev_price * 100) if prev_price > 0 else 0

        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50_series = close.ewm(span=50, adjust=False).mean()
        ema50 = float(ema50_series.iloc[-1])
        ema50_prev = float(ema50_series.iloc[-6])
        ema50_slope = ((ema50 - ema50_prev) / ema50_prev * 100) if ema50_prev > 0 else 0

        rsi = self._calc_rsi(close)
        macd_hist = self._macd_hist(close)
        macd_cur = float(macd_hist.iloc[-1])
        macd_prev = float(macd_hist.iloc[-2])

        avg_vol = float(volume.tail(30).mean())
        recent_vol = float(volume.tail(3).mean())
        volume_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        candle = self._last_candle_quality(df)
        structure = self._structure_score(df)
        breakout = self._breakout_acceptance(df)
        distribution = self._distribution_risk(df, volume_ratio)

        bull = 0.0
        bear = 0.0

        if change_10 > 1.2:
            bull += 10
        elif change_10 > 0.35:
            bull += 5
        elif change_10 < -1.2:
            bear += 10
        elif change_10 < -0.35:
            bear += 5

        if price > ema21 > ema50:
            bull += 12
        elif price > ema21:
            bull += 5
        if price < ema21 < ema50:
            bear += 12
        elif price < ema21:
            bear += 5

        if ema50_slope > 0.08:
            bull += 5
        elif ema50_slope < -0.08:
            bear += 5

        if 52 <= rsi <= 68:
            bull += 5
        elif rsi > 75:
            bear += 7
        elif rsi < 42:
            bear += 4

        if macd_cur > 0 and macd_cur > macd_prev:
            bull += 6
        elif macd_cur < 0 and macd_cur < macd_prev:
            bear += 6

        if volume_ratio >= 1.2 and candle["close_strength"] >= 0.58 and candle["body_ratio"] >= 0.35:
            bull += 10
        elif volume_ratio >= 1.5 and candle["upper_wick_ratio"] > 0.45:
            bear += 12
        elif volume_ratio < 0.75 and change_10 > 0.35:
            bear += 10

        bull += structure.get("bull", 0)
        bear += structure.get("bear", 0)
        bull += breakout.get("score", 0)
        bear += distribution

        if candle["upper_wick_ratio"] > 0.55:
            bear += 6
        if candle["close_strength"] > 0.72 and candle["body_ratio"] > 0.45:
            bull += 5

        status = "NEUTRAL"
        if bull >= bear + 8 and bull >= 24:
            status = "BULLISH"
        elif bear >= bull + 8 and bear >= 24:
            status = "BEARISH"

        return {
            "status": status,
            "bull": round(bull, 1),
            "bear": round(bear, 1),
            "close": price,
            "change_10": round(change_10, 3),
            "rsi": round(rsi, 1),
            "volume_ratio": round(volume_ratio, 2),
            "close_strength": round(candle["close_strength"], 2),
            "upper_wick_ratio": round(candle["upper_wick_ratio"], 2),
            "breakout": breakout,
            "structure": structure,
        }

    def _combine_timeframes(self, m15: dict, h1: dict, h4: dict) -> dict:
        statuses = {"15m": m15.get("status", "NEUTRAL"), "1h": h1.get("status", "NEUTRAL"), "4h": h4.get("status", "NEUTRAL")}
        bull_score = m15.get("bull_score", 0) * 0.2 + h1.get("bull_score", 0) * 0.35 + h4.get("bull_score", 0) * 0.45
        bear_score = m15.get("bear_score", 0) * 0.2 + h1.get("bear_score", 0) * 0.35 + h4.get("bear_score", 0) * 0.45

        h1_bull = "BULL" in statuses["1h"]
        h4_bull = "BULL" in statuses["4h"]
        h1_bear = "BEAR" in statuses["1h"]
        h4_bear = "BEAR" in statuses["4h"]
        m15_bear = "BEAR" in statuses["15m"]

        if h4_bear or (h1_bear and m15_bear):
            return {
                "direction": "BEARISH",
                "strength": "STRONG" if h4_bear and h1_bear else "NORMAL",
                "confidence": max(h4.get("confidence", 50), h1.get("confidence", 50)),
                "bull_score": round(bull_score, 1),
                "bear_score": round(bear_score, 1),
                "reason": f"Bear priority: {statuses}",
            }

        if h1_bull and h4_bull and not m15_bear:
            return {
                "direction": "BULLISH",
                "strength": "STRONG" if "STRONG" in statuses["4h"] else "NORMAL",
                "confidence": max(h1.get("confidence", 50), h4.get("confidence", 50)),
                "bull_score": round(bull_score, 1),
                "bear_score": round(bear_score, 1),
                "reason": f"Accepted bull candidate: {statuses}",
            }

        if h1_bull and not h4_bear:
            return {
                "direction": "MIXED",
                "strength": "RECOVERY",
                "confidence": 55,
                "bull_score": round(bull_score, 1),
                "bear_score": round(bear_score, 1),
                "reason": f"Recovery candidate, not accepted yet: {statuses}",
            }

        return {
            "direction": "NEUTRAL",
            "strength": "NEUTRAL",
            "confidence": 50,
            "bull_score": round(bull_score, 1),
            "bear_score": round(bear_score, 1),
            "reason": f"No accepted direction: {statuses}",
        }

    def _calculate_acceptance(self, frames: dict, combined: dict) -> dict:
        leader_score, leader_detail = self._score_leadership(frames)
        breakout_score, breakout_detail = self._score_breakout(frames)
        volume_score, volume_detail, distribution_flags = self._score_volume_quality(frames)
        follow_score, follow_detail = self._score_follow_through(frames)
        external_score, external_detail = self._score_external_context()
        news_score, news_detail, news_risk = self._score_news_context()
        ai_score, ai_detail = self._score_ai_models()
        advisor_score, advisor_detail = self._score_static_advisors()

        rejection_penalty = min(10, distribution_flags * 4)
        if combined.get("direction") == "BEARISH":
            rejection_penalty += 10
        if news_risk:
            rejection_penalty += 8

        score = leader_score + breakout_score + volume_score + follow_score + external_score + news_score + ai_score + advisor_score - rejection_penalty
        score = max(0, min(100, score))
        fake_rally = (
            breakout_score < 8
            and volume_score < 9
            and leader_score < 14
            and combined.get("direction") != "BEARISH"
        ) or distribution_flags >= 3 or (news_risk and score < self.MIN_BULL_ACCEPTANCE + 6)

        return {
            "score": round(score, 1),
            "leader_score": round(leader_score, 1),
            "breakout_score": round(breakout_score, 1),
            "volume_score": round(volume_score, 1),
            "follow_score": round(follow_score, 1),
            "external_score": round(external_score, 1),
            "news_score": round(news_score, 1),
            "ai_score": round(ai_score, 1),
            "advisor_score": round(advisor_score, 1),
            "rejection_penalty": round(rejection_penalty, 1),
            "fake_rally": fake_rally,
            "detail": " | ".join([leader_detail, breakout_detail, volume_detail, follow_detail, external_detail, news_detail, ai_detail, advisor_detail]),
        }

    def _score_leadership(self, frames: dict) -> tuple[float, str]:
        h1 = frames["1h"].get("symbols", {})
        h4 = frames["4h"].get("symbols", {})
        score = 0.0
        bull_leaders = 0
        core_confirm = 0

        for symbol in self.LEADERS:
            h1_bull = h1.get(symbol, {}).get("status") == "BULLISH"
            h4_bull = h4.get(symbol, {}).get("status") == "BULLISH"
            h4_bear = h4.get(symbol, {}).get("status") == "BEARISH"
            if h1_bull and h4_bull:
                bull_leaders += 1
                score += 4.2
            elif h1_bull and not h4_bear:
                score += 2.0
            if symbol in self.CORE_LEADERS and h1_bull and not h4_bear:
                core_confirm += 1

        if bull_leaders >= 3:
            score += 4
        if core_confirm == 2:
            score += 4
        elif core_confirm == 0:
            score -= 4

        return max(0, min(25, score)), f"Leadership {bull_leaders}/5 core={core_confirm}/2"

    def _score_breakout(self, frames: dict) -> tuple[float, str]:
        symbols = frames["1h"].get("symbols", {})
        score = 0.0
        accepted = 0
        for symbol, weight in [("BTC/USDT", 6), ("ETH/USDT", 5), ("BNB/USDT", 3), ("SOL/USDT", 3), ("XRP/USDT", 3)]:
            br = symbols.get(symbol, {}).get("breakout", {})
            if br.get("accepted"):
                score += weight
                accepted += 1
            elif br.get("near"):
                score += weight * 0.35
        return min(20, score), f"Breakout accepted={accepted}/5"

    def _score_volume_quality(self, frames: dict) -> tuple[float, str, int]:
        symbols = frames["1h"].get("symbols", {})
        score = 0.0
        quality = 0
        distribution = 0
        for symbol in self.LEADERS:
            r = symbols.get(symbol, {})
            vr = r.get("volume_ratio", 1.0)
            close_strength = r.get("close_strength", 0.5)
            upper = r.get("upper_wick_ratio", 0.0)
            if vr >= 1.2 and close_strength >= 0.58 and upper < 0.42:
                quality += 1
                score += 4
            elif vr >= 1.0 and close_strength >= 0.52:
                score += 2
            if vr >= 1.4 and upper >= 0.45:
                distribution += 1
        return min(20, score), f"Volume quality={quality}/5 distribution={distribution}", distribution

    def _score_follow_through(self, frames: dict) -> tuple[float, str]:
        symbols_15 = frames["15m"].get("symbols", {})
        symbols_1h = frames["1h"].get("symbols", {})
        score = 0.0
        confirmed = 0
        for symbol in self.LEADERS:
            s15 = symbols_15.get(symbol, {})
            s1h = symbols_1h.get(symbol, {})
            if s15.get("structure", {}).get("higher_lows") and s1h.get("structure", {}).get("higher_lows"):
                score += 2.0
                confirmed += 1
            if s1h.get("breakout", {}).get("retest_hold"):
                score += 2.0
            if s15.get("status") == "BEARISH":
                score -= 1.5
        return max(0, min(10, score)), f"Follow-through={confirmed}/5"

    def _score_external_context(self) -> tuple[float, str]:
        score = 5.0
        details = []
        try:
            if self._external_client and hasattr(self._external_client, "get_global_data"):
                data = self._external_client.get_global_data() or {}
                mc = float(data.get("market_cap_change", 0) or 0)
                dominance = float(data.get("btc_dominance", 0) or 0)
                total_vol = float(data.get("total_volume", 0) or 0)
                if mc > 1.0:
                    score += 3
                elif mc < -1.0:
                    score -= 3
                if total_vol > 80_000_000_000:
                    score -= 5
                elif total_vol < 50_000_000_000:
                    score += 5
                details.append(f"MC:{mc:+.2f}% Dom:{dominance:.1f}")
            else:
                details.append("External neutral")
        except Exception:
            details.append("External error")

        try:
            if self._external_client and hasattr(self._external_client, "get_market_sentiment_global"):
                fng = self._external_client.get_market_sentiment_global() or {}
                fg = float(fng.get("value", 50) or 50)
                if 40 <= fg <= 70:
                    score += 1
                elif fg > 82:
                    score -= 2
                elif fg < 25:
                    score -= 1
                details.append(f"FG:{fg:.0f}")
        except Exception:
            pass
        return max(0, min(10, score)), "External " + ", ".join(details)

    def _score_news_context(self) -> tuple[float, str, bool]:
        analyzer = self._get_news_analyzer()
        if not analyzer:
            return 0.0, "News neutral(no storage)", False

        score = 0.0
        total_news = 0
        positive = 0
        negative = 0
        avoid = 0
        details = []

        for symbol in self.LEADERS:
            try:
                sentiment = analyzer.get_news_sentiment(symbol, hours=24) or {}
                if not sentiment:
                    continue

                total = int(sentiment.get("total", sentiment.get("news_count_24h", 0)) or 0)
                pos = int(sentiment.get("positive", sentiment.get("positive_news_count", 0)) or 0)
                neg = int(sentiment.get("negative", sentiment.get("negative_news_count", 0)) or 0)
                news_score = float(sentiment.get("news_score", sentiment.get("news_sentiment_avg", 0)) or 0)

                total_news += total
                positive += pos
                negative += neg
                if total >= 2:
                    score += max(-2.0, min(2.0, news_score / 4.0))
                if analyzer.should_avoid_coin(symbol, hours=24):
                    avoid += 1
            except Exception:
                details.append(f"{symbol}:err")

        if total_news == 0:
            return 0.0, "News neutral(no recent news)", False

        if positive >= negative * 2 and positive >= 3:
            score += 2
        if negative >= positive * 2 and negative >= 3:
            score -= 4

        core_negative = 0
        for symbol in self.CORE_LEADERS:
            try:
                sentiment = analyzer.get_news_sentiment(symbol, hours=24) or {}
                total = int(sentiment.get("total", sentiment.get("news_count_24h", 0)) or 0)
                neg = int(sentiment.get("negative", sentiment.get("negative_news_count", 0)) or 0)
                if total >= 3 and neg / max(total, 1) >= 0.65:
                    core_negative += 1
            except Exception:
                pass

        news_risk = avoid >= 2 or core_negative >= 1 or (negative >= 4 and negative > positive)
        details.append(f"pos={positive} neg={negative} total={total_news} avoid={avoid}")
        return max(-8.0, min(6.0, score)), "News " + ", ".join(details), news_risk

    def _score_ai_models(self) -> tuple[float, str]:
        if not self.dl_client or not hasattr(self.dl_client, "_models"):
            return 4.0, "AI neutral(no client)"

        btc_df = self._fetch_df("BTC/USDT", "1h", 80)
        if btc_df is None or len(btc_df) < 30:
            return 4.0, "AI neutral(no data)"

        analysis = self._ai_analysis_payload(btc_df)
        market_sentiment = self._market_sentiment_payload()
        news_payload = self._news_payload("BTC/USDT")
        if news_payload:
            analysis["news"] = news_payload

        model_names = [
            "volume_pred",
            "sentiment",
            "liquidity",
            "smart_money",
            "crypto_news",
            "anomaly",
            "candle_expert",
            "pattern",
        ]
        votes = 0
        bears = 0
        total = 0
        details = []

        try:
            if hasattr(self.dl_client, "get_advice"):
                advice = self.dl_client.get_advice(
                    rsi=analysis["rsi"],
                    macd=analysis["macd"],
                    volume_ratio=analysis["volume_ratio"],
                    price_momentum=analysis["price_momentum"],
                    market_sentiment=market_sentiment,
                    candle_analysis=analysis,
                    analysis_data=analysis,
                    action="BUY",
                )
                for name in model_names:
                    value = advice.get(name, "N/A")
                    if value == "N/A":
                        continue
                    total += 1
                    if "Bullish" in value:
                        votes += 1
                    elif "Bearish" in value:
                        bears += 1
                    details.append(f"{name}:{value}")

                if total:
                    points = (votes / total) * 12
                    points -= min(5, bears * 1.5)
                    if total < 4:
                        points = min(points, 5)
                    return max(0, min(12, points)), f"AI {votes}/{total} bear={bears} " + ",".join(details)
        except Exception as e:
            details.append(f"advice:err")

        for name in model_names:
            try:
                model = self.dl_client._models.get(name)
                if not model:
                    continue
                score = self._predict_cached_model_score(model, name, analysis, market_sentiment)
                if score is None:
                    details.append(f"{name}:err")
                    continue
                total += 1
                if score > 0.55:
                    votes += 1
                    details.append(f"{name}:Y{score:.2f}")
                elif score < 0.40:
                    bears += 1
                    details.append(f"{name}:N{score:.2f}")
                else:
                    details.append(f"{name}:M{score:.2f}")
            except Exception:
                details.append(f"{name}:err")

        if total == 0:
            return 4.0, "AI neutral(no models)"

        points = (votes / total) * 12
        points -= min(5, bears * 1.5)
        if total < 4:
            points = min(points, 5)

        return max(0, min(12, points)), f"AI {votes}/{total} bear={bears} " + ",".join(details)

    def _score_static_advisors(self) -> tuple[float, str]:
        score = 0.0
        details = []
        btc_df = self._fetch_df("BTC/USDT", "1h", 80)
        try:
            if self._ted and btc_df is not None:
                ted = self._ted.detect_trend_birth(btc_df)
                if ted.get("trend") == "BULLISH" and ted.get("confidence", 0) >= 55:
                    score += 5
                elif ted.get("trend") == "BEARISH":
                    score -= 4
                details.append(f"TED:{ted.get('trend')}/{ted.get('confidence')}")
        except Exception:
            details.append("TED:error")
        try:
            if self._mtf and btc_df is not None:
                candles = btc_df.to_dict("records")
                mtf = self._mtf.analyze_bottom(
                    candles_5m=None,
                    candles_15m=None,
                    candles_1h=candles,
                    current_price=float(btc_df["close"].iloc[-1]),
                    macro_status=self._last_status,
                )
                if mtf.get("is_bottom") and mtf.get("confidence", 0) >= 60:
                    score += 4
                details.append(f"MTF:{mtf.get('confidence', 0):.0f}")
        except Exception:
            details.append("MTF:error")
        try:
            if self._volume_engine and btc_df is not None:
                volumes = btc_df["volume"].tolist()
                quality = self._volume_engine.get_volume_quality_score("BTC/USDT", volumes)
                if quality >= 65:
                    score += 3
                elif quality < 35:
                    score -= 2
                details.append(f"VolQ:{quality:.0f}")
        except Exception:
            details.append("VolQ:error")
        return max(0, min(5, score)), "Advisors " + ", ".join(details)

    def _ai_feature_row(self, df: pd.DataFrame):
        close = df["close"]
        volume = df["volume"]
        row = pd.DataFrame([{
            "c": float(close.iloc[-1]),
            "v": float(volume.iloc[-1]),
            "rsi": self._calc_rsi(close),
            "volume_ratio": float(volume.iloc[-1] / volume.tail(20).mean()) if volume.tail(20).mean() > 0 else 1.0,
            "price_change": float(close.pct_change().iloc[-1] * 100),
        }])
        return row.values

    def _ai_analysis_payload(self, df: pd.DataFrame) -> dict:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        current_volume = float(volume.iloc[-1])
        avg20 = float(volume.tail(20).mean()) if len(volume) >= 20 else current_volume
        avg50 = float(volume.tail(50).mean()) if len(volume) >= 50 else avg20
        price_change_1h = float(close.pct_change().iloc[-1] * 100)
        price_change_4h = float((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100) if len(close) >= 5 and close.iloc[-5] else 0.0
        price_change_24h = float((close.iloc[-1] - close.iloc[-25]) / close.iloc[-25] * 100) if len(close) >= 25 and close.iloc[-25] else 0.0
        macd_hist = self._macd_hist(close)
        atr = float((high - low).tail(14).mean()) if len(df) >= 14 else 0.0
        volume_ratio = current_volume / avg20 if avg20 > 0 else 1.0
        volume_ratio_4h = current_volume / avg50 if avg50 > 0 else 1.0
        candle = self._last_candle_quality(df)
        return {
            "volume": current_volume,
            "volume_avg_1h": avg20,
            "volume_avg_4h": avg50,
            "volume_avg_24h": avg50,
            "volume_ratio": volume_ratio,
            "volume_ratio_4h": volume_ratio_4h,
            "volume_ratio_24h": volume_ratio_4h,
            "volume_trend": 1.2 if volume.tail(3).mean() > avg20 else 0.8,
            "volume_volatility": float(volume.tail(20).std() / avg20) if avg20 > 0 and len(volume) >= 20 else 0.0,
            "price_change_1h": price_change_1h,
            "price_change_4h": price_change_4h,
            "price_change_24h": price_change_24h,
            "price_momentum": price_change_4h,
            "rsi": self._calc_rsi(close),
            "macd": float(macd_hist.iloc[-1]),
            "macd_diff": float(macd_hist.iloc[-1]),
            "atr": atr,
            "bid_ask_spread": 0.0,
            "volume_momentum": float((volume.tail(3).mean() / avg20 - 1) * 100) if avg20 > 0 else 0.0,
            "volume_acceleration": float((volume.tail(3).mean() / volume.tail(10).mean() - 1) * 100) if len(volume) >= 10 and volume.tail(10).mean() > 0 else 0.0,
            "anomaly_score": max(0.0, min(100.0, (volume_ratio - 1.0) * 30 + abs(price_change_1h) * 12)),
            "statistical_outliers": 1 if abs(price_change_1h) > 3 else 0,
            "pattern_anomalies": 1 if candle["upper_wick_ratio"] > 0.55 and price_change_1h > 0 else 0,
            "behavioral_anomalies": 1 if volume_ratio > 2.5 and candle["close_strength"] < 0.45 else 0,
            "volume_anomalies": 1 if volume_ratio > 2.0 else 0,
            "harmonic_patterns_score": 0.0,
            "elliott_wave_signals": 0.0,
            "fractal_patterns": 0.0,
            "cycle_patterns": 0.0,
            "momentum_patterns": price_change_4h,
        }

    def _market_sentiment_payload(self) -> dict:
        fg = 50.0
        try:
            if self._external_client and hasattr(self._external_client, "get_market_sentiment_global"):
                data = self._external_client.get_market_sentiment_global() or {}
                fg = float(data.get("value", 50) or 50)
        except Exception:
            pass
        return {
            "fear_greed": fg,
            "social_volume": 1000,
            "positive_ratio": 0.33,
            "negative_ratio": 0.33,
            "neutral_ratio": 0.34,
            "trending_score": 0,
            "news_sentiment": 0,
        }

    def _news_payload(self, symbol: str) -> dict:
        analyzer = self._get_news_analyzer()
        if not analyzer:
            return {}
        try:
            sentiment = analyzer.get_news_sentiment(symbol, hours=24) or {}
            if not sentiment:
                return {}
            total = int(sentiment.get("total", sentiment.get("news_count_24h", 0)) or 0)
            positive = int(sentiment.get("positive", sentiment.get("positive_news_count", 0)) or 0)
            negative = int(sentiment.get("negative", sentiment.get("negative_news_count", 0)) or 0)
            neutral = max(0, total - positive - negative)
            score = float(sentiment.get("news_score", sentiment.get("news_sentiment_avg", 0)) or 0)
            return {
                "news_count_24h": total,
                "total": total,
                "positive_news_count": positive,
                "positive": positive,
                "negative_news_count": negative,
                "negative": negative,
                "neutral_news_count": neutral,
                "neutral": neutral,
                "news_sentiment_avg": score,
                "news_score": score,
            }
        except Exception:
            return {}

    def _predict_cached_model_score(self, model, name: str, analysis: dict, market_sentiment: dict) -> Optional[float]:
        try:
            if hasattr(model, "predict_proba"):
                if name == "crypto_news":
                    payload = {"news": analysis.get("news", {})}
                    data = pd.DataFrame([[
                        payload["news"].get("news_count_24h", payload["news"].get("total", 0)),
                        payload["news"].get("positive_news_count", payload["news"].get("positive", 0)),
                        payload["news"].get("negative_news_count", payload["news"].get("negative", 0)),
                        payload["news"].get("neutral_news_count", payload["news"].get("neutral", 0)),
                        payload["news"].get("news_sentiment_avg", payload["news"].get("news_score", 0)),
                        payload["news"].get("positive_news_count", payload["news"].get("positive", 0)) / (payload["news"].get("negative_news_count", payload["news"].get("negative", 0)) + 0.001),
                        (payload["news"].get("positive_news_count", payload["news"].get("positive", 0)) - payload["news"].get("negative_news_count", payload["news"].get("negative", 0))) / (payload["news"].get("news_count_24h", payload["news"].get("total", 0)) + 0.001),
                        1 if payload["news"].get("news_count_24h", payload["news"].get("total", 0)) > 5 else 0,
                        1 if payload["news"].get("positive_news_count", payload["news"].get("positive", 0)) > payload["news"].get("negative_news_count", payload["news"].get("negative", 0)) * 2 else 0,
                        1 if payload["news"].get("negative_news_count", payload["news"].get("negative", 0)) > payload["news"].get("positive_news_count", payload["news"].get("positive", 0)) * 2 else 0,
                    ]])
                    return float(model.predict_proba(data)[0][1])
            return None
        except Exception:
            return None

    def _fetch_df(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                return None
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna().reset_index(drop=True)
            df["o"] = df["open"]
            df["h"] = df["high"]
            df["l"] = df["low"]
            df["c"] = df["close"]
            df["v"] = df["volume"]
            return df if len(df) >= 20 else None
        except Exception as e:
            print(f"⚠️ {symbol} {timeframe}: {e}")
            return None

    def _breakout_acceptance(self, df: pd.DataFrame) -> dict:
        if len(df) < 25:
            return {"accepted": False, "near": False, "retest_hold": False, "score": 0}
        prior_high = float(df["high"].iloc[-24:-3].max())
        prior_low = float(df["low"].iloc[-24:-3].min())
        close = float(df["close"].iloc[-1])
        low = float(df["low"].iloc[-1])
        candle = self._last_candle_quality(df)
        accepted = close > prior_high * 1.001 and candle["close_strength"] >= 0.58 and candle["upper_wick_ratio"] < 0.42
        near = close > prior_high * 0.997
        retest_hold = low <= prior_high * 1.003 and close >= prior_high * 0.998 and close > prior_low
        score = 0
        if accepted:
            score += 10
        elif near:
            score += 4
        if retest_hold:
            score += 5
        return {"accepted": accepted, "near": near, "retest_hold": retest_hold, "prior_high": prior_high, "score": min(12, score)}

    def _structure_score(self, df: pd.DataFrame) -> dict:
        lows = df["low"].tail(12).tolist()
        highs = df["high"].tail(12).tolist()
        higher_lows = len(lows) >= 8 and min(lows[-4:]) > min(lows[-8:-4])
        higher_highs = len(highs) >= 8 and max(highs[-4:]) > max(highs[-8:-4])
        lower_lows = len(lows) >= 8 and min(lows[-4:]) < min(lows[-8:-4])
        lower_highs = len(highs) >= 8 and max(highs[-4:]) < max(highs[-8:-4])
        bull = 0
        bear = 0
        if higher_lows:
            bull += 6
        if higher_highs:
            bull += 5
        if lower_lows:
            bear += 6
        if lower_highs:
            bear += 5
        return {
            "bull": bull,
            "bear": bear,
            "higher_lows": higher_lows,
            "higher_highs": higher_highs,
            "lower_lows": lower_lows,
            "lower_highs": lower_highs,
        }

    def _distribution_risk(self, df: pd.DataFrame, volume_ratio: float) -> float:
        risk = 0.0
        for _, row in df.tail(4).iterrows():
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            open_ = float(row["open"])
            rng = high - low
            if rng <= 0:
                continue
            upper = high - max(open_, close)
            body = abs(close - open_)
            close_strength = (close - low) / rng
            if upper / rng > 0.45 and close_strength < 0.55:
                risk += 4
            if volume_ratio > 1.5 and upper > body * 1.8:
                risk += 4
        return min(14, risk)

    @staticmethod
    def _last_candle_quality(df: pd.DataFrame) -> dict:
        row = df.iloc[-1]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        open_ = float(row["open"])
        rng = max(high - low, 1e-12)
        body = abs(close - open_)
        upper = high - max(open_, close)
        lower = min(open_, close) - low
        return {
            "close_strength": (close - low) / rng,
            "body_ratio": body / rng,
            "upper_wick_ratio": upper / rng,
            "lower_wick_ratio": lower / rng,
        }

    @staticmethod
    def _calc_rsi(prices: pd.Series, period: int = 14) -> float:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        value = (100 - (100 / (1 + rs))).iloc[-1]
        return float(value) if not pd.isna(value) else 50.0

    @staticmethod
    def _macd_hist(prices: pd.Series) -> pd.Series:
        macd = prices.ewm(span=12, adjust=False).mean() - prices.ewm(span=26, adjust=False).mean()
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd - signal

    def _finalize(self, status: str, snapshot: dict) -> str:
        acceptance = snapshot["acceptance"]
        combined = snapshot["combined"]
        self._last_status = status
        self._last_check_time = time.time()
        self._last_analysis = snapshot["state"]
        self._last_analysis_time = time.time()
        self._status_history.append((time.time(), status, acceptance.get("score", 0)))
        self._status_history = self._status_history[-50:]
        self._display_info = {
            "status": status,
            "total_bull": combined.get("bull_score", 0),
            "total_bear": combined.get("bear_score", 0),
            "detail": f"{combined.get('reason', '')} | Acceptance:{acceptance.get('score', 0):.0f} | {acceptance.get('detail', '')}",
        }
        return status

    def _reset_recovery(self, failed: bool) -> None:
        if failed:
            self._recovery_fail_count += 1
        else:
            self._recovery_fail_count = 0
        self._recovery_started_at = None
        self._recovery_success_count = 0

    def _load_component(self, module_name: str, class_name: str):
        try:
            module = __import__(module_name, fromlist=[class_name])
            return getattr(module, class_name)()
        except Exception:
            return None

    @staticmethod
    def _load_external_client():
        try:
            from external_apis import get_global_external_client
            return get_global_external_client()
        except Exception:
            return None

    def _load_news_analyzer(self):
        try:
            from news_analyzer import NewsAnalyzer
            return NewsAnalyzer(storage=self.db)
        except Exception:
            return None

    def _get_news_analyzer(self):
        try:
            if self._news_analyzer and getattr(self._news_analyzer, "storage", None) is self.db:
                return self._news_analyzer
            if not self.db:
                return self._news_analyzer
            self._news_analyzer = self._load_news_analyzer()
            return self._news_analyzer
        except Exception:
            return None

    def _get_historical_status(self, hours_ago: float = 2) -> Optional[str]:
        try:
            if not self.db:
                return None
            raw = self.db.load_setting("bot_status")
            if not raw:
                return None
            data = json.loads(raw)
            macro = data.get("macro_status", "")
            saved_time = data.get("time", "")
            if not macro or not saved_time:
                return None
            now = datetime.now()
            saved_dt = datetime.strptime(saved_time, "%H:%M:%S").replace(year=now.year, month=now.month, day=now.day)
            diff = (now - saved_dt).total_seconds()
            if diff < 0:
                saved_dt -= timedelta(days=1)
                diff = (now - saved_dt).total_seconds()
            return macro if 0 <= diff <= hours_ago * 3600 else None
        except Exception:
            return None

    @staticmethod
    def _empty_state() -> dict:
        empty = {
            "status": "NEUTRAL",
            "confidence": 50,
            "bull_score": 0,
            "bear_score": 0,
            "bull_count": 0,
            "bear_count": 0,
            "symbols": {},
            "reason": "No data",
        }
        return {
            "15m": empty.copy(),
            "1h": empty.copy(),
            "4h": empty.copy(),
            "combined": {
                "direction": "NEUTRAL",
                "strength": "NEUTRAL",
                "confidence": 50,
                "bull_score": 0,
                "bear_score": 0,
                "reason": "No data",
            },
            "acceptance": {"score": 0, "fake_rally": False, "detail": "No data"},
        }
