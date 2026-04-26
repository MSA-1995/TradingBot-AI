"""
🟢 Buy Handler
Processes BUY results, sends notifications, and saves position data.
"""

import sys
import os

# Add src path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir     = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from datetime import datetime, timezone
from colorama import Fore, Style

from utils import execute_buy, save_open_positions
from notifications import send_buy_notification, send_advisor_report
from config import MIN_TRADE_AMOUNT

# Optional import - does not stop the program if not available
try:
    from analysis import get_liquidity_metrics
    _LIQUIDITY_AVAILABLE = True
except ImportError:
    _LIQUIDITY_AVAILABLE = False


# ──────────────────────────────────────────────
# 🔧 Helper: Calculate TP & SL Dynamically
# ──────────────────────────────────────────────
def _calculate_tp_sl(price: float, confidence: float) -> tuple[float, float]:
    """
    Calculates Take Profit and Stop Loss based on price and confidence.
    - confidence 0->100
    - TP: from 2% to 6% based on confidence
    - SL: fixed 2%
    """
    confidence = max(0.0, min(100.0, confidence))
    tp_pct     = 0.02 + (confidence / 100.0) * 0.04   # 2% - 6%
    sl_pct     = 0.02                                   # 2% fixed
    tp_target  = round(price * (1 + tp_pct), 6)
    sl_target  = round(price * (1 - sl_pct), 6)
    return tp_target, sl_target


# ──────────────────────────────────────────────
# 🔧 Helper: Fetch Liquidity Safely
# ──────────────────────────────────────────────
def _fetch_liquidity_scores(exchange, symbol: str) -> dict:
    """
    Fetches liquidity metrics and returns defaults on failure.
    """
    defaults = {
        'liquidity_score':    50,
        'depth_ratio':        1.0,
        'price_impact':       0.5,
        'volume_consistency': 50,
    }

    if not _LIQUIDITY_AVAILABLE:
        return defaults

    try:
        liquidity = get_liquidity_metrics(exchange, symbol)
        return {
            'liquidity_score':    liquidity.get('liquidity_score',    defaults['liquidity_score']),
            'depth_ratio':        liquidity.get('depth_ratio',        defaults['depth_ratio']),
            'price_impact':       liquidity.get('price_impact',       defaults['price_impact']),
            'volume_consistency': liquidity.get('volume_consistency', defaults['volume_consistency']),
        }
    except Exception as e:
        print(f"⚠️ [{symbol}] Failed to fetch liquidity data, using defaults: {e}")
        return defaults


# ──────────────────────────────────────────────
# 🔧 Helper: Fetch Actual Executed Amount
# ──────────────────────────────────────────────
def _get_actual_amount(exchange, symbol: str, buy_result: dict) -> float:
    """
    Tries to get actual amount from:
    1. 'filled' field in the order
    2. Actual balance from Binance
    3. Calculated fallback amount
    """
    fallback_amount = buy_result.get('amount', 0)

    try:
        order  = buy_result.get('order', {}) or {}
        filled = order.get('filled', 0) or 0

        if filled > 0:
            print(f"✅ [{symbol}] Actual amount from Binance (filled): {filled}")
            return filled

        balance       = exchange.fetch_balance()
        base_currency = symbol.split('/')[0]
        balance_free  = balance.get(base_currency, {}).get('free', fallback_amount)

        if balance_free and balance_free > 0:
            print(f"✅ [{symbol}] Amount from balance: {balance_free}")
            return balance_free

    except Exception as e:
        print(f"⚠️ [{symbol}] Failed to fetch actual amount, using calculated: {e}")

    print(f"ℹ️ [{symbol}] Using calculated fallback amount: {fallback_amount}")
    return fallback_amount


# ──────────────────────────────────────────────
# 🟢 Main: Process Buy Order
# ──────────────────────────────────────────────
def process_buy(result: dict, exchange, ctx: dict) -> bool:
    """
    Process a BUY action result.

    ctx keys:
        SYMBOLS_DATA        - dict of symbols and positions
        symbols_data_lock   - Lock for thread-safe access
        storage             - storage object
        smart_money_tracker - (optional)
        risk_manager        - (optional)
        anomaly_detector    - (optional)
        exit_strategy       - (optional)
        pattern_recognizer  - (optional)
        liquidity_analyzer  - (optional)
        advisor_manager     - (optional)

    Returns:
        True  - if buy succeeded
        False - if buy failed or rejected
    Note:
        Caller is responsible for updating active_count and available.
    """

    # Extract basic data
    symbol            = result['symbol']
    SYMBOLS_DATA      = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage           = ctx['storage']

    decision           = result.get('decision', {})
    buy_vote_percentage = decision.get('buy_vote_percentage')
    buy_vote_count      = decision.get('buy_vote_count')
    total_consultants   = decision.get('total_consultants')

    # Build display text
    news_display = (
        f" | 📰 {result['news_summary']}"
        if result.get('news_summary') else ""
    )

    voting_display = ""
    if buy_vote_percentage is not None:
        voting_display = (
            f" | 🗳️ Buy:{buy_vote_percentage:.0f}%"
            f" Amount:${result['amount']:.0f}"
        )

    print(
        f"{Fore.GREEN}"
        f"🟢 BUY {symbol}"
        f" | Price:${result['price']:.4f}"
        f" | Amount:${result['amount']:.2f}"
        f" | Meta Confidence:{result['confidence']:.1f}"
        f"{voting_display}{news_display}"
        f"{Style.RESET_ALL}"
    )

    # Check minimum trade value
    trade_value = result['amount']
    if trade_value < MIN_TRADE_AMOUNT:
        print(
            f"❌ BUY REJECTED [{symbol}]: "
            f"Trade value ${trade_value:.2f} < minimum ${MIN_TRADE_AMOUNT}"
        )
        return False

    # Execute buy order
    buy_result = execute_buy(
        exchange,
        symbol,
        result['amount'],
        result['price'],
        result['confidence']
    )

    if not buy_result.get('success'):
        print(f"❌ [{symbol}] Buy order failed: {buy_result.get('error', 'Unknown error')}")
        return False

    # Actual executed amount
    actual_amount = _get_actual_amount(exchange, symbol, buy_result)
    buy_value     = actual_amount * buy_result['price']

    # Calculate TP / SL
    tp_target, sl_target = _calculate_tp_sl(
        price      = buy_result['price'],
        confidence = result['confidence']
    )
    print(
        f"🎯 [{symbol}] TP: ${tp_target:.4f}"
        f" | SL: ${sl_target:.4f}"
        f" | Buy Price: ${buy_result['price']:.4f}"
    )

    # Send notification
    send_buy_notification(
        symbol              = symbol,
        amount              = actual_amount,
        price               = buy_result['price'],
        value               = buy_value,
        confidence          = result['confidence'],
        tp_target           = tp_target,
        sl_target           = sl_target,
        buy_vote_percentage = buy_vote_percentage,
        buy_vote_count      = buy_vote_count,
        total_consultants   = total_consultants
    )

    # 📊 Send Advisor Report
    try:
        _decision = result.get('decision', {})
        _core_votes = _decision.get('core_votes', {})
        _ai = _decision.get('advisors_intelligence', {})
        _analysis = result.get('analysis', {})

        _support_data = {
            'rsi': _analysis.get('rsi', 50),
            'macd_diff': _analysis.get('macd_diff', 0),
            'volume_ratio': _analysis.get('volume_ratio', 1.0),
            'fear_greed': _analysis.get('sentiment', {}).get('fear_greed', 50),
            '1h_bullish': _ai.get('1h_bullish', False),
            '4h_bullish': _ai.get('4h_bullish', False),
            '1h_bearish': _ai.get('1h_bearish', False),
            '4h_bearish': _ai.get('4h_bearish', False),
            'prediction_1h': True,
        }

        send_advisor_report(
            signal_type='BUY',
            symbol=symbol,
            core_votes=_core_votes,
            meta_confidence=result['confidence'],
            support_data=_support_data,
            total_points=result['confidence'],
            reason=result.get('reason', ''),
        )
    except Exception as e:
        print(f"⚠️ [{symbol}] Advisor report error: {e}")

    # Build position data
    position_data = {
        'buy_price':      buy_result['price'],
        'amount':         actual_amount,
        'highest_price':  buy_result['price'],
        'buy_time':       datetime.now(timezone.utc).isoformat(),
        'buy_confidence': result['confidence'],
        'buy_amount':     buy_value,
        'tp_target':      tp_target,
        'sl_target':      sl_target,
    }

    # Add decision data if available
    if decision:
        buy_votes_from_decision = (
            decision.get('buy_votes') or
            {
                k: 1
                for k, v in decision.get('advisors_intelligence', {}).items()
                if v
            }
        )

        # Build advisor_scores
        advisor_scores = {**result.get('analysis', {})}
        advisor_scores.update({
            'confidence':      result.get('confidence', 0),
            'rsi':             result.get('rsi', 50),
            'volume_ratio':    result.get('volume_ratio', 1.0),
            'whale_confidence': result.get('analysis', {}).get('whale_confidence', 0),
        })

        # Add liquidity metrics
        liquidity_scores = _fetch_liquidity_scores(exchange, symbol)
        advisor_scores.update(liquidity_scores)

        # Update position_data
        position_data.update({
            'max_wait_hours': decision.get('max_wait_hours', 48),
            'ai_data':        advisor_scores,
            'decision_factors': {
                'buy_vote_percentage': decision.get('buy_vote_percentage', 0),
                'buy_vote_count':      decision.get('buy_vote_count',      0),
                'total_consultants':   decision.get('total_consultants',   0),
                'reasons':             [
                    result.get('confidence', 0),
                    result.get('rsi', 0)
                ],
                'fib_score':           decision.get('fib_score', 0),
                'fib_level':           decision.get('fib_level', None),
            },
            'advisor_votes': buy_votes_from_decision,
        })

    # Save position safely
    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = position_data

    save_open_positions(storage, SYMBOLS_DATA, symbols_data_lock)

    print(
        f"{Fore.GREEN}"
        f"✅ [{symbol}] Position recorded successfully"
        f" | Amount: {actual_amount:.6f}"
        f" | Value: ${buy_value:.2f}"
        f"{Style.RESET_ALL}"
    )

    return True
