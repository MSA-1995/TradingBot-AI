"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً
"""
import os
import json
from datetime import datetime

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        self.local_path = '../data/'
        
        if self.mode == 'cloud':
            from .database_storage import DatabaseStorage
            self.storage = DatabaseStorage()
        elif self.mode == 'local':
            from .local_storage import LocalStorage
            self.storage = LocalStorage(self.local_path)
        else:  # hybrid
            from .hybrid_storage import HybridStorage
            self.storage = HybridStorage(self.local_path)
        
        print(f"💾 Storage Mode: {self.mode.upper()}")
    
    def detect_environment(self):
        """يكتشف البيئة تلقائياً"""
        supabase_url = os.getenv('SUPABASE_URL')
        storage_mode = os.getenv('STORAGE_MODE', 'auto')
        
        if storage_mode == 'local':
            return 'local'
        elif storage_mode == 'cloud' and supabase_url:
            return 'cloud'
        elif storage_mode == 'hybrid' and supabase_url:
            return 'hybrid'
        elif supabase_url:
            return 'hybrid'  # الافتراضي: الاثنين معاً
        else:
            return 'local'
    
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
