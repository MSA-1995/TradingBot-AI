"""
Meta (The King) - The Ultimate Decision Maker
"""
import pandas as pd
from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, USE_DYNAMIC_TRAILING_STOP, ATR_MULTIPLIER, MIN_CONFIDENCE, PEAK_DROP_THRESHOLD, BOTTOM_BOUNCE_THRESHOLD
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

    def should_buy(self, symbol, analysis, models_scores, candles=None):
        """القرار - كشف القاع بالشموع + مؤشرات + تصويت المستشارين"""

        analysis_data = analysis
        temp_conf = 20
        action = "DISPLAY"
        reasons = []

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

        # --- 3. كشف القاع بالشموع ---
        reversal = analysis_data.get('reversal', {})
        if reversal.get('is_reversing'):
            temp_conf += 20
            reasons.append(f"Bottom Bounce {reversal.get('bounce_percent', 0):.2f}%")
        elif reversal.get('candle_signal'):
            temp_conf += 10
            reasons.append("Candle Bottom Signal")

        temp_conf = min(temp_conf, 99)

        # --- 4. تصويت المستشارين ---
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

        # --- 5. القرار النهائي ---
        if temp_conf >= MIN_CONFIDENCE:
            if buy_votes:
                consultant_avg = sum(buy_votes.values()) / len(buy_votes)
                final_vote = (temp_conf + consultant_avg) / 2
            else:
                final_vote = temp_conf

            min_required = mood_details.get('min_buy_consensus', 57)
            if final_vote >= min_required:
                action = "BUY"
                reason = f"Bottom+Indicators | Conf:{final_vote:.0f}% >= {min_required}% | {', '.join(reasons)}"
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

        # 🛡️ حارس السيولة (Fake Pump Blocker)
        # يمنع الشراء في اللحظة الأخيرة إذا كانت السيولة ضعيفة، مع إبقاء العملة ظاهرة على الشاشة
        if action == "BUY" and volume_ratio < 0.8:
            action = "DISPLAY"
            reason = f"Blocked: Weak Volume ({volume_ratio:.1f}x) ⚠️"

        decision = {'action': action, 'reason': reason, 'confidence': temp_conf}

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
        """القرار الذكي: هل نبيع؟ (الملك يقرر مع استشارة المستشارين)"""
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        # --- 1. Unconditional Rule: Trailing Stop Loss (The Royal Guard) ---
        highest_price = position.get('highest_price', buy_price)
        stop_loss_percent = 2.0
        drop_from_high = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
        if drop_from_high >= stop_loss_percent:
            print(f"🛑 {symbol}: TRAILING STOP triggered (dropped {drop_from_high:.2f}% from peak, limit {stop_loss_percent:.2f}%)")
            return {
                'action': 'SELL',
                'reason': f'TRAILING STOP -{stop_loss_percent:.1f}%',
                'profit': profit_percent
            }

        # News is now just a confidence factor, not an emergency exit.
        news_analyzer = self.advisor_manager.get('NewsAnalyzer')
        mood_details = self._get_market_mood(analysis)

        # --- 3. كشف القمة بالشموع + تصويت المستشارين ---
        sell_conf = 20
        sell_reasons = []

        # مؤشرات البيع
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        ema_crossover = analysis.get('ema_crossover', 0)

        # RSI تشبع شرائي
        if rsi >= 70:
            sell_conf += 25
            sell_reasons.append(f"RSI High ({rsi:.0f})")
        elif rsi >= 60:
            sell_conf += 15
            sell_reasons.append(f"RSI Elevated ({rsi:.0f})")

        # MACD هبوط
        if macd_diff < 0:
            sell_conf += 15
            sell_reasons.append("MACD Bearish")

        # حجم منخفض = ضعف الاتجاه
        if volume_ratio < 0.7:
            sell_conf += 10
            sell_reasons.append(f"Vol Low ({volume_ratio:.1f}x)")

        # EMA سلبي
        if ema_crossover < 0:
            sell_conf += 15
            sell_reasons.append("EMA Death Cross")

        # كشف القمة بالشموع
        peak = analysis.get('peak', {})
        if peak.get('is_peaking'):
            sell_conf += 20
            sell_reasons.append(f"Peak Drop {peak.get('drop_percent', 0):.2f}%")
        elif peak.get('candle_signal'):
            sell_conf += 10
            sell_reasons.append("Candle Peak Signal")

        sell_conf = min(sell_conf, 99)

        # تصويت المستشارين للبيع
        sell_vote_percentage = 0
        total_consultants = 0
        try:
            dl_client = self.advisor_manager.get('dl_client')
            if dl_client and hasattr(dl_client, 'vote_sell_now'):
                buy_time_str = position.get('buy_time')
                hours_held = 0
                if buy_time_str:
                    buy_time_dt = datetime.fromisoformat(buy_time_str)
                    hours_held = (datetime.now() - buy_time_dt).total_seconds() / 3600

                mtf = analysis.get('mtf', {})
                trend = mtf.get('trend', 'neutral')
                trend_numeric = 1 if trend == 'bullish' else (-1 if trend == 'bearish' else 0)

                sell_votes = dl_client.vote_sell_now(
                    macd_diff, volume_ratio,
                    trend=trend_numeric,
                    hours_held=hours_held
                )
                if sell_votes:
                    sell_vote_percentage = sell_votes.get('score', 0)
                    total_consultants = 1
        except Exception as e:
            pass

        min_consensus_percentage = mood_details['min_sell_consensus']

        if sell_conf >= MIN_CONFIDENCE:
            if total_consultants > 0:
                final_sell_vote = (sell_conf + sell_vote_percentage) / 2
            else:
                final_sell_vote = sell_conf

            if final_sell_vote >= min_consensus_percentage:
                return {
                    'action': 'SELL',
                    'reason': f"Peak+Indicators | Conf:{final_sell_vote:.0f}% >= {min_consensus_percentage}% | {', '.join(sell_reasons)}",
                    'profit': profit_percent
                }
            else:
                return {'action': 'HOLD', 'reason': f"Sell conf {final_sell_vote:.0f}% < {min_consensus_percentage}% | {', '.join(sell_reasons) if sell_reasons else 'Holding'}"}
        else:
            return {'action': 'HOLD', 'reason': f"Low sell conf ({sell_conf}%) | Holding"}

    def _get_market_mood(self, analysis):
        """Analyzes BTC, ETH, BNB changes to determine the overall market mood and required consensus."""
        btc_change = analysis.get('btc_change_1h', 0) if analysis else 0
        eth_change = analysis.get('eth_change_1h', 0) if analysis else 0
        bnb_change = analysis.get('bnb_change_1h', 0) if analysis else 0

        up_count = 0
        down_count = 0
        # A significant move is more than 0.5% in 1 hour (0.2% was too sensitive for crypto noise)
        threshold = 0.5 

        if btc_change > threshold: up_count += 1
        elif btc_change < -threshold: down_count += 1

        if eth_change > threshold: up_count += 1
        elif eth_change < -threshold: down_count += 1

        if bnb_change > threshold: up_count += 1
        elif bnb_change < -threshold: down_count += 1

        mood_details = {}
        if up_count >= 2:
            mood_details['mood'] = "Bullish" # سوق صاعد (إيجابي)
            mood_details['min_buy_consensus'] = 42 # نسبة الشراء: 42% (3/7) - أكثر حذراً
            mood_details['min_sell_consensus'] = 70 # نسبة البيع: 70% (نطمع في الربح ولا نبيع بسرعة)
        elif down_count >= 2:
            mood_details['mood'] = "Bearish" # سوق هابط (سلبي)
            mood_details['min_buy_consensus'] = 71 # نسبة الشراء: 71% (5/7) - حذر جداً، نبحث عن فرصة حقيقية فقط
            mood_details['min_sell_consensus'] = 33 # نسبة البيع: 33% (هروب سريع لحماية رأس المال)
        else:
            mood_details['mood'] = "Neutral" # سوق محايد (مستقر)
            mood_details['min_buy_consensus'] = 57 # نسبة الشراء: 57% (4/7) - أغلبية واضحة مطلوبة
            mood_details['min_sell_consensus'] = 50 # نسبة البيع: 50% (جني أرباح متوازن)
        
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