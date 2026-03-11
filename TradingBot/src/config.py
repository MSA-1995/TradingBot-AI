"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters
MIN_CONFIDENCE = 60
MAX_POSITIONS = 20
BASE_AMOUNT = 10
BOOST_AMOUNT = 20

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

# Supported Coins
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT',
    'ADA/USDT', 'AVAX/USDT', 'LINK/USDT',
    'DOT/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT',
    'XRP/USDT', 'DOGE/USDT', 'SHIB/USDT', 'TRX/USDT',
    'APT/USDT', 'ARB/USDT', 'OP/USDT', 'FIL/USDT', 'NEAR/USDT'
]

# Initialize symbol data structure
def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
