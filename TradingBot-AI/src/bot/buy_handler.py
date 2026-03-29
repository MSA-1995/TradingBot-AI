"""
🟢 Buy Handler
Processes BUY results, sends notifications, and saves position data.
"""

from datetime import datetime
from colorama import Fore, Style

from trading import execute_buy
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

    print(f"{Fore.GREEN}🟢 BUY {symbol} | Meta Confidence:{result['confidence']}{voting_display}{news_display}{Style.RESET_ALL}")

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

    send_buy_notification(
        symbol, buy_result['amount'], result['price'], result['amount'],
        result['confidence'], tp_target, sl_target,
        buy_vote_percentage, buy_vote_count, total_consultants
    )

    # The learning process is now handled by the trainer, not the bot.
    # The old ai_brain.save_buy_voting_results call is removed.

    position_data = {
        'buy_price':    buy_result['price'],
        'amount':       buy_result['amount'],
        'highest_price': buy_result['price'],
        'buy_time':     datetime.now().isoformat()
    }

    if 'decision' in result:
        decision = result['decision']
        models_scores = result.get('models_scores', {})

        # Collect all advisor scores directly from the pre-calculated models_scores
        advisor_scores = {
            'confidence':   result.get('confidence', 0),
            'rsi':          result.get('rsi', 0),
            'volume':       result.get('volume', 0),
            'macd_diff':    result.get('macd_diff', 0),
            'mtf_score':    models_scores.get('mtf', 0),
            'risk_score':   models_scores.get('risk', 0),
            'anomaly_score': models_scores.get('anomaly', 0),
            'exit_score':   models_scores.get('exit', 0),
            'pattern_score': models_scores.get('pattern', 0),
            'ranking_score': models_scores.get('liquidity', 0),
            'smart_money_score': models_scores.get('smart_money', 0)
        }

        position_data.update({
            'tp_target':      0,
            'sl_target':      0,
            'max_wait_hours': decision.get('max_wait_hours', 48),
            'ai_data':        advisor_scores
        })

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = position_data

    # Use the dedicated save function to ensure correct formatting
    from utils import save_open_positions
    save_open_positions(storage, SYMBOLS_DATA, symbols_data_lock)

    return True