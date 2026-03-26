"""
🐋 Smart Money Tracker
يكشف حركة الحيتان والأموال الذكية
"""

class SmartMoneyTracker:
    def __init__(self, exchange):
        self.exchange = exchange
        print("🐋 Smart Money Tracker initialized")
    
    def detect_whale_activity(self, symbol, df):
        """كشف نشاط الحيتان من حجم التداول"""
        try:
            if len(df) < 20:
                return {'detected': False, 'confidence_boost': 0}
            
            # حساب متوسط الحجم
            avg_volume = df['volume'].tail(20).mean()
            current_volume = df['volume'].iloc[-1]
            
            # Volume Spike (زيادة مفاجئة في الحجم)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Large Volume Spike = نشاط حيتان
            if volume_ratio >= 3.0:
                # تحقق من الاتجاه
                price_change = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
                
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
                price_change = ((df['close'].iloc[-1] - df['close'].iloc[-3]) / df['close'].iloc[-3]) * 100
                
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
    
    def analyze_order_flow(self, symbol, df):
        """تحليل تدفق الأوامر"""
        try:
            if len(df) < 10:
                return 0
            
            # حساب Price-Volume Trend
            recent_df = df.tail(10)
            
            # إذا السعر طالع والحجم يزيد = تراكم (Accumulation)
            first_close = recent_df['close'].iloc[0]
            first_volume = recent_df['volume'].iloc[0]
            
            if first_close == 0 or first_volume == 0:
                return 0
            
            price_trend = (recent_df['close'].iloc[-1] - first_close) / first_close
            volume_trend = (recent_df['volume'].iloc[-1] - first_volume) / first_volume
            
            if price_trend > 0 and volume_trend > 0:
                # تراكم قوي
                if price_trend > 0.02 and volume_trend > 0.5:
                    return 10
                # تراكم متوسط
                elif price_trend > 0.01 and volume_trend > 0.3:
                    return 5
            
            # إذا السعر نازل والحجم يزيد = توزيع (Distribution)
            elif price_trend < 0 and volume_trend > 0:
                return -10
            
            return 0
        
        except:
            return 0
    
    def get_confidence_adjustment(self, symbol, df):
        """حساب تعديل الثقة بناءً على Smart Money"""
        try:
            if df is None or len(df) < 20:
                return 0
            
            # كشف نشاط الحيتان
            whale_activity = self.detect_whale_activity(symbol, df)
            
            # تحليل تدفق الأوامر
            order_flow = self.analyze_order_flow(symbol, df)
            
            # الجمع
            total_adjustment = whale_activity['confidence_boost'] + order_flow
            
            # الحد الأقصى ±20
            total_adjustment = max(-20, min(20, total_adjustment))
            
            return total_adjustment
        
        except:
            return 0
    
    def should_avoid(self, symbol, df):
        """هل يجب تجنب العملة؟"""
        try:
            if df is None:
                return False, ""
            
            whale_activity = self.detect_whale_activity(symbol, df)
            
            # إذا الحيتان تبيع بقوة
            if whale_activity['detected'] and whale_activity['type'] == 'SELL':
                if whale_activity['volume_ratio'] >= 4.0:
                    return True, whale_activity['reason']
            
            return False, ""
        
        except:
            return False, ""
