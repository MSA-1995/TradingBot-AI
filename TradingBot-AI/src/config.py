"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_SELL_CONFIDENCE = 85  # Peak/Valley Catcher: خروج عند قمة مكتشفة
MIN_BUY_CONFIDENCE = 55   # حد الثقة للشراء (reversal analysis)
MACRO_CANDLE_THRESHOLD = 85  # حد الشموع لتجاوز حارس الماكرو
MAX_POSITIONS = 10  # صفقتين كحد أقصى لكل مجموعة (5+5)
TOTAL_COINS_TO_SCAN = 10

# =====================================================================
# 👑 Meta Decision Thresholds (الأرقام المعتدلة - النظام الجديد)
# =====================================================================
META_BUY_INTELLIGENCE = 50      # حد الذكاء الكلي للشراء (متوازن)
META_BUY_WHALE = 50             # حد نشاط الحيتان (متوازن)
META_BUY_TREND = 55             # حد بداية الاتجاه (متوازن)
META_BUY_VOLUME = 50            # حد زخم الحجم (متوازن)
META_BUY_PATTERN = 50           # حد قوة النمط (متوازن)
META_BUY_CANDLE = 70            # حد أنماط الشموع (متوازن)
META_BUY_SUPPORT = 50           # حد قوة الدعم (متوازن)
META_BUY_HISTORY = 55           # حد الذاكرة التاريخية (متوازن)
META_BUY_CONSENSUS = 50         # حد الإجماع - 3+ مستشارين (متوازن)
META_DISPLAY_THRESHOLD = 40     # حد عرض العملات (معتدل)

# Capital Management
MAX_CAPITAL = 3000
PROFIT_RESERVE = True

# Trade Amount Limits
MIN_TRADE_AMOUNT = 12
MAX_TRADE_AMOUNT = 30  # متوازن للمخاطر والفرص

# Minimum Profit Threshold for Selling
MIN_SELL_PROFIT = 0.5  # % - لا يبيع إلا إذا الربح >= 0.5%

# Price Filters for Peak/Valley Catcher - REMOVED
# MIN_ENTRY_PRICE = 12.0  # أقل سعر للدخول (دولار) - REMOVED
# MAX_ENTRY_PRICE = 25.0  # أعلى سعر للدخول (دولار) - REMOVED

# Risk Management
# ✅ الحماية الآن عبر:
# 1. نظام الوقف الزاحف الواسع (Wide Trailing Stop) بمساحة تنفس 10-15%
# 2. مستشار الاتجاه الماكرو (Macro Trend Advisor) للفلترة اليومية

PEAK_DROP_THRESHOLD = 5.0   # Peak/Valley Catcher: مساحة تنفس للقمم المكتشفة
BOTTOM_BOUNCE_THRESHOLD = 2.0  # Peak/Valley Catcher: ارتداد من القاع
REVERSAL_CANDLES = 30       # Peak/Valley Catcher: رؤية الأنماط الكاملة
VOLUME_SPIKE_FACTOR = 1.5   # معامل انفجار الحجم للأنماط

# Performance & Memory Tuning
BATCH_SIZE = 20          # معالجة 20 عملة في نفس الوقت
MAX_WORKERS = 20         # 20 عامل لـ 20 عملة

# 🛡️ Advanced Institutional Settings
CROSS_CHECK_TOLERANCE = 0.8  # أقصى انحراف مسموح به بين السعر المحلي والعالمي (0.8%)
WHALE_FINGERPRINT_LIMIT = 100 # عدد أحداث الحيتان التي يتذكرها الملك لكل عملة

# Memory Management
MEMORY_CLEANUP_INTERVAL = 120  # Interval in seconds to run the memory cleaner (e.g., 120 = 2 minutes)
MEMORY_USAGE_THRESHOLD = 80    # Percentage of RAM usage that triggers an aggressive cleanup

# Timing
LOOP_SLEEP = 2
REPORT_INTERVAL = 1800

# قائمة العملات المضمونة من Binance (أقوى 20 عملة)
# المجموعة الأولى: The Golden Five (القيادية)
# المجموعة الثانية: Layer 1 & DeFi Leaders
# المجموعة الثالثة: High Cap & Emerging
# المجموعة الرابعة: Stable & Promising
SYMBOLS = [
    # Golden Five
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
    # Layer 1 & DeFi Leaders
    'ADA/USDT', 'AVAX/USDT', 'UNI/USDT', 'DOT/USDT', 'LINK/USDT',
    # High Cap & Emerging
    'LTC/USDT', 'ALGO/USDT', 'VET/USDT', 'ICP/USDT', 'FIL/USDT',
    # Stable & Promising
    'TRX/USDT', 'ETC/USDT', 'XLM/USDT', 'THETA/USDT', 'HBAR/USDT'
]

# عدد العملات النشطة للتداول
TOP_COINS_TO_TRADE = 20

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
