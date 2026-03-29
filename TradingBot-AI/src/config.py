"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_CONFIDENCE = 45
MAX_POSITIONS = 50  # الحد الأقصى للصفقات المفتوحة (كل العملات)
TOTAL_COINS_TO_SCAN = 50

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

VOLUME_SPIKE_FACTOR = 1.5 # Multiplier for detecting significant volume spikes (e.g., 2.0 = 100% increase, balanced)
PEAK_DROP_THRESHOLD = 2.0   # % هبوط من القمة يعتبر إشارة بيع (0.5% = وسط)
BOTTOM_BOUNCE_THRESHOLD = 0.8  # % ارتداد من القاع يعتبر إشارة شراء (0.5% = وسط)
REVERSAL_CANDLES = 30       # عدد الشموع للبحث عن القاع والقمة

# Performance & Memory Tuning
BATCH_SIZE = 10          # Number of symbols to process in a single batch (Increased to match DB pool)
MAX_WORKERS = 10          # Max number of threads for parallel processing (Matched to DB pool size)

# Memory Management
MEMORY_CLEANUP_INTERVAL = 120  # Interval in seconds to run the memory cleaner (e.g., 120 = 2 minutes)
MEMORY_USAGE_THRESHOLD = 80    # Percentage of RAM usage that triggers an aggressive cleanup

# Timing
LOOP_SLEEP = 2  # تحسين السرعة: من 5 إلى 2 ثانية (هدف: 20 ثانية)
REPORT_INTERVAL = 1800  # بالثواني، كل 30 دقيقة

# Notifications
# Choose where to store the Discord status message ID: 'database' or 'file'
# 'database' is recommended for production (uses bot_settings table)
# 'file' is for local/testing (uses data/bot_status_message_id.txt)
STATUS_STORAGE_METHOD = 'file' # or 'database'

# قائمة العملات الثابتة (Top 50 by Market Cap - March 2026)
SYMBOLS = [
    # Top 10 - Giants
    'BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'BNB/USDT', 'SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'TRX/USDT', 'AVAX/USDT', 'TON/USDT', 
    # 11-20 - Major Alts
    'LINK/USDT', 'DOT/USDT', 'BCH/USDT', 'NEAR/USDT', 'LTC/USDT',
    'UNI/USDT', 'ATOM/USDT', 'XLM/USDT', 'HBAR/USDT', 'ICP/USDT',
    # 21-30 - Established Coins
    'XTZ/USDT', 'ETC/USDT', 'FIL/USDT', 'VET/USDT', 'ALGO/USDT',
    'MANA/USDT', 'SAND/USDT', 'AXS/USDT', 'AAVE/USDT', 'IOTA/USDT',
    # 31-40 - Popular Coins
    'NEO/USDT', 'THETA/USDT', 'DASH/USDT', 'GRT/USDT', 'RUNE/USDT',
    'EGLD/USDT', 'CHZ/USDT', 'GALA/USDT', 'ENJ/USDT', 'ZIL/USDT',
    # 41-50 - DeFi & Others
    'COMP/USDT', 'SNX/USDT', 'SUSHI/USDT', 'YFI/USDT', 'CRV/USDT',
    '1INCH/USDT', 'ZEC/USDT', 'QTUM/USDT', 'KSM/USDT', 'SHIB/USDT',
]

# عدد العملات النشطة للتداول (الأقوى من القائمة)
TOP_COINS_TO_TRADE = 10

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
