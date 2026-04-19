"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً (نسخة مطهرة)
"""
import os
import json
from datetime import datetime
import gc
from memory.memory_cache import MemoryCache

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
        # ====== MEMORY CACHE SYSTEM (Requirement 4) ======
        # كاش مضغوط بالكامل مع آلية تنظيف فوري
        self.mem_cache = MemoryCache(default_expiry=7200, max_items=500)

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
        print("✅ [Startup] Loading Models, News, and Memory into Compressed Cache...")
        
        # 1. تحميل النماذج (Requirement 1)
        self.load_model('meta_trading')
        
        # 2. تحميل الأخبار الأولية (Requirement 2)
        self.get_news_data()

        # 3. تحميل بيانات التعلم (King Learning) عند التشغيل
        self.get_learning_data()
        
        # 3. ذاكرة العملات يتم تحميلها وتحديثها عند الطلب
        print("✅ Startup data compressed and cached in RAM.")
        gc.collect()

    def get_news_data(self, symbol=None):
        """جلب الأخبار مع تحديث كل 30 دقيقة من الداتابيز (Requirement 2)"""
        cache_key = f"news_{symbol}" if symbol else "news_all"
        now = datetime.now()

        # التحقق من مرور 30 دقيقة للتحديث من الداتابيز
        if self._last_news_update is None or (now - self._last_news_update).total_seconds() > 1800:
            self._last_news_update = now # تحديث التوقيت أولاً لمنع التكرار عند الفشل
            db_news = self.load_setting(f'news_{symbol}') if symbol else self.load_setting('news_all')
            if db_news:
                # حفظ مضغوطة بالكاش
                self.mem_cache.set(cache_key, db_news, expiry_seconds=3600)
                print(f"📰 News updated in compressed cache from DB (30m cycle)")
            gc.collect()
        
        return self.mem_cache.get(cache_key)

    def get_learning_data(self):
        """جلب بيانات التعلم مضغوطة مع تحديث كل 30 دقيقة من الداتابيز"""
        cache_key = "king_learning_data"
        now = datetime.now()

        # تحديث كل 30 دقيقة من الداتابيز
        if self._last_learning_update is None or (now - self._last_learning_update).total_seconds() > 1800:
            self._last_learning_update = now # تحديث التوقيت أولاً
            data = self.load_setting(cache_key)
            if data:
                # حفظ مضغوطة بالكاش
                self.mem_cache.set(cache_key, data, expiry_seconds=3600)
                print(f"🧠 King Learning Data updated in compressed cache (30m cycle)")
            gc.collect()
        
        cached_data = self.mem_cache.get(cache_key)
        gc.collect() # تنظيف بعد فك الضغط والاستخدام
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
            self.mem_cache.cache.pop('all_trades', None)
        return res
    
    def load_trades(self, limit=None):
        """تحميل الصفقات"""
        return self.storage.load_trades(limit)
    
    def get_all_trades(self):
        """جلب جميع الصفقات من الكاش المضغوط (Requirement 4)"""
        cache_key = "all_trades"
        cached_trades = self.mem_cache.get(cache_key)
        if cached_trades:
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
            self.mem_cache.cache.pop('all_trades', None)
            gc.collect()
            return res
        return False

    # ========== Memory & Patterns ==========
    def save_pattern(self, pattern_data):
        """حفظ نمط متعلم"""
        self.mem_cache.cache.pop('all_patterns', None) # إفراغ كاش الأنماط
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
                self.mem_cache.cache.pop(f"symbol_mem_{symbol}", None)
            return self.storage.update_symbol_memory(*args, **kwargs)
        return False

    def get_symbol_memory(self, symbol):
        """جلب ذاكرة العملة الشاملة"""
        cache_key = f"symbol_mem_{symbol}"
        now = datetime.now()
        
        # تحديث كل 1 ساعة من الداتابيز (Requirement 3)
        last_update = self._last_symbol_mem_update.get(symbol)
        if last_update is None or (now - last_update).total_seconds() > 3600:
            self._last_symbol_mem_update[symbol] = now # تحديث التوقيت أولاً
            if hasattr(self.storage, 'get_symbol_memory'):
                data = self.storage.get_symbol_memory(symbol)
                if data:
                    # حفظ مضغوطة بالكاش رام
                    self.mem_cache.set(cache_key, data, expiry_seconds=7200)
            gc.collect()

        cached_data = self.mem_cache.get(cache_key)
        # Requirement 3 & 4: القراءة حصراً من الكاش المضغوط لضمان عدم استهلاك Egress
        # إذا كان الكاش فارغاً (أول مرة)، سيعيد dict فارغ ولن يضرب الداتابيز حتى تنتهي الساعة
        return cached_data if cached_data is not None else {}

    # ========== Positions ==========
    def save_positions(self, positions):
        """حفظ المراكز المفتوحة دفعة واحدة"""
        # تحديث الكاش فوراً عند الحفظ لضمان عدم القراءة من DB
        self.mem_cache.set('open_positions', positions, expiry_seconds=60)
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
        # كاش قصير لـ 60 ثانية لضمان الدقة مع تقليل القراءة المكثفة
        self.mem_cache.set(cache_key, positions, expiry_seconds=60)
        gc.collect()
        return positions
    
    def delete_position(self, symbol):
        """حذف صفقة مغلقة وإفراغ كاش المراكز"""
        res = self.storage.delete_position(symbol)
        self.mem_cache.cache.pop('open_positions', None)
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
                self.mem_cache.set(key, value, expiry_seconds=3600)
                self._last_learning_update = datetime.now()
                gc.collect()
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
                # كاش لمدة 10 دقائق للإعدادات العامة غير المجدولة
                self.mem_cache.set(cache_key, val, expiry_seconds=600)
            return val
        return None

    def cleanup_old_data(self):
        """التنظيف التلقائي للجداول الأساسية فقط"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False

    def load_model(self, model_name):
        """تحميل الموديل من الداتابيز"""
        cache_key = f"model_{model_name}"
        cached_model = self.mem_cache.get(cache_key)
        
        if cached_model:
            return cached_model
            
        # تحميل النموذج وحفظه مضغوطاً للأبد لعدم الاتصال بالداتابيز مجدداً (Requirement 1)
        model = self.storage.load_model(model_name)
        if model:
            self.mem_cache.set(cache_key, model, expiry_seconds=None) 
            gc.collect()
        return model
