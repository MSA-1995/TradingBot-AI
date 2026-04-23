"""
🧬 Adaptive Intelligence System - نظام الذكاء التكيفي
يتعلم خصائص كل عملة ويعدل الاستراتيجية تلقائياً
"""

import numpy as np


class AdaptiveIntelligence:
    """
    يحلل سلوك كل عملة ويخصص لها:
    - حد ثقة مخصص (بدلاً من 75 لكل العملات)
    - نطاق RSI مخصص (بعض العملات تتحرك بين 20-80، أخرى 30-70)
    - حجم صفقة مخصص (عملات متقلبة = حجم أقل)
    """

    DEFAULT_PROFILE = {
        'min_confidence': 75,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'volatility_multiplier': 1.0,
        'preferred_timeframe': '5m',
        'success_pattern': None,
        'win_rate': 0.0,
        'avg_profit': 0.0
    }

    MIN_TRADES_FOR_PROFILE = 3
    MAX_MISTAKES_STORED = 10
    SIMILAR_MISTAKES_THRESHOLD = 3

    def __init__(self, storage):
        self.storage = storage
        self._profiles = {}  # {symbol: profile}

    def get_symbol_profile(self, symbol: str) -> dict:
        """جلب ملف العملة المخصص"""
        if symbol in self._profiles:
            return self._profiles[symbol]

        memory = self.storage.get_symbol_memory(symbol)

        # ملف افتراضي للعملات الجديدة أو ذات البيانات القليلة
        if not memory or memory.get('total_trades', 0) < self.MIN_TRADES_FOR_PROFILE:
            return dict(self.DEFAULT_PROFILE)

        total = max(memory.get('total_trades', 1), 1)
        wins = memory.get('win_count', 0)
        win_rate = wins / total
        avg_profit = memory.get('avg_profit') or 0.0
        best_rsi = memory.get('best_rsi') or 30

        # تعديل حد الثقة بناءً على معدل النجاح
        if win_rate >= 0.8:
            min_confidence = 65   # عملة موثوقة - نخفف الشروط
        elif win_rate >= 0.6:
            min_confidence = 75   # عادي
        else:
            min_confidence = 85   # عملة صعبة - نشدد الشروط

        # تعديل نطاق RSI بناءً على أفضل نقاط دخول سابقة
        rsi_oversold = max(20, min(40, best_rsi))

        profile = {
            'min_confidence': min_confidence,
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': 70,
            'volatility_multiplier': 1.0,
            'preferred_timeframe': '5m',
            'success_pattern': memory.get('last_trade_quality'),
            'win_rate': win_rate,
            'avg_profit': avg_profit
        }

        self._profiles[symbol] = profile
        return profile

    def adjust_confidence(self, symbol: str, base_confidence: float) -> float:
        """تعديل الثقة بناءً على ملف العملة"""
        try:
            profile = self.get_symbol_profile(symbol)
            win_rate = profile.get('win_rate') or 0.0

            if win_rate >= 0.75:
                return base_confidence + 10
            elif win_rate < 0.4:
                return base_confidence - 15

        except Exception as e:
            print(f"⚠️ Adaptive AI confidence error: {e}")

        return base_confidence

    def should_trade_now(self, symbol: str, current_hour: int) -> bool:
        """هل هذا الوقت مناسب لهذه العملة؟"""
        try:
            memory = self.storage.get_symbol_memory(symbol)
            if not memory:
                return True

            best_hours = memory.get('best_trading_hours', [])
            if best_hours and current_hour not in best_hours:
                return False

        except Exception as e:
            print(f"⚠️ Adaptive AI trading hours error: {e}")

        return True

    def detect_market_regime(self, df) -> str:
        """كشف نظام السوق (Bull/Bear/Sideways)"""
        try:
            if df is None or len(df) < 50:
                return 'UNKNOWN'

            closes = df['close'].tail(50).tolist()

            first_avg = sum(closes[:10]) / 10
            last_avg = sum(closes[-10:]) / 10

            if first_avg == 0:
                return 'UNKNOWN'

            change = ((last_avg - first_avg) / first_avg) * 100
            volatility = np.std(closes) / np.mean(closes) * 100

            if change > 5 and volatility > 3:
                return 'BULL_VOLATILE'
            elif change > 5:
                return 'BULL_STABLE'
            elif change < -5 and volatility > 3:
                return 'BEAR_VOLATILE'
            elif change < -5:
                return 'BEAR_STABLE'
            elif volatility > 4:
                return 'SIDEWAYS_VOLATILE'
            else:
                return 'SIDEWAYS_STABLE'

        except Exception as e:
            print(f"⚠️ Adaptive AI market regime error: {e}")
            return 'UNKNOWN'

    def learn_from_mistake(self, symbol: str, trade_data: dict) -> bool:
        """التعلم من الأخطاء"""
        try:
            profit = trade_data.get('profit_percent', 0)

            if profit >= 0:
                return False

            mistake_pattern = {
                'rsi': trade_data.get('entry_rsi'),
                'volume_ratio': trade_data.get('entry_volume_ratio'),
                'trend': trade_data.get('entry_trend'),
                'reason': trade_data.get('exit_reason'),
                'loss': abs(profit)
            }

            memory = self.storage.get_symbol_memory(symbol) or {}
            mistakes = memory.get('mistakes', [])
            mistakes.append(mistake_pattern)

            # الاحتفاظ بآخر MAX_MISTAKES_STORED أخطاء فقط
            memory['mistakes'] = mistakes[-self.MAX_MISTAKES_STORED:]
            self.storage.save_symbol_memory(symbol, memory)

            # مسح الكاش لإعادة بناء الملف
            self._profiles.pop(symbol, None)

            return True

        except Exception as e:
            print(f"⚠️ Adaptive AI learn from mistake error: {e}")
            return False

    def should_avoid_pattern(self, symbol: str, current_analysis: dict) -> bool:
        """هل يجب تجنب هذا النمط؟"""
        try:
            memory = self.storage.get_symbol_memory(symbol)
            if not memory or 'mistakes' not in memory:
                return False

            mistakes = memory['mistakes']
            current_rsi = current_analysis.get('rsi', 50)
            current_volume = current_analysis.get('volume_ratio', 1.0)
            current_trend = current_analysis.get('trend', 'neutral')

            similar_mistakes = sum(
                1 for mistake in mistakes
                if abs(current_rsi - (mistake.get('rsi') or 50)) < 10
                and abs(current_volume - (mistake.get('volume_ratio') or 1.0)) < 0.5
                and current_trend == mistake.get('trend')
            )

            return similar_mistakes >= self.SIMILAR_MISTAKES_THRESHOLD

        except Exception as e:
            print(f"⚠️ Adaptive AI avoid pattern error: {e}")
            return False

    def get_optimal_position_size(self, symbol: str, base_amount: float) -> float:
        """حساب حجم الصفقة الأمثل لهذه العملة"""
        try:
            profile = self.get_symbol_profile(symbol)
            avg_profit = profile.get('avg_profit') or 0.0

            if avg_profit > 5:
                return base_amount * 1.2
            elif avg_profit < 1:
                return base_amount * 0.7

        except Exception as e:
            print(f"⚠️ Adaptive AI position size error: {e}")

        return base_amount

    def invalidate_cache(self, symbol: str) -> None:
        """مسح كاش العملة لإعادة بنائه"""
        self._profiles.pop(symbol, None)

    def get_all_profiles(self) -> dict:
        """جلب جميع ملفات العملات المحفوظة في الكاش"""
        return dict(self._profiles)