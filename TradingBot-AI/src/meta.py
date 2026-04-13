"""
Meta (The King) - The Ultimate Decision Maker
"""
import pandas as pd
from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, MIN_CONFIDENCE, PEAK_DROP_THRESHOLD, BOTTOM_BOUNCE_THRESHOLD, VOLUME_SPIKE_FACTOR
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
        self.meta_learner_data = None
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

            model_data = dl_client.get_model_data('meta_trading')

            if model_data:
                self.meta_learner_data = model_data
            else:
                print("⚠️ Meta: Meta-Learner model blueprint not found in DB. Buy decisions will be disabled.")
                self.meta_learner_data = None
        except Exception as e:
            print(f"❌ Meta: Error loading Meta-Learner blueprint from DB: {e}")
            self.meta_learner_data = None

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

            if len(similar_wins) >= 1:
                avg_profit = sum(r['profit'] for r in similar_wins) / len(similar_wins)
                boost = min(avg_profit * 2.5, 18)  # max +18 نقطة
                print(f"💪 Courage Boost [{symbol}]: +{boost:.1f} (based on {len(similar_wins)} similar wins, avg {avg_profit:.1f}%)")
                return round(boost, 1)

            # حتى عملتين ناجحتين تعطي boost خفيف
            if len(similar_wins) == 2:
                avg_profit = sum(r['profit'] for r in similar_wins) / 2
                boost = min(avg_profit * 1.2, 8)
                print(f"💪 Soft Courage [{symbol}]: +{boost:.1f} (2 similar wins)")
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
        """القرار - كشف القاع بالشموع + مؤشرات + تصويت المستشارين"""

        analysis_data = analysis
        temp_conf = 20
        action = "DISPLAY"
        reasons = []

        # --- بداية الكود الحساس ---
        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action': 'DISPLAY', 'reason': 'Invalid analysis data', 'confidence': 0}
        
        # --- 1. Market Mood ---
        mood_details = self._get_market_mood(analysis_data)
        market_mood = mood_details['mood']

        # --- 🎯 1.2 Macro Filter (مرشح الاتجاه الماكرو) ---
        macro_advisor = self.advisor_manager.get('MacroTrendAdvisor')
        is_macro_bullish = macro_advisor.can_aim_high()
        if not is_macro_bullish and market_mood != "Bullish":
            reasons.append("Waiting for Macro Bullish Alignment")
            temp_conf -= 30 # عقوبة قوية لو السوق العام هابط

        # --- 🎯 1.5 Market Regime Detection - حالة السوق ---
        market_regime = analysis_data.get('market_regime', {})
        regime = market_regime.get('regime', 'UNKNOWN')
        
        # في ترند هابط قوي - لا تشتري بدون تأكيد اضافي
        if regime == 'STRONG_DOWNTREND':
            temp_conf -= 15
            reasons.append("Strong Downtrend (-15)")
        
        # في تقلبات عالية - خفض الحجم
        regime_position_multiplier = market_regime.get('trading_advice', {}).get('position_size', 1.0)
        
        # --- 🚨 1.6 Flash Crash Protection - حماية السقوط المفاجئ ---
        flash_crash = analysis_data.get('flash_crash_protection', {})
        flash_risk_score = flash_crash.get('risk_score', 0)
        
        # خطر حرج - لا تتاجر
        if flash_risk_score >= 70:
            print(f"🚫 META BLOCK [{symbol}]: Flash Crash CRITICAL ({flash_risk_score}%)")
            return {
                'action': 'DISPLAY',
                'reason': f'🚨 Flash Crash Risk ({flash_risk_score}%) - STOP',
                'confidence': 0,
                'flash_risk': flash_risk_score
            }
        
        # خطر عالي - فقط البيع (متوسط: رفعنا من 50 إلى 60)
        if flash_risk_score >= 60:
            print(f"🚫 META BLOCK [{symbol}]: Flash Crash HIGH ({flash_risk_score}%)")
            return {
                'action': 'DISPLAY',
                'reason': f'⚠️ High Risk ({flash_risk_score}%) - No Buy',
                'confidence': 0,
                'flash_risk': flash_risk_score
            }

        # --- ⏰ 1.7 Time Analysis - تحليل الوقت ---
        time_analysis = analysis_data.get('time_analysis', {})
        time_recommendation = time_analysis.get('trading_recommendation', {})
        time_multiplier = time_recommendation.get('size_multiplier', 1.0)
        time_can_trade = time_recommendation.get('can_trade', True)
        
        # وقت سيء - لا تتاجر
        if not time_can_trade:
            print(f"🚫 META BLOCK [{symbol}]: Bad Time ({time_recommendation.get('reason', '')})")
            return {
                'action': 'DISPLAY',
                'reason': f'⏰ Bad Time: {time_recommendation.get("reason", "")}',
                'confidence': 0,
                'time_analysis': time_analysis
            }

        # --- 2. Technical Indicators ---
        rsi = analysis_data.get('rsi', 50)
        macd_diff = analysis_data.get('macd_diff', 0)
        volume_ratio = analysis_data.get('volume_ratio', 1.0)
        ema_crossover = analysis_data.get('ema_crossover', 0)

        # 🚨 استراتيجية Wave Rider: نمنع الشراء إذا RSI > 60 
        # نحن نبحث عن "قاع دورة" حقيقي وليس مجرد اختراق مؤقت
        if rsi > 60:
            return {
                'action': 'DISPLAY',
                'reason': f'⏳ Cycle Entry Block: RSI too high for Wave Catch ({rsi:.0f})',
                'confidence': 0
            }

        if rsi <= 35:
            temp_conf += 25
            reasons.append(f"RSI Low ({rsi:.0f})")
        elif 35 < rsi <= 45:          # ✅ متوسط: أضفنا نطاق 35-45 منفصل
            temp_conf += 20
            reasons.append(f"RSI Oversold ({rsi:.0f})")
        elif 45 < rsi < 55:
            temp_conf += 12
            reasons.append(f"RSI OK ({rsi:.0f})")
        elif 55 <= rsi <= 65:
            temp_conf += 5             # ✅ متوسط: نطاق 55-65 يضيف نقاط خفيفة
            reasons.append(f"RSI Neutral ({rsi:.0f})")
        # RSI 65-85: لا يضيف ولا يمنع

        # MACD: متوسط - نطاقات متدرجة
        if macd_diff > 1.0:
            temp_conf += 18
            reasons.append("MACD Strong Bullish")
        elif macd_diff > 0.3:         # ✅ خففنا من 0.5 إلى 0.3
            temp_conf += 12
            reasons.append("MACD Bullish")
        elif macd_diff > 0:
            temp_conf += 5            # ✅ حتى MACD موجب بسيط يضيف نقاط
            reasons.append("MACD Positive")

        if volume_ratio > 2.0:
            temp_conf += 22
            reasons.append(f"Vol Very High ({volume_ratio:.1f}x)")
        elif volume_ratio > 1.3:      # ✅ خففنا من 1.5 إلى 1.3
            temp_conf += 15
            reasons.append(f"Vol Up ({volume_ratio:.1f}x)")
        elif volume_ratio > 1.0:      # ✅ حتى حجم طبيعي يضيف نقاط خفيفة
            temp_conf += 7
            reasons.append(f"Vol Normal ({volume_ratio:.1f}x)")

        if ema_crossover > 0:
            temp_conf += 15
            reasons.append("EMA Cross")

        # --- 3. كشف القاع بالشموع (نظام الثقة الجديد) ---
        reversal = analysis_data.get('reversal', {})
        reversal_confidence = reversal.get('confidence', 0)
        reversal_reasons = reversal.get('reasons', [])

        if reversal_confidence > 0:
            temp_conf += reversal_confidence
            reasons.extend(reversal_reasons)

        # --- 📰 4. تعديل الثقة بالأخبار (مُعدِّل فقط، لا يحكم) ---
        news_boost, news_summary = self._get_news_confidence_modifier(symbol)
        if news_boost != 0:
            temp_conf += news_boost
            direction = f"+{news_boost}" if news_boost > 0 else str(news_boost)
            reasons.append(f"News({direction})")

        # --- 📊 5. كشف الذعر/الجشع النفسي (أقل صرامة) ---
        panic_greed = analysis.get('panic_greed', {})
        panic_score = panic_greed.get('panic_score', 0)
        greed_score = panic_greed.get('greed_score', 0)

        if panic_score > 10:  # أقل صرامة (تأثير خفيف)
            temp_conf -= panic_score * 0.5  # تقليل الثقة قليلاً عند الذعر
        if greed_score > 10:
            temp_conf += greed_score * 0.3  # زيادة الثقة قليلاً عند الجشع

        # --- 📊 6. فيبوناتشي (مستويات الدعم/المقاومة) ---
        fib_score = 0
        fib_level = None
        try:
            # 🚨 لا تستخدم Fibonacci إذا RSI عالي (>70)
            if rsi <= 70:
                fib_analyzer = self.advisor_manager.get('FibonacciAnalyzer') if self.advisor_manager else None
                if fib_analyzer:
                    is_at_support, support_boost = fib_analyzer.is_at_support(
                        current_price=analysis_data.get('close', 0),
                        analysis=analysis_data,
                        volume_ratio=volume_ratio,
                        symbol=symbol
                    )
                    if is_at_support:
                        fib_score = support_boost
                        temp_conf += support_boost
                        support_info = fib_analyzer.get_support_level(
                            analysis_data.get('close', 0), 
                            analysis_data
                        )
                        if support_info:
                            fib_level = support_info['level']
                            reasons.append(f"Fib {fib_level}% (+{support_boost})")
        except Exception as e:
            print(f"⚠️ Fibonacci error: {e}")

        # =========================================================
        # 🧠 الذاكرة الذكية — تضيف ثقة بدون تعديل نسب التصويت
        # =========================================================

        # 💪 1. الجرأة الديناميكية
        courage_boost = self._get_courage_boost(symbol, rsi, volume_ratio)
        if courage_boost > 0:
            temp_conf += courage_boost
            reasons.append(f"CourageBoost(+{courage_boost:.0f})")

        # ⏰ 2. ذاكرة الوقت
        time_mod, time_label = self._get_time_memory_modifier(symbol)
        if time_mod != 0:
            temp_conf += time_mod
            reasons.append(time_label)

        # 🔁 3. ذاكرة الأنماط
        pattern_boost, pattern_label = self._get_symbol_pattern_score(symbol, rsi, macd_diff, volume_ratio)
        if pattern_boost > 0:
            temp_conf += pattern_boost
            reasons.append(pattern_label)

        # 🏆 4. معدل نجاح العملة
        win_boost, win_label = self._get_symbol_win_rate_boost(symbol)
        if win_boost != 0:
            temp_conf += win_boost
            reasons.append(win_label)

        # =========================================================
        temp_conf = min(max(temp_conf, 0), 99)  # نضمن النطاق 0-99

        # --- نهاية الكود الحساس ---

        # --- 5. تصويت المستشارين ---
        buy_vote_count = 0
        total_advisors = 0
        vote_breakdown = {}
        
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            # ✅ تم اعادة تشغيل نظام تصويت المستشارين بعد اصلاح النماذج
            # بناء candle_analysis من تحليل القاع والقمة
            reversal = analysis_data.get('reversal', {})
            peak = analysis_data.get('peak', {})
            candle_analysis = {
                'is_reversal': reversal.get('candle_signal', False),
                'is_bottom':   reversal.get('candle_signal', False),
                'is_peak':     peak.get('candle_signal', False),
                'is_rejection': peak.get('candle_signal', False),
                'reversal_confidence': reversal.get('confidence', 0),
                'peak_confidence':     peak.get('confidence', 0),
            }

            # جلب النصائح من كل مستشار
            market_sentiment = analysis_data.get('market_sentiment', None)
            advisors_advice = dl_client.get_advice(
                rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                price_momentum=analysis_data.get('price_momentum', 0),
                confidence=temp_conf,
                liquidity_metrics=analysis_data.get('liquidity_metrics'),
                market_sentiment=market_sentiment,
                candle_analysis=candle_analysis
            )

            # ✅ النظام المحدث: 10 مستشارين يقدمون النصائح (الملك ميتا مستبعد من العداد)
            total_advisors = 10 
            # نعتبر النصيحة فعالة إذا كانت تحتوي على بيانات وليست فارغة
            active_advices = sum(1 for k, adv in advisors_advice.items() if k != 'meta_trading' and adv and str(adv) != "N/A")
            
            buy_vote_count = active_advices # نستخدم المتغير القديم لتجنب كسر الكود في أماكن أخرى
            vote_breakdown = advisors_advice  # الآن advice

            # إزالة التصويت الثابت، ميتا يقرر مباشرة بناءً على النصائح
        except Exception as e:
            print(f"⚠️ Buy voting error [{symbol}]: {e}")

        # 🔄 Fallback: إذا فشل التصويت، الملك يقرر بناءً على الثقة وحده
        if total_advisors == 0:
            buy_vote_count = 0
            total_advisors = 10
            vote_breakdown = {'king_fallback': 0}

        # =========================================================
        # 👑 6. الملك يقرر أولاً (Independent Decision)
        # =========================================================
        # نقاط الشموع من تحليل القاع
        candle_score = reversal.get('confidence', 0)
        
        # ✅ قرار الملك: يعتمد على إشارات القاع الحقيقية فقط
        king_wants_to_buy = False

        # حارس الماكرو: لا نشتري للموجة الطويلة إلا إذا كان الاتجاه العام (اليومي) صاعداً أو إشارة قوية جداً
        if not is_macro_bullish and candle_score < 90:
            return {
                'action': 'DISPLAY',
                'reason': f'⏳ Macro Bearish Block | King:{temp_conf}/75',
                'confidence': temp_conf
            }

        # الشرط 1: إشارة شمعية انعكاسية واضحة من القاع (الأقوى)
        if reversal.get('candle_signal', False):
            king_wants_to_buy = True
            king_reason = f"King: Reversal Signal ({candle_score}/110)"

        # الشرط 2: نقاط القاع كافية (شموع + حجم + تريند + دعم)
        elif candle_score >= MIN_CONFIDENCE:
            king_wants_to_buy = True
            king_reason = f"King: Bottom Score ({candle_score}/110)"

        # الشرط 3: انفجار حجم مع بداية ارتداد (بدون أرقام RSI ثابتة)
        elif volume_ratio >= 2.0 and reversal.get('is_reversing', False):
            king_wants_to_buy = True
            king_reason = f"King: Vol Explosion + Reversal ({volume_ratio:.1f}x)"
        
        # =========================================================
        # 🗳️ 7. التصويت الفوري بعد قرار الملك
        # =========================================================
        if king_wants_to_buy:
            # ✅ القرار للملك فقط، النصائح للعرض فقط
            action = "BUY"
            market_emoji = "🟢" if market_mood == "Bullish" else "🔴" if market_mood == "Bearish" else "⚪"
            reason = f"BUY ✅ | King:{temp_conf} | Advices:{buy_vote_count}/{total_advisors} | {market_emoji} {market_mood}"
        else:
            market_emoji = "🟢" if market_mood == "Bullish" else "🔴" if market_mood == "Bearish" else "⚪"
            reason = f"King:{temp_conf}/{MIN_CONFIDENCE} | Advices:{buy_vote_count}/{total_advisors} | {market_emoji} {market_mood}"

        decision = {
            'action': action,
            'reason': reason,
            'confidence': temp_conf,
            'news_summary': news_summary,
            'buy_vote_count': buy_vote_count,
            'total_consultants': total_advisors,
            'buy_vote_percentage': int((buy_vote_count / total_advisors * 100)) if total_advisors > 0 else 0,
            'buy_votes': vote_breakdown,  # للأرشفة والتعلم
            'fib_score': fib_score,  # فيبوناتشي score
            'fib_level': fib_level,   # فيبوناتشي مستوى
            'market_regime': regime,  # حالة السوق
            'market_regime_multiplier': regime_position_multiplier,  # مضاعف الحجم
            'flash_crash_risk': flash_risk_score  # خطر السقوط المفاجئ
        }

        if action == 'BUY':
            try:
                amount = self._calculate_smart_amount(symbol, temp_conf, analysis_data)
                decision['amount'] = amount
            except Exception as e:
                print(f"⚠️ Error calculating smart amount: {e}")
                decision['action'] = 'DISPLAY'
                decision['reason'] = 'Amount calc failed'
                decision['confidence'] = 40

        return decision

    def should_sell(self, symbol, position, current_price, analysis, mtf, candles=None, preloaded_advisors=None):
        """القرار الاستراتيجي: صيد الموجة الكبرى (50%-80%) - Wave Rider Strategy"""
        from config import MIN_SELL_CONFIDENCE
        
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        # --- 🌊 1. نظام الوقف الزاحف الواسع (Wide Trailing Stop) ---
        highest_price = position.get('highest_price', buy_price)
        drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
        
        # منطق صيد الموجات: لا خروج مبكر نهائياً
        trailing_threshold = 100.0 
        if profit_percent > 50:
            trailing_threshold = 15.0  # حماية أرباح جبارة (تسمح بتصحيح 15% للوصول لـ 80%)
        elif profit_percent > 20:
            trailing_threshold = 12.0  # حماية ربح ضخم إذا بدأ الانهيار
        elif profit_percent < -10:
            trailing_threshold = 10.0  # وقف خسارة "نفس طويل" للعملات القيادية

        # حساب التفاؤل للأرشفة (إذا كان RSI عالٍ وقت كسر الوقف الزاحف)
        optimism_penalty = round((analysis.get('rsi', 50) - 75) * 0.8, 2) if analysis.get('rsi', 50) > 75 else 0

        if drop_from_peak >= trailing_threshold:
            return {
                'action': 'SELL',
                'reason': f'🌊 Wave Rider Exit: Trend Broken (-{drop_from_peak:.1f}% from peak)',
                'profit': profit_percent,
                'optimism_penalty': optimism_penalty
            }

        # --- 🎯 2. صائد القمم الدورية (Cycle Peak Detection) ---
        peak_analysis = analysis.get('peak', {})
        peak_score = peak_analysis.get('confidence', 0)
        
        if peak_score >= 95 and profit_percent >= 50:
            return {
                'action': 'SELL',
                'reason': f'🏆 Cycle Peak Reached! Profit: {profit_percent:.1f}%',
                'profit': profit_percent,
                'optimism_penalty': round((profit_percent - 40) * 0.5, 2)
            }

        return {
            'action': 'HOLD', 
            'reason': f'🌊 Wave Rider | Profit: {profit_percent:+.1f}% | Peak: {peak_score}/110', 
            'profit': profit_percent
        }

    def _get_market_mood(self, analysis):
        """Analyzes BTC, ETH, BNB changes to determine the overall market mood and required consensus."""
        btc_change = analysis.get('btc_change_1h', 0) if analysis else 0
        eth_change = analysis.get('eth_change_1h', 0) if analysis else 0
        bnb_change = analysis.get('bnb_change_1h', 0) if analysis else 0

        up_count = 0
        down_count = 0
        threshold = 0.5

        if btc_change > threshold: up_count += 1
        elif btc_change < -threshold: down_count += 1

        if eth_change > threshold: up_count += 1
        elif eth_change < -threshold: down_count += 1

        if bnb_change > threshold: up_count += 1
        elif bnb_change < -threshold: down_count += 1

        mood_details = {}
        if up_count >= 2:
            mood_details['mood'] = "Bullish"
        elif down_count >= 2:
            mood_details['mood'] = "Bearish"
        else:
            mood_details['mood'] = "Neutral"
        
        return mood_details

    def _calculate_smart_amount(self, symbol, confidence, analysis):
        """حساب المبلغ الذكي بالتصويت من المستشارين + Risk Manager"""
        try:
            # القاعدة الأساسية لاستثمار الموجات: توزيع الـ 3000$ على 5 صفقات
            base_amount = 500.0 
            confidence_factor = (confidence - 75) / 25.0  # الحساب يبدأ من حد الثقة الجديد 75
            final_amount = base_amount + (confidence_factor * 100.0)
            
            # 🎯 Market Regime Multiplier - مضاعف حالة السوق
            market_regime = analysis.get('market_regime', {})
            regime_multiplier = market_regime.get('trading_advice', {}).get('position_size', 1.0)
            final_amount *= regime_multiplier
            
            # 🚨 Flash Crash Protection - مضاعف حماية السقوط
            flash_crash = analysis.get('flash_crash_protection', {})
            flash_risk = flash_crash.get('risk_score', 0)
            if flash_risk >= 30:
                final_amount *= 0.5
            
            # ⏰ Time Multiplier - مضاعف الوقت
            time_analysis = analysis.get('time_analysis', {})
            time_multiplier = time_analysis.get('trading_recommendation', {}).get('size_multiplier', 1.0)
            final_amount *= time_multiplier
            
            # 🚨 حدود الأمان النهائية المتوافقة مع Config
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
            volume_ratio = ai_data.get('volume', 1.0) # ✅ توحيد المسمى مع سجلات الشراء الحقيقية
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
            if profit > 5.0: # لا نعتبر الشراء "ناجحاً جداً" للتعلم إلا إذا حقق موجة 5% فأكثر (Wave Rider)
                data['buy_success'] += 1
                if buy_votes and len([v for v in buy_votes.values() if v == 1]) >= 3:
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
                    whale_conf=extra_data.get('whale_conf', 0) if extra_data else 0,
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
            pass
