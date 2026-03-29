"""
Meta (The King) - The Ultimate Decision Maker
"""
import pandas as pd
from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, USE_DYNAMIC_TRAILING_STOP, ATR_MULTIPLIER, MIN_CONFIDENCE, PEAK_DROP_THRESHOLD, BOTTOM_BOUNCE_THRESHOLD, VOLUME_SPIKE_FACTOR
from datetime import datetime
import gc
import psutil
import pickle
import os
from datetime import datetime

class Meta:
    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager = advisor_manager # <<< The King now keeps his secretary
        self.storage = storage
        self.meta_learner_data = None # Store the raw model data, not the loaded model
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

        # --- 1. Market Mood ---
        mood_details = self._get_market_mood(analysis_data)
        market_mood = mood_details['mood']

        # --- 2. Technical Indicators ---
        rsi = analysis_data.get('rsi', 50)
        macd_diff = analysis_data.get('macd_diff', 0)
        volume_ratio = analysis_data.get('volume_ratio', 1.0)
        ema_crossover = analysis_data.get('ema_crossover', 0)

        if rsi <= 35:
            temp_conf += 25
            reasons.append(f"RSI Low ({rsi:.0f})")
        elif 35 < rsi < 55:
            temp_conf += 15
            reasons.append(f"RSI OK ({rsi:.0f})")

        if macd_diff > 0.0:
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

        temp_conf = min(max(temp_conf, 0), 99)  # نضمن النطاق 0-99

        # --- نهاية الكود الحساس ---

        # --- 5. تصويت المستشارين ---
        buy_votes = {}
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if dl_client and hasattr(dl_client, 'vote_buy_now'):
                mtf = analysis_data.get('mtf', {})
                trend = mtf.get('trend', 'neutral')
                trend_numeric = 1 if trend == 'bullish' else (-1 if trend == 'bearish' else 0)
                buy_vote = dl_client.vote_buy_now(
                    rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                    trend=trend_numeric, mtf_score=mtf.get('total', 0)
                )
                if buy_vote:
                    buy_votes['dl_client'] = buy_vote.get('score', 0)
        except Exception:
            pass

        # --- 6. القرار النهائي ---
        if temp_conf >= MIN_CONFIDENCE:
            if buy_votes:
                consultant_avg = sum(buy_votes.values()) / len(buy_votes)
                final_vote = (temp_conf + consultant_avg) / 2
            else:
                final_vote = temp_conf

            min_required = mood_details.get('min_buy_consensus', 57)
            
            # --- صائد القيعان (الزناد: فوليوم + شمعة مؤكدة) ---
            candle_condition = reversal.get('candle_signal', False) # candle_signal now means confirmed pattern
            volume_condition = volume_ratio > VOLUME_SPIKE_FACTOR
            trigger_activated = candle_condition and volume_condition

            if final_vote >= min_required:
                if trigger_activated:
                    action = "BUY"
                    reason = f"Bottom Hunter Triggered | Conf:{final_vote:.0f}% >= {min_required}% | {', '.join(reasons)}"
                else:
                    action = "DISPLAY"
                    reason = f"Wait Bottom Hunter (Vol:{volume_condition}, Candle:{candle_condition}) | Conf:{final_vote:.0f}% | {', '.join(reasons)}"
            else:
                action = "DISPLAY"
                reason = f"Conf:{temp_conf}% | {', '.join(reasons) if reasons else 'Monitoring'}"
        else:
            action = "DISPLAY"
            reason = f"Conf:{temp_conf}% | {', '.join(reasons) if reasons else 'Monitoring'}"

        if market_mood == "Bearish" and action == "BUY":
            action = "DISPLAY"
            reason = "Market Bearish - holding off buy"
            temp_conf = max(20, temp_conf - 30)

        decision = {
            'action': action,
            'reason': reason,
            'confidence': temp_conf,
            'news_summary': news_summary  # للعرض فقط في الواجهة
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

        mood_details = self._get_market_mood(analysis)

        # --- 2. صائد القمم (الزناد: فوليوم + شمعة مؤكدة) ---
        peak_analysis = analysis.get('peak', {})
        candle_condition   = peak_analysis.get('candle_signal', False) # candle_signal now means confirmed pattern

        volume_spike_factor_sell = VOLUME_SPIKE_FACTOR + 0.5
        volume_condition = analysis.get('volume_ratio', 1.0) > volume_spike_factor_sell

        trigger_activated = candle_condition and volume_condition

        if not trigger_activated:
            return {'action': 'HOLD', 'reason': f'Waiting for Peak Hunter trigger (Vol:{volume_condition}, Candle:{candle_condition})', 'profit': profit_percent}

        print(f"🎯 {symbol}: PEAK HUNTER trigger activated. Proceeding to full council vote.")

        sell_conf = 20
        sell_reasons = []

        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        ema_crossover = analysis.get('ema_crossover', 0)

        if rsi >= 70:
            sell_conf += 25
            sell_reasons.append(f"RSI High ({rsi:.0f})")
        elif rsi >= 60:
            sell_conf += 15
            sell_reasons.append(f"RSI Elevated ({rsi:.0f})")

        if macd_diff < 0:
            sell_conf += 15
            sell_reasons.append("MACD Bearish")

        if volume_ratio < 0.7:
            sell_conf += 10
            sell_reasons.append(f"Vol Low ({volume_ratio:.1f}x)")

        if ema_crossover < 0:
            sell_conf += 15
            sell_reasons.append("EMA Death Cross")

        # The 'peak_analysis' variable is already defined above
        peak_confidence = peak_analysis.get('confidence', 0)
        peak_reasons = peak_analysis.get('reasons', [])

        if peak_confidence > 0:
            sell_conf += peak_confidence
            sell_reasons.extend(peak_reasons)

        # --- 📰 تعديل ثقة البيع بالأخبار (مُعدِّل فقط، لا يحكم) ---
        # للبيع: أخبار إيجابية = تخفض رغبة البيع | أخبار سلبية = ترفعها
        news_boost, news_summary = self._get_news_confidence_modifier(symbol)
        if news_boost != 0:
            sell_conf -= news_boost  # عكس الاتجاه: خبر إيجابي يخفف رغبة البيع
            direction = f"+{news_boost}" if news_boost > 0 else str(news_boost)
            sell_reasons.append(f"News({direction})")

        sell_conf = min(max(sell_conf, 0), 99)

        # --- 3. القرار الملكي النهائي (Peak Hunter) ---
        min_required_conf = mood_details.get('min_sell_consensus', 55)

        if sell_conf >= min_required_conf:
            action = 'SELL'
            reason = f"Peak Hunter SELL | Conf {sell_conf:.0f}% | {', '.join(sell_reasons)}"
        else:
            action = 'HOLD'
            reason = f"Triggered but low conf ({sell_conf}%) | Holding"

        return {'action': action, 'reason': reason, 'profit': profit_percent}

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
            mood_details['min_buy_consensus'] = 42
            mood_details['min_sell_consensus'] = 70
        elif down_count >= 2:
            mood_details['mood'] = "Bearish"
            mood_details['min_buy_consensus'] = 71
            mood_details['min_sell_consensus'] = 33
        else:
            mood_details['mood'] = "Neutral"
            mood_details['min_buy_consensus'] = 57
            mood_details['min_sell_consensus'] = 50
        
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
                
                amount = round(final_amount, 2)
                
                print(f"💰 {symbol}: ${avg_amount:.2f}→${amount} (Meta Vote)")
                
            except Exception as e:
                print(f"⚠️ Meta amount voting error: {e}")
                amount = MIN_TRADE_AMOUNT
        else:
            amount = MIN_TRADE_AMOUNT
        
        return amount
