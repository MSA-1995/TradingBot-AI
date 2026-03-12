"""
🚨 Anomaly Detection Model
يكتشف الحركات الغريبة: Pump & Dump, Flash Crash, Whale Movements
"""

import statistics
from datetime import datetime, timedelta

class AnomalyDetector:
    def __init__(self, exchange):
        self.exchange = exchange
        self.anomaly_history = []
        print("🚨 Anomaly Detector initialized")
    
    def detect_anomalies(self, symbol, analysis):
        """كشف الشذوذات في العملة"""
        try:
            anomalies = []
            severity = 'NORMAL'
            
            # 1. فحص Pump (ارتفاع مفاجئ)
            pump_detected = self._detect_pump(symbol, analysis)
            if pump_detected:
                anomalies.append(pump_detected)
                severity = 'HIGH'
            
            # 2. فحص Dump (انخفاض مفاجئ)
            dump_detected = self._detect_dump(symbol, analysis)
            if dump_detected:
                anomalies.append(dump_detected)
                severity = 'HIGH'
            
            # 3. فحص Volume الشاذ
            volume_anomaly = self._detect_volume_anomaly(analysis)
            if volume_anomaly:
                anomalies.append(volume_anomaly)
                if severity == 'NORMAL':
                    severity = 'MEDIUM'
            
            # 4. فحص Volatility العالية
            volatility_anomaly = self._detect_high_volatility(symbol)
            if volatility_anomaly:
                anomalies.append(volatility_anomaly)
                if severity == 'NORMAL':
                    severity = 'MEDIUM'
            
            # 5. فحص Price Manipulation
            manipulation = self._detect_manipulation(symbol, analysis)
            if manipulation:
                anomalies.append(manipulation)
                severity = 'CRITICAL'
            
            result = {
                'symbol': symbol,
                'anomalies': anomalies,
                'severity': severity,
                'safe_to_trade': severity in ['NORMAL', 'LOW', 'MEDIUM'],  # Changed: accept MEDIUM
                'timestamp': datetime.now().isoformat()
            }
            
            # حفظ في التاريخ
            if anomalies:
                self.anomaly_history.append(result)
                # الاحتفاظ بآخر 100 شذوذ فقط
                if len(self.anomaly_history) > 100:
                    self.anomaly_history = self.anomaly_history[-100:]
            
            return result
            
        except Exception as e:
            print(f"⚠️ Anomaly detection error {symbol}: {e}")
            return {
                'symbol': symbol,
                'anomalies': [],
                'severity': 'NORMAL',
                'safe_to_trade': True
            }
    
    def _detect_pump(self, symbol, analysis):
        """كشف Pump (ارتفاع مفاجئ وسريع)"""
        try:
            df = analysis.get('df')
            if df is None or len(df) < 10:
                return None
            
            # حساب التغير في آخر 5 شموع
            recent_change = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
            
            # حساب التغير في آخر 10 شموع
            medium_change = ((df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10]) * 100
            
            # Volume spike
            volume_ratio = analysis.get('volume_ratio', 1.0)
            
            # Pump conditions:
            # 1. ارتفاع سريع > 5% في 5 شموع
            # 2. Volume عالي جداً > 3x
            # 3. RSI > 75 (overbought)
            
            if recent_change > 5 and volume_ratio > 3 and analysis.get('rsi', 50) > 75:
                return {
                    'type': 'PUMP',
                    'description': f'Sudden price spike +{recent_change:.1f}% with {volume_ratio:.1f}x volume',
                    'risk': 'HIGH',
                    'action': 'AVOID_BUY'
                }
            
            # Pump متوسط
            if recent_change > 3 and volume_ratio > 2.5:
                return {
                    'type': 'PUMP_WARNING',
                    'description': f'Price rising fast +{recent_change:.1f}%',
                    'risk': 'MEDIUM',
                    'action': 'CAUTION'
                }
            
            return None
            
        except Exception as e:
            return None
    
    def _detect_dump(self, symbol, analysis):
        """كشف Dump (انخفاض مفاجئ وسريع)"""
        try:
            df = analysis.get('df')
            if df is None or len(df) < 10:
                return None
            
            # حساب التغير في آخر 5 شموع
            recent_change = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]) * 100
            
            # Volume spike
            volume_ratio = analysis.get('volume_ratio', 1.0)
            
            # Dump conditions:
            # 1. انخفاض سريع > -5% في 5 شموع
            # 2. Volume عالي جداً > 3x
            # 3. RSI < 25 (oversold extreme)
            
            if recent_change < -5 and volume_ratio > 3 and analysis.get('rsi', 50) < 25:
                return {
                    'type': 'DUMP',
                    'description': f'Flash crash {recent_change:.1f}% with {volume_ratio:.1f}x volume',
                    'risk': 'CRITICAL',
                    'action': 'AVOID_BUY'
                }
            
            # Dump متوسط (ممكن فرصة شراء)
            if recent_change < -3 and volume_ratio > 2:
                return {
                    'type': 'DUMP_WARNING',
                    'description': f'Sharp decline {recent_change:.1f}%',
                    'risk': 'MEDIUM',
                    'action': 'WAIT_STABILIZE'
                }
            
            return None
            
        except Exception as e:
            return None
    
    def _detect_volume_anomaly(self, analysis):
        """كشف Volume الشاذ"""
        try:
            volume_ratio = analysis.get('volume_ratio', 1.0)
            
            # Volume شاذ جداً
            if volume_ratio > 5:
                return {
                    'type': 'EXTREME_VOLUME',
                    'description': f'Unusual volume spike {volume_ratio:.1f}x normal',
                    'risk': 'HIGH',
                    'action': 'INVESTIGATE'
                }
            
            # Volume منخفض جداً
            if volume_ratio < 0.3:
                return {
                    'type': 'LOW_VOLUME',
                    'description': f'Very low volume {volume_ratio:.1f}x normal',
                    'risk': 'MEDIUM',
                    'action': 'AVOID_LOW_LIQUIDITY'
                }
            
            return None
            
        except:
            return None
    
    def _detect_high_volatility(self, symbol):
        """كشف التقلب العالي"""
        try:
            # جلب بيانات آخر ساعة
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=12)
            
            if len(ohlcv) < 12:
                return None
            
            # حساب التقلب (range)
            highs = [candle[2] for candle in ohlcv]
            lows = [candle[3] for candle in ohlcv]
            closes = [candle[4] for candle in ohlcv]
            
            avg_close = statistics.mean(closes)
            ranges = [(h - l) / avg_close * 100 for h, l in zip(highs, lows)]
            avg_range = statistics.mean(ranges)
            
            # تقلب عالي جداً
            if avg_range > 2:
                return {
                    'type': 'HIGH_VOLATILITY',
                    'description': f'High volatility {avg_range:.2f}% average range',
                    'risk': 'HIGH',
                    'action': 'TIGHT_STOP_LOSS'
                }
            
            return None
            
        except:
            return None
    
    def _detect_manipulation(self, symbol, analysis):
        """كشف التلاعب بالسعر"""
        try:
            df = analysis.get('df')
            if df is None or len(df) < 20:
                return None
            
            # فحص الشموع المتطابقة (ممكن تلاعب)
            recent_closes = df['close'].tail(10).tolist()
            
            # لو فيه 5 شموع متطابقة تقريباً
            if len(set([round(c, 4) for c in recent_closes])) <= 3:
                return {
                    'type': 'PRICE_MANIPULATION',
                    'description': 'Suspicious price pattern detected',
                    'risk': 'CRITICAL',
                    'action': 'AVOID'
                }
            
            # فحص Wick الطويل جداً (ممكن Stop Loss hunting)
            for i in range(-5, 0):
                candle = df.iloc[i]
                body = abs(candle['close'] - candle['open'])
                upper_wick = candle['high'] - max(candle['close'], candle['open'])
                lower_wick = min(candle['close'], candle['open']) - candle['low']
                
                # لو الـ wick أطول من الـ body بـ 5 مرات
                if body > 0 and (upper_wick > body * 5 or lower_wick > body * 5):
                    return {
                        'type': 'WICK_MANIPULATION',
                        'description': 'Extreme wick detected (possible stop hunting)',
                        'risk': 'HIGH',
                        'action': 'CAUTION'
                    }
            
            return None
            
        except:
            return None
    
    def get_recent_anomalies(self, symbol=None, hours=24):
        """الحصول على الشذوذات الأخيرة"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            recent = [
                a for a in self.anomaly_history
                if datetime.fromisoformat(a['timestamp']) > cutoff
            ]
            
            if symbol:
                recent = [a for a in recent if a['symbol'] == symbol]
            
            return recent
            
        except:
            return []
    
    def is_coin_safe(self, symbol):
        """هل العملة آمنة للتداول؟"""
        # فحص آخر ساعة
        recent_anomalies = self.get_recent_anomalies(symbol, hours=1)
        
        if not recent_anomalies:
            return {'safe': True, 'reason': 'No recent anomalies'}
        
        # فحص الخطورة
        latest = recent_anomalies[-1]
        
        if latest['severity'] in ['CRITICAL', 'HIGH']:
            return {
                'safe': False,
                'reason': f"{latest['severity']} anomaly detected",
                'details': latest['anomalies']
            }
        
        return {
            'safe': True,
            'reason': 'Minor anomalies only',
            'caution': True
        }
    
    def get_anomaly_report(self):
        """تقرير شامل عن الشذوذات"""
        try:
            recent = self.get_recent_anomalies(hours=24)
            
            if not recent:
                return {
                    'total_anomalies': 0,
                    'critical': 0,
                    'high': 0,
                    'medium': 0
                }
            
            critical = sum(1 for a in recent if a['severity'] == 'CRITICAL')
            high = sum(1 for a in recent if a['severity'] == 'HIGH')
            medium = sum(1 for a in recent if a['severity'] == 'MEDIUM')
            
            # أكثر العملات شذوذاً
            coin_counts = {}
            for a in recent:
                symbol = a['symbol']
                coin_counts[symbol] = coin_counts.get(symbol, 0) + 1
            
            most_anomalous = sorted(coin_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                'total_anomalies': len(recent),
                'critical': critical,
                'high': high,
                'medium': medium,
                'most_anomalous_coins': most_anomalous,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ Anomaly report error: {e}")
            return None
