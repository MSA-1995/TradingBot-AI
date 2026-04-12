"""
التخزين الهجين - Database + ملفات محلية (الاثنين معاً)
"""
from .local_storage import LocalStorage
from .database_storage import DatabaseStorage

class HybridStorage:
    def __init__(self, local_path='../data/'):
        self.local = LocalStorage(local_path)
        try:
            self.database = DatabaseStorage()
            self.db_available = True
            print("💾 Hybrid Mode: Database + Local Files")
        except:
            self.database = None
            self.db_available = False
            print("⚠️ Database unavailable, using Local only")
    
    def _save_both(self, db_method, local_method, data):
        """حفظ في الاثنين"""
        local_success = local_method(data)
        db_success = False
        
        if self.db_available:
            try:
                db_success = db_method(data)
            except:
                self.db_available = False
                print("⚠️ Database connection lost, using Local only")
        
        return local_success or db_success
    
    def _load_prefer_db(self, db_method, local_method, *args):
        """تحميل من Database أولاً، ثم Local"""
        if self.db_available:
            try:
                data = db_method(*args)
                if data:
                    return data
            except:
                self.db_available = False
        
        return local_method(*args)
    
    # ========== Trades ==========
    def save_trade(self, trade_data):
        return self._save_both(
            self.database.save_trade if self.db_available else lambda x: False,
            self.local.save_trade,
            trade_data
        )
    
    def load_trades(self, limit=None):
        return self._load_prefer_db(
            self.database.load_trades if self.db_available else lambda x: [],
            self.local.load_trades,
            limit
        )
    
    # ========== Patterns ==========
    def save_pattern(self, pattern_data):
        return self._save_both(
            self.database.save_pattern if self.db_available else lambda x: False,
            self.local.save_pattern,
            pattern_data
        )
    
    def load_patterns(self):
        return self._load_prefer_db(
            self.database.load_patterns if self.db_available else lambda: [],
            self.local.load_patterns
        )
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        return self._save_both(
            self.database.save_ai_decision if self.db_available else lambda x: False,
            self.local.save_ai_decision,
            decision_data
        )
    
    def load_ai_decisions(self, limit=10):
        return self._load_prefer_db(
            self.database.load_ai_decisions if self.db_available else lambda x: [],
            self.local.load_ai_decisions,
            limit
        )
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        return self._save_both(
            self.database.save_performance if self.db_available else lambda x: False,
            self.local.save_performance,
            metrics_data
        )
    
    def load_performance(self, days=7):
        return self._load_prefer_db(
            self.database.load_performance if self.db_available else lambda x: [],
            self.local.load_performance,
            days
        )
    
    # ========== Traps ==========
    def save_trap(self, trap_data):
        return self._save_both(
            self.database.save_trap if self.db_available else lambda x: False,
            self.local.save_trap,
            trap_data
        )
    
    def load_traps(self):
        return self._load_prefer_db(
            self.database.load_traps if self.db_available else lambda: [],
            self.local.load_traps
        )
    
    # ========== Positions ==========
    def save_positions(self, positions):
        return self._save_both(
            self.database.save_positions if self.db_available else lambda x: False,
            self.local.save_positions,
            positions
        )
    
    def load_positions(self):
        return self._load_prefer_db(
            self.database.load_positions if self.db_available else lambda: {},
            self.local.load_positions
        )
