"""
🔴 Sell Handler
Processes SELL results and handles AI learning after a successful sell.
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
import json

from utils import execute_sell, calculate_sell_value
from notifications import send_sell_notification


def process_sell(result, exchange, ctx):
    """
    Process a SELL action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              exit_strategy, pattern_recognizer, sell_cooldown,
              meta, advisor_manager
    Returns: True if sell executed successfully, False otherwise.
    """
    symbol          = result['symbol']
    SYMBOLS_DATA    = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage         = ctx['storage']
    advisor_manager = ctx.get('advisor_manager')
    meta            = ctx.get('meta')
    sell_cooldown   = ctx.get('sell_cooldown', {})

    print(f"{Fore.RED}🔴 SELL {symbol} | {result['reason']} | Profit: {result['profit']:+.2f}%{Style.RESET_ALL}")

    sell_result = execute_sell(exchange, symbol, result['amount'], result['reason'])
    if not sell_result['success']:
        return False

    sell_cooldown[symbol] = datetime.now()

    sell_value = calculate_sell_value(result['amount'], result['price'])
    send_sell_notification(
        symbol, result['amount'], result['price'],
        sell_value, result['profit'], result['reason']
    )

    position = result['position']

    # AI Learning with instant evaluation
    try:
        hours_held = 24
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str:
                buy_time = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except:
            pass

        profit = result.get('profit', 0)
        
        # تقييم فوري للصفقة
        if profit >= 1.5:
            trade_quality = 'GREAT'
        elif profit >= 0.8:
            trade_quality = 'GOOD'
        elif profit >= 0.3:
            trade_quality = 'OK'
        elif profit >= -0.5:
            trade_quality = 'RISKY'
        else:
            trade_quality = 'TRAP'

        # جلب أصوات المستشارين
        advisor_votes = position.get('advisor_votes', {})
        
        # حفظ بيانات الصفقة
        trade_data = {
            'symbol': symbol,
            'action': 'sell',
            'profit_percent': profit,
            'trade_quality': trade_quality,
            'sell_reason': result.get('reason'),
            'hours_held': hours_held,
            'advisor_votes': advisor_votes,
            'buy_votes': advisor_votes,  # نفس الأصوات للشراء
            'data': {
                'buy_price': position.get('buy_price'),
                'sell_price': result.get('price'),
                'ai_data': position.get('ai_data', {})
            }
        }
        storage.save_trade(trade_data)
        
        # =========================================================
        # 🎓 التعلم المباشر للملك والمستشارين - حفظ في الداتابيز
        # =========================================================
        
        # حفظ بيانات التعلم
        try:
            # تعلم الملك
            king_learning_data = {
                'king': {
                    'buy_success': 1 if profit > 0.5 else 0,
                    'buy_fail': 1 if profit < -0.5 else 0,
                    'sell_success': 1 if trade_quality in ['GREAT', 'GOOD', 'OK'] else 0,
                    'sell_fail': 1 if trade_quality in ['RISKY', 'TRAP'] else 0,
                    'peak_correct': 1 if trade_quality in ['GREAT', 'GOOD', 'OK'] else 0,
                    'peak_wrong': 1 if trade_quality in ['RISKY', 'TRAP'] else 0,
                    'bottom_correct': 1 if profit > 0.5 else 0,
                    'bottom_wrong': 1 if profit < -0.5 else 0
                }
            }
            storage.save_learning_data('king', king_learning_data)
            
            # تعلم المستشارين
            advisor_learning_data = {}
            for advisor, voted in advisor_votes.items():
                if trade_quality in ['GREAT', 'GOOD', 'OK']:
                    advisor_learning_data[advisor] = {
                        'sell_success': 1 if voted == 1 else 0,
                        'sell_fail': 0 if voted == 1 else 1
                    }
                elif trade_quality in ['RISKY', 'TRAP']:
                    advisor_learning_data[advisor] = {
                        'sell_success': 0 if voted == 1 else 1,
                        'sell_fail': 1 if voted == 1 else 0
                    }
            if advisor_learning_data:
                storage.save_learning_data('advisors', advisor_learning_data)
            
            print(f"🎓 Learning saved to database")
            
        except Exception as e:
            print(f"⚠️ Learning save error: {e}")
        
        quality_emoji = '🟢' if trade_quality in ['GREAT', 'GOOD'] else ('🟡' if trade_quality == 'OK' else '🔴')
        print(f"{quality_emoji} Trade Quality: {trade_quality} | Profit: {profit:+.2f}% | Held: {hours_held:.1f}h")
        
    except Exception as e:
        print(f"⚠️ Error saving trade for {symbol}: {e}")

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = None

    try:
        storage.delete_position(symbol)
        print(f"✅ {symbol} position deleted from database.")
    except Exception as e:
        print(f"⚠️ Error deleting {symbol} from database: {e}")

    return True
