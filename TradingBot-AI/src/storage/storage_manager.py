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
        
        # ✅ تتبع آخر تنظيف للذاكرة (كل 5 دقائق)
        self._last_gc_time = datetime.now()

        # تحميل البيانات المطلوبة عند بدء التشغيل
        self._startup_load()

    def _startup_load(self):
        """تحميل جميع الجداول بالتوازي عند التشغيل (Requirement 1, 2, 3)"""
        print("✅ [Startup] Pre-loading all tables in parallel into RAM Cache...")
        
        import concurrent.futures
        
        def load_settings():
            self.load_setting('bot_settings')
            self.load_setting('risk_settings')
        
        def load_news():
            self.get_news_data()
        
        def load_learning():
            self.get_learning_data()
        
        def load_symbol_memories():
            for symbol in SYMBOLS:
                self.get_symbol_memory(symbol)
        
        def load_patterns():
            self.load_all_patterns()
        
        def load_positions():
            self.load_positions()
        
        # تحميل كل الجداول بالتوازي
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(load_settings),
                executor.submit(load_news),
                executor.submit(load_learning),
                executor.submit(load_symbol_memories),
                executor.submit(load_patterns),
                executor.submit(load_positions)
            ]
            concurrent.futures.wait(futures)

        print("✅ [Startup] All tables loaded in parallel into RAM cache.")
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
            data = self.mem_cache.get(cache_key)

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
            cached_data = self.mem_cache.get(cache_key)

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
            return cached_trades

        try:
            trades = self.storage.load_trades(limit=1000)
            if trades:
                self.mem_cache.set(cache_key, trades, expiry_seconds=1800)
            return trades
        except Exception as e:
            print(f"⚠️ Error loading trades: {e}")
            return []

    def update_trade_sentiment(self, trade_id, sentiment_data):
        """تحديث مشاعر الصفقة وتطهير كاش الصفقات"""
        if hasattr(self.storage, 'update_trade_sentiment'):
            res = self.storage.update_trade_sentiment(trade_id, sentiment_data)
            self.mem_cache.delete('all_trades')
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
            self.mem_cache.set(cache_key, patterns, expiry_seconds=7200)
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
            cached_data = self.mem_cache.get(cache_key)
        
        # ✅ استخدام النسخة المضغوطة في الرام حصراً
        return cached_data if cached_data is not None else {}

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
        self.mem_cache.set(cache_key, positions, expiry_seconds=1800)
        return positions
    
    def delete_position(self, symbol):
        """حذف صفقة مغلقة وإفراغ كاش المراكز"""
        res = self.storage.delete_position(symbol)
        self.mem_cache.delete('open_positions')
        return res
    
    def get_open_positions(self):
        """جلب الصفقات المفتوحة (alias لـ load_positions)"""
        return self.load_positions()
    
    # ========== Settings & Models ==========
    def save_setting(self, key, value):
        """حفظ إعداد في الداتابيز"""
        if hasattr(self.storage, 'save_setting'):
            if key == 'king_learning_data':
                self.mem_cache.set(key, value, expiry_seconds=1800)
                self._last_learning_update = datetime.now()
            return self.storage.save_setting(key, value)
        return False

    def load_setting(self, key):
        """تحميل إعداد من الداتابيز مع نظام كاش داخلي لحماية Egress"""
        cache_key = f"setting_{key}"
        cached = self.mem_cache.get(cache_key)
        if cached:
            return cached

        if hasattr(self.storage, 'load_setting'):
            val = self.storage.load_setting(key)
            if val:
                self.mem_cache.set(cache_key, val, expiry_seconds=1800)
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
            self._periodic_gc()
            return cached_model
            
        model = self.storage.load_model(model_name)
        if model:
            self.mem_cache.set(cache_key, model, expiry_seconds=None) 
            self._periodic_gc()
        return model
    
    def _periodic_gc(self):
        """✅ تنظيف دوري للذاكرة (كل 5 دقائق فقط)"""
        now = datetime.now()
        if (now - self._last_gc_time).total_seconds() > 300:  # 5 دقائق
            gc.collect()
            self._last_gc_time = now
