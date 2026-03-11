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
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            raise Exception("DATABASE_URL not found!")
        
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import json as json_module
        
        # فك تشفير URL بطريقة أقوى
        database_url = database_url.replace('%23', '#')
        database_url = database_url.replace('%25', '%')
        database_url = database_url.replace('%21', '!')
        database_url = database_url.replace('%2C', ',')
        database_url = database_url.replace('%2F', '/')
        
        self.conn = psycopg2.connect(database_url)
        self.json = json_module
        self.RealDictCursor = RealDictCursor
        self._create_tables()
        print("✅ Connected to PostgreSQL (Supabase)")
    
    def _create_tables(self):
        """إنشاء الجداول إذا لم تكن موجودة"""
        try:
            cursor = self.conn.cursor()
            
            # Positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Trades history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades_history (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20),
                    action VARCHAR(10),
                    profit_percent FLOAT,
                    sell_reason TEXT,
                    tp_target FLOAT,
                    sl_target FLOAT,
                    hours_held FLOAT,
                    data JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Learned patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_type VARCHAR(20),
                    data JSONB,
                    success_rate FLOAT,
                    last_updated TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # AI decisions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20),
                    decision VARCHAR(10),
                    confidence INTEGER,
                    data JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Trap memory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trap_memory (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20),
                    data JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            
            self.conn.commit()
            cursor.close()
        except Exception as e:
            print(f"⚠️ Table creation error: {e}")
            self.conn.rollback()
    
    # ========== Trades ==========
    def save_trade(self, trade_data):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trades_history (symbol, action, profit_percent, sell_reason, tp_target, sl_target, hours_held, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                trade_data.get('symbol'),
                trade_data.get('action'),
                trade_data.get('profit_percent'),
                trade_data.get('sell_reason'),
                trade_data.get('tp_target'),
                trade_data.get('sl_target'),
                trade_data.get('hours_held'),
                self.json.dumps(trade_data)
            ))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save trade error: {e}")
            self.conn.rollback()
            return False
    
    def load_trades(self, limit=None):
        try:
            cursor = self.conn.cursor(cursor_factory=self.RealDictCursor)
            if limit:
                cursor.execute("SELECT * FROM trades_history ORDER BY timestamp DESC LIMIT %s", (limit,))
            else:
                cursor.execute("SELECT * FROM trades_history ORDER BY timestamp DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except:
            return []
    
    # ========== Patterns ==========
    def save_pattern(self, pattern_data):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO learned_patterns (pattern_type, data, success_rate)
                VALUES (%s, %s, %s)
            """, (
                pattern_data.get('type'),
                self.json.dumps(pattern_data),
                pattern_data.get('success_rate', 0.0)
            ))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save pattern error: {e}")
            self.conn.rollback()
            return False
    
    def load_patterns(self):
        try:
            cursor = self.conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM learned_patterns ORDER BY last_updated DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except:
            return []
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO ai_decisions (symbol, decision, confidence, data)
                VALUES (%s, %s, %s, %s)
            """, (
                decision_data.get('symbol'),
                decision_data.get('decision'),
                decision_data.get('confidence'),
                self.json.dumps(decision_data)
            ))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save decision error: {e}")
            self.conn.rollback()
            return False
    
    def load_ai_decisions(self, limit=10):
        try:
            cursor = self.conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM ai_decisions ORDER BY timestamp DESC LIMIT %s", (limit,))
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
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
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trap_memory (symbol, data)
                VALUES (%s, %s)
            """, (
                trap_data.get('symbol'),
                self.json.dumps(trap_data)
            ))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save trap error: {e}")
            self.conn.rollback()
            return False
    
    def load_traps(self):
        try:
            cursor = self.conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM trap_memory ORDER BY timestamp DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
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

    
    # ========== Positions ==========
    def save_positions(self, positions):
        try:
            data = {}
            for symbol, config in positions.items():
                if config.get('position'):
                    data[symbol] = config['position']
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO positions (id, data, updated_at)
                VALUES (1, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET data = %s, updated_at = NOW()
            """, (self.json.dumps(data), self.json.dumps(data)))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save positions error: {e}")
            self.conn.rollback()
            return False
    
    def load_positions(self):
        try:
            cursor = self.conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT data FROM positions WHERE id = 1")
            result = cursor.fetchone()
            cursor.close()
            if result:
                return result['data']
            return {}
        except:
            return {}
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        return True
    
    def load_performance(self, days=7):
        return []
