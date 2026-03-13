"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters
MIN_CONFIDENCE = 55  # Changed from 60 - more aggressive
MAX_POSITIONS = 999

# Capital Management
MAX_CAPITAL = 300  # الحد الأقصى لرأس المال المستخدم ($200-$300)
PROFIT_RESERVE = True  # حفظ الأرباح (لا يتداول فيها)

# Trade Amount Limits
MIN_TRADE_AMOUNT = 12  # Minimum trade size (safe for Binance $10 limit)
MAX_TRADE_AMOUNT = 30  # Maximum trade size

# Legacy (kept for compatibility)
BASE_AMOUNT = 12
BOOST_AMOUNT = 24

# Risk Management
STOP_LOSS_PERCENT = 2.0
TAKE_PROFIT_PERCENT = 1.0
TRAILING_STOP_PERCENT = 2.0

# Technical Indicators
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Volume
MIN_VOLUME_RATIO = 1.0

# Timing
LOOP_SLEEP = 10  # seconds
REPORT_INTERVAL = 30  # minutes

# Supported Coins (Legacy - for fallback only)
# النظام الجديد يستخدم Dynamic Scanner (995 عملة)
# هذي القائمة تُستخدم فقط كـfallback إذا Scanner فشل
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT',
    'ADA/USDT', 'AVAX/USDT', 'LINK/USDT',
    'DOT/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT',
    'XRP/USDT', 'DOGE/USDT', 'SHIB/USDT', 'TRX/USDT',
    'APT/USDT', 'ARB/USDT', 'OP/USDT', 'FIL/USDT', 'NEAR/USDT'
]

# Initialize symbol data structure
def init_symbols():
    """Initialize symbols dictionary (dynamic)"""
    # البداية بقائمة فارغة - سيتم ملؤها ديناميكياً
    return {}
