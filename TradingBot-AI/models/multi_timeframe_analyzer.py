"""
🕐 Multi-Timeframe Analyzer
تحليل متعدد الأطر الزمنية (5m, 15m, 1h) لكشف القمم والقيعان
"""

from typing import Optional

from config import (
    REALTIME_PEAK_BASE_CONFIDENCE,
    REALTIME_PEAK_BASE_CONFIRMATIONS,
    REALTIME_PEAK_STRONG_BULL_CONFIDENCE,
    REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS,
    REALTIME_PEAK_BULL_CONFIDENCE,
    REALTIME_PEAK_SIDEWAYS_CONFIDENCE,
    REALTIME_PEAK_BEAR_CONFIDENCE,
    REALTIME_BOTTOM_BASE_CONFIDENCE,
    REALTIME_BOTTOM_BASE_CONFIRMATIONS,
    REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE,
    REALTIME_BOTTOM_BULL_CONFIDENCE,
    REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE,
    REALTIME_BOTTOM_BEAR_CONFIDENCE,
    REALTIME_BOTTOM_BEAR_CONFIRMATIONS,
)


class MultiTimeframeAnalyzer:

    # أوزان الأطر الزمنية
    TF_WEIGHTS = {'5m': 0.40, '15m': 0.35, '1h': 0.25}

    # حد الثقة الافتراضي عند الخطأ
    DEFAULT_THRESHOLD = 60

    # عتبات التحليل
    PEAK_DROP_THRESHOLD       = 1.0    # انخفاض 1% من القمة
    PEAK_VOLUME_DROP          = 0.7    # حجم أقل من 70% = ضغط بيع
    PEAK_SELL_PRESSURE_RATIO  = 1.3
    BOTTOM_BOUNCE_THRESHOLD   = 0.5    # ارتداد 0.5% من القاع
    BOTTOM_VOLUME_SPIKE       = 1.5    # حجم أعلى من 150% = اهتمام شراء
    BOTTOM_BUY_PRESSURE_RATIO = 1.3
    MIN_CANDLES               = 3
    ORDER_BOOK_DEPTH          = 10
    VOLUME_LOOKBACK           = 5
    SINGLE_TF_MIN_CONFIDENCE  = 50

    # معاملات تعديل الثقة حسب السوق
    BULL_PEAK_MULTIPLIER      = 0.9
    BEAR_PEAK_MULTIPLIER      = 1.1
    BULL_BOTTOM_MULTIPLIER    = 1.1
    BEAR_BOTTOM_MULTIPLIER    = 0.9

    def __init__(self):
        print("✅ Multi-Timeframe Analyzer initialized")

    # ─────────────────────────────────────────────
    # تحليل القمة
    # ─────────────────────────────────────────────

    def analyze_peak(
        self,
        candles_5m, candles_15m, candles_1h,
        current_price: float, highest_price: float,
        volume_data_5m=None, volume_data_15m=None, volume_data_1h=None,
        order_book=None, macro_status: str = 'NEUTRAL'
    ) -> dict:
        """
        تحليل القمة عبر 3 أطر زمنية.

        Returns:
            {
                'is_peak': bool,
                'confidence': float (0-100),
                'confirmations': int (0-3),
                'signals': list,
                'market_context': str,
                'threshold_used': float,
                'timeframes': dict
            }
        """
        try:
            threshold, required_conf = self._get_peak_thresholds(macro_status)

            tf_5m  = self._analyze_single_timeframe_peak(candles_5m,  current_price, highest_price, volume_data_5m,  order_book, '5m')
            tf_15m = self._analyze_single_timeframe_peak(candles_15m, current_price, highest_price, volume_data_15m, order_book, '15m')
            tf_1h  = self._analyze_single_timeframe_peak(candles_1h,  current_price, highest_price, volume_data_1h,  order_book, '1h')

            weighted_confidence = self._weighted_confidence(
                tf_5m['confidence'], tf_15m['confidence'], tf_1h['confidence']
            )
            weighted_confidence = self._adjust_confidence_by_market(
                weighted_confidence, macro_status,
                bull_mult=self.BULL_PEAK_MULTIPLIER,
                bear_mult=self.BEAR_PEAK_MULTIPLIER
            )

            confirmations = sum([tf_5m['is_peak'], tf_15m['is_peak'], tf_1h['is_peak']])
            signals       = self._collect_signals(tf_5m, tf_15m, tf_1h, key='is_peak')
            is_peak       = weighted_confidence >= threshold and confirmations >= required_conf

            return {
                'is_peak':        is_peak,
                'confidence':     weighted_confidence,
                'confirmations':  confirmations,
                'signals':        signals,
                'market_context': macro_status,
                'threshold_used': threshold,
                'timeframes':     {'5m': tf_5m, '15m': tf_15m, '1h': tf_1h}
            }

        except Exception as e:
            print(f"⚠️ Multi-TF Peak error: {e}")
            return self._empty_peak_result(macro_status)

    # ─────────────────────────────────────────────
    # تحليل القاع
    # ─────────────────────────────────────────────

    def analyze_bottom(
        self,
        candles_5m, candles_15m, candles_1h,
        current_price: float,
        volume_data_5m=None, volume_data_15m=None, volume_data_1h=None,
        order_book=None, macro_status: str = 'NEUTRAL'
    ) -> dict:
        """
        تحليل القاع عبر 3 أطر زمنية.

        Returns:
            {
                'is_bottom': bool,
                'confidence': float (0-100),
                'confirmations': int (0-3),
                'signals': list,
                'market_context': str,
                'threshold_used': float,
                'timeframes': dict
            }
        """
        try:
            threshold, required_conf = self._get_bottom_thresholds(macro_status)

            tf_5m  = self._analyze_single_timeframe_bottom(candles_5m,  current_price, volume_data_5m,  order_book, '5m')
            tf_15m = self._analyze_single_timeframe_bottom(candles_15m, current_price, volume_data_15m, order_book, '15m')
            tf_1h  = self._analyze_single_timeframe_bottom(candles_1h,  current_price, volume_data_1h,  order_book, '1h')

            weighted_confidence = self._weighted_confidence(
                tf_5m['confidence'], tf_15m['confidence'], tf_1h['confidence']
            )
            weighted_confidence = self._adjust_confidence_by_market(
                weighted_confidence, macro_status,
                bull_mult=self.BULL_BOTTOM_MULTIPLIER,
                bear_mult=self.BEAR_BOTTOM_MULTIPLIER
            )

            confirmations = sum([tf_5m['is_bottom'], tf_15m['is_bottom'], tf_1h['is_bottom']])
            signals       = self._collect_signals(tf_5m, tf_15m, tf_1h, key='is_bottom')
            is_bottom     = weighted_confidence >= threshold and confirmations >= required_conf

            return {
                'is_bottom':      is_bottom,
                'confidence':     weighted_confidence,
                'confirmations':  confirmations,
                'signals':        signals,
                'market_context': macro_status,
                'threshold_used': threshold,
                'timeframes':     {'5m': tf_5m, '15m': tf_15m, '1h': tf_1h}
            }

        except Exception as e:
            print(f"⚠️ Multi-TF Bottom error: {e}")
            return self._empty_bottom_result(macro_status)

    # ─────────────────────────────────────────────
    # تحليل الأطر الزمنية الفردية
    # ─────────────────────────────────────────────

    def _analyze_single_timeframe_peak(
        self, candles, current_price: float, highest_price: float,
        volume_data, order_book, timeframe: str
    ) -> dict:
        """تحليل قمة في إطار زمني واحد"""
        try:
            if not candles or len(candles) < self.MIN_CANDLES:
                return {'is_peak': False, 'confidence': 0, 'reason': 'Not enough data'}

            confidence = 0
            reasons    = []

            # 1. انخفاض من القمة
            if highest_price > 0:
                drop = ((highest_price - current_price) / highest_price) * 100
                if drop > self.PEAK_DROP_THRESHOLD:
                    confidence += 30
                    reasons.append(f"Drop {drop:.1f}%")

            # 2. شموع هابطة
            bearish = sum(1 for c in candles[-3:] if c.get('close', 0) < c.get('open', 0))
            if bearish >= 2:
                confidence += 25
                reasons.append(f"{bearish} bearish candles")

            # 3. انخفاض الحجم
            if volume_data and len(volume_data) >= self.MIN_CANDLES:
                avg_vol = self._avg_volume(volume_data)
                if volume_data[-1] < avg_vol * self.PEAK_VOLUME_DROP:
                    confidence += 20
                    reasons.append("Volume drop")

            # 4. ضغط البيع في Order Book
            if self._has_order_book(order_book):
                sell = sum(a[1] for a in order_book['asks'][:self.ORDER_BOOK_DEPTH])
                buy  = sum(b[1] for b in order_book['bids'][:self.ORDER_BOOK_DEPTH])
                if sell > buy * self.PEAK_SELL_PRESSURE_RATIO:
                    confidence += 25
                    reasons.append("Sell wall")

            return {
                'is_peak':    confidence >= self.SINGLE_TF_MIN_CONFIDENCE,
                'confidence': confidence,
                'reason':     ', '.join(reasons) if reasons else 'No signals'
            }

        except Exception as e:
            return {'is_peak': False, 'confidence': 0, 'reason': f'Error: {e}'}

    def _analyze_single_timeframe_bottom(
        self, candles, current_price: float,
        volume_data, order_book, timeframe: str
    ) -> dict:
        """تحليل قاع في إطار زمني واحد"""
        try:
            if not candles or len(candles) < self.MIN_CANDLES:
                return {'is_bottom': False, 'confidence': 0, 'reason': 'Not enough data'}

            confidence = 0
            reasons    = []

            # 1. ارتداد من القاع
            lowest = min(c.get('low', float('inf')) for c in candles[-5:])
            if lowest > 0:
                bounce = ((current_price - lowest) / lowest) * 100
                if bounce > self.BOTTOM_BOUNCE_THRESHOLD:
                    confidence += 30
                    reasons.append(f"Bounce {bounce:.1f}%")

            # 2. شموع صاعدة
            bullish = sum(1 for c in candles[-3:] if c.get('close', 0) > c.get('open', 0))
            if bullish >= 2:
                confidence += 25
                reasons.append(f"{bullish} bullish candles")

            # 3. ارتفاع الحجم
            if volume_data and len(volume_data) >= self.MIN_CANDLES:
                avg_vol = self._avg_volume(volume_data)
                if volume_data[-1] > avg_vol * self.BOTTOM_VOLUME_SPIKE:
                    confidence += 20
                    reasons.append("Volume spike")

            # 4. ضغط الشراء في Order Book
            if self._has_order_book(order_book):
                buy  = sum(b[1] for b in order_book['bids'][:self.ORDER_BOOK_DEPTH])
                sell = sum(a[1] for a in order_book['asks'][:self.ORDER_BOOK_DEPTH])
                if buy > sell * self.BOTTOM_BUY_PRESSURE_RATIO:
                    confidence += 25
                    reasons.append("Buy wall")

            return {
                'is_bottom':  confidence >= self.SINGLE_TF_MIN_CONFIDENCE,
                'confidence': confidence,
                'reason':     ', '.join(reasons) if reasons else 'No signals'
            }

        except Exception as e:
            return {'is_bottom': False, 'confidence': 0, 'reason': f'Error: {e}'}

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    def _get_peak_thresholds(self, macro_status: str) -> tuple[float, int]:
        """عتبات القمة حسب حالة السوق"""
        if 'STRONG_BULL' in macro_status:
            return REALTIME_PEAK_STRONG_BULL_CONFIDENCE, REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS
        elif 'BULL' in macro_status:
            return REALTIME_PEAK_BULL_CONFIDENCE, REALTIME_PEAK_BASE_CONFIRMATIONS
        elif 'BEAR' in macro_status:
            return REALTIME_PEAK_BEAR_CONFIDENCE, REALTIME_PEAK_BASE_CONFIRMATIONS
        else:
            return REALTIME_PEAK_SIDEWAYS_CONFIDENCE, REALTIME_PEAK_BASE_CONFIRMATIONS

    def _get_bottom_thresholds(self, macro_status: str) -> tuple[float, int]:
        """عتبات القاع حسب حالة السوق"""
        if 'STRONG_BULL' in macro_status:
            return REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE, REALTIME_BOTTOM_BASE_CONFIRMATIONS
        elif 'BULL' in macro_status:
            return REALTIME_BOTTOM_BULL_CONFIDENCE, REALTIME_BOTTOM_BASE_CONFIRMATIONS
        elif 'BEAR' in macro_status:
            return REALTIME_BOTTOM_BEAR_CONFIDENCE, REALTIME_BOTTOM_BEAR_CONFIRMATIONS
        else:
            return REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE, REALTIME_BOTTOM_BASE_CONFIRMATIONS

    def _weighted_confidence(self, c5m: float, c15m: float, c1h: float) -> float:
        """حساب الثقة الموزونة للأطر الثلاثة"""
        return min(100.0, (
            c5m  * self.TF_WEIGHTS['5m']  +
            c15m * self.TF_WEIGHTS['15m'] +
            c1h  * self.TF_WEIGHTS['1h']
        ))

    @staticmethod
    def _adjust_confidence_by_market(confidence: float, macro_status: str,
                                      bull_mult: float, bear_mult: float) -> float:
        """تعديل الثقة بناءً على حالة السوق"""
        if 'BULL' in macro_status:
            confidence *= bull_mult
        elif 'BEAR' in macro_status:
            confidence *= bear_mult
        return min(100.0, confidence)

    @staticmethod
    def _collect_signals(tf_5m: dict, tf_15m: dict, tf_1h: dict, key: str) -> list[str]:
        """جمع إشارات الأطر الزمنية"""
        signals = []
        for label, tf in [('5m', tf_5m), ('15m', tf_15m), ('1h', tf_1h)]:
            if tf.get(key):
                signals.append(f"{label}: {tf['reason']}")
        return signals

    @staticmethod
    def _avg_volume(volume_data: list) -> float:
        """حساب متوسط الحجم"""
        recent = volume_data[-5:] if len(volume_data) >= 5 else volume_data
        return sum(recent) / len(recent) if recent else 1.0

    @staticmethod
    def _has_order_book(order_book) -> bool:
        """التحقق من وجود Order Book صالح"""
        return bool(order_book and order_book.get('bids') and order_book.get('asks'))

    @staticmethod
    def _empty_peak_result(macro_status: str) -> dict:
        """نتيجة فارغة عند فشل تحليل القمة"""
        return {
            'is_peak':        False,
            'confidence':     0,
            'confirmations':  0,
            'signals':        [],
            'market_context': macro_status,
            'threshold_used': MultiTimeframeAnalyzer.DEFAULT_THRESHOLD
        }

    @staticmethod
    def _empty_bottom_result(macro_status: str) -> dict:
        """نتيجة فارغة عند فشل تحليل القاع"""
        return {
            'is_bottom':      False,
            'confidence':     0,
            'confirmations':  0,
            'signals':        [],
            'market_context': macro_status,
            'threshold_used': MultiTimeframeAnalyzer.DEFAULT_THRESHOLD
        }