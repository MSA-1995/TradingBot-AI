"""
التخزين السحابي - Supabase Database
"""
import os
import requests
from datetime import datetime
try:
    from supabase import create_client, Client
except:
    pass

class DatabaseStorage:
    def __init__(self):
        self._ensure_ssl_cert()
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            raise Exception("DATABASE_URL not found!")
        
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import json as json_module
        from urllib.parse import urlparse, unquote
        
        # استخراج المعلومات من URL
        parsed = urlparse(database_url)
        
        self._db_params = {
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path[1:],
                'user': parsed.username,
                'password': unquote(parsed.password),
                'sslmode': 'verify-full',
                'sslrootcert': 'prod-supabase.cer',
                'connect_timeout': 10
            }
        self.conn = psycopg2.connect(**self._db_params)
        self.json = json_module
        self.RealDictCursor = RealDictCursor
        self._psycopg2 = psycopg2
        
        if not self._create_tables():
            raise Exception("Failed to create database tables after multiple attempts.")

    def _get_conn(self):
        """إرجاع connection صالح - يعيد الاتصال إذا انقطع"""
        try:
            # اختبار الاتصال عبر استعلام بسيط
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except (self._psycopg2.OperationalError, self._psycopg2.InterfaceError):
            # إذا فشل الاختبار، أعد الاتصال
            try:
                print("🔄 DB connection lost. Reconnecting...")
                self.conn = self._psycopg2.connect(**self._db_params)
            except Exception as e:
                print(f"❌ DB reconnect error: {e}")
        return self.conn

    # ========== General Settings ==========
    def save_setting(self, key, value):
        """Saves a key-value setting to the bot_settings table."""
        sql = """
            INSERT INTO bot_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(sql, (key, str(value)))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB Error saving setting {key}: {e}")
            return False

    def load_setting(self, key):
        """Loads a value from the bot_settings table."""
        sql = "SELECT value FROM bot_settings WHERE key = %s;"
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(sql, (key,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except Exception as e:
            print(f"❌ DB Error loading setting {key}: {e}")
            return None

    def _ensure_ssl_cert(self):
        """Downloads the Supabase SSL certificate if it doesn't exist."""
        cert_file = 'prod-supabase.cer'
        if not os.path.exists(cert_file):
            print("📜 Downloading Supabase SSL certificate...")
            try:
                url = 'https://supabase.com/docs/guides/database/connecting-to-postgres#ssl-connection'
                # This is a placeholder URL. In a real scenario, you'd get the correct cert URL.
                # For this example, we'll create a dummy file as the actual download is complex.
                # In a real implementation, you would fetch the actual certificate content.
                response = requests.get('https://raw.githubusercontent.com/supabase/cli/main/apps/studio/certs/prod-ca-2024.cer')
                response.raise_for_status()
                with open(cert_file, 'wb') as f:
                    f.write(response.content)
                print("✅ SSL certificate downloaded.")
            except Exception as e:
                print(f"❌ Failed to download SSL certificate: {e}")
                # Depending on the desired behavior, you might want to raise an exception here
                # or allow the connection to proceed without the certificate.
                pass
    
    def _create_tables(self):
        """إنشاء الجداول إذا لم تكن موجودة (مع إعادة محاولة). Returns True on success, False on failure."""
        for attempt in range(3):
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                
                # ... (rest of the table creation queries remain the same)
                # Positions table
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

                # General settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bot_settings (
                        key VARCHAR(255) PRIMARY KEY,
                        value TEXT
                    );
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
                
                # Consultant votes table (نتائج التصويت)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS consultant_votes (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20),
                        consultant_name VARCHAR(50),
                        vote_type VARCHAR(20),
                        vote_value FLOAT,
                        actual_result FLOAT,
                        is_correct BOOLEAN,
                        profit_percent FLOAT,
                        timestamp TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                conn.commit()
                cursor.close()
                return True # Success, exit the loop

            except Exception as e:
                print(f"⚠️ Table creation error (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    import time
                    time.sleep(5) # Wait 5 seconds before retrying
                else:
                    try:
                        self._get_conn().rollback()
                    except Exception as rb_e:
                        print(f"⚠️ Error during rollback: {rb_e}")
        
        return False # Failure after all attempts
    
    # ========== Trades ==========
    def save_trade(self, trade_data):
        try:
            def convert_value(val):
                if val is None:
                    return None
                if hasattr(val, 'item'):
                    return val.item()
                return val
            
            conn = self._get_conn()
            cursor = conn.cursor()
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
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save trade error: {e}")
            self._get_conn().rollback()
            return False
    
    def load_trades(self, limit=None):
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
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
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learned_patterns (pattern_type, data, success_rate)
                VALUES (%s, %s, %s)
            """, (
                pattern_data.get('type'),
                self.json.dumps(pattern_data),
                pattern_data.get('success_rate', 0.0)
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save pattern error: {e}")
            self._get_conn().rollback()
            return False
    
    def load_patterns(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM learned_patterns ORDER BY last_updated DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except:
            return []
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        for attempt in range(3):
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ai_decisions (symbol, decision, confidence, data)
                    VALUES (%s, %s, %s, %s)
                """, (
                    decision_data.get('symbol'),
                    decision_data.get('decision'),
                    decision_data.get('confidence'),
                    self.json.dumps(decision_data)
                ))
                conn.commit()
                cursor.close()
                return True
            except Exception as e:
                print(f"❌ DB save decision error (attempt {attempt+1}/3): {e}")
                try:
                    self._get_conn().rollback()
                except:
                    pass
                
                if attempt < 2:
                    import time
                    time.sleep(1)
                else:
                    return False
        
        return False
    
    def load_ai_decisions(self, limit=10):
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
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
    
    # ========== Consultant Votes ==========
    def save_consultant_vote(self, vote_data):
        """حفظ نتيجة تصويت مستشار"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO consultant_votes 
                (symbol, consultant_name, vote_type, vote_value, actual_result, is_correct, profit_percent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                vote_data.get('symbol'),
                vote_data.get('consultant_name'),
                vote_data.get('vote_type'),
                vote_data.get('vote_value'),
                vote_data.get('actual_result'),
                vote_data.get('is_correct'),
                vote_data.get('profit_percent')
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save vote error: {e}")
            self._get_conn().rollback()
            return False
    
    def load_consultant_votes(self, consultant_name=None, limit=1000):
        """قراءة نتائج التصويت"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            if consultant_name:
                cursor.execute("""
                    SELECT * FROM consultant_votes 
                    WHERE consultant_name = %s 
                    ORDER BY timestamp DESC LIMIT %s
                """, (consultant_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM consultant_votes 
                    ORDER BY timestamp DESC LIMIT %s
                """, (limit,))
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except:
            return []

    
    # ========== Auto Cleanup ==========
    def cleanup_old_data(self):
        """حذف البيانات القديمة تلقائياً"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # بيانات التدريب: 6 أشهر (مهمة للـ Deep Learning Trainer)
            cursor.execute("DELETE FROM trades_history WHERE timestamp < NOW() - INTERVAL '180 days'")
            trades_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM learned_patterns WHERE last_updated < NOW() - INTERVAL '180 days'")
            patterns_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM trap_memory WHERE timestamp < NOW() - INTERVAL '180 days'")
            traps_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM consultant_votes WHERE timestamp < NOW() - INTERVAL '180 days'")
            votes_deleted = cursor.rowcount
            
            # ai_decisions: 30 يوم فقط (للمراقبة - لا يستخدمها الـ Trainer)
            cursor.execute("DELETE FROM ai_decisions WHERE timestamp < NOW() - INTERVAL '30 days'")
            decisions_deleted = cursor.rowcount
            
            conn.commit()
            cursor.close()
            
            total_deleted = trades_deleted + patterns_deleted + decisions_deleted + traps_deleted + votes_deleted
            if total_deleted > 0:
                print(f"🗑️ Cleaned: {trades_deleted} trades (6m), {patterns_deleted} patterns (6m), {decisions_deleted} AI decisions (30d), {traps_deleted} traps (6m), {votes_deleted} votes (6m)")
            
            return True
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
            self._get_conn().rollback()
            return False
    
    # ========== Traps ==========
    def save_trap(self, trap_data):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trap_memory (symbol, data)
                VALUES (%s, %s)
            """, (
                trap_data.get('symbol'),
                self.json.dumps(trap_data)
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save trap error: {e}")
            self._get_conn().rollback()
            return False
    
    def load_traps(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM trap_memory ORDER BY timestamp DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except:
            return []
    
    
    # ========== Positions ==========
    def save_positions(self, positions):
        try:
            conn = self._get_conn()
            conn.rollback()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM positions")
            
            for symbol, config in positions.items():
                if config.get('position'):
                    pos = config['position']
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
            
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save positions error: {e}")
            self._get_conn().rollback()
            return False
    
    def load_positions(self):
        try:
            conn = self._get_conn()
            conn.rollback()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
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
            self._get_conn().rollback()
            return {}
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        return True
    
    def load_performance(self, days=7):
        return []
