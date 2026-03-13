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
        from urllib.parse import urlparse, unquote
        
        # استخراج المعلومات من URL
        parsed = urlparse(database_url)
        
        self.conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password)
        )
        self.json = json_module
        self.RealDictCursor = RealDictCursor
        self._create_tables()
        # تهيئة صامتة لقاعدة البيانات
    
    def _create_tables(self):
        """إنشاء الجداول إذا لم تكن موجودة"""
        try:
            cursor = self.conn.cursor()
            
            # Positions table (نفس البوت القديم)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol VARCHAR(20) PRIMARY KEY,
                    buy_price FLOAT NOT NULL,
                    amount FLOAT NOT NULL,
                    highest_price FLOAT NOT NULL,
                    tp_level_1 BOOLEAN DEFAULT FALSE,
                    tp_level_2 BOOLEAN DEFAULT FALSE,
                    buy_time TIMESTAMP NOT NULL,
                    invested FLOAT NOT NULL,
                    data JSONB
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
            # تهيئة صامتة للجداول
        except Exception as e:
            print(f"⚠️ Table creation error: {e}")
            self.conn.rollback()
    
    # ========== Trades ==========
    def save_trade(self, trade_data):
        try:
            # تحويل numpy types إلى Python types
            def convert_value(val):
                if val is None:
                    return None
                # تحويل numpy types
                if hasattr(val, 'item'):
                    return val.item()
                return val
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trades_history (symbol, action, profit_percent, sell_reason, tp_target, sl_target, hours_held, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                trade_data.get('symbol'),
                trade_data.get('action'),
                convert_value(trade_data.get('profit_percent')),
                trade_data.get('sell_reason'),
                convert_value(trade_data.get('tp_target')),
                convert_value(trade_data.get('sl_target')),
                convert_value(trade_data.get('hours_held')),
                self.json.dumps(trade_data, default=str)
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
    
    # ========== Auto Cleanup ==========
    def cleanup_old_data(self):
        """حذف البيانات القديمة تلقائياً"""
        try:
            cursor = self.conn.cursor()
            
            # حذف trades_history الأقدم من 30 يوم
            cursor.execute("""
                DELETE FROM trades_history 
                WHERE timestamp < NOW() - INTERVAL '30 days'
            """)
            trades_deleted = cursor.rowcount
            
            # حذف learned_patterns الأقدم من 30 يوم
            cursor.execute("""
                DELETE FROM learned_patterns 
                WHERE last_updated < NOW() - INTERVAL '30 days'
            """)
            patterns_deleted = cursor.rowcount
            
            # حذف ai_decisions الأقدم من 90 يوم (للتعلم)
            cursor.execute("""
                DELETE FROM ai_decisions 
                WHERE timestamp < NOW() - INTERVAL '90 days'
            """)
            decisions_deleted = cursor.rowcount
            
            # حذف trap_memory الأقدم من 90 يوم
            cursor.execute("""
                DELETE FROM trap_memory 
                WHERE timestamp < NOW() - INTERVAL '90 days'
            """)
            traps_deleted = cursor.rowcount
            
            self.conn.commit()
            cursor.close()
            
            total_deleted = trades_deleted + patterns_deleted + decisions_deleted + traps_deleted
            if total_deleted > 0:
                print(f"🗑️ Cleaned: {trades_deleted} trades, {patterns_deleted} patterns, {decisions_deleted} AI decisions, {traps_deleted} traps")
            
            return True
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
            self.conn.rollback()
            return False
    
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
    
    
    # ========== Positions ==========
    def save_positions(self, positions):
        try:
            self.conn.rollback()
            cursor = self.conn.cursor()
            
            # حذف المراكز القديمة
            cursor.execute("DELETE FROM positions")
            
            # إضافة المراكز الجديدة
            for symbol, config in positions.items():
                if config.get('position'):
                    pos = config['position']
                    # حساب invested من buy_price * amount
                    invested = float(pos['buy_price']) * float(pos['amount'])
                    
                    cursor.execute("""
                        INSERT INTO positions 
                        (symbol, buy_price, amount, highest_price, tp_level_1, tp_level_2, buy_time, invested, data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        symbol,
                        float(pos['buy_price']),
                        float(pos['amount']),
                        float(pos['highest_price']),
                        pos.get('tp_level_1', False),
                        pos.get('tp_level_2', False),
                        pos['buy_time'],
                        invested,
                        self.json.dumps(pos)
                    ))
            
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save positions error: {e}")
            self.conn.rollback()
            return False
    
    def load_positions(self):
        try:
            self.conn.rollback()
            cursor = self.conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM positions")
            rows = cursor.fetchall()
            cursor.close()
            
            data = {}
            for row in rows:
                data[row['symbol']] = {
                    'buy_price': row['buy_price'],
                    'amount': row['amount'],
                    'highest_price': row['highest_price'],
                    'tp_level_1': row['tp_level_1'],
                    'tp_level_2': row['tp_level_2'],
                    'buy_time': row['buy_time'].isoformat(),
                    'invested': row['invested']
                }
            
            return data
        except Exception as e:
            print(f"❌ DB load positions error: {e}")
            self.conn.rollback()
            return {}
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        return True
    
    def load_performance(self, days=7):
        return []
