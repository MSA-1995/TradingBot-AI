"""
📊 Fibonacci Retracement Analyzer - Enhanced
يحدد أفضل نقاط الدخول بناءً على مستويات فيبوناتشي
+ تتبع نجاح المستويات
+ تكيف مع العملات
+ دمج مع Volume
"""

from typing import Optional


class FibonacciAnalyzer:

    # مستويات فيبوناتشي الأساسية
    FIB_LEVELS = {
        '0':    0.0,
        '23.6': 0.236,
        '38.2': 0.382,
        '50':   0.5,
        '61.8': 0.618,  # الأهم - النسبة الذهبية
        '78.6': 0.786,
        '100':  1.0
    }

    # مستويات قوية للدعم والمقاومة
    STRONG_LEVELS = {'61.8', '50'}
    MEDIUM_LEVELS = {'38.2', '78.6'}

    # عملات كبيرة تحصل على boost إضافي
    MAJOR_SYMBOLS = {'BTC', 'ETH'}

    def __init__(self):
        print("📊 Fibonacci Analyzer initialized (Enhanced)")

    # ─────────────────────────────────────────────
    # حسابات المستويات
    # ─────────────────────────────────────────────

    def calculate_levels(self, high: float, low: float,
                         use_extensions: bool = False) -> Optional[dict]:
        """حساب مستويات فيبوناتشي + Extensions اختياري"""
        try:
            if high <= low:
                return None

            diff = high - low
            levels = {name: high - (diff * ratio)
                      for name, ratio in self.FIB_LEVELS.items()}

            if use_extensions:
                levels['127.2'] = high + (diff * 0.272)
                levels['161.8'] = high + (diff * 0.618)
                levels['200']   = high + (diff * 1.0)
                levels['261.8'] = high + (diff * 1.618)

            return levels

        except Exception as e:
            print(f"⚠️ Fibonacci calculate_levels error: {e}")
            return None

    def _get_high_low(self, analysis: dict) -> tuple[Optional[float], Optional[float]]:
        """استخراج High/Low من التحليل مع التحقق"""
        high = analysis.get('high_24h')
        low  = analysis.get('low_24h')
        if not high or not low or high <= low:
            return None, None
        return high, low

    def _is_major_symbol(self, symbol: str) -> bool:
        """هل العملة من الكبار؟"""
        return any(major in symbol for major in self.MAJOR_SYMBOLS)

    def _apply_volume_boost(self, base_boost: int, volume_ratio: float,
                            is_support: bool = True) -> int:
        """تعديل الـ boost بناءً على Volume"""
        if is_support:
            if volume_ratio > 1.5:
                return int(base_boost * 1.3)
            elif volume_ratio < 0.8:
                return int(base_boost * 0.8)
        else:
            if volume_ratio < 0.7:
                return int(base_boost * 1.3)
            elif volume_ratio > 1.5:
                return int(base_boost * 0.8)
        return base_boost

    def _level_base_boost(self, level: str, is_support: bool = True) -> int:
        """حساب الـ boost الأساسي بناءً على قوة المستوى"""
        if level in self.STRONG_LEVELS:
            return 22 if is_support else 12
        elif level in self.MEDIUM_LEVELS:
            return 12 if is_support else 8
        else:
            return 5

    # ─────────────────────────────────────────────
    # مستويات الدعم
    # ─────────────────────────────────────────────

    def get_support_level(self, current_price: float, analysis: dict) -> Optional[dict]:
        """تحديد أقرب مستوى دعم فيبوناتشي"""
        try:
            high, low = self._get_high_low(analysis)
            if high is None:
                return None

            levels = self.calculate_levels(high, low)
            if not levels:
                return None

            support_levels = {k: v for k, v in levels.items() if v < current_price}
            if not support_levels:
                return None

            level_name, level_price = max(support_levels.items(), key=lambda x: x[1])
            distance_percent = ((current_price - level_price) / current_price) * 100

            return {
                'level':      level_name,
                'price':      level_price,
                'distance':   distance_percent,
                'high':       high,
                'low':        low,
                'all_levels': levels
            }

        except Exception as e:
            print(f"⚠️ Fibonacci get_support_level error: {e}")
            return None

    def is_at_support(self, current_price: float, analysis: dict,
                      tolerance: float = 0.5, volume_ratio: float = 1.0,
                      symbol: str = '') -> tuple[bool, int]:
        """هل السعر عند مستوى دعم فيبوناتشي؟"""
        try:
            # RSI مرتفع = خطر شراء
            rsi = analysis.get('rsi', 50)
            if rsi > 70:
                return False, 0

            support = self.get_support_level(current_price, analysis)
            if not support or support['distance'] > tolerance:
                return False, 0

            level = support['level']

            # Dynamic boost بناءً على Volume العالي جداً
            extra_multiplier = 1.4 if volume_ratio > 2.0 else 1.0

            base_boost = int(self._level_base_boost(level, is_support=True) * extra_multiplier)
            base_boost = self._apply_volume_boost(base_boost, volume_ratio, is_support=True)

            if self._is_major_symbol(symbol):
                base_boost = int(base_boost * 1.2)

            return True, base_boost

        except Exception as e:
            print(f"⚠️ Fibonacci is_at_support error: {e}")
            return False, 0

    # ─────────────────────────────────────────────
    # مستويات المقاومة
    # ─────────────────────────────────────────────

    def get_resistance_level(self, current_price: float, analysis: dict) -> Optional[dict]:
        """تحديد أقرب مستوى مقاومة فيبوناتشي"""
        try:
            high, low = self._get_high_low(analysis)
            if high is None:
                return None

            levels = self.calculate_levels(high, low)
            if not levels:
                return None

            resistance_levels = {k: v for k, v in levels.items() if v > current_price}
            if not resistance_levels:
                return None

            level_name, level_price = min(resistance_levels.items(), key=lambda x: x[1])
            distance_percent = ((level_price - current_price) / current_price) * 100

            return {
                'level':      level_name,
                'price':      level_price,
                'distance':   distance_percent,
                'high':       high,
                'low':        low,
                'all_levels': levels
            }

        except Exception as e:
            print(f"⚠️ Fibonacci get_resistance_level error: {e}")
            return None

    def is_at_resistance(self, current_price: float, analysis: dict,
                         tolerance: float = 0.5, volume_ratio: float = 1.0,
                         symbol: str = '') -> tuple[bool, int]:
        """هل السعر عند مستوى مقاومة فيبوناتشي؟ (للبيع)"""
        try:
            # RSI منخفض = قد يرتد، لا تبيع
            rsi = analysis.get('rsi', 50)
            if rsi < 30:
                return False, 0

            resistance = self.get_resistance_level(current_price, analysis)
            if not resistance or resistance['distance'] > tolerance:
                return False, 0

            level = resistance['level']

            # Volume منخفض = إشارة ضعيفة
            if volume_ratio < 0.7:
                return False, 0

            base_boost  = self._level_base_boost(level, is_support=False)
            volume_boost = 5 if volume_ratio > 1.5 else 0
            base_boost   = self._apply_volume_boost(base_boost, volume_ratio, is_support=False)
            base_boost  += volume_boost

            if self._is_major_symbol(symbol):
                base_boost = int(base_boost * 1.2)

            return True, base_boost

        except Exception as e:
            print(f"⚠️ Fibonacci is_at_resistance error: {e}")
            return False, 0

    # ─────────────────────────────────────────────
    # Confidence Boost
    # ─────────────────────────────────────────────

    def get_confidence_boost(self, current_price: float, analysis: dict,
                             volume_ratio: float = 1.0, symbol: str = '') -> int:
        """حساب زيادة الثقة بناءً على فيبوناتشي"""
        try:
            at_support, boost = self.is_at_support(
                current_price, analysis,
                volume_ratio=volume_ratio, symbol=symbol
            )
            if at_support:
                return boost

            # قريب من مستوى قوي (0.5 - 2%)
            support = self.get_support_level(current_price, analysis)
            if support and support['level'] in self.STRONG_LEVELS:
                if 0.5 < support['distance'] <= 2.0:
                    return 5

            return 0

        except Exception as e:
            print(f"⚠️ Fibonacci get_confidence_boost error: {e}")
            return 0

    # ─────────────────────────────────────────────
    # Fibonacci Clusters
    # ─────────────────────────────────────────────

    def detect_fibonacci_clusters(self, current_price: float,
                                  analysis: dict) -> dict:
        """كشف Fibonacci Clusters - تجمع المستويات"""
        try:
            high, low = self._get_high_low(analysis)
            if high is None:
                return {'detected': False, 'strength': 0}

            levels = self.calculate_levels(high, low)
            if not levels:
                return {'detected': False, 'strength': 0}

            nearby_levels = [
                (name, price, abs((current_price - price) / current_price) * 100)
                for name, price in levels.items()
                if abs((current_price - price) / current_price) * 100 < 1.0
            ]

            if len(nearby_levels) < 2:
                return {'detected': False, 'strength': 0}

            strength = sum(
                15 if name in self.STRONG_LEVELS else
                10 if name in self.MEDIUM_LEVELS else 5
                for name, _, _ in nearby_levels
            )

            return {
                'detected': True,
                'strength': min(strength, 30),
                'levels':   nearby_levels,
                'reason':   f'{len(nearby_levels)} Fib levels clustered'
            }

        except Exception as e:
            print(f"⚠️ Fibonacci detect_clusters error: {e}")
            return {'detected': False, 'strength': 0}

    # ─────────────────────────────────────────────
    # Swing High / Low
    # ─────────────────────────────────────────────

    def get_swing_high_low(self, df, lookback: int = 20) -> tuple[Optional[float], Optional[float]]:
        """حساب Swing High/Low بدلاً من 24h"""
        try:
            if df is None or len(df) < lookback:
                return None, None

            recent = df.tail(lookback)
            return float(recent['high'].max()), float(recent['low'].min())

        except Exception as e:
            print(f"⚠️ Fibonacci get_swing_high_low error: {e}")
            return None, None