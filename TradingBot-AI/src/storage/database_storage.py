"""
التخزين السحابي - Supabase Database (Cleaned Version)
"""
import os
import logging
from datetime import datetime
import time
import inspect
import threading
import math
import psycopg2
from psycopg2.extras import RealDictCursor
import json as json_module
from urllib.parse import urlparse, unquote
from psycopg2.pool import ThreadedConnectionPool, PoolError
import pandas as pd

class DatabaseStorage:
    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise Exception("DATABASE_URL not found!")
        
        parsed = urlparse(database_url)
        self._db_params = {
            'host':                parsed.hostname,
            'port':                parsed.port or 5432,
            'database':            parsed.path[1:],
            'user':                parsed.username,
            'password':            unquote(parsed.password),
            'sslmode':             'require',
            'connect_timeout':     15,
            'keepalives':          1,
            'keepalives_idle':     60,
            'keepalives_interval': 30,
            'keepalives_count':    10
        }
        
        self.pool                 = ThreadedConnectionPool(6, 10, **self._db_params)
        self.db_access_semaphore  = threading.Semaphore(self.pool.maxconn)
        self.json                 = json_module
        self.RealDictCursor       = RealDictCursor
        self._psycopg2            = psycopg2

        if self._create_tables():
            print("✅ Database: Connected Successfully")
        else:
            print("❌ Database: Failed to create tables")

    def _create_tables(self):
        """Creates necessary database tables if they don't exist."""
        conn = None
        try:
            conn = self.pool.getconn()
            with conn.cursor() as cursor:
                # 1. Bot Settings
                cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (key VARCHAR(50) PRIMARY KEY, value TEXT);")
                # 2. Positions
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        symbol VARCHAR(20) PRIMARY KEY, buy_price FLOAT, amount FLOAT, highest_price FLOAT,
                        tp_level_1 FLOAT, tp_level_2 FLOAT, buy_time TIMESTAMP, invested FLOAT, data TEXT
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_buy_time ON positions(buy_time DESC);")

                # 3. Trades History
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades_history (
                        id SERIAL PRIMARY KEY, symbol VARCHAR(20), action VARCHAR(10), timestamp TIMESTAMP DEFAULT NOW(),
                        profit_percent FLOAT, sell_reason TEXT, hours_held FLOAT,
                        rsi FLOAT, volume_ratio FLOAT, trade_quality VARCHAR(20), profit FLOAT,
                        whale_confidence FLOAT, atr_value FLOAT, sentiment_score FLOAT, panic_score FLOAT, optimism_penalty FLOAT,
                        psychological_analysis TEXT, data JSONB, order_book_imbalance FLOAT, spread_volatility FLOAT,
                        depth_at_1pct FLOAT, market_impact_score FLOAT, liquidity_trends FLOAT, volatility_risk_score FLOAT,
                        correlation_risk FLOAT, gap_risk_score FLOAT, black_swan_probability FLOAT, behavioral_risk FLOAT,
                        systemic_risk FLOAT, profit_optimization_score FLOAT, time_decay_signals FLOAT, opportunity_cost_exits FLOAT,
                        market_condition_exits FLOAT, harmonic_patterns_score FLOAT, elliott_wave_signals FLOAT, fractal_patterns FLOAT,
                        cycle_patterns FLOAT, momentum_patterns FLOAT, smart_money_ratio FLOAT, exchange_whale_flows FLOAT,
                        statistical_outliers FLOAT, pattern_anomalies FLOAT, behavioral_anomalies FLOAT, volume_anomalies FLOAT,
                        attention_mechanism_score FLOAT, multi_scale_features FLOAT, temporal_features FLOAT,
                        volume_trend_strength FLOAT, volume_volatility FLOAT, volume_momentum FLOAT, volume_seasonality FLOAT,
                        volume_correlation FLOAT, dynamic_consultant_weights FLOAT, uncertainty_quantification FLOAT, context_aware_score FLOAT
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades_history(symbol);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades_history(timestamp DESC);")

                # 4. Learned Patterns
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learned_patterns (
                        id SERIAL PRIMARY KEY, pattern_type VARCHAR(20), data JSONB, success_rate FLOAT, last_updated TIMESTAMP DEFAULT NOW()
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_updated ON learned_patterns(last_updated DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON learned_patterns(pattern_type);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_success ON learned_patterns(success_rate DESC);")

                # 5. Symbol Memory
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_memory (
                        symbol VARCHAR(20) PRIMARY KEY, total_trades INT DEFAULT 0, win_count INT DEFAULT 0, loss_count INT DEFAULT 0,
                        trap_count INT DEFAULT 0, avg_profit FLOAT DEFAULT 0, max_profit FLOAT DEFAULT 0, min_profit FLOAT DEFAULT 0,
                        avg_hold_hours FLOAT DEFAULT 0, best_rsi FLOAT, best_volume_ratio FLOAT, last_trade_quality VARCHAR(20),
                        sentiment_avg FLOAT DEFAULT 0, whale_confidence_avg FLOAT DEFAULT 0, panic_score_avg FLOAT DEFAULT 0,
                        optimism_penalty_avg FLOAT DEFAULT 0,
                        profit_loss_ratio FLOAT DEFAULT 0, volume_trend FLOAT DEFAULT 0,
                        psychological_summary VARCHAR(50) DEFAULT 'Neutral',
                        courage_boost FLOAT DEFAULT 0, time_memory_modifier FLOAT DEFAULT 0,
                        pattern_score FLOAT DEFAULT 0, win_rate_boost FLOAT DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT NOW()
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_memory_updated ON symbol_memory(last_updated DESC);")

                # 6. فهرس على dl_models_v2 فقط لو الجدول موجود
                cursor.execute("""
                    DO 

$$
BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dl_models_v2') THEN
                            CREATE INDEX IF NOT EXISTS idx_models_lookup ON dl_models_v2(model_name, trained_at DESC);
                        END IF;
                    END
$$

;
                """)

                # 7. فهارس إضافية
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_memory_symbol_updated ON symbol_memory(symbol, last_updated DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_quality ON trades_history(trade_quality, timestamp DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_profit ON trades_history(profit DESC) WHERE profit IS NOT NULL;")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades_history(symbol, timestamp DESC);")

                conn.commit()

            return True
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            return False
        finally:
            if conn:
                self.pool.putconn(conn)

    def _initialize_tables_background(self):
        self._create_tables()

    def _get_conn(self):
        self.db_access_semaphore.acquire()
        conn = None
        try:
            for attempt in range(20):
                try:
                    conn = self.pool.getconn()
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT 1')
                    return conn
                except self._psycopg2.OperationalError:
                    if conn:
                        self.pool.putconn(conn, close=True)
                        conn = None
                    time.sleep(0.1)
                except PoolError:
                    conn = None
                    time.sleep(0.1)
            raise Exception("DB Connection failed")
        except Exception as e:
            self.db_access_semaphore.release()
            raise e

    def _put_conn(self, conn):
        try:
            if conn and not conn.closed:
                if conn.get_transaction_status() != 0:
                    conn.rollback()
                self.pool.putconn(conn)
        finally:
            self.db_access_semaphore.release()

    def save_setting(self, key, value):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO bot_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;", (key, value))
            conn.commit()
            return True
        except Exception:
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)

    def load_setting(self, key):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY;")
                cursor.execute("SELECT value FROM bot_settings WHERE key = %s", (key,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception:
            return None
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    def get_news_data(self, symbol=None):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=self.RealDictCursor) as cursor:
                cursor.execute("SET TRANSACTION READ ONLY;")
                if symbol:
                    cursor.execute("""
                        SELECT sentiment, score
                        FROM news_sentiment
                        WHERE symbol = %s
                        AND timestamp > NOW() - INTERVAL '24 hours'
                    """, (symbol,))
                else:
                    cursor.execute("""
                        SELECT sentiment, score
                        FROM news_sentiment
                        WHERE timestamp > NOW() - INTERVAL '24 hours'
                    """)
                rows = cursor.fetchall()

            if not rows:
                return None

            positive = sum(1 for r in rows if r['sentiment'] == 'POSITIVE')
            negative = sum(1 for r in rows if r['sentiment'] == 'NEGATIVE')
            neutral  = sum(1 for r in rows if r['sentiment'] == 'NEUTRAL')
            total    = len(rows)
            score    = sum(float(r['score'] or 0) for r in rows)
            score    = max(-10.0, min(10.0, score))

            return {
                'news_score': round(score, 2),
                'total':      total,
                'positive':   positive,
                'negative':   negative,
                'neutral':    neutral,
            }

        except Exception as e:
            print(f"⚠️ get_news_data error [{symbol}]: {e}")
            return None
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    @staticmethod
    def _convert_to_native(d):
        """تحويل جميع الأنواع غير المتوافقة مع JSON"""
        import numpy as np
        if isinstance(d, float) and not math.isfinite(d):
            return 0.0
        if isinstance(d, pd.Timestamp):
            return d.isoformat()
        if isinstance(d, datetime):
            return d.isoformat()
        if isinstance(d, np.generic):
            val = d.item()
            return 0.0 if isinstance(val, float) and not math.isfinite(val) else val
        if isinstance(d, dict):
            return {k: DatabaseStorage._convert_to_native(v) for k, v in d.items()}
        if isinstance(d, list):
            return [DatabaseStorage._convert_to_native(i) for i in d]
        return d

    def save_trade(self, trade_data):
        conn = None
        try:
            trade_data = self._convert_to_native(trade_data if isinstance(trade_data, dict) else {})
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO trades_history (
                        symbol, action, profit_percent, sell_reason, hours_held,
                        rsi, volume_ratio, trade_quality, profit, whale_confidence, atr_value, sentiment_score, 
                        panic_score, optimism_penalty, psychological_analysis, data, order_book_imbalance, 
                        spread_volatility, depth_at_1pct, market_impact_score, liquidity_trends, volatility_risk_score, 
                        correlation_risk, gap_risk_score, black_swan_probability, behavioral_risk, systemic_risk, 
                        profit_optimization_score, time_decay_signals, opportunity_cost_exits, market_condition_exits, 
                        harmonic_patterns_score, elliott_wave_signals, fractal_patterns, cycle_patterns, momentum_patterns, 
                        smart_money_ratio, exchange_whale_flows, statistical_outliers, pattern_anomalies, behavioral_anomalies, 
                        volume_anomalies, attention_mechanism_score, multi_scale_features, temporal_features, 
                        volume_trend_strength, volume_volatility, volume_momentum, volume_seasonality, volume_correlation, 
                        dynamic_consultant_weights, uncertainty_quantification, context_aware_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    trade_data.get('symbol'), trade_data.get('action'), trade_data.get('profit_percent'), trade_data.get('sell_reason'),
                    trade_data.get('hours_held'), trade_data.get('rsi', 0),
                    trade_data.get('volume_ratio', 0), trade_data.get('trade_quality', ''), trade_data.get('profit', 0),
                    trade_data.get('whale_confidence', 0), trade_data.get('atr_value', 0), trade_data.get('sentiment_score', 0),
                    trade_data.get('panic_score', 0), trade_data.get('optimism_penalty', 0), trade_data.get('psychological_analysis', ''),
                    self.json.dumps(trade_data, default=str), trade_data.get('order_book_imbalance', 0), trade_data.get('spread_volatility', 0),
                    trade_data.get('depth_at_1pct', 0), trade_data.get('market_impact_score', 0), trade_data.get('liquidity_trends', 0),
                    trade_data.get('volatility_risk_score', 0), trade_data.get('correlation_risk', 0), trade_data.get('gap_risk_score', 0),
                    trade_data.get('black_swan_probability', 0), trade_data.get('behavioral_risk', 0), trade_data.get('systemic_risk', 0),
                    trade_data.get('profit_optimization_score', 0), trade_data.get('time_decay_signals', 0), trade_data.get('opportunity_cost_exits', 0),
                    trade_data.get('market_condition_exits', 0), trade_data.get('harmonic_patterns_score', 0), trade_data.get('elliott_wave_signals', 0),
                    trade_data.get('fractal_patterns', 0), trade_data.get('cycle_patterns', 0), trade_data.get('momentum_patterns', 0),
                    trade_data.get('smart_money_ratio', 0), trade_data.get('exchange_whale_flows', 0), trade_data.get('statistical_outliers', 0),
                    trade_data.get('pattern_anomalies', 0), trade_data.get('behavioral_anomalies', 0), trade_data.get('volume_anomalies', 0),
                    trade_data.get('attention_mechanism_score', 0), trade_data.get('multi_scale_features', 0), trade_data.get('temporal_features', 0),
                    trade_data.get('volume_trend_strength', 0), trade_data.get('volume_volatility', 0), trade_data.get('volume_momentum', 0),
                    trade_data.get('volume_seasonality', 0), trade_data.get('volume_correlation', 0), trade_data.get('dynamic_consultant_weights', 0),
                    trade_data.get('uncertainty_quantification', 0), trade_data.get('context_aware_score', 0)
                ))
            conn.commit()
            return True
        except Exception as e:
            # ✅ logging للأخطاء الحرجة
            logging.error(f"DB save_trade error [{trade_data.get('symbol')}]: {e}", exc_info=True)
            print(f"❌ DB save trade error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)

    def load_trades(self, limit=None):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=self.RealDictCursor) as cursor:
                cursor.execute("SET TRANSACTION READ ONLY;")
                if limit: cursor.execute("SELECT * FROM trades_history ORDER BY timestamp DESC LIMIT %s", (limit,))
                else:     cursor.execute("SELECT * FROM trades_history ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    def delete_position(self, symbol):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM positions WHERE symbol = %s;", (symbol,))
            conn.commit()
            return True
        except Exception:
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)

    def save_positions_batch(self, positions_data):
        from psycopg2.extras import execute_batch
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                if not positions_data:
                    cursor.execute("TRUNCATE TABLE positions;")
                    conn.commit()
                    return

                valid_positions = [
                    self._convert_to_native(p.copy())
                    for p in positions_data
                    if isinstance(p, dict)
                ]

                if not valid_positions:
                    cursor.execute("TRUNCATE TABLE positions;")
                    conn.commit()
                    return

                for pos in valid_positions:
                    if 'data' in pos and isinstance(pos['data'], dict):
                        pos['data'] = self.json.dumps(pos['data'])

                sql_upsert = """
                    INSERT INTO positions (symbol, buy_price, amount, highest_price, tp_level_1, tp_level_2, buy_time, invested, data)
                    VALUES (%(symbol)s, %(buy_price)s, %(amount)s, %(highest_price)s, %(tp_level_1)s, %(tp_level_2)s, %(buy_time)s, %(invested)s, %(data)s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        buy_price     = EXCLUDED.buy_price,
                        amount        = EXCLUDED.amount,
                        highest_price = EXCLUDED.highest_price,
                        tp_level_1    = EXCLUDED.tp_level_1,
                        tp_level_2    = EXCLUDED.tp_level_2,
                        buy_time      = EXCLUDED.buy_time,
                        invested      = EXCLUDED.invested,
                        data          = EXCLUDED.data;
                """
                execute_batch(cursor, sql_upsert, valid_positions)
                symbols_in_batch = tuple(pos['symbol'] for pos in valid_positions)
                cursor.execute("DELETE FROM positions WHERE symbol NOT IN %s;", (symbols_in_batch,))
                conn.commit()

        except Exception as e:
            # ✅ logging للأخطاء الحرجة
            logging.error(f"DB save_positions_batch error: {e}", exc_info=True)
            print(f"❌ DB save_positions_batch error: {e}")
            if conn: conn.rollback()
        finally:
            if conn: self._put_conn(conn)

    def load_positions(self):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=self.RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM positions")
                rows = cursor.fetchall()
                result = {}
                for row in rows:
                    data_field = row.get('data')
                    if data_field:
                        try:
                            if isinstance(data_field, str):
                                data_dict = self.json.loads(data_field)
                            else:
                                data_dict = data_field
                        except Exception:
                            data_dict = {}
                    else:
                        data_dict = {}

                    result[row['symbol']] = {
                        'buy_price':           row['buy_price'],
                        'amount':              row['amount'],
                        'highest_price':       row['highest_price'],
                        'tp_level_1':          row['tp_level_1'],
                        'tp_level_2':          row['tp_level_2'],
                        'buy_time':            row['buy_time'].isoformat() if row['buy_time'] else None,
                        'invested':            row['invested'],
                        'data':                data_dict,
                        'stop_loss_threshold': data_dict.get('stop_loss_threshold')
                    }
                return result
        except Exception:
            return {}
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    def save_pattern(self, pattern_data):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO learned_patterns (pattern_type, data, success_rate) VALUES (%s, %s, %s)",
                    (pattern_data.get('type'), self.json.dumps(pattern_data), pattern_data.get('success_rate', 0.0))
                )
            conn.commit()
            return True
        except Exception:
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)

    def load_all_patterns(self):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=self.RealDictCursor) as cursor:
                cursor.execute("SET TRANSACTION READ ONLY;")
                cursor.execute("""
                    SELECT id, pattern_type,
                           (data->'features') as features,
                           (data->>'success_rate')::float as success_rate
                    FROM learned_patterns
                    ORDER BY last_updated DESC;
                """)
                return [
                    {
                        'id':           r['id'],
                        'pattern_type': r['pattern_type'],
                        'data':         {'features': r.get('features', {})},
                        'success_rate': r['success_rate']
                    }
                    for r in cursor.fetchall()
                ]
        except Exception:
            return []
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    def cleanup_old_data(self):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                queries = {
                    "trades (30d)":  ("trades_history",   "timestamp",    30),
                    "patterns (7d)": ("learned_patterns",  "last_updated", 7),
                    "symbol (180d)": ("symbol_memory",     "last_updated", 180)
                }
                for key, (table, date_col, days) in queries.items():
                    while True:
                        cursor.execute(
                            f"DELETE FROM {table} WHERE ctid IN "
                            f"(SELECT ctid FROM {table} WHERE {date_col} < NOW() - INTERVAL '{days} days' LIMIT 500);"
                        )
                        if cursor.rowcount == 0:
                            break
                        conn.commit()
                        time.sleep(0.1)
            return True
        except Exception:
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    def update_symbol_memory(self, symbol, profit, trade_quality, hours_held, rsi, volume_ratio,
                             sentiment=0, whale_conf=0, panic=0, optimism=0,
                             profit_loss_ratio=0, volume_trend=0, psychological_summary='Neutral',
                             courage_boost=0, time_memory_modifier=0, pattern_score=0, win_rate_boost=0):
        conn = None
        try:
            profit               = float(profit)
            hours_held           = float(hours_held)
            rsi                  = float(rsi)
            volume_ratio         = float(volume_ratio)
            sentiment            = float(sentiment)
            whale_conf           = float(whale_conf)
            panic                = float(panic)
            optimism             = float(optimism)
            profit_loss_ratio    = float(profit_loss_ratio)
            volume_trend         = float(volume_trend)
            courage_boost        = float(courage_boost)
            time_memory_modifier = float(time_memory_modifier)
            pattern_score        = float(pattern_score)
            win_rate_boost       = float(win_rate_boost)

            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO symbol_memory (
                        symbol, total_trades, win_count, loss_count, trap_count,
                        avg_profit, max_profit, min_profit, avg_hold_hours,
                        best_rsi, best_volume_ratio, last_trade_quality,
                        sentiment_avg, whale_confidence_avg, profit_loss_ratio, volume_trend,
                        panic_score_avg, optimism_penalty_avg, psychological_summary,
                        courage_boost, time_memory_modifier, pattern_score, win_rate_boost, last_updated
                    ) VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (symbol) DO UPDATE SET
                        total_trades          = symbol_memory.total_trades + 1,
                        win_count             = symbol_memory.win_count + EXCLUDED.win_count,
                        loss_count            = symbol_memory.loss_count + EXCLUDED.loss_count,
                        trap_count            = symbol_memory.trap_count + EXCLUDED.trap_count,
                        avg_profit            = (symbol_memory.avg_profit * symbol_memory.total_trades + EXCLUDED.avg_profit) / (symbol_memory.total_trades + 1),
                        max_profit            = GREATEST(symbol_memory.max_profit, EXCLUDED.max_profit),
                        min_profit            = LEAST(symbol_memory.min_profit, EXCLUDED.min_profit),
                        avg_hold_hours        = (symbol_memory.avg_hold_hours * symbol_memory.total_trades + EXCLUDED.avg_hold_hours) / (symbol_memory.total_trades + 1),
                        best_rsi              = EXCLUDED.best_rsi,
                        best_volume_ratio     = EXCLUDED.best_volume_ratio,
                        last_trade_quality    = EXCLUDED.last_trade_quality,
                        sentiment_avg         = (symbol_memory.sentiment_avg * symbol_memory.total_trades + EXCLUDED.sentiment_avg) / (symbol_memory.total_trades + 1),
                        whale_confidence_avg  = (symbol_memory.whale_confidence_avg * symbol_memory.total_trades + EXCLUDED.whale_confidence_avg) / (symbol_memory.total_trades + 1),
                        profit_loss_ratio     = EXCLUDED.profit_loss_ratio,
                        volume_trend          = EXCLUDED.volume_trend,
                        panic_score_avg       = (symbol_memory.panic_score_avg * symbol_memory.total_trades + EXCLUDED.panic_score_avg) / (symbol_memory.total_trades + 1),
                        optimism_penalty_avg  = (symbol_memory.optimism_penalty_avg * symbol_memory.total_trades + EXCLUDED.optimism_penalty_avg) / (symbol_memory.total_trades + 1),
                        psychological_summary = EXCLUDED.psychological_summary,
                        courage_boost         = EXCLUDED.courage_boost,
                        time_memory_modifier  = EXCLUDED.time_memory_modifier,
                        pattern_score         = EXCLUDED.pattern_score,
                        win_rate_boost        = EXCLUDED.win_rate_boost,
                        last_updated          = NOW();
                """, (
                    symbol,
                    1 if profit > 0 else 0,
                    1 if profit <= 0 else 0,
                    1 if trade_quality in ['TRAP', 'RISKY'] else 0,
                    profit, profit, profit,
                    hours_held, rsi, volume_ratio, trade_quality,
                    sentiment, whale_conf, profit_loss_ratio, volume_trend,
                    panic, optimism, psychological_summary,
                    courage_boost, time_memory_modifier, pattern_score, win_rate_boost
                ))
            conn.commit()
            return True
        except Exception as e:
            # ✅ logging للأخطاء الحرجة
            logging.error(f"DB update_symbol_memory error [{symbol}]: {e}", exc_info=True)
            print(f"❌ DB update symbol memory error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: self._put_conn(conn)

    def get_symbol_memory(self, symbol):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=self.RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM symbol_memory WHERE symbol = %s", (symbol,))
                row = cursor.fetchone()
                return dict(row) if row else {}
        except Exception:
            return {}
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)

    def load_model(self, name):
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT model_data FROM dl_models_v2 WHERE model_name = %s ORDER BY trained_at DESC LIMIT 1",
                    (name,)
                )
                result = cursor.fetchone()
                return bytes(result[0]) if result and result[0] is not None else None
        except Exception:
            return None
        finally:
            if conn:
                conn.rollback()
                self._put_conn(conn)