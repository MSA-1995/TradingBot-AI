"""
🔍 Enhanced Coin Scanner - Reads from Smart Scanner Database
Displays only active and open positions
"""

import time
import gc
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote
import os

class CoinScanner:
    def __init__(self, exchange, ai_brain=None, mtf_analyzer=None, risk_manager=None):
        self.exchange = exchange
        self.ai_brain = ai_brain
        self.mtf_analyzer = mtf_analyzer
        self.risk_manager = risk_manager
        
        # Database connection
        self.conn = None
        self._connect_db()
        
        # Fallback list (if database fails) - Empty, rely on scanner
        self.fallback_coins = []
        
        # Initialize with fallback
        self.top_coins = [(symbol, 0) for symbol in self.fallback_coins]
        self.last_scan = datetime.now()
        
        # Try to load from database
        self._load_from_database()
    
    def _connect_db(self):
        """Connect to PostgreSQL"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                print("⚠️ DATABASE_URL not found, using fallback coins")
                return
            
            parsed = urlparse(database_url)
            self.conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=unquote(parsed.password)
            )
            print("✅ Scanner connected to database")
        except Exception as e:
            print(f"⚠️ Scanner DB connection error: {e}")
            print("📋 Using fallback coin list")
    
    def _load_from_database(self):
        """Load top 50 coins from Smart Scanner database"""
        if not self.conn:
            return
        
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            
            # Get latest scan results
            cursor.execute("""
                SELECT coins FROM scanner_top_coins
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            cursor.close()
            
            if result and result['coins']:
                coins_data = result['coins']
                self.top_coins = [(coin['symbol'], coin['score']) for coin in coins_data]
                self.last_scan = datetime.now()
                print(f"🔍 Loaded {len(self.top_coins)} coins from Smart Scanner")
            else:
                print("⚠️ No scanner data found, using fallback")
        
        except Exception as e:
            print(f"⚠️ Scanner load error: {e}")
            print("📋 Using fallback coin list")
    
    def get_top_coins(self):
        """Get current top coins list"""
        # Reload from database every 10 minutes
        if (datetime.now() - self.last_scan).seconds > 600:
            self._load_from_database()
        
        return self.top_coins.copy()
    
    def get_scan_status(self):
        """Get scanner status"""
        return {
            'last_scan': self.last_scan,
            'top_coins_count': len(self.top_coins),
            'using_database': self.conn is not None
        }

