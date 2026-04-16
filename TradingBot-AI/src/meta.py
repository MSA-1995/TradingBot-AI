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
from datetime import datetime
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
        self._load_model_data_from_db()

        print("👑 Meta (The King) is initialized and ready to rule.")

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
            if hasattr(dl_client, '_models') and 'meta_trading' in dl_client._models:
                self.meta_model = dl_client._models['meta_trading']
                if hasattr(dl_client, '_feature_names') and 'meta_trading' in dl_client._feature_names:
                    self.meta_feature_names = dl_client._feature_names['meta_trading']
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
            current_hour = datetime.now().hour
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

    def should_buy(self, symbol, analysis, models_scores=None, candles=None, preloaded_advisors=None):
        """القرار - الملك يجمع ذكاء المستشارين ويقرر بحرية كاملة"""

        analysis_data = analysis
        reasons = []

        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action': 'DISPLAY', 'reason': 'Invalid analysis data', 'confidence': 0}
        
        # =====================================================================
        # 🧠 جمع الذكاء من المستشارين الـ14 (مصادر معلومات قوية)
        # =====================================================================
        advisors_intelligence = {}
        
        try:
            # 1. Smart Money Tracker - نشاط الحيتان
            smart_money = self.advisor_manager.get('SmartMoneyTracker') if self.advisor_manager else None
            if smart_money:
                whale_score = analysis_data.get('whale_confidence', 0)
                advisors_intelligence['whale_activity'] = abs(whale_score) * 4  # 0-100
                advisors_intelligence['whale_direction'] = 'buy' if whale_score > 0 else 'sell'
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
            combined_pattern_score = (base_pattern_confidence + candle_expert_score + peak_valley_score) / 3
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
            # 8. News Analyzer - تأثير الأخبار
            news_analyzer = self.advisor_manager.get('NewsAnalyzer') if self.advisor_manager else None
            if news_analyzer:
                news_boost = news_analyzer.get_news_confidence_boost(symbol)
                advisors_intelligence['news_impact'] = news_boost  # -15 to +15
        except: pass
        
        try:
            # 9. Adaptive Intelligence - الذاكرة التاريخية
            adaptive_ai = self.advisor_manager.get('AdaptiveIntelligence') if self.advisor_manager else None
            if adaptive_ai:
                profile = adaptive_ai.get_symbol_profile(symbol)
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
        except: pass
        
        try:
            # 14. Exit Strategy - توقيت الدخول
            # (يستخدم في البيع أكثر، لكن نأخذ رأيه)
            advisors_intelligence['entry_timing'] = 60  # محايد للشراء
        except: pass
        
        # =====================================================================
        # 👑 الملك يحلل كل الذكاء المجموع
        # =====================================================================
        # Layer 1: التحليل الفني الأساسي
        rsi = analysis_data.get('rsi', 50)
        macd_diff = analysis_data.get('macd_diff', 0)
        volume_ratio = analysis_data.get('volume_ratio', 1.0)
        
        # 🔍 طباعة تشخيصية (موقفة مؤقتاً)
        # print(f"\n{'='*60}")
        # print(f"🔍 META INTELLIGENCE CHECK for {symbol}")
        # print(f"{'='*60}")
        # print(f"📊 RAW DATA:")
        # print(f"   RSI: {rsi:.1f}")
        # print(f"   MACD: {macd_diff:.2f}")
        # print(f"   Volume Ratio: {volume_ratio:.2f}x")
        # print(f"   Reversal Confidence: {analysis_data.get('reversal', {}).get('confidence', 0)}/110")
        
        technical_score = 0
        if rsi <= 35:
            technical_score += 30
        elif rsi <= 45:
            technical_score += 20
        elif rsi < 55:
            technical_score += 10
        
        if macd_diff > 1.0:
            technical_score += 20
        elif macd_diff > 0.3:
            technical_score += 12
        elif macd_diff > 0:
            technical_score += 5
        
        if volume_ratio > 2.0:
            technical_score += 25
        elif volume_ratio > 1.3:
            technical_score += 15
        elif volume_ratio > 1.0:
            technical_score += 7
        
        # Layer 2: ذكاء المستشارين (الملك يأخذهم على محمل الجد)
        whale_activity = advisors_intelligence.get('whale_activity', 0)
        trend_birth = advisors_intelligence.get('trend_birth', 0)
        volume_momentum = advisors_intelligence.get('volume_momentum', 0)
        liquidation_safety = advisors_intelligence.get('liquidation_safety', 50)
        pattern_confidence = advisors_intelligence.get('pattern_confidence', 0)
        candle_expert_score = advisors_intelligence.get('candle_expert_score', 50)  # 🆕 الجديد!
        support_strength = advisors_intelligence.get('support_strength', 0)
        sentiment_score = advisors_intelligence.get('sentiment_score', 0)
        news_impact = advisors_intelligence.get('news_impact', 0)
        historical_success = advisors_intelligence.get('historical_success', 50)
        liquidity_score = advisors_intelligence.get('liquidity_score', 50)
        trap_detection = advisors_intelligence.get('trap_detection', 50)
        risk_level = advisors_intelligence.get('risk_level', 50)
        macro_trend = advisors_intelligence.get('macro_trend', 50)
        
        # 🔍 طباعة ذكاء المستشارين (موقفة مؤقتاً)
        # print(f"\n🧠 ADVISORS INTELLIGENCE:")
        # print(f"   Whale Activity: {whale_activity:.1f}/100")
        # print(f"   Trend Birth: {trend_birth:.1f}/100")
        # print(f"   Volume Momentum: {volume_momentum:.1f}/100")
        # print(f"   Pattern Confidence: {pattern_confidence:.1f}/100")
        # print(f"   Support Strength: {support_strength:.1f}/100")
        # print(f"   Historical Success: {historical_success:.1f}/100")
        # print(f"   Trap Detection: {trap_detection:.1f}/100")
        # print(f"   Risk Level: {risk_level:.1f}/100")
        # print(f"   Macro Trend: {macro_trend:.1f}/100")
        
        # Layer 3: الذكاء الكلي (الملك يجمع كل شيء بأوزان ذكية)
        total_intelligence = (
            technical_score * 0.25 +           # 25% التحليل الفني
            whale_activity * 0.12 +            # 12% نشاط الحيتان
            trend_birth * 0.12 +               # 12% بداية الاتجاه
            volume_momentum * 0.10 +           # 10% زخم الحجم
            candle_expert_score * 0.12 +       # 12% أنماط الشموع (مرفوع) 
            support_strength * 0.08 +          # 8% قوة الدعم
            historical_success * 0.05 +        # 5% الذاكرة
            trap_detection * 0.05 +            # 5% كشف الفخاخ
            risk_level * 0.05 +                # 5% المخاطر
            (sentiment_score + 10) * 0.04 +    # 4% المشاعر
            liquidity_score * 0.03 +           # 3% السيولة
            (news_impact + 15) * 0.02 +        # 2% الأخبار
            macro_trend * 0.01                 # 1% الاتجاه الكلي
        )
        
        # 🔍 طباعة حساب الذكاء الكلي (موقفة مؤقتاً)
        # print(f"\n🧩 INTELLIGENCE CALCULATION:")
        # print(f"   Technical (25%):     {technical_score * 0.25:.1f}")
        # print(f"   Whale (12%):         {whale_activity * 0.12:.1f}")
        # print(f"   Trend (12%):         {trend_birth * 0.12:.1f}")
        # print(f"   Volume (10%):        {volume_momentum * 0.10:.1f}")
        # print(f"   Candle Expert (12%): {candle_expert_score * 0.12:.1f}")
        # print(f"   Pattern (8%):        {pattern_confidence * 0.08:.1f}")
        # print(f"   Support (8%):        {support_strength * 0.08:.1f}")
        # print(f"   History (5%):        {historical_success * 0.05:.1f}")
        # print(f"   Trap (5%):           {trap_detection * 0.05:.1f}")
        # print(f"   Risk (5%):           {risk_level * 0.05:.1f}")
        # print(f"   Others (8%):         {((sentiment_score + 10) * 0.04 + liquidity_score * 0.03 + (news_impact + 15) * 0.02 + macro_trend * 0.01):.1f}")
        # print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        # print(f"   🎯 TOTAL INTELLIGENCE: {total_intelligence:.1f}/100")
        # print(f"   🎯 MIN REQUIRED: {META_BUY_INTELLIGENCE}")
        # print(f"   🎯 RESULT: {'✅ PASS' if total_intelligence >= META_BUY_INTELLIGENCE else '❌ FAIL'}")
        # print(f"{'='*60}\n")
        
        # Layer 4: الجرأة من الذاكرة
        courage_boost = self._get_courage_boost(symbol, rsi, volume_ratio)
        time_mod, _ = self._get_time_memory_modifier(symbol)
        pattern_boost, _ = self._get_symbol_pattern_score(symbol, rsi, macd_diff, volume_ratio)
        win_boost, _ = self._get_symbol_win_rate_boost(symbol)
        
        memory_intelligence = courage_boost + time_mod + pattern_boost + win_boost
        total_intelligence += memory_intelligence
        
        # Layer 5: الحماية من المخاطر الحرجة
        flash_crash = analysis_data.get('flash_crash_protection', {})
        flash_risk = flash_crash.get('risk_score', 0)
        
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
        
        # =====================================================================
        # 👑 القرار النهائي (الملك يقرر بحرية بناءً على الذكاء المجموع)
        # =====================================================================
        
        # 🔍 طباعة تشخيصية لقرار الملك (موقفة مؤقتاً)
        # print(f"\n👑 META DECISION for {symbol}:")
        # print(f"   Total Intelligence: {total_intelligence:.1f}/100")
        # print(f"   Technical Score: {technical_score:.1f}")
        # print(f"   Whale Activity: {whale_activity:.1f}")
        # print(f"   Trend Birth: {trend_birth:.1f}")
        # print(f"   Volume Momentum: {volume_momentum:.1f}")
        # print(f"   Pattern Confidence: {pattern_confidence:.1f}")
        # print(f"   Support Strength: {support_strength:.1f}")
        # print(f"   Historical Success: {historical_success:.1f}")
        # print(f"   Memory Intelligence: {memory_intelligence:.1f}")
        # print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        # print(f"   MIN_BUY_INTELLIGENCE: {META_BUY_INTELLIGENCE}")
        # print(f"   MIN_BUY_WHALE: {META_BUY_WHALE}")
        # print(f"   MIN_BUY_TREND: {META_BUY_TREND}")
        # print(f"   MIN_BUY_CONSENSUS: {META_BUY_CONSENSUS}")
        
        king_wants_to_buy = False
        buy_reason = ""

        # السيناريو 0: صائد القمم والقيعان - قاع حقيقي مكتشف
        peak_valley_score = advisors_intelligence.get('peak_valley_score', 50)
        if peak_valley_score >= 80 and total_intelligence >= 45:  # قاع قوي مكتشف
            king_wants_to_buy = True
            buy_reason = f"🎯 قاع حقيقي مكتشف: {peak_valley_score:.0f}/100 - صائد القمم والقيعان"

        # السيناريو 1: ذكاء عالي جداً (ثقة قوية من المستشارين)
        elif total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"ثقة عالية جداً: {total_intelligence:.0f}/100"
        
        # السيناريو 2: حيتان تشتري بقوة + ذكاء جيد
        elif whale_activity > META_BUY_WHALE and total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"حيتان تشتري + ثقة: {total_intelligence:.0f}/100"
        
        # السيناريو 3: بداية اتجاه قوي + ذكاء جيد
        elif trend_birth > META_BUY_TREND and total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"بداية موجة قوية: {total_intelligence:.0f}/100"
        
        # السيناريو 4: انفجار حجم متوقع + ذكاء جيد
        elif volume_momentum > META_BUY_VOLUME and total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"انفجار حجم قادم: {total_intelligence:.0f}/100"
        
        # السيناريو 5: نمط شموع قوي جداً (candle_expert يكتشف Hammer أو Engulfing)
        elif candle_expert_score >= META_BUY_CANDLE and total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"🕯️ نمط شموع قوي: {total_intelligence:.0f}/100"
        
        # السيناريو 6: نمط انعكاس قوي + دعم قوي + ذكاء جيد
        elif candle_expert_score >= META_BUY_PATTERN and support_strength >= META_BUY_SUPPORT and total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"نمط شموع قوي + دعم: {total_intelligence:.0f}/100"
        
        # السيناريو 7: ذاكرة قوية (نجح هنا قبل) + ذكاء جيد
        elif historical_success > META_BUY_HISTORY and total_intelligence >= META_BUY_INTELLIGENCE:
            king_wants_to_buy = True
            buy_reason = f"ذاكرة قوية: {total_intelligence:.0f}/100"
        
        # السيناريو 7: ذكاء متوسط لكن عدة مستشارين يؤكدون
        elif total_intelligence >= META_BUY_CONSENSUS:
            # فحص: كم مستشار يعطي إشارة قوية؟
            strong_signals = 0
            if whale_activity > META_BUY_WHALE: strong_signals += 1
            if trend_birth > META_BUY_TREND: strong_signals += 1
            if volume_momentum > META_BUY_VOLUME: strong_signals += 1
            if candle_expert_score > META_BUY_CANDLE: strong_signals += 1  # 🕯️ candle_expert
            if support_strength > META_BUY_SUPPORT: strong_signals += 1
            if historical_success > META_BUY_HISTORY: strong_signals += 1
            
            if strong_signals >= 3:
                king_wants_to_buy = True
                buy_reason = f"{strong_signals} مستشارين يؤكدون: {total_intelligence:.0f}/100"
        
        # 🔍 طباعة القرار النهائي (موقفة مؤقتاً)
        # print(f"   🎯 DECISION: {'✅ BUY' if king_wants_to_buy else '❌ NO BUY'}")
        # if king_wants_to_buy:
        #     print(f"   🎯 REASON: {buy_reason}")
        # else:
        #     print(f"   🎯 REASON: Intelligence too low ({total_intelligence:.0f} < {META_BUY_INTELLIGENCE})")
        # print(f"{'='*60}\n")
        
        if king_wants_to_buy:
            action = "BUY"
            reason = f"BUY ✅ | {buy_reason}"
            
            try:
                amount = self._calculate_smart_amount(symbol, total_intelligence, analysis_data)
            except:
                amount = MIN_TRADE_AMOUNT
            
            return {
                'action': action,
                'reason': reason,
                'confidence': min(total_intelligence, 99),
                'amount': amount,
                'advisors_intelligence': advisors_intelligence,
                'total_intelligence': total_intelligence
            }
        else:
            return {
                'action': 'DISPLAY',
                'reason': f"Intel: {total_intelligence:.0f}/100 - Waiting for better entry",
                'confidence': min(total_intelligence, 99),
                'advisors_intelligence': advisors_intelligence
            }

    def should_sell(self, symbol, position, current_price, analysis, mtf, candles=None, preloaded_advisors=None):
        """🔴 قرار البيع مع استشارة المستشارين عن القمة"""
        from config import MIN_SELL_CONFIDENCE
        
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)

        # فحص الحد الأدنى للربح قبل البيع
        from config import MIN_SELL_PROFIT
        if profit_percent < MIN_SELL_PROFIT:
            return {
                'action': 'HOLD',
                'reason': f'Minimum profit not reached: {profit_percent:.2f}% < {MIN_SELL_PROFIT}%',
                'profit': profit_percent
            }

        # نقاط القمة (تبدأ من 0)
        peak_confidence = 0
        peak_reasons = []

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
        
        # --- 📊 2. Volume Forecast - كشف انهيار الحجم ---
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
        except Exception as e:
            print(f"⚠️ Volume forecast error: {e}")
        
        # --- 🧬 3. Adaptive Intelligence - تعديل حد البيع ---
        try:
            adaptive_ai = self.advisor_manager.get('AdaptiveIntelligence') if self.advisor_manager else None
            if adaptive_ai:
                profile = adaptive_ai.get_symbol_profile(symbol)
                
                # إذا العملة تاريخياً تنهار بسرعة، نبيع أسرع
                if profile.get('avg_profit', 0) < 2.0 and profit_percent > 5.0:
                    peak_confidence += 15
                    peak_reasons.append(f"Adaptive: Quick Exit for {symbol} (+15)")
                    print(f"🧬 Adaptive: {symbol} tends to crash fast, exit now!")
        except Exception as e:
            print(f"⚠️ Adaptive AI error: {e}")

        # =========================================================
        # 🗣️ 4. استشارة المستشارين الـ 12 عن القمة (بما فيهم candle_expert)
        # =========================================================
        sell_vote_count = 0
        total_advisors = 12  # ✅ زدنا من 10 إلى 12 (أضفنا candle_expert)
        sell_votes = {}
        
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if dl_client:
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

                total_advisors = 12  # ✅ 12 مستشار (بما فيهم candle_expert)
        except Exception as e:
            print(f"⚠️ Sell voting error [{symbol}]: {e}")
            sell_vote_count = 0
            total_advisors = 12

        # =========================================================
        # 👑 5. الملك يقرر بناءً على القمة + المستشارين
        # =========================================================
        peak_analysis = analysis.get('peak', {})
        peak_score = peak_analysis.get('confidence', 0) + peak_confidence  # إضافة نقاط المستشارين الجدد
        
        # 🚨 بيع فوري إذا:
        # 1. المستشارون يؤكدون القمة (6+ أصوات)
        # 2. نقاط القمة عالية (85+)
        # 3. RSI مرتفع جداً (70+) مع MACD هابط
        
        king_wants_to_sell = False
        sell_reason = ""
        
        # الشرط 1: المستشارون يؤكدون القمة (50%+ أصوات) + ربح معقول
        if sell_vote_count >= 6 and profit_percent > 5.0:  # ✅ 6 من 12 = 50%
            king_wants_to_sell = True
            sell_reason = f"Advisors Confirm Peak: {sell_vote_count}/{total_advisors} votes (+{profit_percent:.1f}%)"
        
        # الشرط 2: نقاط القمة عالية جداً + ربح معقول
        elif peak_score >= MIN_SELL_CONFIDENCE and profit_percent > 3.0:  # ✅ رفعنا من 0.5% إلى 3%
            king_wants_to_sell = True
            sell_reason = f"Strong Peak Signal: {peak_score}/110 points (+{profit_percent:.1f}%)"
        
        # الشرط 3: RSI مرتفع + MACD هابط + مستشارين يحذرون + ربح معقول
        elif rsi > 75 and macd_diff < -1 and sell_vote_count >= 5 and profit_percent > 3.0:  # ✅ رفعنا RSI من 70 إلى 75
            king_wants_to_sell = True
            sell_reason = f"Technical Peak: RSI {rsi:.0f} + MACD {macd_diff:.1f} + {sell_vote_count} votes (+{profit_percent:.1f}%)"
        
        # الشرط 4: ربح عالي (50%+) مع إشارات قمة متوسطة
        elif profit_percent >= 50 and (peak_score >= 70 or sell_vote_count >= 5):
            king_wants_to_sell = True
            sell_reason = f"Wave Target Hit: {profit_percent:.1f}% (Peak: {peak_score}, Votes: {sell_vote_count})"
        
        # الشرط 5: ربح متوسط (30%+) مع إشارات قمة قوية جداً
        elif profit_percent >= 30 and peak_score >= 95:
            king_wants_to_sell = True
            sell_reason = f"Strong Reversal at {profit_percent:.1f}% (Peak: {peak_score})"
        
        # الشرط 6: المستشارين الجدد يكتشفون إنهاك + انهيار حجم + ربح معقول
        elif peak_confidence >= 40 and profit_percent > 5.0:  # ✅ رفعنا من 3% إلى 5%
            king_wants_to_sell = True
            sell_reason = f"New Advisors Alert: {', '.join(peak_reasons)} (+{profit_percent:.1f}%)"
        
        # =========================================================
        # 👑 6. القرار النهائي
        # =========================================================
        if king_wants_to_sell:
            optimism_penalty = round((profit_percent - 50) * 0.3, 2) if profit_percent > 50 else 0
            sell_vote_percentage = (sell_vote_count / total_advisors * 100) if total_advisors > 0 else 0
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
        # 🛡️ 7. Wave Protection (الحماية من الهبوط الحاد)
        # =========================================================
        highest_price = position.get('highest_price', buy_price)
        drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
        
        # تخفيض Wave Protection من 11.1% إلى 3-7%
        atr_p = analysis.get('atr_percent', 2.5) 
        trailing_threshold = max(3.0, atr_p * 1.0)  # حد أدنى 3% بدلاً من 11.1%

        if drop_from_peak >= trailing_threshold:
            return {
                'action': 'SELL',
                'reason': f'Wave Protection: -{drop_from_peak:.1f}% from peak',
                'profit': profit_percent,
                'optimism_penalty': 0,
                'sell_votes': sell_votes,
                'peak_score': peak_score
            }

        # =========================================================
        # ✅ 8. HOLD - مستمر في ركوب الموجة
        # =========================================================
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
            memory = self.storage.get_symbol_memory(symbol)
            if not memory: return 0
            
            # إذا كانت آخر بصمة حوت في الذاكرة مرتبطة بربح تاريخي
            last_whale_conf = memory.get('whale_conf', 0)
            plr = memory.get('profit_loss_ratio', 1.0)

            if last_whale_conf > 10 and plr > 1.2:
                return 15  # الحيتان في هذه العملة يشترون للصعود
            elif last_whale_conf > 10 and plr < 0.8:
                return -25 # الحيتان في هذه العملة يستخدمون الحجم للتصريف (Fake Wall)
        except Exception:
            pass
        return 0

    def _calculate_smart_amount(self, symbol, confidence, analysis):
        """حساب المبلغ الذكي حسب الثقة - من الأدنى للأعلى"""
        try:
            # حساب المبلغ بناءً على الثقة: من 12 دولار (ثقة 30) إلى 35 دولار (ثقة 100)
            confidence_ratio = max(0.3, min(1.0, confidence / 100.0))  # من 30% إلى 100%
            final_amount = MIN_TRADE_AMOUNT + (MAX_TRADE_AMOUNT - MIN_TRADE_AMOUNT) * confidence_ratio

            # تعديل بسيط حسب المخاطر
            flash_crash = analysis.get('flash_crash_protection', {})
            flash_risk = flash_crash.get('risk_score', 0)
            if flash_risk >= 30:
                final_amount *= 0.8  # خفض قليل عند المخاطر العالية

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
                    'date': datetime.now().isoformat()
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
                print(f"✅ Saved {pattern_type} pattern for {symbol}")
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
                raw = self.storage.load_setting(DB_LEARNING_KEY)
                if raw:
                    loaded = json.loads(raw)
                    # Backward compatibility: أضف الحقول الجديدة لو مش موجودة
                    for key, val in default.items():
                        if key not in loaded:
                            loaded[key] = val
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
