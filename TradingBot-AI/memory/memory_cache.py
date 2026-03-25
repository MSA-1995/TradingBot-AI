# memory_cache.py - في الذاكرة فقط
import time
import gc
from typing import Dict, Any, Optional

class MemoryCache:
    def __init__(self, default_expiry=300, max_items=100):
        self.cache = {}
        self.default_expiry = default_expiry
        self.max_items = max_items  # حد أقصى للعناصر
        self.hits = 0
        self.misses = 0
    
    def set(self, key, value, expiry_seconds=None):
        """يخزن في الذاكرة فقط مع وقت انتهاء"""
        if expiry_seconds is None:
            expiry_seconds = self.default_expiry
        
        # تنظيف ذكي إذا وصلنا للحد الأقصى
        if len(self.cache) >= self.max_items:
            self._cleanup_least_used()
        
        self.cache[key] = {
            'value': value,
            'expiry': time.time() + expiry_seconds,
            'size': self._get_size(value),
            'last_access': time.time()  # لتتبع أقل العناصر استخداماً
        }
        
        # تنظيف تلقائي للقديم
        self._cleanup_expired()
    
    def get(self, key):
        """يجلب من الذاكرة فقط"""
        if key in self.cache:
            data = self.cache[key]
            if time.time() < data['expiry']:
                self.hits += 1
                return data['value']
            else:
                # انتهت الصلاحية، نمسحها
                del self.cache[key]
                self.misses += 1
                gc.collect()  # تنظيف الذاكرة
        else:
            self.misses += 1
        return None
    
    def _cleanup_expired(self):
        """ينظف العناصر المنتهية تلقائياً"""
        current_time = time.time()
        expired_keys = [
            key for key, data in self.cache.items() 
            if current_time >= data['expiry']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            gc.collect()  # تنظيف الذاكرة بعد الحذف
    
    def _cleanup_least_used(self):
        """ينظف أقل العناصر استخداماً للحفاظ على الحد الأقصى"""
        if len(self.cache) < self.max_items:
            return
        
        # نرتب حسب آخر وصول ونحذف 20% من الأقدم
        sorted_items = sorted(
            self.cache.items(), 
            key=lambda x: x[1].get('last_access', 0)
        )
        
        items_to_remove = int(self.max_items * 0.2)  # حذف 20%
        for i, (key, _) in enumerate(sorted_items[:items_to_remove]):
            del self.cache[key]
        
        gc.collect()
    
    def _get_size(self, obj):
        """يحسب حجم العنصر في الذاكرة"""
        if isinstance(obj, (str, int, float)):
            return len(str(obj))
        elif isinstance(obj, (list, dict)):
            return len(str(obj)) // 4  # تقديري
        return 1
    
    def get_stats(self):
        """يعطي إحصائيات الاستخدام"""
        total_size = sum(data['size'] for data in self.cache.values())
        return {
            'active_items': len(self.cache),
            'total_size': total_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_ratio': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }
    
    def clear_all(self):
        """يمسح كل الكاش وينظف الذاكرة"""
        self.cache.clear()
        gc.collect()
        self.hits = 0
        self.misses = 0