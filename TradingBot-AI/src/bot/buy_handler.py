"""
🟢 Buy Handler
Processes BUY results, sends notifications, and saves position data.
"""

import sys
import os

# إضافة مسار src للاستيراد
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir     = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from datetime import datetime, timezone
from colorama import Fore, Style

from utils import execute_buy, save_open_positions
from notifications import send_buy_notification
from config import MIN_TRADE_AMOUNT

# ✅ استيراد اختياري - لا يوقف البرنامج إذا لم يكن موجوداً
try:
    from analysis import get_liquidity_metrics
    _LIQUIDITY_AVAILABLE = True
except ImportError:
    _LIQUIDITY_AVAILABLE = False


# ──────────────────────────────────────────────
# 🔧 Helper: حساب TP و SL بشكل ديناميكي
# ──────────────────────────────────────────────
def _calculate_tp_sl(price: float, confidence: float) -> tuple[float, float]:
    """
    يحسب Take Profit و Stop Loss بناءً على السعر والثقة.
    - confidence 0→100
    - TP: من 2% إلى 6% بناءً على الثقة
    - SL: ثابت 2% (يمكن تعديله)
    """
    confidence = max(0.0, min(100.0, confidence))
    tp_pct     = 0.02 + (confidence / 100.0) * 0.04   # 2% - 6%
    sl_pct     = 0.02                                   # 2% ثابت
    tp_target  = round(price * (1 + tp_pct), 6)
    sl_target  = round(price * (1 - sl_pct), 6)
    return tp_target, sl_target


# ──────────────────────────────────────────────
# 🔧 Helper: جلب السيولة بأمان
# ──────────────────────────────────────────────
def _fetch_liquidity_scores(exchange, symbol: str) -> dict:
    """
    يجلب مقاييس السيولة ويعيد قيماً افتراضية عند الفشل.
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
        print(f"⚠️ [{symbol}] فشل جلب بيانات السيولة، سيتم استخدام القيم الافتراضية: {e}")
        return defaults


# ──────────────────────────────────────────────
# 🔧 Helper: جلب الكمية الفعلية المنفذة
# ──────────────────────────────────────────────
def _get_actual_amount(exchange, symbol: str, buy_result: dict) -> float:
    """
    يحاول الحصول على الكمية الفعلية من:
    1. حقل 'filled' في الأوردر
    2. الرصيد الفعلي من Binance
    3. الكمية المحسوبة كـ fallback
    """
    fallback_amount = buy_result.get('amount', 0)

    try:
        order  = buy_result.get('order', {}) or {}
        filled = order.get('filled', 0) or 0

        if filled > 0:
            print(f"✅ [{symbol}] الكمية الفعلية من Binance (filled): {filled}")
            return filled

        # محاولة الحصول من الرصيد
        balance       = exchange.fetch_balance()
        base_currency = symbol.split('/')[0]
        balance_free  = balance.get(base_currency, {}).get('free', fallback_amount)

        if balance_free and balance_free > 0:
            print(f"✅ [{symbol}] الكمية من الرصيد: {balance_free}")
            return balance_free

    except Exception as e:
        print(f"⚠️ [{symbol}] تعذّر جلب الكمية الفعلية، سيتم استخدام الكمية المحسوبة: {e}")

    print(f"ℹ️ [{symbol}] استخدام الكمية المحسوبة كـ fallback: {fallback_amount}")
    return fallback_amount


# ──────────────────────────────────────────────
# 🟢 Main: معالجة أمر الشراء
# ──────────────────────────────────────────────
def process_buy(result: dict, exchange, ctx: dict) -> bool:
    """
    Process a BUY action result.

    ctx keys:
        SYMBOLS_DATA        - dict العملات والمواقع
        symbols_data_lock   - Lock للوصول الآمن
        storage             - كائن التخزين
        smart_money_tracker - (اختياري)
        risk_manager        - (اختياري)
        anomaly_detector    - (اختياري)
        exit_strategy       - (اختياري)
        pattern_recognizer  - (اختياري)
        liquidity_analyzer  - (اختياري)
        advisor_manager     - (اختياري)

    Returns:
        True  - إذا نجح الشراء
        False - إذا فشل أو رُفض
    Note:
        المستدعي مسؤول عن تحديث active_count و available.
    """

    # ── استخراج البيانات الأساسية ──
    symbol            = result['symbol']
    SYMBOLS_DATA      = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage           = ctx['storage']

    decision           = result.get('decision', {})
    buy_vote_percentage = decision.get('buy_vote_percentage')
    buy_vote_count      = decision.get('buy_vote_count')
    total_consultants   = decision.get('total_consultants')

    # ── بناء نص العرض ──
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

    # ── التحقق من الحد الأدنى للصفقة ──
    trade_value = result['amount']
    if trade_value < MIN_TRADE_AMOUNT:
        print(
            f"❌ BUY REJECTED [{symbol}]: "
            f"Trade value ${trade_value:.2f} < minimum ${MIN_TRADE_AMOUNT}"
        )
        return False

    # ── تنفيذ الشراء ──
    buy_result = execute_buy(
        exchange,
        symbol,
        result['amount'],
        result['price'],
        result['confidence']
    )

    if not buy_result.get('success'):
        print(f"❌ [{symbol}] فشل تنفيذ أمر الشراء: {buy_result.get('error', 'Unknown error')}")
        return False

    # ── الكمية الفعلية المنفذة ──
    actual_amount = _get_actual_amount(exchange, symbol, buy_result)
    buy_value     = actual_amount * buy_result['price']

    # ── حساب TP / SL ──
    tp_target, sl_target = _calculate_tp_sl(
        price      = buy_result['price'],
        confidence = result['confidence']
    )
    print(
        f"🎯 [{symbol}] TP: ${tp_target:.4f}"
        f" | SL: ${sl_target:.4f}"
        f" | Buy Price: ${buy_result['price']:.4f}"
    )

    # ── إرسال الإشعار ──
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

    # ── بناء بيانات الموقف الأساسية ──
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

    # ── إضافة بيانات القرار إذا توفرت ──
    if decision:
        # ✅ جرب buy_votes أولاً ثم advisors_intelligence كـ fallback
        buy_votes_from_decision = (
            decision.get('buy_votes') or
            {
                k: 1
                for k, v in decision.get('advisors_intelligence', {}).items()
                if v
            }
        )

        # ── بناء advisor_scores ──
        advisor_scores = {**result.get('analysis', {})}
        advisor_scores.update({
            'confidence':      result.get('confidence', 0),
            'rsi':             result.get('rsi', 50),
            'volume_ratio':    result.get('volume_ratio', 1.0),
            'whale_confidence': result.get('analysis', {}).get('whale_confidence', 0),
        })

        # ── إضافة مقاييس السيولة ──
        liquidity_scores = _fetch_liquidity_scores(exchange, symbol)
        advisor_scores.update(liquidity_scores)

        # ── تحديث position_data ──
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

    # ── حفظ الموقف بشكل آمن ──
    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = position_data

    save_open_positions(storage, SYMBOLS_DATA, symbols_data_lock)

    print(
        f"{Fore.GREEN}"
        f"✅ [{symbol}] تم تسجيل الموقف بنجاح"
        f" | Amount: {actual_amount:.6f}"
        f" | Value: ${buy_value:.2f}"
        f"{Style.RESET_ALL}"
    )

    return True