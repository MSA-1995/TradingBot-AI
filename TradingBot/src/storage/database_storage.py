"""
التخزين السحابي - Supabase Database
"""
import os
from datetime import datetime
try:
    from supabase import create_client, Client
except:
    pass

class DatabaseStorage:
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        
        if not url or not key:
            raise Exception("Supabase credentials not found!")
        
        self.supabase: Client = create_client(url, key)
        print("✅ Connected to Supabase")
    
    # ========== Trades ==========
    def save_trade(self, trade_data):
        try:
            trade_data['timestamp'] = datetime.now().isoformat()
            self.supabase.table('trades_history').insert(trade_data).execute()
            return True
        except Exception as e:
            print(f"❌ DB save trade error: {e}")
            return False
    
    def load_trades(self, limit=None):
        try:
            query = self.supabase.table('trades_history').select('*').order('timestamp', desc=True)
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data
        except:
            return []
    
    # ========== Patterns ==========
    def save_pattern(self, pattern_data):
        try:
            pattern_data['last_updated'] = datetime.now().isoformat()
            self.supabase.table('learned_patterns').insert(pattern_data).execute()
            return True
        except Exception as e:
            print(f"❌ DB save pattern error: {e}")
            return False
    
    def load_patterns(self):
        try:
            result = self.supabase.table('learned_patterns').select('*').execute()
            return result.data
        except:
            return []
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        try:
            decision_data['timestamp'] = datetime.now().isoformat()
            self.supabase.table('ai_decisions').insert(decision_data).execute()
            return True
        except Exception as e:
            print(f"❌ DB save decision error: {e}")
            return False
    
    def load_ai_decisions(self, limit=10):
        try:
            result = self.supabase.table('ai_decisions').select('*').order('timestamp', desc=True).limit(limit).execute()
            return result.data
        except:
            return []
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        try:
            metrics_data['date'] = datetime.now().strftime('%Y-%m-%d')
            self.supabase.table('performance_metrics').insert(metrics_data).execute()
            return True
        except Exception as e:
            print(f"❌ DB save performance error: {e}")
            return False
    
    def load_performance(self, days=7):
        try:
            result = self.supabase.table('performance_metrics').select('*').order('date', desc=True).limit(days).execute()
            return result.data
        except:
            return []
    
    # ========== Traps ==========
    def save_trap(self, trap_data):
        try:
            trap_data['timestamp'] = datetime.now().isoformat()
            self.supabase.table('trap_memory').insert(trap_data).execute()
            return True
        except Exception as e:
            print(f"❌ DB save trap error: {e}")
            return False
    
    def load_traps(self):
        try:
            result = self.supabase.table('trap_memory').select('*').execute()
            return result.data
        except:
            return []
    
    # ========== Positions (متوافق مع النظام الحالي) ==========
    def save_positions(self, positions):
        try:
            data = {}
            for symbol, config in positions.items():
                if config['position']:
                    data[symbol] = config['position']
            
            # نحفظ في جدول positions
            self.supabase.table('positions').upsert({
                'id': 1,
                'data': data,
                'updated_at': datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            print(f"❌ DB save positions error: {e}")
            return False
    
    def load_positions(self):
        try:
            result = self.supabase.table('positions').select('data').eq('id', 1).execute()
            if result.data:
                return result.data[0]['data']
            return {}
        except:
            return {}
