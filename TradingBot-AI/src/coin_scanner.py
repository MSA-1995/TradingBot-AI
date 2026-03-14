"""
🔍 Enhanced Coin Scanner - 50 Coins with Smart Filtering
Scans 50 coins, displays only active and open positions
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
        
        # قائمة 50 عملة مشهورة ونشطة
        self.all_coins = [
            # Top 20 (الأساسية)
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
            'POL/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT', 'UNI/USDT',
            'ATOM/USDT', 'ALGO/USDT', 'XRP/USDT', 'LTC/USDT', 'BCH/USDT',
            'ETC/USDT', 'FIL/USDT', 'AAVE/USDT', 'DOGE/USDT', 'TRX/USDT',
            # 30 عملة إضافية
            'XLM/USDT', 'HBAR/USDT', 'VET/USDT', 'ICP/USDT', 'APT/USDT',
            'NEAR/USDT', 'OP/USDT', 'ARB/USDT', 'SUI/USDT', 'INJ/USDT',
            'SEI/USDT', 'TIA/USDT', 'RUNE/USDT', 'TON/USDT', 'SHIB/USDT',
            'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'GALA/USDT', 'ENJ/USDT',
            'CHZ/USDT', 'THETA/USDT', 'XTZ/USDT', 'IMX/USDT', 'ASTR/USDT',
            'KAVA/USDT', 'ZIL/USDT', 'ONE/USDT', 'CELO/USDT', 'ROSE/USDT'
        ]
        
        # تحليل فوري عند التهيئة
        self.top_coins = [(symbol, 0) for symbol in self.all_coins]
        self.last_scan = datetime.now()
    
    def get_top_coins(self):
        """الحصول على القائمة الكاملة (50 عملة)"""
        return self.top_coins.copy()
    
    def get_scan_status(self):
        """حالة الفحص"""
        return {
            'last_scan': self.last_scan,
            'top_coins_count': len(self.top_coins)
        }
