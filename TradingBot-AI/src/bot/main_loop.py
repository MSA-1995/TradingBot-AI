"""
🔄 Main Trading Loop
Runs the continuous analysis and execution cycle.
"""

import time
import gc
import threading
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import get_active_positions_count, get_total_invested, should_send_report, format_price, save_open_positions
from notifications import send_positions_report
from config import MAX_POSITIONS, LOOP_SLEEP, REPORT_INTERVAL, TOP_COINS_TO_TRADE, MAX_CAPITAL, BATCH_SIZE, MAX_WORKERS, META_DISPLAY_THRESHOLD

from bot.sell_handler import process_sell
from bot.buy_handler import process_buy


def chunker(seq, size):
    """Yield successive n-sized chunks from a sequence."""
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def run_main_loop(exchange, ctx):
    """
    Main trading loop.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, balance_lock, sell_cooldown,
              storage, capital_manager, memory_optimizer, analyze_fn,
              get_dynamic_symbols_fn, advisor_manager, meta
    """
    # ========== DIAGNOSTIC ==========
    try:
        import psutil
        start_time = time.time()
        memory_usage = psutil.virtual_memory().percent
        print(f"🔍 Loop start - Memory: {memory_usage:.1f}% - Time: {time.strftime('%H:%M:%S')}")
    except ImportError:
        start_time = time.time()
        print(f"🔍 Loop start - No psutil - Time: {time.strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"⚠️ Diagnostic error: {e}")

    # ========== UNPACK CONTEXT ==========
    SYMBOLS_DATA           = ctx['SYMBOLS_DATA']
    symbols_data_lock      = ctx['symbols_data_lock']
    balance_lock           = ctx['balance_lock']
    sell_cooldown          = ctx['sell_cooldown']
    storage                = ctx['storage']
    capital_manager        = ctx['capital_manager']
    memory_optimizer       = ctx['memory_optimizer']
    meta                   = ctx.get('meta')
    analyze_fn             = ctx['analyze_fn']
    get_dynamic_symbols_fn = ctx['get_dynamic_symbols_fn']
    advisor_manager        = ctx['advisor_manager']

    # ========== PRE-LOAD ADVISORS ==========
    advisors_to_preload = [
        'SmartMoneyTracker', 'FibonacciAnalyzer',
        'NewsAnalyzer', 'LiquidityAnalyzer', 'AnomalyDetector',
        'EnhancedPatternRecognition', 'RiskManager', 'ExitStrategyModel'
    ]
    preloaded_advisors = {}
    for name in advisors_to_preload:
        try:
            preloaded_advisors[name] = advisor_manager.get(name)
        except Exception as e:
            print(f"  ❌ Failed to pre-load {name}: {e}")

    try:
        loop_count       = 0
        available        = 0
        last_report_time = datetime.now(timezone.utc)

        while True:
            loop_count   += 1
            current_time  = datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")

            # ========== BALANCE ==========
            if loop_count == 1 or loop_count % 60 == 0:
                try:
                    balance   = exchange.fetch_balance()
                    available = balance['USDT']['free']
                except Exception as e:
                    print(f"⚠️ Balance fetch error: {e}")
                    available = 0

            active_count = get_active_positions_count(SYMBOLS_DATA)
            invested     = get_total_invested(SYMBOLS_DATA)

            # ========== CAPITAL ==========
            capital_status   = capital_manager.get_tradable_balance(available, invested)
            tradable_balance = capital_status['tradable']
            locked_profit    = capital_status['locked_profit']

            # ========== MACRO TREND ==========
            macro_status = "NEUTRAL"
            try:
                macro_advisor = advisor_manager.get('MacroTrendAdvisor')
                if macro_advisor:
                    macro_status = macro_advisor.get_macro_status()
            except Exception:
                pass

            # ========== HEADER ==========
            print()
            print(f"✦•······················•✦•······················•✦")
            print(f"⏰ {current_time}")
            print(f"💼 Balance: ${available:.2f} | Invested: ${invested:.2f} | Active: {active_count}/{MAX_POSITIONS}")
            print(f"🌐 Macro Trend: {macro_status}")
            try:
                macro_advisor = meta.advisor_manager.get('MacroTrendAdvisor') if meta.advisor_manager else None
                if macro_advisor:
                    info = macro_advisor.get_display_info()
                    s1 = info.get('1h_icon', '⚪')
                    s4 = info.get('4h_icon', '⚪')
                    print(f"🔮 1h{s1} | 4h{s4}")
            except:
                pass
            if locked_profit > 0:
                print(f"🔒 Locked Profit: ${locked_profit:.2f} | Tradable: ${tradable_balance:.2f}")
            else:
                print(f"  Tradable: ${tradable_balance:.2f} | Max Capital: ${MAX_CAPITAL}")
            print(f"✦•······················•✦•······················•✦")
            print()

            # ========== PARALLEL PROCESSING ==========
            current_symbols = get_dynamic_symbols_fn()
            results = []
            for symbol_batch in chunker(current_symbols, BATCH_SIZE):
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    future_to_symbol = {
                        executor.submit(
                            analyze_fn, symbol, exchange, active_count,
                            available, invested, meta, preloaded_advisors,
                            ctx['storage']
                        ): symbol
                        for symbol in symbol_batch
                    }

                    for future in as_completed(future_to_symbol):
                        sym = future_to_symbol[future]
                        try:
                            result = future.result()
                            if result:
                                results.append(result)
                        except Exception as e:
                            print(f"⚠️ {sym}: Thread error - {e}")

                time.sleep(0.1)
                gc.collect()

            # ========== SORT RESULTS ==========
            position_results = [r for r in results if r and r.get('action') in ['HOLD', 'SELL', 'SELL_WAIT']]
            buy_results      = [r for r in results if r and r.get('action') == 'BUY']
            strong_results   = [r for r in results if r and r.get('action') == 'STRONG']
            display_results  = [r for r in results if r and r.get('action') == 'DISPLAY']

            buy_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            strong_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            display_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            results = position_results + buy_results + strong_results + display_results

            # ========== FILTER RESULTS ==========
            active_results = [
                r for r in results
                if r and r.get('action') in ['HOLD', 'SELL', 'SELL_WAIT', 'BUY', 'STRONG', 'DISPLAY', 'ERROR']
            ]

            skipped_count = len(results) - len(active_results)
            active_results.sort(key=lambda x: x.get('symbol', ''))

            # ========== PROCESS RESULTS ==========
            for result in active_results:
                symbol   = result.get('symbol', '')
                action   = result.get('action', '')
                analysis = result.get('analysis', {})

                # ERROR
                if action == 'ERROR':
                    print(f"❌ {symbol}: {result.get('message', 'Unknown error')}")
                    continue

                # SKIP
                if action == 'SKIP':
                    continue
                # ========== HOLD ==========
                if action == 'HOLD':
                    profit       = result.get('profit', 0) or 0
                    profit_emoji = "📈" if profit > 0 else "📉"

                    with symbols_data_lock:
                        if symbol in SYMBOLS_DATA and SYMBOLS_DATA[symbol].get('position'):
                            old_sl = SYMBOLS_DATA[symbol]['position'].get('stop_loss_threshold') or 0
                            new_sl = result.get('stop_loss_threshold') or old_sl or 3.0
                            SYMBOLS_DATA[symbol]['position']['stop_loss_threshold'] = new_sl
                            if abs(new_sl - old_sl) > 0.01:
                                try:
                                    save_open_positions(storage, SYMBOLS_DATA, symbols_data_lock)
                                except:
                                    pass

                    if profit < 0:
                        line_color = Fore.RED
                    elif profit > 0:
                        line_color = Fore.GREEN
                    else:
                        line_color = Fore.YELLOW

                    coin_forecast   = result.get('coin_forecast', {})
                    market_forecast = result.get('market_forecast', {})
                    forecast_text   = ""
                    if coin_forecast and market_forecast:
                        coin_dir      = coin_forecast.get('direction', 'neutral')
                        market_dir    = market_forecast.get('direction', 'neutral')
                        coin_emoji    = "🟢" if coin_dir == 'bullish' else "🔴" if coin_dir == 'bearish' else "⚪"
                        market_emoji  = "🟢" if market_dir == 'bullish' else "🔴" if market_dir == 'bearish' else "⚪"
                        forecast_text = f" | Coin{coin_emoji} Market{market_emoji}"

                    print(
                        f"{line_color}{profit_emoji} {symbol:12} {format_price(result['price'])} "
                        f"| Profit:{profit:+7.1f}% "
                        f"| Buy:{format_price(result.get('buy_price', 0))} "
                        f"| High:{format_price(result.get('highest', 0))} "
                        f"| {result.get('reason', '')}{forecast_text}{Style.RESET_ALL}"
                    )
                    continue

                # ========== SELL_WAIT ==========
                if action == 'SELL_WAIT':
                    min_val = 10
                    print(
                        f"{Fore.YELLOW}⏳ {symbol} | {result.get('reason', '')} "
                        f"but value ${result.get('value', 0):.4f} < ${min_val} minimum - Waiting{Style.RESET_ALL}"
                    )
                    continue

                # ========== SELL ==========
                if action == 'SELL':
                    process_sell(result, exchange, {
                        'SYMBOLS_DATA':      SYMBOLS_DATA,
                        'symbols_data_lock': symbols_data_lock,
                        'storage':           storage,
                        'advisor_manager':   advisor_manager,
                        'meta':              meta,
                        'sell_cooldown':     sell_cooldown,
                        'last_analysis':     analysis
                    })
                    continue

                # ========== BUY ==========
                if action == 'BUY':
                    bought = process_buy(result, exchange, {
                        'SYMBOLS_DATA':      SYMBOLS_DATA,
                        'symbols_data_lock': symbols_data_lock,
                        'storage':           storage,
                        'advisor_manager':   advisor_manager,
                        'meta':              meta,
                    })
                    if bought:
                        active_count += 1
                        with balance_lock:
                            available -= result.get('amount', 0)
                    continue

                # ========== STRONG ==========
                if action == 'STRONG':
                    rsi  = analysis.get('rsi', result.get('rsi', 0))
                    vol  = analysis.get('volume_ratio', result.get('volume', 0))
                    macd = analysis.get('macd_diff', result.get('macd', 0))

                    vol_status   = "🟢" if vol > 0.8 else "🔴"
                    news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""

                    coin_forecast   = result.get('coin_forecast', {})
                    market_forecast = result.get('market_forecast', {})
                    forecast_text   = ""
                    if coin_forecast and market_forecast:
                        coin_dir      = coin_forecast.get('direction', 'neutral')
                        market_dir    = market_forecast.get('direction', 'neutral')
                        coin_emoji    = "🟢" if coin_dir == 'bullish' else "🔴" if coin_dir == 'bearish' else "⚪"
                        market_emoji  = "🟢" if market_dir == 'bullish' else "🔴" if market_dir == 'bearish' else "⚪"
                        forecast_text = f" | Coin{coin_emoji} Market{market_emoji}"

                    print(
                        f"{Fore.GREEN}💪 {symbol:12} {format_price(result['price'])} "
                        f"| RSI:{rsi:>5.1f} "
                        f"| Vol:{vol_status} {min(vol, 100):.0f}x "
                        f"| MACD:{macd:>+6.1f} "
                        f"| Conf:{result.get('confidence', 0):.0f}/100"
                        f"{news_display} | {result.get('reason', '')}{forecast_text}{Style.RESET_ALL}"
                    )
                    continue

                # ========== DISPLAY ==========
                if action == 'DISPLAY':
                    if result.get('confidence', 0) >= META_DISPLAY_THRESHOLD:
                        rsi  = analysis.get('rsi', result.get('rsi', 0))
                        vol  = analysis.get('volume_ratio', result.get('volume', 0))
                        macd = analysis.get('macd_diff', result.get('macd', 0))

                        vol_status   = "🟢" if vol > 0.8 else "🔴"
                        news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""

                        coin_forecast   = result.get('coin_forecast', {})
                        market_forecast = result.get('market_forecast', {})
                        forecast_text   = ""
                        if coin_forecast and market_forecast:
                            coin_dir      = coin_forecast.get('direction', 'neutral')
                            market_dir    = market_forecast.get('direction', 'neutral')
                            coin_emoji    = "🟢" if coin_dir == 'bullish' else "🔴" if coin_dir == 'bearish' else "⚪"
                            market_emoji  = "🟢" if market_dir == 'bullish' else "🔴" if market_dir == 'bearish' else "⚪"
                            forecast_text = f" | Coin{coin_emoji} Market{market_emoji}"

                        print(
                            f"📊 {symbol:12} ${result.get('price', 0):>8.2f} "
                            f"| RSI:{rsi:>5.1f} "
                            f"| Vol:{vol_status} {min(vol, 100):.0f}x "
                            f"| MACD:{macd:>+6.1f} "
                            f"| Conf:{result.get('confidence', 0):.0f}/100"
                            f"{news_display} | {result.get('reason', '')}{forecast_text}"
                        )
                    continue

            # ========== SUMMARY ==========
            if len(active_results) <= active_count and skipped_count > 0:
                print(f"{Fore.CYAN}ℹ️  Scanned {skipped_count} other coins... (No opportunities found){Style.RESET_ALL}")

            # ========== PORTFOLIO REPORT ==========
            if should_send_report(last_report_time, REPORT_INTERVAL):
                open_positions_data = {}
                symbols_to_fetch    = []

                with symbols_data_lock:
                    for sym, data in SYMBOLS_DATA.items():
                        if data.get('position'):
                            symbols_to_fetch.append(sym)

                if symbols_to_fetch:
                    try:
                        all_tickers = exchange.fetch_tickers(symbols_to_fetch)
                    except Exception as e:
                        print(f"⚠️ Report: Could not fetch tickers: {e}")
                        all_tickers = {}

                    with symbols_data_lock:
                        for sym in symbols_to_fetch:
                            if sym not in SYMBOLS_DATA:
                                continue

                            position = SYMBOLS_DATA[sym].get('position')
                            if not position or not isinstance(position, dict):
                                continue

                            current_price = position.get('buy_price')
                            if sym in all_tickers and all_tickers[sym].get('last') is not None:
                                current_price = all_tickers[sym]['last']

                            if 'buy_price' in position and 'amount' in position:
                                buy_amount    = position['amount'] * position.get('buy_price', 0)
                                position_data = position.get('data', {})

                                if isinstance(position_data, str):
                                    try:
                                        position_data = json.loads(position_data)
                                    except Exception:
                                        position_data = {}

                                # ✅ اقرأ من position مباشرة أولاً، ثم من position_data كـ fallback
                                buy_confidence      = position.get('buy_confidence', 0) or position_data.get('buy_confidence', 0)
                                advisor_votes       = position.get('advisor_votes', {}) or position_data.get('advisor_votes', {})
                                ai_data             = position.get('ai_data', {}) or position_data.get('ai_data', {})
                                stop_loss_threshold = (
                                    position.get('stop_loss_threshold') or
                                    position_data.get('stop_loss_threshold')
                                )

                                open_positions_data[sym] = {
                                    'buy_price':           position.get('buy_price', 0),
                                    'current_price':       current_price,
                                    'amount':              position['amount'],
                                    'buy_amount':          buy_amount,
                                    'buy_confidence':      buy_confidence,
                                    'advisor_votes':       advisor_votes,
                                    'ai_data':             ai_data,
                                    'highest_price':       position.get('highest_price', position.get('buy_price', 0)),
                                    'stop_loss_threshold': stop_loss_threshold
                                }
                            else:
                                print(f"⚠️ Report: Skipping {sym} - incomplete position data")

                send_positions_report(available, invested, active_count, MAX_POSITIONS, open_positions_data, exchange)
                last_report_time = datetime.now(timezone.utc)

                try:
                    if hasattr(storage, 'cleanup_old_data'):
                        storage.cleanup_old_data()
                except Exception as e:
                    print(f"⚠️ Cleanup error: {e}")

            # ========== MEMORY OPTIMIZATION ==========
            try:
                memory_optimizer.periodic_cleanup()
            except Exception as e:
                print(f"⚠️ Memory optimizer error: {e}")

            # ========== RISK / ANOMALY / PATTERN REPORTS ==========
            if should_send_report(last_report_time, REPORT_INTERVAL):
                risk_manager       = preloaded_advisors.get('RiskManager')
                anomaly_detector   = preloaded_advisors.get('AnomalyDetector')
                pattern_recognizer = preloaded_advisors.get('EnhancedPatternRecognition')

                if risk_manager:
                    try:
                        risk_report = risk_manager.get_risk_report()
                        if risk_report:
                            stop_check = risk_manager.should_stop_trading()
                            if stop_check['stop']:
                                print(f"\n⚠️ {Fore.RED}RISK ALERT: {stop_check['reason']}{Style.RESET_ALL}")
                                print(f"Severity: {stop_check['severity']}")
                                if stop_check['severity'] == 'CRITICAL':
                                    print(f"🛑 Stopping bot for safety...")
                                    break
                    except Exception as e:
                        print(f"⚠️ Risk report error: {e}")

                if anomaly_detector:
                    try:
                        anomaly_report = anomaly_detector.get_anomaly_report()
                        if anomaly_report and anomaly_report.get('total_anomalies', 0) > 0:
                            pass
                    except Exception as e:
                        print(f"⚠️ Anomaly report error: {e}")

                if pattern_recognizer:
                    try:
                        pattern_stats = pattern_recognizer.get_pattern_statistics()
                        if pattern_stats:
                            pass
                    except Exception as e:
                        print(f"⚠️ Pattern stats error: {e}")

            # ========== SAVE BOT STATUS TO DB ==========
            try:
                import json as _json
                _bot_status = {
                    'balance': available,
                    'invested': invested,
                    'active': active_count,
                    'max_positions': MAX_POSITIONS,
                    'macro_status': macro_status,
                    'locked_profit': locked_profit,
                    'tradable': tradable_balance,
                    'time': current_time,
                    '1h_icon': '⚪',
                    '4h_icon': '⚪',
                }
                try:
                    _ma = meta.advisor_manager.get('MacroTrendAdvisor') if meta.advisor_manager else None
                    if _ma:
                        _info = _ma.get_display_info()
                        _bot_status['1h_icon'] = _info.get('1h_icon', '⚪')
                        _bot_status['4h_icon'] = _info.get('4h_icon', '⚪')
                except:
                    pass
                def _save_status(s, st):
                    try:
                        s.save_setting('bot_status', st)
                    except Exception as e:
                        print(f'⚠️ bot_status save failed: {e}')
                threading.Thread(target=_save_status, args=(ctx['storage'], _json.dumps(_bot_status)), daemon=True).start()
            except Exception as e:
                print(f'⚠️ bot_status block error: {e}')

            # ========== CLEANUP ==========
            gc.collect()
            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped")
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        print(f"\n📍 Full traceback:")
        traceback.print_exc()
        print(f"\n🔄 Restarting in 5 seconds...")
        time.sleep(5)
