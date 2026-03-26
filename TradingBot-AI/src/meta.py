"""
Meta (The King) - The Ultimate Decision Maker
"""
import pandas as pd
from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, USE_DYNAMIC_TRAILING_STOP, ATR_MULTIPLIER
from datetime import datetime
import pickle
import os
from datetime import datetime

class Meta:
    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager = advisor_manager # <<< The King now keeps his secretary
        self.storage = storage
        self.meta_learner = None
        self.load_meta_learner()
        print("👑 Meta (The King) is initialized and ready to rule.")

    def load_meta_learner(self):
        """تحميل عقل الملك الجديد المدرب من قاعدة البيانات عبر AdvisorManager"""
        if not self.advisor_manager:
            print("⚠️ Meta: Advisor Manager not provided, cannot load Meta-Learner.")
            return

        try:
            # Use the advisor_manager to get the dl_client
            dl_client = self.advisor_manager.get('dl_client')
            if not dl_client:
                print("⚠️ Meta: Deep Learning Client not available via Advisor Manager.")
                return

            # Use dl_client to get the model from the database
            model_data = dl_client.get_model_data('meta_learner')

            if model_data:
                self.meta_learner = pickle.loads(model_data)
                #print("👑🧠 Meta: New King's Brain (Meta-Learner) loaded successfully from DB!")
            else:
                print("⚠️ Meta: Meta-Learner model not found in DB. Buy decisions will be disabled.")
                self.meta_learner = None
        except Exception as e:
            print(f"❌ Meta: Error loading Meta-Learner model from DB: {e}")
            print("💡 Hint: Ensure the 'get_model_data' method exists in 'dl_client_v2.py' and the model is in 'dl_models_v2' table.")
            self.meta_learner = None

    def is_active(self):
        return self.meta_learner is not None

    def should_buy(self, symbol, analysis, models_scores):
        """القرار باستخدام الملك الجديد (Meta-Learner)"""
        # First, check for catastrophic news
        news_analyzer = self.advisor_manager.get('NewsAnalyzer')
        if news_analyzer and news_analyzer.should_avoid_coin(symbol):
            return {'action': 'SKIP', 'reason': 'Catastrophic news detected', 'confidence': 0}

        if not self.is_active():
            return {'action': 'DISPLAY', 'reason': 'Meta-Learner NOT ACTIVE', 'confidence': 0}

        if not self.is_active():
            return {'action': 'DISPLAY', 'reason': 'Meta-Learner NOT ACTIVE', 'confidence': 0}

        models_scores = models_scores or {}
        
        # The feature names must match EXACTLY the order and names used in training (9 features)
        feature_names = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern', 
            'liquidity', 'chart_cnn', 'brain_confidence', 'was_trapped'
        ]
        
        # Prepare the features for the king in the correct order
        try:
            # Create a list of feature values from the models_scores dictionary
            # Use a default of 0.5 for any missing consultant scores
            # Use a default of 50 for brain_confidence and 0 for was_trapped if missing
            feature_values = [
                models_scores.get('smart_money', 0.5),
                models_scores.get('risk', 0.5),
                models_scores.get('anomaly', 0.5),
                models_scores.get('exit', 0.5),
                models_scores.get('pattern', 0.5),
                models_scores.get('liquidity', 0.5),
                models_scores.get('chart_cnn', 0.5),
                # 'rescue' was removed as the model was not trained on it.
                models_scores.get('brain_confidence', 50), # Feature from old brain
                models_scores.get('was_trapped', 0)       # Feature from old brain
            ]

            # Create a DataFrame for the model prediction
            opinions_df = pd.DataFrame([feature_values], columns=feature_names)

            # The King makes the prediction
            prediction = self.meta_learner.predict(opinions_df)[0]
            probability = self.meta_learner.predict_proba(opinions_df)[0]
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

            confidence = max(0, min(100, confidence)) # Ensure confidence is between 0 and 100

        except Exception as e:
            print(f"❌ Meta-Learner prediction error: {e}")
            return {'action': 'SKIP', 'reason': 'Meta-Learner error', 'confidence': 0}

        if prediction == 1 and confidence >= 55:
            amount = self._calculate_smart_amount(symbol, confidence, analysis)
            
            # --- Consultant Buy Voting ---
            buy_vote_percentage = 0
            buy_vote_count = 0
            total_consultants = 0
            dl_client = self.advisor_manager.get('dl_client')
            if dl_client:
                try:
                    rsi = analysis.get('rsi', 50)
                    macd = analysis.get('macd_diff', 0)
                    volume_ratio = analysis.get('volume_ratio', 1.0)
                    price_momentum = analysis.get('price_momentum', 0)
                    
                    # Get votes from consultants
                    vote_result = dl_client.vote_buy_now(
                        rsi, macd, volume_ratio, price_momentum, confidence
                    )
                    
                    # Handle tuple return (votes_dict, market_status)
                    votes = vote_result[0] if isinstance(vote_result, tuple) else vote_result
                    
                    if votes:
                        buy_vote_count = sum(votes.values())
                        total_consultants = len(votes)
                        if total_consultants > 0:
                            buy_vote_percentage = (buy_vote_count / total_consultants) * 100
                except Exception as e:
                    print(f"⚠️ Consultant buy voting error: {e}")
            # --- End Consultant Buy Voting ---

            decision = {
                'action': 'BUY',
                'confidence': confidence,
                'amount': amount,
                'reason': f'Meta approved with {confidence}% confidence',
                'buy_vote_percentage': buy_vote_percentage,
                'buy_vote_count': buy_vote_count,
                'total_consultants': total_consultants
            }
            return decision
        else:
            reason = f'Meta rejected with {confidence}% confidence'
            if prediction == 0:
                reason = f'Meta voted SKIP'
            elif confidence < 55:
                reason = f'Meta confidence {confidence}% < 55%'

            # THIS IS THE FIX: Return 'DISPLAY' instead of 'SKIP'
            return {'action': 'DISPLAY', 'reason': reason, 'confidence': confidence}

    def should_sell(self, symbol, position, current_price, analysis, mtf):
        """القرار الذكي: هل نبيع؟ (الملك يقرر مع استشارة المستشارين)"""
        buy_price = position['buy_price']
        highest_price = position.get('highest_price', buy_price)
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        
        # حساب المدة - حماية من None
        hours_held = 24  # default
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str and isinstance(buy_time_str, str):
                buy_time = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except Exception as e:
            hours_held = 24  # fallback
        
        # حساب أعلى ربح محقق والنزول منه (للمستشارين)
        highest_profit_percent = ((highest_price - buy_price) / buy_price) * 100
        drop_from_high_percent = ((highest_price - current_price) / buy_price) * 100

        # 0. Zombie Trade Check (3 Days Limit)
        if hours_held >= 72:
            return {
                'action': 'SELL',
                'reason': 'ZOMBIE TRADE (72h timeout)',
                'profit': profit_percent
            }

        # 1. Dynamic Trailing Stop Loss
        stop_loss_percent = 2.0  # Default static 2%
        reason_prefix = "TRAILING STOP"

        if USE_DYNAMIC_TRAILING_STOP and analysis and analysis.get('atr', 0) > 0:
            atr = analysis.get('atr')
            # Calculate stop-loss based on ATR, relative to current price
            dynamic_stop_loss = (atr / current_price) * 100 * ATR_MULTIPLIER
            # Use the dynamic value, but keep it within reasonable bounds (e.g., 1.5% to 5.0%)
            stop_loss_percent = max(1.5, min(dynamic_stop_loss, 5.0))
            reason_prefix = "DYNAMIC TSL"

        drop_from_high = ((highest_price - current_price) / highest_price) * 100
        
        if drop_from_high >= stop_loss_percent:
            print(f"🛑 {symbol}: {reason_prefix} triggered (dropped {drop_from_high:.2f}% from peak, limit {stop_loss_percent:.2f}%)")
            return {
                'action': 'SELL',
                'reason': f'{reason_prefix} -{stop_loss_percent:.1f}%',
                'profit': profit_percent
            }
        
        # 3. استشارة المستشارين للبيع (تصويت - النظام الوحيد للبيع)
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
                
                sell_votes = dl_client.vote_sell_now(
                    symbol, profit_percent, rsi, macd_diff, volume_ratio, trend, hours_held,
                    market_sentiment, highest_profit_percent, drop_from_high_percent
                )
                
                total_votes = len(sell_votes)
                sell_count = sum(sell_votes.values())
                sell_percentage = (sell_count / total_votes) * 100
                
                if sell_count >= 3:
                    reason_type = "profit" if profit_percent > 0 else "loss"
                    market_info = ""
                    if market_sentiment:
                        btc = market_sentiment['btc_change_1h']
                        eth = market_sentiment['eth_change_1h']
                        bnb = market_sentiment['bnb_change_1h']
                        market_info = f" | Market: BTC {btc:+.1f}% ETH {eth:+.1f}% BNB {bnb:+.1f}%"
                    print(f"🗳️ {symbol}: {sell_count}/{total_votes} voted SELL ({sell_percentage:.0f}%) - {reason_type}{market_info}")
                    return {
                        'action': 'SELL',
                        'reason': f'Consultants voted SELL ({sell_percentage:.0f}%)',
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
