"""
📊 Volume Forecasting Engine - محرك التنبؤ بالحجم
يتنبأ بالحجم في الشموع القادمة لاكتشاف الانفجارات مبكراً
"""

import numpy as np
from typing import Optional


class VolumeForecastEngine:
    """
    يستخدم:
    - Moving Average للحجم
    - Volume Momentum (تسارع الحجم)
    - Time-based patterns (أوقات الذروة)
    """

    # ─── إعدادات المتوسطات ───
    MA_LONG          = 20
    MA_MID           = 5
    MA_SHORT         = 3
    EMA_ALPHA        = 0.3

    # ─── عتبات الزخم والتسارع ───
    ACCELERATION_UP   = 1.2
    ACCELERATION_DOWN = 0.8
    ACCELERATION_BOOST = 1.15
    ACCELERATION_SLOW  = 0.85
    TREND_UP_THRESHOLD = 1.2
    TREND_DOWN_THRESHOLD = 0.8

    # ─── عتبات انفجار الحجم ───
    BREAKOUT_RATIO_HIGH    = 1.5
    BREAKOUT_RATIO_MED     = 1.3
    BREAKOUT_MOMENTUM_MIN  = 20
    BREAKOUT_PROB_HIGH     = 70
    BREAKOUT_PROB_MED      = 50
    BREAKOUT_PROB_LOW      = 40
    BREAKOUT_MIN_PROB      = 50

    # ─── عتبات Volume Profile ───
    PROFILE_LOW_PERCENTILE  = 6    # 30%
    PROFILE_HIGH_PERCENTILE = 13   # 70%
    CLIMAX_MULTIPLIER       = 3.0
    ACCUMULATION_MIN        = 4
    DISTRIBUTION_MIN        = 2
    LOW_ACTIVITY_MIN        = 4
    RECENT_WINDOW           = 5

    # ─── جودة الحجم ───
    QUALITY_VOLUME_WEIGHT   = 25
    QUALITY_VOLUME_MAX      = 50
    QUALITY_STABILITY_MAX   = 50
    MIN_VOLUMES_REQUIRED    = 20
    DEFAULT_QUALITY_SCORE   = 50

    # ─── مضاعفات الوقت ───
    PEAK_HOUR_START    = 14    # الجلسة الأمريكية
    PEAK_HOUR_END      = 20
    QUIET_HOUR_START   = 0     # الجلسة الآسيوية
    QUIET_HOUR_END     = 6
    PEAK_MULTIPLIER    = 1.3
    QUIET_MULTIPLIER   = 0.7
    NORMAL_MULTIPLIER  = 1.0

    def __init__(self):
        self.volume_history: dict = {}   # {symbol: [volumes]}
        self.time_patterns:  dict = {}   # {symbol: {hour: avg_volume}}

    # ─────────────────────────────────────────────
    # التنبؤ بالحجم
    # ─────────────────────────────────────────────

    def predict_next_volume(self, symbol: str, current_volumes: list,
                             current_hour: int) -> dict:
        """
        التنبؤ بحجم الشمعة القادمة + Volume Profile Analysis.

        Returns:
            {
                'predicted_volume': float,
                'confidence':       0-100,
                'trend':            'INCREASING' | 'DECREASING' | 'STABLE' | 'UNKNOWN'
            }
        """
        if len(current_volumes) < self.MA_LONG:
            return {
                'predicted_volume': current_volumes[-1] if current_volumes else 0,
                'confidence': 0,
                'trend': 'UNKNOWN'
            }

        ma_20 = float(np.mean(current_volumes[-self.MA_LONG:]))
        ma_5  = float(np.mean(current_volumes[-self.MA_MID:]))
        ma_3  = float(np.mean(current_volumes[-self.MA_SHORT:]))

        recent_trend = ma_5 / ma_20 if ma_20 > 0 else 1.0
        acceleration = ma_3 / ma_5  if ma_5  > 0 else 1.0

        # تنبؤ EMA
        predicted = (self.EMA_ALPHA * current_volumes[-1]
                     + (1 - self.EMA_ALPHA) * ma_5)

        # تعديل بناءً على التسارع
        if acceleration > self.ACCELERATION_UP:
            predicted *= self.ACCELERATION_BOOST
        elif acceleration < self.ACCELERATION_DOWN:
            predicted *= self.ACCELERATION_SLOW

        # تعديل بناءً على الوقت
        time_multiplier = self._get_time_multiplier(current_hour)
        predicted      *= time_multiplier

        # Volume Profile
        volume_profile = self._analyze_volume_profile(current_volumes)

        # حساب الثقة
        volume_std = float(np.std(current_volumes[-self.MA_LONG:]))
        volume_cv  = volume_std / ma_20 if ma_20 > 0 else 1.0
        confidence = max(0.0, min(100.0, 100 - volume_cv * 50))

        # الاتجاه
        trend = self._resolve_volume_trend(recent_trend)

        return {
            'predicted_volume': predicted,
            'current_volume':   current_volumes[-1],
            'ma_20':            ma_20,
            'confidence':       round(confidence, 1),
            'trend':            trend,
            'momentum':         round((recent_trend - 1) * 100, 1),
            'acceleration':     round((acceleration - 1) * 100, 1),
            'time_multiplier':  time_multiplier,
            'volume_profile':   volume_profile
        }

    # ─────────────────────────────────────────────
    # كشف انفجار الحجم
    # ─────────────────────────────────────────────

    def detect_volume_breakout(self, symbol: str, current_volumes: list,
                                prediction: dict) -> dict:
        """
        كشف انفجار الحجم قبل حدوثه.

        Returns:
            {'breakout_imminent': bool, 'probability': 0-100}
        """
        if len(current_volumes) < 10:
            return {'breakout_imminent': False, 'probability': 0}

        avg            = float(np.mean(current_volumes[-self.MA_LONG:]))
        current        = current_volumes[-1]
        current_ratio  = current / avg if avg > 0 else 1.0
        predicted_vol  = prediction.get('predicted_volume', 0)
        predicted_ratio = predicted_vol / avg if avg > 0 else 1.0
        trend          = prediction.get('trend', 'STABLE')
        momentum       = prediction.get('momentum', 0)

        probability = self._calculate_breakout_probability(
            current_ratio, predicted_ratio, trend, momentum
        )

        return {
            'breakout_imminent': probability >= self.BREAKOUT_MIN_PROB,
            'probability':       probability,
            'current_ratio':     round(current_ratio, 2),
            'predicted_ratio':   round(predicted_ratio, 2)
        }

    def _calculate_breakout_probability(self, current_ratio: float,
                                         predicted_ratio: float,
                                         trend: str, momentum: float) -> int:
        """حساب احتمالية انفجار الحجم"""
        if current_ratio > self.BREAKOUT_RATIO_HIGH and trend == 'INCREASING':
            return self.BREAKOUT_PROB_HIGH
        if current_ratio > self.BREAKOUT_RATIO_MED and predicted_ratio > self.BREAKOUT_RATIO_HIGH:
            return self.BREAKOUT_PROB_MED
        if trend == 'INCREASING' and momentum > self.BREAKOUT_MOMENTUM_MIN:
            return self.BREAKOUT_PROB_LOW
        return 0

    # ─────────────────────────────────────────────
    # جودة الحجم
    # ─────────────────────────────────────────────

    def get_volume_quality_score(self, symbol: str,
                                  current_volumes: list) -> float:
        """
        تقييم جودة الحجم (0-100).
        حجم عالي + مستقر = جودة عالية.
        """
        if len(current_volumes) < self.MIN_VOLUMES_REQUIRED:
            return float(self.DEFAULT_QUALITY_SCORE)

        avg     = float(np.mean(current_volumes[-self.MA_LONG:]))
        std     = float(np.std(current_volumes[-self.MA_LONG:]))
        current = current_volumes[-1]

        volume_score    = min(self.QUALITY_VOLUME_MAX,
                              (current / avg) * self.QUALITY_VOLUME_WEIGHT) if avg > 0 else 0.0
        cv              = std / avg if avg > 0 else 1.0
        stability_score = max(0.0, self.QUALITY_STABILITY_MAX - cv * self.QUALITY_VOLUME_WEIGHT)

        return round(volume_score + stability_score, 1)

    # ─────────────────────────────────────────────
    # Volume Profile
    # ─────────────────────────────────────────────

    def _analyze_volume_profile(self, volumes: list) -> dict:
        """تحليل Volume Profile - توزيع الحجم"""
        try:
            if len(volumes) < self.MIN_VOLUMES_REQUIRED:
                return {'type': 'UNKNOWN', 'strength': 0}

            sorted_vols     = sorted(volumes[-self.MA_LONG:])
            low_threshold   = sorted_vols[self.PROFILE_LOW_PERCENTILE]
            high_threshold  = sorted_vols[self.PROFILE_HIGH_PERCENTILE]
            recent          = volumes[-self.RECENT_WINDOW:]
            mean_vol        = float(np.mean(volumes[-self.MA_LONG:]))

            high_count = sum(1 for v in recent if v > high_threshold)
            low_count  = sum(1 for v in recent if v < low_threshold)

            if recent[-1] > mean_vol * self.CLIMAX_MULTIPLIER:
                return {'type': 'CLIMAX',       'strength': 90}
            if high_count >= self.ACCUMULATION_MIN:
                return {'type': 'ACCUMULATION', 'strength': 85}
            if high_count >= self.DISTRIBUTION_MIN and low_count >= self.DISTRIBUTION_MIN:
                return {'type': 'DISTRIBUTION', 'strength': 70}
            if low_count >= self.LOW_ACTIVITY_MIN:
                return {'type': 'LOW_ACTIVITY', 'strength': 30}

            return {'type': 'NEUTRAL', 'strength': 50}

        except Exception as e:
            print(f"⚠️ _analyze_volume_profile error: {e}")
            return {'type': 'UNKNOWN', 'strength': 0}

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    def _get_time_multiplier(self, current_hour: int) -> float:
        """مضاعف الوقت - بعض الساعات تشهد حجم أعلى"""
        if self.PEAK_HOUR_START <= current_hour <= self.PEAK_HOUR_END:
            return self.PEAK_MULTIPLIER     # الجلسة الأمريكية
        if self.QUIET_HOUR_START <= current_hour <= self.QUIET_HOUR_END:
            return self.QUIET_MULTIPLIER    # الجلسة الآسيوية
        return self.NORMAL_MULTIPLIER

    def _resolve_volume_trend(self, recent_trend: float) -> str:
        """تحديد اتجاه الحجم من النسبة"""
        if recent_trend > self.TREND_UP_THRESHOLD:
            return 'INCREASING'
        if recent_trend < self.TREND_DOWN_THRESHOLD:
            return 'DECREASING'
        return 'STABLE'