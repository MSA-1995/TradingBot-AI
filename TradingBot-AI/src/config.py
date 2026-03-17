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
STOP_LOSS_PERCENT = 2.0
TAKE_PROFIT_PERCENT = 1.0

# Timing
LOOP_SLEEP = 2  # تحسين السرعة: من 5 إلى 2 ثانية (هدف: 20 ثانية)
REPORT_INTERVAL = 30

# قائمة العملات الثابتة (50 عملة مشهورة)
SYMBOLS = [
    # كبار العملات
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
    'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'TRX/USDT', 'DOT/USDT',
    # DeFi
    'LINK/USDT', 'UNI/USDT', 'AAVE/USDT', 'CRV/USDT', 'LDO/USDT',
    'SUSHI/USDT', 'COMP/USDT', 'SNX/USDT', 'ZRX/USDT', '1INCH/USDT',
    # Layer 2
    'ARB/USDT', 'OP/USDT', 'POL/USDT', 'IMX/USDT', 'LRC/USDT',
    # Layer 1
    'ATOM/USDT', 'NEAR/USDT', 'APT/USDT', 'SUI/USDT', 'SEI/USDT',
    'INJ/USDT', 'TIA/USDT', 'S/USDT', 'ALGO/USDT', 'EGLD/USDT',
    # Meme & Others
    'SHIB/USDT', 'PEPE/USDT', 'FLOKI/USDT', 'WIF/USDT', 'BONK/USDT',
    # Exchange & Infra
    'LTC/USDT', 'BCH/USDT', 'FIL/USDT', 'ICP/USDT', 'RENDER/USDT',
    # Gaming & NFT
    'AXS/USDT', 'SAND/USDT', 'MANA/USDT', 'ENJ/USDT', 'GALA/USDT',
]

# عدد العملات النشطة للتداول (الأقوى من القائمة)
TOP_COINS_TO_TRADE = 10

def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}
