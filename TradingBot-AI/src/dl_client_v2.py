"""
🧠 Deep Learning Client V3 - للبوت الرئيسي
يحمل موديلات LightGBM المدربة من قاعدة البيانات ويستخدمها للتصويت
"""
import gc
import os
import sys
import json
import pickle
import gzip
import zlib
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote
from datetime import datetime, timezone

# ✅ تعريف المسارات أولاً
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir  = os.path.dirname(current_dir)
except Exception:
    current_dir = ''
    parent_dir  = ''

try:
    memory_path = os.path.join(os.path.dirname(parent_dir), 'memory')
    if os.path.exists(memory_path) and memory_path not in sys.path:
        sys.path.insert(0, memory_path)
    from memory_cache import MemoryCache
except Exception:
    MemoryCache = None

try:
    trainer_path = os.path.join(os.path.dirname(parent_dir), 'MSA-DeepLearning-Trainer')
    if os.path.exists(trainer_path) and trainer_path not in sys.path:
        sys.path.insert(0, trainer_path)
except Exception:
    pass


class DeepLearningClientV2:
    def __init__(self, database_url, load_models=True):
        self.database_url      = database_url
        self.conn              = None
        self._db_params        = None
        self._pool             = None
        self._models           = MemoryCache(max_items=20) if MemoryCache else {}
        self._model_accuracy   = {}
        self._model_trained_at = {}
        self._feature_names    = {}
        self._prediction_cache = {}
        try:
            self._connect_db()
            if load_models:
                self._load_all_models_from_db()
                self._print_models_status()
        except Exception as e:
            raise

    def _connect_db(self):
        from psycopg2.pool import ThreadedConnectionPool
        try:
            parsed   = urlparse(self.database_url)
            password = unquote(parsed.password) if parsed.password else None
            self._db_params = {
                'host'               : parsed.hostname,
                'port'               : parsed.port or 5432,
                'database'           : parsed.path[1:],
                'user'               : parsed.username,
                'password'           : password,
                'sslmode'            : 'require',
                'connect_timeout'    : 15,
                'keepalives'         : 1,
                'keepalives_idle'    : 60,
                'keepalives_interval': 10,
                'keepalives_count'   : 5,
            }
            self._pool = ThreadedConnectionPool(1, 4, **self._db_params)
            conn       = self._pool.getconn()
            self.conn  = conn
            self._pool.putconn(conn)
        except Exception as e:
            print(f"⚠️ DL Client V2 DB error: {e}")
            self.conn  = None
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
            conn   = self._get_conn()
            if not conn:
                return None
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT model_data FROM dl_models_v2
                WHERE model_name = %s
                ORDER BY trained_at DESC LIMIT 1
            """, (model_name,))
            result = cursor.fetchone()
            cursor.close()
            self._return_conn(conn)
            conn = None
            return result['model_data'] if result and result.get('model_data') else None
        except Exception as e:
            print(f"⚠️ get_model_data error: {e}")
            if conn:
                try:
                    self._pool.putconn(conn, close=True) if self._pool else conn.close()
                except Exception:
                    pass
            return None

    def _load_single_model(self, name):
        import time
        for attempt in range(3):
            conn = None
            try:
                if self._db_params is None:
                    return
                conn   = psycopg2.connect(**self._db_params.copy())
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT accuracy, trained_at, model_data,
                           octet_length(model_data) as data_size
                    FROM dl_models_v2
                    WHERE model_name = %s
                    ORDER BY trained_at DESC LIMIT 1
                """, (name,))
                result = cursor.fetchone()
                if not result:
                    cursor.close()
                    conn.close()
                    return
                db_acc = result.get('accuracy')
                self._model_accuracy[name]   = float(db_acc) if db_acc is not None else 0.0
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
                            self._models.set(name, model_obj, expiry_seconds=None)
                        else:
                            self._models[name] = model_obj
                        cursor.close()
                        conn.close()
                        gc.collect()
                        return
                    except Exception as e:
                        print(f"⚠️ Model deserialize error ({name}): {e}")
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    if MemoryCache:
                        self._models.set(name, None, expiry_seconds=None)
                    else:
                        self._models[name] = None

    def _load_all_models_from_db(self):
        import time
        model_names = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern',
            'liquidity', 'chart_cnn', 'candle_expert', 'volume_pred',
            'meta_trading', 'sentiment', 'crypto_news'
        ]
        print("📥 Loading Deep Learning Models from Database...")
        for i, name in enumerate(model_names):
            try:
                self._load_single_model(name)
                loaded = (self._models.get(name) is not None) if MemoryCache else (self._models.get(name) is not None)
                if loaded:
                    acc = self._model_accuracy.get(name, 0.0)
                    print(f"  {name:17} {acc * 100:5.1f}%")
                else:
                    print(f"  {name:17} Not found")
            except Exception as e:
                print(f"  {name:17} Error")
                if i < len(model_names) - 1:
                    time.sleep(1)
        gc.collect()
        self._last_models_check = datetime.now(timezone.utc)

    def _print_models_status(self):
        pass
    def _print_models_status(self):
        pass

    def check_for_updates(self):
        conn = None
        try:
            conn   = self._get_conn()
            if not conn:
                return False
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT model_name, trained_at FROM dl_models_v2
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
                name              = row['model_name']
                db_trained_at     = str(row['trained_at'])
                current_loaded_at = self._model_trained_at.get(name)
                if not current_loaded_at or db_trained_at != current_loaded_at:
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
                   liquidity_metrics=None, market_sentiment=None, candle_analysis=None,
                   analysis_data=None, action='BUY'):
        advice   = {}
        analysis = analysis_data if analysis_data else {}
        is_sell_mode = (action == 'SELL')

        full_data = {
            'rsi'           : rsi,
            'macd'          : macd,
            'macd_diff'     : macd,
            'volume_ratio'  : volume_ratio,
            'price_momentum': price_momentum,
            **analysis,
        }
        if liquidity_metrics:
            full_data.update(liquidity_metrics)
        if market_sentiment:
            full_data.update(market_sentiment)
        if candle_analysis:
            full_data.update(candle_analysis)

        try:
            from MSA_DeepLearning_Trainer.core.features import calculate_enhanced_features, get_feature_names
            all_40    = calculate_enhanced_features(full_data)
            all_names = get_feature_names()
        except ImportError:
            all_40    = self._calculate_features_local(full_data)
            all_names = self._get_feature_names_local()

        # ✅ لا يوجد leaky features بعد الآن — نستخدم كل الميزات
        base_features = list(all_40)
        base_names    = list(all_names)

        def _predict(model, features, names, is_sell=False):
            try:
                X     = pd.DataFrame([features], columns=names)
                model.set_params(predict_disable_shape_check=True)
                proba = model.predict_proba(X)[0][1]
                if is_sell:
                    if proba < 0.3:    return "Strong-Bearish"
                    elif proba < 0.45: return "Bearish"
                    elif proba > 0.7:  return "Strong-Bullish"
                    elif proba > 0.55: return "Bullish"
                    else:              return "Neutral"
                else:
                    if proba > 0.7:    return "Strong-Bullish"
                    elif proba > 0.55: return "Bullish"
                    elif proba < 0.3:  return "Strong-Bearish"
                    elif proba < 0.45: return "Bearish"
                    else:              return "Neutral"
            except Exception as e:
                print(f"⚠️ _predict error [{model.__class__.__name__}]: {e}")
                return "N/A"

        # ========== Smart Money ==========
        model = self._models.get('smart_money') if not MemoryCache else self._models.get('smart_money')
        if model:
            whale                      = analysis.get('whale_confidence', 0)
            inflow                     = analysis.get('exchange_inflow', 0)
            whale_wallet_changes       = analysis.get('whale_wallet_changes', 0.0)
            institutional_accumulation = analysis.get('institutional_accumulation', 0.0)
            smart_money_ratio          = analysis.get('smart_money_ratio', 0.0)
            exchange_whale_flows       = analysis.get('exchange_whale_flows', 0.0)
            features = (base_features + [whale, inflow, whale_wallet_changes,
                        institutional_accumulation, smart_money_ratio,
                        exchange_whale_flows, 0.5, 0.5])[:12]
            names    = (base_names + ['whale_activity', 'exchange_inflow', 'whale_wallet_changes',
                        'institutional_accumulation', 'smart_money_ratio',
                        'exchange_whale_flows', 'tp_accuracy', 'sell_accuracy'])[:12]
            advice['smart_money'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['smart_money'] = "N/A"

        # ========== Risk ==========
        model = self._models.get('risk') if not MemoryCache else self._models.get('risk')
        if model:
            volatility_risk_score  = analysis.get('volatility_risk_score', 0.0)
            correlation_risk       = analysis.get('correlation_risk', 0.0)
            gap_risk_score         = analysis.get('gap_risk_score', 0.0)
            black_swan_probability = analysis.get('black_swan_probability', 0.0)
            behavioral_risk        = analysis.get('behavioral_risk', 0.0)
            features = (base_features + [rsi, analysis.get('atr', 1), volatility_risk_score,
                        correlation_risk, gap_risk_score, black_swan_probability,
                        behavioral_risk, 0.5, 0.5])[:12]
            names    = (base_names + ['risk_rsi', 'risk_atr', 'volatility_risk_score',
                        'correlation_risk', 'gap_risk_score', 'black_swan_probability',
                        'behavioral_risk', 'tp_accuracy', 'sell_accuracy'])[:12]
            advice['risk'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['risk'] = "N/A"

        # ========== Anomaly ==========
        model = self._models.get('anomaly') if not MemoryCache else self._models.get('anomaly')
        if model:
            statistical_outliers = analysis.get('statistical_outliers', 0.0)
            pattern_anomalies    = analysis.get('pattern_anomalies', 0.0)
            behavioral_anomalies = analysis.get('behavioral_anomalies', 0.0)
            volume_anomalies     = analysis.get('volume_anomalies', 0.0)
            features = (base_features + [analysis.get('anomaly_score', 0), statistical_outliers,
                        pattern_anomalies, behavioral_anomalies,
                        volume_anomalies, 0.5, 0.5])[:12]
            names    = (base_names + ['anomaly_score', 'statistical_outliers', 'pattern_anomalies',
                        'behavioral_anomalies', 'volume_anomalies',
                        'tp_accuracy', 'sell_accuracy'])[:12]
            advice['anomaly'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['anomaly'] = "N/A"

        # ========== Exit ==========
        model = self._models.get('exit') if not MemoryCache else self._models.get('exit')
        if model:
            profit_optimization_score = analysis.get('profit_optimization_score', 0.0)
            time_decay_signals        = analysis.get('time_decay_signals', 0.0)
            opportunity_cost_exits    = analysis.get('opportunity_cost_exits', 0.0)
            market_condition_exits    = analysis.get('market_condition_exits', 0.0)
            features = (base_features + [24, profit_optimization_score, time_decay_signals,
                        opportunity_cost_exits, market_condition_exits, 0.5, 0.5])[:12]
            names    = (base_names + ['hours_held', 'profit_optimization_score', 'time_decay_signals',
                        'opportunity_cost_exits', 'market_condition_exits',
                        'tp_accuracy', 'sell_accuracy'])[:12]
            advice['exit'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['exit'] = "N/A"

        # ========== Pattern ==========
        model = self._models.get('pattern') if not MemoryCache else self._models.get('pattern')
        if model:
            harmonic_patterns_score = analysis.get('harmonic_patterns_score', 0.0)
            elliott_wave_signals    = analysis.get('elliott_wave_signals', 0.0)
            fractal_patterns        = analysis.get('fractal_patterns', 0.0)
            cycle_patterns          = analysis.get('cycle_patterns', 0.0)
            momentum_patterns       = analysis.get('momentum_patterns', 0.0)
            features = (base_features + [price_momentum, harmonic_patterns_score,
                        elliott_wave_signals, fractal_patterns, cycle_patterns,
                        momentum_patterns, 0.5, 0.5])[:12]
            names    = (base_names + ['pattern_momentum', 'harmonic_patterns_score',
                        'elliott_wave_signals', 'fractal_patterns', 'cycle_patterns',
                        'momentum_patterns', 'tp_accuracy', 'sell_accuracy'])[:12]
            advice['pattern'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['pattern'] = "N/A"

        # ========== Liquidity ==========
        model = self._models.get('liquidity') if not MemoryCache else self._models.get('liquidity')
        if model:
            liq                  = liquidity_metrics or {}
            liquidity_score      = liq.get('liquidity_score', 50)
            price_impact         = liq.get('price_impact', 0.5)
            depth_ratio          = liq.get('depth_ratio', 1.0)
            volume_consistency   = liq.get('volume_consistency', 50)
            spread_percent       = liq.get('spread_percent', 0.1)
            spread_volatility    = analysis.get('spread_volatility', 0)
            depth_at_1pct        = analysis.get('depth_at_1pct', 0)
            market_impact_score  = analysis.get('market_impact_score', 0)
            liquidity_trends     = analysis.get('liquidity_trends', 0)
            order_book_imbalance = analysis.get('order_book_imbalance', 0)
            good_liquidity       = 1 if liquidity_score > 70 else 0
            low_impact           = 1 if price_impact < 0.3 else 0
            consistent_vol       = 1 if volume_consistency > 60 else 0
            high_depth           = 1 if depth_at_1pct > 100000 else 0
            low_spread_vol       = 1 if spread_volatility < 0.5 else 0
            balanced_book        = 1 if abs(order_book_imbalance) < 0.2 else 0
            liquidity_depth      = depth_ratio * liquidity_score / 100
            impact_risk          = price_impact * (1 - liquidity_score / 100)
            volume_liq_score     = volume_ratio * liquidity_score / 100
            spread_impact        = spread_percent * price_impact
            features = [
                volume_ratio, analysis.get('bid_ask_spread', 0), analysis.get('volume_trend', 0),
                depth_ratio, liquidity_score, price_impact, volume_consistency,
                good_liquidity, low_impact, consistent_vol,
                spread_volatility, depth_at_1pct, market_impact_score,
                liquidity_trends, order_book_imbalance,
                high_depth, low_spread_vol, balanced_book,
                liquidity_depth, impact_risk, volume_liq_score,
                spread_percent, spread_impact, 0.5, 0.5,
            ]
            names = [
                'volume_ratio', 'bid_ask_spread', 'volume_trend',
                'depth_ratio', 'liquidity_score', 'price_impact', 'volume_consistency',
                'good_liquidity', 'low_impact', 'consistent_vol',
                'spread_volatility', 'depth_at_1pct', 'market_impact_score',
                'liquidity_trends', 'order_book_imbalance',
                'high_depth', 'low_spread_vol', 'balanced_book',
                'liquidity_depth', 'impact_risk', 'volume_liquidity_score',
                'spread_percent', 'spread_impact', 'tp_accuracy', 'sell_accuracy',
            ]
            advice['liquidity'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['liquidity'] = "N/A"

        # ========== Chart CNN ==========
        model = self._models.get('chart_cnn') if not MemoryCache else self._models.get('chart_cnn')
        if model:
            bullish                   = 1 if (rsi < 40 and macd > 0 and volume_ratio > 1.2) else 0
            bearish                   = 1 if (rsi > 65 and macd < 0) else 0
            neutral                   = 1 if (40 <= rsi <= 60) else 0
            attention_mechanism_score = analysis.get('attention_mechanism_score', 0.0)
            multi_scale_features      = analysis.get('multi_scale_features', 0.0)
            temporal_features         = analysis.get('temporal_features', 0.0)
            features = (base_features + [bullish, bearish, neutral, attention_mechanism_score,
                        multi_scale_features, temporal_features, 0.5, 0.5])[:12]
            names    = (base_names + ['bullish_chart', 'bearish_chart', 'neutral_chart',
                        'attention_mechanism_score', 'multi_scale_features',
                        'temporal_features', 'tp_accuracy', 'sell_accuracy'])[:12]
            advice['chart_cnn'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['chart_cnn'] = "N/A"

        # ========== Volume Pred ==========
        model = self._models.get('volume_pred') if not MemoryCache else self._models.get('volume_pred')
        if model:
            vol = analysis.get('volume', 0)
            features = [
                vol,
                analysis.get('volume_avg_1h',    vol),
                analysis.get('volume_avg_4h',    vol),
                analysis.get('volume_avg_24h',   vol),
                volume_ratio,
                analysis.get('volume_ratio_4h',  1),
                analysis.get('volume_ratio_24h', 1),
                analysis.get('volume_trend',     0),
                analysis.get('volume_volatility',0),
                analysis.get('price_change_1h',  0),
                analysis.get('price_change_4h',  0),
                analysis.get('price_change_24h', 0),
                rsi, macd,
                analysis.get('atr',           0),
                analysis.get('bid_ask_spread', 0),
                analysis.get('volume_momentum',     0),
                analysis.get('volume_acceleration', 0),
                1 if volume_ratio > 2.0 else 0,
                1 if volume_ratio < 0.5 else 0,
                1 if abs(analysis.get('price_change_1h', 0)) > 3 else 0,
                1 if rsi < 20 or rsi > 80 else 0,
                1 if volume_ratio > 1.5 and analysis.get('price_change_1h', 0) > 0 else 0,
                1 if volume_ratio > 1.5 and analysis.get('price_change_1h', 0) < 0 else 0,
                volume_ratio * abs(analysis.get('price_change_1h', 0)) / 100,
            ]
            names = [
                'volume_current', 'volume_avg_1h', 'volume_avg_4h', 'volume_avg_24h',
                'volume_ratio_1h', 'volume_ratio_4h', 'volume_ratio_24h',
                'volume_trend', 'volume_volatility', 'price_change_1h',
                'price_change_4h', 'price_change_24h', 'rsi', 'macd',
                'atr', 'bid_ask_spread', 'volume_momentum', 'volume_acceleration',
                'volume_spike', 'volume_declining', 'high_momentum', 'rsi_extreme',
                'bullish_volume', 'bearish_volume', 'volume_price_conf',
            ]
            advice['volume_pred'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['volume_pred'] = "N/A"

        # ========== Sentiment ==========
        model = self._models.get('sentiment') if not MemoryCache else self._models.get('sentiment')
        if model:
            sent            = market_sentiment or {}
            fear_greed      = sent.get('fear_greed', 50)
            social_volume   = sent.get('social_volume', 1000)
            positive        = sent.get('positive_ratio', 0.33)
            negative        = sent.get('negative_ratio', 0.33)
            neutral_sent    = sent.get('neutral_ratio', 0.34)
            trending_score  = sent.get('trending_score', 0)
            news_sentiment  = sent.get('news_sentiment', 0)
            pos_neg_ratio   = positive / (negative + 0.001)
            sentiment_score = positive - negative
            fear_greed_norm = (fear_greed - 50) / 50
            is_fearful      = 1 if fear_greed < 30 else 0
            is_greedy       = 1 if fear_greed > 70 else 0
            high_social     = 1 if social_volume > 1000 else 0
            strong_positive = 1 if positive > 0.6 else 0
            strong_negative = 1 if negative > 0.6 else 0
            features = [
                fear_greed, social_volume, positive, negative, neutral_sent,
                trending_score, news_sentiment, pos_neg_ratio, sentiment_score,
                fear_greed_norm, is_fearful, is_greedy, high_social,
                strong_positive, strong_negative,
            ]
            names = [
                'fear_greed_index', 'social_volume', 'positive_ratio',
                'negative_ratio', 'neutral_ratio', 'trending_score',
                'news_sentiment', 'pos_neg_ratio', 'sentiment_score',
                'fear_greed_norm', 'is_fearful', 'is_greedy',
                'high_social', 'strong_positive', 'strong_negative',
            ]
            advice['sentiment'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['sentiment'] = "N/A"

        # ========== Candle Expert ==========
        model = self._models.get('candle_expert') if not MemoryCache else self._models.get('candle_expert')
        if model:
            candle_features         = self._extract_advanced_candle_features(analysis)
            features                = candle_features + [rsi, volume_ratio, 0.5, 0.5]
            names                   = self._get_candle_feature_names() + ['rsi', 'volume_ratio', 'tp_accuracy', 'sell_accuracy']
            advice['candle_expert'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['candle_expert'] = "N/A"

        # ========== Crypto News ==========
        model = self._models.get('crypto_news') if not MemoryCache else self._models.get('crypto_news')
        if model:
            news            = analysis.get('news', {})
            news_count      = float(news.get('news_count_24h', news.get('total', 0)) or 0)
            news_pos        = float(news.get('positive_news_count', news.get('positive', 0)) or 0)
            news_neg        = float(news.get('negative_news_count', news.get('negative', 0)) or 0)
            news_neutral    = float(news.get('neutral_news_count',  news.get('neutral',  0)) or 0)
            sentiment_avg   = float(news.get('news_sentiment_avg',  news.get('news_score', 0)) or 0)
            pos_neg_ratio   = news_pos / (news_neg + 0.001)
            news_sentiment  = (news_pos - news_neg) / (news_count + 0.001)
            high_news_vol   = 1 if news_count > 5 else 0
            strong_positive = 1 if news_pos > news_neg * 2 else 0
            strong_negative = 1 if news_neg > news_pos * 2 else 0
            features = [
                news_count, news_pos, news_neg, news_neutral, sentiment_avg,
                pos_neg_ratio, news_sentiment,
                high_news_vol, strong_positive, strong_negative,
            ]
            names = [
                'news_count_24h', 'positive_news_count', 'negative_news_count',
                'neutral_news_count', 'news_sentiment_avg',
                'pos_neg_ratio', 'news_sentiment',
                'high_news_volume', 'strong_positive', 'strong_negative',
            ]
            advice['crypto_news'] = _predict(model, features, names, is_sell_mode)
        else:
            advice['crypto_news'] = "N/A"

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
            self._return_conn(conn)
            return exists
        except Exception as e:
            print(f"⚠️ is_available error: {e}")
            return False

    def get_models_status(self):
        conn = None
        try:
            conn   = self._get_conn()
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
            return {
                row['model_name']: {
                    'accuracy'  : row['accuracy'],
                    'trained_at': str(row['trained_at']),
                }
                for row in results
            }
        except Exception as e:
            print(f"⚠️ get_models_status error: {e}")
            if conn:
                try:
                    self._pool.putconn(conn, close=True) if self._pool else conn.close()
                except Exception:
                    pass
            return {}

    def _get_feature_names_local(self):
        """✅ 40 features — بدون profit_magnitude و is_profitable"""
        return [
            # التقليدية (15)
            'rsi', 'macd', 'volume_ratio', 'price_momentum',
            'bb_position', 'atr_estimate', 'stochastic', 'ema_signal',
            'volume_strength', 'momentum_strength',
            'atr', 'ema_crossover', 'bid_ask_spread', 'volume_trend', 'price_change_1h',
            # السياق (4)
            'trade_quality_score', 'advisor_vote_consensus',
            'hours_held_normalized', 'is_trap_trade',
            # السوق والوقت (7)
            'btc_trend_normalized', 'is_bullish_market', 'hour_normalized',
            'is_asian_session', 'is_european_session', 'is_us_session', 'optimal_hold_score',
            # فيبوناتشي (2)
            'fib_score', 'fib_level_encoded',
            # Market Regime (4)
            'regime_score', 'regime_adx', 'volatility_ratio', 'position_multiplier',
            # Flash Crash (4)
            'flash_risk_score', 'flash_crash_detected', 'whale_dump_detected', 'cascade_risk_score',
            # Whale + Additional (4)
            'whale_confidence', 'sentiment_score', 'panic_score', 'optimism_penalty',
        ]

    def _calculate_features_local(self, data, trade=None):
        """✅ 40 features — بدون profit_magnitude و is_profitable"""
        try:
            full_data = {**data}
            if trade:
                trade_data = trade.get('data', {})
                if isinstance(trade_data, str):
                    trade_data = json.loads(trade_data)
                full_data = {**trade, **trade_data, **data}

            rsi             = float(full_data.get('rsi', 50) or 50)
            macd            = float(full_data.get('macd_diff', full_data.get('macd', 0)) or 0)
            volume_ratio    = float(full_data.get('volume_ratio', 1) or 1)
            price_momentum  = float(full_data.get('price_momentum', 0) or 0)
            bb_position     = (rsi - 30) / 40
            atr_estimate    = abs(price_momentum) * volume_ratio
            stochastic      = rsi
            ema_signal      = 1 if macd > 0 else -1
            volume_strength    = min(volume_ratio / 2.0, 2.0)
            momentum_strength  = abs(price_momentum) / 10.0
            atr             = float(full_data.get('atr', atr_estimate) or atr_estimate)
            ema_9           = float(full_data.get('ema_9', 0) or 0)
            ema_21          = float(full_data.get('ema_21', 0) or 0)
            ema_crossover   = 1 if ema_9 > ema_21 else -1
            bid_ask_spread  = float(full_data.get('bid_ask_spread', 0) or 0)
            price_change_1h = float(full_data.get('price_change_1h', 0) or 0)

            _vt = full_data.get('volume_trend', 0)
            if _vt == 'up':       volume_trend = 1.2
            elif _vt == 'down':   volume_trend = 0.8
            elif _vt == 'neutral':volume_trend = 0.0
            else:
                try:              volume_trend = float(_vt or 0)
                except Exception: volume_trend = 0.0

            return [
                # التقليدية (15)
                rsi, macd, volume_ratio, price_momentum,
                bb_position, atr_estimate, stochastic, ema_signal,
                volume_strength, momentum_strength,
                atr, ema_crossover, bid_ask_spread, volume_trend, price_change_1h,
                # السياق (4)
                3, 0.5, 0.5, 0,
                # السوق والوقت (7)
                0, 0, 0.5, 0, 0, 0, 0.5,
                # فيبوناتشي (2)
                0, 0,
                # Regime (4)
                0.5, 0.4, 1.0, 1.0,
                # Flash Crash (4)
                0, 0, 0, 0,
                # Whale + Additional (4)
                0, 0, 0, 0,
            ]
        except Exception:
            return [
                50, 0, 1, 0, 0.5, 1, 50, 0, 1, 0, 1, 0, 0, 0, 0,
                3, 0.5, 0.5, 0,
                0, 0, 0.5, 0, 0, 0, 0.5,
                0, 0,
                0.5, 0.4, 1.0, 1.0,
                0, 0, 0, 0,
                0, 0, 0, 0,
            ]

    def _extract_advanced_candle_features(self, analysis):
        try:
            candles = analysis.get('candles', [])
            if not candles or len(candles) < 3:
                return [0] * 56
            features = []
            last_7   = list(candles[-7:]) if len(candles) >= 7 else list(candles)
            while len(last_7) < 7:
                last_7.insert(0, {'open': 0, 'high': 0, 'low': 0, 'close': 0})
            for c in last_7:
                o  = float(c.get('open',  0) or 0)
                h  = float(c.get('high',  0) or 0)
                l  = float(c.get('low',   0) or 0)
                cl = float(c.get('close', 0) or 0)
                full_range         = (h - l) if (h - l) > 0 else 0.000001
                body_size          = abs(cl - o)
                body_ratio         = body_size / full_range
                upper_shadow_ratio = (h - max(o, cl)) / full_range
                lower_shadow_ratio = (min(o, cl) - l) / full_range
                direction          = 1 if cl > o else (-1 if cl < o else 0)
                is_doji            = 1 if body_ratio < 0.1 else 0
                is_long_body       = 1 if body_ratio > 0.7 else 0
                features.extend([body_ratio, upper_shadow_ratio, lower_shadow_ratio,
                                  direction, is_doji, is_long_body])
            if len(last_7) >= 3:
                c1, c2, c3 = last_7[-3], last_7[-2], last_7[-1]

                def _g(c, k):
                    try: return float(c.get(k, 0) or 0)
                    except: return 0.0

                body1 = abs(_g(c1,'close') - _g(c1,'open'))
                body2 = abs(_g(c2,'close') - _g(c2,'open'))
                body3 = abs(_g(c3,'close') - _g(c3,'open'))
                rel_size_2_1      = body2 / (body1 + 0.000001)
                rel_size_3_2      = body3 / (body2 + 0.000001)
                dir1 = 1 if _g(c1,'close') > _g(c1,'open') else -1
                dir2 = 1 if _g(c2,'close') > _g(c2,'open') else -1
                dir3 = 1 if _g(c3,'close') > _g(c3,'open') else -1
                consecutive_green = 1 if (dir1==1  and dir2==1  and dir3==1)  else 0
                consecutive_red   = 1 if (dir1==-1 and dir2==-1 and dir3==-1) else 0
                gap_2_1 = abs(_g(c2,'open') - _g(c1,'close')) / (_g(c1,'close') + 0.000001)
                gap_3_2 = abs(_g(c3,'open') - _g(c2,'close')) / (_g(c2,'close') + 0.000001)
                c3_upper = _g(c3,'high') - max(_g(c3,'open'), _g(c3,'close'))
                c3_lower = min(_g(c3,'open'), _g(c3,'close')) - _g(c3,'low')
                c3_range = _g(c3,'high') - _g(c3,'low')
                c3_range = c3_range if c3_range > 0 else 0.000001
                upper_wick_dominance = c3_upper / c3_range
                lower_wick_dominance = c3_lower / c3_range
                is_star       = 1 if (body3 < 0.1 * c3_range and gap_3_2 > 0.005) else 0
                high_3        = max(_g(c1,'high'), _g(c2,'high'), _g(c3,'high'))
                low_3         = min(_g(c1,'low'),  _g(c2,'low'),  _g(c3,'low'))
                breakout_up   = 1 if _g(c3,'close') > high_3 * 1.002 else 0
                breakout_down = 1 if _g(c3,'close') < low_3  * 0.998 else 0
                features.extend([
                    rel_size_2_1, rel_size_3_2,
                    consecutive_green, consecutive_red,
                    gap_2_1, gap_3_2,
                    upper_wick_dominance, lower_wick_dominance,
                    is_star, breakout_up, breakout_down,
                    dir1, dir2, dir3,
                ])
            else:
                features.extend([0] * 14)
            return features
        except Exception as e:
            print(f"⚠️ Candle feature extraction error: {e}")
            return [0] * 56

    def _get_candle_feature_names(self):
        names = []
        for i in range(7, 0, -1):
            names.extend([
                f'c{i}_body_ratio', f'c{i}_upper_shadow', f'c{i}_lower_shadow',
                f'c{i}_direction',  f'c{i}_is_doji',      f'c{i}_is_long_body',
            ])
        names.extend([
            'rel_size_2_1', 'rel_size_3_2',
            'consecutive_green', 'consecutive_red',
            'gap_2_1', 'gap_3_2',
            'upper_wick_dominance', 'lower_wick_dominance',
            'is_star', 'breakout_up', 'breakout_down',
            'dir1', 'dir2', 'dir3',
        ])
        return names

    def _analyze_candles_from_data(self, analysis):
        try:
            candles = analysis.get('candles', [])
            if not candles or len(candles) < 2:
                return {'bullish': 0, 'bearish': 0, 'neutral': 1}
            bullish_score = 0
            bearish_score = 0
            neutral_score = 0
            for i, candle in enumerate(candles):
                if not isinstance(candle, dict):
                    continue
                o  = float(candle.get('open',  0) or 0)
                cl = float(candle.get('close', 0) or 0)
                h  = float(candle.get('high',  0) or 0)
                l  = float(candle.get('low',   0) or 0)
                if o == 0 or cl == 0:
                    continue
                body         = abs(cl - o)
                total_range  = h - l
                upper_shadow = h - max(o, cl)
                lower_shadow = min(o, cl) - l
                if total_range == 0:
                    continue
                body_ratio = body / total_range
                if body == 0:
                    body = 0.0001
                is_green = cl > o
                is_red   = cl < o

                if lower_shadow > body * 2 and upper_shadow < body * 0.3 and body_ratio < 0.4:
                    bullish_score += 3
                if upper_shadow > body * 2 and lower_shadow < body * 0.3 and body_ratio < 0.4 and is_green:
                    bullish_score += 2
                if i > 0 and is_green:
                    prev       = candles[i-1]
                    prev_close = float(prev.get('close', 0) or 0)
                    prev_open  = float(prev.get('open',  0) or 0)
                    prev_body  = abs(prev_close - prev_open)
                    if prev_close < prev_open and cl > prev_open and o < prev_close and body > prev_body * 1.2:
                        bullish_score += 4
                    prev_mid = (prev_open + prev_close) / 2
                    if prev_close < prev_open and o < prev_close and cl > prev_mid:
                        bullish_score += 3
                if i >= 2:
                    p1       = candles[i-1]
                    p2       = candles[i-2]
                    p2_close = float(p2.get('close', 0) or 0)
                    p2_open  = float(p2.get('open',  0) or 0)
                    p1_body  = abs(float(p1.get('close', 0) or 0) - float(p1.get('open', 0) or 0))
                    if p2_close < p2_open and p1_body < body * 0.3 and is_green:
                        bullish_score += 5
                    c1_g = float(candles[i-2].get('close',0)or 0) > float(candles[i-2].get('open',0)or 0)
                    c2_g = float(candles[i-1].get('close',0)or 0) > float(candles[i-1].get('open',0)or 0)
                    if c1_g and c2_g and is_green:
                        if float(candles[i-1].get('close',0)or 0) > float(candles[i-2].get('close',0)or 0) and cl > float(candles[i-1].get('close',0)or 0):
                            bullish_score += 4

                if upper_shadow > body * 2 and lower_shadow < body * 0.3 and body_ratio < 0.4 and is_red:
                    bearish_score += 3
                if lower_shadow > body * 2 and upper_shadow < body * 0.3 and body_ratio < 0.4 and is_red:
                    bearish_score += 2
                if i > 0 and is_red:
                    prev       = candles[i-1]
                    prev_close = float(prev.get('close', 0) or 0)
                    prev_open  = float(prev.get('open',  0) or 0)
                    prev_body  = abs(prev_close - prev_open)
                    if prev_close > prev_open and o > prev_close and cl < prev_open and body > prev_body * 1.2:
                        bearish_score += 4
                    prev_mid = (prev_open + prev_close) / 2
                    if prev_close > prev_open and o > prev_close and cl < prev_mid:
                        bearish_score += 3
                if i >= 2:
                    p1       = candles[i-1]
                    p2       = candles[i-2]
                    p2_close = float(p2.get('close', 0) or 0)
                    p2_open  = float(p2.get('open',  0) or 0)
                    p1_body  = abs(float(p1.get('close', 0) or 0) - float(p1.get('open', 0) or 0))
                    if p2_close > p2_open and p1_body < body * 0.3 and is_red:
                        bearish_score += 5
                    c1_r = float(candles[i-2].get('close',0)or 0) < float(candles[i-2].get('open',0)or 0)
                    c2_r = float(candles[i-1].get('close',0)or 0) < float(candles[i-1].get('open',0)or 0)
                    if c1_r and c2_r and is_red:
                        if float(candles[i-1].get('close',0)or 0) < float(candles[i-2].get('close',0)or 0) and cl < float(candles[i-1].get('close',0)or 0):
                            bearish_score += 4

                if body < total_range * 0.1:
                    neutral_score += 2
                if 0.2 < body_ratio < 0.4 and upper_shadow > body * 0.8 and lower_shadow > body * 0.8:
                    neutral_score += 1
                if is_green and body_ratio > 0.6:
                    bullish_score += 0.5
                if is_red and body_ratio > 0.6:
                    bearish_score += 0.5

            total = bullish_score + bearish_score + neutral_score
            if total == 0:
                return {'bullish': 0, 'bearish': 0, 'neutral': 1}
            b_r = bullish_score / total
            br_r = bearish_score / total
            n_r  = neutral_score / total
            if b_r > 0.5:    return {'bullish': 1, 'bearish': 0, 'neutral': 0}
            elif br_r > 0.5: return {'bullish': 0, 'bearish': 1, 'neutral': 0}
            elif n_r > 0.4:  return {'bullish': 0, 'bearish': 0, 'neutral': 1}
            else:
                if bullish_score > bearish_score: return {'bullish': 1, 'bearish': 0, 'neutral': 0}
                elif bearish_score > bullish_score: return {'bullish': 0, 'bearish': 1, 'neutral': 0}
                else: return {'bullish': 0, 'bearish': 0, 'neutral': 1}
        except Exception as e:
            print(f"⚠️ Candle analysis error: {e}")
            return {'bullish': 0, 'bearish': 0, 'neutral': 1}

    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, signal_type='sell'):
        try:
            pass
        except Exception:
            pass
