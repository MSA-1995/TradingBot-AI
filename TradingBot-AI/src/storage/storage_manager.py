"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً (نسخة مطهرة)
"""
import os
import json
from datetime import datetime
import gc
from config import SYMBOLS
from memory.memory_cache import MemoryCache

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
        # ====== MEMORY CACHE SYSTEM (Requirement 4) ======
        # كاش مضغوط بالكامل مع آلية تنظيف فوري
        self.mem_cache = MemoryCache(default_expiry=1800, max_items=500)

        if self.mode == 'cloud':
            from .database_storage import DatabaseStorage
            self.storage = DatabaseStorage()
        else:  # local
            from .local_storage import LocalStorage
            self.storage = LocalStorage('data/')

        # تتبع أوقات التحديث لضمان التوقيت المحدد (Requirement 2 & 3)
        self._last_news_update = None
        self._last_symbol_mem_update = {}
        self._last_learning_update = None

        # تحميل البيانات المطلوبة عند بدء التشغيل
        self._startup_load()

    def _startup_load(self):
        """تحميل النماذج والأخبار والذاكرة عند التشغيل (Requirement 1, 2, 3)"""
        print("✅ [Startup] Pre-loading ALL Tables into Compressed RAM Cache...")
        
        # 1. تحميل كافة النماذج الذكية الـ 12 لضمان ضغطها في الرام للأبد (Requirement 1)
        # تم إضافة كافة الأسماء الظاهرة في الـ Logs لضمان عدم الاتصال بالداتابيز لاحقاً
        all_models = [
            'smart_money', 'risk', 'anomaly', 'exit', 'pattern', 
            'liquidity', 'chart_cnn', 'candle_expert', 'volume_pred', 
            'meta_trading', 'sentiment', 'crypto_news', 'exit_strategy'
        ]
        for model_name in all_models:
            self.load_model(model_name)
        
        # 2. تحميل البيانات الأساسية لضمان عدم الاتصال بالداتابيز لاحقاً بشكل مفاجئ
        self.load_setting('bot_settings')
        self.load_setting('risk_settings')
        self.get_news_data() # تحميل الأخبار الشاملة

        # 3. تحميل بيانات التعلم (King Learning) عند التشغيل
        self.get_learning_data()
        
        # 4. 🔒 تحميل ذاكرة كافة العملات مسبقاً لمنع الاتصال بالداتابيز لاحقاً
        for symbol in SYMBOLS:
            self.get_symbol_memory(symbol)
            
        # 5. تحميل الأنماط والصفقات التاريخية لضمان كاش كامل
        self.load_all_patterns()

        print("✅ [Startup] All tables (Settings, News, Memory, Patterns, Models) are compressed in RAM.")
        gc.collect()

    def get_news_data(self, symbol=None):
        """جلب الأخبار: تحديث كل 30 دقيقة من DB، وبقية الوقت من الكاش المضغوط حصراً"""
        cache_key = f"news_{symbol}" if symbol else "news_all"
        now = datetime.now()
        data = self.mem_cache.get(cache_key)

        # 🔒 تحديث من DB فقط إذا كان الكاش فارغاً أو مر 30 دقيقة
        if data is None or self._last_news_update is None or (now - self._last_news_update).total_seconds() > 1800:
            self._last_news_update = now # تحديث التوقيت أولاً لمنع التكرار عند الفشل
            
            key = f'news_{symbol}' if symbol else 'news_all'
            # 🔒 إجبار القراءة من الداتابيز مباشرة لتحديث الكاش
            if hasattr(self.storage, 'load_setting'):
                db_news = self.storage.load_setting(key)
                if db_news:
                    self.mem_cache.set(cache_key, db_news, expiry_seconds=1800)
                    print(f"📰 News updated in compressed cache from DB (30m cycle)")
            gc.collect()
            data = self.mem_cache.get(cache_key)

        # تنظيف فوري
        gc.collect()
        return data

    def get_learning_data(self):
        """جلب بيانات التعلم: تحديث كل 30 دقيقة من DB، وبقية الوقت من الكاش المضغوط حصراً"""
        cache_key = "king_learning_data"
        now = datetime.now()
        cached_data = self.mem_cache.get(cache_key)

        # 🔒 تحديث من DB فقط إذا كان الكاش فارغاً أو مر 30 دقيقة
        if cached_data is None or self._last_learning_update is None or (now - self._last_learning_update).total_seconds() > 1800:
            self._last_learning_update = now # تحديث التوقيت أولاً
            
            # 🔒 إجبار القراءة من الداتابيز لتحديث بيانات التعلم
            if hasattr(self.storage, 'load_setting'):
                db_data = self.storage.load_setting(cache_key)
                if db_data:
                    self.mem_cache.set(cache_key, db_data, expiry_seconds=1800)
                    print(f"🧠 King Learning Data updated in compressed cache (30m cycle)")
            gc.collect()
            cached_data = self.mem_cache.get(cache_key)

        gc.collect()
        return cached_data
    
    def detect_environment(self):
        """يكتشف البيئة تلقائياً"""
        database_url = os.getenv('DATABASE_URL')
        return 'cloud' if database_url else 'local'
    
    # ========== Trade Operations ==========
    def save_trade(self, trade_data):
        """حفظ صفقة وتحديث كاش الصفقات فوراً"""
        res = self.storage.save_trade(trade_data)
        if res:
            # إفراغ الكاش لإجبار النظام على جلب الصفقات الجديدة في المرة القادمة
            self.mem_cache.delete('all_trades')
        return res
    
    def load_trades(self, limit=None):
        """تحميل الصفقات"""
        return self.storage.load_trades(limit)
    
    def get_all_trades(self):
        """جلب جميع الصفقات من الكاش المضغوط (Requirement 4)"""
        cache_key = "all_trades"
        cached_trades = self.mem_cache.get(cache_key)
        if cached_trades is not None:
            # تنظيف فوري بعد فك الضغط
            gc.collect()
            return cached_trades

        try:
            trades = self.storage.load_trades(limit=1000)
            if trades:
                self.mem_cache.set(cache_key, trades, expiry_seconds=1800) # كاش لـ 30 دقيقة
                gc.collect()
            return trades
        except Exception as e:
            print(f"⚠️ Error loading trades: {e}")
            return []

    def update_trade_sentiment(self, trade_id, sentiment_data):
        """تحديث مشاعر الصفقة وتطهير كاش الصفقات"""
        if hasattr(self.storage, 'update_trade_sentiment'):
            res = self.storage.update_trade_sentiment(trade_id, sentiment_data)
            self.mem_cache.delete('all_trades')
            gc.collect()
            return res
        return False

    # ========== Memory & Patterns ==========
    def save_pattern(self, pattern_data):
        """حفظ نمط متعلم"""
        self.mem_cache.delete('all_patterns') # إفراغ كاش الأنماط
        return self.storage.save_pattern(pattern_data)

    def load_all_patterns(self):
        """تحميل كل الأنماط من الكاش المضغوط"""
        cache_key = "all_patterns"
        cached = self.mem_cache.get(cache_key)
        if cached: return cached

        patterns = self.storage.load_all_patterns()
        if patterns:
            self.mem_cache.set(cache_key, patterns, expiry_seconds=7200) # كاش لساعتين
            gc.collect()
        return patterns

    def update_symbol_memory(self, *args, **kwargs):
        """تحديث ذاكرة العملة (المشاعر، السيولة، الذعر)"""
        if hasattr(self.storage, 'update_symbol_memory'):
            symbol = kwargs.get('symbol') or (args[0] if args else None)
            if symbol:
                self.mem_cache.delete(f"symbol_mem_{symbol}")
            return self.storage.update_symbol_memory(*args, **kwargs)
        return False

    def get_symbol_memory(self, symbol):
        """جلب ذاكرة العملة الشاملة"""
        cache_key = f"symbol_mem_{symbol}"
        now = datetime.now()
        cached_data = self.mem_cache.get(cache_key)
        
        # 🔒 تحديث من DB فقط إذا كان الكاش فارغاً أو مر 30 دقيقة
        last_update = self._last_symbol_mem_update.get(symbol)
        if cached_data is None or last_update is None or (now - last_update).total_seconds() > 1800:
            self._last_symbol_mem_update[symbol] = now # تحديث التوقيت أولاً
            try:
                data = self.storage.get_symbol_memory(symbol)
                if data:
                    # حفظ مضغوطة بالكاش رام
                    self.mem_cache.set(cache_key, data, expiry_seconds=1800)
            except Exception as e:
                pass # الحفاظ على استقرار البوت في حال فشل الاتصال
            gc.collect()
            cached_data = self.mem_cache.get(cache_key)
        # ✅ استخدام النسخة المضغوطة في الرام حصراً
        result = cached_data if cached_data is not None else {}
        del cached_data
        # تحرير الرام فوراً بعد فك الضغط للاستخدام المحلي
        gc.collect()
        return result

    # ========== Positions ==========
    def save_positions(self, positions):
        """حفظ المراكز المفتوحة دفعة واحدة"""
        # تحديث الكاش فوراً عند الحفظ لضمان عدم القراءة من DB
        self.mem_cache.set('open_positions', positions, expiry_seconds=1800)
        if self.mode == 'cloud':
            if isinstance(positions, dict):
                positions_list = [{'symbol': s, **p} for s, p in positions.items() if p]
                res = self.storage.save_positions_batch(positions_list)
            elif isinstance(positions, list):
                res = self.storage.save_positions_batch(positions)
        else:
            res = self.storage.save_positions(positions)
        gc.collect()
        return res
    
    def load_positions(self):
        """تحميل المراكز المفتوحة من الكاش لتقليل القراءة من DB"""
        cache_key = "open_positions"
        cached_pos = self.mem_cache.get(cache_key)
        if cached_pos:
            return cached_pos

        positions = self.storage.load_positions()
        # 🔒 توحيد الكاش ليكون 30 دقيقة لتقليل الضغط على الداتابيز
        self.mem_cache.set(cache_key, positions, expiry_seconds=1800)
        gc.collect()
        return positions
    
    def delete_position(self, symbol):
        """حذف صفقة مغلقة وإفراغ كاش المراكز"""
        res = self.storage.delete_position(symbol)
        self.mem_cache.delete('open_positions')
        gc.collect()
        return res
    
    def get_open_positions(self):
        """جلب الصفقات المفتوحة (alias لـ load_positions)"""
        return self.load_positions()
    
    # ========== Settings & Models ==========
    def save_setting(self, key, value):
        """حفظ إعداد في الداتابيز"""
        if hasattr(self.storage, 'save_setting'):
            # إذا كان المفتاح هو بيانات التعلم، نحدث الكاش فوراً لضمان الدقة
            if key == 'king_learning_data':
                self.mem_cache.set(key, value, expiry_seconds=1800)
                self._last_learning_update = datetime.now()
                gc.collect()
            return self.storage.save_setting(key, value)
        return False

    def load_setting(self, key):
        """تحميل إعداد من الداتابيز مع نظام كاش داخلي لحماية Egress"""
        cache_key = f"setting_{key}"
        # 🔒 منع الاستعلام المباشر: العودة للكاش دائماً
        cached = self.mem_cache.get(cache_key)
        if cached:
            gc.collect()
            return cached

        if hasattr(self.storage, 'load_setting'):
            val = self.storage.load_setting(key)
            if val:
                # كاش مضغوط لمدة 30 دقيقة للإعدادات (Bot Settings)
                self.mem_cache.set(cache_key, val, expiry_seconds=1800)
                gc.collect()
            return val
        return None

    def cleanup_old_data(self):
        """التنظيف التلقائي للجداول الأساسية فقط"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False

    def load_model(self, model_name):
        """تحميل الموديل وحفظه في الكاش المضغوط للأبد (Requirement 1)"""
        cache_key = f"model_{model_name}"
        cached_model = self.mem_cache.get(cache_key)
        
        if cached_model:
            gc.collect() # تنظيف فوري بعد فك الضغط للاستخدام
            return cached_model
            
        # تحميل من DB فقط إذا لم يكن موجوداً في الكاش (عند التشغيل)
        model = self.storage.load_model(model_name)
        if model:
            self.mem_cache.set(cache_key, model, expiry_seconds=None) 
            gc.collect()
        return model
