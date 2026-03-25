"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters
MIN_CONFIDENCE = 55
MAX_POSITIONS = 20  # الحد الأقصى للصفقات المفتوحة (كل العملات)
TOTAL_COINS_TO_SCAN = 20

# Capital Management
MAX_CAPITAL = 1000
PROFIT_RESERVE = True

# Trade Amount Limits
MIN_TRADE_AMOUNT = 12
MAX_TRADE_AMOUNT = 30

# Legacy (kept for compatibility)
BASE_AMOUNT = 12

# Risk Management
# Stop Loss removed - الحماية عبر:
# 1. تصويت المستشارين (-0.8% إلى -1.2%)
# 2. Trailing Stop -2% من أعلى سعر (جدار نهائي)

# Dynamic Trailing Stop-Loss
USE_DYNAMIC_TRAILING_STOP = True  # Master switch for the feature
ATR_PERIOD = 14  # Period for ATR calculation
ATR_MULTIPLIER = 2.0  # Multiplier for ATR to set stop-loss. Higher value = wider stop-loss

# Performance & Memory Tuning
BATCH_SIZE = 20          # Number of symbols to process in a single batch to conserve memory
MAX_WORKERS = 20         # Max number of threads for parallel processing, should be <= BATCH_SIZE

# Memory Management
MEMORY_CLEANUP_INTERVAL = 120  # Interval in seconds to run the memory cleaner (e.g., 120 = 2 minutes)
MEMORY_USAGE_THRESHOLD = 80    # Percentage of RAM usage that triggers an aggressive cleanup

# Timing
LOOP_SLEEP = 2  # تحسين السرعة: من 5 إلى 2 ثانية (هدف: 20 ثانية)
REPORT_INTERVAL = 30

# Notifications
# Choose where to store the Discord status message ID: 'database' or 'file'
# 'database' is recommended for production (uses bot_settings table)
# 'file' is for local/testing (uses data/bot_status_message_id.txt)
STATUS_STORAGE_METHOD = 'file' # or 'database'

# قائمة العملات الثابتة (Top 20 by Market Cap - March 2026)
SYMBOLS = [
    # Top 10 - Giants
    'BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'BNB/USDT', 'SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'TRX/USDT', 'AVAX/USDT', 'TON/USDT', 
    # 11-20 - Major Alts
    'LINK/USDT', 'DOT/USDT', 'BCH/USDT', 'NEAR/USDT', 'LTC/USDT',
    'UNI/USDT', 'ATOM/USDT', 'XLM/USDT', 'HBAR/USDT', 'ICP/USDT',
]

# عدد العملات النشطة للتداول (الأقوى من القائمة)
TOP_COINS_TO_TRADE = 10

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
