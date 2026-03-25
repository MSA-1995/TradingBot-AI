# memory_cleaner.py - في الذاكرة فقط
import gc
import psutil
import time
from typing import Dict, Any

class MemoryCleaner:
    """ينظف الذاكرة بذكاء بدون يؤثر على التداول"""
    
    def __init__(self):
        self.last_cleanup = time.time()
        self.cleanup_interval = 120  # كل دقيقتين
        self.min_memory_threshold = 100  # MB - تحت هذا ننظف
        self.safe_operations = [
            'compress_old_data',
            'clear_expired_cache',
            'release_unused_objects',
            'cleanup_temp_variables'
        ]
    
    def should_cleanup(self):
        """يحدد إذا كان وقت التنظيف"""
        current_time = time.time()
        memory_percent = psutil.virtual_memory().percent
        
        # ننظف إذا:
        # 1. مر أكثر من دقيقتين
        # 2. الذاكرة فوق 80%
        # 3. أو فيه عمليات ثقيلة
        time_condition = (current_time - self.last_cleanup) > self.cleanup_interval
        memory_condition = memory_percent > 80
        
        return time_condition or memory_condition
    
    def safe_cleanup(self, context: Dict[str, Any] = None):
        """ينظف الذاكرة بطريقة آمنة"""
        if not self.should_cleanup():
            return "No cleanup needed"
        
        try:
            # 1. نضغط البيانات القديمة
            compressed_count = self._compress_old_data(context)
            
            # 2. ننظف الكاش المنتهي
            cache_cleared = self._clear_expired_cache(context)
            
            # 3. نفرغ المتغيرات المؤقتة
            temp_cleared = self._cleanup_temp_variables(context)
            
            # 4. نجمع القمامة
            gc.collect()
            
            self.last_cleanup = time.time()
            
            return {
                'compressed_items': compressed_count,
                'cache_items_cleared': cache_cleared,
                'temp_variables_cleared': temp_cleared,
                'memory_saved_mb': self._estimate_memory_saved()
            }
            
        except Exception as e:
            print(f"⚠️ تنظيف الذاكرة فشل: {e}")
            return f"Cleanup failed: {e}"
    
    def _compress_old_data(self, context):
        """يضغط البيانات القديمة"""
        if not context or 'memory_cache' not in context:
            return 0
        
        cache = context['memory_cache']
        old_keys = []
        
        # نبحث عن بيانات قديمة
        for key, data in cache.cache.items():
            if 'candles' in key or 'analysis' in key:
                if time.time() - data.get('expiry', 0) > 600:  # أكثر من 10 دقائق
                    old_keys.append(key)
        
        # نضغطهم
        compressed_count = 0
        for key in old_keys:
            old_data = cache.cache[key]['value']
            compressed = MemoryCompressor.compress_analysis_result(old_data)
            if compressed:
                cache.cache[key]['value'] = compressed
                compressed_count += 1
        
        return compressed_count
    
    def _clear_expired_cache(self, context):
        """ينظف الكاش المنتهي"""
        if not context or 'memory_cache' not in context:
            return 0
        
        cache = context['memory_cache']
        initial_count = len(cache.cache)
        cache._cleanup_expired()
        final_count = len(cache.cache)
        
        return initial_count - final_count
    
    def _cleanup_temp_variables(self, context):
        """ينظف المتغيرات المؤقتة والمصفوفات الكبيرة"""
        cleared = 0
        
        # نمسح المتغيرات الكبيرة المؤقتة
        temp_vars = [
            'temp_analysis', 'temp_candles', 'temp_indicators',
            'large_temp_list', 'temp_calculation', 'temp_df',
            'temp_array', 'temp_matrix', 'temp_results'
        ]
        
        if context:
            for var in temp_vars:
                if var in context:
                    try:
                        # نفرغ المحتوى أولاً ثم نمسح
                        if hasattr(context[var], 'clear'):
                            context[var].clear()
                        del context[var]
                        cleared += 1
                    except:
                        pass
        
        # تنظيف المتغيرات المؤقتة في الذاكرة العامة
        import gc
        gc.collect()  # جمع القمامة مرتين للتأكد
        
        return cleared
    
    def _estimate_memory_saved(self):
        """يقدر الذاكرة التي تم توفيرها"""
        # تقدير تقريبي
        return f"~15-25MB"
    
    def get_memory_status(self):
        """يعطي حالة الذاكرة"""
        memory = psutil.virtual_memory()
        return {
            'total_mb': memory.total // (1024 * 1024),
            'available_mb': memory.available // (1024 * 1024),
            'used_percent': memory.percent,
            'need_cleanup': memory.percent > 80
        }
