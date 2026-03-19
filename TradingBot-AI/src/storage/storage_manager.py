"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً
"""
import os
import json
from datetime import datetime

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
        # كاش للصفقات (تحسين السرعة)
        self.trades_cache = None
        self.trades_cache_time = None
        self.cache_duration = 60  # ثانية
        
        if self.mode == 'cloud':
            from .database_storage import DatabaseStorage
            self.storage = DatabaseStorage()
        else:  # local
            from .local_storage import LocalStorage
            self.storage = LocalStorage('data/')
    
    def detect_environment(self):
        """يكتشف البيئة تلقائياً"""
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            return 'cloud'  # PostgreSQL فقط (Koyeb)
        else:
            return 'local'  # JSON فقط (جهازك)
    
    # ========== Trade Operations ==========
    def save_trade(self, trade_data):
        """حفظ صفقة"""
        return self.storage.save_trade(trade_data)
    
    def load_trades(self, limit=None):
        """تحميل الصفقات"""
        return self.storage.load_trades(limit)
    
    # ========== Pattern Operations ==========
    def save_pattern(self, pattern_data):
        """حفظ نمط متعلم"""
        return self.storage.save_pattern(pattern_data)
    
    def load_patterns(self):
        """تحميل الأنماط"""
        return self.storage.load_patterns()
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        """حفظ قرار AI"""
        return self.storage.save_ai_decision(decision_data)
    
    def load_ai_decisions(self, limit=10):
        """تحميل قرارات AI"""
        return self.storage.load_ai_decisions(limit)
    
    # ========== Performance Metrics ==========
    def save_performance(self, metrics_data):
        """حفظ مقاييس الأداء"""
        return self.storage.save_performance(metrics_data)
    
    def load_performance(self, days=7):
        """تحميل الأداء"""
        return self.storage.load_performance(days)
    
    # ========== Trap Memory ==========
    def save_trap(self, trap_data):
        """حفظ فخ"""
        return self.storage.save_trap(trap_data)
    
    def load_traps(self):
        """تحميل الفخاخ"""
        return self.storage.load_traps()
    
    # ========== Consultant Votes ==========
    def save_consultant_vote(self, vote_data):
        """حفظ نتيجة تصويت مستشار"""
        return self.storage.save_consultant_vote(vote_data)
    
    def load_consultant_votes(self, consultant_name=None, limit=1000):
        """قراءة نتائج التصويت"""
        return self.storage.load_consultant_votes(consultant_name, limit)
    
    # ========== Positions (الحالي) ==========
    def save_positions(self, positions):
        """حفظ المراكز (متوافق مع النظام الحالي)"""
        return self.storage.save_positions(positions)
    
    def load_positions(self):
        """تحميل المراكز (متوافق مع النظام الحالي)"""
        return self.storage.load_positions()
    
    # ========== Advanced Queries ==========
    def get_all_trades(self):
        """جلب جميع الصفقات (للتحليل) - مع كاش"""
        try:
            # استخدام الكاش إذا كان حديث
            now = datetime.now()
            if self.trades_cache and self.trades_cache_time:
                elapsed = (now - self.trades_cache_time).total_seconds()
                if elapsed < self.cache_duration:
                    return self.trades_cache
            
            # تحديث الكاش
            trades = self.storage.load_trades(limit=1000)
            self.trades_cache = trades
            self.trades_cache_time = now
            return trades
        except:
            return []
    
    # ========== Auto Cleanup ==========
    def cleanup_old_data(self):
        """حذف البيانات القديمة تلقائياً"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False
