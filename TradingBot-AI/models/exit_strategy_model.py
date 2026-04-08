"""
🎯 Exit Strategy Model
يحسن توقيت البيع ويزيد الأرباح
"""

from datetime import datetime, timedelta
import statistics

class ExitStrategyModel:
    def __init__(self, storage):
        self.storage = storage
        self.exit_patterns = {} # This is no longer used for learning, but can be kept for other analytics if needed.
        print("🎯 Exit Strategy Model initialized")
    
    def should_exit(self, symbol, position, current_price, analysis, mtf):
        """قرار البيع الذكي"""
        try:
            buy_price = position['buy_price']
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            
            # جلب تاريخ العملة
            coin_history = self._get_coin_exit_history(symbol)
            
            # 1. فحص TP الذكي
            tp_decision = self._check_smart_tp(
                symbol, profit_percent, position, 
                analysis, mtf, coin_history
            )
            if tp_decision['action'] == 'SELL':
                return tp_decision
            
            # 2. فحص Trailing Stop الذكي
            trailing_decision = self._check_smart_trailing(
                symbol, current_price, position, 
                analysis, coin_history
            )
            if trailing_decision['action'] == 'SELL':
                return trailing_decision
            
            # 3. فحص Bearish Exit الذكي
            bearish_decision = self._check_smart_bearish(
                symbol, profit_percent, mtf, 
                analysis, coin_history
            )
            if bearish_decision['action'] == 'SELL':
                return bearish_decision
            
            # 4. فحص Time-based Exit
            time_decision = self._check_time_exit(
                symbol, position, profit_percent, coin_history
            )
            if time_decision['action'] == 'SELL':
                return time_decision

            # 5. فحص Exit بسبب الأخبار السلبية
            news_exit_decision = self._check_news_exit(symbol, profit_percent, analysis)
            if news_exit_decision['action'] == 'SELL':
                return news_exit_decision

            # 6. Hold
            return {
                'action': 'HOLD',
                'reason': 'Waiting for better exit',
                'confidence': self._calculate_hold_confidence(
                    profit_percent, analysis, mtf
                )
            }
            
        except Exception as e:
            print(f"⚠️ Exit strategy error {symbol}: {e}")
            return {'action': 'HOLD', 'reason': 'Error in analysis'}
    
    def _check_smart_tp(self, symbol, profit_percent, position, analysis, mtf, history):
        """فحص TP الذكي - محسّن للسرعة"""
        try:
            # TP الافتراضي
            tp_target = position.get('tp_target', 1.0)
            
            # تعديل TP حسب تاريخ العملة
            if history and history['avg_profit'] > 0:
                # لو العملة عادة تربح أكثر، نرفع TP
                if history['avg_profit'] > 2.0:
                    tp_target = max(tp_target, 1.5)
                elif history['avg_profit'] > 1.5:
                    tp_target = max(tp_target, 1.2)
            
            # فحص الوصول للهدف
            if profit_percent >= tp_target:
                # فحص إذا السوق لسه قوي
                rsi = analysis.get('rsi', 50)
                macd_diff = analysis.get('macd_diff', 0)
                trend = mtf.get('trend', 'neutral')
                
                # تحسين: نبيع أسرع - إذا الربح > TP + 0.3% نبيع مباشرة
                if profit_percent >= tp_target + 0.3:
                    return {
                        'action': 'SELL',
                        'reason': f'HIGH PROFIT {profit_percent:.1f}%',
                        'profit': profit_percent,
                        'confidence': 95
                    }
                
                # لو السوق قوي جداً والربح قريب من TP، ننتظر شوي
                market_very_strong = (
                    (rsi < 65 and macd_diff > 2) and  # RSI معقول و MACD قوي
                    (trend == 'strong_bullish')  # الاتجاه صاعد قوي
                )
                
                if market_very_strong and profit_percent < tp_target + 0.2:
                    return {
                        'action': 'HOLD',
                        'reason': f'TP {tp_target}% reached but market very strong'
                    }
                
                # وإلا نبيع
                return {
                    'action': 'SELL',
                    'reason': f'SMART TP {tp_target}%',
                    'profit': profit_percent,
                    'confidence': 95
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _check_smart_trailing(self, symbol, current_price, position, analysis, history):
        """فحص Trailing Stop الذكي - محذوف (مدمج في AI Brain)"""
        return {'action': 'HOLD'}
    
    def _check_smart_bearish(self, symbol, profit_percent, mtf, analysis, history):
        """فحص Bearish Exit الذكي - محسّن للسرعة"""
        try:
            trend = mtf.get('trend', 'neutral')
            
            # Bearish قوي
            if trend in ['bearish', 'strong_bearish']:
                # تحسين: نبيع بربح أقل (0.2% بدل 0.3%)
                if profit_percent > 0.2:
                    return {
                        'action': 'SELL',
                        'reason': 'BEARISH TREND',
                        'profit': profit_percent,
                        'confidence': 85
                    }
                
                # لو الخسارة صغيرة والسوق bearish جداً
                if profit_percent > -0.8 and trend == 'strong_bearish':
                    return {
                        'action': 'SELL',
                        'reason': 'STRONG BEARISH',
                        'profit': profit_percent,
                        'confidence': 80
                    }
            
            # فحص RSI + MACD معاً
            rsi = analysis.get('rsi', 50)
            macd_diff = analysis.get('macd_diff', 0)
            
            # تحسين: نخفض الحدود للبيع الأسرع
            if rsi > 68 and macd_diff < -2 and profit_percent > 0.15:
                return {
                    'action': 'SELL',
                    'reason': 'OVERBOUGHT + BEARISH MACD',
                    'profit': profit_percent,
                    'confidence': 85
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _check_time_exit(self, symbol, position, profit_percent, history):
        """فحص Time-based Exit"""
        try:
            buy_time = datetime.fromisoformat(position['buy_time'])
            hours_held = (datetime.now() - buy_time).total_seconds() / 3600
            
            max_wait = position.get('max_wait_hours', 48)
            
            # لو انتهى الوقت والربح سلبي
            if hours_held >= max_wait and profit_percent < 0:
                return {
                    'action': 'SELL',
                    'reason': f'TIMEOUT {int(hours_held)}h',
                    'profit': profit_percent,
                    'confidence': 70
                }
            
            # لو مضى وقت طويل جداً (72 ساعة) حتى لو ربح صغير
            if hours_held >= 72 and profit_percent < 0.5:
                return {
                    'action': 'SELL',
                    'reason': f'LONG HOLD {int(hours_held)}h',
                    'profit': profit_percent,
                    'confidence': 75
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _calculate_hold_confidence(self, profit_percent, analysis, mtf):
        """حساب ثقة الـ Hold"""
        confidence = 50
        
        # الربح الحالي
        if profit_percent > 0.5:
            confidence += 20
        elif profit_percent > 0:
            confidence += 10
        elif profit_percent < -1:
            confidence -= 20
        
        # RSI
        rsi = analysis.get('rsi', 50)
        if 40 < rsi < 60:
            confidence += 10
        elif rsi < 30:
            confidence += 15
        
        # Trend
        trend = mtf.get('trend', 'neutral')
        if trend in ['bullish', 'strong_bullish']:
            confidence += 15
        elif trend in ['bearish', 'strong_bearish']:
            confidence -= 15
        
        return max(0, min(100, confidence))
    
    def _get_coin_exit_history(self, symbol):
        """جلب تاريخ البيع للعملة"""
        try:
            # Directly query the storage for historical trades of the symbol
            coin_trades = self.storage.get_trades_for_symbol(symbol, limit=50) # Fetch last 50 trades
            
            if not coin_trades or len(coin_trades) < 3:
                return None
            
            # Filter for sell trades and ensure profit_percent is a float
            sell_trades = [t for t in coin_trades if t.get('action') == 'SELL']
            profits = [float(t.get('profit_percent', 0) or 0) for t in sell_trades]
            
            if not profits:
                return None

            avg_profit = statistics.mean(profits)
            
            durations = [float(t.get('hours_held', 24) or 24) for t in sell_trades]
            avg_duration = statistics.mean(durations)
            
            return {
                'avg_profit': avg_profit,
                'avg_duration': avg_duration,
                'trades_count': len(sell_trades)
            }
            
        except:
            return None

    def _check_news_exit(self, symbol, profit_percent, analysis):
        """فحص الخروج بسبب الأخبار السلبية مع API خارجي"""
        try:
            # Sentiment محلي
            from src.news_analyzer import NewsAnalyzer
            news_analyzer = NewsAnalyzer()
            sentiment = news_analyzer.get_news_sentiment(symbol, hours=6)

            # Sentiment خارجي من external_apis
            from src.external_apis import get_external_news_sentiment
            external_sentiment = get_external_news_sentiment(symbol)

            # دمج
            local_score = sentiment['news_score'] if sentiment else 0
            external_score = external_sentiment.get('score', 0)
            combined_score = (local_score + external_score) / 2

            if combined_score < -3:  # أخبار سلبية قوية
                return {
                    'action': 'SELL',
                    'reason': f'Negative news sentiment (local: {local_score:.1f}, external: {external_score:.1f})',
                    'profit': profit_percent,
                    'confidence': 85
                }

            return {'action': 'HOLD'}

        except Exception as e:
            return {'action': 'HOLD'}
    
    
    def get_optimal_exit_point(self, symbol, current_profit):
        """الحصول على نقطة البيع المثالية"""
        try:
            history = self._get_coin_exit_history(symbol)
            
            if not history:
                return {
                    'optimal_tp': 1.0,
                    'optimal_sl': 2.0,
                    'confidence': 50
                }
            
            avg_profit = history['avg_profit']
            
            # حساب TP المثالي
            if avg_profit > 2:
                optimal_tp = 1.8
            elif avg_profit > 1.5:
                optimal_tp = 1.3
            elif avg_profit > 1:
                optimal_tp = 1.0
            else:
                optimal_tp = 0.8
            
            # حساب SL المثالي
            if avg_profit > 1:
                optimal_sl = 2.5  # نعطي مساحة أكبر
            else:
                optimal_sl = 1.5  # نشدد الحماية
            
            return {
                'optimal_tp': optimal_tp,
                'optimal_sl': optimal_sl,
                'confidence': min(history['trades_count'] * 10, 90)
            }
            
        except:
            return {
                'optimal_tp': 1.0,
                'optimal_sl': 2.0,
                'confidence': 50
            }

    def suggest_stop_loss(self, symbol, position, analysis, mtf):
        """اقتراح مسافة ستوب لوس ذكية بناءً على تحليل الخروج"""
        try:
            # ✅ إصلاح: تمرير الربح الحالي الفعلي بدل 0 دائماً
            buy_price = position.get('buy_price', 0)
            current_price = analysis.get('close', buy_price)
            current_profit = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

            exit_point = self.get_optimal_exit_point(symbol, current_profit)
            stop_distance = exit_point['optimal_sl']

            # تعديل بناءً على التقلبات الحالية
            volume_ratio = analysis.get('volume_ratio', 1.0)
            if volume_ratio > 2.0:
                stop_distance *= 1.2
            elif volume_ratio < 0.5:
                stop_distance *= 0.8

            # تعديل بناءً على RSI
            rsi = analysis.get('rsi', 50)
            if rsi > 70:
                stop_distance *= 0.9
            elif rsi < 30:
                stop_distance *= 1.1

            stop_distance = max(0.5, min(stop_distance, 5.0))
            return stop_distance
        except Exception as e:
            print(f"⚠️ Exit strategy stop loss suggestion error: {e}")
            return 1.5

    def check_trailing_stop_from_peak(self, symbol, position, current_price):
        """
        ✅ جديد: فحص Trailing Stop بناءً على أعلى سعر وصلته العملة (Peak).
        يُحدّث peak_price في الـ position ويُعيد قرار SELL إذا انخفض السعر
        عن القمة بمقدار يتجاوز مسافة الـ trailing المُقررة.
        """
        try:
            buy_price = position.get('buy_price', 0)
            if buy_price <= 0 or current_price <= 0:
                return {'action': 'HOLD', 'reason': 'Invalid prices'}

            profit_percent = ((current_price - buy_price) / buy_price) * 100

            # تحديث القمة إذا السعر الحالي أعلى
            peak_price = position.get('peak_price', buy_price)
            if current_price > peak_price:
                position['peak_price'] = current_price
                peak_price = current_price

            peak_profit = ((peak_price - buy_price) / buy_price) * 100

            # لا نُفعّل الـ trailing إلا إذا وصل لربح 0.5% على الأقل
            if peak_profit < 0.5:
                return {'action': 'HOLD', 'reason': 'Peak profit too low to trail'}

            # تحديد مسافة الـ trailing حسب حجم الربح من القمة
            if peak_profit >= 3.0:
                trail_distance = 1.0   # ربح كبير → نحمي بـ 1% من القمة
            elif peak_profit >= 1.5:
                trail_distance = 0.8
            elif peak_profit >= 0.8:
                trail_distance = 0.5
            else:
                trail_distance = 0.4

            # حساب نسبة الانخفاض عن القمة
            drop_from_peak = ((peak_price - current_price) / peak_price) * 100

            if drop_from_peak >= trail_distance:
                return {
                    'action': 'SELL',
                    'reason': f'TRAILING STOP: dropped {drop_from_peak:.2f}% from peak {peak_profit:.2f}%',
                    'profit': profit_percent,
                    'peak_profit': peak_profit,
                    'drop_from_peak': drop_from_peak,
                    'confidence': 88
                }

            return {
                'action': 'HOLD',
                'reason': f'Trailing OK: drop={drop_from_peak:.2f}% < trail={trail_distance}%',
                'peak_profit': peak_profit
            }

        except Exception as e:
            print(f"⚠️ Trailing stop from peak error {symbol}: {e}")
            return {'action': 'HOLD', 'reason': 'Error in trailing stop'}
