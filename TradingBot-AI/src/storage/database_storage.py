"""
التخزين السحابي - Supabase Database
"""
import os
from datetime import datetime

# --- DATABASE CONNECTION POOL ---
# To make the bot stable, we use a connection pool.
# This avoids connection drops and manages reconnections automatically.
from psycopg2.pool import ThreadedConnectionPool
# --- END --- 

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
        
        self._db_params = {
                'host': parsed.hostname,
                'port': 5432, # --- FINAL FIX: Force Direct Connection (Bypass PgBouncer) ---
                'database': parsed.path[1:],
                'user': parsed.username,
                'password': unquote(parsed.password),
                'sslmode': 'require',
                'connect_timeout': 15, # Increased timeout for direct connection
                # --- TCP Keepalives (Good practice, but direct port is the real fix) ---
                'keepalives': 1,
                'keepalives_idle': 60,
                'keepalives_interval': 30,
                'keepalives_count': 10
            }
        
        # --- Initialize Connection Pool ---
        # minconn=1, maxconn=5
        self.pool = ThreadedConnectionPool(1, 5, **self._db_params)
        # --- END ---

        self.json = json_module
        self.RealDictCursor = RealDictCursor
        self._psycopg2 = psycopg2
        
        if not self._create_tables():
            raise Exception("Failed to create database tables after multiple attempts.")
        self._check_schema_updates()

    def _get_conn(self):
        """Get a healthy connection from the pool, implementing a manual pre-ping."""
        for attempt in range(3): # Try up to 3 times to get a healthy connection
            conn = self.pool.getconn()
            try:
                # --- Pre-ping: Test the connection before returning it ---
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                # --- Connection is healthy, return it ---
                return conn
            except self._psycopg2.Error as e:
                print(f"⚠️ Pre-ping failed (attempt {attempt+1}): {e}. Discarding connection.")
                # --- Connection is dead, discard it and get a new one ---
                self.pool.putconn(conn, close=True)
                if attempt == 2:
                    print("❌ Failed to get a healthy DB connection after multiple attempts.")
                    raise # Re-raise the last exception

    def _put_conn(self, conn):
        """Return a connection to the pool."""
        if conn and not conn.closed:
            self.pool.putconn(conn)
        else:
            print("ℹ️ Attempted to return a closed connection to the pool. It was ignored.")

    # ========== General Settings ==========
    def save_setting(self, key, value):
        """Saves a key-value setting to the bot_settings table."""
        sql = """
            INSERT INTO bot_settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(sql, (key, str(value)))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB Error saving setting {key}: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)

    def load_setting(self, key):
        """Loads a value from the bot_settings table."""
        sql = "SELECT value FROM bot_settings WHERE key = %s;"
        conn = None
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
        finally:
            if conn: self._put_conn(conn)

    def _create_tables(self):
        """إنشاء الجداول إذا لم تكن موجودة (مع إعادة محاولة). Returns True on success, False on failure."""
        # تجميع كل أوامر إنشاء الجداول في نص واحد لتنفيذها كمعاملة واحدة
        create_sql = """
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
        );
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
        );
        CREATE TABLE IF NOT EXISTS bot_settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS learned_patterns (
            id SERIAL PRIMARY KEY,
            pattern_type VARCHAR(20),
            data JSONB,
            success_rate FLOAT,
            last_updated TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS ai_decisions (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20),
            decision VARCHAR(10),
            confidence INTEGER,
            data JSONB,
            timestamp TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS trap_memory (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20),
            data JSONB,
            timestamp TIMESTAMP DEFAULT NOW()
        );
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
        );
        """
        for attempt in range(3):
            conn = None
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute(create_sql)
                conn.commit()
                cursor.close()
                self._put_conn(conn) # --- إرجاع الاتصال السليم إلى المجمع
                print("✅ Database tables created/verified successfully.")
                return True # --- نجاح، خروج

            except self._psycopg2.Error as e: # --- التعامل مع أخطاء قاعدة البيانات فقط
                print(f"⚠️ Table creation DB error (attempt {attempt + 1}/3): {e}")
                if conn:
                    # --- الخطوة الأهم: تخلص من الاتصال الفاشل ولا تعيده للمجمع
                    self.pool.putconn(conn, close=True)
                    print("🔥 Discarded faulty DB connection. Will retry with a new one.")

                if attempt < 2:
                    import time
                    time.sleep(5) # --- انتظار قبل المحاولة التالية
                else:
                    print("❌ Final attempt to create tables failed.")
            except Exception as e:
                print(f"⚠️ An unexpected error occurred during table creation: {e}")
                if conn: # تخلص من الاتصال عند حدوث أي خطأ غير متوقع أيضًا
                    self.pool.putconn(conn, close=True)
                # لا تعيد المحاولة في الأخطاء العامة غير المتوقعة
                break

        return False # فشل بعد كل المحاولات
    
    def _check_schema_updates(self):
        """التحقق من تحديثات المخطط وإصلاحها تلقائياً (Self-Healing)"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # --- FIX: Increase statement timeout for this session to prevent DDL timeouts ---
            cursor.execute("SET statement_timeout = '60s';")
            
            # --- ADD 'invested' to 'positions' ---
            try:
                cursor.execute("ALTER TABLE positions ADD COLUMN invested FLOAT NOT NULL DEFAULT 0;")
                conn.commit()
                print("🔧 Schema Update: Added 'invested' column to 'positions' table.")
            except self._psycopg2.errors.DuplicateColumn:
                conn.rollback() # Ignore if column already exists
            except Exception as e:
                print(f"⚠️ Schema update error (invested): {e}")
                conn.rollback()

            # --- ADD 'dl_models_v2' table ---
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS dl_models_v2 (
                        model_name VARCHAR(50) PRIMARY KEY,
                        model_data BYTEA NOT NULL,
                        trained_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                print("🔧 Schema Update: Ensured 'dl_models_v2' table exists.")
            except Exception as e:
                print(f"⚠️ Schema update error (dl_models_v2): {e}")
                conn.rollback()
            
            cursor.close()
        except Exception as e:
            print(f"⚠️ Schema update check failed: {e}")
            if conn: 
                try: conn.rollback()
                except: pass
        finally:
            if conn: self._put_conn(conn)

    # ========== Trades ==========
    def save_trade(self, trade_data):
        conn = None
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
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)
    
    def load_trades(self, limit=None):
        conn = None
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
        except Exception as e:
            print(f"❌ DB load trades error: {e}")
            return []
        finally:
            if conn: self._put_conn(conn)
    
    # ========== Patterns ==========
    def save_pattern(self, pattern_data):
        conn = None
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
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)
    
    def load_patterns(self):
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM learned_patterns ORDER BY last_updated DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except Exception as e:
            print(f"❌ DB load patterns error: {e}")
            return []
        finally:
            if conn: self._put_conn(conn)
    
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
    
    # ========== Model Storage (King's Brain) ==========
    def load_model(self, name):
        """تحميل ملف الموديل"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT model_data FROM dl_models_v2 WHERE model_name = %s ORDER BY trained_at DESC LIMIT 1", (name,))
            result = cursor.fetchone()
            if result and result[0] is not None:
                return bytes(result[0])
            return None
        except self._psycopg2.errors.UndefinedTable:
            # This happens if dl_models_v2 doesn't exist yet. It's not an error.
            conn.rollback()
            print(f"INFO: Table 'dl_models_v2' not found for model '{name}'. This is expected before the first training cycle.")
            return None
        except Exception as e:
            print(f"❌ DB Error loading model {name}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
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
