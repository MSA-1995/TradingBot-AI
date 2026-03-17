"""
📊 Fibonacci Retracement Analyzer
يحدد أفضل نقاط الدخول بناءً على مستويات فيبوناتشي
"""

class FibonacciAnalyzer:
    def __init__(self):
        # مستويات فيبوناتشي الأساسية
        self.levels = {
            '0': 0.0,
            '23.6': 0.236,
            '38.2': 0.382,
            '50': 0.5,
            '61.8': 0.618,  # الأهم - النسبة الذهبية
            '78.6': 0.786,
            '100': 1.0
        }
        print("📊 Fibonacci Analyzer initialized")
    
    def calculate_levels(self, high, low):
        """حساب مستويات فيبوناتشي"""
        try:
            diff = high - low
            levels = {}
            
            for name, ratio in self.levels.items():
                levels[name] = high - (diff * ratio)
            
            return levels
        except:
            return None
    
    def get_support_level(self, current_price, df):
        """تحديد أقرب مستوى دعم فيبوناتشي"""
        try:
            # أعلى وأقل سعر في آخر 24 ساعة (288 شمعة × 5 دقائق)
            if len(df) < 50:
                return None
            
            recent_df = df.tail(min(288, len(df)))
            high = recent_df['high'].max()
            low = recent_df['low'].min()
            
            if high <= low or high == 0:
                return None
            
            # حساب المستويات
            levels = self.calculate_levels(high, low)
            if not levels:
                return None
            
            # إيجاد أقرب مستوى دعم تحت السعر الحالي
            support_levels = {k: v for k, v in levels.items() if v < current_price}
            
            if not support_levels:
                return None
            
            # أقرب مستوى دعم
            closest_level = max(support_levels.items(), key=lambda x: x[1])
            level_name = closest_level[0]
            level_price = closest_level[1]
            
            # المسافة من السعر الحالي
            distance_percent = ((current_price - level_price) / current_price) * 100
            
            return {
                'level': level_name,
                'price': level_price,
                'distance': distance_percent,
                'high': high,
                'low': low,
                'all_levels': levels
            }
        except Exception as e:
            return None
    
    def is_at_support(self, current_price, df, tolerance=0.5):
        """هل السعر عند مستوى دعم فيبوناتشي؟"""
        try:
            support = self.get_support_level(current_price, df)
            if not support:
                return False, 0
            
            distance = support['distance']
            level = support['level']
            
            # إذا السعر قريب من مستوى دعم (أقل من tolerance%)
            if distance <= tolerance:
                # المستويات القوية
                if level in ['61.8', '50']:
                    return True, 10  # boost قوي
                elif level in ['38.2', '78.6']:
                    return True, 5   # boost متوسط
                else:
                    return True, 3   # boost ضعيف
            
            return False, 0
        except:
            return False, 0
    
    def get_confidence_boost(self, current_price, df):
        """حساب زيادة الثقة بناءً على فيبوناتشي"""
        try:
            at_support, boost = self.is_at_support(current_price, df)
            
            if at_support:
                return boost
            
            # إذا مو عند دعم، شوف المسافة
            support = self.get_support_level(current_price, df)
            if not support:
                return 0
            
            distance = support['distance']
            level = support['level']
            
            # إذا قريب من مستوى قوي (1-2%)
            if level in ['61.8', '50'] and 0.5 < distance <= 2.0:
                return 3  # boost صغير (قريب من الدعم)
            
            return 0
        except:
            return 0
    
    def get_stop_loss_level(self, entry_price, df):
        """تحديد Stop Loss تحت مستوى فيبوناتشي"""
        try:
            support = self.get_support_level(entry_price, df)
            if not support:
                return entry_price * 0.985  # -1.5% default
            
            level_price = support['price']
            
            # Stop Loss تحت مستوى الدعم بـ 0.5%
            sl_price = level_price * 0.995
            
            # التأكد أنه ما يتجاوز -2%
            min_sl = entry_price * 0.98
            sl_price = max(sl_price, min_sl)
            
            return sl_price
        except:
            return entry_price * 0.985
