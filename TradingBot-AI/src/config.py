"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_CONFIDENCE = 75  # رفع الصرامة: لا دخول إلا بإشارة قوية جداً (قاع دورة)
MIN_SELL_CONFIDENCE = 85  # لا خروج إلا عند قمة حقيقية أو كسر تريند ماكرو
MAX_POSITIONS = 5  # صفقة واحدة لكل عملة قيادية
TOTAL_COINS_TO_SCAN = 5

# Capital Management
MAX_CAPITAL = 3000
PROFIT_RESERVE = True

# Trade Amount Limits
MIN_TRADE_AMOUNT = 12
MAX_TRADE_AMOUNT = 600  # رفع الحد الأقصى لاستغلال رأس المال (3000$ / 5 عملات)

# Risk Management
# ✅ الحماية الآن عبر:
# 1. نظام الوقف الزاحف الواسع (Wide Trailing Stop) بمساحة تنفس 10-15%
# 2. مستشار الاتجاه الماكرو (Macro Trend Advisor) للفلترة اليومية

VOLUME_SPIKE_FACTOR = 1.0 
PEAK_DROP_THRESHOLD = 2.0   
BOTTOM_BOUNCE_THRESHOLD = 2.0  
REVERSAL_CANDLES = 15       # زيادة المدى لـ 15 شمعة لاكتشاف تجميع القاع الحقيقي للدورة

# Performance & Memory Tuning
BATCH_SIZE = 10          # Number of symbols to process in a single batch (Increased to match DB pool)
MAX_WORKERS = 10          # Max number of threads for parallel processing (Matched to DB pool size)

# Memory Management
MEMORY_CLEANUP_INTERVAL = 120  # Interval in seconds to run the memory cleaner (e.g., 120 = 2 minutes)
MEMORY_USAGE_THRESHOLD = 80    # Percentage of RAM usage that triggers an aggressive cleanup

# Timing
LOOP_SLEEP = 2
REPORT_INTERVAL = 1800

# قائمة العملات المضمونة من Binance (أقوى 50 عملة بالحجم)
# تم الحذف والاكتفاء بالخمسة الكبار (Golden Five)
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT']

# عدد العملات النشطة للتداول (الأقوى من القائمة)
TOP_COINS_TO_TRADE = 5

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
