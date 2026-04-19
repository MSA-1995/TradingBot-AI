"""
🧠 Deep Learning Client V3 - الشيف القائد
مسؤول عن جلب الموديلات الـ 12 من الداتابيز وتحويل البيانات لتوقعات
"""
import os
import pickle
import gzip
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

try:
    from memory_cache import MemoryCache
except Exception:
    MemoryCache = None

class DeepLearningClientV2:
    def __init__(self, database_url, load_models=True):
        self.database_url = database_url
        self._models = MemoryCache(max_items=20) if MemoryCache else {}
        self._model_accuracy = {}
        if load_models:
            self._load_all_models_from_db()
    
    def _get_conn(self):
        try:
            p = urlparse(self.database_url)
            return psycopg2.connect(
                host=p.hostname, port=p.port or 5432,
                database=p.path[1:], user=p.username,
                password=unquote(p.password) if p.password else None,
                sslmode='require'
            )
        except: return None

    def _load_all_models_from_db(self):
        names = ['smart_money', 'risk', 'anomaly', 'exit', 'pattern', 'liquidity', 
                 'chart_cnn', 'candle_expert', 'volume_pred', 'meta_trading', 'sentiment', 'crypto_news']
        conn = self._get_conn()
        if not conn: return
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            for name in names:
                cursor.execute("SELECT accuracy, model_data FROM dl_models_v2 WHERE model_name = %s ORDER BY trained_at DESC LIMIT 1", (name,))
                res = cursor.fetchone()
                if res:
                    self._model_accuracy[name] = float(res['accuracy'])
                    raw = res['model_data']
                    if isinstance(raw, memoryview): raw = bytes(raw)
                    model = pickle.loads(gzip.decompress(raw)) if raw.startswith(b'\x1f\x8b') else pickle.loads(raw)
                    if MemoryCache: self._models.set(name, model)
                    else: self._models[name] = model
            cursor.close()
            conn.close()
        except: pass

    def _print_models_status(self):
        """Print the status of loaded models"""
        if not self._model_accuracy:
            print("⚠️ Deep Learning: No models found in database.")
            return
        print(f"🧠 Deep Learning: {len(self._model_accuracy)}/12 models loaded successfully")
        for name, acc in self._model_accuracy.items():
            print(f"  ✅ {name:17} {acc*100:5.1f}%")

    def get_advice(self, rsi, macd, volume_ratio, price_momentum, analysis_data=None, action='BUY'):
        advice = {}
        is_sell = (action == 'SELL')
        analysis = analysis_data or {}
        
        # ميزات مطابقة لتدريب الـ 16 ألف صفقة
        features = [rsi, macd, volume_ratio, price_momentum, 0, 0, 0, 0, 0, 0, 0.5, 0.5]
        cols = ['rsi', 'macd', 'volume_ratio', 'price_momentum', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'tp_acc', 'sell_acc']

        def _predict(m, f):
            try:
                X = pd.DataFrame([f], columns=cols)
                m.set_params(predict_disable_shape_check=True)
                p = m.predict_proba(X)[0][1]
                if is_sell:
                    return "Strong-Bearish" if p < 0.3 else "Bearish" if p < 0.45 else "Strong-Bullish" if p > 0.7 else "Bullish" if p > 0.55 else "Neutral"
                return "Strong-Bullish" if p > 0.7 else "Bullish" if p > 0.55 else "Strong-Bearish" if p < 0.3 else "Bearish" if p < 0.45 else "Neutral"
            except: return "N/A"

        # ✅ استخدام _model_accuracy لضمان التكرار السليم حتى لو الذاكرة مضغوطة
        for name in list(self._model_accuracy.keys()):
            m = self._models.get(name)
            advice[name] = _predict(m, features)
        
        return advice

    def is_available(self):
        return len(self._model_accuracy) > 0
