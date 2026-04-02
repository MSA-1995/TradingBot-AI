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

        # جلب أصوات المستشارين للبيع (من result) والشراء (من position)
        sell_votes = result.get('sell_votes', {})
        buy_votes = position.get('advisor_votes', {})
        
        # جلب بيانات الأخبار والسيولة لحفظها في بيانات الصفقة
        news_data = {}
        sentiment_data = {}
        liquidity_data = {}
        try:
            news_analyzer = advisor_manager.get('NewsAnalyzer') if advisor_manager else None
            if news_analyzer:
                # محاولة بـ 24 ساعة أولاً، بعدين 48 ساعة، بعدين 72 ساعة
                news_sentiment = None
                for hours in [24, 48, 72]:
                    news_sentiment = news_analyzer.get_news_sentiment(symbol, hours=hours)
                    if news_sentiment:
                        break
                
                if news_sentiment:
                    news_data = {
                        'positive': news_sentiment.get('positive', 0),
                        'negative': news_sentiment.get('negative', 0),
                        'neutral': news_sentiment.get('neutral', 0),
                        'total': news_sentiment.get('total', 0),
                        'news_score': news_sentiment.get('news_score', 0)
                    }
                    sentiment_data = {
                        'news_sentiment': news_sentiment.get('news_score', 0)
                    }
        except:
            pass

        # جلب بيانات السيولة من الصفقة
        try:
            ai_data = position.get('ai_data', {})
            if ai_data:
                liquidity_data = {
                    'depth_ratio': ai_data.get('depth_ratio', 1.0),
                    'spread_percent': ai_data.get('spread_percent', 0.1),
                    'liquidity_score': ai_data.get('liquidity_score', 50),
                    'price_impact': ai_data.get('price_impact', 0.5),
                    'volume_consistency': ai_data.get('volume_consistency', 50)
                }
        except:
            pass

        # حفظ بيانات الصفقة
        trade_data = {
            'symbol': symbol,
            'action': 'sell',
            'profit_percent': profit,
            'trade_quality': trade_quality,
            'sell_reason': result.get('reason'),
            'hours_held': hours_held,
            'sell_votes': sell_votes,
            'buy_votes': buy_votes,
            'data': {
                'buy_price': position.get('buy_price'),
                'sell_price': result.get('price'),
                'ai_data': position.get('ai_data', {}),
                'news': news_data,
                'sentiment': sentiment_data,
                'liquidity': liquidity_data
            }
        }
        # تحديث ذاكرة العملة
        try:
            if hasattr(storage.storage, 'update_symbol_memory'):
                storage.storage.update_symbol_memory(
                    symbol=symbol,
                    profit=float(profit),
                    trade_quality=str(trade_quality),
                    hours_held=float(hours_held),
                    rsi=float(position.get('ai_data', {}).get('rsi', 50)),
                    volume_ratio=float(position.get('ai_data', {}).get('volume_ratio', 1))
                )
        except Exception as e:
            print(f"⚠️ Symbol memory update error: {e}")

        storage.save_trade(trade_data)
        
        # =========================================================
        # 🎓 التعلم المباشر للملك والمستشارين - حفظ في الداتابيز
        # =========================================================
        
        # حفظ بيانات التعلم
        try:
            # تعلم الملك (مع symbol للقائمة السوداء)
            if meta:
                meta.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, symbol=symbol)
            
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
            
            # تعلم المستشارين (من أصوات البيع)
            advisor_learning_data = {}
            for advisor, voted in sell_votes.items():
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
