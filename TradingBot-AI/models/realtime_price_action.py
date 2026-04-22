"""
🎯 Real-time Price Action Analyzer
كشف القمم والقيعان بشكل فوري
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
    PEAK_MIN_CONFIDENCE     = 65
    PEAK_MIN_SIGNALS        = 3
    PEAK_DISTANCE_MAX       = 2.0    # أقصى مسافة من القمة %
    PEAK_DISTANCE_MIN       = 0.5    # أدنى مسافة لاعتبارها عند القمة %
    PEAK_CONFIDENCE_BOOST   = 20
    UPPER_WICK_THRESHOLD    = 60     # % من نطاق الشمعة
    RSI_OVERBOUGHT          = 70
    VOLUME_DROP_THRESHOLD   = 30     # % انخفاض الحجم
    SELL_WALL_RATIO         = 150    # % نسبة asks/bids

    # ─── عتبات القاع ───
    BOTTOM_MIN_CONFIDENCE   = 65
    BOTTOM_MIN_SIGNALS      = 3
    LOWER_WICK_THRESHOLD    = 60
    RSI_OVERSOLD            = 30
    VOLUME_SPIKE_THRESHOLD  = 50     # % ارتفاع الحجم
    BUY_WALL_RATIO          = 150    # % نسبة bids/asks
    BOUNCE_THRESHOLD        = 0.5    # % ارتداد من القاع

    # ─── إعدادات عامة ───
    ORDER_BOOK_DEPTH        = 10
    VOLUME_LOOKBACK         = 5
    STALLING_PRICE_CHANGE   = 0.3    # % تغير السعر للتعرف على الركود
    STALLING_MIN_DURATION   = 3      # دقائق
    STALLING_TRACKER_TTL    = 24     # ساعات
    MOMENTUM_LOOKBACK       = 5
    MOMENTUM_THRESHOLD      = 0.5
    MOMENTUM_MIN_AVG        = 0.3
    STOP_LOSS_TIME_LIMIT    = 5      # دقائق

    def __init__(self):
        self.stalling_tracker: dict = {}
        # للتوافق مع الكود القديم
        self.rsi_period  = self.RSI_PERIOD
        self.macd_fast   = self.MACD_FAST
        self.macd_slow   = self.MACD_SLOW
        self.macd_signal = self.MACD_SIGNAL

    # ─────────────────────────────────────────────
    # الواجهات الرئيسية
    # ─────────────────────────────────────────────

    def analyze_peak_signals(
        self, symbol: str, candles: list,
        current_price: float, highest_price: Optional[float] = None,
        volume_data=None, order_book=None
    ) -> dict:
        """🔴 كشف القمة السريع"""
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
        """🟢 كشف القاع السريع"""
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

    # ─────────────────────────────────────────────
    # كشف الأنماط
    # ─────────────────────────────────────────────

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
        """كشف تغير الزخم (مشترك بين loss و gain)"""
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

    # ─────────────────────────────────────────────
    # تحليل الحجم و Order Book
    # ─────────────────────────────────────────────

    def _analyze_volume_drop(self, volume_data: list) -> dict:
        """كشف انخفاض الحجم"""
        return self._analyze_volume(volume_data, direction='drop')

    def _analyze_volume_spike(self, volume_data: list) -> dict:
        """كشف ارتفاع الحجم"""
        return self._analyze_volume(volume_data, direction='spike')

    def _analyze_volume(self, volume_data: list, direction: str) -> dict:
        """تحليل الحجم (مشترك بين drop و spike)"""
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
        """تحليل Order Book (مشترك بين sell و buy)"""
        try:
            asks = order_book.get('asks', [])
            bids = order_book.get('bids', [])

            if not asks or not bids:
                return {'detected': False, 'strength': 0}

            ask_vol = sum(float(a[1]) for a in asks[:self.ORDER_BOOK_DEPTH])
            bid_vol = sum(float(b[1]) for b in bids[:self.ORDER_BOOK_DEPTH])

            if side == 'sell':
                denom = bid_vol
                threshold = self.SELL_WALL_RATIO
                ratio = (ask_vol / denom) * 100 if denom > 0 else 0
            else:
                denom = ask_vol
                threshold = self.BUY_WALL_RATIO
                ratio = (bid_vol / denom) * 100 if denom > 0 else 0

            return {'detected': ratio > threshold, 'strength': min(100.0, ratio - 100)}

        except Exception as e:
            print(f"⚠️ _analyze_order_book_wall error: {e}")
            return {'detected': False, 'strength': 0}

    # ─────────────────────────────────────────────
    # حساب المؤشرات
    # ─────────────────────────────────────────────

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

    # ─────────────────────────────────────────────
    # تنظيف الكاش
    # ─────────────────────────────────────────────

    def _cleanup_stalling_tracker(self) -> None:
        """تنظيف الـ stalling tracker من الإدخالات القديمة"""
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