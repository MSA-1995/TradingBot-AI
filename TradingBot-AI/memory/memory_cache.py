# memory_cache.py - في الذاكرة فقط مع ضغط gzip
import time
import gc
import sys
import gzip
import pickle
from typing import Dict, Any, Optional

class MemoryCache:
    def __init__(self, default_expiry=300, max_items=100):
        self.cache = {}
        self.default_expiry = default_expiry
        self.max_items = max_items  # حد أقصى للعناصر (تم رفعه)
        self.hits = 0
        self.misses = 0
    
    def set(self, key, value, expiry_seconds=None):
        """يخزن في الذاكرة مع ضغط gzip"""
        if expiry_seconds is None:
            expiry_seconds = self.default_expiry

        compressed_value = self._compress_data(value)

        if len(self.cache) >= self.max_items:
            self._cleanup_least_used()

        self.cache[key] = {
            'value': compressed_value,
            'expiry': time.time() + expiry_seconds,
            'original_size': self._get_size(value),
            'compressed_size': len(compressed_value),
            'last_access': time.time()
        }
    
    def get(self, key):
        """يجلب من الذاكرة مع فك الضغط"""
        if key in self.cache:
            data = self.cache[key]
            if time.time() < data['expiry']:
                self.hits += 1
                self.cache[key]['last_access'] = time.time()
                return self._decompress_data(data['value'])
            else:
                del self.cache[key]
                self.misses += 1
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
    
    def _cleanup_least_used(self):
        """ينظف أقل العناصر استخداماً للحفاظ على الحد الأقصى"""
        if len(self.cache) < self.max_items:
            return
        
        sorted_items = sorted(
            self.cache.items(), 
            key=lambda x: x[1].get('last_access', 0)
        )
        
        items_to_remove = int(self.max_items * 0.2)
        for i, (key, _) in enumerate(sorted_items[:items_to_remove]):
            del self.cache[key]
    
    def _get_size(self, obj):
        """يحسب حجم العنصر في الذاكرة بدقة"""
        try:
            return sys.getsizeof(obj)
        except:
            return len(str(obj))
    
    def get_stats(self):
        """يعطي إحصائيات الاستخدام"""
        total_size = sum(data['size'] for data in self.cache.values())
        compressed_size = sum(v.get('compressed_size', v.get('size', 0)) for v in self.cache.values())

        return {
            'active_items': len(self.cache),
            'max_items': self.max_items,
            'total_size': total_size,
            'compressed_size': compressed_size,
            'compression_ratio': compressed_size / total_size if total_size > 0 else 1.0,
            'hits': self.hits,
            'misses': self.misses,
            'hit_ratio': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }

    def _compress_data(self, data):
        """ضغط البيانات بـ gzip"""
        try:
            pickled_data = pickle.dumps(data)
            compressed = gzip.compress(pickled_data)
            return compressed
        except Exception:
            return pickle.dumps(data)

    def _decompress_data(self, compressed_data):
        """فك ضغط البيانات من gzip"""
        try:
            decompressed = gzip.decompress(compressed_data)
            return pickle.loads(decompressed)
        except Exception:
            return pickle.loads(compressed_data)

    def clear_all(self):
        """يمسح كل الكاش وينظف الذاكرة"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def delete(self, key):
        """حذف عنصر معين من الكاش"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def get_item(self, key):
        """يجلب عنصر معين مع معلوماته"""
        if key in self.cache:
            data = self.cache[key]
            if time.time() < data['expiry']:
                return {
                    'value': data['value'],
                    'size': data['size'],
                    'age': time.time() - data['last_access'],
                    'expires_in': data['expiry'] - time.time()
                }
        return None
