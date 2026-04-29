"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً (نسخة مطهرة)
"""
import os
from datetime import datetime
import gc
from config import SYMBOLS
from memory.memory_cache import MemoryCache

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
        # ====== MEMORY CACHE SYSTEM (Requirement 4) ======
        self.mem_cache = MemoryCache(default_expiry=1800, max_items=500)

        if self.mode == 'cloud':
            from .database_storage import DatabaseStorage
            self.storage = DatabaseStorage()
        else:
            from .local_storage import LocalStorage
            self.storage = LocalStorage('data/')

        self._last_news_update        = {}
        self._last_symbol_mem_update  = {}
        self._last_learning_update    = None
        self._last_gc_time            = datetime.now()

        self._startup_load()

    def _startup_load(self):
        """تحميل جميع الجداول بالتوازي عند التشغيل"""
        print("✅ [Startup] Pre-loading all tables in parallel into RAM Cache...")
        
        import concurrent.futures
        
        def load_settings():
            self.load_setting('bot_settings')
            self.load_setting('risk_settings')
        
        def load_news():
            self.get_news_data()
            for symbol in SYMBOLS:
                self.get_news_data(symbol)
        
        def load_learning():
            self.get_learning_data()
        
        def load_symbol_memories():
            for symbol in SYMBOLS:
                self.get_symbol_memory(symbol)
        
        def load_patterns():
            self.load_all_patterns()
        
        def load_positions():
            self.load_positions()
        
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
        """جلب الأخبار من جدول news_sentiment عبر storage مباشرة"""
        cache_key = f"news_{symbol}" if symbol else "news_all"
        now       = datetime.now()

        # رجّع من الكاش لو صالح
        data = self.mem_cache.get(cache_key)
        last_update = self._last_news_update.get(cache_key)
        if data is not None and last_update is not None:
            if (now - last_update).total_seconds() < 1800:
                return data

        # اقرأ من DB عبر storage
        try:
            result = self.storage.get_news_data(symbol)
            self._last_news_update[cache_key] = now
            self.mem_cache.set(cache_key, result or {}, expiry_seconds=1800)
            return result
        except Exception as e:
            print(f"⚠️ get_news_data error [{symbol}]: {e}")
            return data

    def get_learning_data(self):
        """جلب بيانات التعلم: تحديث كل 30 دقيقة من DB، وبقية الوقت من الكاش المضغوط حصراً"""
        cache_key   = "king_learning_data"
        now         = datetime.now()
        cached_data = self.mem_cache.get(cache_key)

        if cached_data is None or self._last_learning_update is None or (now - self._last_learning_update).total_seconds() > 1800:
            self._last_learning_update = now
            
            if hasattr(self.storage, 'load_setting'):
                try:
                    db_data = self.storage.load_setting(cache_key)
                    if db_data:
                        self.mem_cache.set(cache_key, db_data, expiry_seconds=1800)
                        print(f"🧠 King Learning Data updated in compressed cache (30m cycle)")
                except Exception as e:
                    print(f"⚠️ Error loading learning data from DB: {e}")
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
            self.mem_cache.delete('all_trades')
        return res
    
    def load_trades(self, limit=None):
        """تحميل الصفقات"""
        return self.storage.load_trades(limit)
    
    def get_all_trades(self):
        """جلب جميع الصفقات من الكاش المضغوط"""
        cache_key     = "all_trades"
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
        self.mem_cache.delete('all_patterns')
        return self.storage.save_pattern(pattern_data)

    def load_all_patterns(self):
        """تحميل كل الأنماط من الكاش المضغوط"""
        cache_key = "all_patterns"
        cached    = self.mem_cache.get(cache_key)
        if cached:
            return cached

        try:
            patterns = self.storage.load_all_patterns()
            if patterns:
                self.mem_cache.set(cache_key, patterns, expiry_seconds=7200)
            return patterns
        except Exception as e:
            print(f"⚠️ Error loading patterns: {e}")
            return []

    def update_symbol_memory(self, *args, **kwargs):
        """تحديث ذاكرة العملة"""
        if hasattr(self.storage, 'update_symbol_memory'):
            symbol = kwargs.get('symbol') or (args[0] if args else None)
            if symbol:
                self.mem_cache.delete(f"symbol_mem_{symbol}")

            if symbol and len(args) >= 2 and isinstance(args[1], dict) and not kwargs:
                current = self.get_symbol_memory(symbol)
                merged = {**current, **args[1]} if isinstance(current, dict) else args[1]
                self.mem_cache.set(f"symbol_mem_{symbol}", merged, expiry_seconds=1800)
                if self.mode == 'local':
                    return self.storage.update_symbol_memory(symbol, merged)
                return True

            return self.storage.update_symbol_memory(*args, **kwargs)
        return False

    def save_symbol_memory(self, symbol, memory):
        """توافق مع المودلز التي تحفظ ذاكرة العملة كاملة."""
        return self.update_symbol_memory(symbol, memory)

    def get_symbol_memory(self, symbol):
        """جلب ذاكرة العملة الشاملة"""
        cache_key   = f"symbol_mem_{symbol}"
        now         = datetime.now()
        cached_data = self.mem_cache.get(cache_key)
        
        last_update = self._last_symbol_mem_update.get(symbol)
        if cached_data is None or last_update is None or (now - last_update).total_seconds() > 1800:
            self._last_symbol_mem_update[symbol] = now
            try:
                data = self.storage.get_symbol_memory(symbol)
                if data:
                    self.mem_cache.set(cache_key, data, expiry_seconds=1800)
            except Exception:
                pass
            cached_data = self.mem_cache.get(cache_key)
        
        return cached_data if cached_data is not None else {}

    # ========== Positions ==========
    @staticmethod
    def _positions_to_cache_dict(positions):
        if isinstance(positions, dict):
            normalized = {}
            for symbol, value in positions.items():
                if not value:
                    continue
                if isinstance(value, dict) and value.get('position'):
                    normalized[symbol] = value['position']
                elif isinstance(value, dict):
                    normalized[symbol] = value
            return normalized
        if isinstance(positions, list):
            return {
                pos.get('symbol'): {k: v for k, v in pos.items() if k != 'symbol'}
                for pos in positions
                if isinstance(pos, dict) and pos.get('symbol')
            }
        return {}

    def save_positions(self, positions):
        """حفظ المراكز المفتوحة دفعة واحدة"""
        normalized_positions = self._positions_to_cache_dict(positions)
        self.mem_cache.set('open_positions', normalized_positions, expiry_seconds=1800)
        res = False
        if self.mode == 'cloud':
            positions_list = [{'symbol': s, **p} for s, p in normalized_positions.items() if p]
            res = self.storage.save_positions_batch(positions_list)
        else:
            res = self.storage.save_positions(normalized_positions)
        gc.collect()
        return res
    
    def load_positions(self):
        """تحميل المراكز المفتوحة من الكاش لتقليل القراءة من DB"""
        cache_key  = "open_positions"
        cached_pos = self.mem_cache.get(cache_key)
        if cached_pos:
            return self._positions_to_cache_dict(cached_pos)

        try:
            positions = self.storage.load_positions()
            positions = self._positions_to_cache_dict(positions)
            self.mem_cache.set(cache_key, positions, expiry_seconds=1800)
            return positions
        except Exception as e:
            print(f"⚠️ Error loading positions: {e}")
            return {}
    
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
        """تحميل إعداد من الداتابيز مع نظام كاش داخلي"""
        cache_key = f"setting_{key}"
        cached    = self.mem_cache.get(cache_key)
        if cached:
            return cached

        if hasattr(self.storage, 'load_setting'):
            try:
                val = self.storage.load_setting(key)
                if val:
                    self.mem_cache.set(cache_key, val, expiry_seconds=1800)
                return val
            except Exception as e:
                print(f"⚠️ Error loading setting {key}: {e}")
                return None
        return None

    def cleanup_old_data(self):
        """التنظيف التلقائي للجداول الأساسية فقط"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False

    def load_model(self, model_name):
        """تحميل الموديل وحفظه في الكاش المضغوط"""
        cache_key    = f"model_{model_name}"
        cached_model = self.mem_cache.get(cache_key)
        
        if cached_model:
            self._periodic_gc()
            return cached_model
        
        try:
            model = self.storage.load_model(model_name)
            if model:
                self.mem_cache.set(cache_key, model, expiry_seconds=None)
                self._periodic_gc()
            return model
        except Exception as e:
            print(f"⚠️ Error loading model {model_name}: {e}")
            return None
    
    def _periodic_gc(self):
        """تنظيف دوري للذاكرة (كل 5 دقائق فقط)"""
        now = datetime.now()
        if (now - self._last_gc_time).total_seconds() > 300:
            gc.collect()
            self._last_gc_time = now

    def print_cache_stats(self):
        """طباعة إحصائيات الكاش"""
        stats = self.mem_cache.get_stats()
        
        print(f"\n📊 Cache Stats:")
        print(f"  Items    : {stats['active_items']}/{stats['max_items']}")
        print(f"  Hit Rate : {stats['hit_ratio']*100:.1f}% ({stats['hits']} hits / {stats['misses']} misses)")
        print(f"  Size     : {stats['original_size']/1024:.1f}KB → {stats['compressed_size']/1024:.1f}KB compressed")
        print(f"  Ratio    : {stats['compression_ratio']*100:.1f}%\n")
