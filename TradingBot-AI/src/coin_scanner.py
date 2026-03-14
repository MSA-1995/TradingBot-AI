"""
🔍 Simple Coin Scanner - Top 20 Popular Coins
Fast and reliable analysis of 20 most popular cryptocurrencies
"""

import time
import gc
from datetime import datetime

class CoinScanner:
    def __init__(self, exchange, ai_brain=None, mtf_analyzer=None, risk_manager=None):
        self.exchange = exchange
        self.ai_brain = ai_brain
        self.mtf_analyzer = mtf_analyzer
        self.risk_manager = risk_manager
        
        # قائمة العملات المشهورة (20 عملة)
        self.popular_coins = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
            'POL/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT', 'UNI/USDT',
            'ATOM/USDT', 'ALGO/USDT', 'XRP/USDT', 'LTC/USDT', 'BCH/USDT',
            'ETC/USDT', 'FIL/USDT', 'AAVE/USDT', 'DOGE/USDT', 'TRX/USDT'
        ]
        
        # تحليل فوري عند التهيئة
        self.top_coins = [(symbol, 0) for symbol in self.popular_coins]
        self.last_scan = datetime.now()
    
    def get_top_coins(self):
        """الحصول على القائمة الحالية"""
        return self.top_coins.copy()
    
    def get_scan_status(self):
        """حالة الفحص"""
        return {
            'last_scan': self.last_scan,
            'top_coins_count': len(self.top_coins)
        }
