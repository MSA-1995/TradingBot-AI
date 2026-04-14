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
        
        avg_profit = memory.get('avg_profit', 0)
        best_rsi = memory.get('best_rsi', 30)
        
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
        profile = self.get_symbol_profile(symbol)
        
        # إذا العملة ناجحة تاريخياً، نضيف بونص
        if profile.get('win_rate', 0) >= 0.75:
            return base_confidence + 10
        elif profile.get('win_rate', 0) < 0.4:
            return base_confidence - 15
        
        return base_confidence
    
    def should_trade_now(self, symbol, current_hour):
        """هل هذا الوقت مناسب لهذه العملة؟"""
        memory = self.storage.get_symbol_memory(symbol)
        if not memory:
            return True
        
        # تحليل أفضل أوقات التداول لهذه العملة
        # (يمكن توسيعه لاحقاً بتخزين best_hours في الداتابيز)
        return True
    
    def get_optimal_position_size(self, symbol, base_amount):
        """حساب حجم الصفقة الأمثل لهذه العملة"""
        profile = self.get_symbol_profile(symbol)
        
        # عملات ذات ربح عالي = حجم أكبر
        if profile.get('avg_profit', 0) > 5:
            return base_amount * 1.2
        elif profile.get('avg_profit', 0) < 1:
            return base_amount * 0.7
        
        return base_amount
