"""
🧠 Deep Learning Client V3 - للبوت الرئيسي
يحمل موديلات LightGBM المدربة من قاعدة البيانات ويستخدمها للتصويت
"""
import os
import sys
import json
import pickle
import gzip
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

# إضافة مسار memory للكاش المضغوط
try:
    memory_path = os.path.join(os.path.dirname(parent_dir), 'memory')
    if os.path.exists(memory_path) and memory_path not in sys.path:
        sys.path.insert(0, memory_path)
    from memory_cache import MemoryCache
except Exception:
    MemoryCache = None

# إضافة مسار MSA-DeepLearning-Trainer إلى sys.path
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    trainer_path = os.path.join(os.path.dirname(parent_dir), 'MSA-DeepLearning-Trainer')
    if os.path.exists(trainer_path) and trainer_path not in sys.path:
        sys.path.insert(0, trainer_path)
except Exception:
    pass

class DeepLearningClientV2:
    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = None
        self._db_params = None
        self._pool = None
        self._models = MemoryCache(max_items=20) if MemoryCache else {}
        self._model_accuracy = {}
        self._model_trained_at = {}
        self._feature_names = {}
        try:
            self._connect_db()
            self._load_all_models_from_db()
            self._print_models_status()
        except Exception as e:
            raise
    
    def _connect_db(self):
        from psycopg2.pool import ThreadedConnectionPool
        try:
            parsed = urlparse(self.database_url)
            password = unquote(parsed.password) if parsed.password else None
            self._db_params = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path[1:],
                'user': parsed.username,
                'password': password,
                'sslmode': 'require',
                'connect_timeout': 15,
                'keepalives': 1,
                'keepalives_idle': 60,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            }
            self._pool = ThreadedConnectionPool(3, 12, **self._db_params)
            conn = self._pool.getconn()
            self.conn = conn
            self._pool.putconn(conn)
        except Exception as e:
            print(f"⚠️ DL Client V2 DB error: {e}")
            self.conn = None
            self._pool = None

    def _get_conn(self):
        try:
            if self._pool:
                conn = self._pool.getconn()
                if conn and not conn.closed:
                    return conn
                try:
                    self._pool.putconn(conn, close=True)
                except Exception:
                    pass
            if self._db_params:
                return psycopg2.connect(**self._db_params)
            return None
        except Exception as e:
            print(f"⚠️ DL Client V2 reconnect error: {e}")
            return None

    def _return_conn(self, conn):
        try:
            if self._pool and conn:
                self._pool.putconn(conn)
        except Exception:
            pass
    
    def get_model_data(self, model_name):
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return None
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT model_data
                FROM dl_models_v2
                WHERE model_name = %s
                ORDER BY trained_at DESC
                LIMIT 1
            """, (model_name,))
            result = cursor.fetchone()
            cursor.close()
            self._return_conn(conn)
            conn = None
            if result and result.get('model_data'):
                return result['model_data']
            else:
                return None
        except Exception:
            if conn:
                try:
                    self._pool.putconn(conn, close=True) if self._pool else conn.close()
                except Exception:
                    pass
            return None

    def _load_single_model(self, name):
        import time
        max_retries = 3
        for attempt in range(max_retries):
            conn = None
            try:
                if self._db_params is None:
                    return
                _params = self._db_params.copy()
                _params['keepalives'] = 1
                _params['keepalives_idle'] = 5
                _params['keepalives_interval'] = 1
                _params['keepalives_count'] = 3
                conn = psycopg2.connect(**_params)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SET statement_timeout = '300s'")
                cursor.execute("SET tcp_user_timeout = '120s'")
                cursor.execute("""
                    SELECT accuracy, trained_at, model_data,
                           octet_length(model_data) as data_size
                    FROM dl_models_v2
                    WHERE TRIM(LOWER(model_name)) = TRIM(LOWER(%s))
                    ORDER BY trained_at DESC
                    LIMIT 1
                """, (name,))
                result = cursor.fetchone()
                if not result:
                    cursor.close()
                    conn.close()
                    return
                db_acc = result.get('accuracy')
                self._model_accuracy[name] = float(db_acc) if db_acc is not None else 0.0
                self._model_trained_at[name] = str(result.get('trained_at') or 'N/A')
                if result.get('model_data'):
                    raw_data = result['model_data']
                    if isinstance(raw_data, memoryview):
                        raw_data = bytes(raw_data)
                    try:
                        if raw_data.startswith(b'\x1f\x8b'):
                            model_obj = pickle.loads(gzip.decompress(raw_data))
                        else:
                            model_obj = pickle.loads(raw_data)
                        if MemoryCache:
                            self._models.set(name, model_obj, expiry_seconds=3600)  # كاش مضغوط لساعة
                        else:
                            self._models[name] = model_obj

                        # تنظيف الذاكرة فوري بعد التحميل لتوفير المساحة
                        import gc
                        gc.collect()
                        try:
                            from MSA_DeepLearning_Trainer.core.features import get_feature_names
                            self._feature_names[name] = get_feature_names()
                        except ImportError:
                            self._feature_names[name] = self._get_feature_names_local()
                    except Exception: pass
                cursor.close()
                conn.close()
                return
            except Exception as e:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

    def _load_all_models_from_db(self):
        from datetime import datetime
        import time
        model_names = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern',
            'liquidity', 'chart_cnn', 'candle_expert', 'volume_pred', 'meta_trading',
            'sentiment', 'crypto_news'
        ]
        print("\n" + "="*60)
        print("📥 Loading Deep Learning Models from Database...")
        print("="*60)
        loaded = 0
        for i, name in enumerate(model_names):
            try:
                self._load_single_model(name)
                if name in self._models and self._models[name] is not None:
                    loaded += 1
                    acc = self._model_accuracy.get(name, 0.0)
                    print(f"  {name:17} {acc*100:5.1f}%")
                else:
                    print(f"  {name:17} Not found")
            except Exception as e:
                print(f"  {name:17} Error")
            if i < len(model_names) - 1:
                time.sleep(1)
        print("="*60)
        print(f"✅ Successfully loaded {loaded}/{len(model_names)} models")
        print("="*60 + "\n")
        import gc
        gc.collect()
        self._last_models_check = datetime.now()

    def _print_models_status(self):
        # تم تعطيل طباعة الحالة - يتم الطباعة فقط عند التحميل
        pass

    def check_for_updates(self):
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return False
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT model_name, trained_at
                FROM dl_models_v2
                WHERE status = 'active'
                ORDER BY trained_at DESC
            """)
            results = cursor.fetchall()
            cursor.close()
            self._return_conn(conn)
            conn = None
            if not results:
                return False
            for row in results:
                name = row['model_name']
                db_trained_at = str(row['trained_at'])
                current_loaded_at = self._model_trained_at.get(name)
                if not current_loaded_at:
                    return True
                if db_trained_at != current_loaded_at:
                    return True
            return False
        except Exception as e:
            print(f"⚠️ check_for_updates error: {e}")
            if conn:
                try:
                    self._pool.putconn(conn, close=True) if self._pool else conn.close()
                except Exception:
                    pass
            return False
    
    def get_model_accuracy(self, model_name):
        return self._model_accuracy.get(model_name, 0)

    def get_advice(self, rsi, macd, volume_ratio, price_momentum, confidence=50,
                   liquidity_metrics=None, market_sentiment=None, candle_analysis=None, analysis_data=None, action='BUY'):
        advice = {}
        analysis = analysis_data if analysis_data else {}
        
        # تحديد نوع القرار (شراء أو بيع)
        is_sell_mode = (action == 'SELL')
        
        full_data = {
            'rsi': rsi,
            'macd': macd,
            'macd_diff': macd,
            'volume_ratio': volume_ratio,
            'price_momentum': price_momentum,
            **analysis
        }
        
        if liquidity_metrics:
            full_data.update(liquidity_metrics)
        if market_sentiment:
            full_data.update(market_sentiment)
        if candle_analysis:
            full_data.update(candle_analysis)
        
        try:
            from MSA_DeepLearning_Trainer.core.features import calculate_enhanced_features, get_feature_names
            all_43 = calculate_enhanced_features(full_data)
            all_names = get_feature_names()
        except ImportError:
            all_43 = self._calculate_features_local(full_data)
            all_names = self._get_feature_names_local()
        
        leaky = {'trade_quality_score', 'is_trap_trade', 'profit_magnitude', 'is_profitable', 'hours_held_normalized'}
        base_features = [f for f, n in zip(all_43, all_names) if n not in leaky]
        base_names = [n for n in all_names if n not in leaky]

        def _predict(model, features, names, is_sell=False):
            try:
                X = pd.DataFrame([features], columns=names)
                proba = model.predict_proba(X)[0][1]
                
                # في وضع البيع، نعكس المنطق (نبحث عن إشارات هبوط)
                if is_sell:
                    if proba < 0.3:
                        return "Strong-Bearish"  # قمة قوية - بيع
                    elif proba < 0.45:
                        return "Bearish"  # قمة متوسطة
                    elif proba > 0.7:
                        return "Strong-Bullish"  # لا تبيع - استمر
                    elif proba > 0.55:
                        return "Bullish"  # لا تبيع
                    else:
                        return "Neutral"
                else:
                    # وضع الشراء (المنطق الأصلي)
                    if proba > 0.7:
                        return "Strong-Bullish"
                    elif proba > 0.55:
                        return "Bullish"
                    elif proba < 0.3:
                        return "Strong-Bearish"
                    elif proba < 0.45:
                        return "Bearish"
                    else:
                        return "Neutral"
            except Exception as e:
                return "N/A"
        
        # Smart Money (38 + 4 = 42)
        model = self._models.get('smart_money') if MemoryCache else self._models.get('smart_money')
        if model:
            whale = analysis.get('whale_confidence', 0)
            inflow = analysis.get('exchange_inflow', 0)
            features = base_features + [whale, inflow, 0.5, 0.5]
            names = base_names + ['whale_activity', 'exchange_inflow', 'tp_accuracy', 'sell_accuracy']
            advice['smart_money'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['smart_money'] = "N/A"
        
        # Risk (38 + 4 = 42)
        model = self._models.get('risk')
        if model:
            features = base_features + [rsi, analysis.get('atr', 1), 0.5, 0.5]
            names = base_names + ['risk_rsi', 'risk_atr', 'tp_accuracy', 'sell_accuracy']
            advice['risk'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['risk'] = "N/A"
        
        # Anomaly (38 + 3 = 41)
        model = self._models.get('anomaly')
        if model:
            features = base_features + [analysis.get('anomaly_score', 0), 0.5, 0.5]
            names = base_names + ['anomaly_score', 'tp_accuracy', 'sell_accuracy']
            advice['anomaly'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['anomaly'] = "N/A"
        
        # Exit (38 + 3 = 41)
        model = self._models.get('exit')
        if model:
            features = base_features + [24, 0.5, 0.5]
            names = base_names + ['hours_held', 'tp_accuracy', 'sell_accuracy']
            advice['exit'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['exit'] = "N/A"
        
        # Pattern (38 + 3 = 41)
        model = self._models.get('pattern')
        if model:
            features = base_features + [price_momentum, 0.5, 0.5]
            names = base_names + ['pattern_momentum', 'tp_accuracy', 'sell_accuracy']
            advice['pattern'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['pattern'] = "N/A"
        
        # Liquidity (26 ميزة متقدمة!)
        model = self._models.get('liquidity')
        if model:
            liq = liquidity_metrics or {}
            
            # الميزات الأساسية
            liquidity_score = liq.get('liquidity_score', 50)
            price_impact = liq.get('price_impact', 0.5)
            depth_ratio = liq.get('depth_ratio', 1.0)
            volume_consistency = liq.get('volume_consistency', 50)
            spread_percent = liq.get('spread_percent', 0.1)
            
            # 🆕 الميزات المتقدمة من analysis
            spread_volatility = analysis.get('spread_volatility', 0)
            depth_at_1pct = analysis.get('depth_at_1pct', 0)
            market_impact_score = analysis.get('market_impact_score', 0)
            liquidity_trends = analysis.get('liquidity_trends', 0)
            order_book_imbalance = analysis.get('order_book_imbalance', 0)
            
            # الميزات المشتقة
            good_liquidity = 1 if liquidity_score > 70 else 0
            low_impact = 1 if price_impact < 0.3 else 0
            consistent_vol = 1 if volume_consistency > 60 else 0
            high_depth = 1 if depth_at_1pct > 100000 else 0
            low_spread_vol = 1 if spread_volatility < 0.5 else 0
            balanced_book = 1 if abs(order_book_imbalance) < 0.2 else 0
            
            # الميزات المركبة
            liquidity_depth = depth_ratio * liquidity_score / 100
            impact_risk = price_impact * (1 - liquidity_score/100)
            volume_liquidity_score = volume_ratio * liquidity_score / 100
            spread_impact = spread_percent * price_impact
            
            features = [
                # الميزات الأساسية (10)
                volume_ratio,
                analysis.get('bid_ask_spread', 0),
                analysis.get('volume_trend', 0),
                depth_ratio, liquidity_score, price_impact, volume_consistency,
                good_liquidity, low_impact, consistent_vol,
                # 🆕 الميزات المتقدمة (5)
                spread_volatility, depth_at_1pct, market_impact_score,
                liquidity_trends, order_book_imbalance,
                # 🆕 الميزات المشتقة (6)
                high_depth, low_spread_vol, balanced_book,
                liquidity_depth, impact_risk, volume_liquidity_score,
                # الميزات الإضافية (3)
                spread_percent, spread_impact,
                0.5, 0.5
            ]
            names = [
                # الميزات الأساسية (10)
                'volume_ratio', 'bid_ask_spread', 'volume_trend',
                'depth_ratio', 'liquidity_score', 'price_impact', 'volume_consistency',
                'good_liquidity', 'low_impact', 'consistent_vol',
                # 🆕 الميزات المتقدمة (5)
                'spread_volatility', 'depth_at_1pct', 'market_impact_score',
                'liquidity_trends', 'order_book_imbalance',
                # 🆕 الميزات المشتقة (6)
                'high_depth', 'low_spread_vol', 'balanced_book',
                'liquidity_depth', 'impact_risk', 'volume_liquidity_score',
                # الميزات الإضافية (3)
                'spread_percent', 'spread_impact',
                'tp_accuracy', 'sell_accuracy'
            ]
            advice['liquidity'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['liquidity'] = "N/A"
        
        # Chart CNN (38 + 5 = 43) - تحليل الرسم البياني العام
        model = self._models.get('chart_cnn')
        if model:
            bullish = 1 if (rsi < 40 and macd > 0 and volume_ratio > 1.2) else 0
            bearish = 1 if (rsi > 65 and macd < 0) else 0
            neutral = 1 if (40 <= rsi <= 60) else 0
            features = base_features + [bullish, bearish, neutral, 0.5, 0.5]
            names = base_names + ['bullish_chart', 'bearish_chart', 'neutral_chart', 'tp_accuracy', 'sell_accuracy']
            advice['chart_cnn'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['chart_cnn'] = "N/A"
        
        # Volume Pred (25 ميزة)
        model = self._models.get('volume_pred')
        if model:
            vol = analysis.get('volume', 0)
            features = [
                vol, analysis.get('volume_avg_1h', vol), analysis.get('volume_avg_4h', vol),
                analysis.get('volume_avg_24h', vol), volume_ratio,
                analysis.get('volume_ratio_4h', 1), analysis.get('volume_ratio_24h', 1),
                analysis.get('volume_trend', 0), analysis.get('volume_volatility', 0),
                analysis.get('price_change_24h_old', 0),
                rsi, macd, analysis.get('atr', 0), analysis.get('bid_ask_spread', 0),
                analysis.get('volume_momentum', 0), analysis.get('volume_acceleration', 0),
                1 if volume_ratio > 2.0 else 0,
                1 if volume_ratio < 0.5 else 0,
                1 if rsi < 20 or rsi > 80 else 0,
                # إضافة 6 ميزات إضافية للوصول إلى 25
                analysis.get('volume_ma_ratio', 1.0),
                analysis.get('volume_std', 0),
                analysis.get('price_volume_corr', 0),
                analysis.get('volume_breakout', 0),
                analysis.get('volume_trend_strength', 0),
                analysis.get('volume_consistency', 50)
            ]
            names = [
                'volume', 'volume_avg_1h', 'volume_avg_4h', 'volume_avg_24h', 'volume_ratio',
                'volume_ratio_4h', 'volume_ratio_24h', 'volume_trend', 'volume_volatility',
                'price_history_lag', 'rsi', 'macd', 'atr', 'bid_ask_spread',
                'volume_momentum', 'volume_acceleration',
                'volume_spike', 'volume_declining', 'rsi_extreme',
                'volume_ma_ratio', 'volume_std', 'price_volume_corr',
                'volume_breakout', 'volume_trend_strength', 'volume_consistency'
            ]
            advice['volume_pred'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['volume_pred'] = "N/A"
        
        # Sentiment (15 ميزة)
        model = self._models.get('sentiment')
        if model:
            sent = market_sentiment or {}
            fear_greed = sent.get('fear_greed', 50)
            social_volume = sent.get('social_volume', 1000)
            positive = sent.get('positive_ratio', 0.33)
            negative = sent.get('negative_ratio', 0.33)
            neutral = sent.get('neutral_ratio', 0.34)
            trending_score = sent.get('trending_score', 0)
            news_sentiment = sent.get('news_sentiment', 0)
            pos_neg_ratio = positive / (negative + 0.001)
            sentiment_score = positive - negative
            fear_greed_norm = (fear_greed - 50) / 50
            is_fearful = 1 if fear_greed < 30 else 0
            is_greedy = 1 if fear_greed > 70 else 0
            high_social = 1 if social_volume > 1000 else 0
            strong_positive = 1 if positive > 0.6 else 0
            strong_negative = 1 if negative > 0.6 else 0
            
            features = [
                fear_greed, social_volume, positive, negative, neutral,
                trending_score, news_sentiment,
                pos_neg_ratio, sentiment_score, fear_greed_norm,
                is_fearful, is_greedy, high_social, strong_positive, strong_negative
            ]
            names = [
                'fear_greed_index', 'social_volume', 'positive_ratio',
                'negative_ratio', 'neutral_ratio', 'trending_score',
                'news_sentiment', 'pos_neg_ratio', 'sentiment_score',
                'fear_greed_norm', 'is_fearful', 'is_greedy',
                'high_social', 'strong_positive', 'strong_negative'
            ]
            advice['sentiment'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['sentiment'] = "N/A"
        
        # Candle Expert (56 + 4 = 60) - متخصص بأنماط الشموع اليابانية المتقدمة
        model = self._models.get('candle_expert')
        if model:
            candle_features = self._extract_advanced_candle_features(analysis)
            features = candle_features + [rsi, volume_ratio, 0.5, 0.5]
            
            # أسماء الميزات (56 ميزة شموع + 4 إضافية)
            names = self._get_candle_feature_names() + ['rsi', 'volume_ratio', 'tp_accuracy', 'sell_accuracy']
            
            advice['candle_expert'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['candle_expert'] = "N/A"
        
        # Crypto News (10 ميزة)
        model = self._models.get('crypto_news')
        if model:
            news = analysis.get('news', {})
            news_score = news.get('news_score', 0)
            news_pos = news.get('positive', 0)
            news_neg = news.get('negative', 0)
            news_total = news.get('total', 0)
            news_ratio = news_pos / (news_neg + 0.001)
            has_news = 1 if news_total > 0 else 0
            strong_pos_news = 1 if news_pos > 3 else 0
            strong_neg_news = 1 if news_neg > 3 else 0
            balanced_news = 1 if abs(news_pos - news_neg) <= 1 else 0
            high_volume_news = 1 if news_total > 5 else 0
            
            features = [
                news_score, news_pos, news_neg, news_total, news_ratio,
                has_news, strong_pos_news, strong_neg_news, balanced_news, high_volume_news
            ]
            names = [
                'news_score', 'news_positive', 'news_negative', 'news_total', 'news_ratio',
                'has_news', 'strong_pos_news', 'strong_neg_news', 'balanced_news', 'high_volume_news'
            ]
            advice['crypto_news'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['crypto_news'] = "N/A"

        # تنظيف الذاكرة بعد الانتهاء من استخدام المودلات
        import gc
        gc.collect()

        return advice

    def is_available(self):
        try:
            conn = self._get_conn()
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'dl_models_v2'
                )
            """)
            exists = cursor.fetchone()[0]
            cursor.close()
            return exists
        except:
            return False

    def get_models_status(self):
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return {}
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT model_name, accuracy, trained_at
                FROM dl_models_v2
                WHERE status = 'active'
                ORDER BY model_name
            """)
            results = cursor.fetchall()
            cursor.close()
            self._return_conn(conn)
            conn = None
            status = {}
            for row in results:
                status[row['model_name']] = {
                    'accuracy': row['accuracy'],
                    'trained_at': str(row['trained_at'])
                }
            return status
        except Exception as e:
            if conn:
                try:
                    self._pool.putconn(conn, close=True) if self._pool else conn.close()
                except Exception:
                    pass
            return {}
    
    def _get_feature_names_local(self):
        return [
            'rsi', 'macd', 'volume_ratio', 'price_momentum',
            'bb_position', 'atr_estimate', 'stochastic', 'ema_signal',
            'volume_strength', 'momentum_strength',
            'atr', 'ema_crossover', 'bid_ask_spread', 'volume_trend', 'price_change_1h',
            'trade_quality_score', 'advisor_vote_consensus', 'is_trap_trade',
            'profit_magnitude', 'hours_held_normalized', 'is_profitable',
            'btc_trend_normalized', 'is_bullish_market', 'hour_normalized',
            'is_asian_session', 'is_european_session', 'is_us_session', 'optimal_hold_score',
            'fib_score', 'fib_level_encoded',
            'regime_score', 'regime_adx', 'volatility_ratio', 'position_multiplier',
            'flash_risk_score', 'flash_crash_detected', 'whale_dump_detected', 'cascade_risk_score',
            'whale_confidence', 'atr_value', 'sentiment_score', 'panic_score', 'optimism_penalty'
        ]
    
    def _calculate_features_local(self, data, trade=None):
        try:
            full_data = {**data}
            if trade:
                trade_data = trade.get('data', {})
                if isinstance(trade_data, str):
                    trade_data = json.loads(trade_data)
                full_data = {**trade, **trade_data, **data}
            
            rsi = full_data.get('rsi', 50)
            macd = full_data.get('macd_diff', full_data.get('macd', 0))
            volume_ratio = full_data.get('volume_ratio', 1)
            price_momentum = full_data.get('price_momentum', 0)
            
            bb_position = (rsi - 30) / 40
            atr_estimate = abs(price_momentum) * volume_ratio
            stochastic = rsi
            ema_signal = 1 if macd > 0 else -1
            volume_strength = min(volume_ratio / 2.0, 2.0)
            momentum_strength = abs(price_momentum) / 10.0
            
            atr = full_data.get('atr', atr_estimate)
            ema_9 = full_data.get('ema_9', 0)
            ema_21 = full_data.get('ema_21', 0)
            ema_crossover = 1 if ema_9 > ema_21 else -1
            bid_ask_spread = full_data.get('bid_ask_spread', 0)
            volume_trend = full_data.get('volume_trend', 0)
            price_change_1h = full_data.get('price_change_1h', 0)
            
            # 43 ميزة كاملة
            return [
                # 15 ميزة تقليدية
                rsi, macd, volume_ratio, price_momentum,
                bb_position, atr_estimate, stochastic, ema_signal,
                volume_strength, momentum_strength,
                atr, ema_crossover, bid_ask_spread, volume_trend, price_change_1h,
                # 6 ميزات من التعلم (leaky - ستحذف لاحقاً)
                3, 0.5, 0, 0, 0.5, 1,
                # 7 ميزات من السوق والوقت
                0, 0, 0.5, 0, 0, 0, 0.5,
                # 2 ميزة فيبوناتشي
                0, 0,
                # 4 ميزات Market Regime
                0.5, 0.4, 1.0, 1.0,
                # 4 ميزات Flash Crash
                0, 0, 0, 0,
                # 5 ميزات إضافية
                0, 0, 0, 0, 0
            ]
        except Exception:
            # 43 ميزة افتراضية
            return [50, 0, 1, 0, 0.5, 1, 50, 0, 1, 0, 1, 0, 0, 0, 0,
                   3, 0.5, 0, 0, 0.5, 1, 0, 0, 0.5, 0, 0, 0, 0.5,
                   0, 0, 0.5, 0.4, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    
    def _extract_advanced_candle_features(self, analysis):
        """
        🕹️ استخراج ميزات متقدمة من الشموع (56 ميزة)
        يتطابق مع extract_candle_features في candle_expert_model.py
        """
        try:
            candles = analysis.get('candles', [])
            if not candles or len(candles) < 3:
                return [0] * 56
            
            features = []
            
            # تحليل آخر 7 شموع
            last_7 = candles[-7:] if len(candles) >= 7 else candles
            while len(last_7) < 7:
                last_7.insert(0, {'open': 0, 'high': 0, 'low': 0, 'close': 0})
            
            # === 1. ميزات الشموع الفردية (7 × 6 = 42) ===
            for c in last_7:
                o = float(c.get('open', 0))
                h = float(c.get('high', 0))
                l = float(c.get('low', 0))
                cl = float(c.get('close', 0))
                
                full_range = (h - l) if (h - l) > 0 else 0.000001
                body_size = abs(cl - o)
                
                body_ratio = body_size / full_range
                upper_shadow_ratio = (h - max(o, cl)) / full_range
                lower_shadow_ratio = (min(o, cl) - l) / full_range
                direction = 1 if cl > o else (-1 if cl < o else 0)
                is_doji = 1 if body_ratio < 0.1 else 0
                is_long_body = 1 if body_ratio > 0.7 else 0
                
                features.extend([
                    body_ratio, upper_shadow_ratio, lower_shadow_ratio,
                    direction, is_doji, is_long_body
                ])
            
            # === 2. ميزات الأنماط المركبة (14) ===
            if len(last_7) >= 3:
                c1, c2, c3 = last_7[-3], last_7[-2], last_7[-1]
                
                body1 = abs(float(c1.get('close', 0)) - float(c1.get('open', 0)))
                body2 = abs(float(c2.get('close', 0)) - float(c2.get('open', 0)))
                body3 = abs(float(c3.get('close', 0)) - float(c3.get('open', 0)))
                
                rel_size_2_1 = body2 / (body1 + 0.000001)
                rel_size_3_2 = body3 / (body2 + 0.000001)
                
                dir1 = 1 if float(c1.get('close', 0)) > float(c1.get('open', 0)) else -1
                dir2 = 1 if float(c2.get('close', 0)) > float(c2.get('open', 0)) else -1
                dir3 = 1 if float(c3.get('close', 0)) > float(c3.get('open', 0)) else -1
                
                consecutive_green = 1 if (dir1 == 1 and dir2 == 1 and dir3 == 1) else 0
                consecutive_red = 1 if (dir1 == -1 and dir2 == -1 and dir3 == -1) else 0
                
                gap_2_1 = abs(float(c2.get('open', 0)) - float(c1.get('close', 0))) / (float(c1.get('close', 0)) + 0.000001)
                gap_3_2 = abs(float(c3.get('open', 0)) - float(c2.get('close', 0))) / (float(c2.get('close', 0)) + 0.000001)
                
                c3_upper = float(c3.get('high', 0)) - max(float(c3.get('open', 0)), float(c3.get('close', 0)))
                c3_lower = min(float(c3.get('open', 0)), float(c3.get('close', 0))) - float(c3.get('low', 0))
                c3_range = float(c3.get('high', 0)) - float(c3.get('low', 0))
                
                upper_wick_dominance = c3_upper / (c3_range + 0.000001)
                lower_wick_dominance = c3_lower / (c3_range + 0.000001)
                
                is_star = 1 if (body3 < 0.1 * c3_range and gap_3_2 > 0.005) else 0
                
                high_3 = max(float(c1.get('high', 0)), float(c2.get('high', 0)), float(c3.get('high', 0)))
                low_3 = min(float(c1.get('low', 0)), float(c2.get('low', 0)), float(c3.get('low', 0)))
                breakout_up = 1 if float(c3.get('close', 0)) > high_3 * 1.002 else 0
                breakout_down = 1 if float(c3.get('close', 0)) < low_3 * 0.998 else 0
                
                features.extend([
                    rel_size_2_1, rel_size_3_2,
                    consecutive_green, consecutive_red,
                    gap_2_1, gap_3_2,
                    upper_wick_dominance, lower_wick_dominance,
                    is_star, breakout_up, breakout_down,
                    dir1, dir2, dir3
                ])
            else:
                features.extend([0] * 14)
            
            return features
            
        except Exception as e:
            print(f"⚠️ Candle feature extraction error: {e}")
            return [0] * 56
    
    def _get_candle_feature_names(self):
        """أسماء ميزات الشموع (56 ميزة)"""
        names = []
        
        # ميزات الشموع الفردية (7 × 6 = 42)
        for i in range(7, 0, -1):
            names.extend([
                f'c{i}_body_ratio',
                f'c{i}_upper_shadow',
                f'c{i}_lower_shadow',
                f'c{i}_direction',
                f'c{i}_is_doji',
                f'c{i}_is_long_body'
            ])
        
        # ميزات الأنماط المركبة (14)
        names.extend([
            'rel_size_2_1', 'rel_size_3_2',
            'consecutive_green', 'consecutive_red',
            'gap_2_1', 'gap_3_2',
            'upper_wick_dominance', 'lower_wick_dominance',
            'is_star', 'breakout_up', 'breakout_down',
            'dir1', 'dir2', 'dir3'
        ])
        
        return names
    
    def _analyze_candles_from_data(self, analysis):
        """
        🕯️ تحليل ذكي لجميع أنماط الشموع اليابانية - يعتمد على الموديل 100%
        يقرأ الشموع مباشرة ويحللها بذكاء اصطناعي متطور
        
        الأنماط المدعومة:
        - Hammer, Inverted Hammer (قاع)
        - Bullish Engulfing, Piercing Line (قاع)
        - Morning Star, Three White Soldiers (قاع)
        - Shooting Star, Hanging Man (قمة)
        - Bearish Engulfing, Dark Cloud Cover (قمة)
        - Evening Star, Three Black Crows (قمة)
        - Doji, Spinning Top (محايد)
        """
        try:
            candles = analysis.get('candles', [])
            if not candles or len(candles) < 2:
                return {'bullish': 0, 'bearish': 0, 'neutral': 1}
            
            # تحليل ذكي لكل الأنماط
            bullish_score = 0
            bearish_score = 0
            neutral_score = 0
            
            for i, candle in enumerate(candles):
                if not isinstance(candle, dict):
                    continue
                    
                open_price = float(candle.get('open', 0))
                close_price = float(candle.get('close', 0))
                high_price = float(candle.get('high', 0))
                low_price = float(candle.get('low', 0))
                
                if open_price == 0 or close_price == 0:
                    continue
                
                # حساب جسم الشمعة والظلال
                body = abs(close_price - open_price)
                total_range = high_price - low_price
                upper_shadow = high_price - max(open_price, close_price)
                lower_shadow = min(open_price, close_price) - low_price
                
                if total_range == 0:
                    continue
                
                body_ratio = body / total_range
                is_green = close_price > open_price
                is_red = close_price < open_price
                
                # ========== أنماط القاع (Bullish) ==========
                
                # 1. Hammer (مطرقة - قاع قوي)
                if lower_shadow > body * 2 and upper_shadow < body * 0.3 and body_ratio < 0.4:
                    bullish_score += 3
                
                # 2. Inverted Hammer (مطرقة مقلوبة - قاع)
                if upper_shadow > body * 2 and lower_shadow < body * 0.3 and body_ratio < 0.4 and is_green:
                    bullish_score += 2
                
                # 3. Bullish Engulfing (ابتلاع صاعد - قاع قوي)
                if i > 0 and is_green:
                    prev_candle = candles[i-1]
                    prev_close = float(prev_candle.get('close', 0))
                    prev_open = float(prev_candle.get('open', 0))
                    prev_body = abs(prev_close - prev_open)
                    if prev_close < prev_open and close_price > prev_open and open_price < prev_close and body > prev_body * 1.2:
                        bullish_score += 4
                
                # 4. Piercing Line (خط الاختراق - قاع)
                if i > 0 and is_green:
                    prev_candle = candles[i-1]
                    prev_close = float(prev_candle.get('close', 0))
                    prev_open = float(prev_candle.get('open', 0))
                    prev_mid = (prev_open + prev_close) / 2
                    if prev_close < prev_open and open_price < prev_close and close_price > prev_mid:
                        bullish_score += 3
                
                # 5. Morning Star (نجمة الصباح - قاع قوي جداً)
                if i >= 2:
                    prev1 = candles[i-1]
                    prev2 = candles[i-2]
                    prev2_close = float(prev2.get('close', 0))
                    prev2_open = float(prev2.get('open', 0))
                    prev1_body = abs(float(prev1.get('close', 0)) - float(prev1.get('open', 0)))
                    if prev2_close < prev2_open and prev1_body < body * 0.3 and is_green:
                        bullish_score += 5
                
                # 6. Three White Soldiers (ثلاثة جنود بيض - قاع قوي)
                if i >= 2:
                    c1 = candles[i-2]
                    c2 = candles[i-1]
                    c1_green = float(c1.get('close', 0)) > float(c1.get('open', 0))
                    c2_green = float(c2.get('close', 0)) > float(c2.get('open', 0))
                    if c1_green and c2_green and is_green:
                        if float(c2.get('close', 0)) > float(c1.get('close', 0)) and close_price > float(c2.get('close', 0)):
                            bullish_score += 4
                
                # ========== أنماط القمة (Bearish) ==========
                
                # 7. Shooting Star (نجمة هابطة - قمة قوية)
                if upper_shadow > body * 2 and lower_shadow < body * 0.3 and body_ratio < 0.4 and is_red:
                    bearish_score += 3
                
                # 8. Hanging Man (رجل معلق - قمة)
                if lower_shadow > body * 2 and upper_shadow < body * 0.3 and body_ratio < 0.4 and is_red:
                    bearish_score += 2
                
                # 9. Bearish Engulfing (ابتلاع هابط - قمة قوية)
                if i > 0 and is_red:
                    prev_candle = candles[i-1]
                    prev_close = float(prev_candle.get('close', 0))
                    prev_open = float(prev_candle.get('open', 0))
                    prev_body = abs(prev_close - prev_open)
                    if prev_close > prev_open and open_price > prev_close and close_price < prev_open and body > prev_body * 1.2:
                        bearish_score += 4
                
                # 10. Dark Cloud Cover (غطاء سحابة داكنة - قمة)
                if i > 0 and is_red:
                    prev_candle = candles[i-1]
                    prev_close = float(prev_candle.get('close', 0))
                    prev_open = float(prev_candle.get('open', 0))
                    prev_mid = (prev_open + prev_close) / 2
                    if prev_close > prev_open and open_price > prev_close and close_price < prev_mid:
                        bearish_score += 3
                
                # 11. Evening Star (نجمة المساء - قمة قوية جداً)
                if i >= 2:
                    prev1 = candles[i-1]
                    prev2 = candles[i-2]
                    prev2_close = float(prev2.get('close', 0))
                    prev2_open = float(prev2.get('open', 0))
                    prev1_body = abs(float(prev1.get('close', 0)) - float(prev1.get('open', 0)))
                    if prev2_close > prev2_open and prev1_body < body * 0.3 and is_red:
                        bearish_score += 5
                
                # 12. Three Black Crows (ثلاثة غربان سود - قمة قوية)
                if i >= 2:
                    c1 = candles[i-2]
                    c2 = candles[i-1]
                    c1_red = float(c1.get('close', 0)) < float(c1.get('open', 0))
                    c2_red = float(c2.get('close', 0)) < float(c2.get('open', 0))
                    if c1_red and c2_red and is_red:
                        if float(c2.get('close', 0)) < float(c1.get('close', 0)) and close_price < float(c2.get('close', 0)):
                            bearish_score += 4
                
                # ========== أنماط محايدة (Neutral) ==========
                
                # 13. Doji (دوجي - تردد)
                if body < total_range * 0.1:
                    neutral_score += 2
                
                # 14. Spinning Top (قمة دوارة - تردد)
                if body_ratio > 0.2 and body_ratio < 0.4 and upper_shadow > body * 0.8 and lower_shadow > body * 0.8:
                    neutral_score += 1
                
                # شموع عادية (وزن خفيف)
                if is_green and body_ratio > 0.6:
                    bullish_score += 0.5
                if is_red and body_ratio > 0.6:
                    bearish_score += 0.5
            
            # تحويل النتائج إلى 0 أو 1 (الموديل يقرر)
            total_score = bullish_score + bearish_score + neutral_score
            if total_score == 0:
                return {'bullish': 0, 'bearish': 0, 'neutral': 1}
            
            bullish_ratio = bullish_score / total_score
            bearish_ratio = bearish_score / total_score
            neutral_ratio = neutral_score / total_score
            
            # تحديد الإشارة الأقوى (الموديل يتعلم من هذه النسب)
            if bullish_ratio > 0.5:
                return {'bullish': 1, 'bearish': 0, 'neutral': 0}
            elif bearish_ratio > 0.5:
                return {'bullish': 0, 'bearish': 1, 'neutral': 0}
            elif neutral_ratio > 0.4:
                return {'bullish': 0, 'bearish': 0, 'neutral': 1}
            else:
                # حالة مختلطة - نعطي الأولوية للأقوى
                if bullish_score > bearish_score:
                    return {'bullish': 1, 'bearish': 0, 'neutral': 0}
                elif bearish_score > bullish_score:
                    return {'bullish': 0, 'bearish': 1, 'neutral': 0}
                else:
                    return {'bullish': 0, 'bearish': 0, 'neutral': 1}
                
        except Exception as e:
            print(f"⚠️ Candle analysis error: {e}")
            return {'bullish': 0, 'bearish': 0, 'neutral': 1}
    
    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, signal_type='sell'):
        try:
            pass
        except Exception:
            pass
