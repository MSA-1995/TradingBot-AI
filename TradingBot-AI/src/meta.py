"""
Meta (The King) - The Ultimate Decision Maker
"""
import pandas as pd
from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, USE_DYNAMIC_TRAILING_STOP, ATR_MULTIPLIER
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
        """القرار باستخدام الملك الجديد (Meta-Learner) - مع التحميل الديناميكي للذاكرة"""
        # First, check for catastrophic news
        news_analyzer = self.advisor_manager.get('NewsAnalyzer')
        if news_analyzer and news_analyzer.should_avoid_coin(symbol):
            return {'action': 'SKIP', 'reason': 'Catastrophic news detected', 'confidence': 0}

        pattern_analyzer = self.advisor_manager.get('EnhancedPatternRecognition')
        peak_hunter_signal = 'neutral'
        if pattern_analyzer and candles:
            peak_hunter_result = pattern_analyzer.analyze_peak_hunter_pattern(candles)
            peak_hunter_signal = peak_hunter_result.get('signal', 'neutral')

        # --- Consultant Buy Voting First ---
        buy_vote_percentage, buy_vote_count, total_consultants = 0, 0, 0
        dl_client = self.advisor_manager.get('dl_client')
        if dl_client:
            try:
                vote_result = dl_client.vote_buy_now(
                    analysis.get('rsi', 50), analysis.get('macd_diff', 0),
                    analysis.get('volume_ratio', 1.0), analysis.get('price_momentum', 0),
                    50, # Base confidence for voting
                    peak_hunter_signal=peak_hunter_signal
                )
                votes = vote_result[0] if isinstance(vote_result, tuple) else vote_result
                if votes:
                    buy_vote_count = sum(votes.values())
                    total_consultants = len(votes)
                    if total_consultants > 0:
                        buy_vote_percentage = (buy_vote_count / total_consultants) * 100
            except Exception as e:
                print(f"⚠️ Consultant buy voting error: {e}")
        # --- End Consultant Buy Voting ---

        # --- Market Sentiment Analysis (3-coin balance) ---
        btc_change = analysis.get('btc_change_1h', 0) if analysis else 0
        eth_change = analysis.get('eth_change_1h', 0) if analysis else 0
        bnb_change = analysis.get('bnb_change_1h', 0) if analysis else 0

        up_count = 0
        down_count = 0
        # A significant move is more than 0.2% in 1 hour
        threshold = 0.2 

        if btc_change > threshold: up_count += 1
        elif btc_change < -threshold: down_count += 1

        if eth_change > threshold: up_count += 1
        elif eth_change < -threshold: down_count += 1

        if bnb_change > threshold: up_count += 1
        elif bnb_change < -threshold: down_count += 1

        if up_count >= 2:
            market_mood = "Bullish"
            min_consensus_percentage = 33 # Be more aggressive
        elif down_count >= 2:
            market_mood = "Bearish"
            min_consensus_percentage = 70 # Be more cautious
        else:
            market_mood = "Neutral"
            min_consensus_percentage = 40 # Balanced approach
        # --- End Market Sentiment ---

        if total_consultants > 0 and buy_vote_percentage < min_consensus_percentage:
            return {
                'action': 'DISPLAY',
                'reason': f'Consultant consensus failed ({buy_vote_percentage:.0f}% < {min_consensus_percentage}%) in {market_mood} market',
                'confidence': 0
            }


        # --- Dynamic Model Loading ---
        # Load the model from raw data
        meta_learner = pickle.loads(self.meta_learner_data)
        # --- End Dynamic Model Loading ---

        decision = {}
        try:
            models_scores = models_scores or {}
            
            # The feature names must match EXACTLY the order and names used in training (9 features)
            feature_names = [
                'smart_money', 'risk', 'anomaly', 'exit', 'pattern', 
                'liquidity', 'chart_cnn', 'brain_confidence', 'was_trapped'
            ]
            
            # Prepare the features for the king in the correct order
            feature_values = [
                models_scores.get('smart_money', 0.5),
                models_scores.get('risk', 0.5),
                models_scores.get('anomaly', 0.5),
                models_scores.get('exit', 0.5),
                models_scores.get('pattern', 0.5),
                models_scores.get('liquidity', 0.5),
                models_scores.get('chart_cnn', 0.5),
                models_scores.get('brain_confidence', 50),
                models_scores.get('was_trapped', 0)
            ]

            opinions_df = pd.DataFrame([feature_values], columns=feature_names)

            # The King makes the prediction
            prediction = meta_learner.predict(opinions_df)[0]
            probability = meta_learner.predict_proba(opinions_df)[0]
            confidence = int(probability[1] * 100)

            # Add news confidence boost
            if news_analyzer: # Already fetched above
                news_boost = news_analyzer.get_news_confidence_boost(symbol)
                confidence += news_boost

            # Add fibonacci confidence boost
            fibonacci_analyzer = self.advisor_manager.get('FibonacciAnalyzer')
            if fibonacci_analyzer:
                fibo_boost = fibonacci_analyzer.get_confidence_boost(analysis['close'], analysis, analysis.get('volume_ratio', 1.0), symbol)
                confidence += fibo_boost

            confidence = max(0, min(100, confidence))

            # The King makes the final decision, but only after consultants have agreed
            if prediction == 1 and confidence >= 55:
                amount = self._calculate_smart_amount(symbol, confidence, analysis)

                decision = {
                    'action': 'BUY', 'confidence': confidence, 'amount': amount,
                    'reason': f'Meta approved ({buy_vote_percentage:.0f}% consultants agree)',
                    'buy_vote_percentage': buy_vote_percentage, 'buy_vote_count': buy_vote_count,
                    'total_consultants': total_consultants
                }
            else:
                reason = f'Meta rejected with {confidence}% confidence'
                if prediction == 0: reason = f'Meta voted SKIP'
                elif confidence < 55: reason = f'Meta confidence {confidence}% < 55%'
                decision = {'action': 'DISPLAY', 'reason': reason, 'confidence': confidence}

        except Exception as e:
            print(f"❌ Meta-Learner prediction error: {e}")
            decision = {'action': 'SKIP', 'reason': 'Meta-Learner error', 'confidence': 0}
        
        finally:
            # --- Cleanup ---
            del meta_learner
            gc.collect()
            # --- End Cleanup ---
        
        return decision

    def should_sell(self, symbol, position, current_price, analysis, mtf, candles=None):
        """القرار الذكي: هل نبيع؟ (الملك يقرر مع استشارة المستشارين)"""
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100

        # --- 1. Market Sentiment Analysis (3-coin balance) ---
        btc_change = analysis.get('btc_change_1h', 0) if analysis else 0
        eth_change = analysis.get('eth_change_1h', 0) if analysis else 0
        bnb_change = analysis.get('bnb_change_1h', 0) if analysis else 0

        up_count = 0
        down_count = 0
        # A significant move is more than 0.2% in 1 hour
        threshold = 0.2

        if btc_change > threshold: up_count += 1
        elif btc_change < -threshold: down_count += 1

        if eth_change > threshold: up_count += 1
        elif eth_change < -threshold: down_count += 1

        if bnb_change > threshold: up_count += 1
        elif bnb_change < -threshold: down_count += 1

        if up_count >= 2:
            market_mood = "Bullish"
        elif down_count >= 2:
            market_mood = "Bearish"
        else:
            market_mood = "Neutral"
        # --- End Market Sentiment ---

        # --- 2. Emergency Exit: Catastrophic News ONLY in a Bearish Market ---
        news_analyzer = self.advisor_manager.get('NewsAnalyzer')
        if news_analyzer and news_analyzer.should_avoid_coin(symbol):
            if market_mood == "Bearish":
                print(f"🚨 {symbol}: EMERGENCY EXIT (Catastrophic news in bearish market)")
                return {
                    'action': 'SELL',
                    'reason': 'EMERGENCY EXIT (News)',
                    'profit': profit_percent
                }
            else:
                # Log that we are ignoring the news because the market is strong
                print(f"📰 {symbol}: Ignoring catastrophic news due to {market_mood} market.")
        # --- End Emergency Exit ---

        # --- 3. Standard Trailing Stop Loss ---
        highest_price = position.get('highest_price', buy_price)
        stop_loss_percent = 2.0
        reason_prefix = "TRAILING STOP"
        drop_from_high = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
        
        if drop_from_high >= stop_loss_percent:
            print(f"🛑 {symbol}: {reason_prefix} triggered (dropped {drop_from_high:.2f}% from peak, limit {stop_loss_percent:.2f}%)")
            return {
                'action': 'SELL',
                'reason': f'{reason_prefix} -{stop_loss_percent:.1f}%',
                'profit': profit_percent
            }
        
        pattern_analyzer = self.advisor_manager.get('EnhancedPatternRecognition')
        peak_hunter_signal = 'neutral'
        if pattern_analyzer and candles:
            peak_hunter_result = pattern_analyzer.analyze_peak_hunter_pattern(candles)
            peak_hunter_signal = peak_hunter_result.get('signal', 'neutral')

        # --- 4. Consultant Voting (Dynamic Consensus) ---
        dl_client = self.advisor_manager.get('dl_client')
        if dl_client:
            try:
                rsi = analysis.get('rsi', 50) if analysis else 50
                macd_diff = analysis.get('macd_diff', 0) if analysis else 0
                volume_ratio = analysis.get('volume_ratio', 1.0) if analysis else 1.0
                trend = mtf.get('trend', 'neutral') if mtf else 'neutral'
                
                market_sentiment = None
                try:
                    btc_change_1h = analysis.get('btc_change_1h', 0) if analysis else 0
                    eth_change_1h = analysis.get('eth_change_1h', 0) if analysis else 0
                    bnb_change_1h = analysis.get('bnb_change_1h', 0) if analysis else 0
                    market_sentiment = {
                        'btc_change_1h': btc_change_1h,
                        'eth_change_1h': eth_change_1h,
                        'bnb_change_1h': bnb_change_1h
                    }
                except:
                    pass
                
                # Re-calculate these values as they were moved from the top
                highest_price = position.get('highest_price', buy_price)
                highest_profit_percent = ((highest_price - buy_price) / buy_price) * 100
                drop_from_high_percent = ((highest_price - current_price) / buy_price) * 100
                hours_held = 24  # default
                try:
                    buy_time_str = position.get('buy_time')
                    if buy_time_str and isinstance(buy_time_str, str):
                        buy_time = datetime.fromisoformat(buy_time_str)
                        hours_held = (datetime.now() - buy_time).total_seconds() / 3600
                except Exception as e:
                    hours_held = 24  # fallback

                sell_votes = dl_client.vote_sell_now(
                symbol, profit_percent, rsi, macd_diff, volume_ratio, trend, hours_held,
                market_sentiment, highest_profit_percent, drop_from_high_percent, peak_hunter_signal=peak_hunter_signal
            )

                # --- Dynamic Consensus Threshold for Selling (using mood from above) ---
                if market_mood == "Bullish":
                    min_sell_percentage = 70  # Bullish: Hold for more profit, sell only on strong consensus
                elif market_mood == "Bearish":
                    min_sell_percentage = 33  # Bearish: Get out quickly on weaker consensus
                else: # Neutral
                    min_sell_percentage = 40  # Neutral: Balanced approach
                # --- End Dynamic Consensus ---

                total_votes = len(sell_votes)
                if total_votes > 0:
                    sell_count = sum(sell_votes.values())
                    sell_percentage = (sell_count / total_votes) * 100

                    if sell_percentage >= min_sell_percentage:
                        reason_type = "profit" if profit_percent > 0 else "loss"
                        print(f"🗳️ {symbol}: {sell_count}/{total_votes} voted SELL ({sell_percentage:.0f}% >= {min_sell_percentage}%) in {market_mood} market - {reason_type}")
                        return {
                            'action': 'SELL',
                            'reason': f'Voted SELL in {market_mood} market ({sell_percentage:.0f}%)',
                            'profit': profit_percent
                        }

                    
            except Exception as e:
                print(f"⚠️ Sell voting error: {e}")
        
        return {'action': 'HOLD', 'reason': 'Waiting for target'}

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
