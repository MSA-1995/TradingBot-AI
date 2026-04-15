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
        self.news_analyzer = NewsAnalyzer()
        self.profit_history = {}  # {symbol: [(timestamp, profit), ...]}
        print("🎯 Exit Strategy Model initialized")
    
    def should_exit(self, symbol, position, current_price, analysis, mtf):
        """قرار البيع الذكي + Minimum Hold Time + Profit Spike Detection"""
        try:
            buy_price = position['buy_price']
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            
            # ✅ Profit Spike Detection - كشف القفزات المفاجئة!
            spike_detected = self._detect_profit_spike(symbol, profit_percent)
            if spike_detected['should_sell']:
                return {
                    'action': 'SELL',
                    'reason': spike_detected['reason'],
                    'profit': profit_percent,
                    'confidence': 98
                }
            
            # ✅ Minimum Hold Time (لكن يسمح بالبيع عند القفزات)
            buy_time = datetime.fromisoformat(position['buy_time'])
            minutes_held = (datetime.now() - buy_time).total_seconds() / 60
            
            if minutes_held < 5:
                # استثناءات البيع الفوري:
                # 1. خسارة كارثية
                if profit_percent < -10:
                    return {
                        'action': 'SELL',
                        'reason': f'EMERGENCY EXIT: {profit_percent:.1f}% loss',
                        'profit': profit_percent,
                        'confidence': 95
                    }
                # 2. ربح ضخم مفاجئ (تم فحصه في Profit Spike أعلاه)
                # وإلا انتظر!
                return {
                    'action': 'HOLD',
                    'reason': f'Minimum hold time not met ({minutes_held:.1f}/5 min)',
                    'confidence': 100
                }
            
            coin_history = self._get_coin_exit_history(symbol)
            
            tp_decision = self._check_smart_tp(
                symbol, profit_percent, position, 
                analysis, mtf, coin_history
            )
            if tp_decision['action'] == 'SELL':
                return tp_decision
            
            trailing_decision = self._check_smart_trailing(
                symbol, current_price, position, 
                analysis, coin_history
            )
            if trailing_decision['action'] == 'SELL':
                return trailing_decision
            
            bearish_decision = self._check_smart_bearish(
                symbol, profit_percent, mtf, 
                analysis, coin_history
            )
            if bearish_decision['action'] == 'SELL':
                return bearish_decision
            
            time_decision = self._check_time_exit(
                symbol, position, profit_percent, coin_history
            )
            if time_decision['action'] == 'SELL':
                return time_decision

            news_exit_decision = self._check_news_exit(symbol, profit_percent, analysis)
            if news_exit_decision['action'] == 'SELL':
                return news_exit_decision

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
        """فحص TP الذكي - محسّن للسرعة + Peak Detection"""
        try:
            peak_analysis = analysis.get('peak', {})
            peak_score = peak_analysis.get('confidence', 0)
            rsi = analysis.get('rsi', 50)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            
            # ✅ 1. Peak Detection المتقدم - بيع عند القمة مباشرة!
            if profit_percent > 10:  # ربح جيد - ابحث عن القمة
                peak_signals = 0
                reasons = []
                
                # Signal 1: RSI Extreme Overbought
                if rsi > 80:
                    peak_signals += 1
                    reasons.append(f'RSI={rsi:.0f} (extreme overbought)')
                
                # Signal 2: Volume Collapse
                if volume_ratio < 0.5:
                    peak_signals += 1
                    reasons.append(f'Volume collapsed ({volume_ratio:.1f}x)')
                
                # Signal 3: Peak Score High
                if peak_score > 85:
                    peak_signals += 1
                    reasons.append(f'Peak score={peak_score}')
                
                # Signal 4: Momentum Slowdown
                momentum = analysis.get('price_momentum', 0)
                if momentum < 0.3:  # الزخم توقف
                    peak_signals += 1
                    reasons.append(f'Momentum slowed ({momentum:.2f}%)')
                
                # Signal 5: Smart Money Exit
                if analysis.get('whale_dumping', False):
                    peak_signals += 2  # إشارة قوية جداً!
                    reasons.append('Whales dumping detected')
                
                # القرار: إذا 3+ إشارات = بيع فوري!
                if peak_signals >= 3:
                    return {
                        'action': 'SELL',
                        'reason': f'PEAK DETECTED: {" | ".join(reasons)}',
                        'profit': profit_percent,
                        'confidence': 95
                    }
            
            # ✅ 2. Peak Exhaustion (النظام القديم)
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
        """فحص Trailing Stop الذكي المتقدم - مع تحليل الشموع الانعكاسية"""
        try:
            buy_price = position.get('buy_price', 0)
            highest_price = position.get('highest_price', buy_price)
            
            profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0

            # 🕯️ تحليل الشموع الانعكاسية عند القمة
            reversal_signal = self._detect_reversal_candles(analysis, profit_percent)
            
            # 🚨 بيع فوري إذا اكتشفنا شمعة انعكاسية قوية عند القمة
            if reversal_signal['detected'] and profit_percent > 0.5:
                return {
                    'action': 'SELL',
                    'reason': f'REVERSAL DETECTED: {reversal_signal["pattern"]} at peak',
                    'profit': profit_percent,
                    'confidence': reversal_signal['confidence']
                }
            
            # Wave Protection الذكي المتقدم
            wave_protection = self._calculate_dynamic_wave_protection(
                profit_percent, analysis, history, drop_from_peak
            )
            
            if wave_protection['should_exit']:
                return {
                    'action': 'SELL',
                    'reason': wave_protection['reason'],
                    'profit': profit_percent,
                    'confidence': 90
                }
            
            return {'action': 'HOLD'}
        except Exception as e:
            print(f"⚠️ Smart Trailing error {symbol}: {e}")
            return {'action': 'HOLD'}
    
    def _calculate_dynamic_wave_protection(self, profit_percent, analysis, history, drop_from_peak):
        """حساب Wave Protection الديناميكي المتقدم + Minimum Hold Time"""
        try:
            atr_p = analysis.get('atr_percent', 2.5)
            
            # 1. الحد الأساسي (مرفوع من 3% إلى 8%)
            base_threshold = max(8.0, atr_p * 2.5)  # ✅ حد أدنى 8% بدلاً من 3%
            
            # 2. تعديل حسب الربح الحالي
            if profit_percent > 50:  # ربح عالي جداً - اصبر أكثر
                threshold = base_threshold * 2.0
            elif profit_percent > 30:  # ربح جيد - اصبر
                threshold = base_threshold * 1.5
            elif profit_percent > 10:  # ربح متوسط
                threshold = base_threshold * 1.2
            elif profit_percent > 2:  # ربح بسيط
                threshold = base_threshold * 1.0
            else:  # ربح ضعيف أو خسارة - اصبر أكثر!
                threshold = base_threshold * 1.5  # ✅ لا تبيع بسرعة إذا خسران
            
            # 3. تعديل حسب التاريخ
            if history:
                avg_profit = history.get('avg_profit', 0)
                if profit_percent < avg_profit * 0.5:  # تحت المتوسط - اصبر
                    threshold *= 1.3
            
            # 4. تعديل حسب الحجم
            volume_ratio = analysis.get('volume_ratio', 1.0)
            if volume_ratio < 0.5:  # حجم ضعيف - احمي بسرعة
                threshold *= 0.8
            
            # 5. القرار
            if drop_from_peak >= threshold:
                return {
                    'should_exit': True,
                    'reason': f'WAVE PROTECTION: -{drop_from_peak:.1f}% from peak (threshold: {threshold:.1f}%)'
                }
            
            return {'should_exit': False}
            
        except:
            return {'should_exit': False}
    
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
    
    def _detect_reversal_candles(self, analysis, profit_percent):
        """🕯️ كشف الشموع الانعكاسية عند القمة"""
        try:
            # جلب بيانات الشموع من التحليل
            candles = analysis.get('candles', [])
            if not candles or len(candles) < 3:
                return {'detected': False, 'pattern': 'None', 'confidence': 0}
            
            # آخر 3 شموع للتحليل
            prev2 = candles[-3] if len(candles) >= 3 else None
            prev1 = candles[-2]
            current = candles[-1]
            
            # التحقق من البيانات
            required_keys = ['open', 'close', 'high', 'low', 'volume']
            if not all(key in current and key in prev1 for key in required_keys):
                return {'detected': False, 'pattern': 'Incomplete data', 'confidence': 0}
            
            # حساب خصائص الشمعة الحالية
            body = abs(current['close'] - current['open'])
            candle_range = current['high'] - current['low']
            if candle_range == 0:
                return {'detected': False, 'pattern': 'Doji', 'confidence': 0}
            
            upper_wick = current['high'] - max(current['open'], current['close'])
            lower_wick = min(current['open'], current['close']) - current['low']
            
            is_red = current['close'] < current['open']
            is_green = current['close'] > current['open']
            
            # حجم التداول
            volume_spike = current['volume'] > prev1['volume'] * 1.5
            
            # RSI و MACD للتأكيد
            rsi = analysis.get('rsi', 50)
            macd_diff = analysis.get('macd_diff', 0)
            
            # 1. Shooting Star (نجمة هابطة) - قمة حقيقية
            if (upper_wick > body * 2 and 
                lower_wick < body * 0.5 and 
                rsi > 65 and 
                volume_spike and
                profit_percent > 1.0):
                return {
                    'detected': True,
                    'pattern': 'Shooting Star',
                    'confidence': 95
                }
            
            # 2. Bearish Engulfing (ابتلاع هبوطي)
            if (prev1['close'] > prev1['open'] and  # شمعة خضراء سابقة
                is_red and  # شمعة حمراء حالية
                current['open'] > prev1['close'] and  # فتحت فوق إغلاق السابقة
                current['close'] < prev1['open'] and  # أغلقت تحت فتح السابقة
                volume_spike and
                profit_percent > 0.8):
                return {
                    'detected': True,
                    'pattern': 'Bearish Engulfing',
                    'confidence': 92
                }
            
            # 3. Evening Star (نجمة المساء) - 3 شموع
            if (prev2 and
                prev2['close'] > prev2['open'] and  # شمعة 1: خضراء قوية
                abs(prev1['close'] - prev1['open']) < body * 0.3 and  # شمعة 2: doji صغيرة
                is_red and  # شمعة 3: حمراء قوية
                current['close'] < prev2['close'] and
                rsi > 70 and
                profit_percent > 1.5):
                return {
                    'detected': True,
                    'pattern': 'Evening Star',
                    'confidence': 93
                }
            
            # 4. Dark Cloud Cover (غطاء سحابة مظلمة)
            if (prev1['close'] > prev1['open'] and  # شمعة خضراء سابقة
                is_red and  # شمعة حمراء حالية
                current['open'] > prev1['high'] and  # فتحت فوق قمة السابقة
                current['close'] < (prev1['open'] + prev1['close']) / 2 and  # أغلقت تحت منتصف السابقة
                volume_spike and
                profit_percent > 1.0):
                return {
                    'detected': True,
                    'pattern': 'Dark Cloud Cover',
                    'confidence': 90
                }
            
            # 5. Three Black Crows (3 غربان سوداء) - هبوط قوي
            if (prev2 and
                prev2['close'] < prev2['open'] and  # 3 شموع حمراء متتالية
                prev1['close'] < prev1['open'] and
                is_red and
                current['close'] < prev1['close'] < prev2['close'] and
                macd_diff < -2 and
                profit_percent > 0.5):
                return {
                    'detected': True,
                    'pattern': 'Three Black Crows',
                    'confidence': 94
                }
            
            # 6. Hanging Man (الرجل المعلق) - تحذير من انعكاس
            if (lower_wick > body * 2 and
                upper_wick < body * 0.5 and
                rsi > 68 and
                profit_percent > 1.2):
                return {
                    'detected': True,
                    'pattern': 'Hanging Man',
                    'confidence': 88
                }
            
            # 7. Bearish Harami (حامل هبوطي)
            if (prev1['close'] > prev1['open'] and  # شمعة خضراء كبيرة سابقة
                is_red and  # شمعة حمراء صغيرة حالية
                current['open'] < prev1['close'] and
                current['close'] > prev1['open'] and
                body < abs(prev1['close'] - prev1['open']) * 0.5 and
                rsi > 72 and
                profit_percent > 1.0):
                return {
                    'detected': True,
                    'pattern': 'Bearish Harami',
                    'confidence': 87
                }
            
            return {'detected': False, 'pattern': 'No reversal', 'confidence': 0}
            
        except Exception as e:
            print(f"⚠️ Reversal detection error: {e}")
            return {'detected': False, 'pattern': 'Error', 'confidence': 0}
    

    def _detect_profit_spike(self, symbol, current_profit):
        """🚀 كشف القفزات المفاجئة - مقارنة مع آخر دورة فقط!"""
        try:
            now = datetime.now()
            
            # حفظ الربح الحالي
            if symbol not in self.profit_history:
                self.profit_history[symbol] = []
            
            history = self.profit_history[symbol]
            
            # ✅ مقارنة مع آخر دورة فقط!
            if len(history) >= 1:
                last_time, last_profit = history[-1]
                time_diff = (now - last_time).total_seconds()
                
                # إذا مر أقل من 20 ثانية (دورتين)
                if time_diff <= 20:
                    profit_jump = current_profit - last_profit
                    
                    # ✅ قفزة سريعة: +5% بين دورتين
                    if profit_jump >= 5 and current_profit >= 8:
                        return {
                            'should_sell': True,
                            'reason': f'PROFIT SPIKE: +{profit_jump:.1f}% in {time_diff:.0f}s (from {last_profit:.1f}% to {current_profit:.1f}%)'
                        }
                    
                    # ✅ قفزة ضخمة: +8% بين دورتين
                    if profit_jump >= 8 and current_profit >= 10:
                        return {
                            'should_sell': True,
                            'reason': f'PROFIT SPIKE: +{profit_jump:.1f}% in {time_diff:.0f}s (from {last_profit:.1f}% to {current_profit:.1f}%)'
                        }
                    
                    # ✅ هبوط سريع: -3% بعد قمة
                    if last_profit >= 10 and profit_jump <= -3:
                        return {
                            'should_sell': True,
                            'reason': f'PROFIT CRASH: Dropped {profit_jump:.1f}% in {time_diff:.0f}s (from {last_profit:.1f}% to {current_profit:.1f}%)'
                        }
            
            # حفظ القراءة الحالية
            self.profit_history[symbol].append((now, current_profit))
            
            # الاحتفاظ بآخر 5 قراءات فقط (تقريباً 45 ثانية)
            if len(self.profit_history[symbol]) > 5:
                self.profit_history[symbol] = self.profit_history[symbol][-5:]
            
            return {'should_sell': False}
            
        except Exception as e:
            print(f"⚠️ Profit spike detection error: {e}")
            return {'should_sell': False}
