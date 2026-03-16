"""
🧠 Deep Learning Client - للبوت الرئيسي
يقرأ توقعات الديب ليرننج من قاعدة البيانات
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

class DeepLearningClient:
    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = None
        self._db_params = None
        self._connect_db()
        print("🧠 Deep Learning Client initialized")
    
    def _connect_db(self):
        """Connect to PostgreSQL"""
        try:
            parsed = urlparse(self.database_url)
            self._db_params = {
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path[1:],
                'user': parsed.username,
                'password': unquote(parsed.password)
            }
            self.conn = psycopg2.connect(**self._db_params)
        except Exception as e:
            print(f"⚠️ DL Client DB error: {e}")
            self.conn = None
    
    def _get_conn(self):
        """Get valid connection - reconnect if closed"""
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(**self._db_params)
        except Exception as e:
            print(f"⚠️ DL Client reconnect error: {e}")
        return self.conn
    
    def get_dl_boost(self, features):
        """
        الحصول على Boost من الديب ليرننج
        features: dict with keys: rsi, macd, volume_ratio, price_momentum, confidence, etc.
        Returns: confidence_boost (int) to add to base confidence
        """
        try:
            conn = self._get_conn()
            if not conn:
                return 0
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # قراءة آخر توقع من الديب ليرننج
            cursor.execute("""
                SELECT predictions, model_accuracy
                FROM dl_predictions
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                return 0
            
            accuracy = result.get('model_accuracy', 0)
            
            # حساب Boost بناءً على دقة النموذج
            if accuracy >= 0.70:  # 70%+
                boost = 5
            elif accuracy >= 0.65:  # 65-70%
                boost = 3
            elif accuracy >= 0.60:  # 60-65%
                boost = 2
            else:
                boost = 0
            
            return boost
        
        except Exception as e:
            print(f"⚠️ DL boost error: {e}")
            return 0
    
    def get_advisor_knowledge(self, advisor_name):
        """
        الحصول على معرفة مستشار معين
        advisor_name: 'ai_brain', 'exit_strategy', 'pattern_recognition', 'coin_ranking'
        """
        try:
            conn = self._get_conn()
            if not conn:
                return None
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT knowledge
                FROM dl_advisors_knowledge
                WHERE advisor_name = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (advisor_name,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result.get('knowledge')
            return None
        
        except Exception as e:
            print(f"⚠️ Advisor knowledge error: {e}")
            return None
    
    def get_coin_ranking(self, symbol):
        """الحصول على تقييم عملة من الديب ليرننج"""
        try:
            knowledge = self.get_advisor_knowledge('coin_ranking')
            if not knowledge or symbol not in knowledge:
                return None
            
            coin_data = knowledge[symbol]
            trades = coin_data.get('trades', 0)
            total_profit = coin_data.get('total_profit', 0)
            
            if trades == 0:
                return None
            
            avg_profit = total_profit / trades
            
            return {
                'trades': trades,
                'avg_profit': avg_profit,
                'total_profit': total_profit,
                'score': int(avg_profit * 10)  # تحويل لنقاط
            }
        
        except Exception as e:
            print(f"⚠️ Coin ranking error: {e}")
            return None
    
    def is_available(self):
        """فحص إذا الديب ليرننج متوفر"""
        try:
            conn = self._get_conn()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'dl_predictions'
                )
            """)
            exists = cursor.fetchone()[0]
            cursor.close()
            
            return exists
        except:
            return False
