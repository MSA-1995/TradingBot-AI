"""
نظام التخزين الذكي - يحفظ في Database و ملفات محلية تلقائياً
"""
import os
import json
from datetime import datetime

class StorageManager:
    def __init__(self):
        self.mode = self.detect_environment()
        
        # ====== SMART CACHE (تقليل Egress من Supabase) ======
        # كاش للصفقات - يُستخدم بكثرة من RiskManager في كل دورة
        self.trades_cache = None
        self.trades_cache_time = None
        self.cache_duration = 120  # دقيقتان (كان 60 ثانية)

        # كاش للفخاخ - تتغير نادراً
        self._traps_cache = None
        self._traps_cache_time = None
        self._traps_cache_ttl = 300  # 5 دقائق

        # كاش للأنماط - تتغير نادراً جداً
        self._patterns_cache = None
        self._patterns_cache_time = None
        self._patterns_cache_ttl = 600  # 10 دقائق

        # كاش لقرارات AI
        self._ai_decisions_cache = None
        self._ai_decisions_cache_time = None
        self._ai_decisions_cache_ttl = 60  # دقيقة
        # ====================================================
        
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
        self._patterns_cache = None  # invalidate cache on write
        return self.storage.save_pattern(pattern_data)
    
    def load_patterns(self):
        """تحميل الأنماط"""
        return self.storage.load_patterns()

    def load_all_patterns(self):
        """تحميل كل الأنماط - مع cache لمدة 10 دقائق لتقليل Egress"""
        now = datetime.now()
        if self._patterns_cache is not None and self._patterns_cache_time:
            if (now - self._patterns_cache_time).total_seconds() < self._patterns_cache_ttl:
                return self._patterns_cache
        self._patterns_cache = self.storage.load_all_patterns()
        self._patterns_cache_time = now
        return self._patterns_cache
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        """حفظ قرار AI"""
        self._ai_decisions_cache = None  # invalidate cache on write
        return self.storage.save_ai_decision(decision_data)
    
    def load_ai_decisions(self, limit=10):
        """تحميل قرارات AI - مع cache لمدة دقيقة"""
        now = datetime.now()
        if self._ai_decisions_cache is not None and self._ai_decisions_cache_time:
            if (now - self._ai_decisions_cache_time).total_seconds() < self._ai_decisions_cache_ttl:
                return self._ai_decisions_cache[-limit:]
        self._ai_decisions_cache = self.storage.load_ai_decisions(limit=100)
        self._ai_decisions_cache_time = now
        return self._ai_decisions_cache[-limit:]
    
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
        self._traps_cache = None  # invalidate cache on write
        return self.storage.save_trap(trap_data)
    
    def load_traps(self):
        """تحميل الفخاخ - مع cache لمدة 5 دقائق لتقليل Egress"""
        now = datetime.now()
        if self._traps_cache is not None and self._traps_cache_time:
            if (now - self._traps_cache_time).total_seconds() < self._traps_cache_ttl:
                return self._traps_cache
        self._traps_cache = self.storage.load_traps()
        self._traps_cache_time = now
        return self._traps_cache
    
    # ========== Consultant Votes ==========
    def save_consultant_vote(self, vote_data):
        """حفظ نتيجة تصويت مستشار"""
        return self.storage.save_consultant_vote(vote_data)
    
    def load_consultant_votes(self, consultant_name=None, limit=1000):
        """قراءة نتائج التصويت"""
        return self.storage.load_consultant_votes(consultant_name, limit)
    
    # ========== Rescue (Crazy) Data ==========
    def save_rescue_event(self, rescue_data):
        """حفظ بيانات الإنقاذ لتدريب الخبل"""
        if hasattr(self.storage, 'save_rescue_event'):
            return self.storage.save_rescue_event(rescue_data)
        return False
    
    # ========== Positions (الحالي) ==========
    def save_positions(self, positions):
        """حفظ المراكز (متوافق مع النظام الحالي)"""
        if self.mode == 'cloud':
            # تحويل dict إلى list of dicts
            if isinstance(positions, dict):
                positions_list = []
                for symbol, pos in positions.items():
                    if isinstance(pos, dict) and pos:
                        entry = {'symbol': symbol}
                        entry.update(pos)
                        positions_list.append(entry)
                return self.storage.save_positions_batch(positions_list)
            elif isinstance(positions, list):
                return self.storage.save_positions_batch(positions)
        else:
            return self.storage.save_positions(positions)
    
    def load_positions(self):
        """تحميل المراكز (متوافق مع النظام الحالي)"""
        return self.storage.load_positions()
    
    def delete_position(self, symbol):
        """Deletes a position from the storage."""
        return self.storage.delete_position(symbol)
    
    # ========== Advanced Queries ==========
    def get_all_trades(self):
        """
        جلب جميع الصفقات (للتحليل) - مع cache 120 ثانية.
        ⚠️ هذه الدالة تُستدعى من RiskManager في كل دورة تحليل.
        الـ cache هنا هو الحل الرئيسي لتقليل Egress من Supabase.
        """
        try:
            now = datetime.now()
            if self.trades_cache and self.trades_cache_time:
                elapsed = (now - self.trades_cache_time).total_seconds()
                if elapsed < self.cache_duration:  # 120 ثانية
                    return self.trades_cache
            
            trades = self.storage.load_trades(limit=1000)
            self.trades_cache = trades
            self.trades_cache_time = now
            return trades
        except:
            return []
    
    # ========== Learning Data ==========
    def save_learning_data(self, learning_type, data):
        """حفظ بيانات التعلم (الملك والمستشارين)"""
        if hasattr(self.storage, 'save_learning_data'):
            return self.storage.save_learning_data(learning_type, data)
        return False
    
    def load_learning_data(self, learning_type):
        """تحميل بيانات التعلم"""
        if hasattr(self.storage, 'load_learning_data'):
            return self.storage.load_learning_data(learning_type)
        return {}
    
    # ========== Auto Cleanup ==========
    def cleanup_old_data(self):
        """حذف البيانات القديمة تلقائياً"""
        if hasattr(self.storage, 'cleanup_old_data'):
            return self.storage.cleanup_old_data()
        return False

    # ========== Model Storage (DB Only) ==========
    def save_model_to_db(self, model_name, model_data):
        """حفظ نموذج (مثل Meta-Learner) في قاعدة البيانات"""
        if self.mode == 'cloud' and hasattr(self.storage, 'save_model'):
            return self.storage.save_model(model_name, model_data)
        print("⚠️ Model saving is only supported in cloud mode.")
        return False

    def load_model(self, model_name):
        """تحميل نموذج (مثل Meta-Learner) من قاعدة البيانات أو ملف محلي"""
        return self.storage.load_model(model_name)
    
    def get_recent_trades_by_symbol(self, symbol, limit=10):
        """جلب آخر صفقات لعملة محددة (للقائمة السوداء)"""
        if hasattr(self.storage, 'get_recent_trades_by_symbol'):
            return self.storage.get_recent_trades_by_symbol(symbol, limit)
        # Fallback: filter from all trades
        all_trades = self.get_all_trades()
        symbol_trades = [t for t in all_trades if t.get('symbol') == symbol]
        return symbol_trades[-limit:] if symbol_trades else []
