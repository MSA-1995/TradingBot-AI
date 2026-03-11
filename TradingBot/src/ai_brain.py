"""
AI Brain - العقل المفكر
يقرر، يتعلم، يتحسن (ضمن الحدود الآمنة)
"""
from datetime import datetime
import sys
sys.path.append('..')
from storage.storage_manager import StorageManager

class AIBrain:
    def __init__(self, boundaries):
        self.storage = StorageManager()
        self.boundaries = boundaries
        self.learned_patterns = []
        self.trap_memory = []
        
        # تحميل المعرفة السابقة
        self.load_knowledge()
        
        print("🧠 AI Brain initialized")
        print(f"📊 Loaded {len(self.learned_patterns)} patterns")
        print(f"🚫 Loaded {len(self.trap_memory)} traps")
    
    def load_knowledge(self):
        """تحميل المعرفة من التخزين"""
        try:
            self.learned_patterns = self.storage.load_patterns()
            self.trap_memory = self.storage.load_traps()
        except Exception as e:
            print(f"⚠️ Error loading knowledge: {e}")
            self.learned_patterns = []
            self.trap_memory = []
    
    def should_buy(self, symbol, analysis, mtf, price_drop):
        """
        القرار الذكي: هل نشتري؟
        يحلل، يتذكر، يقرر (ضمن الحدود)
        """
        from learning.safety_validator import SafetyValidator
        from learning.pattern_detector import PatternDetector
        
        # 1. التحليل الأساسي
        base_confidence = self._calculate_base_confidence(analysis, mtf, price_drop)
        
        # 2. فحص الفخاخ
        if self._is_trap_pattern(symbol, analysis):
            decision = {
                'action': 'SKIP',
                'reason': 'Matches known trap pattern',
                'confidence': 0
            }
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'SKIP',
                'reason': 'Trap detected',
                'confidence': base_confidence
            })
            return decision
        
        # 3. البحث عن أنماط مشابهة ناجحة
        similar_success = self._find_similar_patterns(analysis, pattern_type='SUCCESS')
        
        # 4. تحسين الـ Confidence بناءً على التعلم
        optimized_confidence = self._optimize_confidence(
            base_confidence, 
            similar_success
        )
        
        # 5. التحقق من الحدود الآمنة
        validator = SafetyValidator(self.boundaries)
        is_safe = validator.validate_decision({
            'confidence': optimized_confidence,
            'volume': analysis['volume_ratio'],
            'rsi': analysis['rsi'],
            'macd': analysis['macd_diff']
        })
        
        if not is_safe:
            decision = {
                'action': 'SKIP',
                'reason': 'Failed safety validation',
                'confidence': optimized_confidence
            }
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'SKIP',
                'reason': 'Safety check failed',
                'confidence': optimized_confidence
            })
            return decision
        
        # 6. القرار النهائي
        if optimized_confidence >= 60:  # استخدام 60 (الحد الجديد)
            # حساب المبلغ الذكي
            amount = self._calculate_smart_amount(optimized_confidence)
            
            # حساب TP و SL الذكي
            smart_targets = self._calculate_smart_targets(optimized_confidence, analysis, similar_success)
            
            decision = {
                'action': 'BUY',
                'confidence': optimized_confidence,
                'amount': amount,
                'tp_target': smart_targets['tp'],
                'sl_target': smart_targets['sl'],
                'max_wait_hours': smart_targets['wait_hours'],
                'reason': f'AI optimized from {base_confidence} to {optimized_confidence}',
                'success_probability': self._estimate_success_probability(similar_success)
            }
            
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'BUY',
                'confidence': optimized_confidence,
                'amount': amount,
                'tp_target': smart_targets['tp'],
                'sl_target': smart_targets['sl'],
                'max_wait_hours': smart_targets['wait_hours'],
                'base_confidence': base_confidence,
                'reasoning': decision['reason']
            })
            
            return decision
        else:
            decision = {
                'action': 'SKIP',
                'reason': f'Confidence {optimized_confidence} < 60',
                'confidence': optimized_confidence
            }
            return decision
    
    def _calculate_base_confidence(self, analysis, mtf, price_drop):
        """حساب Confidence الأساسي (نفس النظام الحالي)"""
        import pandas as pd
        
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        momentum = analysis.get('price_momentum', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        trend = mtf.get('trend', 'neutral')
        drop_percent = price_drop.get('drop_percent', 0)
        
        # Handle NaN values
        if pd.isna(rsi):
            rsi = 50
        if pd.isna(macd_diff):
            macd_diff = 0
        if pd.isna(momentum):
            momentum = 0
        if pd.isna(volume_ratio) or volume_ratio <= 0:
            volume_ratio = 1.0
        if pd.isna(drop_percent):
            drop_percent = 0
        
        confidence = 0
        
        # RSI
        if rsi < 25:
            confidence += 30
        elif rsi < 30:
            confidence += 25
        elif rsi < 35:
            confidence += 20
        elif rsi < 40:
            confidence += 15
        elif rsi < 45:
            confidence += 10
        else:
            confidence += 5
        
        # Volume
        if pd.isna(volume_ratio) or volume_ratio <= 0:
            volume_points = 0
        else:
            volume_points = min(int((volume_ratio - 0.6) * 20), 25)
        confidence += volume_points
        
        # Trend
        if trend == 'bullish':
            confidence += 20
        elif trend == 'neutral':
            confidence += 10
        
        # MACD
        if macd_diff > 5:
            confidence += 15
        elif macd_diff > 0:
            confidence += 10
        else:
            confidence += 5
        
        # Momentum
        if momentum < -5:
            confidence += 15
        elif momentum < -3:
            confidence += 12
        elif momentum < -2:
            confidence += 8
        
        # Price Drop
        if drop_percent >= 3:
            confidence += 15
        elif drop_percent >= 2:
            confidence += 10
        elif drop_percent >= 1:
            confidence += 5
        
        return confidence
    
    def _is_trap_pattern(self, symbol, analysis):
        """فحص إذا كان النمط يشبه فخ سابق"""
        for trap in self.trap_memory:
            similarity = self._calculate_similarity(analysis, trap.get('pattern', {}))
            if similarity > 0.85:  # 85% مشابه
                return True
        return False
    
    def _find_similar_patterns(self, analysis, pattern_type='SUCCESS'):
        """البحث عن أنماط مشابهة"""
        similar = []
        for pattern in self.learned_patterns:
            if pattern.get('type') == pattern_type:
                similarity = self._calculate_similarity(analysis, pattern.get('conditions', {}))
                if similarity > 0.7:  # 70% مشابه
                    similar.append({
                        'pattern': pattern,
                        'similarity': similarity
                    })
        return similar
    
    def _calculate_similarity(self, current, stored):
        """حساب التشابه بين نمطين"""
        if not stored:
            return 0
        
        score = 0
        count = 0
        
        # مقارنة RSI
        if 'rsi' in stored and 'rsi' in current:
            diff = abs(current['rsi'] - stored['rsi'])
            score += max(0, 1 - diff / 100)
            count += 1
        
        # مقارنة Volume
        if 'volume_ratio' in stored and 'volume_ratio' in current:
            diff = abs(current['volume_ratio'] - stored['volume_ratio'])
            score += max(0, 1 - diff / 2)
            count += 1
        
        # مقارنة MACD
        if 'macd_diff' in stored and 'macd_diff' in current:
            diff = abs(current['macd_diff'] - stored['macd_diff'])
            score += max(0, 1 - diff / 50)
            count += 1
        
        return score / count if count > 0 else 0
    
    def _optimize_confidence(self, base_confidence, similar_patterns):
        """تحسين Confidence بناءً على الأنماط المشابهة"""
        if not similar_patterns:
            return base_confidence
        
        # حساب متوسط نجاح الأنماط المشابهة
        total_success = sum(p['pattern'].get('success_rate', 0) for p in similar_patterns)
        avg_success = total_success / len(similar_patterns)
        
        # تعديل Confidence
        if avg_success > 0.85:  # نجاح عالي
            adjustment = 3
        elif avg_success > 0.75:
            adjustment = 2
        elif avg_success < 0.60:  # نجاح منخفض
            adjustment = -5
        else:
            adjustment = 0
        
        optimized = base_confidence + adjustment
        
        # التأكد من البقاء ضمن الحدود (60-75)
        optimized = max(60, optimized)
        optimized = min(75, optimized)
        
        return optimized
    
    def _calculate_smart_amount(self, confidence):
        """حساب المبلغ الذكي بناءً على Confidence"""
        if confidence >= 110:
            return 20
        elif confidence >= 100:
            return 18
        elif confidence >= 90:
            return 16
        elif confidence >= 80:
            return 14
        elif confidence >= 70:
            return 12
        else:
            return 10
    
    def _estimate_success_probability(self, similar_patterns):
        """تقدير احتمال النجاح"""
        if not similar_patterns:
            return 0.5  # 50% افتراضي
        
        total_success = sum(p['pattern'].get('success_rate', 0.5) for p in similar_patterns)
        return total_success / len(similar_patterns)
    
    def learn_from_trade(self, trade_result):
        """
        التعلم من صفقة (يُستدعى بعد كل بيع)
        """
        from learning.pattern_detector import PatternDetector
        
        # حفظ الصفقة
        self.storage.save_trade(trade_result)
        
        # استخراج النمط
        detector = PatternDetector()
        pattern = detector.extract_pattern(trade_result)
        
        if pattern:
            # حفظ النمط
            self.storage.save_pattern(pattern)
            
            # تحديث الذاكرة
            if pattern['type'] == 'SUCCESS':
                self.learned_patterns.append(pattern)
                print(f"✅ Learned success pattern: {pattern.get('summary', '')}")
            elif pattern['type'] == 'TRAP':
                self.trap_memory.append(pattern)
                self.storage.save_trap(pattern)
                print(f"🚫 Learned trap pattern: {pattern.get('summary', '')}")
        
        return pattern

    
    def _calculate_smart_targets(self, confidence, analysis, similar_patterns):
        """حساب TP و SL والانتظار بذكاء"""
        import pandas as pd
        
        # الافتراضي
        tp = 1.0
        sl = 2.0
        wait_hours = 48
        
        # تعديل حسب Confidence
        if confidence >= 70:
            tp = 1.5  # هدف أعلى
            sl = 2.5  # صبر أكثر
            wait_hours = 72  # انتظار أطول
        elif confidence >= 65:
            tp = 1.2
            sl = 2.0
            wait_hours = 60
        else:  # 60-64
            tp = 0.8  # هدف سريع
            sl = 1.5  # حماية سريعة
            wait_hours = 36  # انتظار أقل
        
        # تعديل حسب RSI (Oversold)
        rsi = analysis.get('rsi', 50)
        if not pd.isna(rsi):
            if rsi < 25:  # oversold جداً
                tp += 0.3  # فرصة ارتداد قوي
                wait_hours += 12
            elif rsi < 30:
                tp += 0.2
                wait_hours += 6
        
        # تعديل حسب الأنماط المشابهة
        if similar_patterns:
            avg_profit = sum(p['pattern'].get('avg_profit', 1.0) for p in similar_patterns) / len(similar_patterns)
            if avg_profit > 1.5:
                tp = min(tp + 0.3, 2.0)  # لا يتجاوز 2%
        
        # تعديل حسب Volume
        volume_ratio = analysis.get('volume_ratio', 1.0)
        if not pd.isna(volume_ratio):
            if volume_ratio > 2.0:  # حجم عالي جداً = خطر
                sl = max(sl - 0.3, 1.2)  # حماية أسرع
                wait_hours = max(wait_hours - 12, 24)
        
        return {
            'tp': round(tp, 1),
            'sl': round(sl, 1),
            'wait_hours': int(wait_hours)
        }
    
    def should_sell(self, symbol, position, current_price, analysis, mtf):
        """القرار الذكي: هل نبيع؟"""
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        
        # الأهداف الذكية من وقت الشراء
        tp_target = position.get('tp_target', 1.0)
        sl_target = position.get('sl_target', 2.0)
        max_wait_hours = position.get('max_wait_hours', 48)
        
        # حساب المدة
        from datetime import datetime
        buy_time = datetime.fromisoformat(position['buy_time'])
        hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        
        # 1. TP الذكي
        if profit_percent >= tp_target:
            return {
                'action': 'SELL',
                'reason': f'SMART TP {tp_target}%',
                'profit': profit_percent
            }
        
        # 2. Bearish Exit
        if mtf['trend'] == 'bearish' and mtf['total'] >= 2:
            return {
                'action': 'SELL',
                'reason': 'BEARISH TREND',
                'profit': profit_percent
            }
        
        # 3. Stop Loss الذكي
        highest_price = position.get('highest_price', buy_price)
        trailing_stop = highest_price * (1 - sl_target / 100)
        
        if current_price <= trailing_stop:
            # فحص ذكي قبل البيع
            rsi = analysis.get('rsi', 50)
            macd_diff = analysis.get('macd_diff', 0)
            
            # لو السوق قوي - لا تبيع
            if profit_percent > 0 and rsi > 50 and macd_diff > 0:
                return {'action': 'HOLD', 'reason': 'Market still strong'}
            
            return {
                'action': 'SELL',
                'reason': f'SMART SL {sl_target}%',
                'profit': profit_percent
            }
        
        # 4. انتهى وقت الانتظار
        if hours_held >= max_wait_hours and profit_percent < 0:
            return {
                'action': 'SELL',
                'reason': f'TIMEOUT {max_wait_hours}h',
                'profit': profit_percent
            }
        
        # 5. Hold
        return {'action': 'HOLD', 'reason': 'Waiting for target'}
