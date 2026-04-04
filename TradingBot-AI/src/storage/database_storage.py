"""
التخزين السحابي - Supabase Database
"""
import os
from datetime import datetime
import time
import inspect
import threading

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
                'port': parsed.port or 5432, # استخدام المنفذ من URL أو القيمة الافتراضية
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
        self.pool = ThreadedConnectionPool(10, 10, **self._db_params)
        # --- END ---

        # A semaphore to limit concurrent access to the database pool
        self.db_access_semaphore = threading.Semaphore(self.pool.maxconn)

        self.json = json_module
        self.RealDictCursor = RealDictCursor
        self._psycopg2 = psycopg2

        # --- FAST STARTUP: Run table checks in the background ---
        self.init_thread = threading.Thread(target=self._initialize_tables_background, daemon=True)
        self.init_thread.start()

    def _initialize_tables_background(self):
        """Runs the slow table creation/verification in a background thread."""
        if not self._create_tables():
            # If this fails, the bot might run into issues, but we log it loudly.
            print("❌ CRITICAL: Background creation of database tables failed after multiple attempts.")
        self._check_schema_updates()
   

    def _get_conn(self):
        """Gets a HEALTHY connection from the pool, with self-healing and semaphore protection."""
        # Acquire the semaphore, blocking if the pool is at its concurrent access limit.
        # This prevents the thundering herd problem.
        self.db_access_semaphore.acquire()

        start_time = time.time()
        try:
            for attempt in range(20): # Try up to 20 times
                conn = None # Initialize to prevent UnboundLocalError in except block
                try:
                    conn = self.pool.getconn()
                    
                    # --- SMART PING (Only if idle) ---
                    if not hasattr(self, 'conn_last_used'):
                        self.conn_last_used = {}
                    
                    now = time.time()
                    last_used = self.conn_last_used.get(id(conn), 0)
                    
                    # Run ping only if the connection has been idle for more than 30 seconds
                    if now - last_used > 30:
                        with conn.cursor() as cursor:
                            cursor.execute('SELECT 1')
                    
                    # Update last used time
                    self.conn_last_used[id(conn)] = now
                    # --- END SMART PING ---

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
        except Exception as e:
            # CRITICAL: If we failed to get a connection, we must release the semaphore
            self.db_access_semaphore.release()
            raise e

    def _put_conn(self, conn):
        """
        إرجاع اتصال إلى المجمع مع فحص سلامته.
        هذا هو "صمام الأمان" الرئيسي لمنع تسرب الموارد.
        """
        try:
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
        finally:
            # Always release the semaphore, even if putconn fails, 
            # to prevent deadlocks.
            self.db_access_semaphore.release()

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
                conn.rollback()
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
            whale_confidence FLOAT DEFAULT 0,
            atr_value FLOAT DEFAULT 0,
            sentiment_score FLOAT DEFAULT 0,
            panic_score FLOAT DEFAULT 0,
            optimism_penalty FLOAT DEFAULT 0,
            psychological_analysis TEXT,
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
        CREATE TABLE IF NOT EXISTS symbol_memory (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) UNIQUE,
            sentiment_avg FLOAT DEFAULT 0,
            whale_confidence_avg FLOAT DEFAULT 0,
            profit_loss_ratio FLOAT DEFAULT 0,
            volume_trend VARCHAR(10) DEFAULT 'neutral',
            last_interaction TIMESTAMP DEFAULT NOW(),
            panic_score_avg FLOAT DEFAULT 0,
            optimism_penalty_avg FLOAT DEFAULT 0,
            psychological_summary TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
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
        CREATE TABLE IF NOT EXISTS symbol_memory (
            symbol VARCHAR(20) PRIMARY KEY,
            total_trades INTEGER DEFAULT 0,
            win_count INTEGER DEFAULT 0,
            loss_count INTEGER DEFAULT 0,
            trap_count INTEGER DEFAULT 0,
            avg_profit FLOAT DEFAULT 0,
            max_profit FLOAT DEFAULT 0,
            min_profit FLOAT DEFAULT 0,
            avg_hold_hours FLOAT DEFAULT 0,
            best_rsi FLOAT DEFAULT 50,
            best_volume_ratio FLOAT DEFAULT 1,
            last_trade_quality VARCHAR(10),
            last_updated TIMESTAMP DEFAULT NOW()
        );
        -- ✅ تم تعطيل جدول causal_data تمهيدا للحذف النهائي
        -- لا يتم انشاءه تلقائياً بعد الان
        """
        # --- FIX: Add indexes for cleanup performance and query speed ---
        create_indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_trades_history_timestamp ON trades_history(timestamp);
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_last_updated ON learned_patterns(last_updated);
        CREATE INDEX IF NOT EXISTS idx_ai_decisions_timestamp ON ai_decisions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_trap_memory_timestamp ON trap_memory(timestamp);
        CREATE INDEX IF NOT EXISTS idx_consultant_votes_timestamp ON consultant_votes(timestamp);
        CREATE INDEX IF NOT EXISTS idx_symbol_memory_symbol ON symbol_memory(symbol);
        -- ✅ تم حذف ايديكسات جدول causal_data بعد تعطيل الجدول
        
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
            # --- FIX: Convert all numpy types to native Python types before saving ---
            import numpy as np
            def convert_to_native(d):
                """Recursively converts NumPy data types in a dictionary or list to native Python types."""
                if isinstance(d, np.generic):
                    return d.item()
                if isinstance(d, dict):
                    return {k: convert_to_native(v) for k, v in d.items()}
                if isinstance(d, list):
                    return [convert_to_native(i) for i in d]
                return d
            trade_data = convert_to_native(trade_data)

            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades_history (symbol, action, profit_percent, sell_reason, tp_target, sl_target, hours_held, whale_confidence, atr_value, sentiment_score, panic_score, optimism_penalty, psychological_analysis, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                trade_data.get('symbol'),
                trade_data.get('action'),
                trade_data.get('profit_percent'),
                trade_data.get('sell_reason'),
                trade_data.get('tp_target'),
                trade_data.get('sl_target'),
                trade_data.get('hours_held'),
                trade_data.get('whale_confidence', 0),
                trade_data.get('atr_value', 0),
                trade_data.get('sentiment_score', 0),
                trade_data.get('panic_score', 0),
                trade_data.get('optimism_penalty', 0),
                trade_data.get('psychological_analysis', ''),
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
            # Inform the database that this is a read-only transaction for potential optimization.
            cursor.execute("SET TRANSACTION READ ONLY;")
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

    def delete_position(self, symbol):
        """Deletes a position from the positions table."""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM positions WHERE symbol = %s;", (symbol,))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB delete position error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                self._put_conn(conn)

    def save_positions_batch(self, positions_data):
        """
        Saves a batch of open positions using an efficient UPSERT and DELETE strategy.
        1. UPSERTs all current positions.
        2. Deletes any positions from the DB that are no longer in the provided list.
        """
        from psycopg2.extras import execute_batch

        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # If the positions list is empty, it means all positions are closed.
            # TRUNCATE is the most efficient way to clear the table.
            if not positions_data:
                cursor.execute("TRUNCATE TABLE positions;")
                conn.commit()
                cursor.close()
                return

            # --- If there are positions, perform the UPSERT + DELETE combo ---

            # --- FIX: Convert all numpy types to native Python types before saving ---
            def convert_to_native(d):
                for k, v in d.items():
                    if hasattr(v, 'item'): # Check if it's a numpy type
                        d[k] = v.item()
                    elif isinstance(v, dict):
                        convert_to_native(v) # Recurse for nested dicts (like 'data')
                return d

            # --- FIX: Filter out non-dict items and convert numpy types ---
            valid_positions = [p for p in positions_data if isinstance(p, dict)]
            if len(valid_positions) != len(positions_data):
                print(f"⚠️ save_positions_batch: filtered {len(positions_data) - len(valid_positions)} invalid entries")
            
            native_positions_data = [convert_to_native(p.copy()) for p in valid_positions]

            # Before executing, serialize the 'data' dictionary to a JSON string for each position.
            for pos in native_positions_data:
                if 'data' in pos and isinstance(pos['data'], dict):
                    pos['data'] = self.json.dumps(pos['data'])

            # 1. UPSERT all current positions into the database.
            sql_upsert = """
                INSERT INTO positions (symbol, buy_price, amount, highest_price, tp_level_1, tp_level_2, buy_time, invested, data)
                VALUES (%(symbol)s, %(buy_price)s, %(amount)s, %(highest_price)s, %(tp_level_1)s, %(tp_level_2)s, %(buy_time)s, %(invested)s, %(data)s)
                ON CONFLICT (symbol) DO UPDATE SET
                    buy_price = EXCLUDED.buy_price,
                    amount = EXCLUDED.amount,
                    highest_price = EXCLUDED.highest_price,
                    tp_level_1 = EXCLUDED.tp_level_1,
                    tp_level_2 = EXCLUDED.tp_level_2,
                    buy_time = EXCLUDED.buy_time,
                    invested = EXCLUDED.invested,
                    data = EXCLUDED.data;
            """
            execute_batch(cursor, sql_upsert, native_positions_data)

            # 2. DELETE any positions from the DB that are no longer in the live batch.
            symbols_in_batch = tuple(pos['symbol'] for pos in valid_positions)
            if not symbols_in_batch:
                cursor.execute("TRUNCATE TABLE positions;")
            else:
                sql_delete = "DELETE FROM positions WHERE symbol NOT IN %s;"
                cursor.execute(sql_delete, (symbols_in_batch,))

            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"❌ DB save_positions_batch error: {e}")
            if conn: conn.rollback()
        finally:
            if conn:
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
                self._put_conn(conn)
    
    def load_all_patterns(self):
        """
        Loads all learned patterns from the database into a list of dictionaries.
        This is intended for caching all patterns in memory to avoid frequent DB calls.
        """
        start_time = time.time()
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            
            cursor.execute("SET TRANSACTION READ ONLY;")

            query = """
                SELECT 
                    id, 
                    pattern_type, 
                    (data->'features') as features, 
                    (data->>'success_rate')::float as success_rate
                FROM learned_patterns
                ORDER BY last_updated DESC;
            """
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            reconstructed_results = []
            for row in results:
                row_dict = dict(row)
                row_dict['data'] = {'features': row_dict.pop('features', {})}
                reconstructed_results.append(row_dict)

            return reconstructed_results

        except Exception as e:
            print(f"❌ DB load_all_patterns error: {e}")
            return []
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)
    
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
    
    def save_learning_data(self, learning_type, data):
        """حفظ بيانات التعلم (الملك والمستشارين)
        
        Args:
            learning_type: 'king' أو 'advisors'
            data: قاموس البيانات
        """
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # اختصار الأسماء لأن symbol عمود VARCHAR(10)
            short_names = {'king': 'lk', 'advisors': 'la'}
            short_name = short_names.get(learning_type, learning_type[:2])
            
            cursor.execute("""
                INSERT INTO ai_decisions (symbol, decision, confidence, data)
                VALUES (%s, %s, %s, %s)
            """, (
                short_name,
                'learn',  # اختصار من 15 حرف لـ 5
                0,
                self.json.dumps({
                    'learning_type': learning_type,
                    'learning_data': data
                })
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save learning error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                self._put_conn(conn)
    
    def load_learning_data(self, learning_type):
        """تحميل بيانات التعلم"""
        conn = None
        try:
            short_names = {'king': 'lk', 'advisors': 'la'}
            short_name = short_names.get(learning_type, learning_type[:2])
            
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("""
                SELECT data FROM ai_decisions 
                WHERE symbol = %s AND decision = 'learn'
                ORDER BY timestamp DESC LIMIT 1
            """, (short_name,))
            result = cursor.fetchone()
            cursor.close()
            if result and result.get('data'):
                return result['data'].get('learning_data', {})
            return {}
        except Exception as e:
            print(f"❌ DB load learning error: {e}")
            return {}
        finally:
            if conn:
                conn.rollback()
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
                "trades (30d)":     ("trades_history",     "timestamp",    30),
                "patterns (7d)":    ("learned_patterns",  "last_updated", 7),
                "traps (30d)":      ("trap_memory",      "timestamp",    30),
                "votes (30d)":      ("consultant_votes", "timestamp",    30),
                "symbol (180d)":    ("symbol_memory",    "last_updated", 180),
                "news (7d)":        ("news_sentiment",   "timestamp",    7),
                "ai decisions (7d)":("ai_decisions",     "timestamp",    7),
            }
            
            total_deleted = 0
            deleted_log = []
            batch_size = 500

            for key, (table, date_col, days) in queries.items():
                table_total_deleted = 0
                while True:
                    query = f"""DELETE FROM {table} WHERE ctid IN (
                                 SELECT ctid FROM {table} 
                                 WHERE {date_col} < NOW() - INTERVAL '{days} days' 
                                 LIMIT {batch_size}
                             );"""
                    cursor.execute(query)
                    count = cursor.rowcount
                    conn.commit()
                    
                    if count == 0:
                        break
                    
                    table_total_deleted += count
                    time.sleep(0.1)

                if table_total_deleted > 0:
                    deleted_log.append(f"{table_total_deleted} {key}")
                total_deleted += table_total_deleted

            # حذف ai_decisions القديمة مع حماية آخر سجل تعلم للملك والمستشارين
            ai_total_deleted = 0
            while True:
                query = """
                    DELETE FROM ai_decisions WHERE ctid IN (
                        SELECT ctid FROM ai_decisions
                        WHERE timestamp < NOW() - INTERVAL '30 days'
                        AND id NOT IN (
                            SELECT id FROM ai_decisions WHERE symbol = 'lk' ORDER BY timestamp DESC LIMIT 1
                        )
                        AND id NOT IN (
                            SELECT id FROM ai_decisions WHERE symbol = 'la' ORDER BY timestamp DESC LIMIT 1
                        )
                        LIMIT 500
                    );
                """
                cursor.execute(query)
                count = cursor.rowcount
                conn.commit()
                if count == 0:
                    break
                ai_total_deleted += count
                time.sleep(0.1)

            if ai_total_deleted > 0:
                deleted_log.append(f"{ai_total_deleted} AI decisions (30d)")
            total_deleted += ai_total_deleted

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
    
    # ========== Symbol Memory ==========
    def update_symbol_memory(self, symbol, profit, trade_quality, hours_held, rsi, volume_ratio):
        """تحديث ذاكرة العملة بعد كل صفقة"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO symbol_memory 
                (symbol, total_trades, win_count, loss_count, trap_count, avg_profit, 
                 max_profit, min_profit, avg_hold_hours, best_rsi, best_volume_ratio, 
                 last_trade_quality, last_updated)
                VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    total_trades = symbol_memory.total_trades + 1,
                    win_count = symbol_memory.win_count + %s,
                    loss_count = symbol_memory.loss_count + %s,
                    trap_count = symbol_memory.trap_count + %s,
                    avg_profit = (symbol_memory.avg_profit * symbol_memory.total_trades + %s) / (symbol_memory.total_trades + 1),
                    max_profit = GREATEST(symbol_memory.max_profit, %s),
                    min_profit = LEAST(symbol_memory.min_profit, %s),
                    avg_hold_hours = (symbol_memory.avg_hold_hours * symbol_memory.total_trades + %s) / (symbol_memory.total_trades + 1),
                    best_rsi = %s,
                    best_volume_ratio = %s,
                    last_trade_quality = %s,
                    last_updated = NOW();
            """, (
                symbol,
                1 if profit > 0 else 0, 1 if profit <= 0 else 0,
                1 if trade_quality in ['TRAP', 'RISKY'] else 0,
                profit, profit, profit, hours_held, rsi, volume_ratio, trade_quality,
                1 if profit > 0 else 0, 1 if profit <= 0 else 0,
                1 if trade_quality in ['TRAP', 'RISKY'] else 0,
                profit, profit, profit, hours_held, rsi, volume_ratio, trade_quality
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB update symbol memory error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                self._put_conn(conn)

    def get_symbol_memory(self, symbol):
        """جلب ذاكرة عملة معينة"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("SELECT * FROM symbol_memory WHERE symbol = %s", (symbol,))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else {}
        except Exception as e:
            print(f"❌ DB get symbol memory error: {e}")
            return {}
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    # ========== Causal Data ==========
    def save_causal_data(self, symbol, fear_greed=50, whale_activity=0,
                         exchange_inflow=0, exchange_outflow=0, social_volume=0,
                         funding_rate=0, btc_dominance=50, market_sentiment='neutral',
                         source='live'):
        """حفظ بيانات السببية"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO causal_data 
                (symbol, fear_greed, whale_activity, exchange_inflow, exchange_outflow,
                 social_volume, funding_rate, btc_dominance, market_sentiment, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (symbol, fear_greed, whale_activity, exchange_inflow, exchange_outflow,
                  social_volume, funding_rate, btc_dominance, market_sentiment, source))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ DB save causal data error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                self._put_conn(conn)

    def get_causal_data(self, symbol, hours=24):
        """جلب بيانات السببية لعملة معينة"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            cursor.execute("""
                SELECT * FROM causal_data 
                WHERE symbol = %s 
                AND timestamp > NOW() - INTERVAL '%s hours'
                ORDER BY timestamp DESC LIMIT 1
            """, (symbol, hours))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else {}
        except Exception as e:
            print(f"❌ DB get causal data error: {e}")
            return {}
        finally:
            if conn:
                conn.rollback()
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

    def save_symbol_memory(self, symbol, data):
        """حفظ بيانات ذاكرة الملك للعملة"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO symbol_memory (
                    symbol, sentiment_avg, whale_confidence_avg, profit_loss_ratio,
                    volume_trend, panic_score_avg, optimism_penalty_avg, psychological_summary
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    sentiment_avg = EXCLUDED.sentiment_avg,
                    whale_confidence_avg = EXCLUDED.whale_confidence_avg,
                    profit_loss_ratio = EXCLUDED.profit_loss_ratio,
                    volume_trend = EXCLUDED.volume_trend,
                    panic_score_avg = EXCLUDED.panic_score_avg,
                    optimism_penalty_avg = EXCLUDED.optimism_penalty_avg,
                    psychological_summary = EXCLUDED.psychological_summary,
                    updated_at = NOW()
            """, (
                symbol,
                data.get('sentiment_avg', 0),
                data.get('whale_confidence_avg', 0),
                data.get('profit_loss_ratio', 0),
                data.get('volume_trend', 'neutral'),
                data.get('panic_score_avg', 0),
                data.get('optimism_penalty_avg', 0),
                data.get('psychological_summary', '')
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"Error saving symbol memory: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_symbol_memory(self, symbol):
        """جلب ذاكرة الملك للعملة"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM symbol_memory WHERE symbol = %s", (symbol,))
            result = cursor.fetchone()
            cursor.close()
            return result
        except Exception as e:
            print(f"Error getting symbol memory: {e}")
            return None
        finally:
            if conn:
                conn.close()
