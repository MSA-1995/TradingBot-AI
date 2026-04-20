"""
🧬 Adaptive Intelligence System - نظام الذكاء التكيفي
يتعلم خصائص كل عملة ويعدل الاستراتيجية تلقائياً
"""

class AdaptiveIntelligence:
    """
    يحلل سلوك كل عملة ويخصص لها:
    - حد ثقة مخصص (بدلاً من 75 لكل العملات)
    - نطاق RSI مخصص (بعض العملات تتحرك بين 20-80، أخرى 30-70)
    - حجم صفقة مخصص (عملات متقلبة = حجم أقل)
    """
    
    def __init__(self, storage):
        self.storage = storage
        self._profiles = {}  # {symbol: profile}
    
    def get_symbol_profile(self, symbol):
        """جلب ملف العملة المخصص"""
        if symbol in self._profiles:
            return self._profiles[symbol]
        
        # جلب من الداتابيز
        memory = self.storage.get_symbol_memory(symbol)
        if not memory or memory.get('total_trades', 0) < 3:
            # ملف افتراضي للعملات الجديدة
            return {
                'min_confidence': 75,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'volatility_multiplier': 1.0,
                'preferred_timeframe': '5m',
                'success_pattern': None
            }
        
        # حساب الملف المخصص بناءً على التاريخ
        total = memory.get('total_trades', 1)
        wins = memory.get('win_count', 0)
        win_rate = wins / total
        
        avg_profit = memory.get('avg_profit', 0) or 0
        best_rsi = memory.get('best_rsi', 30) or 30
        
        # تعديل حد الثقة بناءً على معدل النجاح
        if win_rate >= 0.8:
            min_confidence = 65  # عملة موثوقة - نخفف الشروط
        elif win_rate >= 0.6:
            min_confidence = 75  # عادي
        else:
            min_confidence = 85  # عملة صعبة - نشدد الشروط
        
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
    
    def adjust_confidence(self, symbol, base_confidence):
        """تعديل الثقة بناءً على ملف العملة"""
        try:
            profile = self.get_symbol_profile(symbol)
            if not profile:
                return base_confidence

            # إذا العملة ناجحة تاريخياً، نضيف بونص
            win_rate = profile.get('win_rate') or 0
            if win_rate >= 0.75:
                return base_confidence + 10
            elif win_rate < 0.4:
                return base_confidence - 15
        except Exception as e:
            print(f"⚠️ Adaptive AI confidence error: {e}")

        return base_confidence
    
    def should_trade_now(self, symbol, current_hour):
        """هل هذا الوقت مناسب لهذه العملة؟"""
        memory = self.storage.get_symbol_memory(symbol)
        if not memory:
            return True
        
        # تحليل أفضل أوقات التداول
        best_hours = memory.get('best_trading_hours', [])
        if best_hours and current_hour not in best_hours:
            return False
        
        return True
    
    def detect_market_regime(self, df):
        """كشف نظام السوق (Bull/Bear/Sideways)"""
        try:
            if df is None or len(df) < 50:
                return 'UNKNOWN'
            
            # حساب الاتجاه من 50 شمعة
            closes = df['close'].tail(50).tolist()
            
            # مقارنة أول 10 مع آخر 10
            first_10_avg = sum(closes[:10]) / 10
            last_10_avg = sum(closes[-10:]) / 10
            
            change = ((last_10_avg - first_10_avg) / first_10_avg) * 100
            
            # حساب التقلب (Volatility)
            import numpy as np
            volatility = np.std(closes) / np.mean(closes) * 100
            
            # تحديد النظام
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
        except:
            return 'UNKNOWN'
    
    def learn_from_mistake(self, symbol, trade_data):
        """التعلم من الأخطاء"""
        try:
            profit = trade_data.get('profit_percent', 0)
            
            # إذا كانت صفقة خاسرة
            if profit < 0:
                # حفظ النمط الفاشل
                mistake_pattern = {
                    'rsi': trade_data.get('entry_rsi'),
                    'volume_ratio': trade_data.get('entry_volume_ratio'),
                    'trend': trade_data.get('entry_trend'),
                    'reason': trade_data.get('exit_reason'),
                    'loss': abs(profit)
                }
                
                # حفظ في الذاكرة
                memory = self.storage.get_symbol_memory(symbol) or {}
                mistakes = memory.get('mistakes', [])
                mistakes.append(mistake_pattern)
                
                # الاحتفاظ بآخر 10 أخطاء فقط
                memory['mistakes'] = mistakes[-10:]
                
                self.storage.save_symbol_memory(symbol, memory)
                
                return True
            
            return False
        except:
            return False
    
    def should_avoid_pattern(self, symbol, current_analysis):
        """هل يجب تجنب هذا النمط؟"""
        try:
            memory = self.storage.get_symbol_memory(symbol)
            if not memory or 'mistakes' not in memory:
                return False
            
            mistakes = memory['mistakes']
            current_rsi = current_analysis.get('rsi', 50)
            current_volume = current_analysis.get('volume_ratio', 1.0)
            current_trend = current_analysis.get('trend', 'neutral')
            
            # فحص إذا كان النمط الحالي يشبه أخطاء سابقة
            similar_mistakes = 0
            for mistake in mistakes:
                rsi_diff = abs(current_rsi - mistake.get('rsi', 50))
                volume_diff = abs(current_volume - mistake.get('volume_ratio', 1.0))
                
                if rsi_diff < 10 and volume_diff < 0.5 and current_trend == mistake.get('trend'):
                    similar_mistakes += 1
            
            # إذا كان هناك 3+ أخطاء مشابهة = تجنب
            if similar_mistakes >= 3:
                return True
            
            return False
        except:
            return False
    
    def get_optimal_position_size(self, symbol, base_amount):
        """حساب حجم الصفقة الأمثل لهذه العملة"""
        try:
            profile = self.get_symbol_profile(symbol)
            if not profile:
                return base_amount

            # عملات ذات ربح عالي = حجم أكبر
            avg_profit = profile.get('avg_profit') or 0
            if avg_profit > 5:
                return base_amount * 1.2
            elif avg_profit < 1:
                return base_amount * 0.7
        except Exception as e:
            print(f"⚠️ Adaptive AI position size error: {e}")
            return base_amount

        return base_amount
