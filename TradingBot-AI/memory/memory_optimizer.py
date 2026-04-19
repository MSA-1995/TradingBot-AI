# memory_optimizer.py - المدير الرئيسي
import time
import gc
from .memory_cache import MemoryCache
from .memory_compressor import MemoryCompressor
from .memory_cleaner import MemoryCleaner

class MemoryOptimizer:
    """يدير كل نظام تحسين الذاكرة"""
    
    def __init__(self, cleanup_interval=300, memory_threshold=80):
        self.cache = MemoryCache(max_items=50)  # مخفض لتوفير الذاكرة
        self.compressor = MemoryCompressor()
        self.cleaner = MemoryCleaner(cleanup_interval, memory_threshold)
        self.last_aggressive_cleanup = time.time()
        self.context = {
            'memory_cache': self.cache,
            'memory_compressor': self.compressor,
            'memory_cleaner': self.cleaner
        }
        self._ttl_data = {}  # البيانات المهمة بعمر افتراضي
    
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
        self.cache.set(cache_key, analysis_data, expiry_seconds=120)  # مخفض من 300 إلى 120
        
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
        self.cache.set(cache_key, candles_data, expiry_seconds=300)  # مخفض من 600 إلى 300
        
        return candles_data
    
    def store_important_data(self, key, data, ttl=3600):
        """يخزن بيانات مهمة ب TTL أطول"""
        self._ttl_data[key] = {
            'data': data,
            'expires': time.time() + ttl
        }
    
    def get_important_data(self, key):
        """يجلب بيانات مهمة"""
        if key in self._ttl_data:
            item = self._ttl_data[key]
            if time.time() < item['expires']:
                return item['data']
            else:
                del self._ttl_data[key]
        return None
    
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
            'ttl_data_count': len(self._ttl_data),
            'total_optimization': 'Active'
        }
    
    def _should_compress(self, data):
        """يحدد إذا كان لازم نضغط"""
        data_size = len(str(data))
        return data_size > 5000  # أكثر من 5KB نضغطها
    
    def force_cleanup(self):
        """تنظيف إجباري"""
        self.cache.clear_all()
        gc.collect()
        return {'status': 'Force cleanup completed'}
    
    def get_memory_health(self):
        """يعطي صحة الذاكرة"""
        status = self.cleaner.get_memory_status()
        cache = self.cache.get_stats()
        
        # حساب صحة الذاكرة
        health_score = 100
        
        if status['used_percent'] > 90:
            health_score -= 20
        
        if cache['hit_ratio'] < 0.5:
            health_score -= 10
        
        if len(self._ttl_data) > 50:
            health_score -= 5
        
        return {
            'score': max(0, health_score),
            'status': 'Good' if health_score > 70 else 'Warning' if health_score > 40 else 'Critical',
            'recommendations': self._get_recommendations(health_score, status, cache)
        }
    
    def _get_recommendations(self, score, status, cache):
        """يعطي توصيات لتحسين الذاكرة"""
        recommendations = []
        
        if cache['hit_ratio'] < 0.5:
            recommendations.append("نسبة hits منخفضة - راجع استراتيجية الكاش")
        
        if len(self._ttl_data) > 50:
            recommendations.append("بيانات TTL كثيرة - نظف البيانات القديمة")
        
        if not recommendations:
            recommendations.append("الذاكرة في حالة جيدة ✅")
        
        return recommendations
