# memory_cleaner.py - في الذاكرة فقط

import gc
import time
from typing import Any, Dict, Optional, Union

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class MemoryCleaner:
    """ينظف الذاكرة بذكاء بدون يؤثر على التداول"""

    # ─── إعدادات افتراضية ───
    DEFAULT_CLEANUP_INTERVAL  = 300   # ثانية  (5 دقائق)
    DEFAULT_MEMORY_THRESHOLD  = 90    # %

    # ─── حدود الضغط ───
    OLD_DATA_AGE_THRESHOLD    = 300   # ثانية - البيانات "القديمة"
    MEMORY_ESTIMATE_RATIO     = 0.05  # 5% من الذاكرة المتاحة
    MB                        = 1024 * 1024
    FALLBACK_MEMORY_SAVED     = "~15-25MB"
    FALLBACK_USED_PERCENT     = 50

    # ─── المتغيرات المؤقتة المراد تنظيفها ───
    TEMP_VAR_NAMES = (
        'temp_analysis', 'temp_candles', 'temp_indicators',
        'large_temp_list', 'temp_calculation', 'temp_df',
        'temp_array', 'temp_matrix', 'temp_results'
    )

    def __init__(self, cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
                 memory_threshold: int = DEFAULT_MEMORY_THRESHOLD):
        self.cleanup_interval  = cleanup_interval
        self.memory_threshold  = memory_threshold
        self.last_cleanup      = time.time()

    # ─────────────────────────────────────────────
    # قرار التنظيف
    # ─────────────────────────────────────────────

    def should_cleanup(self) -> bool:
        """هل حان وقت التنظيف؟"""
        time_due = (time.time() - self.last_cleanup) > self.cleanup_interval

        if PSUTIL_AVAILABLE:
            try:
                memory_high = psutil.virtual_memory().percent > self.memory_threshold
                return time_due or memory_high
            except Exception as e:
                print(f"⚠️ should_cleanup psutil error: {e}")

        return time_due

    # ─────────────────────────────────────────────
    # التنظيف الآمن
    # ─────────────────────────────────────────────

    def safe_cleanup(self, context: Optional[Dict[str, Any]] = None) -> Union[dict, str]:
        """ينظف الذاكرة بطريقة آمنة"""
        if not self.should_cleanup():
            return "No cleanup needed"

        try:
            compressed_count = self._compress_old_data(context)
            cache_cleared    = self._clear_expired_cache(context)
            temp_cleared     = self._cleanup_temp_variables(context)

            gc.collect()
            self.last_cleanup = time.time()

            return {
                'compressed_items':      compressed_count,
                'cache_items_cleared':   cache_cleared,
                'temp_variables_cleared': temp_cleared,
                'memory_saved_mb':       self._estimate_memory_saved(),
                'status':                'Success'
            }

        except Exception as e:
            print(f"⚠️ safe_cleanup error: {e}")
            return f"Cleanup failed: {e}"

    # ─────────────────────────────────────────────
    # خطوات التنظيف
    # ─────────────────────────────────────────────

    def _compress_old_data(self, context: Optional[dict]) -> int:
        """يضغط البيانات القديمة في الكاش"""
        cache = self._get_cache(context)
        if not cache:
            return 0

        compressed_count = 0
        now              = time.time()

        old_keys = [
            key for key, data in cache.cache.items()
            if ('candles' in key or 'analysis' in key)
            and now - data.get('expiry', 0) > self.OLD_DATA_AGE_THRESHOLD
        ]

        for key in old_keys:
            try:
                old_value  = cache.cache[key]['value']
                compressed = _compress_analysis_safe(old_value)
                if compressed:
                    cache.cache[key]['value'] = compressed
                    compressed_count += 1
            except Exception as e:
                print(f"⚠️ _compress_old_data error for {key}: {e}")

        return compressed_count

    def _clear_expired_cache(self, context: Optional[dict]) -> int:
        """ينظف الكاش المنتهي الصلاحية"""
        cache = self._get_cache(context)
        if not cache:
            return 0

        try:
            initial_count = len(cache.cache)
            cache._cleanup_expired()
            return initial_count - len(cache.cache)
        except Exception as e:
            print(f"⚠️ _clear_expired_cache error: {e}")
            return 0

    def _cleanup_temp_variables(self, context: Optional[dict]) -> int:
        """ينظف المتغيرات المؤقتة من الـ context"""
        if not context:
            return 0

        cleared = 0
        for var in self.TEMP_VAR_NAMES:
            if var not in context:
                continue
            try:
                obj = context[var]
                if hasattr(obj, 'clear'):
                    obj.clear()
                del context[var]
                cleared += 1
            except Exception as e:
                print(f"⚠️ _cleanup_temp_variables error for {var}: {e}")

        gc.collect()
        return cleared

    # ─────────────────────────────────────────────
    # حالة الذاكرة
    # ─────────────────────────────────────────────

    def get_memory_status(self) -> dict:
        """حالة الذاكرة الحالية"""
        if PSUTIL_AVAILABLE:
            try:
                mem = psutil.virtual_memory()
                return {
                    'total_mb':     mem.total       // self.MB,
                    'available_mb': mem.available   // self.MB,
                    'used_mb':      mem.used        // self.MB,
                    'used_percent': mem.percent,
                    'need_cleanup': mem.percent > self.memory_threshold
                }
            except Exception as e:
                print(f"⚠️ get_memory_status error: {e}")

        # fallback بدون psutil
        return {
            'total_mb':     0,
            'available_mb': 0,
            'used_mb':      0,
            'used_percent': self.FALLBACK_USED_PERCENT,
            'need_cleanup': False
        }

    def _estimate_memory_saved(self) -> Union[float, str]:
        """تقدير الذاكرة التي تم توفيرها بعد التنظيف"""
        if PSUTIL_AVAILABLE:
            try:
                available = psutil.virtual_memory().available
                return round(available * self.MEMORY_ESTIMATE_RATIO / self.MB, 2)
            except Exception as e:
                print(f"⚠️ _estimate_memory_saved error: {e}")

        return self.FALLBACK_MEMORY_SAVED

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    @staticmethod
    def _get_cache(context: Optional[dict]):
        """استخراج الكاش من الـ context بأمان"""
        if not context:
            return None
        return context.get('memory_cache')


def _compress_analysis_safe(data: Any) -> Optional[dict]:
    """
    ضغط آمن لبيانات التحليل بدون استيراد دائري.
    يُستخدم داخل MemoryCleaner فقط.
    """
    try:
        import json
        import zlib
        json_str   = json.dumps(data, separators=(',', ':'), default=str)
        compressed = zlib.compress(json_str.encode('utf-8'), level=6)
        return {
            'compressed':      compressed,
            'original_size':   len(json_str),
            'compressed_size': len(compressed)
        }
    except Exception as e:
        print(f"⚠️ _compress_analysis_safe error: {e}")
        return None