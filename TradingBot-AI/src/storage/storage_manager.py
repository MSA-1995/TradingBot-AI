"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً
"""
import os
import json
from datetime import datetime

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
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
    
    # ========== Positions (الحالي) ==========
    def save_positions(self, positions):
        """حفظ المراكز (متوافق مع النظام الحالي)"""
        return self.storage.save_positions(positions)
    
    def load_positions(self):
        """تحميل المراكز (متوافق مع النظام الحالي)"""
        return self.storage.load_positions()
    
    # ========== Advanced Queries ==========
    def get_all_trades(self):
        """جلب جميع الصفقات (للتحليل)"""
        try:
            return self.storage.load_trades(limit=1000)
        except:
            return []
    
    def get_symbol_trades(self, symbol, limit=20):
        """جلب صفقات عملة محددة"""
        try:
            all_trades = self.storage.load_trades(limit=100)
            symbol_trades = [t for t in all_trades if t.get('symbol') == symbol]
            return symbol_trades[:limit]
        except:
            return []
    
    # ========== Auto Cleanup ==========
    def cleanup_old_data(self):
        """حذف البيانات القديمة تلقائياً"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False
