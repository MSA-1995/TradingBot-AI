"""
📊 Fibonacci Retracement Analyzer - Enhanced
يحدد أفضل نقاط الدخول بناءً على مستويات فيبوناتشي
+ تتبع نجاح المستويات
+ تكيف مع العملات
+ دمج مع Volume
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
        
        # The level_success dictionary is kept for structure but will no longer be updated.
        self.level_success = {
            '61.8': {'success': 0, 'fail': 0},
            '50': {'success': 0, 'fail': 0},
            '38.2': {'success': 0, 'fail': 0},
            '78.6': {'success': 0, 'fail': 0}
        }
        
        print("📊 Fibonacci Analyzer initialized (Enhanced)")
    
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
    
    def get_resistance_level(self, current_price, analysis):
        """تحديد أقرب مستوى مقاومة فيبوناتشي"""
        try:
            high = analysis.get('high_24h')
            low = analysis.get('low_24h')
            
            if not high or not low or high <= low:
                return None
            
            # حساب المستويات
            levels = self.calculate_levels(high, low)
            if not levels:
                return None
            
            # إيجاد أقرب مستوى مقاومة فوق السعر الحالي
            resistance_levels = {k: v for k, v in levels.items() if v > current_price}
            
            if not resistance_levels:
                return None
            
            # أقرب مستوى مقاومة
            closest_level = min(resistance_levels.items(), key=lambda x: x[1])
            level_name = closest_level[0]
            level_price = closest_level[1]
            
            # المسافة من السعر الحالي
            distance_percent = ((level_price - current_price) / current_price) * 100
            
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
    
    def is_at_resistance(self, current_price, analysis, tolerance=0.5, volume_ratio=1.0, symbol=''):
        """هل السعر عند مستوى مقاومة فيبوناتشي؟ (للبيع)"""
        try:
            # 🚨 فحص RSI أولاً - إذا تشبع بيعي لا تضيف نقاط!
            rsi = analysis.get('rsi', 50)
            if rsi < 30:
                return False, 0  # RSI منخفض = قد يرتد، لا تبيع
            
            resistance = self.get_resistance_level(current_price, analysis)
            if not resistance:
                return False, 0
            
            distance = resistance['distance']
            level = resistance['level']
            
            # إذا السعر قريب من مستوى مقاومة (أقل من tolerance%)
            if distance <= tolerance:
                # دمج مع Volume للدقة
                volume_boost = 0
                if volume_ratio > 1.5:
                    volume_boost = 5  # volume عالي يعزز الإشارة
                elif volume_ratio < 0.7:
                    return False, 0  # volume منخفض يضعف الإشارة

                # حساب Boost الأساسي
                if level in ['61.8', '50']:
                    base_boost = 12  # boost قوي
                elif level in ['38.2', '78.6']:
                    base_boost = 8   # boost متوسط
                else:
                    base_boost = 5   # boost ضعيف
                
                # تعديل حسب قوة المستوى (من التاريخ)
                level_strength = self.get_level_strength(level)
                base_boost = int(base_boost * level_strength)
                
                # تعديل حسب Volume (محسن)
                if volume_ratio < 0.7:
                    base_boost = int(base_boost * 1.3)  # volume ضعيف = مقاومة أقوى
                elif volume_ratio > 1.5:
                    base_boost = int(base_boost * 0.8)  # volume عالي = قد يخترق

                # إضافة volume_boost الإضافي
                base_boost += volume_boost
                
                # تعديل حسب العملة
                if 'BTC' in symbol or 'ETH' in symbol:
                    base_boost = int(base_boost * 1.2)  # العملات الكبيرة أقوى
                
                return True, base_boost
            
            return False, 0
        except:
            return False, 0
        """تحديد أقرب مستوى دعم فيبوناتشي"""
        try:
            high = analysis.get('high_24h')
            low = analysis.get('low_24h')
            
            if not high or not low or high <= low:
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
    
    def get_level_strength(self, level_name):
        """حساب قوة المستوى بناءً على التاريخ"""
        if level_name not in self.level_success:
            return 1.0  # قوة عادية
        
        stats = self.level_success[level_name]
        total = stats['success'] + stats['fail']
        
        if total < 5:
            return 1.0  # بيانات قليلة
        
        success_rate = stats['success'] / total
        
        # قوة المستوى (0.5 - 1.5)
        if success_rate > 0.7:
            return 1.5  # قوي جداً
        elif success_rate > 0.6:
            return 1.3  # قوي
        elif success_rate < 0.4:
            return 0.7  # ضعيف
        else:
            return 1.0  # عادي
    
    def is_at_support(self, current_price, analysis, tolerance=0.5, volume_ratio=1.0, symbol=''):
        """هل السعر عند مستوى دعم فيبوناتشي؟ (محسّن)"""
        try:
            # 🚨 فحص RSI أولاً - إذا تشبع شرائي لا تضيف نقاط!
            rsi = analysis.get('rsi', 50)
            if rsi > 70:
                return False, 0  # RSI عالي = خطر، لا تشتري
            
            support = self.get_support_level(current_price, analysis)
            if not support:
                return False, 0
            
            distance = support['distance']
            level = support['level']
            
            # إذا السعر قريب من مستوى دعم (أقل من tolerance%)
            if distance <= tolerance:
                # 👑 Dynamic Fibonacci (تطوير جريء)
                # لو فيه "قنص سيولة" أو "ارتباط عكسي"، الـ Fib يصبح مغناطيس حقيقي
                extra_multiplier = 1.0
                if volume_ratio > 2.0: extra_multiplier = 1.4
                
                if level in ['61.8', '50']:
                    base_boost = 22  # رفع القوة من 15 إلى 22
                elif level in ['38.2', '78.6']:
                    base_boost = 12  # رفع القوة من 8 إلى 12
                else:
                    base_boost = 5   # boost ضعيف (زيادة من 3)
                
                base_boost = int(base_boost * extra_multiplier)
                level_strength = self.get_level_strength(level)
                base_boost = int(base_boost * level_strength)
                
                # تعديل حسب Volume
                if volume_ratio > 1.5:
                    base_boost = int(base_boost * 1.3)  # volume عالي = أقوى
                elif volume_ratio < 0.8:
                    base_boost = int(base_boost * 0.8)  # volume ضعيف = أضعف
                
                # تعديل حسب العملة
                if 'BTC' in symbol or 'ETH' in symbol:
                    base_boost = int(base_boost * 1.2)  # العملات الكبيرة أقوى
                
                return True, base_boost
            
            return False, 0
        except:
            return False, 0
    
    def get_confidence_boost(self, current_price, analysis, volume_ratio=1.0, symbol=''):
        """حساب زيادة الثقة بناءً على فيبوناتشي (محسّن)"""
        try:
            at_support, boost = self.is_at_support(current_price, analysis, volume_ratio=volume_ratio, symbol=symbol)
            
            if at_support:
                return boost
            
            # إذا مو عند دعم، شوف المسافة
            support = self.get_support_level(current_price, analysis)
            if not support:
                return 0
            
            distance = support['distance']
            level = support['level']
            
            # إذا قريب من مستوى قوي (0.5-2%)
            if level in ['61.8', '50'] and 0.5 < distance <= 2.0:
                base_boost = 5  # boost صغير (زيادة من 3)
                
                # تعديل حسب قوة المستوى
                level_strength = self.get_level_strength(level)
                base_boost = int(base_boost * level_strength)
                
                return base_boost
            
            return 0
        except:
            return 0
    
    
    def get_stop_loss_level(self, entry_price, analysis):
        """تحديد Stop Loss تحت مستوى فيبوناتشي"""
        try:
            support = self.get_support_level(entry_price, analysis)
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