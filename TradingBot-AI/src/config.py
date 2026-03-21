"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters
MIN_CONFIDENCE = 55
MAX_POSITIONS = 50  # الحد الأقصى للصفقات المفتوحة (كل العملات)
TOTAL_COINS_TO_SCAN = 50

# Capital Management
MAX_CAPITAL = 300
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

# Timing
LOOP_SLEEP = 2  # تحسين السرعة: من 5 إلى 2 ثانية (هدف: 20 ثانية)
REPORT_INTERVAL = 30

# قائمة العملات الثابتة (Top 50 by Market Cap - March 2026)
SYMBOLS = [
    # Top 10 - Giants
    'BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'BNB/USDT', 'SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'TRX/USDT', 'MATIC/USDT', 'TON/USDT', # AVAX -> MATIC
    # 11-20 - Major Alts
    'LINK/USDT', 'DOT/USDT', 'BCH/USDT', 'NEAR/USDT', 'LTC/USDT',
    'UNI/USDT', 'ATOM/USDT', 'XLM/USDT', 'HBAR/USDT', 'ICP/USDT',
    # 21-30 - Strong Layer 1 & Layer 2
    'APT/USDT', 'ARB/USDT', 'OP/USDT', 'SUI/USDT', 'INJ/USDT',
    'TIA/USDT', 'SEI/USDT', 'POL/USDT', 'ALGO/USDT', 'VET/USDT',
    # 31-40 - DeFi & Infrastructure
    'AAVE/USDT', 'FIL/USDT', 'RENDER/USDT', 'FTM/USDT', 'RUNE/USDT', # GRT -> FTM
    'LDO/USDT', 'CRV/USDT', 'SNX/USDT', 'COMP/USDT', 'ETC/USDT', # SUSHI -> ETC
    # 41-50 - Meme, Gaming & Others
    'SHIB/USDT', 'PEPE/USDT', 'WIF/USDT', 'FLOKI/USDT', 'BONK/USDT',
    'IMX/USDT', 'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'GALA/USDT',
]

# عدد العملات النشطة للتداول (الأقوى من القائمة)
TOP_COINS_TO_TRADE = 10

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
