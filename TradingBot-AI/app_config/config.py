"""
⚙️ Configuration Module
All bot settings and constants
"""

# Trading Parameters

MIN_SELL_CONFIDENCE = 60


MIN_BUY_CONFIDENCE = 60
MACRO_CANDLE_THRESHOLD = 85
MAX_POSITIONS = 20
TOTAL_COINS_TO_SCAN = 20

# =====================================================================
# 👑 Meta Decision Thresholds
# =====================================================================
META_BUY_INTELLIGENCE = 50
META_BUY_WHALE = 50
META_BUY_TREND = 55
META_BUY_VOLUME = 50
META_BUY_PATTERN = 50
META_BUY_CANDLE = 70
META_BUY_SUPPORT = 50
META_BUY_HISTORY = 55
META_BUY_CONSENSUS = 50
META_DISPLAY_THRESHOLD = 40 #الحد الادنى لنقاط عرض العملة الضعيفة

# Capital Management
MAX_CAPITAL = 1000
PROFIT_RESERVE = True

# Trade Amount Limits
MIN_TRADE_AMOUNT = 12
MAX_TRADE_AMOUNT = 30


# Risk Management
PEAK_DROP_THRESHOLD = 5.0
BOTTOM_BOUNCE_THRESHOLD = 2.0
REVERSAL_CANDLES = 30
VOLUME_SPIKE_FACTOR = 1.3

# Performance & Memory Tuning
BATCH_SIZE = 10
MAX_WORKERS = 8


# Memory Management
MEMORY_CLEANUP_INTERVAL = 60
MEMORY_USAGE_THRESHOLD = 70

# Timing
LOOP_SLEEP = 2
REPORT_INTERVAL = 3600     #تقرير الديسكورد 3600 ثانيه = 1 ساعة 

# =====================================================================
# 🌐 Market Regime Sell Modes
# =====================================================================

SELL_MODE_NORMAL = {
    'mode': 'NORMAL',
    'stability_minutes': 0,
    'min_sell_points': 65,     # نقاط البيع - سوق صاعد (بعد خصم الماكرو -10 = 72 فعلي)
    'stop_loss_mult': 1.2,
    'label': '🟢 Normal',
}

SELL_MODE_CAUTIOUS = {
    'mode': 'CAUTIOUS',
    'stability_minutes': 0,    # AI يقرر بدون وقت ثابت
    'min_sell_points': 60,     # نقاط البيع - سوق محايد
    'stop_loss_mult': 0.8,
    'label': '⚪ Cautious',
}

SELL_MODE_SNIPER_EXIT = {
    'mode': 'SNIPER_EXIT',
    'stability_minutes': 0,
    'min_sell_points': 50,     # نقاط البيع - سوق هابط
    'stop_loss_mult': 0.5,
    'label': '🔴 Sniper Exit',
}

# =====================================================================
# 🌐 Market Regime Buy Modes
# =====================================================================

BUY_MODE_AGGRESSIVE = {
    'mode': 'AGGRESSIVE',
    'min_confidence': 60,
    'max_amount': 30,
    'max_positions': 12,
    'label': '🟢 Aggressive',
}

BUY_MODE_BALANCED = {
    'mode': 'BALANCED',
    'min_confidence': 65,
    'max_amount': 20,
    'max_positions': 12,
    'label': '⚪ Balanced',
}

BUY_MODE_CAUTIOUS = BUY_MODE_BALANCED  # alias

BUY_MODE_NO_BUY = {
    'mode': 'NO_BUY',
    'min_confidence': 70,
    'max_amount': 12,
    'max_positions': 12,
    'label': '🔴 High Confidence Only',
}

# =====================================================================
# 🌐 Macro Trend Voting Points
# Current macro regime -> points
# =====================================================================

MACRO_BUY_POINTS = {
    'BULL': +10,
    'NEUT': 0,
    'BEAR': -10,
}

MACRO_SELL_POINTS = {
    'BULL': -5,   # خفيف - نبيع في القمة حتى في Bull
    'NEUT': +5,
    'BEAR': +10,
}

# =====================================================================
# 🌐 Market Regime Decision Matrix
# Macro Status -> (Buy_Mode, Sell_Mode)
#
# 🟢 BULLISH = AGGRESSIVE $30 | NORMAL Sell
# ⚪ NEUTRAL = BALANCED   $20 | CAUTIOUS Sell
# 🔴 BEARISH = NO_BUY     $12 | SNIPER_EXIT Sell
# =====================================================================

MARKET_MODE_MATRIX = {
    'BULLISH': ('AGGRESSIVE', 'NORMAL'),
    'NEUTRAL': ('BALANCED',   'CAUTIOUS'),
    'BEARISH': ('NO_BUY',     'SNIPER_EXIT'),
}


def get_market_modes(current_trend: str, market_direction: str = None) -> tuple:
    """
    Get buy/sell modes based on macro status only.
    Returns: (buy_mode_dict, sell_mode_dict)
    """
    current_trend = str(current_trend or 'NEUTRAL')

    if 'BULL' in current_trend:
        key = 'BULLISH'
    elif 'BEAR' in current_trend:
        key = 'BEARISH'
    else:
        key = 'NEUTRAL'

    buy_mode_key, sell_mode_key = MARKET_MODE_MATRIX.get(key, ('BALANCED', 'CAUTIOUS'))

    buy_modes = {
        'AGGRESSIVE': BUY_MODE_AGGRESSIVE,
        'BALANCED':   BUY_MODE_BALANCED,
        'NO_BUY':     BUY_MODE_NO_BUY,
    }

    sell_modes = {
        'NORMAL':      SELL_MODE_NORMAL,
        'CAUTIOUS':    SELL_MODE_CAUTIOUS,
        'SNIPER_EXIT': SELL_MODE_SNIPER_EXIT,
    }

    return (
        buy_modes.get(buy_mode_key, BUY_MODE_BALANCED),
        sell_modes.get(sell_mode_key, SELL_MODE_CAUTIOUS),
    )


# =====================================================================
# 🪙 Symbols
# =====================================================================

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

TOP_COINS_TO_TRADE = 20


def init_symbols():
    """Initialize symbols dictionary"""
    return {symbol: {'position': None} for symbol in SYMBOLS}


# =====================================================================
# 🌍 Multi-Timeframe Dynamic Thresholds (used by MultiTimeframeAnalyzer)
# =====================================================================
REALTIME_BOTTOM_BASE_CONFIDENCE = 60
REALTIME_BOTTOM_BASE_CONFIRMATIONS = 2
REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE = 50
REALTIME_BOTTOM_BULL_CONFIDENCE = 60
REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE = 70
REALTIME_BOTTOM_BEAR_CONFIDENCE = 80
REALTIME_BOTTOM_BEAR_CONFIRMATIONS = 2
REALTIME_PEAK_BASE_CONFIDENCE = 60
REALTIME_PEAK_BASE_CONFIRMATIONS = 2
REALTIME_PEAK_STRONG_BULL_CONFIDENCE = 70
REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS = 3
REALTIME_PEAK_BULL_CONFIDENCE = 70
REALTIME_PEAK_SIDEWAYS_CONFIDENCE = 60
REALTIME_PEAK_BEAR_CONFIDENCE = 50


