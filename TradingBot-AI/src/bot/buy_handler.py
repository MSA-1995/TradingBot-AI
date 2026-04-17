"""
🟢 Buy Handler
Processes BUY results, sends notifications, and saves position data.
"""

import sys
import os

# إضافة مسار src للاستيراد
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from datetime import datetime
from colorama import Fore, Style

from utils import execute_buy
from notifications import send_buy_notification


def process_buy(result, exchange, ctx):
    """
    Process a BUY action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              smart_money_tracker, risk_manager, anomaly_detector,
              exit_strategy, pattern_recognizer, liquidity_analyzer
    Returns: True if buy executed successfully, False otherwise.
    Note: caller is responsible for updating active_count and available.
    """
    symbol             = result['symbol']
    SYMBOLS_DATA       = ctx['SYMBOLS_DATA']
    symbols_data_lock  = ctx['symbols_data_lock']
    storage            = ctx['storage']
    advisor_manager    = ctx.get('advisor_manager')

    news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""

    voting_display = ""
    if 'decision' in result:
        decision = result['decision']
        buy_vote_percentage = decision.get('buy_vote_percentage')
        if buy_vote_percentage is not None:
            voting_display = f" | 🗳️ Buy:{buy_vote_percentage:.0f}% Amount:${result['amount']:.0f}"

    print(f"{Fore.GREEN}🟢 BUY {symbol} | Price:${result['price']:.4f} | Amount:${result['amount']:.2f} | Meta Confidence:{result['confidence']:.1f}{voting_display}{news_display}{Style.RESET_ALL}")

    # ✅ التأكد من أن القيمة الإجمالية >= 12 دولار (حد المنصة)
    trade_value = result['amount']  # amount بالفعل القيمة بالدولار
    from config import MIN_TRADE_AMOUNT

    if trade_value < MIN_TRADE_AMOUNT:
        print(f"❌ BUY REJECTED: Trade value ${trade_value:.2f} < minimum ${MIN_TRADE_AMOUNT}")
        return False

    buy_result = execute_buy(exchange, symbol, result['amount'], result['price'], result['confidence'])
    if not buy_result['success']:
        return False

    # Extract voting results if available
    tp_target = None
    sl_target = None
    buy_vote_percentage = None
    buy_vote_count = None
    total_consultants = None
    
    if 'decision' in result:
        decision = result['decision']
        buy_vote_percentage = decision.get('buy_vote_percentage')
        buy_vote_count = decision.get('buy_vote_count')
        total_consultants = decision.get('total_consultants')

    # ✅ الكمية الحقيقية من Binance (filled) وليس الكمية المحسوبة
    actual_amount = buy_result['amount']
    try:
        order = buy_result.get('order', {})
        filled = order.get('filled', 0)
        if filled and filled > 0:
            actual_amount = filled
            print(f"✅ Actual filled amount from Binance: {actual_amount}")
        else:
            # جلب الكمية من الرصيد مباشرة كـ fallback
            balance = exchange.fetch_balance()
            base_currency = symbol.split('/')[0]
            actual_amount = balance.get(base_currency, {}).get('free', actual_amount)
            print(f"✅ Amount from balance: {actual_amount}")
    except Exception as e:
        print(f"⚠️ Could not get actual amount, using calculated: {e}")

    send_buy_notification(
        symbol, actual_amount, buy_result['price'], actual_amount * buy_result['price'],
        result['confidence'], tp_target, sl_target,
        buy_vote_percentage, buy_vote_count, total_consultants
    )

    # Save for learning - with full decision context
    position_data = {
        'buy_price':    buy_result['price'],
        'amount':       actual_amount,
        'highest_price': buy_result['price'],
        'buy_time':     datetime.now().isoformat()
    }

    if 'decision' in result:
        decision = result['decision']
        models_scores = result.get('models_scores', {})
        
        # جلب أصوات المستشارين للشراء
        buy_votes_from_decision = decision.get('buy_votes', {})

        # ✅ حفظ كافة الميزات المتقدمة القادمة من analysis.py داخل ai_data
        advisor_scores = {**result.get('analysis', {})}
        # إضافة المفاتيح الأساسية للضمان
        advisor_scores.update({
            'confidence': result.get('confidence', 0),
            'rsi': result.get('rsi', 50),
            'volume_ratio': result.get('volume_ratio', 1.0)
        })

        # إضافة بيانات السيولة الحقيقية من Order Book
        try:
            from analysis import get_liquidity_metrics
            liquidity = get_liquidity_metrics(exchange, symbol)
            advisor_scores['liquidity_score'] = liquidity.get('liquidity_score', 50)
            advisor_scores['depth_ratio'] = liquidity.get('depth_ratio', 1.0)
            advisor_scores['price_impact'] = liquidity.get('price_impact', 0.5)
            advisor_scores['volume_consistency'] = liquidity.get('volume_consistency', 50)
        except Exception:
            advisor_scores['liquidity_score'] = 50
            advisor_scores['depth_ratio'] = 1.0
            advisor_scores['price_impact'] = 0.5
            advisor_scores['volume_consistency'] = 50

        position_data.update({
            'tp_target':      0,
            'sl_target':      0,
            'max_wait_hours': decision.get('max_wait_hours', 48),
            'ai_data':        advisor_scores,
            'decision_factors': {
                'buy_vote_percentage': decision.get('buy_vote_percentage', 0),
                'buy_vote_count': decision.get('buy_vote_count', 0),
                'total_consultants': decision.get('total_consultants', 0),
                'reasons': [result.get('confidence', 0), result.get('rsi', 0)],
                'fib_score': decision.get('fib_score', 0),
                'fib_level': decision.get('fib_level', None)
            },
            'advisor_votes': buy_votes_from_decision
        })

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = position_data

    # Use the dedicated save function to ensure correct formatting
    from utils import save_open_positions
    save_open_positions(storage, SYMBOLS_DATA, symbols_data_lock)

    return True
