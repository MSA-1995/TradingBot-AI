# memory_cache.py - في الذاكرة فقط مع ضغط gzip

import gc
import gzip
import pickle
import sys
import time
from typing import Any, Dict, Optional

_USE_DEFAULT_EXPIRY = object()


class MemoryCache:
    """كاش في الذاكرة مع ضغط gzip تلقائي"""

    # ─── إعدادات افتراضية ───
    DEFAULT_EXPIRY       = 300    # ثانية
    DEFAULT_MAX_ITEMS    = 100
    CLEANUP_RATIO        = 0.2    # 20% من العناصر تُحذف عند الامتلاء

    def __init__(self, default_expiry: int = DEFAULT_EXPIRY,
                 max_items: int = DEFAULT_MAX_ITEMS):
        self.cache:          Dict[str, dict] = {}
        self.default_expiry: int             = default_expiry
        self.max_items:      int             = max_items
        self.hits:           int             = 0
        self.misses:         int             = 0

    # ─────────────────────────────────────────────
    # العمليات الأساسية
    # ─────────────────────────────────────────────

    def set(self, key: str, value: Any,
            expiry_seconds: Optional[int] = _USE_DEFAULT_EXPIRY) -> None:
        """يخزن قيمة في الكاش مع ضغط gzip"""
        now = time.time()
        if expiry_seconds is _USE_DEFAULT_EXPIRY:
            expiry = now + self.default_expiry
        elif expiry_seconds is None:
            expiry = None
        elif expiry_seconds <= 0:
            expiry = now + self.default_expiry
        else:
            expiry = now + expiry_seconds
        compressed_value = self._compress_data(value)

        # تنظيف عند الامتلاء
        if len(self.cache) >= self.max_items:
            self._cleanup_least_used()

        self.cache[key] = {
            'value':           compressed_value,
            'expiry':          expiry,
            'original_size':   self._get_size(value),
            'compressed_size': len(compressed_value),
            'last_access':     now
        }

    def get(self, key: str) -> Optional[Any]:
        """يجلب قيمة من الكاش مع فك الضغط"""
        entry = self.cache.get(key)

        if entry is None:
            self.misses += 1
            return None

        if entry['expiry'] is not None and time.time() >= entry['expiry']:
            del self.cache[key]
            self.misses += 1
            return None

        self.hits                    += 1
        self.cache[key]['last_access'] = time.time()
        return self._decompress_data(entry['value'])

    def delete(self, key: str) -> bool:
        """حذف عنصر معين من الكاش"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear_all(self) -> None:
        """مسح كل الكاش وإعادة تعيين الإحصائيات"""
        self.cache.clear()
        self.hits   = 0
        self.misses = 0
        gc.collect()

    def get_item(self, key: str) -> Optional[dict]:
        """يجلب عنصر مع معلوماته الكاملة"""
        entry = self.cache.get(key)
        if not entry:
            return None

        now = time.time()
        if entry['expiry'] is not None and now >= entry['expiry']:
            del self.cache[key]
            return None

        return {
            'value':           self._decompress_data(entry['value']),
            'original_size':   entry.get('original_size', 0),
            'compressed_size': entry.get('compressed_size', 0),
            'age':             now - entry['last_access'],
            'expires_in':      None if entry['expiry'] is None else entry['expiry'] - now
        }

    # ─────────────────────────────────────────────
    # التنظيف
    # ─────────────────────────────────────────────

    def _cleanup_expired(self) -> int:
        """ينظف العناصر المنتهية - يرجع عدد المحذوفات"""
        now          = time.time()
        expired_keys = [k for k, v in self.cache.items()
                        if v.get('expiry') is not None and now >= v['expiry']]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)

    def _cleanup_least_used(self) -> int:
        """يحذف أقل العناصر استخداماً عند الامتلاء"""
        if len(self.cache) < self.max_items:
            return 0

        sorted_items   = sorted(self.cache.items(),
                                key=lambda x: x[1].get('last_access', 0))
        items_to_remove = max(1, int(self.max_items * self.CLEANUP_RATIO))

        for key, _ in sorted_items[:items_to_remove]:
            del self.cache[key]

        return items_to_remove

    # ─────────────────────────────────────────────
    # الإحصائيات
    # ─────────────────────────────────────────────

    def get_stats(self) -> dict:
        """إحصائيات شاملة للكاش"""
        total_original   = sum(v.get('original_size',   0) for v in self.cache.values())
        total_compressed = sum(v.get('compressed_size', 0) for v in self.cache.values())
        total_requests   = self.hits + self.misses

        return {
            'active_items':      len(self.cache),
            'max_items':         self.max_items,
            'original_size':     total_original,
            'compressed_size':   total_compressed,
            'compression_ratio': (total_compressed / total_original
                                  if total_original > 0 else 1.0),
            'hits':              self.hits,
            'misses':            self.misses,
            'hit_ratio':         (self.hits / total_requests
                                  if total_requests > 0 else 0.0)
        }

    # ─────────────────────────────────────────────
    # الضغط وفك الضغط
    # ─────────────────────────────────────────────

    @staticmethod
    @staticmethod
    def _compress_data(data: Any) -> bytes:
        """يضغط البيانات بـ gzip فقط لو كانت أكبر من 1KB"""
        try:
            raw = pickle.dumps(data)
            # ✅ اضغط فقط لو الحجم أكبر من 1KB
            if len(raw) > 1024:
                compressed = gzip.compress(raw)
                # ✅ استخدم المضغوط فقط لو أصغر فعلاً
                if len(compressed) < len(raw):
                    return b'gz:' + compressed
            return b'raw:' + raw
        except Exception as e:
            print(f"⚠️ _compress_data error: {e}")
            return pickle.dumps(data)

    @staticmethod
    def _decompress_data(compressed_data: bytes) -> Any:
        """يفك ضغط البيانات"""
        try:
            if compressed_data.startswith(b'gz:'):
                return pickle.loads(gzip.decompress(compressed_data[3:]))
            elif compressed_data.startswith(b'raw:'):
                return pickle.loads(compressed_data[4:])
            else:
                # fallback للبيانات القديمة
                try:
                    return pickle.loads(gzip.decompress(compressed_data))
                except Exception:
                    return pickle.loads(compressed_data)
        except Exception as e:
            print(f"⚠️ _decompress_data error: {e}")
            return None

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    @staticmethod
    def _get_size(obj: Any) -> int:
        """يحسب الحجم الفعلي بعد التسلسل"""
        try:
            return len(pickle.dumps(obj))  # ✅ الحجم الحقيقي
        except Exception:
            try:
                return sys.getsizeof(obj)
            except Exception:
                return len(str(obj))
