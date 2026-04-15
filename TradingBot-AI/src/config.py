"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_CONFIDENCE = 75  # تم تقليله للسماح بمزيد من الصفقات
MIN_SELL_CONFIDENCE = 85  # Wave Rider: خروج عند قمة الموجة 50-80% (تم التخفيف من 90)
MIN_CANDLE_SCORE = 75  # تم تقليله لجعل الدخول أسرع
MIN_VOLUME_RATIO = 1.5  # تم تقليله لاكتشاف بداية الموجات مبكراً
MACRO_CANDLE_THRESHOLD = 85  # حد الشموع لتجاوز حارس الماكرو (تم التخفيف من 95)
MAX_POSITIONS = 10  # صفقتين كحد أقصى لكل مجموعة (5+5)
TOTAL_COINS_TO_SCAN = 10

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
