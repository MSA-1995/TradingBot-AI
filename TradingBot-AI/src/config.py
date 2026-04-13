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

VOLUME_SPIKE_FACTOR = 1.5   # رفع الحساسية لاستبعاد الضوضاء واستهداف سيولة المؤسسات
PEAK_DROP_THRESHOLD = 2.5   # توسيع النطاق قليلاً لتجنب الخروج المبكر في الموجات الكبرى
BOTTOM_BOUNCE_THRESHOLD = 2.0  
REVERSAL_CANDLES = 20       # رؤية هيكل تجميع أو تصريف أوضح (100 دقيقة بدلاً من 75)

# Performance & Memory Tuning
BATCH_SIZE = 5           # تقليل الحجم لضمان عدم تجاوز الرام في المعالجة المتوازية
MAX_WORKERS = 5          # 5 عمال كافية جداً لـ 5 عملات وتوفر الكثير من الرام

# 🛡️ Advanced Institutional Settings
CROSS_CHECK_TOLERANCE = 0.8  # أقصى انحراف مسموح به بين السعر المحلي والعالمي (0.8%)
WHALE_FINGERPRINT_LIMIT = 100 # عدد أحداث الحيتان التي يتذكرها الملك لكل عملة

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
