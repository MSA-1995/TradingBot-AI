"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_CONFIDENCE = 60
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

VOLUME_SPIKE_FACTOR = 0.8 # Multiplier for detecting significant volume spikes (lowered for more opportunities)
PEAK_DROP_THRESHOLD = 1.5   # % هبوط من القمة يعتبر إشارة بيع (0.5% = وسط)
BOTTOM_BOUNCE_THRESHOLD = 2.0  # % ارتداد من القاع يعتبر إشارة شراء (0.5% = وسط)
REVERSAL_CANDLES = 10       # عدد الشموع للبحث عن القاع والقمة (أسرع)

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
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT',
    'DOGE/USDT', 'TRX/USDT', 'ADA/USDT', 'LINK/USDT', 'SUI/USDT',
    'PEPE/USDT', 'LTC/USDT', 'FET/USDT', 'BCH/USDT', 'AVAX/USDT',
    'WLD/USDT', 'NEAR/USDT', 'CHZ/USDT', 'ENA/USDT', 'DOT/USDT',
    'SHIB/USDT', 'FIL/USDT', 'BONK/USDT', 'UNI/USDT', 'AAVE/USDT',
    'RENDER/USDT', 'APT/USDT', 'TON/USDT', 'ARB/USDT', 'OP/USDT',
    'ATOM/USDT', 'XLM/USDT', 'ETC/USDT', 'GRT/USDT', 'SAND/USDT',
    'MANA/USDT', 'AXS/USDT', 'THETA/USDT', 'ICP/USDT', 'ALGO/USDT',
    'VET/USDT', 'FLOKI/USDT', 'WIF/USDT', 'CRV/USDT', 'SUSHI/USDT',
    '1INCH/USDT', 'COMP/USDT', 'YFI/USDT', 'SNX/USDT', 'GALA/USDT',
]

# عدد العملات النشطة للتداول (الأقوى من القائمة)
TOP_COINS_TO_TRADE = 10

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
