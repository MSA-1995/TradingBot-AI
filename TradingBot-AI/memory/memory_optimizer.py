# memory_optimizer.py - المدير الرئيسي

import gc
import time
from typing import Any, Optional

from .memory_cache import MemoryCache
from .memory_compressor import MemoryCompressor
from .memory_cleaner import MemoryCleaner


class MemoryOptimizer:
    """يدير كل نظام تحسين الذاكرة"""

    # ─── إعدادات الكاش ───
    CACHE_MAX_ITEMS          = 50
    ANALYSIS_CACHE_TTL       = 120    # ثانية
    CANDLES_CACHE_TTL        = 300    # ثانية
    DEFAULT_TTL              = 3600   # ثانية

    # ─── حدود الضغط ───
    COMPRESS_SIZE_THRESHOLD  = 5_000   # 5KB
    CANDLES_SIZE_THRESHOLD   = 10_000  # 10KB

    # ─── حدود صحة الذاكرة ───
    HEALTH_GOOD_THRESHOLD    = 70
    HEALTH_WARNING_THRESHOLD = 40
    MEMORY_CRITICAL_PERCENT  = 90
    CACHE_MIN_HIT_RATIO      = 0.5
    TTL_DATA_MAX_COUNT       = 50

    # ─── عقوبات الصحة ───
    PENALTY_HIGH_MEMORY      = 20
    PENALTY_LOW_HIT_RATIO    = 10
    PENALTY_MANY_TTL         = 5

    def __init__(self, cleanup_interval: int = 300,
                 memory_threshold: int = 80):
        self.cache      = MemoryCache(max_items=self.CACHE_MAX_ITEMS)
        self.compressor = MemoryCompressor()
        self.cleaner    = MemoryCleaner(cleanup_interval, memory_threshold)

        self._ttl_data: dict = {}
        self._context  = {
            'memory_cache':      self.cache,
            'memory_compressor': self.compressor,
            'memory_cleaner':    self.cleaner
        }
        self.last_aggressive_cleanup = time.time()

    # ─────────────────────────────────────────────
    # تحسين البيانات
    # ─────────────────────────────────────────────

    def optimize_analysis_data(self, symbol: str, analysis_data: dict) -> dict:
        """يحسن بيانات التحليل (كاش + ضغط)"""
        cache_key     = f"{symbol}_analysis"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result

        if self._should_compress(analysis_data):
            compressed = self.compressor.compress_analysis_result(analysis_data)
            if compressed:
                analysis_data = compressed

        self.cache.set(cache_key, analysis_data,
                       expiry_seconds=self.ANALYSIS_CACHE_TTL)
        return analysis_data

    def optimize_candles_data(self, symbol: str, candles_data) -> Any:
        """يحسن بيانات الشموع (كاش + ضغط)"""
        cache_key     = f"{symbol}_candles"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result

        if len(str(candles_data)) > self.CANDLES_SIZE_THRESHOLD:
            compressed = self.compressor.compress_candles(candles_data)
            if compressed:
                candles_data = compressed

        self.cache.set(cache_key, candles_data,
                       expiry_seconds=self.CANDLES_CACHE_TTL)
        return candles_data

    # ─────────────────────────────────────────────
    # بيانات TTL
    # ─────────────────────────────────────────────

    def store_important_data(self, key: str, data: Any,
                              ttl: int = DEFAULT_TTL) -> None:
        """يخزن بيانات مهمة بعمر افتراضي"""
        self._ttl_data[key] = {
            'data':    data,
            'expires': time.time() + ttl
        }

    def get_important_data(self, key: str) -> Optional[Any]:
        """يجلب بيانات مهمة إذا لم تنتهِ صلاحيتها"""
        item = self._ttl_data.get(key)
        if not item:
            return None

        if time.time() < item['expires']:
            return item['data']

        del self._ttl_data[key]
        return None

    def cleanup_expired_ttl(self) -> int:
        """يحذف بيانات TTL المنتهية - يرجع عدد المحذوفات"""
        now     = time.time()
        expired = [k for k, v in self._ttl_data.items()
                   if now >= v['expires']]
        for key in expired:
            del self._ttl_data[key]
        return len(expired)

    # ─────────────────────────────────────────────
    # التنظيف
    # ─────────────────────────────────────────────

    def periodic_cleanup(self) -> dict:
        """ينظف الذاكرة دورياً"""
        return self.cleaner.safe_cleanup(self._context)

    def force_cleanup(self) -> dict:
        """تنظيف إجباري فوري"""
        self.cache.clear_all()
        self.cleanup_expired_ttl()
        gc.collect()
        return {'status': 'Force cleanup completed'}

    # ─────────────────────────────────────────────
    # الإحصائيات والصحة
    # ─────────────────────────────────────────────

    def get_stats(self) -> dict:
        """إحصائيات شاملة للذاكرة"""
        return {
            'cache_stats':        self.cache.get_stats(),
            'memory_status':      self.cleaner.get_memory_status(),
            'ttl_data_count':     len(self._ttl_data),
            'total_optimization': 'Active'
        }

    def get_memory_health(self) -> dict:
        """تقرير صحة الذاكرة مع توصيات"""
        status = self.cleaner.get_memory_status()
        cache  = self.cache.get_stats()

        health_score = self._calculate_health_score(status, cache)
        health_label = self._health_label(health_score)

        return {
            'score':           max(0, health_score),
            'status':          health_label,
            'recommendations': self._get_recommendations(health_score, status, cache)
        }

    def _calculate_health_score(self, status: dict, cache: dict) -> int:
        """حساب نقاط صحة الذاكرة"""
        score = 100

        if status.get('used_percent', 0) > self.MEMORY_CRITICAL_PERCENT:
            score -= self.PENALTY_HIGH_MEMORY

        if cache.get('hit_ratio', 1.0) < self.CACHE_MIN_HIT_RATIO:
            score -= self.PENALTY_LOW_HIT_RATIO

        if len(self._ttl_data) > self.TTL_DATA_MAX_COUNT:
            score -= self.PENALTY_MANY_TTL

        return score

    def _health_label(self, score: int) -> str:
        """تحويل النقاط إلى تصنيف"""
        if score > self.HEALTH_GOOD_THRESHOLD:
            return 'Good'
        if score > self.HEALTH_WARNING_THRESHOLD:
            return 'Warning'
        return 'Critical'

    def _get_recommendations(self, score: int,
                              status: dict, cache: dict) -> list[str]:
        """توصيات لتحسين الذاكرة"""
        recommendations = []

        if cache.get('hit_ratio', 1.0) < self.CACHE_MIN_HIT_RATIO:
            recommendations.append("نسبة hits منخفضة - راجع استراتيجية الكاش")

        if len(self._ttl_data) > self.TTL_DATA_MAX_COUNT:
            recommendations.append("بيانات TTL كثيرة - نظف البيانات القديمة")

        if status.get('used_percent', 0) > self.MEMORY_CRITICAL_PERCENT:
            recommendations.append("استخدام الذاكرة عالي - شغّل force_cleanup")

        if not recommendations:
            recommendations.append("الذاكرة في حالة جيدة ✅")

        return recommendations

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    def _should_compress(self, data: Any) -> bool:
        """هل البيانات تحتاج ضغط؟"""
        return len(str(data)) > self.COMPRESS_SIZE_THRESHOLD