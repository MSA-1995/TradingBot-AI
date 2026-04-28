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

# Minimum Profit Threshold for Selling
MIN_SELL_PROFIT = 0.5

# Risk Management
PEAK_DROP_THRESHOLD = 5.0
BOTTOM_BOUNCE_THRESHOLD = 2.0
REVERSAL_CANDLES = 30
VOLUME_SPIKE_FACTOR = 1.5

# Performance & Memory Tuning
BATCH_SIZE = 20
MAX_WORKERS = 20


# Memory Management
MEMORY_CLEANUP_INTERVAL = 60
MEMORY_USAGE_THRESHOLD = 70

# Timing
LOOP_SLEEP = 2
REPORT_INTERVAL = 1800     #تقرير الديسكورد 1800 ثانيه = 30 دقيقة 

# =====================================================================
# 🔮 Market Prediction Sell Modes
# =====================================================================

SELL_MODE_NORMAL = {
    'mode': 'NORMAL',
    'stability_minutes': 0,
    'min_sell_profit': 0.5,    # حد أدنى عمولة فقط
    'stop_loss_mult': 1.2,
    'label': '👑 Normal',
}

SELL_MODE_SNIPER_EXIT = {
    'mode': 'SNIPER_EXIT',
    'stability_minutes': 0,
    'min_sell_profit': 0.5,    # حد أدنى عمولة فقط - AI يقرر القمة
    'stop_loss_mult': 0.5,
    'label': '🛡️ Sniper Exit',
}

SELL_MODE_WAIT_RECOVERY = {
    'mode': 'WAIT_RECOVERY',
    'stability_minutes': 0,
    'min_sell_profit': 0.5,    # حد أدنى عمولة فقط - AI يقرر القمة
    'stop_loss_mult': 1.0,
    'label': '⏳ Wait Recovery',
}

SELL_MODE_CAUTIOUS = {
    'mode': 'CAUTIOUS',
    'stability_minutes': 0,    # AI يقرر بدون وقت ثابت
    'min_sell_profit': 0.5,    # حد أدنى عمولة فقط - AI يقرر القمة
    'stop_loss_mult': 0.8,
    'label': '⚪ Cautious',
}

# =====================================================================
# 🔮 Market Prediction Buy Modes
# =====================================================================

BUY_MODE_AGGRESSIVE = {
    'mode': 'AGGRESSIVE',
    'min_confidence': 60,
    'max_amount': 30,
    'max_positions': 15,
    'label': '🟢🟢 Aggressive',
}

BUY_MODE_BALANCED = {
    'mode': 'BALANCED',
    'min_confidence': 60,
    'max_amount': 25,
    'max_positions': 15,
    'label': '⚪ Balanced',
}

BUY_MODE_CAUTIOUS = {
    'mode': 'CAUTIOUS_BUY',
    'min_confidence': 65,
    'max_amount': 22,
    'max_positions': 12,
    'label': '⏳ Cautious',
}

BUY_MODE_MINIMAL = {
    'mode': 'MINIMAL',
    'min_confidence': 70,
    'max_amount': 20,
    'max_positions': 10,
    'label': '⚠️ High Confidence',
}

BUY_MODE_NO_BUY = {
    'mode': 'NO_BUY',
    'min_confidence': 80,
    'max_amount': 12,
    'max_positions': 5,
    'label': '🔴🔴 High Confidence Only',
}



# =====================================================================
# 🌐 Macro Trend Voting Points
# (current, 1h, 4h) -> points
# =====================================================================

MACRO_BUY_POINTS = {
    # 🟢 Positive
    ('BULL', 'BULL', 'BULL') : +10,
    ('BULL', 'BULL', 'NEUT') : +5,
    ('BULL', 'BULL', 'BEAR') : -5,

    ('BULL', 'NEUT', 'BULL') : +3,
    ('BULL', 'NEUT', 'NEUT') : 0,
    ('BULL', 'NEUT', 'BEAR') : -8,

    ('BULL', 'BEAR', 'BULL') : -3,
    ('BULL', 'BEAR', 'NEUT') : -8,
    ('BULL', 'BEAR', 'BEAR') : -10,

    ('NEUT', 'BULL', 'BULL') : +5,
    ('NEUT', 'BULL', 'NEUT') : +3,
    ('NEUT', 'BULL', 'BEAR') : -5,

    ('NEUT', 'NEUT', 'BULL') : +3,
    ('NEUT', 'NEUT', 'NEUT') : 0,
    ('NEUT', 'NEUT', 'BEAR') : -10,

    ('NEUT', 'BEAR', 'BULL') : -5,
    ('NEUT', 'BEAR', 'NEUT') : -10,
    ('NEUT', 'BEAR', 'BEAR') : -10,

    ('BEAR', 'BULL', 'BULL') : +3,
    ('BEAR', 'BULL', 'NEUT') : -5,
    ('BEAR', 'BULL', 'BEAR') : -5,

    ('BEAR', 'NEUT', 'BULL') : -5,
    ('BEAR', 'NEUT', 'NEUT') : -9,
    ('BEAR', 'NEUT', 'BEAR') : -10,

    ('BEAR', 'BEAR', 'BULL') : +3,
    ('BEAR', 'BEAR', 'NEUT') : -10,
    ('BEAR', 'BEAR', 'BEAR') : -10,
}

MACRO_SELL_POINTS = {
    # 🟢 Bullish = negative (sell-model hold / avoid sell)
    ('BULL', 'BULL', 'BULL') : -10,
    ('BULL', 'BULL', 'NEUT') : -5,
    ('BULL', 'BULL', 'BEAR') : +5,

    ('BULL', 'NEUT', 'BULL') : -3,
    ('BULL', 'NEUT', 'NEUT') : 0,
    ('BULL', 'NEUT', 'BEAR') : +7,

    ('BULL', 'BEAR', 'BULL') : +3,
    ('BULL', 'BEAR', 'NEUT') : +7,
    ('BULL', 'BEAR', 'BEAR') : +10,

    ('NEUT', 'BULL', 'BULL') : -5,
    ('NEUT', 'BULL', 'NEUT') : -3,
    ('NEUT', 'BULL', 'BEAR') : +5,

    ('NEUT', 'NEUT', 'BULL') : -3,
    ('NEUT', 'NEUT', 'NEUT') : 0,
    ('NEUT', 'NEUT', 'BEAR') : +10,

    ('NEUT', 'BEAR', 'BULL') : +5,
    ('NEUT', 'BEAR', 'NEUT') : +10,
    ('NEUT', 'BEAR', 'BEAR') : +10,

    ('BEAR', 'BULL', 'BULL') : +5,
    ('BEAR', 'BULL', 'NEUT') : +5,
    ('BEAR', 'BULL', 'BEAR') : +5,

    ('BEAR', 'NEUT', 'BULL') : -5,
    ('BEAR', 'NEUT', 'NEUT') : -10,
    ('BEAR', 'NEUT', 'BEAR') : +5,

    ('BEAR', 'BEAR', 'BULL') : +5,
    ('BEAR', 'BEAR', 'NEUT') : +10,
    ('BEAR', 'BEAR', 'BEAR') : +10,
}

# =====================================================================
# 🔮 Market Prediction Decision Matrix
# (Current, Predicted) -> (Buy_Mode, Sell_Mode)
#
# 🟢→🟢 = 50%+ \$30 | Buy strong + Sell at peak
# 🟢→⚪ = 60%+ \$25 | Normal buy + Sell at peak
# 🟢→🔴 = 90%+ \$12 | Almost no buy + Sniper profit
# 🟢→🔄 = 60%+ \$25 | Normal buy + Sell at peak
# ⚪→🟢 = 60%+ \$25 | Good signal + Normal sell
# ⚪→⚪ = 60%+ \$25 | Normal + Normal
# ⚪→🔴 = 90%+ \$12 | Almost no buy + Sniper profit
# ⚪→🔄 = 60%+ \$25 | Normal + Normal
# 🔴→🟢 = 70%+ \$15 | Careful buy + Wait recovery
# 🔴→⚪ = 70%+ \$15 | Careful + Cautious sell
# 🔴→🔴 = 90%+ \$12 | No buy + Exit fast
# 🔴→🔄 = 70%+ \$15 | Careful + Cautious sell
# =====================================================================

PREDICTION_MATRIX = {
    # 🟢 Bullish now
    ('BULLISH', 'BULLISH'):   ('AGGRESSIVE', 'NORMAL'),
    ('BULLISH', 'NEUTRAL'):   ('BALANCED', 'NORMAL'),
    ('BULLISH', 'BEARISH'):   ('CAUTIOUS_BUY', 'SNIPER_EXIT'),
    ('BULLISH', 'MIXED'):     ('BALANCED', 'NORMAL'),

    # ⚪ Neutral now
    ('NEUTRAL', 'BULLISH'):   ('BALANCED', 'NORMAL'),
    ('NEUTRAL', 'NEUTRAL'):   ('BALANCED', 'NORMAL'),
    ('NEUTRAL', 'BEARISH'):   ('CAUTIOUS_BUY', 'SNIPER_EXIT'),
    ('NEUTRAL', 'MIXED'):     ('BALANCED', 'CAUTIOUS'),

    # 🔴 Bearish now
    ('BEARISH', 'BULLISH'):   ('BALANCED', 'WAIT_RECOVERY'),
    ('BEARISH', 'NEUTRAL'):   ('CAUTIOUS_BUY', 'CAUTIOUS'),
    ('BEARISH', 'BEARISH'):   ('NO_BUY', 'SNIPER_EXIT'),
    ('BEARISH', 'MIXED'):     ('CAUTIOUS_BUY', 'CAUTIOUS'),
}


def get_prediction_modes(current_trend: str, predicted_trend: str) -> tuple:
    """
    Get buy/sell modes based on current and predicted trend
    Returns: (buy_mode_dict, sell_mode_dict)
    """
    # Simplify current trend
    if 'BULL' in current_trend:
        current = 'BULLISH'
    elif 'BEAR' in current_trend:
        current = 'BEARISH'
    else:
        current = 'NEUTRAL'

    # Simplify predicted trend
    if not predicted_trend:
        predicted_trend = 'NEUTRAL'
    if not current_trend:
        current_trend = 'NEUTRAL'
    if 'BULL' in predicted_trend:
        predicted = 'BULLISH'
    elif 'BEAR' in predicted_trend:
        predicted = 'BEARISH'
    elif predicted_trend == 'MIXED':
        predicted = 'MIXED'
    else:
        predicted = 'NEUTRAL'

    buy_mode_key, sell_mode_key = PREDICTION_MATRIX.get(
        (current, predicted), ('BALANCED', 'NORMAL')
    )

    buy_modes = {
        'AGGRESSIVE': BUY_MODE_AGGRESSIVE,
        'BALANCED': BUY_MODE_BALANCED,
        'CAUTIOUS_BUY': BUY_MODE_CAUTIOUS,
        'MINIMAL': BUY_MODE_MINIMAL,
        'NO_BUY': BUY_MODE_NO_BUY,
    }

    sell_modes = {
        'NORMAL': SELL_MODE_NORMAL,
        'SNIPER_EXIT': SELL_MODE_SNIPER_EXIT,
        'WAIT_RECOVERY': SELL_MODE_WAIT_RECOVERY,
        'CAUTIOUS': SELL_MODE_CAUTIOUS,
    }

    return (
        buy_modes.get(buy_mode_key, BUY_MODE_BALANCED),
        sell_modes.get(sell_mode_key, SELL_MODE_NORMAL),
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