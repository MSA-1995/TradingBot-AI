"""
🐋 Smart Money Tracker
يكشف حركة الحيتان والأموال الذكية
"""

class SmartMoneyTracker:
    def __init__(self, exchange):
        self.exchange = exchange
        print("🐋 Smart Money Tracker initialized")
    
    def detect_whale_activity(self, symbol, analysis):
        """كشف نشاط الحيتان من حجم التداول"""
        try:
            avg_volume = analysis.get('volume_sma', 0)
            current_volume = analysis.get('volume', 0)
            
            if avg_volume == 0:
                return {'detected': False, 'confidence_boost': 0}

            # Volume Spike (زيادة مفاجئة في الحجم)
            volume_ratio = current_volume / avg_volume
            
            # Large Volume Spike = نشاط حيتان
            if volume_ratio >= 3.0:
                # تحقق من الاتجاه
                price_change = analysis.get('price_momentum', 0)
                
                if price_change > 0:
                    # حيتان تشتري = إشارة إيجابية
                    return {
                        'detected': True,
                        'type': 'BUY',
                        'volume_ratio': volume_ratio,
                        'confidence_boost': 15,
                        'reason': f'Whale buying detected ({volume_ratio:.1f}x volume)'
                    }
                else:
                    # حيتان تبيع = إشارة سلبية
                    return {
                        'detected': True,
                        'type': 'SELL',
                        'volume_ratio': volume_ratio,
                        'confidence_boost': -20,
                        'reason': f'Whale selling detected ({volume_ratio:.1f}x volume)'
                    }
            
            # Medium Volume Spike
            elif volume_ratio >= 2.0:
                price_change = analysis.get('price_momentum', 0)
                
                if price_change > 0:
                    return {
                        'detected': True,
                        'type': 'BUY',
                        'volume_ratio': volume_ratio,
                        'confidence_boost': 8,
                        'reason': f'Smart money accumulation ({volume_ratio:.1f}x volume)'
                    }
            
            return {'detected': False, 'confidence_boost': 0}
        
        except Exception as e:
            return {'detected': False, 'confidence_boost': 0}
    
    def analyze_order_flow(self, symbol, analysis):
        """تحليل تدفق الأوامر - تم تبسيطه ليعتمد على البيانات المتاحة"""
        try:
            price_trend = analysis.get('price_momentum', 0)
            volume_trend = analysis.get('volume_trend', 0)

            if price_trend > 0 and volume_trend > 0:
                # تراكم قوي
                if price_trend > 2 and volume_trend > 50:
                    return 10
                # تراكم متوسط
                elif price_trend > 1 and volume_trend > 30:
                    return 5
            
            # إذا السعر نازل والحجم يزيد = توزيع (Distribution)
            elif price_trend < 0 and volume_trend > 0:
                return -10
            
            return 0
        
        except:
            return 0
    
    def get_confidence_adjustment(self, symbol, analysis):
        """حساب تعديل الثقة بناءً على Smart Money"""
        try:
            if not analysis:
                return 0
            
            # كشف نشاط الحيتان
            whale_activity = self.detect_whale_activity(symbol, analysis)
            
            # تحليل تدفق الأوامر
            order_flow = self.analyze_order_flow(symbol, analysis)
            
            # الجمع
            total_adjustment = whale_activity['confidence_boost'] + order_flow
            
            # الحد الأقصى ±20
            total_adjustment = max(-20, min(20, total_adjustment))
            
            return total_adjustment
        
        except:
            return 0
    
    def should_avoid(self, symbol, analysis):
        """هل يجب تجنب العملة؟"""
        try:
            if not analysis:
                return False, ""
            
            whale_activity = self.detect_whale_activity(symbol, analysis)
            
            # إذا الحيتان تبيع بقوة
            if whale_activity['detected'] and whale_activity['type'] == 'SELL':
                if whale_activity['volume_ratio'] >= 4.0:
                    return True, whale_activity['reason']
            
            return False, ""
        
        except:
            return False, ""
