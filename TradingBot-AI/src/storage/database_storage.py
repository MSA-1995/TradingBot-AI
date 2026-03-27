"""
التخزين السحابي - Supabase Database
"""
import os
from datetime import datetime
import time
import inspect
import inspect

# --- DATABASE CONNECTION POOL ---
# To make the bot stable, we use a connection pool.
# This avoids connection drops and manages reconnections automatically.
from psycopg2.pool import ThreadedConnectionPool, PoolError
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
        # minconn=5, maxconn=5 (Pre-create all connections to avoid locking during runtime)
        self.pool = ThreadedConnectionPool(5, 5, **self._db_params)
        # --- END ---

        self.json = json_module
        self.RealDictCursor = RealDictCursor
        self._psycopg2 = psycopg2
        
        if not self._create_tables():
            raise Exception("Failed to create database tables after multiple attempts.")
        self._check_schema_updates()

    def _get_conn(self):
        """Gets a HEALTHY connection from the pool, with self-healing."""
        for attempt in range(20): # Try up to 20 times
            try:
                conn = self.pool.getconn()
                
                # --- CONNECTION SELF-HEALING (Ping Check) ---
                # Run a super-fast, lightweight query to check if the connection is alive.
                # If it fails, the connection is dead and we'll discard it.
                with conn.cursor() as cursor:
                    cursor.execute('SELECT 1')
                # --- END SELF-HEALING ---

                # Optional: Check transaction status if needed for debugging
                # tx_status = conn.get_transaction_status()
                # if tx_status != 0:
                #     TX_STATUS_MAP = {0: 'IDLE', 1: 'ACTIVE', 2: 'INTRANS', 3: 'INERROR'}
                #     print(f"🔍 DB _get_conn: Received conn with tx_status = {TX_STATUS_MAP.get(tx_status, 'UNKNOWN')} ({tx_status})")
                
                return conn # Connection is healthy, return it

            except self._psycopg2.OperationalError as e:
                # This is the key: The connection was dead. Discard it and retry.
                print(f"⚠️ Stale DB connection detected: {e}. Discarding and retrying...")
                if conn:
                    self.pool.putconn(conn, close=True) # Close the dead connection
                time.sleep(0.1)

            except PoolError:
                # Pool is genuinely exhausted, wait a bit and retry
                print("Pool exhausted, waiting...")
                time.sleep(0.1)
        
        # If we get here, we failed after all retries
        raise Exception("DB Connection failed after multiple retries. The database might be down.")

    def _put_conn(self, conn):
        """
        إرجاع اتصال إلى المجمع مع فحص سلامته.
        هذا هو "صمام الأمان" الرئيسي لمنع تسرب الموارد.
        """
        if conn and not conn.closed:
            tx_status = conn.get_transaction_status()
            # 0 = IDLE (الحالة السليمة)
            if tx_status != 0:
                # --- الطباعة التشخيصية القوية ---
                # الحصول على اسم الوظيفة التي استدعت _put_conn بشكل غير صحيح
                caller_frame = inspect.stack()[1]
                caller_function = caller_frame.function
                TX_STATUS_MAP = {0: 'IDLE', 1: 'ACTIVE', 2: 'INTRANS', 3: 'INERROR'}
                print(f"⚠️ Leak Detector: Function '{caller_function}' returned a dirty connection (Status: {TX_STATUS_MAP.get(tx_status, 'UNKNOWN')}). Forcing rollback.")
                conn.rollback() # --- التنظيف بالقوة ---
            
            self.pool.putconn(conn)
        else:
            # هذا ليس خطأ، قد يتم تجاهل الاتصالات المغلقة عمداً
            pass

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
            if conn:
                # For READ functions, we MUST rollback to close the transaction
                # and prevent `IDLE IN TRANSACTION` state which causes locks.
                conn.rollback()
                self._put_conn(conn)

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
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)

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
        # --- FIX: Add indexes for cleanup performance and query speed ---
        create_indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_trades_history_timestamp ON trades_history(timestamp);
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_last_updated ON learned_patterns(last_updated);
        CREATE INDEX IF NOT EXISTS idx_ai_decisions_timestamp ON ai_decisions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_trap_memory_timestamp ON trap_memory(timestamp);
        CREATE INDEX IF NOT EXISTS idx_consultant_votes_timestamp ON consultant_votes(timestamp);
        
        -- Indexes for lightning fast pattern searching
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_type ON learned_patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_rsi ON learned_patterns((data->'features'->>'rsi_zone'));
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_trend ON learned_patterns((data->'features'->>'trend'));

        -- *** SUPER INDEX for find_similar_patterns_in_db ***
        -- This composite index is specifically designed to make that query extremely fast.
        -- It covers all filtering conditions and the sorting order in one go.
        CREATE INDEX IF NOT EXISTS idx_super_pattern_search ON learned_patterns(pattern_type, (data->'features'->>'rsi_zone'), (data->'features'->>'trend'), last_updated DESC);

        -- Force update of query planner statistics
        ANALYZE learned_patterns;
        """

        for attempt in range(3):
            conn = None
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                # --- FIX: Increase statement timeout for this session to prevent DDL timeouts ---
                cursor.execute("SET statement_timeout = '60s';")
                # --- Create tables first, then indexes ---
                cursor.execute(create_sql)
                cursor.execute(create_indexes_sql)
                conn.commit()
                cursor.close()
                self._put_conn(conn) # --- إرجاع الاتصال السليم إلى المجمع
                print("✅ Database tables and indexes created/verified successfully.")
                return True # --- نجاح، خروج

            except self._psycopg2.Error as e: # --- التعامل مع أخطاء قاعدة البيانات فقط
                print(f"⚠️ Table/Index creation DB error (attempt {attempt + 1}/3): {e}")
                if conn:
                    # --- الخطوة الأهم: تخلص من الاتصال الفاشل ولا تعيده للمجمع
                    self.pool.putconn(conn, close=True)
                    print("🔥 Discarded faulty DB connection. Will retry with a new one.")

                if attempt < 2:
                    import time
                    time.sleep(5) # --- انتظار قبل المحاولة التالية
                else:
                    print("❌ Final attempt to create tables/indexes failed.")
            except Exception as e:
                print(f"⚠️ An unexpected error occurred during table/index creation: {e}")
                if conn: # تخلص من الاتصال عند حدوث أي خطأ غير متوقع أيضًا
                    self.pool.putconn(conn, close=True)
                # لا تعيد المحاولة في الأخطاء العامة غير المتوقعة
                break

        return False # فشل بعد كل المحاولات
    
    def _check_schema_updates(self):
        """التحقق من تحديثات المخطط وإصلاحها تلقائياً (Self-Healing) في معاملات معزولة."""
        
        # --- المهمة: التأكد من وجود جدول 'dl_models_v2' (في معاملة معزولة)
        conn_dl = None
        try:
            conn_dl = self._get_conn()
            cursor = conn_dl.cursor()
            # مهلة أقصر مناسبة لهذه العملية السريعة
            cursor.execute("SET statement_timeout = '30s';")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dl_models_v2 (
                    model_name VARCHAR(50) PRIMARY KEY,
                    model_data BYTEA NOT NULL,
                    trained_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn_dl.commit()
            print("🔧 Schema Update: Ensured 'dl_models_v2' table exists.")
            cursor.close()
        except Exception as e:
            print(f"⚠️ Schema update error (dl_models_v2): {e}")
            if conn_dl: conn_dl.rollback()
        finally:
            if conn_dl:
                # For WRITE functions, we do NOT rollback in finally.
                self._put_conn(conn_dl)

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
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)
    
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
            if conn:
                conn.rollback() # End any lingering transaction
                self._put_conn(conn)
    
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
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)
    
    def find_similar_patterns_in_db(self, features, pattern_type, limit=10):
        """
        Finds similar patterns with 'precision surgery' to release the connection ASAP.
        """
        conn = None
        raw_results = []
        try:
            # --- Step 1: Get connection & data ---
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)

            query_conditions = ["pattern_type = %s"]
            params = [pattern_type]

            if 'rsi_zone' in features:
                query_conditions.append("data->'features'->>'rsi_zone' = %s")
                params.append(features['rsi_zone'])
            
            if 'trend' in features:
                query_conditions.append("data->'features'->>'trend' = %s")
                params.append(features['trend'])

            query = f"""
                SELECT *, (data->>'success_rate')::float as success_rate
                FROM learned_patterns
                WHERE {' AND '.join(query_conditions)}
                ORDER BY last_updated DESC
                LIMIT %s
            """
            params.append(limit * 10)

            cursor.execute(query, tuple(params))
            raw_results = cursor.fetchall()
            cursor.close()

        except Exception as e:
            print(f"❌ DB find_similar_patterns error: {e}")
            return []
        finally:
            # --- Step 2: Release connection IMMEDIATELY ---
            if conn:
                conn.rollback() # Always rollback read-only queries
                self._put_conn(conn)

        # --- Step 3: Process data AFTER connection is released ---
        return [dict(row) for row in raw_results]
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        """Saves an AI decision, ensuring the connection is always returned."""
        conn = None
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
            print(f"❌ DB save decision error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)
    
    def load_ai_decisions(self, limit=10):
        """Loads AI decisions, ensuring the connection is always returned."""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM ai_decisions ORDER BY timestamp DESC LIMIT %s", (limit,))
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except Exception as e:
            print(f"❌ DB load AI decisions error: {e}")
            return []
        finally:
            if conn:
                conn.rollback() # End any lingering transaction
                self._put_conn(conn)
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        """This function is currently not in use and is pending refactoring."""
        print("⚠️ save_performance is not implemented with the new connection handling.")
        return False
    
    def load_performance(self, days=7):
        """This function is currently not in use and is pending refactoring."""
        print("⚠️ load_performance is not implemented with the new connection handling.")
        return []
    
    # ========== Consultant Votes ==========
    def save_consultant_vote(self, vote_data):
        """Saves a consultant vote, ensuring the connection is always returned."""
        conn = None
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
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)
    
    def load_consultant_votes(self, consultant_name=None, limit=1000):
        """Loads consultant votes, ensuring the connection is always returned."""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            sql = "SELECT * FROM consultant_votes "
            params = []
            if consultant_name:
                sql += "WHERE consultant_name = %s "
                params.append(consultant_name)
            sql += "ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(sql, tuple(params))
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except Exception as e:
            print(f"❌ DB load consultant votes error: {e}")
            return []
        finally:
            if conn:
                conn.rollback() # End any lingering transaction
                self._put_conn(conn)

    
    # ========== Auto Cleanup ==========
    def cleanup_old_data(self):
        """Cleans up old data, ensuring the connection is always returned."""
        conn = None
        try:
            # --- BATCH DELETE STRATEGY TO AVOID LONG TABLE LOCKS ---
            conn = self._get_conn()
            cursor = conn.cursor()
            
            queries = {
                "trades (6m)": ("trades_history", "timestamp", 180),
                "patterns (6m)": ("learned_patterns", "last_updated", 180),
                "traps (6m)": ("trap_memory", "timestamp", 180),
                "votes (6m)": ("consultant_votes", "timestamp", 180),
                "AI decisions (30d)": ("ai_decisions", "timestamp", 30)
            }
            
            total_deleted = 0
            deleted_log = []
            batch_size = 500 # Delete 500 rows at a time

            for key, (table, date_col, days) in queries.items():
                table_total_deleted = 0
                while True:
                    # Construct and execute the DELETE command for a single batch
                    query = f"""DELETE FROM {table} WHERE ctid IN (
                                 SELECT ctid FROM {table} 
                                 WHERE {date_col} < NOW() - INTERVAL '{days} days' 
                                 LIMIT {batch_size}
                             );"""
                    cursor.execute(query)
                    count = cursor.rowcount
                    conn.commit() # Commit after each batch to release locks
                    
                    if count == 0:
                        break # No more old rows to delete in this table
                    
                    table_total_deleted += count
                    time.sleep(0.1) # Small sleep to yield to other processes

                if table_total_deleted > 0:
                    deleted_log.append(f"{table_total_deleted} {key}")
                total_deleted += table_total_deleted

            cursor.close()
            
            if total_deleted > 0:
                print(f"🗑️ Batched Cleaned: {', '.join(deleted_log)}")
            
            return True
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                conn.rollback() # End any lingering transaction
                self._put_conn(conn)
    
    # ========== Traps ==========
    def save_trap(self, trap_data):
        """Saves a trap, ensuring the connection is always returned."""
        conn = None
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
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)
    
    def load_traps(self):
        """Loads all traps, ensuring the connection is always returned."""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM trap_memory ORDER BY timestamp DESC")
            result = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in result]
        except Exception as e:
            print(f"❌ DB load traps error: {e}")
            return []
        finally:
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)
    
    # ========== Model Storage (King's Brain) ==========
    def load_model(self, name):
        """تحميل ملف الموديل"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT model_data FROM dl_models_v2 WHERE model_name = %s ORDER BY trained_at DESC LIMIT 1", (name,))
            result = cursor.fetchone()
            cursor.close()
            if result and result[0] is not None:
                return bytes(result[0])
            return None
        except self._psycopg2.errors.UndefinedTable:
            # This happens if dl_models_v2 doesn't exist yet. It's not an error.
            print(f"INFO: Table 'dl_models_v2' not found for model '{name}'. This is expected before the first training cycle.")
            return None
        except Exception as e:
            print(f"❌ DB Error loading model {name}: {e}")
            return None
        finally:
            if conn:
                conn.rollback() # End any lingering transaction
                self._put_conn(conn)
    
    # ========== Positions ==========
    def save_positions(self, positions):
        """Saves positions to the database using a batch insert and proper connection handling."""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Use TRUNCATE for efficiency, it's an atomic DDL command
            cursor.execute("TRUNCATE TABLE positions")

            values_to_insert = []
            for symbol, config in positions.items():
                if config.get('position'):
                    pos = config['position']
                    invested = float(pos['buy_price']) * float(pos['amount'])

                    values_to_insert.append((
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

            if values_to_insert:
                from psycopg2.extras import execute_values
                execute_values(
                    cursor,
                    """INSERT INTO positions 
                    (symbol, buy_price, amount, highest_price, tp_level_1, tp_level_2, buy_time, invested, data)
                    VALUES %s""",
                    values_to_insert
                )

            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save positions error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                # For WRITE functions, we do NOT rollback in finally.
                # The transaction is handled by commit() or rollback() in the try/except blocks.
                self._put_conn(conn)

    def load_positions(self):
        """Loads all positions from the database, ensuring connection is always returned."""
        conn = None
        try:
            conn = self._get_conn()
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
            return {}
        finally:
            if conn:
                conn.rollback() # Always rollback to ensure clean state
                self._put_conn(conn)
