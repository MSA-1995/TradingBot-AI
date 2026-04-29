"""
🎯 Real-time Price Action Analyzer v2
كشف القمم والقيعان بشكل فوري
+ تحليل متعدد الشموع + أنماط الظلال + Shadow+Volume Combo
"""

from datetime import datetime, timezone
from typing import Optional


class RealTimePriceAction:

    # ─── إعدادات المؤشرات ───
    RSI_PERIOD   = 14
    MACD_FAST    = 12
    MACD_SLOW    = 26
    MACD_SIGNAL  = 9

    # ─── عتبات القمة ───
    PEAK_MIN_CONFIDENCE     = 55       # خفضنا من 65 → 55 علشان يكشف أبكر
    PEAK_MIN_SIGNALS        = 2        # خفضنا من 3 → 2
    PEAK_DISTANCE_MAX       = 2.0
    PEAK_DISTANCE_MIN       = 0.5
    PEAK_CONFIDENCE_BOOST   = 20
    UPPER_WICK_THRESHOLD    = 50       # خفضنا من 60 → 50 (أحس أسرع)
    RSI_OVERBOUGHT          = 70
    VOLUME_DROP_THRESHOLD   = 30
    SELL_WALL_RATIO         = 150

    # ─── عتبات القاع ───
    BOTTOM_MIN_CONFIDENCE   = 55       # خفضنا من 65 → 55
    BOTTOM_MIN_SIGNALS      = 2        # خفضنا من 3 → 2
    LOWER_WICK_THRESHOLD    = 50       # خفضنا من 60 → 50
    RSI_OVERSOLD            = 30
    VOLUME_SPIKE_THRESHOLD  = 50
    BUY_WALL_RATIO          = 150
    BOUNCE_THRESHOLD        = 0.5

    # ─── عتبات أنماط الشموع الجديدة ───
    MULTI_CANDLE_LOOKBACK   = 5        # عدد الشموع للتحليل
    SHADOW_BODY_RATIO       = 2.0      # نسبة الظل للجسم (Hammer/Star)
    ENGULFING_MIN_RATIO     = 1.2      # الشمعة الجديدة أكبر بـ 20%
    DOJI_MAX_BODY           = 0.1      # أقصى حجم جسم الدوجي %
    CONSECUTIVE_WICKS       = 2        # عدد الشموع المتتالية بظل
    SHADOW_VOLUME_BOOST     = 15       # بونص ظل + Volume عالي

    # ─── إعدادات عامة ───
    ORDER_BOOK_DEPTH        = 10
    VOLUME_LOOKBACK         = 5
    STALLING_PRICE_CHANGE   = 0.3
    STALLING_MIN_DURATION   = 3
    STALLING_TRACKER_TTL    = 24
    MOMENTUM_LOOKBACK       = 5
    MOMENTUM_THRESHOLD      = 0.5
    MOMENTUM_MIN_AVG        = 0.3
    STOP_LOSS_TIME_LIMIT    = 5

    def __init__(self):
        self.stalling_tracker: dict = {}
        self.rsi_period  = self.RSI_PERIOD
        self.macd_fast   = self.MACD_FAST
        self.macd_slow   = self.MACD_SLOW
        self.macd_signal = self.MACD_SIGNAL

    # ═══════════════════════════════════════════════
    # 🔴 detect_peak - الواجهة اللي يستدعيها meta_advisors
    # ═══════════════════════════════════════════════

    def detect_peak(self, symbol: str, candles: list,
                    current_price: float, analysis: dict = None) -> dict:
        """
        🔴 كشف القمة - يستدعيه meta_advisors للتصويت
        يجمع: analyze_peak_signals + أنماط الشموع المتعددة
        """
        if not candles or len(candles) < 3:
            return {'is_peak': False, 'confidence': 0, 'signals': []}

        analysis = analysis or {}
        highest_price = analysis.get('highest_price', max(c.get('high', 0) for c in candles[-10:]))
        volume_data   = analysis.get('volume_list') or self._extract_volumes(candles)
        order_book    = analysis.get('order_book')

        # أساسي: التحليل القديم
        base = self.analyze_peak_signals(
            symbol, candles, current_price,
            highest_price=highest_price,
            volume_data=volume_data,
            order_book=order_book
        )

        signals    = list(base.get('signals', []))
        confidence = base.get('confidence', 0)

        # ══ جديد: أنماط الشموع المتعددة ══

        # 8. Shooting Star (ظل علوي طويل + جسم صغير)
        star = self._detect_shooting_star(candles[-1])
        if star['detected']:
            signals.append(f"🌠 Shooting Star: {star['strength']:.0f}%")
            confidence += star['strength'] * 0.3

        # 9. Bearish Engulfing (شمعة حمراء تبتلع الخضراء)
        engulf = self._detect_bearish_engulfing(candles)
        if engulf['detected']:
            signals.append(f"🔴 Bearish Engulfing: {engulf['strength']:.0f}%")
            confidence += engulf['strength'] * 0.3

        # 10. Doji عند القمة (تردد)
        doji = self._detect_doji(candles[-1])
        if doji['detected'] and confidence > 20:
            signals.append(f"✝️ Doji at Peak: {doji['strength']:.0f}%")
            confidence += doji['strength'] * 0.2

        # 11. ظلال علوية متتالية (أقوى إشارة!)
        consec = self._detect_consecutive_upper_wicks(candles)
        if consec['detected']:
            signals.append(f"⚡ {consec['count']}x Upper Wicks: {consec['strength']:.0f}%")
            confidence += consec['strength'] * 0.35

        # 12. Shadow + Volume Combo (ظل علوي + Volume عالي)
        combo = self._detect_shadow_volume_combo(candles, volume_data, direction='peak')
        if combo['detected']:
            signals.append(f"💀 Shadow+Volume Peak: {combo['strength']:.0f}%")
            confidence += combo['strength'] * 0.25

        confidence = min(100.0, confidence)

        return {
            'is_peak':    confidence >= self.PEAK_MIN_CONFIDENCE and len(signals) >= self.PEAK_MIN_SIGNALS,
            'confidence': confidence,
            'signals':    signals
        }

    # ═══════════════════════════════════════════════
    # 🟢 detect_bottom - واجهة جديدة متوافقة
    # ═══════════════════════════════════════════════

    def detect_bottom(self, symbol: str, candles: list,
                      current_price: float, analysis: dict = None) -> dict:
        """
        🟢 كشف القاع - نسخة محسنة
        يجمع: analyze_bottom_signals + أنماط الشموع المتعددة
        """
        if not candles or len(candles) < 3:
            return {'is_bottom': False, 'confidence': 0, 'signals': []}

        analysis = analysis or {}
        volume_data = analysis.get('volume_list') or self._extract_volumes(candles)
        order_book  = analysis.get('order_book')

        # أساسي: التحليل القديم
        base = self.analyze_bottom_signals(
            symbol, candles, current_price,
            volume_data=volume_data,
            order_book=order_book
        )

        signals    = list(base.get('signals', []))
        confidence = base.get('confidence', 0)

        # ══ جديد: أنماط الشموع المتعددة ══

        # 8. Hammer (ظل سفلي طويل + جسم صغير فوق)
        hammer = self._detect_hammer(candles[-1])
        if hammer['detected']:
            signals.append(f"🔨 Hammer: {hammer['strength']:.0f}%")
            confidence += hammer['strength'] * 0.3

        # 9. Bullish Engulfing (شمعة خضراء تبتلع الحمراء)
        engulf = self._detect_bullish_engulfing(candles)
        if engulf['detected']:
            signals.append(f"🟢 Bullish Engulfing: {engulf['strength']:.0f}%")
            confidence += engulf['strength'] * 0.3

        # 10. Doji عند القاع (تردد ثم انعكاس)
        doji = self._detect_doji(candles[-1])
        if doji['detected'] and confidence > 20:
            signals.append(f"✝️ Doji at Bottom: {doji['strength']:.0f}%")
            confidence += doji['strength'] * 0.2

        # 11. ظلال سفلية متتالية (أقوى إشارة!)
        consec = self._detect_consecutive_lower_wicks(candles)
        if consec['detected']:
            signals.append(f"⚡ {consec['count']}x Lower Wicks: {consec['strength']:.0f}%")
            confidence += consec['strength'] * 0.35

        # 12. Shadow + Volume Combo (ظل سفلي + Volume عالي)
        combo = self._detect_shadow_volume_combo(candles, volume_data, direction='bottom')
        if combo['detected']:
            signals.append(f"💎 Shadow+Volume Bottom: {combo['strength']:.0f}%")
            confidence += combo['strength'] * 0.25

        confidence = min(100.0, confidence)

        return {
            'is_bottom':  confidence >= self.BOTTOM_MIN_CONFIDENCE and len(signals) >= self.BOTTOM_MIN_SIGNALS,
            'confidence': confidence,
            'signals':    signals
        }

    # ═══════════════════════════════════════════════
    # الواجهات القديمة (محفوظة للتوافق)
    # ═══════════════════════════════════════════════

    def analyze_peak_signals(
        self, symbol: str, candles: list,
        current_price: float, highest_price: Optional[float] = None,
        volume_data=None, order_book=None
    ) -> dict:
        """🔴 كشف القمة السريع - الأصلي"""
        if not candles or len(candles) < 2:
            return {'is_peak': False, 'confidence': 0, 'signals': []}

        signals    = []
        confidence = 0.0

        # 0. المسافة من القمة
        if highest_price:
            distance = ((highest_price - current_price) / highest_price) * 100
            if distance > self.PEAK_DISTANCE_MAX:
                return {'is_peak': False, 'confidence': 0, 'signals': ['Not at peak']}
            if distance < self.PEAK_DISTANCE_MIN:
                signals.append(f"At Peak: {distance:.1f}%")
                confidence += self.PEAK_CONFIDENCE_BOOST

        # 1. Upper Wick
        upper = self._detect_upper_rejection(candles[-1], current_price)
        if upper['detected']:
            signals.append(f"Upper Rejection: {upper['strength']:.0f}%")
            confidence += upper['strength'] * 0.25

        # 2. Volume Drop
        if volume_data:
            vol = self._analyze_volume_drop(volume_data)
            if vol['detected']:
                signals.append(f"Volume Drop: {vol['strength']:.0f}%")
                confidence += vol['strength'] * 0.2

        # 3. Sell Wall
        if order_book:
            ob = self._analyze_sell_wall(order_book)
            if ob['detected']:
                signals.append(f"Sell Wall: {ob['strength']:.0f}%")
                confidence += ob['strength'] * 0.15

        # 4. RSI Overbought
        rsi = self._calculate_rsi(candles)
        if rsi > self.RSI_OVERBOUGHT:
            signals.append(f"RSI: {rsi:.0f}")
            confidence += min(20, (rsi - self.RSI_OVERBOUGHT) * 0.5)

        # 5. MACD Bearish
        if self._calculate_macd(candles)['signal'] == 'bearish':
            signals.append("MACD Bearish")
            confidence += 15

        # 6. Stalling
        stalling = self._detect_stalling(symbol, current_price)
        if stalling['detected']:
            signals.append(f"Stalling: {stalling['duration']:.0f}min")
            confidence += min(20, stalling['duration'] * 3)

        # 7. Momentum Loss
        momentum = self._detect_momentum_loss(candles)
        if momentum['detected']:
            signals.append(f"Momentum Loss: {momentum['strength']:.0f}%")
            confidence += momentum['strength'] * 0.2

        self._cleanup_stalling_tracker()
        confidence = min(100.0, confidence)

        return {
            'is_peak':    confidence >= self.PEAK_MIN_CONFIDENCE and len(signals) >= self.PEAK_MIN_SIGNALS,
            'confidence': confidence,
            'signals':    signals
        }

    def analyze_bottom_signals(
        self, symbol: str, candles: list,
        current_price: float,
        volume_data=None, order_book=None
    ) -> dict:
        """🟢 كشف القاع السريع - الأصلي"""
        if not candles or len(candles) < 2:
            return {'is_bottom': False, 'confidence': 0, 'signals': []}

        signals    = []
        confidence = 0.0

        # 1. Lower Wick
        lower = self._detect_lower_rejection(candles[-1], current_price)
        if lower['detected']:
            signals.append(f"Lower Rejection: {lower['strength']:.0f}%")
            confidence += lower['strength'] * 0.25

        # 2. Volume Spike
        if volume_data:
            vol = self._analyze_volume_spike(volume_data)
            if vol['detected']:
                signals.append(f"Volume Spike: +{vol['strength']:.0f}%")
                confidence += vol['strength'] * 0.2

        # 3. Buy Wall
        if order_book:
            ob = self._analyze_buy_wall(order_book)
            if ob['detected']:
                signals.append(f"Buy Wall: {ob['strength']:.0f}%")
                confidence += ob['strength'] * 0.15

        # 4. RSI Oversold
        rsi = self._calculate_rsi(candles)
        if rsi < self.RSI_OVERSOLD:
            signals.append(f"RSI: {rsi:.0f}")
            confidence += min(20, (self.RSI_OVERSOLD - rsi) * 0.5)

        # 5. MACD Bullish
        if self._calculate_macd(candles)['signal'] == 'bullish':
            signals.append("MACD Bullish")
            confidence += 15

        # 6. Bounce
        bounce = self._detect_bounce(current_price, candles)
        if bounce['detected']:
            signals.append(f"Bounce: +{bounce['strength']:.1f}%")
            confidence += min(20, bounce['strength'] * 10)

        # 7. Momentum Gain
        momentum = self._detect_momentum_gain(candles)
        if momentum['detected']:
            signals.append(f"Momentum Gain: {momentum['strength']:.0f}%")
            confidence += momentum['strength'] * 0.2

        confidence = min(100.0, confidence)

        return {
            'is_bottom':  confidence >= self.BOTTOM_MIN_CONFIDENCE and len(signals) >= self.BOTTOM_MIN_SIGNALS,
            'confidence': confidence,
            'signals':    signals
        }

    def analyze_stop_loss_trigger(
        self, candles: list, current_price: float,
        highest_price: float, stop_threshold: float
    ) -> dict:
        """🛡️ كشف Stop Loss المبكر"""
        if not candles or len(candles) < 2:
            return {'trigger_soon': False, 'confidence': 0}

        drop_from_peak = ((highest_price - current_price) / highest_price) * 100
        remaining      = stop_threshold - drop_from_peak
        momentum       = self._calculate_drop_momentum(candles)
        pressure       = self._calculate_sell_pressure(candles)
        time_to_stop   = (remaining / momentum) * 10 if momentum > 0 else 999

        trigger    = time_to_stop < self.STOP_LOSS_TIME_LIMIT or (remaining < 1.0 and pressure > 70)
        confidence = min(100.0, (stop_threshold - remaining) * 20 + pressure * 0.3) if trigger else 0.0

        return {
            'trigger_soon':  trigger,
            'confidence':    confidence,
            'time_estimate': time_to_stop
        }

    # ═══════════════════════════════════════════════
    # 🕯️ أنماط الشموع الجديدة (Multi-Candle Patterns)
    # ═══════════════════════════════════════════════

    def _detect_shooting_star(self, candle: dict) -> dict:
        """🌠 Shooting Star - ظل علوي طويل + جسم صغير = قمة"""
        try:
            high   = candle.get('high', 0)
            low    = candle.get('low', 0)
            open_p = candle.get('open', 0)
            close  = candle.get('close', 0)

            body        = abs(close - open_p)
            upper_wick  = high - max(close, open_p)
            lower_wick  = min(close, open_p) - low
            total_range = high - low

            if total_range == 0 or body == 0:
                return {'detected': False, 'strength': 0}

            # شروط Shooting Star:
            # 1. الظل العلوي >= ضعف الجسم
            # 2. الظل السفلي صغير (أقل من الجسم)
            # 3. الشمعة حمراء (close < open) أقوى
            shadow_ratio = upper_wick / body if body > 0 else 0
            is_star = (shadow_ratio >= self.SHADOW_BODY_RATIO and
                       lower_wick < body and
                       upper_wick > total_range * 0.4)

            if not is_star:
                return {'detected': False, 'strength': 0}

            strength = min(100.0, shadow_ratio * 25)
            # بونص لو حمراء
            if close < open_p:
                strength = min(100.0, strength + 15)

            return {'detected': True, 'strength': strength}

        except Exception as e:
            print(f"⚠️ _detect_shooting_star error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_hammer(self, candle: dict) -> dict:
        """🔨 Hammer - ظل سفلي طويل + جسم صغير فوق = قاع"""
        try:
            high   = candle.get('high', 0)
            low    = candle.get('low', 0)
            open_p = candle.get('open', 0)
            close  = candle.get('close', 0)

            body        = abs(close - open_p)
            upper_wick  = high - max(close, open_p)
            lower_wick  = min(close, open_p) - low
            total_range = high - low

            if total_range == 0 or body == 0:
                return {'detected': False, 'strength': 0}

            shadow_ratio = lower_wick / body if body > 0 else 0
            is_hammer = (shadow_ratio >= self.SHADOW_BODY_RATIO and
                         upper_wick < body and
                         lower_wick > total_range * 0.4)

            if not is_hammer:
                return {'detected': False, 'strength': 0}

            strength = min(100.0, shadow_ratio * 25)
            # بونص لو خضراء
            if close > open_p:
                strength = min(100.0, strength + 15)

            return {'detected': True, 'strength': strength}

        except Exception as e:
            print(f"⚠️ _detect_hammer error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_bearish_engulfing(self, candles: list) -> dict:
        """🔴 Bearish Engulfing - شمعة حمراء تبتلع الخضراء"""
        try:
            if len(candles) < 2:
                return {'detected': False, 'strength': 0}

            prev = candles[-2]
            curr = candles[-1]

            prev_open  = prev.get('open', 0)
            prev_close = prev.get('close', 0)
            curr_open  = curr.get('open', 0)
            curr_close = curr.get('close', 0)

            prev_body = abs(prev_close - prev_open)
            curr_body = abs(curr_close - curr_open)

            # شروط: السابقة خضراء + الحالية حمراء + الحالية أكبر
            is_engulfing = (prev_close > prev_open and
                            curr_close < curr_open and
                            curr_body > prev_body * self.ENGULFING_MIN_RATIO and
                            curr_open >= prev_close and
                            curr_close <= prev_open)

            if not is_engulfing:
                return {'detected': False, 'strength': 0}

            ratio    = curr_body / prev_body if prev_body > 0 else 1
            strength = min(100.0, ratio * 35)
            return {'detected': True, 'strength': strength}

        except Exception as e:
            print(f"⚠️ _detect_bearish_engulfing error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_bullish_engulfing(self, candles: list) -> dict:
        """🟢 Bullish Engulfing - شمعة خضراء تبتلع الحمراء"""
        try:
            if len(candles) < 2:
                return {'detected': False, 'strength': 0}

            prev = candles[-2]
            curr = candles[-1]

            prev_open  = prev.get('open', 0)
            prev_close = prev.get('close', 0)
            curr_open  = curr.get('open', 0)
            curr_close = curr.get('close', 0)

            prev_body = abs(prev_close - prev_open)
            curr_body = abs(curr_close - curr_open)

            is_engulfing = (prev_close < prev_open and
                            curr_close > curr_open and
                            curr_body > prev_body * self.ENGULFING_MIN_RATIO and
                            curr_open <= prev_close and
                            curr_close >= prev_open)

            if not is_engulfing:
                return {'detected': False, 'strength': 0}

            ratio    = curr_body / prev_body if prev_body > 0 else 1
            strength = min(100.0, ratio * 35)
            return {'detected': True, 'strength': strength}

        except Exception as e:
            print(f"⚠️ _detect_bullish_engulfing error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_doji(self, candle: dict) -> dict:
        """✝️ Doji - جسم صغير جداً = تردد"""
        try:
            high   = candle.get('high', 0)
            low    = candle.get('low', 0)
            open_p = candle.get('open', 0)
            close  = candle.get('close', 0)

            total_range = high - low
            body        = abs(close - open_p)

            if total_range == 0:
                return {'detected': False, 'strength': 0}

            body_pct = (body / total_range) * 100

            if body_pct > self.DOJI_MAX_BODY * 100:
                return {'detected': False, 'strength': 0}

            # كل ما الجسم أصغر = الدوجي أقوى
            strength = min(100.0, (1 - body_pct / 10) * 60)
            return {'detected': True, 'strength': max(0, strength)}

        except Exception as e:
            print(f"⚠️ _detect_doji error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_consecutive_upper_wicks(self, candles: list) -> dict:
        """⚡ ظلال علوية متتالية - أقوى إشارة قمة"""
        try:
            lookback = min(self.MULTI_CANDLE_LOOKBACK, len(candles))
            if lookback < 2:
                return {'detected': False, 'strength': 0, 'count': 0}

            count     = 0
            total_str = 0

            for c in candles[-lookback:]:
                high   = c.get('high', 0)
                close  = c.get('close', 0)
                open_p = c.get('open', 0)
                total  = high - c.get('low', 0)

                if total == 0:
                    continue

                upper_wick = high - max(close, open_p)
                ratio      = (upper_wick / total) * 100

                if ratio > 35:  # عتبة أقل للمتتالية
                    count     += 1
                    total_str += ratio

            avg_str  = total_str / count if count > 0 else 0
            detected = count >= self.CONSECUTIVE_WICKS

            strength = min(100.0, avg_str * 0.8 + count * 15) if detected else 0

            return {'detected': detected, 'strength': strength, 'count': count}

        except Exception as e:
            print(f"⚠️ _detect_consecutive_upper_wicks error: {e}")
            return {'detected': False, 'strength': 0, 'count': 0}

    def _detect_consecutive_lower_wicks(self, candles: list) -> dict:
        """⚡ ظلال سفلية متتالية - أقوى إشارة قاع"""
        try:
            lookback = min(self.MULTI_CANDLE_LOOKBACK, len(candles))
            if lookback < 2:
                return {'detected': False, 'strength': 0, 'count': 0}

            count     = 0
            total_str = 0

            for c in candles[-lookback:]:
                low    = c.get('low', 0)
                close  = c.get('close', 0)
                open_p = c.get('open', 0)
                total  = c.get('high', 0) - low

                if total == 0:
                    continue

                lower_wick = min(close, open_p) - low
                ratio      = (lower_wick / total) * 100

                if ratio > 35:
                    count     += 1
                    total_str += ratio

            avg_str  = total_str / count if count > 0 else 0
            detected = count >= self.CONSECUTIVE_WICKS

            strength = min(100.0, avg_str * 0.8 + count * 15) if detected else 0

            return {'detected': detected, 'strength': strength, 'count': count}

        except Exception as e:
            print(f"⚠️ _detect_consecutive_lower_wicks error: {e}")
            return {'detected': False, 'strength': 0, 'count': 0}

    def _detect_shadow_volume_combo(self, candles: list,
                                     volume_data: list = None,
                                     direction: str = 'peak') -> dict:
        """💀💎 Shadow + Volume Combo - ظل + Volume عالي = إشارة قوية"""
        try:
            if not candles or len(candles) < 2:
                return {'detected': False, 'strength': 0}

            c = candles[-1]
            high   = c.get('high', 0)
            low    = c.get('low', 0)
            close  = c.get('close', 0)
            open_p = c.get('open', 0)
            total  = high - low

            if total == 0:
                return {'detected': False, 'strength': 0}

            if direction == 'peak':
                wick  = high - max(close, open_p)
                ratio = (wick / total) * 100
            else:
                wick  = min(close, open_p) - low
                ratio = (wick / total) * 100

            has_shadow = ratio > 40

            # تشيك Volume
            has_volume = False
            vol_boost  = 0
            if volume_data and len(volume_data) >= 3:
                avg_vol = sum(volume_data[-4:-1]) / 3
                cur_vol = volume_data[-1]
                if avg_vol > 0:
                    vol_change = ((cur_vol - avg_vol) / avg_vol) * 100
                    has_volume = vol_change > 30
                    vol_boost  = min(30, vol_change * 0.3)

            if has_shadow and has_volume:
                strength = min(100.0, ratio * 0.6 + vol_boost + self.SHADOW_VOLUME_BOOST)
                return {'detected': True, 'strength': strength}

            return {'detected': False, 'strength': 0}

        except Exception as e:
            print(f"⚠️ _detect_shadow_volume_combo error: {e}")
            return {'detected': False, 'strength': 0}

    # ═══════════════════════════════════════════════
    # كشف الأنماط الأساسية (القديمة - محفوظة)
    # ═══════════════════════════════════════════════

    def _detect_upper_rejection(self, candle: dict, current_price: float) -> dict:
        """كشف الفتيلة العلوية"""
        try:
            high        = candle.get('high', current_price)
            close       = candle.get('close', current_price)
            open_price  = candle.get('open', current_price)
            upper_wick  = high - max(close, open_price)
            total_range = high - min(close, open_price)

            if total_range == 0:
                return {'detected': False, 'strength': 0}

            wick_ratio = (upper_wick / total_range) * 100
            return {'detected': wick_ratio > self.UPPER_WICK_THRESHOLD,
                    'strength': min(100.0, wick_ratio)}
        except Exception as e:
            print(f"⚠️ _detect_upper_rejection error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_lower_rejection(self, candle: dict, current_price: float) -> dict:
        """كشف الفتيلة السفلية"""
        try:
            low         = candle.get('low', current_price)
            close       = candle.get('close', current_price)
            open_price  = candle.get('open', current_price)
            lower_wick  = min(close, open_price) - low
            total_range = max(close, open_price) - low

            if total_range == 0:
                return {'detected': False, 'strength': 0}

            wick_ratio = (lower_wick / total_range) * 100
            return {'detected': wick_ratio > self.LOWER_WICK_THRESHOLD,
                    'strength': min(100.0, wick_ratio)}
        except Exception as e:
            print(f"⚠️ _detect_lower_rejection error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_stalling(self, symbol: str, current_price: float) -> dict:
        """كشف ركود السعر"""
        try:
            now = datetime.now(timezone.utc)

            if symbol not in self.stalling_tracker:
                self.stalling_tracker[symbol] = {'price': current_price, 'start_time': now}
                return {'detected': False, 'duration': 0}

            tracker      = self.stalling_tracker[symbol]
            price_change = abs((current_price - tracker['price']) / tracker['price']) * 100

            if price_change < self.STALLING_PRICE_CHANGE:
                duration = (now - tracker['start_time']).total_seconds() / 60
                return {'detected': duration >= self.STALLING_MIN_DURATION, 'duration': duration}

            self.stalling_tracker[symbol] = {'price': current_price, 'start_time': now}
            return {'detected': False, 'duration': 0}

        except Exception as e:
            print(f"⚠️ _detect_stalling error: {e}")
            return {'detected': False, 'duration': 0}

    def _detect_bounce(self, current_price: float, candles: list) -> dict:
        """كشف الارتداد من القاع"""
        try:
            if len(candles) < 3:
                return {'detected': False, 'strength': 0}

            lowest = min(c.get('low', current_price) for c in candles[-3:])
            bounce = ((current_price - lowest) / lowest) * 100 if lowest > 0 else 0
            return {'detected': bounce > self.BOUNCE_THRESHOLD, 'strength': bounce}

        except Exception as e:
            print(f"⚠️ _detect_bounce error: {e}")
            return {'detected': False, 'strength': 0}

    def _detect_momentum_loss(self, candles: list) -> dict:
        """كشف فقدان الزخم (للقمة)"""
        return self._detect_momentum(candles, direction='loss')

    def _detect_momentum_gain(self, candles: list) -> dict:
        """كشف اكتساب الزخم (للقاع)"""
        return self._detect_momentum(candles, direction='gain')

    def _detect_momentum(self, candles: list, direction: str) -> dict:
        """كشف تغير الزخم"""
        try:
            if len(candles) < self.MOMENTUM_LOOKBACK:
                return {'detected': False, 'strength': 0}

            changes = [
                ((candles[i].get('close', 0) - candles[i - 1].get('close', 0))
                 / candles[i - 1].get('close', 1)) * 100
                for i in range(-self.MOMENTUM_LOOKBACK, -1)
                if candles[i - 1].get('close', 0) > 0
            ]

            if not changes:
                return {'detected': False, 'strength': 0}

            avg            = sum(changes) / len(changes)
            last_close     = candles[-2].get('close', 0)
            current_close  = candles[-1].get('close', 0)
            current_change = ((current_close - last_close) / last_close) * 100 if last_close > 0 else 0

            if direction == 'loss':
                delta    = avg - current_change
                detected = delta > self.MOMENTUM_THRESHOLD and avg > self.MOMENTUM_MIN_AVG
            else:
                delta    = current_change - avg
                detected = delta > self.MOMENTUM_THRESHOLD and current_change > self.MOMENTUM_MIN_AVG

            return {'detected': detected, 'strength': min(100.0, delta * 30)}

        except Exception as e:
            print(f"⚠️ _detect_momentum error: {e}")
            return {'detected': False, 'strength': 0}

    # ═══════════════════════════════════════════════
    # تحليل الحجم و Order Book
    # ═══════════════════════════════════════════════

    def _analyze_volume_drop(self, volume_data: list) -> dict:
        """كشف انخفاض الحجم"""
        return self._analyze_volume(volume_data, direction='drop')

    def _analyze_volume_spike(self, volume_data: list) -> dict:
        """كشف ارتفاع الحجم"""
        return self._analyze_volume(volume_data, direction='spike')

    def _analyze_volume(self, volume_data: list, direction: str) -> dict:
        """تحليل الحجم"""
        try:
            if len(volume_data) < self.VOLUME_LOOKBACK:
                return {'detected': False, 'strength': 0}

            avg     = sum(volume_data[-self.VOLUME_LOOKBACK:-1]) / (self.VOLUME_LOOKBACK - 1)
            current = volume_data[-1]

            if avg == 0:
                return {'detected': False, 'strength': 0}

            if direction == 'drop':
                change   = ((avg - current) / avg) * 100
                detected = change > self.VOLUME_DROP_THRESHOLD
            else:
                change   = ((current - avg) / avg) * 100
                detected = change > self.VOLUME_SPIKE_THRESHOLD

            return {'detected': detected, 'strength': min(100.0, change)}

        except Exception as e:
            print(f"⚠️ _analyze_volume error: {e}")
            return {'detected': False, 'strength': 0}

    def _analyze_sell_wall(self, order_book: dict) -> dict:
        """كشف جدار البيع"""
        return self._analyze_order_book_wall(order_book, side='sell')

    def _analyze_buy_wall(self, order_book: dict) -> dict:
        """كشف جدار الشراء"""
        return self._analyze_order_book_wall(order_book, side='buy')

    def _analyze_order_book_wall(self, order_book: dict, side: str) -> dict:
        """تحليل Order Book"""
        try:
            asks = order_book.get('asks', [])
            bids = order_book.get('bids', [])

            if not asks or not bids:
                return {'detected': False, 'strength': 0}

            ask_vol = sum(float(a[1]) for a in asks[:self.ORDER_BOOK_DEPTH])
            bid_vol = sum(float(b[1]) for b in bids[:self.ORDER_BOOK_DEPTH])

            if side == 'sell':
                denom     = bid_vol
                threshold = self.SELL_WALL_RATIO
                ratio     = (ask_vol / denom) * 100 if denom > 0 else 0
            else:
                denom     = ask_vol
                threshold = self.BUY_WALL_RATIO
                ratio     = (bid_vol / denom) * 100 if denom > 0 else 0

            return {'detected': ratio > threshold, 'strength': min(100.0, ratio - 100)}

        except Exception as e:
            print(f"⚠️ _analyze_order_book_wall error: {e}")
            return {'detected': False, 'strength': 0}

    # ═══════════════════════════════════════════════
    # حساب المؤشرات
    # ═══════════════════════════════════════════════

    def _calculate_rsi(self, candles: list) -> float:
        """حساب RSI"""
        try:
            if len(candles) < self.RSI_PERIOD + 1:
                return 50.0

            gains  = []
            losses = []
            for i in range(-self.RSI_PERIOD, 0):
                change = candles[i]['close'] - candles[i - 1]['close']
                gains.append(max(0.0, change))
                losses.append(max(0.0, -change))

            avg_gain = sum(gains)  / self.RSI_PERIOD
            avg_loss = sum(losses) / self.RSI_PERIOD

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            return 100.0 - (100.0 / (1 + rs))

        except Exception as e:
            print(f"⚠️ _calculate_rsi error: {e}")
            return 50.0

    def _calculate_macd(self, candles: list) -> dict:
        """حساب MACD"""
        try:
            if len(candles) < self.MACD_SLOW + self.MACD_SIGNAL:
                return {'signal': 'neutral', 'histogram': 0}

            closes     = [c['close'] for c in candles]
            ema_fast   = self._ema(closes, self.MACD_FAST)
            ema_slow   = self._ema(closes, self.MACD_SLOW)
            macd_line  = ema_fast - ema_slow

            macd_values = [
                self._ema(closes[:self.MACD_SLOW + i], self.MACD_FAST) -
                self._ema(closes[:self.MACD_SLOW + i], self.MACD_SLOW)
                for i in range(len(closes) - self.MACD_SLOW + 1)
            ]

            signal_line = self._ema(macd_values, self.MACD_SIGNAL)
            histogram   = macd_line - signal_line

            if len(macd_values) > 1:
                prev_hist = macd_values[-2] - self._ema(macd_values[:-1], self.MACD_SIGNAL)
                if histogram > 0 and prev_hist <= 0:
                    return {'signal': 'bullish',  'histogram': histogram}
                if histogram < 0 and prev_hist >= 0:
                    return {'signal': 'bearish', 'histogram': histogram}

            return {'signal': 'neutral', 'histogram': histogram}

        except Exception as e:
            print(f"⚠️ _calculate_macd error: {e}")
            return {'signal': 'neutral', 'histogram': 0}

    def _calculate_drop_momentum(self, candles: list) -> float:
        """حساب زخم الهبوط"""
        try:
            if len(candles) < 3:
                return 0.0

            drops = [
                ((candles[i - 1].get('close', 0) - candles[i].get('close', 0))
                 / candles[i - 1].get('close', 1)) * 100
                for i in range(-3, 0)
                if candles[i - 1].get('close', 0) > 0
            ]
            drops = [d for d in drops if d > 0]
            return sum(drops) / len(drops) if drops else 0.0

        except Exception as e:
            print(f"⚠️ _calculate_drop_momentum error: {e}")
            return 0.0

    def _calculate_sell_pressure(self, candles: list) -> float:
        """حساب ضغط البيع"""
        try:
            if len(candles) < 5:
                return 0.0
            red = sum(1 for c in candles[-5:] if c.get('close', 0) < c.get('open', 0))
            return (red / 5) * 100
        except Exception as e:
            print(f"⚠️ _calculate_sell_pressure error: {e}")
            return 0.0

    @staticmethod
    def _extract_volumes(candles: list) -> list:
        """استخراج الحجم من الشموع إذا لم يمرره التحليل صراحة."""
        try:
            return [float(c.get('volume', 0) or 0) for c in candles if isinstance(c, dict)]
        except Exception:
            return []

    @staticmethod
    def _ema(data: list, period: int) -> float:
        """حساب EMA"""
        try:
            if not data:
                return 0.0
            if len(data) < period:
                return sum(data) / len(data)

            k   = 2 / (period + 1)
            ema = sum(data[:period]) / period
            for price in data[period:]:
                ema = price * k + ema * (1 - k)
            return ema

        except Exception as e:
            print(f"⚠️ _ema error: {e}")
            return 0.0

    # ═══════════════════════════════════════════════
    # تنظيف الكاش
    # ═══════════════════════════════════════════════

    def _cleanup_stalling_tracker(self) -> None:
        """تنظيف الـ stalling tracker"""
        try:
            now       = datetime.now(timezone.utc)
            to_remove = [
                sym for sym, tracker in self.stalling_tracker.items()
                if (now - tracker['start_time']).total_seconds() / 3600 > self.STALLING_TRACKER_TTL
            ]
            for sym in to_remove:
                del self.stalling_tracker[sym]
        except Exception as e:
            print(f"⚠️ _cleanup_stalling_tracker error: {e}")
