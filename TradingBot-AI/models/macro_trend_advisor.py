"""
📊 Macro Trend Advisor - Simple & Clean
"""

import time
import json
from datetime import datetime
from typing import Optional

import pandas as pd


class MacroTrendAdvisor:
    """
    Macro status engine - Simple & Reliable
    يقرأ BTC + ETH + SOL + BNB
    3 أو 4 صاعدين → BULL
    2 محايدين     → NEUT
    1 أو 0        → BEAR

    Public API:
    - get_macro_status() -> str
    - analyze_market_state() -> dict
    - can_aim_high() -> bool
    - get_display_info() -> dict
    - invalidate_cache() -> None
    """

    LEADERS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT"]
    CACHE_DURATION = 90  # ثواني

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

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    def get_macro_status(self) -> str:
        if not self.exchange:
            return "⚪ SIDEWAYS"

        now = time.time()
        if now - self._last_check_time < self.CACHE_DURATION:
            return self._last_status

        try:
            result = self._analyze_all()
            status = self._resolve_status(result)
            self._finalize(status, result)
            return status
        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor error: {e}")
            return self._last_status or "⚪ SIDEWAYS"

    def can_aim_high(self) -> bool:
        return "BULL" in self.get_macro_status()

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
            result = self._analyze_all()
            status = self._resolve_status(result)
            self._finalize(status, result)
            result["combined"] = self._combined
            self._last_analysis = result
            self._last_analysis_time = time.time()
            return result
        except Exception as e:
            print(f"⚠️ analyze_market_state error: {e}")
            return self._empty_state()

    # ─────────────────────────────────────────────
    # Core Logic
    # ─────────────────────────────────────────────

    def _analyze_all(self) -> dict:
        """يحلل الـ 4 عملات ويرجع النتيجة"""
        results = {}
        bull_count = 0
        bear_count = 0

        for symbol in self.LEADERS:
            df = self._fetch_df(symbol, "1h", 80)
            if df is None or len(df) < 30:
                results[symbol] = {"status": "NEUTRAL", "reason": "no data"}
                continue

            analysis = self._analyze_symbol(symbol, df)
            results[symbol] = analysis

            if analysis["status"] == "BULLISH":
                bull_count += 1
            elif analysis["status"] == "BEARISH":
                bear_count += 1

        neutral_count = len(self.LEADERS) - bull_count - bear_count

        return {
            "symbols": results,
            "bull_count": bull_count,
            "bear_count": bear_count,
            "neutral_count": neutral_count,
            "total": len(self.LEADERS),
        }

    def _analyze_symbol(self, symbol: str, df: pd.DataFrame) -> dict:
        """
        يحلل عملة واحدة:
        - اتجاه السعر (EMA)
        - حجم التداول
        - جودة الكاندل (حقيقي vs وهمي)
        """
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ── السعر والـ EMA ──
        price = float(close.iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])

        price_above_ema21 = price > ema21
        price_above_ema50 = price > ema50
        ema21_above_ema50 = ema21 > ema50

        # تغيير السعر آخر 10 كاندل
        prev_price = float(close.iloc[-11]) if len(close) > 11 else price
        change_10 = ((price - prev_price) / prev_price * 100) if prev_price > 0 else 0

        # ── الحجم ──
        avg_vol_20 = float(volume.tail(20).mean())
        recent_vol = float(volume.tail(3).mean())
        volume_ratio = recent_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
        volume_confirms = volume_ratio >= 1.15  # حجم داعم

        # ── جودة الكاندل (حقيقي vs وهمي) ──
        last = df.iloc[-1]
        candle_range = float(last["high"]) - float(last["low"])
        candle_range = max(candle_range, 1e-12)
        body = abs(float(last["close"]) - float(last["open"]))
        upper_wick = float(last["high"]) - max(float(last["open"]), float(last["close"]))
        close_strength = (float(last["close"]) - float(last["low"])) / candle_range

        # كاندل حقيقي: جسم كبير + إغلاق قوي + ذيل علوي صغير
        real_candle = (
            body / candle_range >= 0.4
            and close_strength >= 0.55
            and upper_wick / candle_range < 0.45
        )

        # كاندل وهمي: ذيل علوي كبير مع حجم عالي = توزيع
        fake_signal = (
            upper_wick / candle_range > 0.55
            and close_strength < 0.35
            and volume_ratio < 1.3
        )

        # ── كشف البامب ودامب ──
        recent_change30 = float(close.iloc[-1] - close.iloc[-30]) / float(close.iloc[-30]) * 100 if len(close) > 30 else 0
        prev_high40 = float(high.iloc[-40:-5].max()) if len(high) > 40 else float(high.max())
        pump_then_dump = (
            prev_high40 > float(close.iloc[-1]) * 1.05
            and recent_change30 < -3.0
        )

        # ── التحديد النهائي ──
        bull_points = 0
        bear_points = 0

        # السعر والـ EMA (نظام نقاط صارم: المتوسطات تعطي 3 نقاط كحد أقصى)
        if price_above_ema21 and price_above_ema50:
            bull_points += 3 # تم رفعها من 2 لتعزيز أهمية التمركز فوق المتوسطات
            if ema21_above_ema50: bull_points += 1 # الإجمالي 4 إذا كان الترتيب مثالياً
        elif price_above_ema21:
            bull_points += 1

        if not price_above_ema21 and not price_above_ema50:
            bear_points += 2
            if not ema21_above_ema50: bear_points += 1
        elif not price_above_ema21:
            bear_points += 1

        # الزخم
        if change_10 > 2.0:
            bull_points += 2
        elif change_10 > 0.8:
            bull_points += 1
        elif change_10 < -2.0:
            bear_points += 2
        elif change_10 < -0.8:
            bear_points += 1

        # الحجم + الكاندل
        if volume_confirms and real_candle:
            bull_points += 2  # صعود حقيقي
        elif fake_signal:
            bear_points += 2  # صعود وهمي
        elif volume_confirms and change_10 > 0:
            bull_points += 1
        elif volume_ratio < 0.7 and change_10 > 0.5:
            bear_points += 2  # صعود بدون حجم = وهمي

        # التحديد
        if fake_signal:
            bear_points += 1  # عقوبة إضافية للوهمي

        if pump_then_dump:
            status = "BEARISH"
        elif fake_signal:
            status = "NEUTRAL" if bull_points > bear_points else "BEARISH"
        elif bull_points >= bear_points + 3 and bull_points >= 5:
            status = "BULLISH"
        elif bear_points >= bull_points + 3 and bear_points >= 5:
            status = "BEARISH"
        else:
            status = "NEUTRAL"

        return {
            "status": status,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "price": price,
            "change_10": round(change_10, 2),
            "volume_ratio": round(volume_ratio, 2),
            "real_candle": real_candle,
            "fake_signal": fake_signal,
            "close_strength": round(close_strength, 2),
            "reason": f"{status} bull={bull_points} bear={bear_points} vol={volume_ratio:.1f}x candle={'real' if real_candle else 'fake' if fake_signal else 'neutral'}",
        }

    def _resolve_status(self, result: dict) -> str:
        """
        3/5 صاعدين + زخم إيجابي + حجم داعم → BULL
        3/5 هابطين + زخم سلبي              → BEAR
        غير ذلك                            → SIDEWAYS
        Sticky: 3 مرات متتالية للتأكيد
        """
        bull    = result["bull_count"]
        bear    = result["bear_count"]
        symbols = result.get("symbols", {})

        # مجموع الزخم والحجم للـ 5 عملات
        momentums    = [d.get("change_10",    0.0) for d in symbols.values()]
        volumes      = [d.get("volume_ratio", 1.0) for d in symbols.values()]
        avg_momentum = sum(momentums) / len(momentums) if momentums else 0.0
        avg_volume   = sum(volumes)   / len(volumes)   if volumes   else 1.0

        # القرار
        if bull >= 3 and avg_momentum > 0.3 and avg_volume >= 1.1:
            new_status = "🟢 BULL_MARKET" if bull >= 4 else "🟢 MILD_BULL"
        elif bear >= 3 and avg_momentum < -0.3:
            new_status = "🔴 BEAR_MARKET" if bear >= 4 else "🔴 MILD_BEAR"
        else:
            new_status = "⚪ SIDEWAYS"

        # Sticky: 3 مرات متتالية
        if new_status != self._last_status:
            if new_status == getattr(self, "_pending_status", None):
                self._pending_count = getattr(self, "_pending_count", 0) + 1
                if self._pending_count >= 2:
                    self._pending_status = None
                    self._pending_count  = 0
                    return new_status
                return self._last_status
            else:
                self._pending_status = new_status
                self._pending_count  = 1
                return self._last_status

        self._pending_status = None
        self._pending_count  = 0
        return new_status

    # ─────────────────────────────────────────────
    # Finalize & Save to DB
    # ─────────────────────────────────────────────

    def _finalize(self, status: str, result: dict) -> None:
        """يحدث الكاش ويكتب الحالة بالداتابيز"""
        self._last_status = status
        self._last_check_time = time.time()
        self._last_analysis = result
        self._last_analysis_time = time.time()

        bull = result["bull_count"]
        bear = result["bear_count"]
        symbols_summary = {
            s: r.get("status", "NEUTRAL")
            for s, r in result.get("symbols", {}).items()
        }

        # ── combined للتوافق مع meta_buy.py ──
        if bull >= 3:
            direction = "BULLISH"
            strength  = "STRONG" if bull == 4 else "NORMAL"
        elif bear >= 3:
            direction = "BEARISH"
            strength  = "STRONG" if bear == 4 else "NORMAL"
        else:
            direction = "NEUTRAL"
            strength  = "NEUTRAL"

        self._combined = {"direction": direction, "strength": strength}

        self._display_info = {
            "status": status,
            "total_bull": bull,
            "total_bear": bear,
            "combined": self._combined,
            "detail": f"Bull:{bull}/4 Bear:{bear}/4 | {symbols_summary}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # ── الكتابة بالداتابيز (نفس العمود والجدول القديم) ──
        self._save_to_db(status, result)

    def _save_to_db(self, status: str, result: dict) -> None:
        """يكتب حالة السوق بالداتابيز بدون مقارنة"""
        if not self.db:
            return
        try:
            symbols_summary = {
                s: r.get("status", "NEUTRAL")
                for s, r in result.get("symbols", {}).items()
            }
            data = {
                "macro_status": status,
                "time": datetime.now().strftime("%H:%M:%S"),
                "bull_count": result.get("bull_count", 0),
                "bear_count": result.get("bear_count", 0),
                "symbols": symbols_summary,
            }
            self.db.save_setting("bot_status", json.dumps(data))
        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor DB save error: {e}")

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _fetch_df(self, symbol: str, timeframe: str, limit: int):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                return None
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna().reset_index(drop=True)
            return df if len(df) >= 20 else None
        except Exception as e:
            print(f"⚠️ {symbol} {timeframe}: {e}")
            return None

    @staticmethod
    def _empty_state() -> dict:
        return {
            "symbols": {},
            "bull_count": 0,
            "bear_count": 0,
            "neutral_count": 0,
            "total": 0,
        }


