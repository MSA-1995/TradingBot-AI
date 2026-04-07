"""
Meta (The King) - The Ultimate Decision Maker
Now powered by trained Meta Model (Independent AI Learner)
"""
import pandas as pd
from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, MIN_CONFIDENCE, PEAK_DROP_THRESHOLD, BOTTOM_BOUNCE_THRESHOLD, VOLUME_SPIKE_FACTOR
from datetime import datetime
import gc
import psutil
import pickle
import os
import json
import numpy as np
from time import time

DB_LEARNING_KEY = 'king_learning_data'

class Meta:
    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager = advisor_manager
        self.storage = storage
        self.meta_model = None
        self.meta_model_accuracy = 0  # ✅ للتحقق من النموذج
        
        # ========== CACHE في الذاكرة ==========
        self._symbol_memory_cache = {}
        self._symbol_memory_cache_timestamp = 0
        self.CACHE_EXPIRATION_SECONDS = 1800  # تحديث الـ cache كل 30 دقيقة
        self._learning_data_cache = {}
        self._learning_data_cache_timestamp = 0
        
        self._load_meta_model_from_db()
        self._load_symbol_memory_cache()

        print("👑 Meta (The King) is initialized with trained Meta Model.")
    
    def is_meta_model_loaded(self):
        """✅ طريقة سريعة للتحقق: هل النموذج المتعلم محمل؟"""
        if self.meta_model is None:
            return False
        # الدقة قد تكون مخزنة كنسبة مئوية (75.0) أو كسر (0.75)
        acc = self.meta_model_accuracy
        normalized = acc / 100.0 if acc > 1.0 else acc
        return normalized > 0.5

    def _load_meta_model_from_db(self):
        """Loads the trained Meta Model from the database."""
        if not self.advisor_manager:
            return

        try:
            dl_client = self.advisor_manager.get('dl_client')
            if not dl_client:
                return

            # جلب النموذج المدرب (meta_model) من قاعدة البيانات
            model = dl_client._models.get('meta_trading')
            
            if model:
                self.meta_model = model
                # ✅ نفس الاسم للنموذج وللدقة
                self.meta_model_accuracy = dl_client._model_accuracy.get('meta_trading', 0)
            else:
                self.meta_model = None
                self.meta_model_accuracy = 0
        except Exception:
            self.meta_model = None
            self.meta_model_accuracy = 0
            print("   >> Falling back to Heuristic predictions...")

    def _load_symbol_memory_cache(self):
        """تحميل symbol_memory من DB مرة واحدة إلى الـ cache"""
        try:
            dl_client = self.advisor_manager.get('dl_client') if self.advisor_manager else None
            if dl_client and hasattr(dl_client, '_load_symbol_memory'):
                all_memory = dl_client._load_symbol_memory()
                self._symbol_memory_cache = all_memory
                self._symbol_memory_cache_timestamp = time()
                print(f"💾 Symbol Memory cached in RAM for {len(all_memory)} symbols")
            else:
                self._symbol_memory_cache = {}
        except Exception as e:
            print(f"⚠️ Error loading symbol memory cache: {e}")
            self._symbol_memory_cache = {}

    def _get_symbol_memory_cached(self, symbol):
        """جلب symbol_memory من الـ cache بدل DB - مع auto refresh"""
        current_time = time()
        
        # تحديث الـ cache إذا انتهت صلاحيته
        if (current_time - self._symbol_memory_cache_timestamp) > self.CACHE_EXPIRATION_SECONDS:
            self._load_symbol_memory_cache()
        
        return self._symbol_memory_cache.get(symbol, {})

    # _load_learning_data مُعرَّفة أسفل الملف (الإصدار الكامل مع storage)

    def _extract_meta_features(self, analysis_data, symbol=None):
        """
        استخراج نفس الـ features التي استخدمها meta_model في التدريب
        + symbol_memory من الـ CACHE (بدل DB)
        Returns: array of feature values matching meta_model training features
        """
        try:
            # ========== TECHNICAL INDICATORS ==========
            rsi = float(analysis_data.get('rsi', 50))
            # 🔧 macd_diff: fallback to 'macd' (training key)
            macd_diff = float(analysis_data.get('macd_diff', analysis_data.get('macd', 0)))
            # 🔧 volume_ratio: fallback to 'volume_spike' or 'vol_ratio'
            volume_ratio = float(analysis_data.get('volume_ratio',
                           analysis_data.get('volume_spike',
                           analysis_data.get('vol_ratio', 1.0))))
            price_momentum = float(analysis_data.get('price_momentum', 0))
            atr = float(analysis_data.get('atr', 0))

            # ========== NEWS DATA ==========
            # 🔧 'news_analysis' في inference ↔ 'news' في training
            news_data = analysis_data.get('news_analysis',
                        analysis_data.get('news', {}))
            if not isinstance(news_data, dict):
                news_data = {}
            # 🔧 'overall_score' في inference ↔ 'news_score' في training
            news_score = float(news_data.get('overall_score',
                         news_data.get('news_score', 0)))
            # 🔧 'positive_count' في inference ↔ 'positive' في training
            news_pos = float(news_data.get('positive_count',
                       news_data.get('positive', 0)))
            # 🔧 'negative_count' في inference ↔ 'negative' في training
            news_neg = float(news_data.get('negative_count',
                       news_data.get('negative', 0)))
            # 🔧 'total_articles' في inference ↔ 'total' في training
            news_total = float(news_data.get('total_articles',
                          news_data.get('total', 0)))
            news_ratio = news_pos / (news_neg + 0.001)
            has_news = 1 if news_total > 0 else 0

            # ========== SENTIMENT ==========
            sentiment = analysis_data.get('sentiment', {})
            if not isinstance(sentiment, dict):
                sentiment = {}
            # 🔧 'sentiment_score' في inference ↔ 'news_sentiment' في training
            sent_score = float(sentiment.get('sentiment_score',
                         sentiment.get('news_sentiment', 0)))
            fear_greed = float(sentiment.get('fear_greed_index', 50))
            fear_greed_norm = (fear_greed - 50) / 50
            is_fearful = 1 if fear_greed < 30 else 0
            is_greedy = 1 if fear_greed > 70 else 0

            # ========== LIQUIDITY ==========
            # 🔧 'liquidity_metrics' في inference ↔ 'liquidity' في training
            liquidity = analysis_data.get('liquidity_metrics',
                        analysis_data.get('liquidity', {}))
            if not isinstance(liquidity, dict):
                liquidity = {}
            liq_score = float(liquidity.get('liquidity_score', 50))
            depth_ratio = float(liquidity.get('depth_ratio', 1.0))
            price_impact = float(liquidity.get('price_impact', 0.5))
            good_liq = 1 if liq_score > 70 else 0

            # ========== MARKET CONDITIONS ==========
            # 🔧 'whale_confidence' في inference ↔ 'whale_activity' في training
            whale_activity = float(analysis_data.get('whale_confidence',
                             analysis_data.get('whale_activity', 0)))
            exchange_inflow = float(analysis_data.get('exchange_inflow', 0))
            social_volume = float(analysis_data.get('social_volume', 0))
            market_sentiment = float(analysis_data.get('market_sentiment', 0))

            # ========== CONSULTANT VOTES ==========
            buy_votes = analysis_data.get('buy_votes', {})
            sell_votes = analysis_data.get('sell_votes', {})
            buy_count = sum(1 for v in buy_votes.values() if v == 1) if buy_votes else 0
            sell_count = sum(1 for v in sell_votes.values() if v == 1) if sell_votes else 0
            # ✅ إصلاح: المستشارين الفعليين 5 (exit, risk, pattern, anomaly, liquidity)
            consensus = buy_count / 5.0

            # ========== SYMBOL MEMORY من CACHE (سريع جداً) ==========
            symbol_memory = {}
            if symbol:
                symbol_memory = self._get_symbol_memory_cached(symbol)
            
            # استخراج البيانات من الذاكرة
            sym_win_rate = float(symbol_memory.get('win_count', 0)) / max(float(symbol_memory.get('total_trades', 1)), 1)
            sym_avg_profit = float(symbol_memory.get('avg_profit', 0))
            sym_trap_count = float(symbol_memory.get('trap_count', 0))
            sym_total = float(symbol_memory.get('total_trades', 0))
            sym_is_reliable = 1 if (sym_win_rate > 0.6 and sym_total > 5) else 0
            
            # الأعمدة الجديدة
            sym_sentiment_avg = float(symbol_memory.get('sentiment_avg', 0))
            sym_whale_avg = float(symbol_memory.get('whale_confidence_avg', 0))
            sym_profit_loss_ratio = float(symbol_memory.get('profit_loss_ratio', 1.0))
            # 🔧 volume_trend قد يكون string ('neutral','up','down') أو float
            _vt = symbol_memory.get('volume_trend', 1.0)
            if isinstance(_vt, str):
                sym_volume_trend = 1.2 if _vt == 'up' else (0.8 if _vt == 'down' else 1.0)
            else:
                sym_volume_trend = float(_vt)
            sym_panic_avg = float(symbol_memory.get('panic_score_avg', 0))
            sym_optimism_avg = float(symbol_memory.get('optimism_penalty_avg', 0))
            
            # الـ 4 أعمدة الجديدة
            sym_courage_boost = float(symbol_memory.get('courage_boost', 0))
            sym_time_memory = float(symbol_memory.get('time_memory_modifier', 0))
            sym_pattern_score = float(symbol_memory.get('pattern_score', 0))
            sym_win_rate_boost = float(symbol_memory.get('win_rate_boost', 0))

            # ========== DERIVED FEATURES ==========
            risk_score = (whale_activity * 0.1 + (1 - liq_score/100) * 20 + news_neg * 5)
            opportunity = ((1 if rsi < 30 else 0) * 20 + news_pos * 5 + good_liq * 10 + buy_count * 5)
            market_quality = (liq_score / 100 + np.abs(news_ratio) / 10 + consensus) / 3
            momentum_strength = np.abs(price_momentum)
            volatility_level = float(analysis_data.get('volatility', 0))

            # ========== BUILD FEATURE VECTOR (must match meta_model training) ==========
            features = np.array([
                # Technical
                rsi, macd_diff, volume_ratio, price_momentum, atr,
                # News
                news_score, news_pos, news_neg, news_total, news_ratio, has_news,
                # Sentiment
                sent_score, fear_greed, fear_greed_norm, is_fearful, is_greedy,
                # Liquidity
                liq_score, depth_ratio, price_impact, good_liq,
                # Smart Money
                whale_activity, exchange_inflow,
                # Social
                social_volume, market_sentiment,
                # Consultants
                consensus, buy_count, sell_count,
                # Derived
                risk_score, opportunity, market_quality,
                momentum_strength, volatility_level,
                # Symbol Memory (الأساسي)
                sym_win_rate, sym_avg_profit, sym_trap_count, sym_total, sym_is_reliable,
                # Symbol Memory (أعمدة جديدة - الـ 7)
                sym_sentiment_avg, sym_whale_avg, sym_profit_loss_ratio, sym_volume_trend,
                sym_panic_avg, sym_optimism_avg,
                # Symbol Memory (أعمدة جديدة - الـ 4)
                sym_courage_boost, sym_time_memory, sym_pattern_score, sym_win_rate_boost,
                # Context
                0  # hours_held placeholder
            ]).reshape(1, -1)
            
            return features
        except Exception as e:
            print(f"⚠️ Meta: Error extracting features: {e}")
            return None

    def _heuristic_meta_prediction(self, analysis_data, symbol=None):
        """
        Fallback: حساب meta prediction من rules بدون ML
        يحسب score من الـ indicators الموجودة
        """
        try:
            # التقنية
            rsi = float(analysis_data.get('rsi', 50))
            # 🔧 fallback keys
            macd_diff = float(analysis_data.get('macd_diff', analysis_data.get('macd', 0)))
            volume_ratio = float(analysis_data.get('volume_ratio',
                           analysis_data.get('volume_spike',
                           analysis_data.get('vol_ratio', 1.0))))
            price_momentum = float(analysis_data.get('price_momentum', 0))
            
            # الأخبار - 🔧 fallback keys
            news_data = analysis_data.get('news_analysis',
                        analysis_data.get('news', {}))
            if not isinstance(news_data, dict):
                news_data = {}
            news_pos = float(news_data.get('positive_count',
                       news_data.get('positive', 0)))
            news_neg = float(news_data.get('negative_count',
                       news_data.get('negative', 0)))
            
            # السنتيمنت - 🔧 fallback keys
            sentiment = analysis_data.get('sentiment', {})
            if not isinstance(sentiment, dict):
                sentiment = {}
            fear_greed = float(sentiment.get('fear_greed_index', 50))
            
            # الـ votes من الـ consultants
            buy_votes = analysis_data.get('buy_votes', {})
            # ✅ إصلاح: المستشارين الفعليين 5
            consensus = sum(1 for v in buy_votes.values() if v == 1) / 5.0 if buy_votes else 0
            
            # ذاكرة الـ symbol
            symbol_memory = {}
            if symbol:
                symbol_memory = self._get_symbol_memory_cached(symbol)
            sym_win_rate = float(symbol_memory.get('win_count', 0)) / max(float(symbol_memory.get('total_trades', 1)), 1)
            
            # ========== HEURISTIC FORMULA ==========
            # تجميع من أفضل predictors (تم اختيارهم من feature importance)
            score = 0.5  # baseline
            
            # Technical (30%)
            if rsi < 30:
                score += 0.12  # oversold
            elif rsi > 70:
                score -= 0.08  # overbought
            
            if macd_diff > 0:
                score += 0.10  # positive momentum
            
            if price_momentum > 0.01:
                score += 0.08
                
            # News (20%)
            news_ratio = news_pos / (news_neg + 0.001)
            if news_ratio > 1.2:
                score += 0.10
            elif news_ratio < 0.8:
                score -= 0.08
            
            # Sentiment (15%)
            if fear_greed < 30:
                score += 0.10  # fear = buying opportunity
            elif fear_greed > 80:
                score -= 0.08
            
            # Consensus (20%)
            score += (consensus * 0.15)
            
            # Symbol Memory (15%)
            if sym_win_rate > 0.65:
                score += 0.08
            elif sym_win_rate < 0.35:
                score -= 0.05
            
            # Normalize between 0-1
            score = max(0, min(1, score))
            return score
        except Exception as e:
            print(f"⚠️ Heuristic Meta prediction error: {e}")
            return 0.5  # neutral fallback

    def _get_meta_model_prediction(self, analysis_data, symbol=None):
        """
        استخدام النموذج المدرب للتنبؤ بـ BUY
        + ذاكرة الرمز (symbol_memory)
        + Heuristic Fallback إذا مافي ML model
        """
        # استخدم heuristic إذا مافي model
        if not self.meta_model:
            return self._heuristic_meta_prediction(analysis_data, symbol=symbol)

        try:
            features = self._extract_meta_features(analysis_data, symbol=symbol)
            if features is None:
                return self._heuristic_meta_prediction(analysis_data, symbol=symbol)

            # ✅ DataFrame الأصلي - يشتغل بسرعة عادية
            feature_names = [
                'rsi', 'macd_diff', 'volume_ratio', 'price_momentum', 'atr',
                'news_score', 'news_pos', 'news_neg', 'news_total', 'news_ratio', 'has_news',
                'sent_score', 'fear_greed', 'fear_greed_norm', 'is_fearful', 'is_greedy',
                'liq_score', 'depth_ratio', 'price_impact', 'good_liq',
                'whale_activity', 'exchange_inflow',
                'social_volume', 'market_sentiment',
                'consensus', 'buy_count', 'sell_count',
                'risk_score', 'opportunity', 'market_quality', 'momentum_strength', 'volatility_level',
                'sym_win_rate', 'sym_avg_profit', 'sym_trap_count', 'sym_total', 'sym_is_reliable',
                'sym_sentiment_avg', 'sym_whale_avg', 'sym_profit_loss_ratio', 'sym_volume_trend',
                'sym_panic_avg', 'sym_optimism_avg',
                'sym_courage_boost', 'sym_time_memory', 'sym_pattern_score', 'sym_win_rate_boost',
                'hours_held'
            ]
            X = pd.DataFrame(features, columns=feature_names)
            
            probabilities = self.meta_model.predict_proba(X)
            buy_probability = float(probabilities[0][1])  # احتمالية الـ BUY (فئة 1)
            
            return buy_probability
        except Exception as e:
            print(f"⚠️ Meta Model prediction error: {e}")
            # Fallback إلى heuristic في حالة الخطأ
            return self._heuristic_meta_prediction(analysis_data, symbol=symbol)

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
    def _get_courage_boost(self, symbol, rsi, volume_ratio, _ld=None):
        """لو البوت نجح قبل بنفس الظروف → يجرؤ أكثر ويرفع الثقة"""
        try:
            data = _ld if _ld is not None else self._load_learning_data()
            courage_record = data.get('courage_record', [])

            similar_wins = [
                r for r in courage_record
                if r.get('symbol') == symbol
                and abs(r.get('rsi', 50) - rsi) < 12
                and abs(r.get('volume_ratio', 1.0) - volume_ratio) < 0.5
                and r.get('profit', 0) > 0.5
            ]

            if len(similar_wins) >= 3:
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
    def _get_time_memory_modifier(self, symbol, _ld=None):
        """يتذكر الأوقات الناجحة والخاسرة لكل عملة ويعدّل الثقة"""
        try:
            data = _ld if _ld is not None else self._load_learning_data()
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
    def _get_symbol_pattern_score(self, symbol, rsi, macd_diff, volume_ratio, _ld=None):
        """يبحث في الصفقات الناجحة السابقة عن نمط مشابه ويرفع الثقة"""
        try:
            data = _ld if _ld is not None else self._load_learning_data()
            patterns = data.get('successful_patterns', [])

            symbol_patterns = [p for p in patterns if p.get('symbol') == symbol]
            if len(symbol_patterns) < 4:
                return 0, ""  # ما في بيانات كافية بعد

            matches = [
                p for p in symbol_patterns
                if abs(p.get('rsi', 50) - rsi) < 10
                and abs(p.get('volume_ratio', 1.0) - volume_ratio) < 0.5
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
    def _get_symbol_win_rate_boost(self, symbol, _ld=None):
        """لو العملة سجلها ناجح تاريخياً → يضيف ثقة إضافية"""
        try:
            data = _ld if _ld is not None else self._load_learning_data()
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
        macd_diff = analysis_data.get('macd_diff', analysis_data.get('macd', 0))  # 🔧 fallback
        volume_ratio = analysis_data.get('volume_ratio',
                       analysis_data.get('volume_spike',
                       analysis_data.get('vol_ratio', 1.0)))  # 🔧 fallback
        ema_crossover = analysis_data.get('ema_crossover', 0)

        # 🚨 فحص RSI أولاً - إذا تشبع شرائي جداً (>85) لا تشتري!
        if rsi > 85:
            return {
                'action': 'DISPLAY',
                'reason': f'🚫 RSI Extremely Overbought ({rsi:.0f}) - No Buy',
                'confidence': 0,
                'rsi': rsi
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
        # 🧠 الذاكرة الذكية — تحميل مرة واحدة فقط (بدل 4 استدعاءات)
        # =========================================================
        _cached_ld = self._load_learning_data()

        # 💪 1. الجرأة الديناميكية
        courage_boost = self._get_courage_boost(symbol, rsi, volume_ratio, _ld=_cached_ld)
        if courage_boost > 0:
            temp_conf += courage_boost
            reasons.append(f"CourageBoost(+{courage_boost:.0f})")

        # ⏰ 2. ذاكرة الوقت
        time_mod, time_label = self._get_time_memory_modifier(symbol, _ld=_cached_ld)
        if time_mod != 0:
            temp_conf += time_mod
            reasons.append(time_label)

        # 🔁 3. ذاكرة الأنماط
        pattern_boost, pattern_label = self._get_symbol_pattern_score(symbol, rsi, macd_diff, volume_ratio, _ld=_cached_ld)
        if pattern_boost > 0:
            temp_conf += pattern_boost
            reasons.append(pattern_label)

        # 🏆 4. معدل نجاح العملة
        win_boost, win_label = self._get_symbol_win_rate_boost(symbol, _ld=_cached_ld)
        if win_boost != 0:
            temp_conf += win_boost
            reasons.append(win_label)

        # =========================================================
        # 👑 5. النموذج الذكي المتعلم — هو القرار الكامل (Meta = King)
        # =========================================================
        meta_model_probability = self._get_meta_model_prediction(analysis_data, symbol=symbol)
        if meta_model_probability is None:
            meta_model_probability = 0.5  # neutral fallback

        # يعزز الثقة أيضاً (0-30 نقطة)
        meta_boost = meta_model_probability * 30
        temp_conf += meta_boost
        reasons.append(f"MetaModel({meta_model_probability*100:.0f}%,+{meta_boost:.0f})")

        # إشارة الشمعة الانعكاسية تضيف ثقة إضافية (لكنها لم تعد البوابة الوحيدة)
        candle_score = reversal.get('confidence', 0)
        if reversal.get('candle_signal', False):
            temp_conf += 12
            reasons.append(f"CandleReversal(+12)")
        elif candle_score >= MIN_CONFIDENCE:
            temp_conf += 7
            reasons.append(f"BottomScore({candle_score:.0f},+7)")
        elif volume_ratio >= 2.0 and reversal.get('is_reversing', False):
            temp_conf += 5
            reasons.append(f"VolReversal(+5)")

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

            # جلب التصويت من كل مستشار
            market_sentiment = analysis_data.get('market_sentiment', None)
            buy_votes, market_status = dl_client.vote_buy_now(
                rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                price_momentum=analysis_data.get('price_momentum', 0),
                confidence=temp_conf,
                liquidity_metrics=analysis_data.get('liquidity_metrics'),
                market_sentiment=market_sentiment,
                candle_analysis=candle_analysis
            )

            if buy_votes:
                total_advisors = len(buy_votes)
                buy_vote_count = sum(1 for v in buy_votes.values() if v == 1)
                vote_breakdown = buy_votes
            else:
                total_advisors = 0
                buy_vote_count = 0
                vote_breakdown = {}

            # ✅ إصلاح: نستخدم min_votes_needed من mood_details (3/4/5) بدل القيمة الثابتة
            votes_required = mood_details.get('min_votes_needed', 4)

            #print(f"✅ Votes: {buy_vote_count}/{total_advisors} (Need {votes_required}) | ⚪ Market: {market_status}")

            if buy_vote_count < votes_required:
              return {
                    'action': 'DISPLAY',
                    'reason': f'Score:{temp_conf:.0f}/99 | Votes:{buy_vote_count}/{votes_required} | {market_status}',
                    'votes': buy_votes,
                    'confidence': temp_conf
                }
        except Exception as e:
            print(f"⚠️ Buy voting error [{symbol}]: {e}")

        # 🔄 Fallback: إذا فشل التصويت، الملك يقرر بناءً على الثقة وحده
        if total_advisors == 0:
            fallback_votes = 0
            if temp_conf >= MIN_CONFIDENCE + 20: fallback_votes = 5
            elif temp_conf >= MIN_CONFIDENCE + 10: fallback_votes = 4
            elif temp_conf >= MIN_CONFIDENCE:     fallback_votes = 3
            elif temp_conf >= MIN_CONFIDENCE - 8: fallback_votes = 2  # ✅ متوسط
            buy_vote_count = fallback_votes
            total_advisors = 5
            vote_breakdown = {'king_fallback': fallback_votes}

        # =========================================================
        # 👑 6. الملك يقرر — بناءً على النموذج الذكي المتعلم
        # =========================================================
        min_votes_needed = mood_details.get('min_votes_needed', 4)
        effective_total = mood_details.get('total_advisors', 5)
        
        # النموذج الذكي هو القرار الكامل (threshold: 50% = محايد، 60% = واثق)
        king_wants_to_buy = meta_model_probability >= 0.50
        king_reason = f"MetaModel({meta_model_probability*100:.0f}%)"
        
        # في سوق هابط — اشترط ثقة أعلى من النموذج
        if market_mood == "Bearish" and meta_model_probability < 0.65:
            king_wants_to_buy = False
            king_reason = f"MetaModel low in Bearish({meta_model_probability*100:.0f}%<65%)"
        
        # =========================================================
        # 🗳️ 7. التصويت بعد قرار الملك الذكي
        # =========================================================
        if king_wants_to_buy and market_mood != "Bearish":
            if buy_vote_count >= min_votes_needed:
                action = "BUY"
                reason = f"BUY ✅ | MetaModel:{meta_model_probability*100:.0f}% | Confidence:{temp_conf:.0f} | Votes:{buy_vote_count}/{min_votes_needed} | {', '.join(reasons[:3])}"
            else:
                action = "DISPLAY"
                market_emoji = "🟢" if market_mood == "Bullish" else "⚪"
                reason = f"MetaModel:{meta_model_probability*100:.0f}% | Confidence:{temp_conf:.0f}/{MIN_CONFIDENCE} | Votes:{buy_vote_count}/{min_votes_needed} (Need {min_votes_needed}) | {market_emoji} Market: {market_mood}"
        elif king_wants_to_buy and market_mood == "Bearish":
            # سوق هابط: النموذج واثق (>=65%) + 5/5 أصوات + إشارة شمعية
            if buy_vote_count >= 5 and reversal.get('candle_signal', False) and meta_model_probability >= 0.65:
                action = "BUY"
                reason = f"BUY (Bearish Override) ✅ | MetaModel:{meta_model_probability*100:.0f}% | Votes:5/5"
            elif rsi <= 28 and buy_vote_count >= 4 and meta_model_probability >= 0.70:
                action = "BUY"
                reason = f"BUY (Deep Oversold) ✅ | RSI:{rsi:.0f} | MetaModel:{meta_model_probability*100:.0f}% | Votes:{buy_vote_count}/4"
            else:
                action = "DISPLAY"
                reason = f"Bearish | MetaModel:{meta_model_probability*100:.0f}% | Votes:{buy_vote_count}/5 | Need MetaModel>=65%+5/5"
        else:
            market_emoji = "🟢" if market_mood == "Bullish" else "🔴" if market_mood == "Bearish" else "⚪"
            reason = f"MetaModel LOW:{meta_model_probability*100:.0f}%(<50%) | Confidence:{temp_conf:.0f} | {market_emoji} Market: {market_mood}"

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
        
        # خطر حرج أو عالي - بيع الكل فوراً (مع شرط ربح لتجنب البيع المبكر)
        if flash_risk >= 40 and profit_percent > 1.0:
            return {
                'action': 'SELL',
                'reason': f'🚨 Flash Risk ({flash_risk}%) - Emergency Sell',
                'profit': profit_percent,
                'flash_risk': flash_risk
            }
        
        mood_details = self._get_market_mood(analysis)

        # استخراج المؤشرات مبكراً
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', analysis.get('macd', 0))  # 🔧 fallback
        volume_ratio = analysis.get('volume_ratio',
                       analysis.get('volume_spike',
                       analysis.get('vol_ratio', 1.0)))  # 🔧 fallback
        ema_crossover = analysis.get('ema_crossover', 0)
        price_momentum = analysis.get('price_momentum', 0)
        liquidity_metrics = analysis.get('liquidity_metrics',
                            analysis.get('liquidity', {}))  # 🔧 fallback
        peak_analysis = analysis.get('peak', {})
        peak_score = peak_analysis.get('confidence', 0)
        candle_condition = peak_analysis.get('candle_signal', False)

        sell_conf = 20
        sell_reasons = []

        # =========================================================
        # 👑 2. النموذج الذكي المتعلم — هو الملك الكامل للبيع
        # =========================================================
        # النموذج يتنبأ باحتمالية الشراء (0-1)
        # احتمالية منخفضة = السوق مو مناسب للشراء = وقت البيع
        sell_meta_probability = self._get_meta_model_prediction(analysis, symbol=symbol)
        if sell_meta_probability is None:
            sell_meta_probability = 0.5  # neutral fallback

        # تحويل احتمالية الشراء إلى إشارة بيع (عكسية)
        sell_signal_strength = 1.0 - sell_meta_probability  # كلما انخفضت احتمالية الشراء، قوي إشارة البيع

        # النموذج يعزز sell_conf (0-30 نقطة)
        meta_sell_boost = sell_signal_strength * 30
        sell_conf += meta_sell_boost
        sell_reasons.append(f"MetaModel(BuyProb:{sell_meta_probability*100:.0f}%,SellBoost:+{meta_sell_boost:.0f})")

        # الشمعة وإشارة القمة تضيف ثقة إضافية (لكنها لم تعد البوابة)
        if candle_condition:
            sell_conf += 15
            sell_reasons.append(f"CandlePeak(+15)")
        elif peak_score >= MIN_SELL_CONFIDENCE:
            sell_conf += 8
            sell_reasons.append(f"PeakScore({peak_score:.0f},+8)")

        # =========================================================
        # 👑 قرار الملك: هل نبيع؟ (النموذج هو المتحكم الكامل)
        # =========================================================
        # سوق صاعد: يشترط إشارة بيع أقوى (احتمالية شراء < 45%)
        # سوق محايد: احتمالية شراء < 50%
        # سوق هابط: احتمالية شراء < 55% (أسهل بيع في الهابط)
        market_mood = mood_details['mood']
        if market_mood == 'Bullish':
            sell_threshold = 0.45
        elif market_mood == 'Bearish':
            sell_threshold = 0.55
        else:
            sell_threshold = 0.50

        king_wants_to_sell = sell_meta_probability <= sell_threshold
        king_sell_reason = f"MetaModel({sell_meta_probability*100:.0f}%<={sell_threshold*100:.0f}%)"

        if not king_wants_to_sell:
            return {
                'action': 'HOLD',
                'reason': f'MetaModel HIGH:{sell_meta_probability*100:.0f}%(>{sell_threshold*100:.0f}%) — Hold | Score:{sell_conf:.0f}',
                'profit': profit_percent
            }

        # --- ✅ الحد الأدنى للربح (بعد قرار الملك)
        if profit_percent < 0.5:
            return {'action': 'HOLD', 'reason': f'Waiting for +0.5% min profit | MetaModel:{sell_meta_probability*100:.0f}%', 'profit': profit_percent}

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

        if rsi >= 75:              # ✅ متوسط: أضفنا نطاق عالي جداً
            sell_conf += 28
            sell_reasons.append(f"RSI Very High ({rsi:.0f})")
        elif rsi >= 70:            # ✅ متوسط: خففنا من 72 إلى 70
            sell_conf += 22
            sell_reasons.append(f"RSI High ({rsi:.0f})")
        elif rsi >= 65:            # ✅ متوسط: خففنا من 68 إلى 65
            sell_conf += 12
            sell_reasons.append(f"RSI Elevated ({rsi:.0f})")

        if macd_diff < -0.5:       # ✅ متوسط: خففنا من -1.0 إلى -0.5
            sell_conf += 15
            sell_reasons.append("MACD Bearish")
        elif macd_diff < 0:        # ✅ متوسط: حتى MACD سالب بسيط يضيف نقاط
            sell_conf += 7
            sell_reasons.append("MACD Negative")

        if volume_ratio < 0.7:     # ✅ متوسط: خففنا من 0.5 إلى 0.7
            sell_conf += 12
            sell_reasons.append(f"Vol Low ({volume_ratio:.1f}x)")
        elif volume_ratio < 0.9:
            sell_conf += 6
            sell_reasons.append(f"Vol Declining ({volume_ratio:.1f}x)")

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
                
                # بناء market_sentiment و candle_analysis من البيانات الموجودة
                market_sentiment = {
                    'btc_change_1h': analysis.get('btc_change_1h', 0),
                    'eth_change_1h': analysis.get('eth_change_1h', 0),
                    'bnb_change_1h': analysis.get('bnb_change_1h', 0),
                }
                reversal = analysis.get('reversal', {})
                peak = analysis.get('peak', {})
                candle_analysis = {
                    'is_reversal': reversal.get('candle_signal', False),
                    'is_bottom':   reversal.get('candle_signal', False),
                    'is_peak':     peak.get('candle_signal', False),
                    'is_rejection': peak.get('candle_signal', False),
                    'reversal_confidence': reversal.get('confidence', 0),
                    'peak_confidence':     peak.get('confidence', 0),
                }

                # جلب التصويت من كل مستشار
                sell_votes, market_status = dl_client.vote_sell_now(
                    rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                    price_momentum=price_momentum, liquidity_metrics=liquidity_metrics,
                    market_sentiment=market_sentiment,
                    candle_analysis=candle_analysis
                )
                
                if sell_votes:
                    total_advisors = len(sell_votes)
                    sell_vote_count = sum(1 for v in sell_votes.values() if v == 1)
                    vote_breakdown = sell_votes
                else:
                    total_advisors = 0
                    sell_vote_count = 0
                    vote_breakdown = {}
        except Exception as e:
            print(f"⚠️ Meta sell voting error [{symbol}]: {e}")

        # 🔄 Fallback: إذا فشل التصويت في البيع، الملك يقرر بناءً على النقاط وحده
        if total_advisors == 0:
            fallback_votes = 0
            if sell_conf >= MIN_SELL_CONFIDENCE + 20: fallback_votes = 5
            elif sell_conf >= MIN_SELL_CONFIDENCE + 10: fallback_votes = 4
            elif sell_conf >= MIN_SELL_CONFIDENCE:     fallback_votes = 3
            elif sell_conf >= MIN_SELL_CONFIDENCE - 8: fallback_votes = 2  # ✅ متوسط
            sell_vote_count = fallback_votes
            total_advisors = 5
            vote_breakdown = {'king_fallback': fallback_votes}

        # --- 4. القرار الملكي النهائي: النموذج + النقاط + التصويت ---
        # ✅ للبيع: النسب عكسية الشراء
        # Bullish → صعب بيع (5/5) | Neutral → متوسط (4/5) | Bearish → سهل بيع (3/5)
        market_mood_for_sell = mood_details.get('mood', 'Neutral')
        if market_mood_for_sell == 'Bullish':
            min_votes_needed = 5   # سوق صاعد: يلزم 5/5 للبيع (صعب)
        elif market_mood_for_sell == 'Bearish':
            min_votes_needed = 3   # سوق هابط: يكفي 3/5 للبيع (سهل)
        else:
            min_votes_needed = 4   # محايد: 4/5
        
        if sell_vote_count >= min_votes_needed and sell_conf >= MIN_SELL_CONFIDENCE:
            action = 'SELL'
            reason = f"SELL ✅ | MetaModel:{sell_meta_probability*100:.0f}% | Score:{sell_conf:.0f} | Votes:{sell_vote_count}/{min_votes_needed} | {', '.join(sell_reasons[:3])}"
        elif vote_breakdown.get('king_fallback', 0) >= min_votes_needed and sell_conf >= MIN_SELL_CONFIDENCE:
            action = 'SELL'
            reason = f"SELL (King) ✅ | MetaModel:{sell_meta_probability*100:.0f}% | Score:{sell_conf:.0f} | {', '.join(sell_reasons[:3])}"
        else:
            action = 'HOLD'
            reason = f"Hold | MetaModel:{sell_meta_probability*100:.0f}% | Score:{sell_conf:.0f} | Votes:{sell_vote_count}/{min_votes_needed}"

        # تجنب التفاؤل في should_sell (أقل صرامة)
        if profit_percent > 15:
            reason += " | Optimism Warning"

        return {'action': action, 'reason': reason, 'profit': profit_percent, 'sell_votes': vote_breakdown}

    def _get_market_mood(self, analysis):
        """
        يحدد حالة السوق بناءً على تغير BTC خلال ساعة.
        - Bullish  : btc_change > +1%  → يكفي 3/5 أصوات للشراء
        - Bearish  : btc_change < -1%  → يلزم 5/5 أصوات للشراء
        - Neutral  : بين -1% و +1%    → يلزم 4/5 أصوات للشراء
        """
        btc_change = analysis.get('btc_change_1h', 0) if analysis else 0

        mood_details = {}
        if btc_change > 1.0:
            mood_details['mood'] = "Bullish"
            mood_details['min_votes_needed'] = 3   # 3/5 - سوق صاعد
            mood_details['total_advisors'] = 5
        elif btc_change < -1.0:
            mood_details['mood'] = "Bearish"
            mood_details['min_votes_needed'] = 5   # 5/5 - سوق هابط
            mood_details['total_advisors'] = 5
        else:
            mood_details['mood'] = "Neutral"
            mood_details['min_votes_needed'] = 4   # 4/5 - سوق محايد
            mood_details['total_advisors'] = 5

        return mood_details

    def _calculate_smart_amount(self, symbol, confidence, analysis):
        """حساب المبلغ الذكي بالتصويت من المستشارين + Risk Manager"""
        rsi = analysis.get('rsi', 50)
        macd = analysis.get('macd_diff', analysis.get('macd', 0))  # 🔧 fallback
        volume_ratio = analysis.get('volume_ratio',
                       analysis.get('volume_spike',
                       analysis.get('vol_ratio', 1.0)))  # 🔧 fallback
        
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
    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, symbol=None, position=None):
        """التعلم المباشر من كل صفقة - يحفظ في الداتابيز"""
        try:
            # تحميل البيانات من الداتابيز
            data = self._load_learning_data()

            # استخراج البيانات الحقيقية من الـ position
            rsi = position.get('buy_rsi', 50) if position else 50
            volume_ratio = position.get('buy_volume_ratio', 1.0) if position else 1.0
            macd_diff = position.get('buy_macd_diff', 0) if position else 0
            buy_confidence = position.get('buy_confidence', 50) if position else 50
            current_hour = datetime.now().hour
            hour_key = str(current_hour)

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

            # حفظ في ذاكرة الملك
            self._update_symbol_memory(symbol)
            
            # ✅ حفظ النمط في جدول الانماط المتعلمة
            try:
                # حفظ نمط النجاح أو الفشل
                pattern_type = 'SUCCESS' if trade_quality in ['GREAT', 'GOOD', 'OK'] else 'TRAP'
                pattern_data = {
                    'type': pattern_type,
                    'success_rate': 1.0 if trade_quality == 'GREAT' else (0.7 if trade_quality == 'GOOD' else 0.5 if trade_quality == 'OK' else 0.0),
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
        """تحميل بيانات التعلم من الداتابيز — مع cache 10 دقائق"""
        current_time = time()
        if (current_time - self._learning_data_cache_timestamp) < 600:
            return self._learning_data_cache

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
                    for key, val in default.items():
                        if key not in loaded:
                            loaded[key] = val
                    self._learning_data_cache = loaded
                    self._learning_data_cache_timestamp = current_time
                    return self._learning_data_cache
        except:
            pass
        # Fallback: قراءة من الملف المحلي لو موجود
        try:
            local_file = 'data/king_learning.json'
            if os.path.exists(local_file):
                with open(local_file, 'r') as f:
                    file_data = json.load(f)
                    self._save_learning_data(file_data)
                    print("✅ Migrated king_learning.json to database")
                    self._learning_data_cache = file_data
                    self._learning_data_cache_timestamp = current_time
                    return self._learning_data_cache
        except:
            pass
        self._learning_data_cache = default
        self._learning_data_cache_timestamp = current_time
        return self._learning_data_cache

    def _save_learning_data(self, data):
        """حفظ بيانات التعلم في الداتابيز + تحديث الـ cache مباشرة"""
        try:
            if self.storage:
                self.storage.save_setting(DB_LEARNING_KEY, json.dumps(data))
            # ✅ تحديث الـ cache مباشرة بعد الحفظ (بدل انتظار 10 دقائق)
            self._learning_data_cache = data
            self._learning_data_cache_timestamp = time()
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
        """تحديث ذاكرة الملك للعملة — بيانات حقيقية من learning_data"""
        try:
            data = self._load_learning_data()

            # ===== حساب win_rate الحقيقي =====
            wr = data.get('symbol_win_rate', {}).get(symbol, {})
            wins  = wr.get('wins', 0)
            total = wr.get('total', 0)
            win_rate = wins / total if total > 0 else 0.0

            # ===== حساب avg_profit من الأنماط الناجحة =====
            sym_patterns = [p for p in data.get('successful_patterns', []) if p.get('symbol') == symbol]
            avg_profit = (sum(p.get('profit', 0) for p in sym_patterns) / len(sym_patterns)) if sym_patterns else 0.0

            # ===== حساب trap_count من error_history =====
            trap_count = sum(
                1 for e in data.get('error_history', [])
                if e.get('symbol') == symbol and e.get('reason') == 'trap'
            )

            # ===== profit_loss_ratio =====
            losses = [p for p in data.get('error_history', []) if p.get('symbol') == symbol]
            profit_loss_ratio = (len(sym_patterns) / len(losses)) if losses else float(len(sym_patterns))
            profit_loss_ratio = round(min(profit_loss_ratio, 10.0), 2)

            # ===== courage_boost من آخر courage_record =====
            courage_records = [r for r in data.get('courage_record', []) if r.get('symbol') == symbol]
            courage_boost = 0.0
            if len(courage_records) >= 2:
                avg_c = sum(r.get('profit', 0) for r in courage_records[-5:]) / min(len(courage_records), 5)
                courage_boost = round(min(avg_c * 1.5, 15.0), 2)

            # ===== pattern_score =====
            pattern_score = round(min(avg_profit * 2.0, 14.0), 2) if len(sym_patterns) >= 3 else 0.0

            # ===== win_rate_boost =====
            win_rate_boost = 0.0
            if total >= 5:
                if win_rate >= 0.80:   win_rate_boost = 10.0
                elif win_rate >= 0.65: win_rate_boost = 5.0
                elif win_rate < 0.35:  win_rate_boost = -8.0

            memory_data = {
                'win_count':           wins,
                'total_trades':        total,
                'avg_profit':          round(avg_profit, 3),
                'trap_count':          trap_count,
                'profit_loss_ratio':   profit_loss_ratio,
                'volume_trend':        1.0,
                'sentiment_avg':       0.0,
                'whale_confidence_avg': 0.0,
                'panic_score_avg':     0.0,
                'optimism_penalty_avg': 0.0,
                'courage_boost':       courage_boost,
                'time_memory_modifier': 0.0,
                'pattern_score':       pattern_score,
                'win_rate_boost':      win_rate_boost,
                'psychological_summary': f'WR:{win_rate*100:.0f}% T:{total} P:{avg_profit:.1f}%'
            }

            if hasattr(self.storage, 'save_symbol_memory'):
                self.storage.save_symbol_memory(symbol, memory_data)

            # تحديث الـ cache مباشرة بعد الحفظ
            self._symbol_memory_cache[symbol] = memory_data

        except Exception as e:
            print(f"⚠️ _update_symbol_memory error [{symbol}]: {e}")
