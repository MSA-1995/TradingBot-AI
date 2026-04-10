"""
🧠 Deep Learning Client V3 - للبوت الرئيسي
يحمل موديلات LightGBM المدربة من قاعدة البيانات ويستخدمها للتصويت
"""
import os
import json
import pickle
import gzip
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

ADVISORS_LEARNING_FILE = 'data/advisors_learning.json'

# ✅ إصلاح: حذف الـ leaky features (معروفة فقط بعد إغلاق الصفقة)
# يجب أن تتطابق مع SAFE_NAMES في models.py
BASE_FEATURE_NAMES = [
    'rsi', 'macd', 'volume_ratio', 'price_momentum',
    'bb_position', 'atr_estimate', 'stochastic', 'ema_signal',
    'volume_strength', 'momentum_strength',
    'atr', 'ema_crossover', 'bid_ask_spread', 'volume_trend', 'price_change_1h',
    # ❌ محذوف: trade_quality_score, is_trap_trade, profit_magnitude, hours_held_normalized, is_profitable
    'advisor_vote_consensus',
    'btc_trend_normalized', 'is_bullish_market', 'hour_normalized',
    'is_asian_session', 'is_european_session', 'is_us_session',
    'optimal_hold_score', 'fib_score', 'fib_level_encoded',
    'regime_score', 'regime_adx', 'volatility_ratio', 'position_multiplier',
    'flash_risk_score', 'flash_crash_detected', 'whale_dump_detected', 'cascade_risk_score',
    'whale_confidence', 'atr_value', 'sentiment_score', 'panic_score', 'optimism_penalty'
]


class DeepLearningClientV2:
    def __init__(self, database_url):
        print("🔄 Initializing DeepLearningClientV2...")
        self.database_url = database_url
        self.conn = None
        self._db_params = None
        self._pool = None  # ✅ Connection Pool
        self._models = {}        # {model_name: model_object}
        self._model_accuracy = {} # {model_name: accuracy}
        self._model_trained_at = {} # {model_name: trained_at}
        self._last_models_check = None  # آخر فحص للنماذج
        try:
            print("🔄 Connecting to DB...")
            self._connect_db()
            print("✅ DB connected")
            print("🔄 Loading learning data...")
            self._load_learning_data()
            print("✅ Learning data loaded")
            print("🔄 Loading all models from DB...")
            self._load_all_models_from_db()
            print("✅ All models loaded")
            self._print_models_status()
            print("🧠 Deep Learning Client V3 initialized (LightGBM)")
        except Exception as e:
            print(f"❌ Error in DeepLearningClientV2 init: {e}")
            raise
    
    def _load_learning_data(self):
        """تحميل بيانات تعلم المستشارين"""
        os.makedirs('data', exist_ok=True)
        if os.path.exists(ADVISORS_LEARNING_FILE):
            with open(ADVISORS_LEARNING_FILE, 'r') as f:
                self.learning_data = json.load(f)
        else:
            self.learning_data = {
                'exit': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 0.5},
                'mtf': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 0},
                'risk': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.0},
                'pattern': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 0},
                'cnn': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.0},
                'anomaly': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.5},
                'liquidity': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.1}
            }
    
    def _save_learning_data(self):
        """حفظ بيانات تعلم المستشارين"""
        with open(ADVISORS_LEARNING_FILE, 'w') as f:
            json.dump(self.learning_data, f, indent=2, ensure_ascii=False)
    
    def _connect_db(self):
        """إنشاء Connection Pool مستقر مع TCP Keepalives"""
        from psycopg2.pool import ThreadedConnectionPool
        try:
            parsed = urlparse(self.database_url)
            # Handle case where password might be None
            password = unquote(parsed.password) if parsed.password else None
            self._db_params = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path[1:],
                'user': parsed.username,
                'password': password,
                'sslmode': 'require',
                'connect_timeout': 15,
                # ✅ TCP Keepalives تمنع SSL drop عند التحميل المتوازي
                'keepalives': 1,
                'keepalives_idle': 60,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            }
            self._pool = ThreadedConnectionPool(3, 12, **self._db_params)
            # للتوافق مع الكود القديم
            conn = self._pool.getconn()
            self.conn = conn
            self._pool.putconn(conn)
        except Exception as e:
            print(f"⚠️ DL Client V2 DB error: {e}")
            self.conn = None
            self._pool = None

    def _get_conn(self):
        """جلب connection صحيح من الـ Pool"""
        try:
            if self._pool:
                conn = self._pool.getconn()
                if conn and not conn.closed:
                    return conn
                try:
                    self._pool.putconn(conn, close=True)
                except Exception:
                    pass
            # fallback: direct connection
            if self._db_params:
                return psycopg2.connect(**self._db_params)
            return None
        except Exception as e:
            print(f"⚠️ DL Client V2 reconnect error: {e}")
            return None

    def _return_conn(self, conn):
        """إرجاع connection للـ Pool بعد الاستخدام"""
        try:
            if self._pool and conn:
                self._pool.putconn(conn)
        except Exception:
            pass
    
    def get_model_data(self, model_name):
        """يجلب البيانات الثنائية (binary data) لنموذج معين من قاعدة البيانات."""
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                print(f"⚠️ DL Client: No DB connection to get model data for {model_name}.")
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
                print(f"⚠️ DL Client: Model data for '{model_name}' not found in the database.")
                return None

        except Exception as e:
            print(f"❌ DL Client: Error getting model data for {model_name}: {e}")
            if conn:
                try:
                    self._pool.putconn(conn, close=True) if self._pool else conn.close()
                except Exception:
                    pass
            return None

    def _load_single_model(self, name):
        """تحميل موديل واحد - connection مستقل لكل محاولة مع keepalives كاملة"""
        import time
        max_retries = 3
        for attempt in range(max_retries):
            conn = None
            try:
                # ✅ connection مستقل لكل موديل مع keepalives — أكثر استقراراً من الـ Pool
                # عند تحميل بيانات ثقيلة (MBs) الـ Pool يسبب SSL drop لأن الـ connection
# يبقى مشغولاً وقت طويل ويُحسب كـ idle من طرف الـ server
                # ✅ نسخ الـ params وتعديل keepalives بدون تكرار
                if self._db_params is None:
                    print(f"⚠️ DL Client: No DB params available for loading model {name}")
                    return
                _params = self._db_params.copy()
                # ✅ تحسين keepalives لمنع إغلاق الاتصالات أثناء تحميل النماذج الكبيرة - أكثر عدوانية
                _params['keepalives'] = 1
                _params['keepalives_idle'] = 5    # فحص كل 5 ثوانٍ بدلاً من 10
                _params['keepalives_interval'] = 1  # فحص كل ثانية بدلاً من ثانيتين
                _params['keepalives_count'] = 3     # تقليل عدد المحاولات الفاشلة أكثر
                # ✅ إضافة TCP user timeout و statement timeout لمنع التعليق indefinitely
                # زيادة الوقت بشكل كبير للنماذج الكبيرة مع تقليل keepalives أكثر عدوانية
                _params['options'] = '-c statement_timeout=300000 -c tcp_user_timeout=120000'
                conn = psycopg2.connect(**_params)

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                # جلب metadata أولاً بدون البيانات الثقيلة
                cursor.execute("""
                    SELECT accuracy, trained_at,
                           octet_length(model_data) as data_size
                    FROM dl_models_v2
                    WHERE model_name = %s
                    ORDER BY trained_at DESC
                    LIMIT 1
                """, (name,))
                meta = cursor.fetchone()

                if not meta:
                    cursor.close()
                    conn.close()
                    return  # موديل غير موجود في DB

                data_size = meta.get('data_size', 0) or 0

                # جلب البيانات الفعلية في query منفصلة
                cursor.execute("""
                    SELECT model_data
                    FROM dl_models_v2
                    WHERE model_name = %s
                    ORDER BY trained_at DESC
                    LIMIT 1
                """, (name,))
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                conn = None

                if result and result.get('model_data'):
                    raw_data = result['model_data']
                    if isinstance(raw_data, memoryview):
                        raw_data = bytes(raw_data)

                    model = None
                    try:
                        decompressed = gzip.decompress(raw_data)
                        model = pickle.loads(decompressed)
                    except Exception:
                        try:
                            model = pickle.loads(raw_data)
                        except Exception as fallback_err:
                            print(f"❌ Final load failed for {name}: {fallback_err}")

                    self._models[name] = model
                    self._model_accuracy[name] = float(meta.get('accuracy', 0) or 0)
                    self._model_trained_at[name] = str(meta.get('trained_at', 'N/A'))
                return  # نجح
            except Exception as e:
                print(f"❌ DL Client: Error loading model {name} (attempt {attempt+1}/{max_retries}): {e}")
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # backoff: 1s, 2s

    def _load_all_models_from_db(self):
        """تحميل جميع الموديلات — بشكلsequential لتجنب SSL drop تمامًا"""
        from datetime import datetime
        import time

        model_names = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern',
            'liquidity', 'chart_cnn', 'volume_pred', 'meta_trading',
            'sentiment', 'crypto_news'
        ]
        loaded = 0

        # تحميل النماذج واحدة تلو الأخرى لتجنب أي ضغط على الاتصال
        for i, name in enumerate(model_names):
            try:
                self._load_single_model(name)
                if name in self._models and self._models[name] is not None:
                    loaded += 1
                    print(f"✅ Loaded model: {name}")
                else:
                    print(f"⚠️ Model {name} not found or failed to load")
            except Exception as e:
                print(f"❌ Failed to load model {name}: {e}")
            
            # تأخير قصير بين كل تحميل نموذج
            if i < len(model_names) - 1:  # لا انتظر بعد النموذج الأخير
                time.sleep(1)

        self._last_models_check = datetime.now()
        print(f"🧠 Loaded {loaded}/{len(model_names)} trained models from database")

    def _print_models_status(self):
        """طباعة حالة جميع الموديلات المدربة عند بداية التشغيل"""
        print("\nTrained Models:")
        loaded_count = len(self._models)
        all_models = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern',
            'liquidity', 'chart_cnn', 'volume_pred', 'meta_learner',
            'sentiment', 'crypto_news'
        ]
        
        for name in all_models:
            if name in self._models:
                acc = self._model_accuracy.get(name, 0)
                if acc > 0:
                    print(f"  {name}: {acc*100:.1f}%")
                else:
                    print(f"  {name}: No data")
            else:
                print(f"  {name}: Not loaded")
        
        print("")

    def check_for_updates(self):
        """
        يفحص إذا في نموذج محدث في الداتابيز مقارنة بوقت التحميل الحالي.
        يرجع True إذا في تحديث → يستدعي restart.
        يرجع False إذا لا شيء جديد → يكمل طبيعي.
        """
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
                print("✅ No active models in DB to compare.")
                return False

            for row in results:
                name = row['model_name']
                db_trained_at = str(row['trained_at'])
                current_loaded_at = self._model_trained_at.get(name)

                if not current_loaded_at:
                    print(f"🆕 New model found in DB (not loaded): {name}")
                    return True

                if db_trained_at != current_loaded_at:
                    print(f"🔄 Model update detected: {name}")
                    print(f"   DB: {db_trained_at} | Loaded: {current_loaded_at}")
                    return True

            print("✅ All models up to date, no restart needed.")
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
        """جلب دقة الموديل المدرب"""
        return self._model_accuracy.get(model_name, 0)

    def _prepare_base_features(self, rsi, macd, volume_ratio, price_momentum,
                                profit=0, hours_held=24, liquidity_metrics=None,
                                market_sentiment=None, candle_analysis=None,
                                extra_features=None):
        """تحضير الـ BASE features للتنبؤ - بدون الـ leaky features"""

        # حساب القيم الأساسية
        bb_position = (rsi - 30) / 40
        atr_estimate = abs(price_momentum) * volume_ratio
        stochastic = rsi
        ema_signal = 1 if macd > 0 else -1
        volume_strength = min(volume_ratio / 2.0, 2.0)
        momentum_strength = abs(price_momentum) / 10.0
        atr = atr_estimate
        ema_crossover = 1 if macd > 0 else -1
        bid_ask_spread = 0
        volume_trend = 1 if volume_ratio > 1.2 else (-1 if volume_ratio < 0.8 else 0)
        price_change_1h = price_momentum
        
        # ✅ باقي من ميزات التعلم المباشر (غير leaky)
        advisor_vote_consensus = 0.5
        # ❌ محذوف: trade_quality_score, is_trap_trade, profit_magnitude, hours_held_normalized, is_profitable
        
        # السوق والوقت
        btc_change = 0
        if market_sentiment:
            btc_change = market_sentiment.get('btc_change_1h', 0)
        btc_trend_normalized = max(-1.0, min(1.0, btc_change / 5.0))
        is_bullish_market = 1 if btc_change > 1.0 else 0
        
        from datetime import datetime
        hour_of_day = datetime.now().hour
        hour_normalized = hour_of_day / 24.0
        is_asian_session = 1 if 0 <= hour_of_day <= 8 else 0
        is_european_session = 1 if 8 < hour_of_day <= 16 else 0
        is_us_session = 1 if 16 < hour_of_day <= 24 else 0
        optimal_hold_score = 0.5
        
        # فيبوناتشي (defaults)
        fib_score = 0
        fib_level_encoded = 0
        
        # Market Regime (defaults)
        regime_score = 0.5
        regime_adx = 0.4
        volatility_ratio = 1.0
        position_multiplier = 1.0
        
        # Flash Crash (defaults)
        flash_risk_score = 0
        flash_crash_detected = 0
        whale_dump_detected = 0
        cascade_risk_score = 0

        # الـ 5 features الإضافية
        whale_confidence = 0
        atr_value = 0
        sentiment_score = 0
        panic_score = 0
        optimism_penalty = 0
        
        base_features = [
            rsi, macd, volume_ratio, price_momentum,
            bb_position, atr_estimate, stochastic, ema_signal,
            volume_strength, momentum_strength,
            atr, ema_crossover, bid_ask_spread, volume_trend, price_change_1h,
            # ✅ بدون leaky features
            advisor_vote_consensus,
            btc_trend_normalized, is_bullish_market, hour_normalized,
            is_asian_session, is_european_session, is_us_session,
            optimal_hold_score, fib_score, fib_level_encoded,
            regime_score, regime_adx, volatility_ratio, position_multiplier,
            flash_risk_score, flash_crash_detected, whale_dump_detected, cascade_risk_score,
            whale_confidence, atr_value, sentiment_score, panic_score, optimism_penalty
        ]
        
        if extra_features:
            base_features.extend(extra_features)
        
        return base_features

    def _predict_buy(self, model_name, features, feature_names):
        """
        التنبؤ باستخدام الموديل المدرب من الداتابيز.
        يرجع 1 أو 0. يرجع None فقط إذا النموذج غير محمل أو فشل كلياً.
        """
        model = self._models.get(model_name)
        if model is None:
            return None

        try:
            X = pd.DataFrame([features], columns=feature_names)
            proba = model.predict_proba(X)[0]
            score = float(proba[1]) if len(proba) > 1 else float(proba[0])

            # ✅ عتبة تكيّفية - exit/pattern/liquidity كانوا دايماً 0
            # ✅ العتبات الطبيعية بعد اصلاح مشكلة Label Leakage
            thresholds = {
                "exit":      0.5,
                "pattern":   0.5,
                "liquidity": 0.5,
                "risk":      0.5,
                "anomaly":   0.5,
            }
            threshold = thresholds.get(model_name, 0.30)
            vote = 1 if score > threshold else 0
            # print(f"   🔍 {model_name}: proba={score:.3f} thr={threshold:.4f} -> {vote}")
            return vote
        except Exception as e:
            print(f"⚠️ Predict error for '{model_name}': {e}")
            return None

    def _predict_proba(self, model_name, features, feature_names):
        """التنبؤ بالاحتمالية - يرجّع probability للـ class 1"""
        model = self._models.get(model_name)
        if model is None:
            return None
        
        try:
            X = pd.DataFrame([features], columns=feature_names)
            proba = model.predict_proba(X)[0]
            return float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception as e:
            print(f"⚠️ Proba error for {model_name}: {e}")
            return None

    
    def get_mtf_prediction(self, rsi, macd, volume_ratio, price_momentum):
        """
        Multi-Timeframe: توقع الترند
        Returns: confidence_boost (-10 to +10)
        """
        accuracy = self.get_model_accuracy('mtf')
        
        if accuracy < 0.55:
            return 0
        
        # حساب Boost بناءً على الدقة
        if accuracy >= 0.70:
            boost = 8
        elif accuracy >= 0.65:
            boost = 5
        elif accuracy >= 0.60:
            boost = 3
        else:
            boost = 2
        
        # تعديل حسب المؤشرات
        if rsi < 30 and macd > 0:
            return boost
        elif rsi > 70 and macd < 0:
            return -boost
        else:
            return boost // 2
    
    def get_risk_prediction(self, rsi, volume_ratio, confidence, price_momentum):
        """
        Risk Manager: تقييم المخاطر
        Returns: risk_level ('low', 'medium', 'high'), confidence_adjustment
        """
        accuracy = self.get_model_accuracy('risk')
        
        if accuracy < 0.55:
            return {'risk_level': 'medium', 'confidence_adjustment': 0}
        
        # تقييم المخاطر
        risk_score = 0
        
        if rsi > 70:
            risk_score += 2
        if volume_ratio > 2.5:
            risk_score += 2
        if confidence < 65:
            risk_score += 1
        
        if risk_score >= 4:
            return {'risk_level': 'high', 'confidence_adjustment': -5}
        elif risk_score >= 2:
            return {'risk_level': 'medium', 'confidence_adjustment': 0}
        else:
            return {'risk_level': 'low', 'confidence_adjustment': 3}
    
    def get_anomaly_prediction(self, rsi, macd, volume_ratio, price_momentum):
        """
        Anomaly Detector: كشف الحالات الشاذة - نظام نقاط متوازن
        Returns: is_anomaly (bool), severity ('low', 'medium', 'high'), confidence_adjustment
        """
        accuracy = self.get_model_accuracy('anomaly')
        
        if accuracy < 0.55:
            return {'is_anomaly': False, 'severity': 'low', 'confidence_adjustment': 0}
        
        # كشف الشذوذ - نظام نقاط متوازن
        anomaly_score = 0
        
        # شذوذ خفيف
        if rsi < 25 or rsi > 75:
            anomaly_score += 1
        
        # شذوذ متوسط
        if volume_ratio > 2.5:
            anomaly_score += 2
        
        # شذوذ قوي
        if rsi < 15 or rsi > 85:
            anomaly_score += 3
        if volume_ratio > 4.0:
            anomaly_score += 3
        if abs(macd) > 20:
            anomaly_score += 2
        
        # حساب التعديل بناءً على الدقة
        boost_multiplier = 1.0
        if accuracy >= 0.75:
            boost_multiplier = 1.5
        elif accuracy >= 0.65:
            boost_multiplier = 1.2
        
        # القرار النهائي
        if anomaly_score >= 5:
            # شذوذ قوي جداً - تحذير قوي
            adjustment = int(-10 * boost_multiplier)
            return {'is_anomaly': True, 'severity': 'high', 'confidence_adjustment': adjustment}
        elif anomaly_score >= 3:
            # شذوذ متوسط - تحذير متوسط
            adjustment = int(-5 * boost_multiplier)
            return {'is_anomaly': True, 'severity': 'medium', 'confidence_adjustment': adjustment}
        elif anomaly_score >= 1:
            # شذوذ خفيف - تحذير خفيف
            adjustment = int(-2 * boost_multiplier)
            return {'is_anomaly': True, 'severity': 'low', 'confidence_adjustment': adjustment}
        else:
            # طبيعي
            return {'is_anomaly': False, 'severity': 'normal', 'confidence_adjustment': 0}
    
    def get_exit_prediction(self, rsi, macd, confidence, price_momentum, profit_percent):
        """
        Exit Strategy: متى نبيع؟ (غير مستخدم - البيع عبر التصويت فقط)
        Returns: should_exit (bool), reason, confidence_boost
        """
        # هذه الدالة غير مستخدمة - البيع يتم عبر vote_sell_now فقط
        return {'should_exit': False, 'reason': 'Hold', 'confidence_boost': 0}
    
    def get_pattern_prediction(self, rsi, macd, volume_ratio, price_momentum, confidence):
        """
        Pattern Recognition: التعرف على الأنماط
        Returns: pattern_type ('success', 'trap', 'neutral'), confidence_adjustment
        """
        accuracy = self.get_model_accuracy('pattern')
        
        if accuracy < 0.55:
            return {'pattern_type': 'neutral', 'confidence_adjustment': 0}
        
        # تحليل النمط
        pattern_score = 0
        
        if rsi < 30 and macd > 0 and volume_ratio > 1.5:
            pattern_score += 3  # نمط ناجح
        elif rsi > 70 and macd < 0:
            pattern_score -= 3  # فخ
        
        if pattern_score >= 2:
            return {'pattern_type': 'success', 'confidence_adjustment': 5}
        elif pattern_score <= -2:
            return {'pattern_type': 'trap', 'confidence_adjustment': -10}
        else:
            return {'pattern_type': 'neutral', 'confidence_adjustment': 0}
    
    def get_ranking_prediction(self, symbol):
        """
        Coin Ranking: تقييم العملة (قديم - سيتم استبداله بـ Liquidity)
        Returns: rank_score (0-100), should_trade (bool)
        """
        accuracy = self.get_model_accuracy('ranking')
        
        if accuracy < 0.55:
            return {'rank_score': 50, 'should_trade': True, 'confidence_adjustment': 0}
        
        # هنا يمكن إضافة منطق أكثر تعقيداً
        # حالياً نعتمد على الدقة فقط
        
        if accuracy >= 0.70:
            return {'rank_score': 80, 'should_trade': True, 'confidence_adjustment': 5}
        elif accuracy >= 0.60:
            return {'rank_score': 65, 'should_trade': True, 'confidence_adjustment': 2}
        else:
            return {'rank_score': 50, 'should_trade': True, 'confidence_adjustment': 0}
    
    def get_liquidity_prediction(self, liquidity_metrics):
        """
        Liquidity Analyzer: تحليل السيولة من Order Book
        Returns: liquidity_quality, should_trade, confidence_adjustment
        """
        accuracy = self.get_model_accuracy('liquidity')
        
        if accuracy < 0.55 or not liquidity_metrics:
            return {'liquidity_quality': 'medium', 'should_trade': True, 'confidence_adjustment': 0}
        
        # استخراج المقاييس
        liquidity_score = liquidity_metrics.get('liquidity_score', 50)
        spread_percent = liquidity_metrics.get('spread_percent', 0.1)
        depth_ratio = liquidity_metrics.get('depth_ratio', 1.0)
        price_impact = liquidity_metrics.get('price_impact', 0.5)
        volume_consistency = liquidity_metrics.get('volume_consistency', 50)
        
        # تقييم السيولة
        quality_score = 0
        
        # 1. Liquidity Score (0-100)
        if liquidity_score >= 80:
            quality_score += 3
        elif liquidity_score >= 60:
            quality_score += 1
        elif liquidity_score < 40:
            quality_score -= 2
        
        # 2. Spread
        if spread_percent < 0.1:
            quality_score += 2
        elif spread_percent > 0.5:
            quality_score -= 3
        
        # 3. Depth Ratio (التوازن)
        if 0.8 <= depth_ratio <= 1.3:
            quality_score += 2
        elif depth_ratio < 0.6 or depth_ratio > 1.6:
            quality_score -= 2
        
        # 4. Price Impact
        if price_impact < 0.2:
            quality_score += 2
        elif price_impact > 1.0:
            quality_score -= 3
        
        # 5. Volume Consistency
        if volume_consistency >= 70:
            quality_score += 1
        elif volume_consistency < 40:
            quality_score -= 1
        
        # حساب التعديل بناءً على الدقة
        boost_multiplier = 1.0
        if accuracy >= 0.75:
            boost_multiplier = 1.5
        elif accuracy >= 0.65:
            boost_multiplier = 1.2
        
        # القرار النهائي
        if quality_score >= 6:
            adjustment = int(8 * boost_multiplier)
            return {'liquidity_quality': 'excellent', 'should_trade': True, 'confidence_adjustment': adjustment}
        elif quality_score >= 3:
            adjustment = int(4 * boost_multiplier)
            return {'liquidity_quality': 'good', 'should_trade': True, 'confidence_adjustment': adjustment}
        elif quality_score >= 0:
            return {'liquidity_quality': 'medium', 'should_trade': True, 'confidence_adjustment': 0}
        elif quality_score >= -3:
            adjustment = int(-5 * boost_multiplier)
            return {'liquidity_quality': 'poor', 'should_trade': True, 'confidence_adjustment': adjustment}
        else:
            adjustment = int(-10 * boost_multiplier)
            return {'liquidity_quality': 'very_poor', 'should_trade': False, 'confidence_adjustment': adjustment}
    
    def get_chart_cnn_prediction(self, rsi, macd, volume_ratio, price_momentum):
        """
        Chart Pattern Analyzer (CNN): تحليل أنماط الشارت
        Returns: pattern_detected, confidence_adjustment
        """
        accuracy = self.get_model_accuracy('chart_cnn')
        
        if accuracy < 0.55:
            return {'pattern_detected': 'neutral', 'confidence_adjustment': 0}
        
        # تحليل النمط البصري
        pattern_score = 0
        
        # نمط صاعد
        if rsi < 35 and macd > 0 and volume_ratio > 1.3:
            pattern_score += 3
        
        # نمط هابط
        if rsi > 65 and macd < 0:
            pattern_score -= 2
        
        # حساب التعديل بناءً على الدقة
        if accuracy >= 0.80:
            boost_multiplier = 1.5
        elif accuracy >= 0.70:
            boost_multiplier = 1.2
        else:
            boost_multiplier = 1.0
        
        if pattern_score >= 2:
            adjustment = int(5 * boost_multiplier)
            return {'pattern_detected': 'bullish', 'confidence_adjustment': adjustment}
        elif pattern_score <= -2:
            adjustment = int(-8 * boost_multiplier)
            return {'pattern_detected': 'bearish', 'confidence_adjustment': adjustment}
        else:
            return {'pattern_detected': 'neutral', 'confidence_adjustment': 0}
    
    def vote_tp_target(self, rsi, macd, volume_ratio, price_momentum, confidence):
        """
        المستشارين يصوتون على TP (Take Profit)
        Returns: tp_votes (dict with each consultant's vote)
        """
        votes = {}
        
        # Exit Strategy vote (0.5% - 10%)
        votes['exit'] = min(max(2.0 + (confidence - 60) * 0.1, 0.5), 10.0)
        
        # MTF vote
        if macd > 0:
            votes['mtf'] = min(max(3.0 + (volume_ratio - 1) * 2, 0.5), 10.0)
        else:
            votes['mtf'] = 2.0
        
        # Risk vote (conservative)
        votes['risk'] = min(max(1.5 if rsi > 70 else 2.5, 0.5), 10.0)
        
        # Pattern vote
        votes['pattern'] = min(max(2.5 + (confidence - 65) * 0.08, 0.5), 10.0)
        
        # CNN vote
        votes['cnn'] = min(max(2.0 + abs(macd) * 0.2, 0.5), 10.0)
        
        # Anomaly vote (conservative if anomaly detected)
        votes['anomaly'] = min(max(1.8 if rsi > 75 else 2.3, 0.5), 10.0)
        
        # Ranking vote
        votes['ranking'] = min(max(2.8, 0.5), 10.0)
        
        return votes
    
    def vote_amount(self, rsi, macd, volume_ratio, confidence, risk_vote=None):
        """
        المستشارين + Risk Manager يصوتون على المبلغ ($12 - $20)
        Returns: amount_votes (dict with each consultant's vote)
        """
        votes = {}
        
        # Exit Strategy vote
        votes['exit'] = 15.0
        
        # MTF vote (aggressive if strong trend)
        if macd > 5:
            votes['mtf'] = min(18.0, 20.0)
        else:
            votes['mtf'] = 14.0
        
        # Risk vote (conservative)
        votes['risk'] = 13.0 if rsi > 70 else 16.0
        
        # Pattern vote
        votes['pattern'] = 16.0
        
        # CNN vote
        votes['cnn'] = 15.0
        
        # Anomaly vote
        votes['anomaly'] = 13.5
        
        # Ranking vote
        votes['ranking'] = 17.0
        
        # Risk Manager vote (مستشار ثامن - Kelly Criterion)
        if risk_vote is not None:
            votes['risk_manager'] = max(12.0, min(20.0, risk_vote))
        
        # Ensure all votes are within bounds ($12 - $20)
        for key in votes:
            votes[key] = max(12.0, min(20.0, votes[key]))
        
        return votes
    
    def vote_stop_loss(self, rsi, macd, volume_ratio, confidence, risk_vote=None):
        """
        المستشارين + Risk Manager يصوتون على SL (Stop Loss: -0.1% to -2%)
        Returns: sl_votes (dict with each consultant's vote)
        """
        votes = {}
        
        # Exit Strategy vote
        votes['exit'] = -1.5
        
        # MTF vote (patient if strong trend)
        if macd > 0:
            votes['mtf'] = -2.0  # patient
        else:
            votes['mtf'] = -1.3
        
        # Risk vote (strict)
        votes['risk'] = -0.8 if rsi > 70 else -1.5
        
        # Pattern vote
        votes['pattern'] = -1.8
        
        # CNN vote
        votes['cnn'] = -1.6
        
        # Anomaly vote (strict if anomaly)
        votes['anomaly'] = -1.0
        
        # Ranking vote
        votes['ranking'] = -1.7
        
        # Risk Manager vote (مستشار ثامن)
        if risk_vote is not None:
            votes['risk_manager'] = max(-2.0, min(-0.1, risk_vote))
        
        # Ensure all votes are within bounds (-0.1% to -2%)
        for key in votes:
            votes[key] = max(-2.0, min(-0.1, votes[key]))
        
        return votes

    
    def get_buy_decision(self, symbol, analysis):
        """
        قرار الشراء الشامل من كل الموديلات (المستشارين + الملك)
        """
        try:
            rsi = analysis.get('rsi', 50)
            macd = analysis.get('macd_diff', 0)
            volume_ratio = analysis.get('volume_ratio', 1)
            price_momentum = analysis.get('price_momentum', 0)
            confidence = analysis.get('confidence', 60)
            
            # جمع توقعات المستشارين (7 مستشارين)
            mtf_boost = self.get_mtf_prediction(rsi, macd, volume_ratio, price_momentum)
            risk_result = self.get_risk_prediction(rsi, volume_ratio, confidence, price_momentum)
            anomaly_result = self.get_anomaly_prediction(rsi, macd, volume_ratio, price_momentum)
            pattern_result = self.get_pattern_prediction(rsi, macd, volume_ratio, price_momentum, confidence)
            ranking_result = self.get_ranking_prediction(symbol)
            cnn_result = self.get_chart_cnn_prediction(rsi, macd, volume_ratio, price_momentum)
            
            # حساب التعديل من المستشارين (بما فيهم Anomaly)
            consultants_adjustment = (
                mtf_boost +
                risk_result['confidence_adjustment'] +
                anomaly_result['confidence_adjustment'] +  # يعطي -10 أو -5 أو -2 أو 0
                pattern_result['confidence_adjustment'] +
                ranking_result['confidence_adjustment'] +
                cnn_result['confidence_adjustment']
            )
            
            # فحص الشذوذ القوي جداً فقط (CRITICAL)
            # ملاحظة: anomaly_result من DL client مختلف عن anomaly_detector من models
            # هنا نعتمد على confidence_adjustment بدل الرفض المباشر
            
            # فحص النمط
            if pattern_result['pattern_type'] == 'trap':
                return {
                    'action': 'SKIP',
                    'reason': 'Trap pattern detected',
                    'confidence_adjustment': 0
                }
            
            # فحص المخاطر
            if risk_result['risk_level'] == 'high':
                consultants_adjustment -= 5
            
            # الملك (Meta) يقرر في meta.py، هنا نرجع نتيجة المستشارين فقط
            return {
                'action': 'BUY' if consultants_adjustment > 0 else 'SKIP',
                'reason': 'Consultants approved' if consultants_adjustment > 0 else 'Low confidence',
                'confidence_adjustment': consultants_adjustment,
                'mtf_boost': mtf_boost,
                'risk_level': risk_result['risk_level'],
                'pattern_type': pattern_result['pattern_type'],
                'rank_score': ranking_result['rank_score'],
                'cnn_pattern': cnn_result['pattern_detected']
            }
        
        except Exception as e:
            print(f"⚠️ Buy decision error: {e}")
            return {'action': 'SKIP', 'confidence_adjustment': 0}
    
    def is_available(self):
        """فحص إذا الموديلات متوفرة"""
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
        """الحصول على حالة كل الموديلات"""
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

    def vote_buy_now(self, rsi, macd, volume_ratio, price_momentum, confidence=50,
                     liquidity_metrics=None, market_sentiment=None, candle_analysis=None):
        """
        الشراء: 5 مستشارين يصوتون على القاع
        Bullish: 3/5 | Neutral: 4/5 | Bearish: 5/5
        Returns: (votes dict, market_status)
        """
        is_bottom_candle = candle_analysis.get('is_bottom', False) if candle_analysis else False
        votes = {'exit': 0, 'risk': 0, 'pattern': 0, 'anomaly': 0, 'liquidity': 0}

        # تحديد حالة السوق
        btc_change = 0
        if market_sentiment:
            btc_change = market_sentiment.get('btc_change_1h', 0)
        if btc_change > 1.0:
            market_status = 'bullish'
        elif btc_change < -1.0:
            market_status = 'bearish'
        else:
            market_status = 'neutral'

        _tp_acc = self._model_accuracy.get('exit', 0.5)
        _sl_acc = self._model_accuracy.get('risk', 0.5)

        # شروط التصويت حسب حالة السوق (متوسط)
        # Bullish: أسهل (rsi < 65) | Neutral: متوسط (rsi < 60) | Bearish: أصعب (rsi < 48)
        if market_status == 'bullish':
            rsi_buy_threshold = 65
            macd_required = False
        elif market_status == 'bearish':
            rsi_buy_threshold = 48
            macd_required = True
        else:  # neutral
            rsi_buy_threshold = 60
            macd_required = False

        # ===== دالة مساعدة: rule-based fallback لكل مستشار =====
        # تتبع تصويت النماذج لكشف النماذج المعطوبة
        _model_votes_log = {}

        def _rule_buy(advisor_name, ml_pred):
            """
            ✅ التعديل: يصوت فقط من النموذج المدرب من قاعدة البيانات
            تم حذف جميع القواعد الثابتة والـ fallback
            """
            _model_votes_log[advisor_name] = ml_pred
            
            # فقط نستخدم النموذج المدرب ولا شيء اخر
            if ml_pred is not None:
                return ml_pred
            
            # في حالة عدم وجود نموذج فقط نرجع صفر
            return 0

        # 1. Exit model
        exit_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                     extra_features=[24, _tp_acc, _sl_acc])
        exit_names = BASE_FEATURE_NAMES + ['hours_held', 'tp_accuracy', 'sell_accuracy']
        exit_pred = self._predict_buy('exit', exit_features, exit_names)
        votes['exit'] = _rule_buy('exit', exit_pred)

        # 2. Risk model
        risk_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                     extra_features=[rsi, abs(price_momentum), _tp_acc, _sl_acc])
        risk_names = BASE_FEATURE_NAMES + ['risk_rsi', 'risk_atr', 'tp_accuracy', 'sell_accuracy']
        risk_pred = self._predict_buy('risk', risk_features, risk_names)
        votes['risk'] = _rule_buy('risk', risk_pred)

        # 3. Pattern model
        pattern_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                        market_sentiment=market_sentiment,
                                                        candle_analysis=candle_analysis,
                                                        extra_features=[price_momentum, _tp_acc, _sl_acc])
        pattern_names = BASE_FEATURE_NAMES + ['pattern_momentum', 'tp_accuracy', 'sell_accuracy']
        pattern_pred = self._predict_buy('pattern', pattern_features, pattern_names)
        votes['pattern'] = _rule_buy('pattern', pattern_pred)

        # 4. Anomaly model
        anomaly_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                        market_sentiment=market_sentiment,
                                                        extra_features=[abs(price_momentum), _tp_acc, _sl_acc])
        anomaly_names = BASE_FEATURE_NAMES + ['anomaly_score', 'tp_accuracy', 'sell_accuracy']
        anomaly_pred = self._predict_buy('anomaly', anomaly_features, anomaly_names)
        votes['anomaly'] = _rule_buy('anomaly', anomaly_pred)

        # 5. Liquidity model
        liquidity_score = liquidity_metrics.get('liquidity_score', 50) if liquidity_metrics else 50
        liq_features = [
            # ✅ إصلاح: حذف profit (كان leakage)
            volume_ratio, 0, 0,
            (liquidity_metrics or {}).get('depth_ratio', 1.0),
            liquidity_score,
            (liquidity_metrics or {}).get('price_impact', 0.5),
            (liquidity_metrics or {}).get('volume_consistency', 50),
            1 if liquidity_score > 70 else 0,
            1 if (liquidity_metrics or {}).get('price_impact', 0.5) < 0.3 else 0,
            1 if (liquidity_metrics or {}).get('volume_consistency', 50) > 60 else 0,
            _tp_acc, _sl_acc
        ]
        liq_names = [
            # ✅ إصلاح: profit محذوف
            'volume_ratio', 'bid_ask_spread', 'volume_trend',
            'depth_ratio', 'liquidity_score', 'price_impact', 'volume_consistency',
            'good_liquidity', 'low_impact', 'consistent_vol', 'tp_accuracy', 'sell_accuracy'
        ]
        liq_pred = self._predict_buy('liquidity', liq_features, liq_names)
        votes['liquidity'] = _rule_buy('liquidity', liq_pred)

        return votes, market_status

    def get_advice(self, rsi, macd, volume_ratio, price_momentum, confidence=50,
                   liquidity_metrics=None, market_sentiment=None, candle_analysis=None):
        """
        النصائح من المستشارين ال10 لميتا بناءً على تخصص كل نموذج
        Returns: dict of advisor_name: advice_string
        """
        advice = {}

        # تحديد حالة السوق
        btc_change = 0
        if market_sentiment:
            btc_change = market_sentiment.get('btc_change_1h', 0)
        market_status = 'bullish' if btc_change > 1.0 else 'bearish' if btc_change < -1.0 else 'neutral'

        # ✅ استخدام features كاملة (42) لكل موديل + حماية من None
        _tp_acc = self._model_accuracy.get('exit', 0.5)
        _sl_acc = self._model_accuracy.get('risk', 0.5)

        # risk
        if 'risk' in self._models:
            f = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                            market_sentiment=market_sentiment,
                                            extra_features=[rsi, abs(price_momentum), _tp_acc, _sl_acc])
            n = BASE_FEATURE_NAMES + ['risk_rsi', 'risk_atr', 'tp_accuracy', 'sell_accuracy']
            p = self._predict_proba('risk', f, n)
            p = p if p is not None else 0.5
            advice['risk'] = f"Risk level: {'High' if p > 0.7 else 'Medium' if p > 0.3 else 'Low'}. Adjust stop loss accordingly."

        # exit
        if 'exit' in self._models:
            f = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                            extra_features=[24, _tp_acc, _sl_acc])
            n = BASE_FEATURE_NAMES + ['hours_held', 'tp_accuracy', 'sell_accuracy']
            p = self._predict_proba('exit', f, n)
            p = p if p is not None else 0.5
            advice['exit'] = f"Exit opportunity: {'Strong' if p > 0.8 else 'Moderate' if p > 0.5 else 'Weak'}."

        # pattern
        if 'pattern' in self._models:
            f = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                            market_sentiment=market_sentiment,
                                            candle_analysis=candle_analysis,
                                            extra_features=[price_momentum, _tp_acc, _sl_acc])
            n = BASE_FEATURE_NAMES + ['pattern_momentum', 'tp_accuracy', 'sell_accuracy']
            p = self._predict_proba('pattern', f, n)
            p = p if p is not None else 0.5
            advice['pattern'] = f"Pattern analysis: {'Bullish' if p > 0.6 else 'Bearish'} signal detected."

        # anomaly
        if 'anomaly' in self._models:
            f = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                            market_sentiment=market_sentiment,
                                            extra_features=[abs(price_momentum), _tp_acc, _sl_acc])
            n = BASE_FEATURE_NAMES + ['anomaly_score', 'tp_accuracy', 'sell_accuracy']
            p = self._predict_proba('anomaly', f, n)
            p = p if p is not None else 0.5
            advice['anomaly'] = f"Anomaly detection: {'High risk' if p > 0.7 else 'Normal'}."

        # liquidity
        if 'liquidity' in self._models:
            liq_score = (liquidity_metrics or {}).get('liquidity_score', 50)
            liq_features = [
                volume_ratio, 0, 0,
                (liquidity_metrics or {}).get('depth_ratio', 1.0),
                liq_score,
                (liquidity_metrics or {}).get('price_impact', 0.5),
                (liquidity_metrics or {}).get('volume_consistency', 50),
                1 if liq_score > 70 else 0,
                1 if (liquidity_metrics or {}).get('price_impact', 0.5) < 0.3 else 0,
                1 if (liquidity_metrics or {}).get('volume_consistency', 50) > 60 else 0,
                _tp_acc, _sl_acc
            ]
            liq_names = [
                'volume_ratio', 'bid_ask_spread', 'volume_trend',
                'depth_ratio', 'liquidity_score', 'price_impact', 'volume_consistency',
                'good_liquidity', 'low_impact', 'consistent_vol', 'tp_accuracy', 'sell_accuracy'
            ]
            p = self._predict_proba('liquidity', liq_features, liq_names)
            p = p if p is not None else 0.5
            advice['liquidity'] = f"Liquidity: {'Excellent' if p > 0.8 else 'Good' if p > 0.6 else 'Poor'}."

        # meta_trading
        if 'meta_trading' in self._models:
            f = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                            market_sentiment=market_sentiment,
                                            extra_features=[confidence, _tp_acc, _sl_acc])
            n = BASE_FEATURE_NAMES + ['confidence', 'tp_accuracy', 'sell_accuracy']
            p = self._predict_proba('meta_trading', f, n)
            p = p if p is not None else 0.5
            advice['meta_trading'] = f"Meta advice: {'Strong buy' if p > 0.8 else 'Buy' if p > 0.6 else 'Hold' if p > 0.4 else 'Sell'}."

        # النصائح الثابتة (لا تحتاج موديل)
        advice['smart_money'] = f"Smart money flow: {'Inflow detected' if volume_ratio > 1.5 else 'Neutral'}."
        advice['chart_cnn'] = f"Chart CNN: {'Reversal likely' if candle_analysis and candle_analysis.get('is_reversal') else 'Trend continuation'}."
        advice['volume_pred'] = f"Volume prediction: {'Increasing' if volume_ratio > 1.2 else 'Stable'} trend."
        advice['sentiment'] = f"Market sentiment: {market_status.capitalize()}."
        advice['crypto_news'] = f"Crypto news impact: {'Positive' if confidence > 70 else 'Neutral' if confidence > 50 else 'Negative'}."

        return advice

    def vote_sell_now(self, rsi, macd, volume_ratio, price_momentum, liquidity_metrics=None, candle_analysis=None, market_sentiment=None):
        """
        البيع: 5 مستشارين يصوتون بالقمة
        Bullish: 3/5 | Neutral: 4/5 | Bearish: 5/5
        """
        votes = {'exit': 0, 'risk': 0, 'pattern': 0, 'anomaly': 0, 'liquidity': 0}

        # استخراج تحليل الشموع
        is_peak_candle = False
        is_rejection = False
        if candle_analysis:
            is_peak_candle = candle_analysis.get('is_peak', False)
            is_rejection = candle_analysis.get('is_rejection', False)

        # تحديد حالة السوق من المعنويات الفعلية
        btc_change = 0
        if market_sentiment:
            btc_change = market_sentiment.get('btc_change_1h', 0)
        if btc_change > 1.0:
            market_status = 'bullish'
        elif btc_change < -1.0:
            market_status = 'bearish'
        else:
            market_status = 'neutral'

        # ===== استخدام الموديلات المدربة للتصويت =====
        _tp_acc = self._model_accuracy.get('exit', 0.5)
        _sl_acc = self._model_accuracy.get('risk', 0.5)

        # ===== دالة مساعدة: rule-based fallback للبيع =====
        def _rule_sell(advisor_name, ml_pred):
            """
            ✅ التعديل: يصوت فقط من النموذج المدرب من قاعدة البيانات
            تم حذف جميع القواعد الثابتة والـ fallback
            """
            # فقط نستخدم النموذج المدرب ولا شيء اخر
            if ml_pred is not None:
                return ml_pred
            
            # في حالة عدم وجود نموذج فقط نرجع صفر
            return 0

        # 1. Exit model
        exit_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                     extra_features=[24, _tp_acc, _sl_acc])
        exit_names = BASE_FEATURE_NAMES + ['hours_held', 'tp_accuracy', 'sell_accuracy']
        exit_pred = self._predict_buy('exit', exit_features, exit_names)
        votes['exit'] = _rule_sell('exit', exit_pred)

        # 2. Risk model
        risk_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                     extra_features=[rsi, abs(price_momentum), _tp_acc, _sl_acc])
        risk_names = BASE_FEATURE_NAMES + ['risk_rsi', 'risk_atr', 'tp_accuracy', 'sell_accuracy']
        risk_pred = self._predict_buy('risk', risk_features, risk_names)
        votes['risk'] = _rule_sell('risk', risk_pred)

        # 3. Pattern model
        pattern_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                        market_sentiment=market_sentiment,
                                                        candle_analysis=candle_analysis,
                                                        extra_features=[price_momentum, _tp_acc, _sl_acc])
        pattern_names = BASE_FEATURE_NAMES + ['pattern_momentum', 'tp_accuracy', 'sell_accuracy']
        pattern_pred = self._predict_buy('pattern', pattern_features, pattern_names)
        votes['pattern'] = _rule_sell('pattern', pattern_pred)

        # 4. Anomaly model
        anomaly_features = self._prepare_base_features(rsi, macd, volume_ratio, price_momentum,
                                                        market_sentiment=market_sentiment,
                                                        extra_features=[abs(price_momentum), _tp_acc, _sl_acc])
        anomaly_names = BASE_FEATURE_NAMES + ['anomaly_score', 'tp_accuracy', 'sell_accuracy']
        anomaly_pred = self._predict_buy('anomaly', anomaly_features, anomaly_names)
        votes['anomaly'] = _rule_sell('anomaly', anomaly_pred)

        # 5. Liquidity model
        liquidity_score = liquidity_metrics.get('liquidity_score', 50) if liquidity_metrics else 50
        liquidity_features = [
            # ✅ إصلاح: حذف profit (كان leakage)
            volume_ratio, 0, 0,
            (liquidity_metrics or {}).get('depth_ratio', 1.0),
            liquidity_score,
            (liquidity_metrics or {}).get('price_impact', 0.5),
            (liquidity_metrics or {}).get('volume_consistency', 50),
            1 if liquidity_score > 70 else 0,
            1 if (liquidity_metrics or {}).get('price_impact', 0.5) < 0.3 else 0,
            1 if (liquidity_metrics or {}).get('volume_consistency', 50) > 60 else 0,
            _tp_acc, _sl_acc
        ]
        liquidity_names = [
            # ✅ إصلاح: profit محذوف
            'volume_ratio', 'bid_ask_spread', 'volume_trend',
            'depth_ratio', 'liquidity_score', 'price_impact', 'volume_consistency',
            'good_liquidity', 'low_impact', 'consistent_vol', 'tp_accuracy', 'sell_accuracy'
        ]
        liq_pred = self._predict_buy('liquidity', liquidity_features, liquidity_names)
        votes['liquidity'] = _rule_sell('liquidity', liq_pred)

        # ✅ 5 مستشارين (exit, risk, pattern, anomaly, liquidity)
        return votes, market_status

    # =========================================================
    # 🎓 التعلم المباشر للمستشارين الـ5 - يتعلمون من كل صفقة
    # =========================================================
    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, signal_type='sell'):
        """
        التعلم المباشر من كل صفقة
        كل مستشار يتعلم من أخطائه بدون أوزان متفاوتة
        """
        try:
            if signal_type == 'sell' and sell_votes:
                for advisor, voted in sell_votes.items():
                    if advisor in self.learning_data:
                        if trade_quality in ['GREAT', 'GOOD', 'OK']:
                            if voted == 1:
                                self.learning_data[advisor]['sell_success'] += 1
                            else:
                                self.learning_data[advisor]['sell_fail'] += 1
                        elif trade_quality in ['RISKY', 'TRAP']:
                            if voted == 1:
                                self.learning_data[advisor]['sell_fail'] += 1
                            else:
                                self.learning_data[advisor]['sell_success'] += 1
            
            elif signal_type == 'buy' and buy_votes:
                for advisor, voted in buy_votes.items():
                    if advisor in self.learning_data:
                        if profit > 0.5:
                            if voted == 1:
                                self.learning_data[advisor]['buy_success'] += 1
                            else:
                                self.learning_data[advisor]['buy_fail'] += 1
                        elif profit < -0.5:
                            if voted == 1:
                                self.learning_data[advisor]['buy_fail'] += 1
                            else:
                                self.learning_data[advisor]['buy_success'] += 1
            
            self._save_learning_data()
            
            # طباعة التعلم
            print(f"🎓 المستشارون تعلموا: {trade_quality} | profit: {profit:+.2f}%")
            
        except Exception as e:
            print(f"⚠️ خطأ في تعلم المستشارين: {e}")
    
    def get_advisor_accuracy(self, advisor_name):
        """حساب دقة المستشار (0-100)"""
        if advisor_name not in self.learning_data:
            return 50
        
        data = self.learning_data[advisor_name]
        total = data['buy_success'] + data['buy_fail'] + data['sell_success'] + data['sell_fail']
        
        if total < 5:
            return 50
        
        success = data['buy_success'] + data['sell_success']
        return round((success / total) * 100, 1)
    
    def get_all_advisors_accuracy(self):
        """دقة جميع المستشارين"""
        return {name: self.get_advisor_accuracy(name) for name in self.learning_data.keys()}
