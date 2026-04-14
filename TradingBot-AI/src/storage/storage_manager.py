"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً (نسخة مطهرة)
"""
import os
import json
from datetime import datetime

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
        # ====== SMART CACHE (تقليل Egress من Supabase) ======
        # كاش للصفقات - يُستخدم بكثرة من RiskManager في كل دورة
        self.trades_cache = None
        self.trades_cache_time = None
        self.cache_duration = 1800  # 30 دقيقة

        # كاش للأنماط - تتغير نادراً جداً
        self._patterns_cache = None
        self._patterns_cache_time = None
        self._patterns_cache_ttl = 7200  # ساعتين
        # ====================================================
        
        if self.mode == 'cloud':
            from .database_storage import DatabaseStorage
            self.storage = DatabaseStorage()
        else:  # local
            from .local_storage import LocalStorage
            self.storage = LocalStorage('data/')
    
    def detect_environment(self):
        """يكتشف البيئة تلقائياً"""
        database_url = os.getenv('DATABASE_URL')
        return 'cloud' if database_url else 'local'
    
    # ========== Trade Operations ==========
    def save_trade(self, trade_data):
        """حفظ صفقة"""
        return self.storage.save_trade(trade_data)
    
    def load_trades(self, limit=None):
        """تحميل الصفقات"""
        return self.storage.load_trades(limit)
    
    def get_all_trades(self):
        """جلب جميع الصفقات مع Cache لتقليل Egress"""
        try:
            now = datetime.now()
            if self.trades_cache and self.trades_cache_time:
                elapsed = (now - self.trades_cache_time).total_seconds()
                if elapsed < self.cache_duration:
                    return self.trades_cache
            
            trades = self.storage.load_trades(limit=1000)
            self.trades_cache = trades
            self.trades_cache_time = now
            return trades
        except Exception as e:
            print(f"⚠️ Error loading trades: {e}")
            return []

    # ========== Memory & Patterns ==========
    def save_pattern(self, pattern_data):
        """حفظ نمط متعلم"""
        self._patterns_cache = None
        return self.storage.save_pattern(pattern_data)

    def load_all_patterns(self):
        """تحميل كل الأنماط مع Cache"""
        now = datetime.now()
        if self._patterns_cache is not None and self._patterns_cache_time:
            if (now - self._patterns_cache_time).total_seconds() < self._patterns_cache_ttl:
                return self._patterns_cache
        self._patterns_cache = self.storage.load_all_patterns()
        self._patterns_cache_time = now
        return self._patterns_cache

    def update_symbol_memory(self, *args, **kwargs):
        """تحديث ذاكرة العملة (المشاعر، السيولة، الذعر)"""
        if hasattr(self.storage, 'update_symbol_memory'):
            return self.storage.update_symbol_memory(*args, **kwargs)
        return False

    def get_symbol_memory(self, symbol):
        """جلب ذاكرة العملة الشاملة"""
        if hasattr(self.storage, 'get_symbol_memory'):
            return self.storage.get_symbol_memory(symbol)
        return {}

    # ========== Positions ==========
    def save_positions(self, positions):
        """حفظ المراكز المفتوحة دفعة واحدة"""
        if self.mode == 'cloud':
            if isinstance(positions, dict):
                positions_list = [{'symbol': s, **p} for s, p in positions.items() if p]
                return self.storage.save_positions_batch(positions_list)
            elif isinstance(positions, list):
                return self.storage.save_positions_batch(positions)
        else:
            return self.storage.save_positions(positions)
    
    def load_positions(self):
        """تحميل المراكز المفتوحة"""
        return self.storage.load_positions()
    
    def delete_position(self, symbol):
        """حذف صفقة مغلقة"""
        return self.storage.delete_position(symbol)
    
    # ========== Settings & Models ==========
    def save_setting(self, key, value):
        """حفظ إعداد في الداتابيز"""
        if hasattr(self.storage, 'save_setting'):
            return self.storage.save_setting(key, value)
        return False

    def load_setting(self, key):
        """تحميل إعداد من الداتابيز"""
        if hasattr(self.storage, 'load_setting'):
            return self.storage.load_setting(key)
        return None

    def cleanup_old_data(self):
        """التنظيف التلقائي للجداول الأساسية فقط"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False

    def load_model(self, model_name):
        """تحميل الموديل من الداتابيز"""
        return self.storage.load_model(model_name)
