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
DB_BLACKLIST_KEY = 'king_blacklist'

class Meta:
    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager = advisor_manager
        self.storage = storage
        self.meta_learner_data = None
        self._load_model_data_from_db()
        
        # 🚫 القائمة السوداء - Cache ذكي (يُحدّث عند التشغيل وكل ساعة)
        self._blacklist_cache = {}
        self._blacklist_cache_time = None
        self._blacklist_cache_ttl = 3600  # ساعة واحدة
        self._load_blacklist()  # تحميل عند بداية التشغيل
        
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

            model_data = dl_client.get_model_data('meta_learner')

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

    def should_buy(self, symbol, analysis, models_scores, candles=None):
        """القرار - كشف القاع بالشموع + مؤشرات + تصويت المستشارين"""

        analysis_data = analysis
        temp_conf = 20
        action = "DISPLAY"
        reasons = []

        # --- بداية الكود الحساس ---
        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action': 'DISPLAY', 'reason': 'Invalid analysis data', 'confidence': 0}
        
        # 🚫 فحص القائمة السوداء - منع شراء العملات الفخ المتكررة
        if self._is_blacklisted(symbol):
            return {
                'action': 'DISPLAY',
                'reason': f'🚫 Blacklisted (Repeated Trap)',
                'confidence': 0
            }

        # --- 1. Market Mood ---
        mood_details = self._get_market_mood(analysis_data)
        market_mood = mood_details['mood']

        # --- 🎯 1.5 Market Regime Detection - حالة السوق ---
        market_regime = analysis_data.get('market_regime', {})
        regime = market_regime.get('regime', 'UNKNOWN')
        
        # في ترند هابط قوي - لا تشتري
        if regime == 'STRONG_DOWNTREND':
            return {
                'action': 'DISPLAY',
                'reason': f'🚫 Strong Downtrend - No Buy',
                'confidence': 0,
                'market_regime': regime
            }
        
        # في تقلبات عالية - خفض الحجم
        regime_position_multiplier = market_regime.get('trading_advice', {}).get('position_size', 1.0)
        
        # --- 🚨 1.6 Flash Crash Protection - حماية السقوط المفاجئ ---
        flash_crash = analysis_data.get('flash_crash_protection', {})
        flash_risk_score = flash_crash.get('risk_score', 0)
        
        # خطر حرج - لا تتاجر
        if flash_risk_score >= 70:
            return {
                'action': 'DISPLAY',
                'reason': f'🚨 Flash Crash Risk ({flash_risk_score}%) - STOP',
                'confidence': 0,
                'flash_risk': flash_risk_score
            }
        
        # خطر عالي - فقط البيع
        if flash_risk_score >= 50:
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

        # 🚨 فحص RSI أولاً - إذا تشبع شرائي (>75) لا تشتري!
        if rsi > 75:
            return {
                'action': 'DISPLAY',
                'reason': f'🚫 RSI Overbought ({rsi:.0f}) - No Buy',
                'confidence': 0,
                'rsi': rsi
            }

        if rsi <= 35:
            temp_conf += 25
            reasons.append(f"RSI Low ({rsi:.0f})")
        elif 35 < rsi < 55:
            temp_conf += 15
            reasons.append(f"RSI OK ({rsi:.0f})")
        elif 55 <= rsi <= 70:
            # RSI محايد - لا يضيف نقاط لكن لا يمنع
            pass

        # MACD: فقط إذا الفرق كبير (> 0.5) وليس أي رقم موجب
        if macd_diff > 0.5:
            temp_conf += 15
            reasons.append("MACD Bullish")

        if volume_ratio > 1.5:
            temp_conf += 20
            reasons.append(f"Vol Up ({volume_ratio:.1f}x)")

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

        # --- 📊 5. فيبوناتشي (مستويات الدعم/المقاومة) ---
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

        temp_conf = min(max(temp_conf, 0), 99)  # نضمن النطاق 0-99

        # --- نهاية الكود الحساس ---

        # --- 5. تصويت المستشارين ---
        buy_vote_count = 0
        total_advisors = 0
        vote_breakdown = {}
        
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if dl_client and hasattr(dl_client, 'vote_buy_now'):
                mtf = analysis_data.get('mtf', {})
                trend = mtf.get('trend', 'neutral')
                trend_numeric = 1 if trend == 'bullish' else (-1 if trend == 'bearish' else 0)
                
                # جلب التصويت من كل مستشار
                buy_votes, market_status = dl_client.vote_buy_now(
                    rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                    price_momentum=analysis_data.get('price_momentum', 0),
                    confidence=temp_conf,
                    liquidity_metrics=analysis_data.get('liquidity_metrics'),
                    market_sentiment=analysis_data.get('market_sentiment'),
                    candle_analysis=analysis_data.get('candle_analysis')
                )
                
                if buy_votes:
                    total_advisors = len(buy_votes)
                    buy_vote_count = sum(1 for v in buy_votes.values() if v == 1)
                    vote_breakdown = buy_votes
        except Exception as e:
            print(f"⚠️ Buy voting error: {e}")
            pass

        # =========================================================
        # 👑 6. الملك يقرر أولاً (Independent Decision)
        # =========================================================
        min_votes_needed = mood_details.get('min_votes_needed', 4)
        total_advisors = mood_details.get('total_advisors', 7)
        
        # نقاط الشموع من تحليل القاع
        candle_score = reversal.get('confidence', 0)
        
        # ✅ قرار الملك: هل أريد الشراء؟
        king_wants_to_buy = False
        king_reason = ""
        
        # الشرط 1: نقاط كافية (Reversal ≥ MIN_CONFIDENCE)
        if reversal.get('candle_signal', False):
            king_wants_to_buy = True
            king_reason = f"King: Reversal Signal ({candle_score}/110)"
        
        # الشرط 2: أو ثقة الملك عالية (temp_conf ≥ MIN_CONFIDENCE)
        elif temp_conf >= MIN_CONFIDENCE:
            king_wants_to_buy = True
            king_reason = f"King: High Confidence ({temp_conf}/110)"
        
        # =========================================================
        # 🗳️ 7. التصويت الفوري بعد قرار الملك
        # =========================================================
        if king_wants_to_buy and market_mood != "Bearish":
            # الملك قال: أريد الشراء
            # المستشارين: موافقين؟
            if buy_vote_count >= min_votes_needed:
                action = "BUY"
                reason = f"BUY ✅ | King:{temp_conf} | Votes:{buy_vote_count}/{min_votes_needed} | {', '.join(reasons[:3])}"
            else:
                action = "DISPLAY"
                reason = f"King:{temp_conf}/{MIN_CONFIDENCE} | Votes:{buy_vote_count}/{min_votes_needed} (Need {min_votes_needed})"
        elif king_wants_to_buy and market_mood == "Bearish":
            action = "DISPLAY"
            reason = f"Blocked (Bearish Market) | King:{temp_conf}"
        else:
            # الملك مو راضي
            reason = f"King Confidence:{temp_conf}/{MIN_CONFIDENCE} | Need {min_votes_needed} votes"

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

    def should_sell(self, symbol, position, current_price, analysis, mtf, candles=None):
        """القرار الذكي: هل نبيع؟ (صائد القمم الجديد)"""
        from config import MIN_SELL_CONFIDENCE
        
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        # --- 1. شبكة الأمان النهائية: وقف الخسارة المتحرك ---
        highest_price = position.get('highest_price', buy_price)
        drop_from_high = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
        if drop_from_high >= PEAK_DROP_THRESHOLD:
            return {
                'action': 'SELL',
                'reason': f'TRAILING STOP -{drop_from_high:.1f}%',
                'profit': profit_percent
            }
        
        # --- 🚨 1.5 Flash Crash Protection في البيع ---
        flash_crash = analysis.get('flash_crash_protection', {})
        flash_risk = flash_crash.get('risk_score', 0)
        
        # خطر حرج أو عالي - بيع الكل فوراً
        if flash_risk >= 50:
            return {
                'action': 'SELL',
                'reason': f'🚨 Flash Risk ({flash_risk}%) - Emergency Sell',
                'profit': profit_percent,
                'flash_risk': flash_risk
            }
        
        mood_details = self._get_market_mood(analysis)

        # --- الحد الأدنى للربح: ما يبيع أي عملة إلا بربح >= 0.5% ---
        if profit_percent < 0.5:
            return {'action': 'HOLD', 'reason': f'Waiting for +0.5% min profit', 'profit': profit_percent}

        # --- 2. صائد القمم (نظام النقاط الذكي - متوازن) ---
        peak_analysis = analysis.get('peak', {})
        peak_score = peak_analysis.get('confidence', 0)
        candle_condition = peak_analysis.get('candle_signal', False)

        # متوازن: نقاط ≥MIN_SELL_CONFIDENCE أو شمعة قمة قوية
        trigger_activated = candle_condition or peak_score >= MIN_SELL_CONFIDENCE

        if not trigger_activated:
            return {'action': 'HOLD', 'reason': f'Waiting for Peak | Score:{peak_score}/110', 'profit': profit_percent}

        sell_conf = 20
        sell_reasons = []

        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        ema_crossover = analysis.get('ema_crossover', 0)
        price_momentum = analysis.get('price_momentum', 0)
        liquidity_metrics = analysis.get('liquidity_metrics', {})

        # --- 🎯 Profit Target (هدف الربح - حلب العملة) ---
        if profit_percent >= 2.5:
            sell_conf += 20
            sell_reasons.append(f"Excellent Profit +{profit_percent:.1f}%")
        elif profit_percent >= 2.0:
            sell_conf += 18
            sell_reasons.append(f"Great Profit +{profit_percent:.1f}%")
        elif profit_percent >= 1.5:
            sell_conf += 15
            sell_reasons.append(f"Good Profit +{profit_percent:.1f}%")
        elif profit_percent >= 1.0:
            sell_conf += 10
            sell_reasons.append(f"Target Profit +{profit_percent:.1f}%")
        elif profit_percent >= 0.5:
            sell_conf += 5
            sell_reasons.append(f"Small Profit +{profit_percent:.1f}%")
        elif profit_percent < 0:
            sell_conf -= 10
            sell_reasons.append(f"Losing Position {profit_percent:.1f}%")

        if rsi >= 72:  # تحسين: رفع من 70 إلى 72 للصبر
            sell_conf += 25
            sell_reasons.append(f"RSI High ({rsi:.0f})")
        elif rsi >= 68:  # تحسين: رفع من 65 إلى 68
            sell_conf += 15
            sell_reasons.append(f"RSI Elevated ({rsi:.0f})")

        if macd_diff < -1.0:  # تحسين: MACD سالب قوي فقط
            sell_conf += 15
            sell_reasons.append("MACD Bearish")

        if volume_ratio < 0.5:  # تحسين: Volume منخفض جداً فقط
            sell_conf += 10
            sell_reasons.append(f"Vol Low ({volume_ratio:.1f}x)")

        if ema_crossover < 0:
            sell_conf += 15
            sell_reasons.append("EMA Death Cross")

        # --- 📰 تعديل ثقة البيع بالأخبار (مُعدِّل فقط، لا يحكم) ---
        # للبيع: أخبار إيجابية = تخفض رغبة البيع | أخبار سلبية = ترفعها
        news_boost, news_summary = self._get_news_confidence_modifier(symbol)
        if news_boost != 0:
            sell_conf -= news_boost  # عكس الاتجاه: خبر إيجابي يخفف رغبة البيع
            direction = f"+{news_boost}" if news_boost > 0 else str(news_boost)
            sell_reasons.append(f"News({direction})")

        # --- 📊 فيبوناتشي (مستويات المقاومة للبيع) ---
        fib_score = 0
        fib_level = None
        try:
            # 🚨 لا تستخدم Fibonacci إذا RSI منخفض (<30)
            if rsi >= 30:
                fib_analyzer = self.advisor_manager.get('FibonacciAnalyzer') if self.advisor_manager else None
                if fib_analyzer:
                    is_at_resistance, resistance_boost = fib_analyzer.is_at_resistance(
                        current_price=current_price,
                        analysis=analysis,
                        volume_ratio=volume_ratio,
                        symbol=symbol
                    )
                    if is_at_resistance:
                        fib_score = resistance_boost
                        sell_conf += resistance_boost
                        resistance_info = fib_analyzer.get_resistance_level(current_price, analysis)
                        if resistance_info:
                            fib_level = resistance_info['level']
                            sell_reasons.append(f"Fib Resistance {fib_level}% (+{resistance_boost})")
        except Exception as e:
            print(f"⚠️ Fibonacci resistance error: {e}")

        sell_conf = min(max(sell_conf, 0), 99)

        # --- 3. تصويت المستشارين (القرار النهائي) ---
        sell_vote_count = 0
        total_advisors = 0
        vote_breakdown = {}
        
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if dl_client and hasattr(dl_client, 'vote_sell_now'):
                mtf_data = analysis.get('mtf', {})
                trend = mtf_data.get('trend', 'neutral')
                trend_numeric = 1 if trend == 'bullish' else (-1 if trend == 'bearish' else 0)
                
                # حساب ساعات الاحتفاظ
                buy_time = position.get('buy_time')
                hours_held = 24  # default
                if buy_time:
                    try:
                        from datetime import datetime
                        buy_datetime = datetime.fromisoformat(buy_time)
                        hours_held = (datetime.now() - buy_datetime).total_seconds() / 3600
                    except:
                        pass
                
                # جلب التصويت من كل مستشار
                sell_votes = dl_client.vote_sell_now(
                    rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                    price_momentum=price_momentum, liquidity_metrics=liquidity_metrics
                )
                
                if sell_votes:
                    total_advisors = len(sell_votes)
                    sell_vote_count = sum(1 for v in sell_votes.values() if v == 1)
                    vote_breakdown = sell_votes
        except Exception as e:
            print(f"⚠️ Meta sell voting error: {e}")
            pass

        # --- 4. القرار الملكي النهائي: نقاط + التصويت (مع صبر لحلب العملة) ---
        min_votes_needed = mood_details.get('min_votes_needed', 4)
        total_advisors = mood_details.get('total_advisors', 7)
        
        # تحسين: إذا النقاط عالية جداً (≥MIN_SELL_CONFIDENCE+10) أو RSI عالي جداً (≥75)، نبيع بتصويت أقل
        urgent_sell = sell_conf >= MIN_SELL_CONFIDENCE + 10 or rsi >= 75
        
        if urgent_sell:
            # حالة طوارئ: نحتاج 3/7 فقط
            if sell_vote_count >= 3 and peak_score >= MIN_SELL_CONFIDENCE:
                action = 'SELL'
                reason = f"URGENT SELL | Score:{sell_conf}/110 | RSI:{rsi:.0f} | {', '.join(sell_reasons[:3])}"
            else:
                action = 'HOLD'
                reason = f"Hold | Score:{peak_score}/110 | Need Score>={MIN_SELL_CONFIDENCE}"
        else:
            # حالة عادية: نحتاج التصويت الكامل
            if sell_vote_count >= min_votes_needed and peak_score >= MIN_SELL_CONFIDENCE:
                action = 'SELL'
                reason = f"SELL | Score:{sell_conf}/110 | {', '.join(sell_reasons[:3])}"
            else:
                action = 'HOLD'
                reason = f"Hold | Score:{peak_score}/110"

        return {'action': action, 'reason': reason, 'profit': profit_percent, 'sell_votes': vote_breakdown}

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
            mood_details['min_votes_needed'] = 3  # 3/7 موافقين
            mood_details['total_advisors'] = 7
        elif down_count >= 2:
            mood_details['mood'] = "Bearish"
            mood_details['min_votes_needed'] = 5  # 5/7 موافقين
            mood_details['total_advisors'] = 7
        else:
            mood_details['mood'] = "Neutral"
            mood_details['min_votes_needed'] = 4  # 4/7 موافقين
            mood_details['total_advisors'] = 7
        
        return mood_details

    def _calculate_smart_amount(self, symbol, confidence, analysis):
        """حساب المبلغ الذكي بالتصويت من المستشارين + Risk Manager"""
        rsi = analysis.get('rsi', 50)
        macd = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        
        dl_client = self.advisor_manager.get('dl_client')
        if dl_client:
            try:
                risk_vote = None
                risk_manager = self.advisor_manager.get('RiskManager')
                if risk_manager:
                    try:
                        risk_vote = risk_manager.calculate_optimal_amount(symbol, confidence, 12, 20)
                    except:
                        pass
                
                amount_votes = dl_client.vote_amount(rsi, macd, volume_ratio, confidence, risk_vote)
                avg_amount = sum(amount_votes.values()) / len(amount_votes)
                
                king_adjustment = min(max((confidence - 65) * 0.06, -3.0), 3.0)
                final_amount = max(12.0, min(23.0, avg_amount + king_adjustment))
                
                # 🎯 Market Regime Multiplier - مضاعف حالة السوق
                market_regime = analysis.get('market_regime', {})
                regime_multiplier = market_regime.get('trading_advice', {}).get('position_size', 1.0)
                final_amount = final_amount * regime_multiplier
                
                # 🚨 Flash Crash Protection - مضاعف حماية السقوط
                flash_crash = analysis.get('flash_crash_protection', {})
                flash_risk = flash_crash.get('risk_score', 0)
                if flash_risk >= 30:
                    flash_multiplier = 0.5
                    final_amount = final_amount * flash_multiplier
                
                # ⏰ Time Multiplier - مضاعف الوقت
                time_analysis = analysis.get('time_analysis', {})
                time_multiplier = time_analysis.get('trading_recommendation', {}).get('size_multiplier', 1.0)
                final_amount = final_amount * time_multiplier
                
                # 🚨 حد أدنى $12 بعد كل المضاعفات (Binance يحتاج $10)
                final_amount = max(final_amount, MIN_TRADE_AMOUNT)
                
                amount = round(final_amount, 2)
                
                print(f"💰 {symbol}: ${avg_amount:.2f}→${amount} | Regime:{regime_multiplier}x | Time:{time_multiplier}x | Flash:{flash_risk}%")
                
            except Exception as e:
                print(f"⚠️ Meta amount voting error: {e}")
                amount = MIN_TRADE_AMOUNT
        else:
            amount = MIN_TRADE_AMOUNT
        
        return amount

    # =========================================================
    # 🎓 التعلم المباشر للملك - يتعلم من كل صفقة
    # =========================================================
    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, symbol=None):
        """
        التعلم المباشر من كل صفقة
        يتعلم الملك من أخطائه مع Time Decay (الحديث أهم)
        """
        try:
            os.makedirs('data', exist_ok=True)
            
            # تحميل بيانات التعلم
            if os.path.exists(LEARNING_FILE):
                with open(LEARNING_FILE, 'r') as f:
                    data = json.load(f)
            else:
                data = {
                    'trades': [],  # قائمة الصفقات مع timestamps
                    'buy_success': 0, 'buy_fail': 0,
                    'sell_success': 0, 'sell_fail': 0,
                    'peak_correct': 0, 'peak_wrong': 0,
                    'bottom_correct': 0, 'bottom_wrong': 0,
                    'blacklist': {},  # {symbol: {'trap_count': X, 'last_trap': timestamp}}
                    'last_update': datetime.now().isoformat()
                }
            
            # إضافة الصفقة الحالية مع timestamp
            trade_record = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'profit': profit,
                'quality': trade_quality,
                'buy_votes': buy_votes,
                'sell_votes': sell_votes
            }
            
            # 🚫 تحديث القائمة السوداء للعملات الفخ
            if 'blacklist' not in data:
                data['blacklist'] = {}
            
            if symbol and trade_quality in ['TRAP', 'RISKY']:
                if symbol not in data['blacklist']:
                    data['blacklist'][symbol] = {'trap_count': 0, 'last_trap': None}
                data['blacklist'][symbol]['trap_count'] += 1
                data['blacklist'][symbol]['last_trap'] = datetime.now().isoformat()
                print(f"🚫 {symbol} added to blacklist (Trap #{data['blacklist'][symbol]['trap_count']})")
            
            if 'trades' not in data:
                data['trades'] = []
            data['trades'].append(trade_record)
            
            # الاحتفاظ بآخر 1000 صفقة فقط
            if len(data['trades']) > 1000:
                data['trades'] = data['trades'][-1000:]
            
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
            if profit > 0.5:
                data['buy_success'] += 1
                if buy_votes and len([v for v in buy_votes.values() if v == 1]) >= 3:
                    data['bottom_correct'] += 1
            elif profit < -0.5:
                data['buy_fail'] += 1
                if buy_votes and len([v for v in buy_votes.values() if v == 1]) >= 3:
                    data['bottom_wrong'] += 1
            
            # حفظ البيانات
            with open(LEARNING_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            # طباعة التعلم
            total = data['buy_success'] + data['buy_fail'] + data['sell_success'] + data['sell_fail']
            if total > 0:
                success = data['buy_success'] + data['sell_success']
                accuracy = (success / total) * 100
                print(f"👑 King learned: {trade_quality} | Accuracy: {accuracy:.0f}% ({success}/{total})")
            
        except Exception as e:
            print(f"⚠️ خطأ في تعلم الملك: {e}")
    
    def get_learning_stats(self):
        """إحصائيات تعلم الملك"""
        try:
            if os.path.exists(LEARNING_FILE):
                with open(LEARNING_FILE, 'r') as f:
                    data = json.load(f)
                total = data['buy_success'] + data['buy_fail'] + data['sell_success'] + data['sell_fail']
                success = data['buy_success'] + data['sell_success']
                return {
                    'total': total,
                    'success': success,
                    'accuracy': (success / total * 100) if total > 0 else 0,
                    'peak_accuracy': (data['peak_correct'] / (data['peak_correct'] + data['peak_wrong']) * 100) if (data['peak_correct'] + data['peak_wrong']) > 0 else 0,
                    'bottom_accuracy': (data['bottom_correct'] / (data['bottom_correct'] + data['bottom_wrong']) * 100) if (data['bottom_correct'] + data['bottom_wrong']) > 0 else 0
                }
        except:
            pass
        return {'total': 0, 'success': 0, 'accuracy': 0, 'peak_accuracy': 0, 'bottom_accuracy': 0}
    
    def _load_blacklist(self):
        """تحميل القائمة السوداء من الملف المحلي (يُستدعى عند التشغيل وكل ساعة)"""
        try:
            if not os.path.exists(LEARNING_FILE):
                self._blacklist_cache = {}
                self._blacklist_cache_time = datetime.now()
                return
            
            with open(LEARNING_FILE, 'r') as f:
                data = json.load(f)
            
            blacklist_data = data.get('blacklist', {})
            self._blacklist_cache = {}
            
            for symbol, info in blacklist_data.items():
                trap_count = info.get('trap_count', 0)
                last_trap_str = info.get('last_trap')
                
                is_banned = False
                
                # 5+ فخاخ = ممنوع 48 ساعة
                if trap_count >= 5 and last_trap_str:
                    try:
                        last_trap = datetime.fromisoformat(last_trap_str)
                        hours_since = (datetime.now() - last_trap).total_seconds() / 3600
                        if hours_since < 48:
                            is_banned = True
                    except:
                        pass
                
                # 3-4 فخاخ = ممنوع 24 ساعة
                elif trap_count >= 3 and last_trap_str:
                    try:
                        last_trap = datetime.fromisoformat(last_trap_str)
                        hours_since = (datetime.now() - last_trap).total_seconds() / 3600
                        if hours_since < 24:
                            is_banned = True
                    except:
                        pass
                
                self._blacklist_cache[symbol] = is_banned
            
            self._blacklist_cache_time = datetime.now()
            
            # طباعة القائمة السوداء
            banned_symbols = [s for s, banned in self._blacklist_cache.items() if banned]
            if banned_symbols:
                print(f"🚫 Blacklist loaded: {', '.join(banned_symbols)}")
            
        except Exception as e:
            print(f"⚠️ Error loading blacklist: {e}")
            self._blacklist_cache = {}
            self._blacklist_cache_time = datetime.now()
    
    def _is_blacklisted(self, symbol):
        """فحص إذا كانت العملة في القائمة السوداء (من Cache - يُحدّث كل ساعة)"""
        try:
            # تحديث Cache إذا مر ساعة
            if self._blacklist_cache_time:
                elapsed = (datetime.now() - self._blacklist_cache_time).total_seconds()
                if elapsed >= self._blacklist_cache_ttl:
                    print("🔄 Refreshing blacklist cache...")
                    self._load_blacklist()
            
            # فحص من Cache
            is_banned = self._blacklist_cache.get(symbol, False)
            
            if is_banned:
                print(f"🚫 {symbol} is blacklisted (from cache)")
            
            return is_banned
            
        except Exception as e:
            print(f"⚠️ Blacklist check error: {e}")
            return False
