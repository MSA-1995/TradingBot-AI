"""
🎯 Trend Early Detection System - نظام الكشف المبكر عن الاتجاهات
يكتشف بداية الاتجاه قبل الجميع (قبل تأكيد EMA/MACD)
"""

import numpy as np
from typing import Optional

import pandas as pd


class TrendEarlyDetector:
    """
    يستخدم:
    - Micro Structure Analysis (تحليل الهيكل الدقيق)
    - Order Flow (تدفق الأوامر)
    - Price Action Footprints (بصمات حركة السعر)
    """

    # ─── إشارات Bullish ───
    BULLISH_SIGNALS = {'BULLISH', 'VOLUME_CONFIRM', 'BOS_BULLISH', 'SWEEP_BULLISH', 'FVG_BULLISH'}

    # ─── إشارات Bearish ───
    BEARISH_SIGNALS = {'BEARISH', 'BOS_BEARISH', 'SWEEP_BEARISH', 'FVG_BEARISH'}

    # ─── عتبات الاتجاه ───
    MIN_TREND_SCORE         = 30     # أدنى نقاط - AI يقرر الباقي ديناميكياً
    VOLUME_CONFIRM_RATIO    = 1.3    # نسبة ارتفاع الحجم للتأكيد
    VOLUME_DECLINE_RATIO    = 0.7    # نسبة انخفاض الحجم للإنهاك
    ORDER_BOOK_DEPTH        = 10
    BID_ASK_BULL_RATIO      = 1.5
    BID_ASK_BEAR_RATIO      = 0.67

    # ─── مراحل الاتجاه ───
    BIRTH_THRESHOLD         = 3
    GROWTH_THRESHOLD        = 6

    # ─── عتبات الإنهاك ───
    RSI_EXHAUSTION_BULL     = 75
    RSI_EXHAUSTION_BEAR     = 25
    CANDLE_SHRINK_RATIO     = 0.5

    # ─── عتبات الأنماط ───
    FVG_MIN_GAP             = 0.5    # % أدنى حجم فجوة FVG
    UPPER_WICK_MIN          = 60     # % للتعرف على الرفض العلوي
    STALLING_PRICE_CHANGE   = 0.3

    # ─── ثقة الإشارات ───
    CONFIDENCE_THRESHOLDS = {4: 85, 3: 65, 2: 50}  # أكثر مرونة - AI يكتشف أبكر
    CONFIDENCE_DEFAULT    = 35  # يعطي فرصة أكبر للاتجاهات الضعيفة

    # ─── درجات الإشارات ───
    SCORE_CANDLE_PATTERN    = 20
    SCORE_HIGHER_LOWS       = 25
    SCORE_VOLUME_CONFIRM    = 15
    SCORE_ORDER_BOOK        = 20
    SCORE_BOS               = 30
    SCORE_SWEEP             = 25
    SCORE_FVG               = 20

    def __init__(self):
        self.trend_memory: dict = {}   # {symbol: last_trend}

    # ─────────────────────────────────────────────
    # الواجهة الرئيسية
    # ─────────────────────────────────────────────

    def detect_trend_birth(self, df: Optional[pd.DataFrame],
                           order_book: Optional[dict] = None) -> dict:
        """
        كشف ولادة اتجاه جديد (قبل التأكيد الكلاسيكي).

        Returns:
            {
                'trend':      'BULLISH' | 'BEARISH' | 'NONE',
                'strength':   0-100,
                'stage':      'BIRTH' | 'GROWTH' | 'MATURE' | 'UNKNOWN',
                'signals':    list,
                'confidence': float
            }
        """
        if df is None or len(df) < 30:
            return {'trend': 'NONE', 'strength': 0,
                    'stage': 'UNKNOWN', 'signals': [], 'confidence': 0}

        signals = []

        # 1. نمط الشموع الأخيرة
        signals += self._signal_candle_pattern(df)

        # 2. Break of Structure
        bos = self._detect_break_of_structure(df)
        if bos:
            signals.append(bos)

        # 3. Higher Lows / Lower Highs
        signals += self._signal_structure_highs_lows(df)

        # 4. Liquidity Sweep
        sweep = self._detect_liquidity_sweep(df)
        if sweep:
            signals.append(sweep)

        # 5. Fair Value Gap
        fvg = self._detect_fair_value_gap(df)
        if fvg:
            signals.append(fvg)

        # 6. تأكيد الحجم
        signals += self._signal_volume_confirm(df)

        # 7. Order Book
        if order_book:
            signals += self._signal_order_book(order_book)

        # 8. تجميع النتائج
        bullish_score = sum(s[1] for s in signals if s[0] in self.BULLISH_SIGNALS)
        bearish_score = sum(s[1] for s in signals if s[0] in self.BEARISH_SIGNALS)

        trend, strength = self._resolve_trend(bullish_score, bearish_score)
        stage           = self._determine_stage(df, trend, strength)

        return {
            'trend':      trend,
            'strength':   strength,
            'stage':      stage,
            'signals':    signals,
            'confidence': self._calculate_confidence(signals)
        }

    def is_optimal_entry(self, trend_data: dict,
                          current_price: float,
                          df: Optional[pd.DataFrame]) -> bool:
        """هل هذه نقطة دخول مثالية؟ (في بداية الاتجاه لا نهايته)"""
        if trend_data.get('trend') == 'NONE':
            return False

        stage    = trend_data.get('stage')
        strength = trend_data.get('strength', 0)

        if stage == 'BIRTH':
            return True
        if stage == 'GROWTH' and strength < 70:
            return True
        return False   # MATURE = خطر انعكاس

    def get_trend_exhaustion_score(self, df: Optional[pd.DataFrame],
                                    trend: str) -> int:
        """
        درجة إنهاك الاتجاه (0-100).
        100 = الاتجاه منهك ومستعد للانعكاس.
        """
        if df is None or len(df) < 20:
            return 0

        exhaustion = 0

        # 1. RSI
        if 'rsi' in df.columns:
            rsi = float(df['rsi'].iloc[-1])
            if trend == 'BULLISH' and rsi > self.RSI_EXHAUSTION_BULL:
                exhaustion += 30
            elif trend == 'BEARISH' and rsi < self.RSI_EXHAUSTION_BEAR:
                exhaustion += 30

        # 2. تناقص الحجم
        volumes = df['volume'].tail(10).tolist()
        if len(volumes) >= 5:
            recent_vol = float(np.mean(volumes[-3:]))
            older_vol  = float(np.mean(volumes[-10:-3]))
            if older_vol > 0 and recent_vol < older_vol * self.VOLUME_DECLINE_RATIO:
                exhaustion += 25

        # 3. تقلص حجم الشموع
        candle_sizes = [abs(float(row['close']) - float(row['open']))
                        for _, row in df.tail(5).iterrows()]
        if len(candle_sizes) >= 3:
            avg_size = float(np.mean(candle_sizes))
            if avg_size > 0 and candle_sizes[-1] < avg_size * self.CANDLE_SHRINK_RATIO:
                exhaustion += 20

        # 4. Divergence
        if 'rsi' in df.columns and len(df) >= 10:
            price_trend = float(df['close'].iloc[-1]) - float(df['close'].iloc[-10])
            rsi_trend   = float(df['rsi'].iloc[-1])   - float(df['rsi'].iloc[-10])

            if trend == 'BULLISH' and price_trend > 0 and rsi_trend < 0:
                exhaustion += 25
            elif trend == 'BEARISH' and price_trend < 0 and rsi_trend > 0:
                exhaustion += 25

        return min(100, exhaustion)

    # ─────────────────────────────────────────────
    # إشارات مساعدة
    # ─────────────────────────────────────────────

    def _signal_candle_pattern(self, df: pd.DataFrame) -> list:
        """إشارة نمط الشموع الأخيرة"""
        last_5        = df.tail(5)
        green_candles = sum(1 for _, r in last_5.iterrows() if r['close'] > r['open'])

        if green_candles >= 4:
            return [('BULLISH', self.SCORE_CANDLE_PATTERN)]
        if green_candles <= 1:
            return [('BEARISH', self.SCORE_CANDLE_PATTERN)]
        return []

    def _signal_structure_highs_lows(self, df: pd.DataFrame) -> list:
        """إشارة Higher Lows / Lower Highs"""
        signals = []
        lows    = df['low'].tail(10).tolist()
        highs   = df['high'].tail(10).tolist()

        if len(lows) >= 6:
            if min(lows[-3:]) > min(lows[-6:-3]):
                signals.append(('BULLISH', self.SCORE_HIGHER_LOWS))

        if len(highs) >= 6:
            if max(highs[-3:]) < max(highs[-6:-3]):
                signals.append(('BEARISH', self.SCORE_HIGHER_LOWS))

        return signals

    def _signal_volume_confirm(self, df: pd.DataFrame) -> list:
        """إشارة تأكيد الحجم"""
        volumes = df['volume'].tail(10).tolist()
        if len(volumes) < 5:
            return []

        recent_vol = float(np.mean(volumes[-3:]))
        older_vol  = float(np.mean(volumes[-10:-3]))

        if older_vol > 0 and recent_vol > older_vol * self.VOLUME_CONFIRM_RATIO:
            return [('VOLUME_CONFIRM', self.SCORE_VOLUME_CONFIRM)]
        return []

    def _signal_order_book(self, order_book: dict) -> list:
        """إشارة Order Book"""
        try:
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])
            if not bids or not asks:
                return []

            bid_depth = sum(b[1] for b in bids[:self.ORDER_BOOK_DEPTH])
            ask_depth = sum(a[1] for a in asks[:self.ORDER_BOOK_DEPTH])
            ratio     = bid_depth / ask_depth if ask_depth > 0 else 1.0

            if ratio > self.BID_ASK_BULL_RATIO:
                return [('BULLISH', self.SCORE_ORDER_BOOK)]
            if ratio < self.BID_ASK_BEAR_RATIO:
                return [('BEARISH', self.SCORE_ORDER_BOOK)]
        except Exception as e:
            print(f"⚠️ _signal_order_book error: {e}")
        return []

    # ─────────────────────────────────────────────
    # كشف الأنماط
    # ─────────────────────────────────────────────

    def _detect_break_of_structure(self, df: pd.DataFrame) -> Optional[tuple]:
        """كشف Break of Structure (BOS)"""
        try:
            if len(df) < 15:
                return None

            highs  = df['high'].tail(15).tolist()
            lows   = df['low'].tail(15).tolist()
            closes = df['close'].tail(15).tolist()

            # Bullish BOS
            if closes[-1] > max(highs[-15:-5]) and max(highs[-5:]) > max(highs[-15:-5]):
                return ('BOS_BULLISH', self.SCORE_BOS)

            # Bearish BOS
            if closes[-1] < min(lows[-15:-5]) and min(lows[-5:]) < min(lows[-15:-5]):
                return ('BOS_BEARISH', self.SCORE_BOS)

        except Exception as e:
            print(f"⚠️ _detect_break_of_structure error: {e}")
        return None

    def _detect_liquidity_sweep(self, df: pd.DataFrame) -> Optional[tuple]:
        """كشف Liquidity Sweep - كنس السيولة"""
        try:
            if len(df) < 10:
                return None

            last_10 = df.tail(10)
            lows    = last_10['low'].tolist()
            highs   = last_10['high'].tolist()
            closes  = last_10['close'].tolist()

            # Bullish Sweep
            for i in range(len(lows) - 3):
                if lows[-2] < min(lows[i:i + 3]) and closes[-1] > closes[-2]:
                    return ('SWEEP_BULLISH', self.SCORE_SWEEP)

            # Bearish Sweep
            for i in range(len(highs) - 3):
                if highs[-2] > max(highs[i:i + 3]) and closes[-1] < closes[-2]:
                    return ('SWEEP_BEARISH', self.SCORE_SWEEP)

        except Exception as e:
            print(f"⚠️ _detect_liquidity_sweep error: {e}")
        return None

    def _detect_fair_value_gap(self, df: pd.DataFrame) -> Optional[tuple]:
        """كشف Fair Value Gap (FVG)"""
        try:
            if len(df) < 5:
                return None

            candles = df.tail(3).to_dict('records')
            if len(candles) < 3:
                return None

            c1, _, c3 = candles

            # Bullish FVG
            if c3['low'] > c1['high']:
                gap = ((c3['low'] - c1['high']) / c1['high']) * 100
                if gap > self.FVG_MIN_GAP:
                    return ('FVG_BULLISH', self.SCORE_FVG)

            # Bearish FVG
            if c3['high'] < c1['low'] and c1['low'] > 0:
                gap = ((c1['low'] - c3['high']) / c3['high']) * 100
                if gap > self.FVG_MIN_GAP:
                    return ('FVG_BEARISH', self.SCORE_FVG)

        except Exception as e:
            print(f"⚠️ _detect_fair_value_gap error: {e}")
        return None

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    @staticmethod
    def _resolve_trend(bullish_score: int, bearish_score: int) -> tuple[str, int]:
        """تحديد الاتجاه النهائي من النقاط"""
        if bullish_score > bearish_score and bullish_score >= TrendEarlyDetector.MIN_TREND_SCORE:
            return 'BULLISH', min(100, bullish_score)
        if bearish_score > bullish_score and bearish_score >= TrendEarlyDetector.MIN_TREND_SCORE:
            return 'BEARISH', min(100, bearish_score)
        return 'NONE', 0

    def _determine_stage(self, df: pd.DataFrame, trend: str, strength: int) -> str:
        """تحديد مرحلة الاتجاه (BIRTH / GROWTH / MATURE)"""
        if trend == 'NONE':
            return 'UNKNOWN'

        last_10 = df.tail(10)

        if trend == 'BULLISH':
            count = sum(1 for _, r in last_10.iterrows() if r['close'] > r['open'])
        else:
            count = sum(1 for _, r in last_10.iterrows() if r['close'] < r['open'])

        if count <= self.BIRTH_THRESHOLD:
            return 'BIRTH'
        if count <= self.GROWTH_THRESHOLD:
            return 'GROWTH'
        return 'MATURE'

    def _calculate_confidence(self, signals: list) -> int:
        """حساب الثقة بناءً على عدد الإشارات"""
        count = len(signals)
        for threshold, confidence in sorted(self.CONFIDENCE_THRESHOLDS.items(), reverse=True):
            if count >= threshold:
                return confidence
        return self.CONFIDENCE_DEFAULT
