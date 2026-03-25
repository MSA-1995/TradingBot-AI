# memory_optimizer.py - المدير الرئيسي
from memory_cache import MemoryCache
from memory_compressor import MemoryCompressor
from memory_cleaner import MemoryCleaner

class MemoryOptimizer:
    """يدير كل نظام تحسين الذاكرة"""
    
    def __init__(self, max_memory_percent=75, cleanup_interval=5):
        self.cache = MemoryCache(max_items=50)  # تقليل العناصر
        self.compressor = MemoryCompressor()
        self.cleaner = MemoryCleaner()
        self.max_memory_percent = max_memory_percent  # نسبة الذاكرة القصوى
        self.cleanup_interval = cleanup_interval  # فاصل التنظيف
        self.last_aggressive_cleanup = time.time()
        self.context = {
            'memory_cache': self.cache,
            'memory_compressor': self.compressor,
            'memory_cleaner': self.cleaner
        }
    
    def optimize_analysis_data(self, symbol, analysis_data):
        """يحسن بيانات التحليل"""
        cache_key = f"{symbol}_analysis"
        
        # نجرب نجيب من الكاش أولاً
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # نضغط البيانات الكبيرة
        if self._should_compress(analysis_data):
            compressed = self.compressor.compress_analysis_result(analysis_data)
            if compressed:
                analysis_data = compressed
        
        # نخزن في الكاش
        self.cache.set(cache_key, analysis_data, expiry_seconds=300)
        
        return analysis_data
    
    def optimize_candles_data(self, symbol, candles_data):
        """يحسن بيانات الشموع"""
        cache_key = f"{symbol}_candles"
        
        # نجرب الكاش
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # نضغط البيانات الكبيرة
        if len(str(candles_data)) > 10000:  # أكثر من 10KB
            compressed = self.compressor.compress_candles(candles_data)
            if compressed:
                candles_data = compressed
        
        # نخزن في الكاش
        self.cache.set(cache_key, candles_data, expiry_seconds=600)
        
        return candles_data
    
    def periodic_cleanup(self):
        """ينظف الذاكرة دورياً"""
        return self.cleaner.safe_cleanup(self.context)
    
    def get_stats(self):
        """يعطي إحصائيات الذاكرة"""
        cache_stats = self.cache.get_stats()
        memory_status = self.cleaner.get_memory_status()
        
        return {
            'cache_stats': cache_stats,
            'memory_status': memory_status,
            'total_optimization': 'Active'
        }
    
    def _should_compress(self, data):
        """يحدد إذا كان لازم نضغط"""
        data_size = len(str(data))
        return data_size > 5000  # أكثر من 5KB نضغطها
