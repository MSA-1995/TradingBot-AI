"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_SELL_CONFIDENCE = 85  # Wave Rider: خروج عند قمة الموجة 50-80%
MIN_BUY_CONFIDENCE = 55   # حد الثقة للشراء (reversal analysis)
MACRO_CANDLE_THRESHOLD = 85  # حد الشموع لتجاوز حارس الماكرو
MAX_POSITIONS = 10  # صفقتين كحد أقصى لكل مجموعة (5+5)
TOTAL_COINS_TO_SCAN = 10

# =====================================================================
# 👑 Meta Decision Thresholds (الأرقام المعتدلة - النظام الجديد)
# =====================================================================
META_BUY_INTELLIGENCE = 55      # حد الذكاء الكلي للشراء (معتدل)
META_BUY_WHALE = 45             # حد نشاط الحيتان (معتدل)
META_BUY_TREND = 55             # حد بداية الاتجاه (معتدل)
META_BUY_VOLUME = 45            # حد زخم الحجم (معتدل)
META_BUY_PATTERN = 45           # حد قوة النمط (معتدل)
META_BUY_CANDLE = 70            # 🕯️ حد أنماط الشموع - candle_expert (مهم!)
META_BUY_SUPPORT = 45           # حد قوة الدعم (معتدل)
META_BUY_HISTORY = 55           # حد الذاكرة التاريخية (معتدل)
META_BUY_CONSENSUS = 50         # حد الإجماع - 3+ مستشارين (معتدل)
META_DISPLAY_THRESHOLD = 35     # حد عرض العملات (معتدل)

# Capital Management
MAX_CAPITAL = 3000
PROFIT_RESERVE = True

# Trade Amount Limits
MIN_TRADE_AMOUNT = 12
MAX_TRADE_AMOUNT = 700  # Wave Rider: حجم أكبر للموجات الطويلة

# Risk Management
# ✅ الحماية الآن عبر:
# 1. نظام الوقف الزاحف الواسع (Wide Trailing Stop) بمساحة تنفس 10-15%
# 2. مستشار الاتجاه الماكرو (Macro Trend Advisor) للفلترة اليومية

PEAK_DROP_THRESHOLD = 5.0   # Wave Rider: مساحة تنفس واسعة للموجات الكبيرة
BOTTOM_BOUNCE_THRESHOLD = 2.0  # Wave Rider: ارتداد قوي من القاع
REVERSAL_CANDLES = 30       # Wave Rider: رؤية هيكل الموجة الكاملة
VOLUME_SPIKE_FACTOR = 1.5   # معامل انفجار الحجم للأنماط

# Performance & Memory Tuning
BATCH_SIZE = 10          # معالجة 10 عملات في نفس الوقت
MAX_WORKERS = 10         # 10 عمال لـ 10 عملات

# 🛡️ Advanced Institutional Settings
CROSS_CHECK_TOLERANCE = 0.8  # أقصى انحراف مسموح به بين السعر المحلي والعالمي (0.8%)
WHALE_FINGERPRINT_LIMIT = 100 # عدد أحداث الحيتان التي يتذكرها الملك لكل عملة

# Memory Management
MEMORY_CLEANUP_INTERVAL = 120  # Interval in seconds to run the memory cleaner (e.g., 120 = 2 minutes)
MEMORY_USAGE_THRESHOLD = 80    # Percentage of RAM usage that triggers an aggressive cleanup

# Timing
LOOP_SLEEP = 2
REPORT_INTERVAL = 1800

# قائمة العملات المضمونة من Binance (أقوى 10 عملات)
# المجموعة الأولى: The Golden Five (القيادية)
# المجموعة الثانية: Layer 1 & DeFi Leaders
SYMBOLS = [
    # Golden Five
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
    # Layer 1 & DeFi Leaders
    'ADA/USDT', 'AVAX/USDT', 'UNI/USDT', 'DOT/USDT', 'LINK/USDT'
]

# عدد العملات النشطة للتداول
TOP_COINS_TO_TRADE = 10

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
