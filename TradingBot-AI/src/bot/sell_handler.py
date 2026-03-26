"""
🔴 Sell Handler
Processes SELL results and handles AI learning after a successful sell.
"""

from datetime import datetime
from colorama import Fore, Style

from trading import execute_sell, calculate_sell_value
from notifications import send_sell_notification


def process_sell(result, exchange, ctx):
    """
    Process a SELL action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              exit_strategy, pattern_recognizer, sell_cooldown
    Returns: True if sell executed successfully, False otherwise.
    """
    symbol          = result['symbol']
    SYMBOLS_DATA    = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage         = ctx['storage']
    advisor_manager = ctx.get('advisor_manager')
    sell_cooldown   = ctx.get('sell_cooldown', {})

    print(f"{Fore.RED}🔴 SELL {symbol} | {result['reason']} | Profit: {result['profit']:+.2f}%{Style.RESET_ALL}")

    sell_result = execute_sell(exchange, symbol, result['amount'], result['reason'])
    if not sell_result['success']:
        return False

    # Add to cooldown
    sell_cooldown[symbol] = datetime.now()

    sell_value = calculate_sell_value(result['amount'], result['price'])
    send_sell_notification(
        symbol, result['amount'], result['price'],
        sell_value, result['profit'], result['reason']
    )

    position = result['position']

    # AI Learning is now handled by the trainer based on trades_history.
    # Instead of learning directly, we save the trade result to the database.
    # The external trainer script will then use this data for asynchronous learning.
    try:
        hours_held = 24
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str:
                buy_time = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except:
            pass # Use default hours_held

        trade_data = {
            'symbol': symbol,
            'action': 'sell',
            'profit_percent': result.get('profit'),
            'sell_reason': result.get('reason'),
            'hours_held': hours_held,
            'data': {
                'buy_price': position.get('buy_price'),
                'sell_price': result.get('price'),
                'ai_data': position.get('ai_data', {})
            }
        }
        storage.save_trade(trade_data)
    except Exception as e:
        print(f"⚠️ Error saving trade for {symbol}: {e}")

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = None
    storage.save_positions(SYMBOLS_DATA)

    return True
