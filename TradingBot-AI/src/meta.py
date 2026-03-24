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
    def __init__(self, dl_client=None, risk_manager=None, rescue_scalper=None, storage=None, news_analyzer=None, fibonacci_analyzer=None):
        self.dl_client = dl_client
        self.risk_manager = risk_manager
        self.rescue_scalper = rescue_scalper
        self.storage = storage
        self.news_analyzer = news_analyzer
        self.fibonacci_analyzer = fibonacci_analyzer
        self.meta_learner = None
        self.load_meta_learner()
        print("👑 Meta (The King) is initialized and ready to rule.")

    def load_meta_learner(self):
        """تحميل عقل الملك الجديد المدرب من قاعدة البيانات عبر dl_client"""
        if not self.dl_client:
            print("⚠️ Meta: Deep Learning Client not provided, cannot load Meta-Learner.")
            return

        try:
            # استخدم dl_client لجلب النموذج من قاعدة البيانات
            model_data = self.dl_client.get_model_data('meta_learner')

            if model_data:
                self.meta_learner = pickle.loads(model_data)
                print("👑🧠 Meta: New King's Brain (Meta-Learner) loaded successfully from DB!")
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
        if self.news_analyzer and self.news_analyzer.should_avoid_coin(symbol):
            return {'action': 'SKIP', 'reason': 'Catastrophic news detected', 'confidence': 0}

        if not self.is_active():
            return {'action': 'SKIP', 'reason': 'Meta-Learner is not active', 'confidence': 0}

        models_scores = models_scores or {}
        
        # The feature names must match EXACTLY the order and names used in training!
        feature_names = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern', 
            'liquidity', 'chart_cnn', 'rescue', 'brain_confidence', 'was_trapped'
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
                models_scores.get('rescue', 0.5),
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
            if self.news_analyzer:
                news_boost = self.news_analyzer.get_news_confidence_boost(symbol)
                confidence += news_boost

            # Add fibonacci confidence boost
            if self.fibonacci_analyzer and analysis.get('df') is not None:
                fibo_boost = self.fibonacci_analyzer.get_confidence_boost(analysis['df']['close'].iloc[-1], analysis['df'], analysis.get('volume_ratio', 1.0), symbol)
                confidence += fibo_boost

            confidence = max(0, min(100, confidence)) # Ensure confidence is between 0 and 100

        except Exception as e:
            print(f"❌ Meta-Learner prediction error: {e}")
            return {'action': 'SKIP', 'reason': 'Meta-Learner error', 'confidence': 0}

        if prediction == 1 and confidence >= 55:
            amount = self._calculate_smart_amount(symbol, confidence, analysis)
            decision = {
                'action': 'BUY',
                'confidence': confidence,
                'amount': amount,
                'reason': f'Meta approved with {confidence}% confidence',
            }
            return decision
        else:
            reason = f'Meta rejected with {confidence}% confidence'
            if prediction == 0:
                reason = f'Meta voted SKIP'
            elif confidence < 55:
                reason = f'Meta confidence {confidence}% < 55%'

            return {'action': 'SKIP', 'reason': reason, 'confidence': confidence}

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
            if self.rescue_scalper:
                print(f"🤪 {symbol}: Handing over to Crazy Rescue Scalper (> 72h)...")
                rescue_decision = self.rescue_scalper.get_exit_decision(symbol, analysis, profit_percent)
                
                if rescue_decision['action'] == 'SELL':
                    return {
                        'action': 'SELL',
                        'reason': rescue_decision['reason'],
                        'profit': profit_percent
                    }
                else:
                    return {
                        'action': 'HOLD',
                        'reason': rescue_decision['reason']
                    }
            else:
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
        if self.dl_client:
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
                
                sell_votes = self.dl_client.vote_sell_now(
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
        
        if self.dl_client:
            try:
                risk_vote = None
                if self.risk_manager:
                    try:
                        risk_vote = self.risk_manager.calculate_optimal_amount(symbol, confidence, 12, 20)
                    except:
                        pass
                
                amount_votes = self.dl_client.vote_amount(rsi, macd, volume_ratio, confidence, risk_vote)
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
