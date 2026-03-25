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
    # The old ai_brain.learn_from_trade call is removed.

    # Exit Strategy Learning
    if advisor_manager:
        try:
            exit_strategy = advisor_manager.get('ExitStrategyModel')
            safe_profit = float(result['profit']) if result['profit'] is not None else 0
            hours_held = 24
            try:
                buy_time_str = position.get('buy_time')
                if buy_time_str:
                    buy_time = datetime.fromisoformat(buy_time_str)
                    hours_held = (datetime.now() - buy_time).total_seconds() / 3600
            except:
                pass

            exit_strategy.learn_from_exit(symbol, {
                'profit_percent': safe_profit,
                'sell_reason': result['reason'],
                'hours_held': hours_held
            })
        except Exception as e:
            pass

    # Pattern Recognition Learning
    if advisor_manager:
        try:
            pattern_recognizer = advisor_manager.get('EnhancedPatternRecognition')
            safe_profit = float(result['profit']) if result['profit'] is not None else 0
            pattern_recognizer.learn_pattern({
                'symbol': symbol,
                'profit_percent': safe_profit,
                'features': position.get('ai_data', {})
            })
        except Exception as e:
            pass

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = None
    storage.save_positions(SYMBOLS_DATA)

    return True