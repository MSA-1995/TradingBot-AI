"""
Meta (The King) - The Ultimate Decision Maker
"""
import pandas as pd
from config import (
    MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, MIN_SELL_CONFIDENCE,
    MACRO_CANDLE_THRESHOLD, PEAK_DROP_THRESHOLD, BOTTOM_BOUNCE_THRESHOLD, 
    VOLUME_SPIKE_FACTOR, META_BUY_INTELLIGENCE, META_BUY_WHALE, META_BUY_TREND, 
    META_BUY_VOLUME, META_BUY_PATTERN, META_BUY_CANDLE, META_BUY_SUPPORT, META_BUY_HISTORY, 
    META_BUY_CONSENSUS, META_DISPLAY_THRESHOLD
)
from datetime import datetime, timezone
import gc
import psutil
import pickle
import os
import json

DB_LEARNING_KEY = 'king_learning_data'

class Meta:
    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager = advisor_manager
        self.storage = storage
        self.meta_model = None
        self.meta_feature_names = None
        self._patterns_cache = None  # 🆕 كاش الأنماط في RAM
        self._load_model_data_from_db()
        self._load_patterns_to_cache()  # 🆕 تحميل الأنماط عند التشغيل
        
        # 🆕 Real-time Price Action
        try:
            import sys
            import os
            # إضافة مجلد models للمسار
            models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
            if models_path not in sys.path:
                sys.path.insert(0, models_path)
            
            from realtime_price_action import RealTimePriceAction
            self.realtime_pa = RealTimePriceAction()
            print("✅ Meta: Real-time Price Action initialized")
        except Exception as e:
            print(f"⚠️ Meta: Failed to load Real-time Price Action: {e}")
            self.realtime_pa = None

        print("👑 Meta (The King) is initialized and ready to rule.")

    def _load_patterns_to_cache(self):
        """🚀 تحميل كل الأنماط من الداتابيز للرام مرة واحدة"""
        try:
            if not self.storage:
                print("⚠️ Meta: Storage not available, patterns cache disabled")
                self._patterns_cache = []
                return
            
            patterns = self.storage.load_all_patterns()
            self._patterns_cache = patterns
            
            # حساب الحجم المضغوط
            import sys
            cache_size_kb = sys.getsizeof(self._patterns_cache) / 1024
            
            print(f"✅ Meta: Loaded {len(patterns)} patterns to RAM cache ({cache_size_kb:.1f} KB)")
            
        except Exception as e:
            print(f"❌ Meta: Failed to load patterns cache: {e}")
            self._patterns_cache = []

    def _load_model_data_from_db(self):
        """Loads the raw model data (blueprint) from the database."""
        if not self.advisor_manager:
            print("⚠️ Meta: Advisor Manager not provided, cannot load Meta-Learner.")
            return

        try:
            dl_client = self.advisor_manager.get('dl_client')
            if not dl_client:
                print("⚠️ Meta: Deep Learning Client not available via Advisor Manager.")
                return

            # ✅ جلب الموديل من الـ _models المحملة مسبقاً
            cached_models = getattr(dl_client, '_models', None)
            if cached_models:
                self.meta_model = cached_models.get('meta_trading')
                print("✅ Meta: King's Intelligence (AI Model) loaded from DL Client.")
            else:
                print("⚠️ Meta: Meta-Learner model not found in DL Client cache.")
                self.meta_model = None
        except Exception as e:
            print(f"❌ Meta: Error loading Meta-Learner from DL Client: {e}")
            self.meta_model = None

    # =========================================================
    # 📰 NEWS CONFIDENCE MODIFIER (يُعدّل الثقة فقط، لا يقرر)
    # =========================================================
    def _get_news_confidence_modifier(self, symbol):
        """
        يجلب تعديل الثقة من مستشار الأخبار.
        القيمة موجبة = أخبار إيجابية → ترفع الثقة
        القيمة سالبة = أخبار سلبية → تخفض الثقة
        النطاق: -15 إلى +15 نقطة فقط
        لا يمنع الشراء ولا يأمر بالبيع بنفسه.
        """
        try:
            news_analyzer = self.advisor_manager.get('NewsAnalyzer') if self.advisor_manager else None
            if not news_analyzer:
                return 0, "No news"
            boost = news_analyzer.get_news_confidence_boost(symbol)
            summary = news_analyzer.get_news_summary(symbol)
            return boost, summary
        except Exception:
            return 0, "No news"

    # =========================================================
    # 💪 الجرأة الديناميكية — يجرؤ أكثر لو نجح قبل بنفس الظروف
    # =========================================================
    def _get_courage_boost(self, symbol, rsi, volume_ratio):
        """لو البوت نجح قبل بنفس الظروف → يجرؤ أكثر ويرفع الثقة"""
        try:
            data = self._load_learning_data()
            courage_record = data.get('courage_record', [])

            similar_wins = [
                r for r in courage_record
                if r.get('symbol') == symbol
                and abs(r.get('rsi', 50) - rsi) < 12
                and abs(r.get('volume_ratio', 1.0) - volume_ratio) < 0.5
                and r.get('profit', 0) > 0.5
            ]

            if len(similar_wins) == 1:
                avg_profit = sum(r['profit'] for r in similar_wins) / len(similar_wins)
                boost = min(avg_profit * 1.2, 8)  # light boost for 1 win
                print(f"💪 Soft Courage [{symbol}]: +{boost:.1f} (1 similar win, avg {avg_profit:.1f}%)")
                return round(boost, 1)

            # لعملتين أو أكثر تعطي boost قوي
            if len(similar_wins) >= 2:
                avg_profit = sum(r['profit'] for r in similar_wins) / len(similar_wins)
                boost = min(avg_profit * 2.5, 18)  # max +18 نقطة
                print(f"💪 Courage Boost [{symbol}]: +{boost:.1f} (based on {len(similar_wins)} similar wins, avg {avg_profit:.1f}%)")
                return round(boost, 1)
        except Exception as e:
            print(f"⚠️ Courage boost error: {e}")
        return 0

    # =========================================================
    # ⏰ ذاكرة الوقت — يتجنب أوقات الخسارة ويفضل أوقات النجاح
    # =========================================================
    def _get_time_memory_modifier(self, symbol):
        """يتذكر الأوقات الناجحة والخاسرة لكل عملة ويعدّل الثقة"""
        try:
            data = self._load_learning_data()
            current_hour = datetime.now(timezone.utc).hour
            hour_key = str(current_hour)

            best_times = data.get('best_buy_times', {}).get(symbol, {})
            worst_times = data.get('worst_buy_times', {}).get(symbol, {})

            success_this_hour = best_times.get(hour_key, 0)
            fails_this_hour = worst_times.get(hour_key, 0)

            total_this_hour = success_this_hour + fails_this_hour

            # ساعة ناجحة بشكل واضح
            if success_this_hour >= 3 and fails_this_hour == 0:
                boost = +10
                label = f"GoodHour({current_hour}h,{success_this_hour}wins)"
                print(f"⏰ Time Boost [{symbol}]: {label}")
                return boost, label

            # ساعة ناجحة بنسبة عالية (75%+)
            if total_this_hour >= 4 and success_this_hour / total_this_hour >= 0.75:
                boost = +6
                label = f"GoodHour({current_hour}h,{int(success_this_hour/total_this_hour*100)}%)"
                print(f"⏰ Time Boost [{symbol}]: {label}")
                return boost, label

            # ساعة خاسرة
            if fails_this_hour >= 2:
                penalty = -12
                label = f"BadHour({current_hour}h,{fails_this_hour}fails)"
                print(f"⏰ Time Penalty [{symbol}]: {label}")
                return penalty, label

            # ساعة خاسرة بنسبة (60%+)
            if total_this_hour >= 3 and fails_this_hour / total_this_hour >= 0.6:
                penalty = -7
                label = f"BadHour({current_hour}h,{int(fails_this_hour/total_this_hour*100)}%)"
                print(f"⏰ Time Penalty [{symbol}]: {label}")
                return penalty, label

        except Exception as e:
            print(f"⚠️ Time memory error: {e}")
        return 0, ""

    # =========================================================
    # 🔁 ذاكرة الأنماط — يبحث عن نمط مشابه ناجح سابق
    # =========================================================
    def _get_symbol_pattern_score(self, symbol, rsi, macd_diff, volume_ratio):
        """يبحث في الصفقات الناجحة السابقة عن نمط مشابه ويرفع الثقة"""
        try:
            data = self._load_learning_data()
            patterns = data.get('successful_patterns', [])

            symbol_patterns = [p for p in patterns if p.get('symbol') == symbol]
            if len(symbol_patterns) < 1:
                return 0, ""  # ما في بيانات كافية بعد

            matches = [
                p for p in symbol_patterns
                if abs(p.get('rsi', 50) - rsi) < 15
                and abs(p.get('volume_ratio', 1.0) - volume_ratio) < 0.8
            ]

            if len(matches) >= 3:
                avg_profit = sum(p.get('profit', 0) for p in matches) / len(matches)
                if avg_profit > 0.8:
                    boost = min(avg_profit * 2.0, 14)
                    label = f"Pattern({len(matches)}hits,avg{avg_profit:.1f}%)"
                    print(f"🔁 Pattern Boost [{symbol}]: +{boost:.1f} — {label}")
                    return round(boost, 1), label

            if len(matches) >= 2:
                avg_profit = sum(p.get('profit', 0) for p in matches) / len(matches)
                if avg_profit > 1.2:
                    boost = min(avg_profit * 1.2, 8)
                    label = f"Pattern(2hits,avg{avg_profit:.1f}%)"
                    return round(boost, 1), label

        except Exception as e:
            print(f"⚠️ Pattern score error: {e}")
        return 0, ""

    # =========================================================
    # 🏆 معدل نجاح العملة — يثق أكثر بالعملات الموثوقة
    # =========================================================
    def _get_symbol_win_rate_boost(self, symbol):
        """لو العملة سجلها ناجح تاريخياً → يضيف ثقة إضافية"""
        try:
            data = self._load_learning_data()
            win_data = data.get('symbol_win_rate', {}).get(symbol, {})
            wins = win_data.get('wins', 0)
            total = win_data.get('total', 0)

            if total < 5:
                return 0, ""  # بيانات غير كافية

            win_rate = wins / total
            if win_rate >= 0.80 and total >= 8:
                boost = +10
                label = f"WinRate({int(win_rate*100)}%,{total}trades)"
                print(f"🏆 Win Rate Boost [{symbol}]: +{boost} — {label}")
                return boost, label
            elif win_rate >= 0.65 and total >= 5:
                boost = +5
                label = f"WinRate({int(win_rate*100)}%,{total}trades)"
                return boost, label
            elif win_rate < 0.35 and total >= 6:
                penalty = -8
                label = f"LowWin({int(win_rate*100)}%,{total}trades)"
                print(f"⚠️ Win Rate Penalty [{symbol}]: {penalty} — {label}")
                return penalty, label
        except Exception as e:
            print(f"⚠️ Win rate boost error: {e}")
        return 0, ""


    def _gather_buy_advisors_intelligence(self, symbol, analysis_data, reasons):
        """جمع ذكاء المستشارين للشراء - دالة منفصلة لتقليل الحجم"""
        advisors_intelligence = {}

        try:
            # 1. Smart Money Tracker - نشاط الحيتان + Order Flow Imbalance
            smart_money = self.advisor_manager.get('SmartMoneyTracker') if self.advisor_manager else None
            if smart_money:
                whale_score = analysis_data.get('whale_confidence', 0)
                advisors_intelligence['whale_activity'] = abs(whale_score) * 4  # 0-100
                advisors_intelligence['whale_direction'] = 'buy' if whale_score > 0 else 'sell'
                
                # 🆕 Order Flow Imbalance - تدفق أوامر الحيتان
                try:
                    order_book = analysis_data.get('order_book')
                    if order_book and order_book.get('bids') and order_book.get('asks'):
                        # حساب حجم الأوامر الكبيرة (الحيتان)
                        large_bids = [b for b in order_book['bids'][:20] if b[1] > sum(bb[1] for bb in order_book['bids'][:20]) / 20 * 3]
                        large_asks = [a for a in order_book['asks'][:20] if a[1] > sum(aa[1] for aa in order_book['asks'][:20]) / 20 * 3]
                        
                        large_bid_volume = sum(b[1] for b in large_bids)
                        large_ask_volume = sum(a[1] for a in large_asks)
                        
                        # Order Flow Imbalance
                        if large_bid_volume + large_ask_volume > 0:
                            flow_imbalance = (large_bid_volume - large_ask_volume) / (large_bid_volume + large_ask_volume)
                            advisors_intelligence['order_flow_imbalance'] = flow_imbalance  # -1 to +1
                            
                            # إذا الحيتان تشتري بكثافة = إشارة قوية للشراء
                            if flow_imbalance > 0.4:
                                advisors_intelligence['whale_activity'] = min(100, advisors_intelligence['whale_activity'] + 20)
                                reasons.append(f"🐋 Whale Buying: Flow Imbalance {flow_imbalance:.2f}")
                        else:
                            advisors_intelligence['order_flow_imbalance'] = 0
                except Exception as flow_err:
                    advisors_intelligence['order_flow_imbalance'] = 0
        except: pass

        try:
            # 2. Trend Early Detector - قوة الاتجاه
            trend_detector = self.advisor_manager.get('TrendEarlyDetector') if self.advisor_manager else None
            if trend_detector:
                candles_data = analysis_data.get('candles', [])
                if len(candles_data) >= 30:
                    import pandas as pd
                    df = pd.DataFrame(candles_data)
                    order_book = analysis_data.get('order_book')
                    trend_data = trend_detector.detect_trend_birth(df, order_book)

                    if trend_data['trend'] == 'BULLISH' and trend_data['stage'] == 'BIRTH':
                        advisors_intelligence['trend_birth'] = 95
                        reasons.append(f"🎯 Trend Birth: {trend_data['strength']}")
                    elif trend_data['trend'] == 'BULLISH' and trend_data['stage'] == 'GROWTH':
                        advisors_intelligence['trend_birth'] = 75
                    else:
                        advisors_intelligence['trend_birth'] = 30
        except: pass

        try:
            # 3. Volume Forecast Engine - زخم الحجم
            volume_engine = self.advisor_manager.get('VolumeForecastEngine') if self.advisor_manager else None
            if volume_engine:
                candles_data = analysis_data.get('candles', [])
                if len(candles_data) >= 20:
                    volumes = [c.get('volume', 0) for c in candles_data[-20:]]
                    current_hour = datetime.now().hour
                    prediction = volume_engine.predict_next_volume(symbol, volumes, current_hour)
                    breakout = volume_engine.detect_volume_breakout(symbol, volumes, prediction)

                    if breakout['breakout_imminent']:
                        advisors_intelligence['volume_momentum'] = breakout['probability']
                        reasons.append(f"💥 Volume Breakout: {breakout['probability']}%")
                    else:
                        advisors_intelligence['volume_momentum'] = 40
        except: pass

        try:
            # 4. Liquidation Shield - أمان المنطقة
            liq_shield = self.advisor_manager.get('LiquidationShield') if self.advisor_manager else None
            if liq_shield:
                current_price = analysis_data.get('close', 0)
                order_book = analysis_data.get('order_book')
                if order_book:
                    liq_analysis = liq_shield.analyze_liquidation_risk(symbol, current_price, order_book)
                    advisors_intelligence['liquidation_safety'] = 100 - liq_analysis.get('risk_score', 50)
        except: pass

        try:
            # 5. Pattern Recognition - أنماط الشموع (من candle_expert + reversal)
            reversal = analysis_data.get('reversal', {})
            base_pattern_confidence = reversal.get('confidence', 0)

            # 🆕 جلب صوت candle_expert من dl_client
            candle_expert_score = 0
            try:
                dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
                if dl_client:
                    # جلب نصيحة candle_expert
                    advisors_advice = dl_client.get_advice(
                        rsi=analysis_data.get('rsi', 50),
                        macd=analysis_data.get('macd_diff', 0),
                        volume_ratio=analysis_data.get('volume_ratio', 1.0),
                        price_momentum=analysis_data.get('price_momentum', 0),
                        confidence=50,
                        analysis_data=analysis_data,
                        action='BUY'
                    )

                    candle_expert_advice = advisors_advice.get('candle_expert', 'N/A')

                    # تحويل الصوت إلى نقاط (0-100) بدون طباعة
                    if 'Strong-Bullish' in str(candle_expert_advice):
                        candle_expert_score = 90  # Hammer أو Engulfing قوي!
                    elif 'Bullish' in str(candle_expert_advice):
                        candle_expert_score = 70
                    elif 'Neutral' in str(candle_expert_advice):
                        candle_expert_score = 50
                    elif 'Bearish' in str(candle_expert_advice):
                        candle_expert_score = 30  # نمط هابط - تحذير
                    elif 'Strong-Bearish' in str(candle_expert_advice):
                        candle_expert_score = 10  # نمط هابط قوي - خطر!
                    else:
                        candle_expert_score = 50  # محايد
            except Exception as e:
                print(f"⚠️ Meta: Error getting candle_expert advice: {e}")
                candle_expert_score = 50

            # 🆕 Enhanced Pattern Recognition - صائد القمم والقيعان المحسن
            peak_valley_score = 50
            try:
                pattern_recognizer = self.advisor_manager.get('EnhancedPatternRecognition') if self.advisor_manager else None
                if pattern_recognizer:
                    candles_data = analysis_data.get('candles', [])
                    if len(candles_data) >= 10:
                        pattern_result = pattern_recognizer.analyze_peak_hunter_pattern(candles_data)
                        if pattern_result['signal'] == 'buy':
                            peak_valley_score = 85  # قاع قوي مكتشف
                            reasons.append(f"🎯 Peak Hunter: {pattern_result['reason']}")
                        elif pattern_result['signal'] == 'sell':
                            peak_valley_score = 15  # قمة قوية مكتشفة
                            reasons.append(f"🎯 Peak Hunter: {pattern_result['reason']}")
                        else:
                            peak_valley_score = 50  # لا نمط
            except Exception as e:
                print(f"⚠️ Meta: Error getting peak hunter pattern: {e}")
                peak_valley_score = 50

            # دمج pattern_confidence من reversal + candle_expert + peak_valley
            # peak_valley_score يأخذ وزن أكبر لأنه الأهم في كشف القاع الحقيقي
            combined_pattern_score = (base_pattern_confidence * 0.2 + candle_expert_score * 0.3 + peak_valley_score * 0.5)
            pattern_confidence = min(100, combined_pattern_score)
            advisors_intelligence['pattern_confidence'] = pattern_confidence
            advisors_intelligence['candle_expert_score'] = candle_expert_score
            advisors_intelligence['peak_valley_score'] = peak_valley_score
        except:
            advisors_intelligence['pattern_confidence'] = 0
            advisors_intelligence['candle_expert_score'] = 50

        try:
            # 6. Fibonacci Analyzer - مستويات الدعم
            fib_analyzer = self.advisor_manager.get('FibonacciAnalyzer') if self.advisor_manager else None
            if fib_analyzer:
                rsi = analysis_data.get('rsi', 50)
                volume_ratio = analysis_data.get('volume_ratio', 1.0)
                if rsi <= 70:
                    is_at_support, support_boost = fib_analyzer.is_at_support(
                        current_price=analysis_data.get('close', 0),
                        analysis=analysis_data,
                        volume_ratio=volume_ratio,
                        symbol=symbol
                    )
                    advisors_intelligence['support_strength'] = support_boost * 2 if is_at_support else 30
        except: pass

        try:
            # 7. Sentiment Analyzer - مشاعر السوق
            sentiment_data = analysis_data.get('sentiment_score', 0)
            advisors_intelligence['sentiment_score'] = sentiment_data  # -10 to +10
        except: pass

        try:
            # 8. News Analyzer - تأثير الأخبار + News Sentiment Reversal
            news_analyzer = self.advisor_manager.get('NewsAnalyzer') if self.advisor_manager else None
            if news_analyzer:
                news_boost = news_analyzer.get_news_confidence_boost(symbol)
                advisors_intelligence['news_impact'] = news_boost
                advisors_intelligence['historical_success'] = 50  # متوسط
                
                # 🆕 News Sentiment Reversal - انعكاس المشاعر في الأخبار
                try:
                    news_summary = news_analyzer.get_news_summary(symbol)
                    if news_summary and 'sentiment_history' in news_summary:
                        history = news_summary['sentiment_history'][-5:]  # آخر 5 أخبار
                        if len(history) >= 3:
                            # فحص إذا المشاعر انعكست من إيجابية لسلبية
                            recent_sentiment = sum(h.get('score', 0) for h in history[-2:]) / 2
                            older_sentiment = sum(h.get('score', 0) for h in history[-5:-2]) / 3
                            
                            sentiment_change = recent_sentiment - older_sentiment
                            
                            # انعكاس إيجابي = أخبار تحسنت (شراء)
                            if sentiment_change > 2:
                                advisors_intelligence['news_impact'] += 10
                                reasons.append(f"📰 News Sentiment Improved: +{sentiment_change:.1f}")
                            # انعكاس سلبي = أخبار ساءت (تحذير)
                            elif sentiment_change < -2:
                                advisors_intelligence['news_impact'] -= 10
                                reasons.append(f"📰 News Sentiment Worsened: {sentiment_change:.1f}")
                except Exception as news_err:
                    pass
        except: pass

        try:
            # 9. Anomaly Detector - كشف الشذوذ والفخاخ
            anomaly_detector = self.advisor_manager.get('AnomalyDetector') if self.advisor_manager else None
            if anomaly_detector:
                anomaly_score = analysis_data.get('anomaly_score', 0)
                if anomaly_score > 70:  # شذوذ عالي = خطر
                    advisors_intelligence['anomaly_risk'] = 10  # يقلل الثقة
                else:
                    advisors_intelligence['anomaly_risk'] = 80  # طبيعي
        except: pass

        try:
            # 10. Liquidity Analyzer - تحليل السيولة
            liquidity_analyzer = self.advisor_manager.get('LiquidityAnalyzer') if self.advisor_manager else None
            if liquidity_analyzer:
                liquidity_score = analysis_data.get('liquidity_score', 50)
                advisors_intelligence['liquidity_score'] = liquidity_score  # 0-100
        except: pass

        try:
            # 11. Whale Tracking - تتبع الحيتان
            whale_tracking = self.advisor_manager.get('SmartMoneyTracker') if self.advisor_manager else None
            if whale_tracking:
                whale_activity = analysis_data.get('whale_activity', 0)
                advisors_intelligence['whale_tracking_score'] = whale_activity * 5  # 0-100
        except: pass

        return advisors_intelligence

    def should_buy(self, symbol, analysis, models_scores=None, candles=None, preloaded_advisors=None):
        """👑 القرار - meta_trading المتعلم يقرر بناءً على تعلمه من التاريخ"""

        analysis_data = analysis
        reasons = []

        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action': 'DISPLAY', 'reason': 'Invalid analysis data', 'confidence': 0}

        # جمع ذكاء المستشارين (للميزات)
        advisors_intelligence = self._gather_buy_advisors_intelligence(symbol, analysis_data, reasons)

        try:
            # 12. Cross-Exchange - مقارنة الأسعار
            cross_exchange = self.advisor_manager.get('CrossExchange') if self.advisor_manager else None
            if cross_exchange:
                price_diff = analysis_data.get('price_diff_pct', 0)
                if abs(price_diff) < 0.5:  # أسعار متسقة = إشارة إيجابية
                    advisors_intelligence['cross_exchange_score'] = 90
                else:
                    advisors_intelligence['cross_exchange_score'] = 40
        except: pass
        
        try:
            # 9. Adaptive Intelligence - الذاكرة التاريخية
            adaptive_ai = self.advisor_manager.get('AdaptiveIntelligence') if self.advisor_manager else None
            if adaptive_ai:
                profile = adaptive_ai.get_symbol_profile(symbol)
                if profile:
                    advisors_intelligence['historical_success'] = profile.get('success_rate', 50)
        except: pass
        
        try:
            # 10. Liquidity Analyzer - سيولة السوق
            liquidity_metrics = analysis_data.get('liquidity_metrics', {})
            advisors_intelligence['liquidity_score'] = liquidity_metrics.get('liquidity_score', 50)
        except: pass
        
        try:
            # 11. Anomaly Detector - كشف الفخاخ
            anomaly_score = analysis_data.get('anomaly_score', 0)
            advisors_intelligence['trap_detection'] = 100 - min(anomaly_score * 10, 100)
        except: pass
        
        try:
            # 12. Risk Manager - تقييم المخاطر
            risk_score = analysis_data.get('volatility_risk_score', 2.0)
            advisors_intelligence['risk_level'] = max(0, 100 - risk_score * 10)
        except: pass
        
        try:
            # 13. Macro Trend Advisor - اتجاه السوق الكلي
            macro_advisor = self.advisor_manager.get('MacroTrendAdvisor') if self.advisor_manager else None
            if macro_advisor:
                macro_status = macro_advisor.get_macro_status()
                if macro_status in ["STRONG_BULL_MARKET", "BULL_MARKET"]:
                    advisors_intelligence['macro_trend'] = 85
                elif macro_status == "BEAR_MARKET":
                    advisors_intelligence['macro_trend'] = 20
                else:
                    advisors_intelligence['macro_trend'] = 50
                # حفظ للاستخدام في البيع
                advisors_intelligence['macro_status'] = macro_status
        except: pass
        
        try:
            # 14. Exit Strategy - توقيت الدخول
            advisors_intelligence['entry_timing'] = 60  # محايد للشراء
        except: pass
        
        # استخراج البيانات الأساسية
        rsi = analysis_data.get('rsi', 50)
        macd_diff = analysis_data.get('macd_diff', 0)
        volume_ratio = analysis_data.get('volume_ratio', 1.0)
        price_momentum = analysis_data.get('price_momentum', 0)
        atr = analysis_data.get('atr', 2.5)
        
        # جلب symbol_memory و bot_settings من الكاش (محملة عند التشغيل)
        from memory.memory_cache import MemoryCache
        cache = MemoryCache()
        symbol_memory = cache.get(f'symbol_mem_{symbol}') or {}
        if not symbol_memory and self.storage:
            symbol_memory = self.storage.get_symbol_memory(symbol) or {}
        
        bot_settings = cache.get('bot_settings') or {}
        
        # بناء الميزات لنموذج meta_trading (48 ميزة)
        features = self._build_meta_features(
            rsi=rsi,
            macd_diff=macd_diff,
            volume_ratio=volume_ratio,
            price_momentum=price_momentum,
            atr=atr,
            analysis_data=analysis_data,
            advisors_intelligence=advisors_intelligence,
            symbol_memory=symbol_memory
        )

        # 🤖 استخدام meta_trading المتعلم للتنبؤ
        buy_probability = 0.5
        confidence = 50
        
        if self.meta_model:
            try:
                import pandas as pd
                X = pd.DataFrame([features], columns=self._get_meta_feature_names())
                buy_probability = self.meta_model.predict_proba(X)[0][1]
                confidence = buy_probability * 100
            except Exception as e:
                print(f"⚠️ Meta prediction error: {e}")
        else:
            print("⚠️ Meta: meta_trading model not loaded, using default confidence")
        
        # إضافة تعديلات الذاكرة للثقة
        courage_boost = self._get_courage_boost(symbol, rsi, volume_ratio)
        time_mod, _ = self._get_time_memory_modifier(symbol)
        pattern_boost, _ = self._get_symbol_pattern_score(symbol, rsi, macd_diff, volume_ratio)
        win_boost, _ = self._get_symbol_win_rate_boost(symbol)
        
        memory_boost = courage_boost + time_mod + pattern_boost + win_boost
        confidence += memory_boost
        confidence = max(0, min(100, confidence))  # حدود 0-100
        
        # الحماية من المخاطر الحرجة
        flash_crash = analysis_data.get('flash_crash_protection', {})
        flash_risk = flash_crash.get('risk_score', 0)
        liquidation_safety = advisors_intelligence.get('liquidation_safety', 50)
        
        if flash_risk >= 70:
            return {
                'action': 'DISPLAY',
                'reason': f'🚨 Flash Crash Risk ({flash_risk}%)',
                'confidence': 0
            }
        
        if liquidation_safety < 30:
            return {
                'action': 'DISPLAY',
                'reason': f'🛡️ High Liquidation Risk',
                'confidence': 0
            }
        
        # 🆕 Real-time Price Action - كشف القاع السريع Multi-Timeframe (الطبقة 1)
        realtime_bottom = None
        if self.realtime_pa and candles and len(candles) >= 5:
            try:
                # جلب الشموع من 3 أطر زمنية
                candles_1m = candles  # الشموع الحالية (1m)
                candles_5m = analysis_data.get('candles_5m', candles)  # 5m من التحليل
                candles_15m = analysis_data.get('candles_15m', candles)  # 15m من التحليل
                
                # جلب بيانات الحجم من 3 أطر زمنية
                volume_data_1m = [c.get('volume', 0) for c in candles_1m[-10:]] if len(candles_1m) >= 10 else None
                volume_data_5m = [c.get('volume', 0) for c in candles_5m[-10:]] if len(candles_5m) >= 10 else None
                volume_data_15m = [c.get('volume', 0) for c in candles_15m[-10:]] if len(candles_15m) >= 10 else None
                
                order_book = analysis_data.get('order_book')
                
                # 🌍 جلب حالة السوق من Macro Advisor
                macro_status = advisors_intelligence.get('macro_status', 'NEUTRAL')
                
                # استخدام Multi-Timeframe للكشف الدقيق
                realtime_bottom = self.realtime_pa.analyze_multi_timeframe_bottom(
                    symbol=symbol,
                    candles_1m=candles_1m,
                    candles_5m=candles_5m,
                    candles_15m=candles_15m,
                    current_price=analysis_data.get('close', 0),
                    volume_data_1m=volume_data_1m,
                    volume_data_5m=volume_data_5m,
                    volume_data_15m=volume_data_15m,
                    order_book=order_book,
                    macro_status=macro_status
                )
                
                if realtime_bottom['is_bottom']:
                    confirmations = realtime_bottom.get('confirmations', 0)
                    market_ctx = realtime_bottom.get('market_context', 'N/A')
                    threshold = realtime_bottom.get('threshold_used', 60)
                    print(f"⚡ Multi-TF Bottom [{symbol}]: {realtime_bottom['confidence']:.0f}% ({confirmations}/3 TF) | Market: {market_ctx} | Threshold: {threshold}%")
                    print(f"   Signals: {', '.join(realtime_bottom['signals'][:3])}")
                    # رفع الثقة بناءً على عدد التأكيدات
                    boost = realtime_bottom['confidence'] * 0.15 * (confirmations / 3)  # +15% max عند 3/3
                    confidence += boost
            except Exception as e:
                print(f"⚠️ Real-time multi-timeframe bottom detection error: {e}")
        
        # 🤖 القرار النهائي من meta_trading المتعلم
        MIN_BUY_CONFIDENCE = 55  # 55% احتمال نجاح
        
        if confidence >= MIN_BUY_CONFIDENCE:
            # حساب المبلغ الذكي
            try:
                amount = self._calculate_smart_amount(symbol, confidence, analysis_data)
            except:
                amount = MIN_TRADE_AMOUNT
            
            return {
                'action': 'BUY',
                'reason': f"🤖 Meta AI: {confidence:.1f}% confidence (learned from history)",
                'confidence': min(confidence, 99),
                'amount': amount,
                'advisors_intelligence': advisors_intelligence,
                'buy_probability': buy_probability
            }
        else:
            return {
                'action': 'DISPLAY',
                'reason': f"🤖 Meta AI: {confidence:.1f}% - Low confidence (need {MIN_BUY_CONFIDENCE}%+)",
                'confidence': min(confidence, 99),
                'advisors_intelligence': advisors_intelligence,
                'buy_probability': buy_probability
            }

    def should_sell(self, symbol, position, current_price, analysis, mtf, candles=None, preloaded_advisors=None):
        """🔴 قرار البيع - القفزات فورية + meta_trading للباقي"""

        # ✅ 1. فحص القفزات المفاجئة أولاً (بيع فوري - لأنها تحدث خلال ثواني)
        spike_info = self._calculate_profit_spike_features(symbol, position, current_price)
        if spike_info.get('is_spike') == 1:
            buy_price = float(position.get('buy_price', 0) or 0)
            profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            return {
                'action': 'SELL',
                'reason': f"🚀 PROFIT SPIKE: {spike_info.get('profit_jump', 0):.1f}% in {spike_info.get('time_diff', 0):.0f}s (Instant Sell)",
                'profit': profit_percent,
                'sell_votes': {},
                'sell_vote_percentage': 100.0,
                'sell_vote_count': 16,
                'total_advisors': 16
            }

        # حساب advisors_intelligence للبيع
        advisors_intelligence = {}
        risk_level = analysis.get('risk_level', 50)
        whale_tracking_score = analysis.get('whale_score', 0)
        sentiment_score = analysis.get('sentiment_score', 0)

        advisors_intelligence['risk_level'] = risk_level
        advisors_intelligence['whale_tracking_score'] = whale_tracking_score
        advisors_intelligence['sentiment_score'] = sentiment_score

        from config import MIN_SELL_CONFIDENCE

        buy_price = float(position.get('buy_price', 0) or 0)
        current_price = float(analysis.get('close', 0) or 0)
        profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
        profit_percent = profit_percent or 0.0
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)

        # ✅ 2. حساب معلومات Stop Loss (للميزات - meta_trading يقرر)
        stop_loss_info = self._calculate_stop_loss_features(position, current_price, analysis, risk_level, whale_tracking_score, sentiment_score)

        # فحص الحد الأدنى للربح قبل البيع (فقط للحماية من الخسارة)
        from config import MIN_SELL_PROFIT
        if profit_percent < MIN_SELL_PROFIT:
            # 🛡️ رسالة ديناميكية: Stop Loss إذا خسارة > -1.0% وإلا Minimum profit
            if profit_percent < -1.0:
                drop_from_peak = stop_loss_info.get('drop_from_peak', 0)
                threshold = stop_loss_info.get('threshold', 0)
                return {
                    'action': 'HOLD',
                    'reason': f'🛡️ Stop Loss Zone: {profit_percent:.2f}% | Drop: {drop_from_peak:.1f}% | Threshold: {threshold:.1f}%',
                    'profit': profit_percent
                }
            else:
                # ⚠️ لا يبيع إلا إذا وصل الحد الأدنى (حماية من البيع بخسارة)
                return {
                    'action': 'HOLD',
                    'reason': f'Minimum profit not reached: {profit_percent:.2f}% < {MIN_SELL_PROFIT}%',
                    'profit': profit_percent
                }

        # ✅ 3. إضافة معلومات Stop Loss للميزات (meta_trading يشوف المستشارين ويقرر)
        advisors_intelligence['drop_from_peak'] = stop_loss_info.get('drop_from_peak', 0)
        advisors_intelligence['stop_threshold'] = stop_loss_info.get('threshold', 0)
        advisors_intelligence['is_stop_loss'] = stop_loss_info.get('is_stop_loss', 0)
        
        # ✅ إضافة المستشارين الثابتين للـ Stop Loss
        try:
            # 1. Fibonacci للـ Stop Loss - مستويات فيبوناتشي كـ Stop ديناميكي
            fib_analyzer = self.advisor_manager.get('FibonacciAnalyzer') if self.advisor_manager else None
            if fib_analyzer:
                current_price_val = analysis.get('close', 0)
                # فحص إذا السعر عند مقاومة فيبوناتشي (قد يكون قمة)
                is_at_resistance, resistance_boost = fib_analyzer.is_at_resistance(
                    current_price=current_price_val,
                    analysis=analysis,
                    tolerance=1.0,  # نطاق أوسع للـ Stop Loss
                    volume_ratio=volume_ratio,
                    symbol=symbol
                )
                advisors_intelligence['fib_resistance_stop'] = resistance_boost if is_at_resistance else 0
        except: 
            advisors_intelligence['fib_resistance_stop'] = 0
        
        try:
            # 2. Volume Forecast للـ Stop Loss - انهيار الحجم = Stop أضيق
            volume_engine = self.advisor_manager.get('VolumeForecastEngine') if self.advisor_manager else None
            if volume_engine:
                candles_data = analysis.get('candles', [])
                if len(candles_data) >= 20:
                    volumes = [c.get('volume', 0) for c in candles_data[-20:]]
                    current_hour = datetime.now().hour
                    prediction = volume_engine.predict_next_volume(symbol, volumes, current_hour)
                    
                    # انهيار الحجم = علامة ضعف = Stop Loss أضيق
                    if prediction['trend'] == 'DECREASING' and prediction['momentum'] < -20:
                        advisors_intelligence['volume_collapse_stop'] = 1  # إشارة قوية
                    elif prediction['trend'] == 'DECREASING':
                        advisors_intelligence['volume_collapse_stop'] = 0.5  # إشارة متوسطة
                    else:
                        advisors_intelligence['volume_collapse_stop'] = 0
        except:
            advisors_intelligence['volume_collapse_stop'] = 0
        
        try:
            # 3. Adaptive Intelligence للـ Stop Loss - تعديل بناءً على تاريخ العملة
            adaptive_ai = self.advisor_manager.get('AdaptiveIntelligence') if self.advisor_manager else None
            if adaptive_ai:
                profile = adaptive_ai.get_symbol_profile(symbol)
                if profile:
                    avg_profit = profile.get('avg_profit', 0) or 0
                    # عملات متقلبة (ربح عالي) = Stop أوسع
                    # عملات مستقرة (ربح منخفض) = Stop أضيق
                    if avg_profit > 5:
                        advisors_intelligence['adaptive_stop_multiplier'] = 1.3  # Stop أوسع
                    elif avg_profit < 2:
                        advisors_intelligence['adaptive_stop_multiplier'] = 0.7  # Stop أضيق
                    else:
                        advisors_intelligence['adaptive_stop_multiplier'] = 1.0
        except:
            advisors_intelligence['adaptive_stop_multiplier'] = 1.0
        
        try:
            # 4. Macro Trend للبيع - انعكاس السوق الكلي
            macro_advisor = self.advisor_manager.get('MacroTrendAdvisor') if self.advisor_manager else None
            if macro_advisor:
                macro_status = macro_advisor.get_macro_status()
                # Bear Market = بيع أسرع
                if 'BEAR' in macro_status:
                    advisors_intelligence['macro_bear_signal'] = 1
                    advisors_intelligence['macro_trend_sell'] = 85  # إشارة بيع قوية
                elif 'BULL' in macro_status:
                    advisors_intelligence['macro_bear_signal'] = 0
                    advisors_intelligence['macro_trend_sell'] = 20  # لا بيع
                else:
                    advisors_intelligence['macro_bear_signal'] = 0
                    advisors_intelligence['macro_trend_sell'] = 50  # محايد
        except:
            advisors_intelligence['macro_bear_signal'] = 0
            advisors_intelligence['macro_trend_sell'] = 50

        # ✅ 4. بناء الميزات لنموذج meta_trading
        # جلب symbol_memory من الكاش (محملة عند التشغيل)
        from memory.memory_cache import MemoryCache
        cache = MemoryCache()
        symbol_memory = cache.get(f'symbol_mem_{symbol}') or {}
        if not symbol_memory and self.storage:
            symbol_memory = self.storage.get_symbol_memory(symbol) or {}
        
        features = self._build_meta_features(
            rsi=rsi,
            macd_diff=macd_diff,
            volume_ratio=volume_ratio,
            price_momentum=analysis.get('price_momentum', 0),
            atr=analysis.get('atr', 2.5),
            analysis_data=analysis,
            advisors_intelligence=advisors_intelligence,
            symbol_memory=symbol_memory
        )

        # =========================================================
        # 🗣️ 4. استشارة المستشارين عن البيع
        # =========================================================
        sell_vote_count = 0
        total_advisors = 16
        sell_votes = {}
        
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if not dl_client:
                pass
            elif dl_client:
                # بناء candle_analysis من تحليل القمة
                peak = analysis.get('peak', {})
                reversal = analysis.get('reversal', {})
                candle_analysis = {
                    'is_reversal': peak.get('candle_signal', False),
                    'is_bottom':   reversal.get('candle_signal', False),
                    'is_peak':     peak.get('candle_signal', False),
                    'is_rejection': peak.get('candle_signal', False),
                    'reversal_confidence': reversal.get('confidence', 0),
                    'peak_confidence':     peak.get('confidence', 0),
                }

                # جلب النصائح من كل مستشار للبيع
                advisors_advice = dl_client.get_advice(
                    rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                    price_momentum=analysis.get('price_momentum', 0),
                    confidence=profit_percent,
                    liquidity_metrics=analysis.get('liquidity_metrics'),
                    market_sentiment=analysis.get('market_sentiment', None),
                    candle_analysis=candle_analysis,
                    analysis_data=analysis,
                    action='SELL'
                )

                # حساب الأصوات
                bearish_keywords = ['Bearish', 'Sell', 'Overbought', 'Peak', 'Reversal']
                sell_vote_count = 0

                for name, adv_text in advisors_advice.items():
                    has_voted = any(k in str(adv_text) for k in bearish_keywords)
                    if has_voted:
                        sell_vote_count += 1
                        sell_votes[name] = 1
                    else:
                        sell_votes[name] = 0

                # إضافة أصوات المستشارين الجديدة
                try:
                    anomaly_detector = self.advisor_manager.get('AnomalyDetector') if self.advisor_manager else None
                    if anomaly_detector and analysis.get('anomaly_score', 0) > 70:
                        sell_vote_count += 1
                        sell_votes['AnomalyDetector'] = 1
                    else:
                        sell_votes['AnomalyDetector'] = 0
                except: sell_votes['AnomalyDetector'] = 0

                try:
                    liquidity_analyzer = self.advisor_manager.get('LiquidityAnalyzer') if self.advisor_manager else None
                    if liquidity_analyzer and analysis.get('liquidity_score', 50) < 30:
                        sell_vote_count += 1
                        sell_votes['LiquidityAnalyzer'] = 1
                    else:
                        sell_votes['LiquidityAnalyzer'] = 0
                except: sell_votes['LiquidityAnalyzer'] = 0

                try:
                    whale_tracking = self.advisor_manager.get('SmartMoneyTracker') if self.advisor_manager else None
                    if whale_tracking and analysis.get('whale_dumping', False):
                        sell_vote_count += 1
                        sell_votes['SmartMoneyTracker'] = 1
                    else:
                        sell_votes['SmartMoneyTracker'] = 0
                except: sell_votes['SmartMoneyTracker'] = 0

                try:
                    cross_exchange = self.advisor_manager.get('CrossExchange') if self.advisor_manager else None
                    if cross_exchange and abs(analysis.get('price_diff_pct', 0)) > 1.0:
                        sell_vote_count += 1
                        sell_votes['CrossExchange'] = 1
                    else:
                        sell_votes['CrossExchange'] = 0
                except: sell_votes['CrossExchange'] = 0
        except Exception as e:
            sell_vote_count = 0

        # ✅ 5. استخدام meta_trading للتنبؤ بالبيع
        sell_probability = 0.5
        sell_confidence = 50
        
        # 🆕 Real-time Price Action - كشف القمة السريع Multi-Timeframe (الطبقة 1)
        realtime_peak = None
        if self.realtime_pa and candles and len(candles) >= 5:
            try:
                # جلب الشموع من 3 أطر زمنية
                candles_1m = candles  # الشموع الحالية (1m)
                candles_5m = analysis.get('candles_5m', candles)  # 5m من التحليل
                candles_15m = analysis.get('candles_15m', candles)  # 15m من التحليل
                
                # جلب بيانات الحجم من 3 أطر زمنية
                volume_data_1m = [c.get('volume', 0) for c in candles_1m[-10:]] if len(candles_1m) >= 10 else None
                volume_data_5m = [c.get('volume', 0) for c in candles_5m[-10:]] if len(candles_5m) >= 10 else None
                volume_data_15m = [c.get('volume', 0) for c in candles_15m[-10:]] if len(candles_15m) >= 10 else None
                
                highest_price = position.get('highest_price', float(position.get('buy_price', 0) or 0))
                order_book = analysis.get('order_book')
                
                # 🌍 جلب حالة السوق من Macro Advisor
                macro_status = advisors_intelligence.get('macro_status', 'NEUTRAL')
                
                # استخدام Multi-Timeframe للكشف الدقيق
                realtime_peak = self.realtime_pa.analyze_multi_timeframe_peak(
                    symbol=symbol,
                    candles_1m=candles_1m,
                    candles_5m=candles_5m,
                    candles_15m=candles_15m,
                    current_price=current_price,
                    highest_price=highest_price,
                    volume_data_1m=volume_data_1m,
                    volume_data_5m=volume_data_5m,
                    volume_data_15m=volume_data_15m,
                    order_book=order_book,
                    macro_status=macro_status
                )
                
                if realtime_peak['is_peak']:
                    confirmations = realtime_peak.get('confirmations', 0)
                    market_ctx = realtime_peak.get('market_context', 'N/A')
                    threshold = realtime_peak.get('threshold_used', 60)
                    print(f"⚡ Multi-TF Peak [{symbol}]: {realtime_peak['confidence']:.0f}% ({confirmations}/3 TF) | Market: {market_ctx} | Threshold: {threshold}%")
                    print(f"   Signals: {', '.join(realtime_peak['signals'][:3])}")
                    # رفع ثقة البيع بناءً على عدد التأكيدات
                    boost = realtime_peak['confidence'] * 0.2 * (confirmations / 3)  # +20% max عند 3/3
                    sell_confidence += boost
            except Exception as e:
                print(f"⚠️ Real-time multi-timeframe peak detection error: {e}")
        
        if self.meta_model:
            try:
                import pandas as pd
                X = pd.DataFrame([features], columns=self._get_meta_feature_names())
                sell_probability = 1 - self.meta_model.predict_proba(X)[0][1]
                sell_confidence = sell_probability * 100
            except Exception as e:
                print(f"⚠️ Meta sell prediction error: {e}")
        else:
            print("⚠️ Meta: meta_trading model not loaded, using default confidence")

        # ✅ 6. القرار النهائي من meta_trading (يحلب العملة ويبيع بالقمة الحقيقية)
        MIN_SELL_CONFIDENCE = 70  # 70% ثقة بالقمة (أعلى من 60% لحلب العملة)
        
        if sell_confidence >= MIN_SELL_CONFIDENCE:
            gc.collect()
            return {
                'action': 'SELL',
                'reason': f'🤖 Meta AI: {sell_confidence:.1f}% sell confidence (REAL PEAK detected - milked the coin)',
                'profit': profit_percent,
                'optimism_penalty': 0,
                'sell_votes': {},
                'sell_confidence': sell_confidence
            }
        else:
            gc.collect()
            return {
                'action': 'HOLD',
                'reason': f'🤖 Meta AI: {sell_confidence:.1f}% - need 70%+ for REAL PEAK',
                'profit': profit_percent,
                'sell_confidence': sell_confidence
            }

        # نقاط القمة (تبدأ من 0)
        peak_confidence = 0
        peak_reasons = []

        # تحسين كشف القمة بالمشاعر والزخم
        sentiment_score = analysis.get('sentiment_score', 0)
        price_momentum = analysis.get('price_momentum', 0)

        if sentiment_score < -5:
            peak_confidence += 20  # مشاعر سلبية قوية = قمة محتملة
            peak_reasons.append("Sentiment Very Bearish (+20)")
        elif sentiment_score < -3:
            peak_confidence += 10
            peak_reasons.append("Sentiment Bearish (+10)")

        if price_momentum < -1.0:
            peak_confidence += 20  # زخم هابط قوي
            peak_reasons.append("Strong Negative Momentum (+20)")
        elif price_momentum < -0.5:
            peak_confidence += 12
            peak_reasons.append("Negative Momentum (+12)")

        # =========================================================
        # 🌟 المستشارين الجدد - يكشفون القمة قبل الانهيار
        # =========================================================
        
        # --- 🎯 1. Trend Early Detector - كشف إنهاك الاتجاه ---
        try:
            trend_detector = self.advisor_manager.get('TrendEarlyDetector') if self.advisor_manager else None
            if trend_detector:
                candles_data = analysis.get('candles', [])
                if len(candles_data) >= 30:
                    import pandas as pd
                    df = pd.DataFrame(candles_data)
                    
                    # كشف إنهاك الاتجاه الصاعد
                    exhaustion = trend_detector.get_trend_exhaustion_score(df, 'BULLISH')
                    
                    if exhaustion >= 75:
                        peak_confidence += 30
                        peak_reasons.append(f"Trend Exhaustion: {exhaustion}% (+30)")
                        print(f"🎯 Trend Exhaustion Detected: {exhaustion}%")
                    elif exhaustion >= 50:
                        peak_confidence += 15
                        peak_reasons.append(f"Trend Weakening: {exhaustion}% (+15)")
        except Exception as e:
            print(f"⚠️ Trend detector error: {e}")
        
        # --- 📊 2. Volume Forecast - كشف انهيار الحجم + Delta Volume ---
        try:
            volume_engine = self.advisor_manager.get('VolumeForecastEngine') if self.advisor_manager else None
            if volume_engine:
                candles_data = analysis.get('candles', [])
                if len(candles_data) >= 20:
                    volumes = [c.get('volume', 0) for c in candles_data[-20:]]
                    current_hour = datetime.now().hour
                    
                    prediction = volume_engine.predict_next_volume(symbol, volumes, current_hour)
                    
                    # انهيار الحجم = إشارة قمة
                    if prediction['trend'] == 'DECREASING' and prediction['momentum'] < -20:
                        peak_confidence += 20
                        peak_reasons.append(f"Volume Collapse: {prediction['momentum']:.1f}% (+20)")
                        print(f"📊 Volume Collapse Detected: {prediction['momentum']:.1f}%")
                    elif prediction['trend'] == 'DECREASING':
                        peak_confidence += 10
                        peak_reasons.append(f"Volume Declining (+10)")
                    
                    # 🆕 Delta Volume - الفرق بين حجم الشراء والبيع
                    try:
                        order_book = analysis.get('order_book')
                        if order_book and order_book.get('bids') and order_book.get('asks'):
                            # حساب Delta من Order Book
                            bid_volume = sum(b[1] for b in order_book['bids'][:20])
                            ask_volume = sum(a[1] for a in order_book['asks'][:20])
                            delta_ratio = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
                            
                            # Delta سالب كبير = ضغط بيع قوي (قمة قريبة)
                            if delta_ratio < -0.3:
                                peak_confidence += 25
                                peak_reasons.append(f"Delta Volume: Strong Sell Pressure ({delta_ratio:.2f}) (+25)")
                                print(f"💥 Delta Volume Alert: Strong Sell Pressure {delta_ratio:.2f}")
                            elif delta_ratio < -0.15:
                                peak_confidence += 15
                                peak_reasons.append(f"Delta Volume: Sell Pressure ({delta_ratio:.2f}) (+15)")
                    except Exception as delta_err:
                        print(f"⚠️ Delta Volume error: {delta_err}")
        except Exception as e:
            print(f"⚠️ Volume forecast error: {e}")
        
        # --- 🧬 3. Adaptive Intelligence - تعديل حد البيع + Profit Velocity ---
        try:
            adaptive_ai = self.advisor_manager.get('AdaptiveIntelligence') if self.advisor_manager else None
            if adaptive_ai:
                profile = adaptive_ai.get_symbol_profile(symbol)
                if profile:
                    # إذا العملة تاريخياً تنهار بسرعة، نبيع أسرع
                    if (profile.get('avg_profit') or 0) < 2.0 and profit_percent > 5.0:
                        peak_confidence += 15
                        peak_reasons.append(f"Adaptive: Quick Exit for {symbol} (+15)")
                        print(f"🧬 Adaptive: {symbol} tends to crash fast, exit now!")
                    
                    # 🆕 Profit Velocity - سرعة الربح
                    try:
                        spike_info = self._calculate_profit_spike_features(symbol, position, current_price)
                        profit_jump = spike_info.get('profit_jump', 0)
                        time_diff = spike_info.get('time_diff', 0)
                        
                        if time_diff > 0 and time_diff < 60:
                            velocity = profit_jump / (time_diff / 60)  # ربح لكل دقيقة
                            
                            # سرعة الربح تتباطأ = قمة قريبة
                            if velocity < -2.0:  # يخسر 2%+ في الدقيقة
                                peak_confidence += 20
                                peak_reasons.append(f"Profit Velocity Crash: {velocity:.1f}%/min (+20)")
                                print(f"⚡ Profit Velocity Crash: {velocity:.1f}%/min")
                            elif velocity < -0.5:
                                peak_confidence += 10
                                peak_reasons.append(f"Profit Slowing: {velocity:.1f}%/min (+10)")
                    except Exception as vel_err:
                        print(f"⚠️ Profit Velocity error: {vel_err}")
        except Exception as e:
            print(f"⚠️ Adaptive AI error: {e}")

        # =========================================================
        # 🗣️ 4. استشارة المستشارين الـ 12 عن القمة (بما فيهم candle_expert - أهم واحد)
        # =========================================================
        sell_vote_count = 0
        total_advisors = 16  # ثابت 16 مستشار
        sell_votes = {}
        candle_confirmed = False  # تأكيد من Candle Expert
        
        print(f"\n📊 Consulting {total_advisors} Sell Advisors...\n")
        
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if not dl_client:
                print("⚠️ dl_client not available - skipping advisor voting")
                print("="*70 + "\n")
            elif dl_client:
                # بناء candle_analysis من تحليل القمة
                peak = analysis.get('peak', {})
                reversal = analysis.get('reversal', {})
                candle_analysis = {
                    'is_reversal': peak.get('candle_signal', False),
                    'is_bottom':   reversal.get('candle_signal', False),
                    'is_peak':     peak.get('candle_signal', False),
                    'is_rejection': peak.get('candle_signal', False),
                    'reversal_confidence': reversal.get('confidence', 0),
                    'peak_confidence':     peak.get('confidence', 0),
                }

                # جلب النصائح من كل مستشار للبيع (بما فيهم candle_expert)
                advisors_advice = dl_client.get_advice(
                    rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                    price_momentum=analysis.get('price_momentum', 0),
                    confidence=profit_percent,  # نستخدم الربح كثقة
                    liquidity_metrics=analysis.get('liquidity_metrics'),
                    market_sentiment=analysis.get('market_sentiment', None),
                    candle_analysis=candle_analysis,
                    analysis_data=analysis,
                    action='SELL'  # 🔑 مهم: نخبرهم إننا نسأل عن البيع
                )

                # حساب الأصوات الإيجابية للبيع (Bearish Keywords)
                bearish_keywords = ['Bearish', 'Sell', 'Overbought', 'Peak', 'Reversal']

                sell_vote_count = 0

                for name, adv_text in advisors_advice.items():
                    has_voted = any(k in str(adv_text) for k in bearish_keywords)
                    if has_voted:
                        sell_vote_count += 1
                        sell_votes[name] = 1
                    else:
                        sell_votes[name] = 0

                # ✅ التركيز على Candle Expert كأهم واحد لتأكيد القمة الصحيحة
                if 'candle_expert' in advisors_advice and any(k in str(advisors_advice['candle_expert']) for k in bearish_keywords):
                    candle_confirmed = True
                    peak_confidence += 15  # رفع من 5 إلى 15 لأن candle_expert أهم مستشار للقمة

                total_advisors = 16  # ثابت 16 مستشار

                # إضافة أصوات المستشارين الجديدة
                try:
                    anomaly_detector = self.advisor_manager.get('AnomalyDetector') if self.advisor_manager else None
                    if anomaly_detector and analysis.get('anomaly_score', 0) > 70:
                        sell_vote_count += 1  # يصوت للبيع عند شذوذ عالي
                        sell_votes['AnomalyDetector'] = 1
                    else:
                        sell_votes['AnomalyDetector'] = 0
                except: sell_votes['AnomalyDetector'] = 0

                try:
                    liquidity_analyzer = self.advisor_manager.get('LiquidityAnalyzer') if self.advisor_manager else None
                    if liquidity_analyzer and analysis.get('liquidity_score', 50) < 30:
                        sell_vote_count += 1  # يصوت للبيع عند سيولة منخفضة
                        sell_votes['LiquidityAnalyzer'] = 1
                    else:
                        sell_votes['LiquidityAnalyzer'] = 0
                except: sell_votes['LiquidityAnalyzer'] = 0

                try:
                    whale_tracking = self.advisor_manager.get('SmartMoneyTracker') if self.advisor_manager else None
                    if whale_tracking and analysis.get('whale_dumping', False):
                        sell_vote_count += 1  # يصوت للبيع عند بيع الحيتان
                        sell_votes['SmartMoneyTracker'] = 1
                    else:
                        sell_votes['SmartMoneyTracker'] = 0
                except: sell_votes['SmartMoneyTracker'] = 0

                try:
                    cross_exchange = self.advisor_manager.get('CrossExchange') if self.advisor_manager else None
                    if cross_exchange and abs(analysis.get('price_diff_pct', 0)) > 1.0:
                        sell_vote_count += 1  # يصوت للبيع عند فروقات أسعار كبيرة
                        sell_votes['CrossExchange'] = 1
                    else:
                        sell_votes['CrossExchange'] = 0
                except: sell_votes['CrossExchange'] = 0

                total_advisors = 16  # رفع من 12 إلى 16
                
                # 🔍 طباعة نتائج التصويت
                print(f"\n📊 Sell Votes Summary:")
                for advisor_name, vote in sell_votes.items():
                    vote_status = "✅ SELL" if vote == 1 else "❌ HOLD"
                    print(f"  {vote_status} {advisor_name}")
                print(f"\n📈 Total: {sell_vote_count}/{total_advisors} voted SELL")
                print("="*70 + "\n")
        except Exception as e:
            print(f"⚠️ Sell voting error [{symbol}]: {e}")
            sell_vote_count = 0
            total_advisors = 16

        # =========================================================
        # 👑 5. الملك يقرر بناءً على القمة + المستشارين
        # =========================================================
        peak_analysis = analysis.get('peak', {})
        peak_score = peak_analysis.get('confidence', 0) + peak_confidence
        
        # 🆕 عدد المؤشرات التي انعكست فعلاً من analyze_peak
        peak_reversal_signals = peak_analysis.get('reversal_signals', 0)

        king_wants_to_sell = False
        sell_reason = ""

        # فحص التفاؤل والأمل
        sentiment_confirmed = False
        try:
            sentiment = analysis.get('sentiment', {})
            if sentiment.get('score', 0) < -1:
                sentiment_confirmed = True
        except:
            sentiment_confirmed = False

        # =========================================================
        # 🎯 القمة الحقيقية = انعكاس واضح من مؤشرات متعددة معاً
        # القاعدة: لا بيع إلا إذا انعكست مؤشران على الأقل من analyze_peak
        # =========================================================

        # قمة قوية جداً: مستشارون + مؤشرات انعكست + sentiment
        if sell_vote_count >= 8 and peak_confidence >= 70 and sentiment_confirmed and peak_reversal_signals >= 2:
            king_wants_to_sell = True
            sell_reason = f"Ultimate Peak: {sell_vote_count}/{total_advisors} votes + {peak_reversal_signals} signals + Sentiment (+{profit_percent:.1f}%)"

        # قمة بإشارات قوية من analyze_peak (مؤشران انعكسوا على الأقل)
        elif peak_score >= 80 and peak_reversal_signals >= 2:
            king_wants_to_sell = True
            sell_reason = f"Strong Peak Signal: {peak_score}/110 pts + {peak_reversal_signals} reversal signals (+{profit_percent:.1f}%)"

        # تقني + مستشارون + انعكاس مؤشرين
        elif rsi > 70 and macd_diff < -1 and sell_vote_count >= 4 and peak_reversal_signals >= 2:
            king_wants_to_sell = True
            sell_reason = f"Technical Peak: RSI {rsi:.0f} + MACD {macd_diff:.1f} + {sell_vote_count} votes (+{profit_percent:.1f}%)"

        # قمة قوية جداً بنقاط عالية مع انعكاس
        elif peak_score >= 95 and peak_reversal_signals >= 2:
            king_wants_to_sell = True
            sell_reason = f"Strong Reversal (Peak: {peak_score}, Signals: {peak_reversal_signals})"

        # مستشارون جدد + انعكاس مؤكد من مؤشرين على الأقل
        elif peak_confidence >= 50 and peak_reversal_signals >= 3:
            king_wants_to_sell = True
            sell_reason = f"Advisors Alert + {peak_reversal_signals} Signals: {', '.join(peak_reasons)}"

        # =========================================================
        # 👑 6. القرار النهائي
        # =========================================================
        sell_vote_percentage = (sell_vote_count / total_advisors * 100) if total_advisors > 0 else 0

        if candle_confirmed and sell_vote_count >= 6:
            risk_vote = sell_votes.get('risk', 0)
            anomaly_vote = sell_votes.get('anomaly', 0)
            if risk_vote or anomaly_vote:
                peak_confidence += 10

        # قمة حقيقية محققة: نقاط عالية + مؤشران انعكسوا + sentiment
        if peak_confidence >= 60 and len(peak_reasons) >= 2 and sentiment_confirmed and peak_reversal_signals >= 2:
            return {
                'action': 'SELL',
                'reason': f'REAL PEAK: {", ".join(peak_reasons)} (Conf:{peak_confidence}, Signals:{peak_reversal_signals})',
                'profit': profit_percent,
                'optimism_penalty': 0,
                'sell_votes': sell_votes,
                'peak_score': peak_score,
                'sell_vote_percentage': sell_vote_percentage,
                'sell_vote_count': sell_vote_count,
                'total_advisors': total_advisors
            }

        if king_wants_to_sell:
            optimism_penalty = round((profit_percent - 50) * 0.3, 2) if profit_percent > 50 else 0
            return {
                'action': 'SELL',
                'reason': sell_reason,
                'profit': profit_percent,
                'optimism_penalty': optimism_penalty,
                'sell_votes': sell_votes,
                'peak_score': peak_score,
                'sell_vote_percentage': sell_vote_percentage,
                'sell_vote_count': sell_vote_count,
                'total_advisors': total_advisors
            }
        
        # =========================================================
        # 🛡️ 7. Wave Protection الذكي + Cascade Risk من Liquidation Shield
        # =========================================================
        highest_price = position.get('highest_price', buy_price)
        drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0

        # حساب ديناميكي بناءً على المستشارين والمؤشرات - لا أرقام ثابتة!
        atr_p = analysis.get('atr_percent', 2.5)
        risk_level = advisors_intelligence.get('risk_level', 50)  # من Risk Manager
        whale_tracking_score = advisors_intelligence.get('whale_tracking_score', 0)  # من Whale Tracking
        sentiment_score = advisors_intelligence.get('sentiment_score', 0)  # من Sentiment
        volume_ratio = analysis.get('volume_ratio', 1.0)  # حجم التداول
        peak_score = advisors_intelligence.get('peak_score', 50)  # نقاط القمة

        # العتبة الأساسية من ATR فقط (ديناميكية كاملة)
        base_threshold = atr_p * 2.5  # يبدأ من ATR × 2.5 ليكون أكثر مرونة

        # حد أدنى ديناميكي بناءً على المخاطر (ليس ثابت)
        min_threshold = risk_level / 25  # مخاطر 100 = 4% حد أدنى (أصغر)
        base_threshold = max(min_threshold, base_threshold)

        # تعديل بناءً على المخاطر: مخاطر عالية = حماية أسرع
        risk_modifier = (risk_level - 50) / 100  # من -0.5 إلى +0.5
        base_threshold += risk_modifier * 3  # يضيف أو ينقص 3%

        # تعديل بناءً على الحيتان: حيتان تشتري = حماية أقل
        whale_modifier = whale_tracking_score / 200  # من 0 إلى 0.5
        base_threshold -= whale_modifier * 2  # يقلل الحماية إذا الحيتان إيجابية

        # تعديل بناءً على المشاعر: مشاعر سلبية = حماية أسرع
        sentiment_modifier = max(-10, min(10, sentiment_score)) / 100  # من -0.1 إلى +0.1
        base_threshold += sentiment_modifier * 2  # يزيد أو يقلل قليلاً

        # 🆕 Cascade Risk من Liquidation Shield - حماية من التصفيات المتتالية
        try:
            liq_shield = self.advisor_manager.get('LiquidationShield') if self.advisor_manager else None
            if liq_shield:
                order_book = analysis.get('order_book')
                if order_book:
                    liq_analysis = liq_shield.analyze_liquidation_risk(symbol, current_price, order_book)
                    cascade_risk = liq_analysis.get('cascade_risk', 'LOW')
                    
                    # Cascade Risk عالي = Stop Loss أضيق (حماية أسرع)
                    if cascade_risk == 'HIGH':
                        base_threshold *= 0.4  # يقلل العتبة 60% (حماية أسرع)
                        print(f"🛡️ Cascade Risk HIGH: Stop Loss tightened to {base_threshold:.1f}%")
                    elif cascade_risk == 'MEDIUM':
                        base_threshold *= 0.7  # يقلل العتبة 30%
                        print(f"🛡️ Cascade Risk MEDIUM: Stop Loss adjusted to {base_threshold:.1f}%")
        except Exception as cascade_err:
            print(f"⚠️ Cascade Risk error: {cascade_err}")

        # الحدود الآمنة
        trailing_threshold = max(1.0, min(15.0, base_threshold))  # من 1% إلى 15%
        
        # 🆕 Real-time Stop Loss Trigger - كشف مبكر مع Multi-Timeframe
        if self.realtime_pa and candles and len(candles) >= 3:
            try:
                # استخدام الشموع 1m للـ Stop Loss (الأسرع)
                stop_trigger = self.realtime_pa.analyze_stop_loss_trigger(
                    candles=candles,
                    current_price=current_price,
                    highest_price=highest_price,
                    stop_threshold=trailing_threshold
                )
                
                if stop_trigger['trigger_soon']:
                    time_estimate = stop_trigger.get('time_estimate', 999)
                    print(f"⚡ Stop Loss Trigger Soon [{symbol}]: {stop_trigger['confidence']:.0f}% - ETA: {time_estimate:.1f}min")
                    
                    # تضييق Stop Loss بناءً على مدى السرعة
                    if time_estimate < 2:  # أقل من دقيقتين
                        trailing_threshold *= 0.6  # تقليل 40% (حماية قوية)
                    elif time_estimate < 5:  # أقل من 5 دقائق
                        trailing_threshold *= 0.8  # تقليل 20%
                    else:
                        trailing_threshold *= 0.9  # تقليل 10%
            except Exception as e:
                print(f"⚠️ Real-time stop loss detection error: {e}")

        if drop_from_peak >= trailing_threshold:
            gc.collect()
            return {
                'action': 'SELL',
                'reason': f'Wave Protection: -{drop_from_peak:.1f}% from peak (threshold: {trailing_threshold:.1f}%)',
                'profit': profit_percent,
                'optimism_penalty': 0,
                'sell_votes': sell_votes,
                'peak_score': peak_score
            }

        # =========================================================
        # ✅ 8. HOLD - مستمر في ركوب الموجة
        # =========================================================
        gc.collect()
        return {
            'action': 'HOLD', 
            'reason': f'Wave Riding | Profit: {profit_percent:+.1f}% | Peak: {peak_score} | Votes: {sell_vote_count}/{total_advisors}', 
            'profit': profit_percent,
            'sell_votes': sell_votes,
            'peak_score': peak_score
        }

    def _get_whale_fingerprint_score(self, symbol):
        """يراجع ذاكرة الحيتان: هل صفقات الحيتان السابقة أدت لربح أم فخ؟"""
        try:
            # 🔒 استخدام الكاش الرام حصراً (تحديث 30 دقيقة)
            memory = self.storage.get_symbol_memory(symbol)
            if not memory: return 0
            
            # إذا كانت آخر بصمة حوت في الذاكرة مرتبطة بربح تاريخي
            last_whale_conf = memory.get('whale_conf', 0)
            plr = memory.get('profit_loss_ratio', 1.0)

            result = 0
            if last_whale_conf > 10 and plr > 1.2:
                result = 15  # الحيتان في هذه العملة يشترون للصعود
            elif last_whale_conf > 10 and plr < 0.8:
                result = -25 # الحيتان في هذه العملة يستخدمون الحجم للتصريف (Fake Wall)
            
            # ✅ تحرير الرام فوراً بعد معالجة بيانات الذاكرة
            del memory
            gc.collect()
            return result
        except Exception:
            pass
        return 0

    def _build_meta_features(self, rsi, macd_diff, volume_ratio, price_momentum, atr, 
                            analysis_data, advisors_intelligence, symbol_memory):
        """بناء الميزات لنموذج meta_trading (48 ميزة)"""
        
        # Technical (5)
        features = [
            rsi,
            macd_diff,
            volume_ratio,
            price_momentum,
            atr
        ]
        
        # News (6)
        news = analysis_data.get('news', {})
        features.extend([
            news.get('news_score', 0),
            news.get('positive', 0),
            news.get('negative', 0),
            news.get('total', 0),
            news.get('positive', 0) / (news.get('negative', 0) + 0.001),
            1 if news.get('total', 0) > 0 else 0
        ])
        
        # Sentiment (5)
        sentiment = analysis_data.get('sentiment', {})
        fear_greed = sentiment.get('fear_greed', 50)
        features.extend([
            sentiment.get('news_sentiment', 0),
            fear_greed,
            (fear_greed - 50) / 50,
            1 if fear_greed < 30 else 0,
            1 if fear_greed > 70 else 0
        ])
        
        # Liquidity (4)
        liquidity = analysis_data.get('liquidity_metrics', {})
        liq_score = liquidity.get('liquidity_score', 50)
        features.extend([
            liq_score,
            liquidity.get('depth_ratio', 1.0),
            liquidity.get('price_impact', 0.5),
            1 if liq_score > 70 else 0
        ])
        
        # Smart Money (2)
        features.extend([
            advisors_intelligence.get('whale_activity', 0),
            analysis_data.get('exchange_inflow', 0)
        ])
        
        # Social (2)
        features.extend([
            analysis_data.get('social_volume', 0),
            advisors_intelligence.get('sentiment_score', 0)
        ])
        
        # Consultants (3)
        features.extend([
            0.5,  # consensus placeholder
            0,    # buy_count placeholder
            0     # sell_count placeholder
        ])
        
        # Derived (5)
        features.extend([
            advisors_intelligence.get('risk_level', 50),
            50,  # opportunity placeholder
            50,  # market_quality placeholder
            abs(price_momentum) / 10.0,
            atr * 10
        ])
        
        # Symbol Memory - Basic (5)
        features.extend([
            symbol_memory.get('win_rate', 0),
            symbol_memory.get('avg_profit', 0),
            symbol_memory.get('trap_count', 0),
            symbol_memory.get('total_trades', 0),
            1 if symbol_memory.get('win_rate', 0) > 0.6 else 0
        ])
        
        # Symbol Memory - New 7
        features.extend([
            symbol_memory.get('sentiment_avg', 0),
            symbol_memory.get('whale_avg', 0),
            symbol_memory.get('profit_loss_ratio', 1.0),
            0,  # volume_trend placeholder
            symbol_memory.get('panic_avg', 0),
            symbol_memory.get('optimism_avg', 0),
            symbol_memory.get('smart_stop_loss', 0)
        ])
        
        # Symbol Memory - New 4 columns
        features.extend([
            symbol_memory.get('courage_boost', 0),
            symbol_memory.get('time_memory', 0),
            symbol_memory.get('pattern_score', 0),
            symbol_memory.get('win_rate_boost', 0)
        ])
        
        # Context (1)
        features.append(24)  # hours_held placeholder
        
        return features
    
    def _get_meta_feature_names(self):
        """أسماء الميزات (48 ميزة)"""
        return [
            # Technical (5)
            'rsi', 'macd_diff', 'volume_ratio', 'price_momentum', 'atr',
            # News (6)
            'news_score', 'news_pos', 'news_neg', 'news_total', 'news_ratio', 'has_news',
            # Sentiment (5)
            'sent_score', 'fear_greed', 'fear_greed_norm', 'is_fearful', 'is_greedy',
            # Liquidity (4)
            'liq_score', 'depth_ratio', 'price_impact', 'good_liq',
            # Smart Money (2)
            'whale_activity', 'exchange_inflow',
            # Social (2)
            'social_volume', 'market_sentiment',
            # Consultants (3)
            'consensus', 'buy_count', 'sell_count',
            # Derived (5)
            'risk_score', 'opportunity', 'market_quality', 'momentum_strength', 'volatility_level',
            # Symbol Memory - Basic (5)
            'sym_win_rate', 'sym_avg_profit', 'sym_trap_count', 'sym_total', 'sym_is_reliable',
            # Symbol Memory - New 7
            'sym_sentiment_avg', 'sym_whale_avg', 'sym_profit_loss_ratio', 'sym_volume_trend',
            'sym_panic_avg', 'sym_optimism_avg', 'sym_smart_stop_loss',
            # Symbol Memory - New 4 columns
            'sym_courage_boost', 'sym_time_memory', 'sym_pattern_score', 'sym_win_rate_boost',
            # Context (1)
            'hours_held'
        ]

    def _calculate_smart_amount(self, symbol, confidence, analysis):
        """🤖 meta_trading المتعلم يحدد المبلغ بناءً على المؤشرات والسوق"""
        try:
            from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT
            
            # ✅ meta_trading يحدد المبلغ بناءً على الثقة والمؤشرات
            # الثقة من 50 إلى 100 → المبلغ من 12 إلى 30 دولار
            MIN_CONFIDENCE = 50
            MAX_CONFIDENCE = 100

            confidence_clamped = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, confidence))
            confidence_ratio = (confidence_clamped - MIN_CONFIDENCE) / (MAX_CONFIDENCE - MIN_CONFIDENCE)
            
            # المبلغ الأساسي من الثقة
            base_amount = MIN_TRADE_AMOUNT + (MAX_TRADE_AMOUNT - MIN_TRADE_AMOUNT) * confidence_ratio

            # ✅ meta_trading يعدل المبلغ بناءً على المؤشرات
            rsi = analysis.get('rsi', 50)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            macd_diff = analysis.get('macd_diff', 0)
            flash_risk = analysis.get('flash_crash_protection', {}).get('risk_score', 0)
            
            # تعديلات ذكية من meta_trading
            multiplier = 1.0
            
            # RSI: قاع قوي = مبلغ أكبر
            if rsi < 30:
                multiplier *= 1.3
            elif rsi < 40:
                multiplier *= 1.1
            elif rsi > 70:
                multiplier *= 0.7
            
            # Volume: حجم عالي = فرصة أكبر
            if volume_ratio > 3:
                multiplier *= 1.2
            elif volume_ratio > 2:
                multiplier *= 1.1
            
            # MACD: إشارة قوية = مبلغ أكبر
            if macd_diff < -1:
                multiplier *= 1.1
            
            # Flash Risk: مخاطر عالية = مبلغ أقل
            if flash_risk >= 30:
                multiplier *= 0.8
            
            final_amount = base_amount * multiplier
            
            # حدود الأمان
            final_amount = max(MIN_TRADE_AMOUNT, min(MAX_TRADE_AMOUNT, final_amount))
            return round(final_amount, 2)

        except Exception as e:
            print(f"⚠️ Smart amount calculation error: {e}")
            return MIN_TRADE_AMOUNT

    # =========================================================
    # 🎓 التعلم المباشر للملك - يتعلم من كل صفقة
    # =========================================================
    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, symbol=None, position=None, extra_data=None):
        """التعلم المباشر من كل صفقة - يحفظ في الداتابيز"""
        try:
            # تحميل البيانات من الداتابيز
            data = self._load_learning_data()

            # استخراج البيانات الحقيقية من الـ position
            ai_data = position.get('ai_data', {}) if position else {}
            rsi = ai_data.get('rsi', 50)
            volume_ratio = ai_data.get('volume_ratio', ai_data.get('volume', 1.0)) # ✅ دعم المسميين لضمان جلب الحجم
            macd_diff = ai_data.get('macd_diff', 0)
            buy_confidence = position.get('buy_confidence', 50) if position else 50
            current_hour = datetime.now().hour
            hour_key = str(current_hour)
            
            current_rsi = extra_data.get('rsi', 50) if extra_data else rsi
            # جلب قيمة التفاؤل من البيانات الإضافية أو حسابها لحظياً
            optimism = extra_data.get('optimism', 0) if extra_data else 0
            if optimism == 0 and current_rsi > 75:
                optimism = (current_rsi - 75) * 0.8

            # تعلم من البيع
            if trade_quality in ['GREAT', 'GOOD', 'OK']:
                data['sell_success'] += 1
                if sell_votes and len([v for v in sell_votes.values() if v == 1]) >= 4:
                    data['peak_correct'] += 1
            elif trade_quality in ['RISKY', 'TRAP']:
                data['sell_fail'] += 1
                if sell_votes and len([v for v in sell_votes.values() if v == 1]) >= 4:
                    data['peak_wrong'] += 1

            # تعلم من الشراء
            if profit > 5.0: # لا نعتبر الشراء "ناجحاً جداً" للتعلم إلا إذا حقق قمة 5% فأكثر (Peak/Valley Catcher)
                data['buy_success'] += 1
                # فحص الكلمات المفتاحية الإيجابية في نصائح المستشارين
                pos_keywords = ['Bullish']
                pos_votes = sum(1 for v in buy_votes.values() if any(k in str(v) for k in pos_keywords))
                if pos_votes >= 3:
                    data['bottom_correct'] += 1
            elif profit < -0.5:
                data['buy_fail'] += 1
                if buy_votes and len([v for v in buy_votes.values() if v == 1]) >= 3:
                    data['bottom_wrong'] += 1

            # =========================================================
            # 🧠 الذاكرة الذكية - بيانات حقيقية من الصفقات
            # =========================================================
            if trade_quality in ['GREAT', 'GOOD', 'OK']:
                # ⏰ أفضل أوقات الشراء
                if symbol not in data['best_buy_times']:
                    data['best_buy_times'][symbol] = {}
                data['best_buy_times'][symbol][hour_key] = \
                    data['best_buy_times'][symbol].get(hour_key, 0) + 1

                # 📈 الأنماط الناجحة - بيانات حقيقية
                data['successful_patterns'].append({
                    'symbol': symbol,
                    'rsi': rsi,
                    'volume_ratio': volume_ratio,
                    'macd_diff': macd_diff,
                    'confidence': buy_confidence,
                    'profit': profit,
                    'hour': current_hour,
                    'date': datetime.now(timezone.utc).isoformat()
                })
                # نحافظ على آخر 500 نمط فقط لتجنب تضخم الذاكرة
                if len(data['successful_patterns']) > 500:
                    data['successful_patterns'] = data['successful_patterns'][-500:]

                # 💪 سجل الجرأة - بيانات حقيقية (RSI منخفض أو حجم عالي)
                if rsi < 40 or volume_ratio > 2.0:
                    data['courage_record'].append({
                        'symbol': symbol,
                        'rsi': rsi,
                        'volume_ratio': volume_ratio,
                        'confidence': buy_confidence,
                        'profit': profit,
                        'hour': current_hour,
                        'date': datetime.now().isoformat()
                    })
                    if len(data['courage_record']) > 200:
                        data['courage_record'] = data['courage_record'][-200:]

                # 🏆 معدل نجاح العملة
                if symbol not in data['symbol_win_rate']:
                    data['symbol_win_rate'][symbol] = {'wins': 0, 'total': 0}
                data['symbol_win_rate'][symbol]['wins'] += 1
                data['symbol_win_rate'][symbol]['total'] += 1

                # 🎯 معايرة الثقة: هل الثقة العالية = نجاح فعلي؟
                conf_bucket = str(int(buy_confidence // 10) * 10)  # e.g. "70", "80"
                if conf_bucket not in data['confidence_calibration']:
                    data['confidence_calibration'][conf_bucket] = {'wins': 0, 'total': 0}
                data['confidence_calibration'][conf_bucket]['wins'] += 1
                data['confidence_calibration'][conf_bucket]['total'] += 1

            # ❌ عند الخسارة - تتذكر الظروف السيئة
            if profit < -0.5 or trade_quality in ['RISKY', 'TRAP']:
                # ⏰ أسوأ أوقات الشراء
                if symbol not in data['worst_buy_times']:
                    data['worst_buy_times'][symbol] = {}
                data['worst_buy_times'][symbol][hour_key] = \
                    data['worst_buy_times'][symbol].get(hour_key, 0) + 1

                # 🏆 معدل نجاح العملة (إضافة للإجمالي بدون فوز)
                if symbol not in data['symbol_win_rate']:
                    data['symbol_win_rate'][symbol] = {'wins': 0, 'total': 0}
                data['symbol_win_rate'][symbol]['total'] += 1

                # 🎯 معايرة الثقة عند الخسارة
                conf_bucket = str(int(buy_confidence // 10) * 10)
                if conf_bucket not in data['confidence_calibration']:
                    data['confidence_calibration'][conf_bucket] = {'wins': 0, 'total': 0}
                data['confidence_calibration'][conf_bucket]['total'] += 1

            # تاريخ الأخطاء
            if trade_quality in ['RISKY', 'TRAP'] or profit < -0.5:
                data['error_history'].append({
                    'symbol': symbol,
                    'rsi': rsi,
                    'volume_ratio': volume_ratio,
                    'reason': 'trap' if trade_quality in ['TRAP'] else 'low_profit' if profit < -0.5 else 'other',
                    'date': datetime.now().isoformat()
                })
                if len(data['error_history']) > 200:
                    data['error_history'] = data['error_history'][-200:]

            # حفظ في الداتابيز
            self._save_learning_data(data)

            # === حساب الأعمدة المفقودة للذاكرة ===
            c_boost = self._get_courage_boost(symbol, rsi, volume_ratio)
            t_mod, _ = self._get_time_memory_modifier(symbol)
            p_score, _ = self._get_symbol_pattern_score(symbol, rsi, macd_diff, volume_ratio)
            w_boost, _ = self._get_symbol_win_rate_boost(symbol)
            
            # حساب PL Ratio للعملة بناءً على تاريخ التعلم
            swr = data.get('symbol_win_rate', {}).get(symbol, {'wins': 0, 'total': 1})
            plr = (swr['wins'] / max(swr['total'] - swr['wins'], 1))

            # ملخص نفسي (Greed / Fear / Neutral)
            sent = extra_data.get('sentiment', 0) if extra_data else 0
            panc = extra_data.get('panic', 0) if extra_data else 0
            psy_sum = "Greed" if sent > 2 else "Panic" if panc > 5 else "Neutral"

            # حفظ في ذاكرة الملك
            if hasattr(self.storage, 'update_symbol_memory'):
                self.storage.update_symbol_memory(
                    symbol=symbol,
                    profit=profit,
                    trade_quality=trade_quality,
                    hours_held=float((datetime.now() - datetime.fromisoformat(position['buy_time'])).total_seconds()/3600) if position else 24,
                    rsi=rsi,
                    volume_ratio=volume_ratio,
                    sentiment=sent,
                    whale_conf=extra_data.get('whale_confidence', 0) if extra_data else ai_data.get('whale_confidence', 0),
                    panic=panc,
                    optimism=float(optimism),
                    profit_loss_ratio=plr,
                    volume_trend=extra_data.get('volume_trend', 0) if extra_data else 0,
                    psychological_summary=psy_sum,
                    courage_boost=c_boost,
                    time_memory_modifier=t_mod,
                    pattern_score=p_score,
                    win_rate_boost=w_boost
                )
            
            # ✅ حفظ النمط في جدول الانماط المتعلمة
            try:
                # حفظ نمط النجاح أو الفشل
                pattern_type = 'SUCCESS' if trade_quality in ['GREAT', 'GOOD', 'OK'] else 'TRAP'
                pattern_data = {
                    'type': pattern_type,
                    'success_rate': 1.0 if trade_quality in ['GREAT', 'GOOD'] else 0.0,
                    'features': {
                        'profit': profit,
                        'trade_quality': trade_quality,
                        'sell_votes': sell_votes,
                        'buy_votes': buy_votes if buy_votes else {},
                        'symbol': symbol
                    }
                }
                self.storage.save_pattern(pattern_data)
                
                # 🔄 تحديث الكاش فورًا
                self._patterns_cache.append({
                    'id': None,
                    'pattern_type': pattern_type,
                    'data': {'features': pattern_data['features']},
                    'success_rate': pattern_data['success_rate']
                })
                
                # تنظيف الكاش (آخر 1000 نمط)
                if len(self._patterns_cache) > 1000:
                    self._patterns_cache = self._patterns_cache[-1000:]
                
                print(f"✅ Saved {pattern_type} pattern for {symbol} + updated cache")
            except Exception as e:
                print(f"⚠️ Failed to save pattern: {e}")

            total = data['buy_success'] + data['buy_fail'] + data['sell_success'] + data['sell_fail']
            if total > 0:
                success = data['buy_success'] + data['sell_success']
                accuracy = (success / total) * 100
                print(f"👑 King learned: {trade_quality} | Accuracy: {accuracy:.0f}% ({success}/{total})")

        except Exception as e:
            print(f"⚠️ King learning error: {e}")

    def _load_learning_data(self):
        """تحميل بيانات التعلم من الداتابيز"""
        default = {
            'buy_success': 0, 'buy_fail': 0,
            'sell_success': 0, 'sell_fail': 0,
            'peak_correct': 0, 'peak_wrong': 0,
            'bottom_correct': 0, 'bottom_wrong': 0,
            'best_buy_times': {},       # {symbol: {hour: success_count}}
            'worst_buy_times': {},      # {symbol: {hour: fail_count}}  ← جديد
            'best_trade_sizes': {},     # {symbol: {size_range: avg_profit}}
            'successful_patterns': [],  # list of {'symbol':, 'rsi':, 'volume_ratio':, 'macd_diff':, 'profit':, 'hour':}
            'error_history': [],        # list of {'symbol':, 'rsi':, 'reason':, 'date':}
            'courage_record': [],       # list of {'symbol':, 'rsi':, 'volume_ratio':, 'profit':, 'date':}
            'symbol_win_rate': {},      # {symbol: {wins, total}}  ← جديد
            'confidence_calibration': {}  # {bucket: {wins, total}}  ← جديد
        }
        try:
            if self.storage:
                # 🔒 جلب إعدادات البوت (التعلم) من الكاش المضغوط
                raw = self.storage.load_setting(DB_LEARNING_KEY)
                if raw:
                    # التحقق إذا كانت البيانات محملة كـ dict من الكاش أو تحتاج parse
                    if isinstance(raw, str):
                        loaded = json.loads(raw)
                    else:
                        loaded = raw
                        
                    # Backward compatibility: أضف الحقول الجديدة لو مش موجودة
                    for key, val in default.items():
                        if key not in loaded:
                            loaded[key] = val
                    
                    gc.collect() # تنظيف بعد فك الضغط والمعالجة
                    return loaded
        except:
            pass
        # Fallback: قراءة من الملف المحلي لو موجود
        try:
            local_file = 'data/king_learning.json'
            if os.path.exists(local_file):
                with open(local_file, 'r') as f:
                    file_data = json.load(f)
                    # نقل البيانات للداتابيز
                    self._save_learning_data(file_data)
                    print("✅ Migrated king_learning.json to database")
                    return file_data
        except:
            pass
        return default

    def _save_learning_data(self, data):
        """حفظ بيانات التعلم في الداتابيز"""
        try:
            if self.storage:
                self.storage.save_setting(DB_LEARNING_KEY, json.dumps(data))
        except Exception as e:
            print(f"⚠️ Error saving learning data: {e}")
    
    def get_patterns_from_cache(self):
        """💾 قراءة الأنماط من الرام بدلاً من الداتابيز"""
        return self._patterns_cache if self._patterns_cache else []

    def get_learning_stats(self):
        """إحصائيات تعلم الملك"""
        try:
            data = self._load_learning_data()
            total = data['buy_success'] + data['buy_fail'] + data['sell_success'] + data['sell_fail']
            success = data['buy_success'] + data['sell_success']

            # إحصائيات معدلات الفوز لكل عملة
            symbol_stats = {}
            for sym, wr in data.get('symbol_win_rate', {}).items():
                t = wr.get('total', 0)
                w = wr.get('wins', 0)
                if t > 0:
                    symbol_stats[sym] = {'win_rate': round(w/t*100, 1), 'total': t}

            # إحصائيات معايرة الثقة
            calib = {}
            for bucket, cc in data.get('confidence_calibration', {}).items():
                t = cc.get('total', 0)
                w = cc.get('wins', 0)
                if t >= 3:
                    calib[f"conf_{bucket}"] = {'win_rate': round(w/t*100, 1), 'total': t}

            return {
                'total': total,
                'success': success,
                'accuracy': (success / total * 100) if total > 0 else 0,
                'peak_accuracy': (data['peak_correct'] / (data['peak_correct'] + data['peak_wrong']) * 100) if (data['peak_correct'] + data['peak_wrong']) > 0 else 0,
                'bottom_accuracy': (data['bottom_correct'] / (data['bottom_correct'] + data['bottom_wrong']) * 100) if (data['bottom_correct'] + data['bottom_wrong']) > 0 else 0,
                'patterns_stored': len(data.get('successful_patterns', [])),
                'courage_records': len(data.get('courage_record', [])),
                'symbol_win_rates': symbol_stats,
                'confidence_calibration': calib
            }
        except:
            pass
        return {'total': 0, 'success': 0, 'accuracy': 0, 'peak_accuracy': 0, 'bottom_accuracy': 0}

    def _calculate_profit_spike_features(self, symbol, position, current_price):
        """🚀 حساب معلومات القفزات (للميزات فقط - ليس للقرار)"""
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'profit_jump': 0, 'time_diff': 0, 'is_spike': 0}
            
            current_profit = ((current_price - buy_price) / buy_price) * 100
            now = datetime.now(timezone.utc)
            
            # حفظ الربح الحالي
            if not hasattr(self, 'profit_history'):
                self.profit_history = {}
            
            if symbol not in self.profit_history:
                self.profit_history[symbol] = []
            
            history = self.profit_history[symbol]
            
            profit_jump = 0
            time_diff = 0
            is_spike = 0
            
            # ✅ مقارنة مع آخر دورة فقط!
            if len(history) >= 1:
                last_time, last_profit = history[-1]
                last_profit = last_profit or 0
                time_diff = (now - last_time).total_seconds()

                # إذا مر أقل من 20 ثانية (دورتين)
                if time_diff < 20:
                    profit_jump = current_profit - last_profit
                    
                    # ✅ كشف القفزات (نفس الأرقام الثابتة)
                    if (profit_jump >= 5 and current_profit >= 8) or \
                       (profit_jump >= 8 and current_profit >= 10) or \
                       (last_profit >= 10 and profit_jump <= -3):
                        is_spike = 1
            
            # حفظ القراءة الحالية
            self.profit_history[symbol].append((now, current_profit))
            
            # الاحتفاظ بآخر 5 قراءات فقط
            if len(self.profit_history[symbol]) > 5:
                self.profit_history[symbol] = self.profit_history[symbol][-5:]
            
            return {
                'profit_jump': profit_jump,
                'time_diff': time_diff,
                'is_spike': is_spike,
                'current_profit': current_profit
            }
            
        except Exception as e:
            print(f"⚠️ Profit spike calculation error: {e}")
            return {'profit_jump': 0, 'time_diff': 0, 'is_spike': 0}

    def _calculate_stop_loss_features(self, position, current_price, analysis, risk_level, whale_tracking_score, sentiment_score):
        """🛡️ حساب معلومات Stop Loss (للميزات فقط - ليس للقرار)"""
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'drop_from_peak': 0, 'threshold': 0, 'is_stop_loss': 0}
            
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            highest_price = position.get('highest_price', buy_price)
            drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
            
            # حساب العتبة الديناميكية (نفس النظام القديم)
            atr_p = analysis.get('atr_percent', 2.5)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            rsi = analysis.get('rsi', 50)
            
            base_threshold = atr_p * (1 + risk_level / 100)
            volume_modifier = (volume_ratio - 1.0) * 0.5
            base_threshold += volume_modifier
            rsi_modifier = (50 - rsi) / 100
            base_threshold += rsi_modifier
            whale_modifier = whale_tracking_score / 500
            base_threshold -= whale_modifier
            sentiment_modifier = sentiment_score / 200
            base_threshold += sentiment_modifier
            
            final_threshold = max(atr_p * 0.5, min(atr_p * 3.0, base_threshold))
            
            # كشف Stop Loss (نفس المنطق)
            is_stop_loss = 0
            if drop_from_peak >= final_threshold or profit_percent <= -(final_threshold * 1.5):
                is_stop_loss = 1
            
            return {
                'drop_from_peak': drop_from_peak,
                'threshold': final_threshold,
                'is_stop_loss': is_stop_loss,
                'profit_percent': profit_percent
            }
            
        except Exception as e:
            print(f"⚠️ Stop loss calculation error: {e}")
            return {'drop_from_peak': 0, 'threshold': 0, 'is_stop_loss': 0}

    def _update_symbol_memory(self, symbol):
        """تحديث ذاكرة الملك للعملة"""
        try:
            # جلب بيانات حديثة
            memory_data = {
                'sentiment_avg': 0,  # من sentiment
                'whale_confidence_avg': 0,  # من whale_confidence
                'profit_loss_ratio': 0,  # حساب من الصفقات
                'volume_trend': 'neutral',  # من volume
                'panic_score_avg': 0,  # من panic_greed
                'optimism_penalty_avg': 0,  # من optimism
                'psychological_summary': 'Updated by Meta'
            }

            # حفظ في قاعدة البيانات
            if hasattr(self.storage, 'save_symbol_memory'):
                self.storage.save_symbol_memory(symbol, memory_data)
        except Exception as e:
            print(f"❌ Meta Error (_update_symbol_memory) for {symbol}: {e}")
