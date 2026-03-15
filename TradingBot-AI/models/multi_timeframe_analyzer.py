"""
📊 Multi-Timeframe Analyzer
يحلل 4 أطر زمنية (1m, 5m, 15m, 1h) ويعطي قرار موحد
"""

import pandas as pd
import ta
from datetime import datetime

class MultiTimeframeAnalyzer:
    def __init__(self, exchange):
        self.exchange = exchange
        # تحسين السرعة: تقليل الأطر الزمنية من 4 إلى 2 (5m, 15m فقط)
        self.timeframes = {
            '5m': {'weight': 0.40, 'limit': 50},
            '15m': {'weight': 0.60, 'limit': 50}
        }
        print("📊 Multi-Timeframe Analyzer initialized (Optimized: 2 timeframes)")
    
    def analyze(self, symbol):
        """تحليل شامل لجميع الأطر الزمنية"""
        try:
            results = {}
            total_score = 0
            total_weight = 0
            
            for tf, config in self.timeframes.items():
                analysis = self._analyze_timeframe(symbol, tf, config['limit'])
                if analysis:
                    results[tf] = analysis
                    weighted_score = analysis['score'] * config['weight']
                    total_score += weighted_score
                    total_weight += config['weight']
            
            if total_weight == 0:
                return None
            
            # حساب النتيجة النهائية
            final_score = total_score / total_weight
            
            # تحديد الاتجاه العام
            trend = self._determine_trend(results)
            
            # تحديد قوة الإشارة
            signal_strength = self._calculate_signal_strength(results)
            
            return {
                'timeframes': results,
                'final_score': round(final_score, 2),
                'trend': trend,
                'signal_strength': signal_strength,
                'confidence_boost': self._calculate_confidence_boost(final_score, trend, signal_strength)
            }
            
        except Exception as e:
            print(f"❌ MTF Analysis error {symbol}: {e}")
            return None
    
    def _analyze_timeframe(self, symbol, timeframe, limit):
        """تحليل إطار زمني واحد"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # المؤشرات الفنية
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_diff'] = macd.macd_diff()
            
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=min(50, len(df))).mean()
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            latest = df.iloc[-1]
            
            # حساب النقاط
            score = 0
            signals = []
            
            # RSI
            rsi = latest['rsi']
            if pd.notna(rsi):
                if rsi < 30:
                    score += 30
                    signals.append('RSI Oversold')
                elif rsi < 40:
                    score += 20
                    signals.append('RSI Low')
                elif rsi > 70:
                    score -= 20
                    signals.append('RSI Overbought')
                elif rsi > 60:
                    score -= 10
            
            # MACD
            macd_diff = latest['macd_diff']
            if pd.notna(macd_diff):
                if macd_diff > 0:
                    score += 20
                    signals.append('MACD Bullish')
                else:
                    score -= 10
            
            # Moving Averages
            close = latest['close']
            sma_20 = latest['sma_20']
            sma_50 = latest['sma_50']
            
            if pd.notna(sma_20) and pd.notna(sma_50):
                if close > sma_20 > sma_50:
                    score += 25
                    signals.append('Bullish Trend')
                elif close < sma_20 < sma_50:
                    score -= 25
                    signals.append('Bearish Trend')
                elif close > sma_20:
                    score += 10
                    signals.append('Above SMA20')
            
            # EMA Cross
            ema_12 = latest['ema_12']
            ema_26 = latest['ema_26']
            
            if pd.notna(ema_12) and pd.notna(ema_26):
                if ema_12 > ema_26:
                    score += 15
                    signals.append('EMA Bullish')
                else:
                    score -= 10
            
            # Volume
            if len(df) >= 20:
                volume_sma = df['volume'].rolling(window=20).mean().iloc[-1]
                volume_ratio = latest['volume'] / volume_sma if volume_sma > 0 else 1.0
                
                if volume_ratio > 1.5:
                    score += 10
                    signals.append('High Volume')
                elif volume_ratio < 0.7:
                    score -= 5
            
            # تحديد الاتجاه
            if score > 30:
                trend = 'bullish'
            elif score < -10:
                trend = 'bearish'
            else:
                trend = 'neutral'
            
            return {
                'score': score,
                'trend': trend,
                'rsi': rsi,
                'macd_diff': macd_diff,
                'signals': signals,
                'close': close
            }
            
        except Exception as e:
            print(f"❌ Error analyzing {timeframe}: {e}")
            return None
    
    def _determine_trend(self, results):
        """تحديد الاتجاه العام من جميع الأطر"""
        bullish = sum(1 for r in results.values() if r['trend'] == 'bullish')
        bearish = sum(1 for r in results.values() if r['trend'] == 'bearish')
        
        # تحسين: 2 أطر زمنية فقط
        if bullish >= 2:
            return 'strong_bullish'
        elif bullish >= 1:
            return 'bullish'
        elif bearish >= 2:
            return 'strong_bearish'
        elif bearish >= 1:
            return 'bearish'
        else:
            return 'neutral'
    
    def _calculate_signal_strength(self, results):
        """حساب قوة الإشارة (0-100)"""
        if not results:
            return 0
        
        # عدد الأطر الإيجابية
        positive_frames = sum(1 for r in results.values() if r['score'] > 20)
        
        # متوسط النقاط
        avg_score = sum(r['score'] for r in results.values()) / len(results)
        
        # قوة الإشارة
        strength = (positive_frames / len(results)) * 50 + (min(avg_score, 50) / 50) * 50
        
        return round(strength, 2)
    
    def _calculate_confidence_boost(self, final_score, trend, signal_strength):
        """حساب تعزيز الثقة"""
        boost = 0
        
        # تعزيز حسب النقاط
        if final_score > 50:
            boost += 10
        elif final_score > 30:
            boost += 5
        elif final_score < -20:
            boost -= 10
        
        # تعزيز حسب الاتجاه
        if trend == 'strong_bullish':
            boost += 8
        elif trend == 'bullish':
            boost += 5
        elif trend == 'strong_bearish':
            boost -= 8
        elif trend == 'bearish':
            boost -= 5
        
        # تعزيز حسب قوة الإشارة
        if signal_strength > 80:
            boost += 5
        elif signal_strength > 60:
            boost += 3
        elif signal_strength < 30:
            boost -= 5
        
        return boost
    
    def get_best_entry_point(self, symbol):
        """تحديد أفضل نقطة دخول"""
        analysis = self.analyze(symbol)
        
        if not analysis:
            return None
        
        # شروط الدخول المثالية
        ideal_conditions = {
            'final_score': analysis['final_score'] > 30,
            'trend': analysis['trend'] in ['bullish', 'strong_bullish'],
            'signal_strength': analysis['signal_strength'] > 60,
            'all_timeframes_positive': all(
                r['score'] > 10 for r in analysis['timeframes'].values()
            )
        }
        
        conditions_met = sum(ideal_conditions.values())
        
        if conditions_met >= 3:
            return {
                'entry': 'EXCELLENT',
                'confidence_boost': analysis['confidence_boost'] + 5,
                'conditions_met': conditions_met
            }
        elif conditions_met >= 2:
            return {
                'entry': 'GOOD',
                'confidence_boost': analysis['confidence_boost'],
                'conditions_met': conditions_met
            }
        else:
            return {
                'entry': 'POOR',
                'confidence_boost': analysis['confidence_boost'] - 5,
                'conditions_met': conditions_met
            }
