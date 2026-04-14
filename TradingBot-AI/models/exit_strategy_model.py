"""
🎯 Exit Strategy Model
يحسن توقيت البيع ويزيد الأرباح
"""

from datetime import datetime, timedelta
import statistics
from src.news_analyzer import NewsAnalyzer
from src.external_apis import get_external_news_sentiment

# ثوابت لتجنب الأرقام السحرية
DEFAULT_MAX_WAIT_HOURS = 48
LONG_HOLD_HOURS = 72
MIN_PROFIT_FOR_HOLD = 0.5
ATR_MULTIPLIER = 1.5
MIN_ATR_THRESHOLD = 1.5
NEWS_NEGATIVE_THRESHOLD = -3
PEAK_SCORE_THRESHOLD = 90
RSI_OVERBOUGHT = 75
VOLUME_RATIO_NEUTRAL = 1.0
BEARISH_RSI_THRESHOLD = 68
BEARISH_MACD_THRESHOLD = -2
MIN_BEARISH_PROFIT = 0.15
MAX_LOSS_FOR_TIMEOUT = -1.0
HOLD_PROFIT_INCREMENT = 0.5
RSI_NEUTRAL_LOW = 40
RSI_NEUTRAL_HIGH = 60
RSI_LOW_THRESHOLD = 30
CONFIDENCE_INCREMENT = 10
CONFIDENCE_DECREMENT = 20
CONFIDENCE_BONUS = 15

class ExitStrategyModel:
    def __init__(self, storage):
        self.storage = storage
        self.news_analyzer = NewsAnalyzer()  # إنشاء مرة واحدة للأداء
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
            peak_analysis = analysis.get('peak', {})
            peak_score = peak_analysis.get('confidence', 0)
            rsi = analysis.get('rsi', 50)
            
            # الخروج عند تأكيد "ضعف الاتجاه" (Divergence/Exhaustion)
            # إذا كان هناك ربح، وأعطى البوت إشارة قمة قوية أو تشبع شرائي مع ضعف حجم
            volume_ratio = analysis.get('volume_ratio', 1.0)
            
            if profit_percent > MIN_PROFIT_FOR_HOLD and (peak_score > PEAK_SCORE_THRESHOLD or (rsi > RSI_OVERBOUGHT and volume_ratio < VOLUME_RATIO_NEUTRAL)):
                return {
                    'action': 'SELL',
                    'reason': f'SMART TP: Peak Exhaustion ({peak_score} pts)',
                    'profit': profit_percent,
                    'confidence': 95
                }
            
            return {'action': 'HOLD'}
            
        except Exception as e:
            print(f"⚠️ Smart TP error {symbol}: {e}")
            return {'action': 'HOLD'}
    
    def _check_smart_trailing(self, symbol, current_price, position, analysis, history):
        """فحص Trailing Stop الذكي - تنفيذ الخيار A (حماية رأس المال)"""
        try:
            buy_price = position.get('buy_price', 0)
            highest_price = position.get('highest_price', buy_price)
            
            profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0

            # الوقف الزاحف السلوكي: يتنفس مع تقلب العملة
            atr_p = analysis.get('atr_percent', 2.5)
            threshold = max(MIN_ATR_THRESHOLD, atr_p * ATR_MULTIPLIER) # ديناميكي بالكامل

            if drop_from_peak >= threshold:
                return {
                    'action': 'SELL',
                    'reason': f'TRAILING EXIT (A): -{drop_from_peak:.1f}% from peak',
                    'profit': profit_percent,
                    'confidence': 90
                }
            return {'action': 'HOLD'}
        except Exception as e:
            print(f"⚠️ Smart TP error {symbol}: {e}")
            return {'action': 'HOLD'}
    
    def _check_smart_bearish(self, symbol, profit_percent, mtf, analysis, history):
        """فحص Bearish Exit الذكي - محسّن للسرعة"""
        try:
            trend = mtf.get('trend', 'neutral')

            # Bearish قوي
            if trend in ['bearish', 'strong_bearish']:
                # الخروج فوراً إذا تأكد الهيكل الهابط حتى لو بربح بسيط أو خسارة طفيفة
                if profit_percent > MAX_LOSS_FOR_TIMEOUT:
                    return {
                        'action': 'SELL',
                        'reason': 'STRUCTURAL EXIT: Bearish Trend Confirmed',
                        'profit': profit_percent,
                        'confidence': 80
                    }
            
            # فحص RSI + MACD معاً
            rsi = analysis.get('rsi', 50)
            macd_diff = analysis.get('macd_diff', 0)
            
            # تحسين: نخفض الحدود للبيع الأسرع
            if rsi > BEARISH_RSI_THRESHOLD and macd_diff < BEARISH_MACD_THRESHOLD and profit_percent > MIN_BEARISH_PROFIT:
                return {
                    'action': 'SELL',
                    'reason': 'OVERBOUGHT + BEARISH MACD',
                    'profit': profit_percent,
                    'confidence': 85
                }
            
            return {'action': 'HOLD'}
            
        except Exception as e:
            print(f"⚠️ Smart TP error {symbol}: {e}")
            return {'action': 'HOLD'}
    
    def _check_time_exit(self, symbol, position, profit_percent, history):
        """فحص Time-based Exit"""
        try:
            buy_time = datetime.fromisoformat(position['buy_time'])
            hours_held = (datetime.now() - buy_time).total_seconds() / 3600
            
            max_wait = position.get('max_wait_hours', DEFAULT_MAX_WAIT_HOURS)
            
            # لو انتهى الوقت والربح سلبي
            if hours_held >= max_wait and profit_percent < 0:
                return {
                    'action': 'SELL',
                    'reason': f'TIMEOUT {int(hours_held)}h',
                    'profit': profit_percent,
                    'confidence': 70
                }
            
            # لو مضى وقت طويل جداً (72 ساعة) حتى لو ربح صغير
            if hours_held >= LONG_HOLD_HOURS and profit_percent < MIN_PROFIT_FOR_HOLD:
                return {
                    'action': 'SELL',
                    'reason': f'LONG HOLD {int(hours_held)}h',
                    'profit': profit_percent,
                    'confidence': 75
                }
            
            return {'action': 'HOLD'}
            
        except Exception as e:
            print(f"⚠️ Smart TP error {symbol}: {e}")
            return {'action': 'HOLD'}
    
    def _calculate_hold_confidence(self, profit_percent, analysis, mtf):
        """حساب ثقة الـ Hold"""
        confidence = 50
        
        # الربح الحالي
        if profit_percent > MIN_PROFIT_FOR_HOLD:
            confidence += 20
        elif profit_percent > 0:
            confidence += CONFIDENCE_INCREMENT
        elif profit_percent < MAX_LOSS_FOR_TIMEOUT:
            confidence -= CONFIDENCE_DECREMENT
        
        # RSI
        rsi = analysis.get('rsi', 50)
        if RSI_NEUTRAL_LOW < rsi < RSI_NEUTRAL_HIGH:
            confidence += CONFIDENCE_INCREMENT
        elif rsi < RSI_LOW_THRESHOLD:
            confidence += CONFIDENCE_BONUS
        
        # Trend
        trend = mtf.get('trend', 'neutral')
        if trend in ['bullish', 'strong_bullish']:
            confidence += CONFIDENCE_BONUS
        elif trend in ['bearish', 'strong_bearish']:
            confidence -= CONFIDENCE_BONUS
        
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
            
        except Exception as e:
            print(f"⚠️ Error getting coin exit history {symbol}: {e}")
            return None

    def _check_news_exit(self, symbol, profit_percent, analysis):
        """فحص الخروج بسبب الأخبار السلبية مع API خارجي"""
        try:
            # Sentiment محلي
            sentiment = self.news_analyzer.get_news_sentiment(symbol, hours=6)

            # Sentiment خارجي
            external_sentiment = get_external_news_sentiment(symbol)

            # دمج
            local_score = sentiment['news_score'] if sentiment else 0
            external_score = external_sentiment.get('score', 0)
            combined_score = (local_score + external_score) / 2

            if combined_score < NEWS_NEGATIVE_THRESHOLD:  # أخبار سلبية قوية
                return {
                    'action': 'SELL',
                    'reason': f'Negative news sentiment (local: {local_score:.1f}, external: {external_score:.1f})',
                    'profit': profit_percent,
                    'confidence': 85
                }

            return {'action': 'HOLD'}

        except Exception as e:
            return {'action': 'HOLD'}
    
