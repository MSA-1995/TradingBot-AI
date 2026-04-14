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

class DeepLearningClientV2:
    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = None
        self._db_params = None
        self._pool = None  # ✅ Connection Pool
        self._models = {}        # {model_name: model_object}
        self._model_accuracy = {} # {model_name: accuracy}
        self._model_trained_at = {} # {model_name: trained_at}
        self._feature_names = {} # {model_name: list_of_feature_names}
        try:
            self._connect_db()
            self._load_all_models_from_db()
            self._print_models_status()
        except Exception as e:
            raise
    
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

        except Exception as e:
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
                    return
                _params = self._db_params.copy()
                # ✅ تحسين keepalives لمنع إغلاق الاتصالات أثناء تحميل النماذج الكبيرة - أكثر عدوانية
                _params['keepalives'] = 1
                _params['keepalives_idle'] = 5    # فحص كل 5 ثوانٍ بدلاً من 10
                _params['keepalives_interval'] = 1  # فحص كل ثانية بدلاً من ثانيتين
                _params['keepalives_count'] = 3     # تقليل عدد المحاولات الفاشلة أكثر
                conn = psycopg2.connect(**_params)

                cursor = conn.cursor(cursor_factory=RealDictCursor)
                # ✅ ضبط التوقيتات عبر SQL للتوافق مع Neon Pooler
                cursor.execute("SET statement_timeout = '300s'")
                cursor.execute("SET tcp_user_timeout = '120s'")

                # ✅ جلب البيانات كاملة في استعلام واحد لتسريع التحميل وضمان جلب الدقة المحقونة
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
                    return  # موديل غير موجود في DB

                # ✅ تعيين الدقة فوراً لكي تظهر في القائمة حتى لو كانت بيانات الموديل فارغة أو محقونة
                db_acc = result.get('accuracy')
                self._model_accuracy[name] = float(db_acc) if db_acc is not None else 0.0
                self._model_trained_at[name] = str(result.get('trained_at') or 'N/A')

                if result.get('model_data'):
                    raw_data = result['model_data']
                    if isinstance(raw_data, memoryview):
                        raw_data = bytes(raw_data)
                    try:
                        # فك ضغط الموديل المستخرج من الـ 16 ألف صفقة
                        if raw_data.startswith(b'\x1f\x8b'):
                            model_obj = pickle.loads(gzip.decompress(raw_data))
                        else:
                            model_obj = pickle.loads(raw_data)
                        
                        # تخزين الموديل وأسماء الميزات (Features) لضمان التوافق
                        self._models[name] = model_obj
                        from MSA_DeepLearning_Trainer.core.features import get_feature_names
                        self._feature_names[name] = get_feature_names()
                    except Exception: pass
                
                cursor.close()
                conn.close()
                return  # نجح
            except Exception as e:
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
                else:
                    pass
            except Exception as e:
                pass
            
            # تأخير قصير بين كل تحميل نموذج
            if i < len(model_names) - 1:  # لا انتظر بعد النموذج الأخير
                time.sleep(1)

        # تنظيف الذاكرة فوراً بعد تحميل كافة الموديلات الثقيلة
        import gc
        gc.collect()
        self._last_models_check = datetime.now()

    def _print_models_status(self):
        """طباعة القائمة الكاملة للمستشارين وقوتهم من الداتابيز"""
        model_names = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern',
            'liquidity', 'chart_cnn', 'volume_pred', 'meta_trading',
            'sentiment', 'crypto_news'
        ]
        
        # عرض الموديلات الـ 11 بالترتيب الأبجدي مع القوة الحقيقية
        for name in sorted(model_names):
            # جلب الدقة المخزنة (إذا كانت مخزنة كـ 0.8 ستظهر 80.0%)
            acc = self._model_accuracy.get(name, 0.0)
            print(f"  {name:17} {acc*100:5.1f}%")

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
        """جلب دقة الموديل المدرب"""
        return self._model_accuracy.get(model_name, 0)

    
    def get_advice(self, rsi, macd, volume_ratio, price_momentum, confidence=50,
                   liquidity_metrics=None, market_sentiment=None, candle_analysis=None, analysis_data=None):
        """
        النصائح من المستشارين بناءً على التخصص الافتراضي (بدون ميزات إضافية)
        Returns: dict of advisor_name: advice_string
        """
        advice = {}
        
        analysis = analysis_data if analysis_data else {}

        # ✅ دالة مساعدة لاستخلاص الميزات والتنبؤ
        def _get_prediction_advice(advisor_name, current_analysis_data, trade_data=None):
            model = self._models.get(advisor_name)
            feature_names = self._feature_names.get(advisor_name)

            if not model or not feature_names:
                return "N/A" # الموديل غير متاح

            try:
                # ✅ استخدام calculate_enhanced_features لاستخلاص الميزات
                from MSA_DeepLearning_Trainer.core.features import calculate_enhanced_features
                features_vector = calculate_enhanced_features(current_analysis_data, trade_data)
                
                # تحويل المتجه إلى DataFrame ليتوافق مع متطلبات LightGBM
                # يجب أن تتطابق أسماء الميزات مع تلك التي تدرب عليها الموديل
                # هذا يتطلب أن تكون calculate_enhanced_features ترجع الميزات بنفس الترتيب
                # أو أن نستخدم قاموساً لإنشاء DataFrame
                
                # هنا نفترض أن calculate_enhanced_features ترجع قائمة مرتبة من القيم
                # وأن feature_names هي قائمة مرتبة من أسماء الميزات
                
                # ✅ التأكد من أن عدد الميزات المستخلصة يطابق عدد الميزات المتوقعة للموديل
                if len(features_vector) != len(feature_names):
                    # هذا يعني أن هناك مشكلة في استخلاص الميزات أو عدم تطابق
                    # يجب تصحيح calculate_enhanced_features لترجع دائماً نفس العدد من الميزات
                    # أو تعديل feature_names هنا
                    print(f"⚠️ Feature mismatch for {advisor_name}: Expected {len(feature_names)}, got {len(features_vector)}")
                    return "N/A"

                features_df = pd.DataFrame([features_vector], columns=feature_names)
                
                # التنبؤ باحتمالية الفئة الإيجابية (1)
                proba = model.predict_proba(features_df)[:, 1][0]

                # ترجمة الاحتمالية إلى نصيحة
                if proba > 0.8:
                    return "Strong-Bullish-Signal"
                elif proba > 0.6:
                    return "Bullish-Signal"
                elif proba < 0.2:
                    return "Strong-Bearish-Warning"
                elif proba < 0.4:
                    return "Bearish-Warning"
                else:
                    return "Neutral-Outlook"
            except Exception as e:
                print(f"❌ Error in {advisor_name} prediction: {e}")
                return "N/A"

        # 🛡️ 1. Risk Advisor (Dynamic Risk)
        advice['risk'] = _get_prediction_advice('risk', analysis)
        
        # 🎯 2. Exit Advisor (Smart Rotation)
        advice['exit'] = _get_prediction_advice('exit', analysis)
        
        # 🧠 3. Pattern Advisor (Institutional Flow)
        advice['pattern'] = _get_prediction_advice('pattern', analysis)
        
        # 🚨 4. Anomaly Advisor (Abnormal Move)
        advice['anomaly'] = _get_prediction_advice('anomaly', analysis)
        
        # 💧 5. Liquidity Advisor (Depth Check)
        advice['liquidity'] = _get_prediction_advice('liquidity', analysis)
        
        # 🐋 6. Smart Money Advisor (Whale Watch)
        advice['smart_money'] = _get_prediction_advice('smart_money', analysis)
        
        # 📊 7. Chart CNN (Deep Vision)
        advice['chart_cnn'] = _get_prediction_advice('chart_cnn', analysis)
        
        # 📈 8. Volume Predictor (Future Inflow)
        advice['volume_pred'] = _get_prediction_advice('volume_pred', analysis)
        
        # 9. Sentiment Advisor (Velocity Focus)
        # ✅ هنا نستخدم market_sentiment مباشرة من analysis_data
        sentiment_analysis_data = {
            'sentiment_score': (market_sentiment or {}).get('sentiment_score', 0),
            'sentiment_velocity': analysis.get('sentiment_velocity', 0),
            'panic_score': (market_sentiment or {}).get('panic_score', 0),
            'optimism_penalty': (market_sentiment or {}).get('optimism_penalty', 0)
        }
        advice['sentiment'] = _get_prediction_advice('sentiment', sentiment_analysis_data)
        
        # 10. Crypto News (Propagation Speed)
        # ✅ هنا نستخدم news_score مباشرة من analysis_data
        news_analysis_data = {
            'news_score': (market_sentiment or {}).get('news_score', 0)
        }
        advice['crypto_news'] = _get_prediction_advice('crypto_news', news_analysis_data)

        return advice

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
