"""
🔄 Main Trading Loop
Runs the continuous analysis and execution cycle.
"""

import time
import gc
from datetime import datetime
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import get_active_positions_count, get_total_invested, should_send_report, format_price
from notifications import send_positions_report, send_heartbeat
from config import MAX_POSITIONS, LOOP_SLEEP, REPORT_INTERVAL, TOP_COINS_TO_TRADE, MAX_CAPITAL

from bot.sell_handler import process_sell
from bot.buy_handler import process_buy


def run_main_loop(exchange, ctx):
    """
    Main trading loop.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, balance_lock, sell_cooldown,
              storage, capital_manager, ai_brain, risk_manager, anomaly_detector,
              exit_strategy, pattern_recognizer, smart_money_tracker, liquidity_analyzer,
              analyze_fn, get_dynamic_symbols_fn
    """
    SYMBOLS_DATA       = ctx['SYMBOLS_DATA']
    symbols_data_lock  = ctx['symbols_data_lock']
    balance_lock       = ctx['balance_lock']
    sell_cooldown      = ctx['sell_cooldown']
    storage            = ctx['storage']
    capital_manager    = ctx['capital_manager']
    ai_brain           = ctx['ai_brain']
    risk_manager       = ctx['risk_manager']
    anomaly_detector   = ctx['anomaly_detector']
    exit_strategy      = ctx['exit_strategy']
    pattern_recognizer = ctx['pattern_recognizer']
    analyze_fn         = ctx['analyze_fn']
    get_dynamic_symbols_fn = ctx['get_dynamic_symbols_fn']

    try:
        loop_count = 0
        available  = 0
        last_report_time = datetime.now()

        while True:
            loop_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n{'='*60}\n⏰ {current_time}\n{'='*60}")

            # ========== HEARTBEAT — كل 10 ثواني للتجربة ==========
            if loop_count == 1 or loop_count % 15 == 0:
                import os
                db_url = os.getenv('DATABASE_URL')
                if db_url:
                    send_heartbeat(db_url)

            # Balance (cached - update every 60 seconds - تحسين السرعة)
            if loop_count == 1 or loop_count % 60 == 0:
                try:
                    balance   = exchange.fetch_balance()
                    available = balance['USDT']['free']
                except:
                    available = 0

            active_count = get_active_positions_count(SYMBOLS_DATA)
            invested     = get_total_invested(SYMBOLS_DATA)

            # Capital Management
            capital_status  = capital_manager.get_tradable_balance(available, invested)
            tradable_balance = capital_status['tradable']
            locked_profit   = capital_status['locked_profit']

            print(f"\n{Fore.CYAN}{Style.BRIGHT}{'█' * 60}")
            print(f"  💼 Balance: ${available:.2f} | Invested: ${invested:.2f} | Active: {active_count}/{MAX_POSITIONS}")
            if locked_profit > 0:
                print(f"  🔒 Locked Profit: ${locked_profit:.2f} | ✅ Tradable: ${tradable_balance:.2f}")
            else:
                print(f"  ✅ Tradable: ${tradable_balance:.2f} | Max Capital: ${MAX_CAPITAL}")
            print(f"{'█' * 60}{Style.RESET_ALL}\n")

            # الحصول على القائمة الديناميكية
            current_symbols = get_dynamic_symbols_fn()

            # ========== PARALLEL PROCESSING ==========
            results = []
            with ThreadPoolExecutor(max_workers=25) as executor:
                future_to_symbol = {
                    executor.submit(analyze_fn, symbol, exchange, active_count, available, invested): symbol
                    for symbol in current_symbols
                }

                for future in as_completed(future_to_symbol):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        symbol = future_to_symbol[future]
                        print(f"⚠️ {symbol}: Thread error - {e}")

            # ========== PROCESS RESULTS ==========
            # اختيار أفضل 10 عملات للتداول (الأعلى confidence)
            display_results  = [r for r in results if r and r.get('action') == 'DISPLAY']
            buy_results      = [r for r in results if r and r.get('action') == 'BUY']
            position_results = [r for r in results if r and r.get('action') in ['HOLD', 'SELL', 'SELL_WAIT']]

            buy_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            display_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            top_buy     = buy_results[:TOP_COINS_TO_TRADE]
            top_display = display_results[:TOP_COINS_TO_TRADE]

            results = position_results + top_buy + top_display

            # Filter: Show only active coins and open positions
            active_results = []
            for result in results:
                if not result:
                    continue

                action = result['action']

                if action in ['HOLD', 'SELL', 'SELL_WAIT']:
                    active_results.append(result)
                    continue

                if action == 'BUY':
                    active_results.append(result)
                    continue

                if action == 'DISPLAY':
                    if result.get('confidence', 0) >= 55:
                        active_results.append(result)
                    continue

            # Process and display active results
            for result in active_results:
                symbol = result['symbol']
                action = result['action']

                if action == 'ERROR':
                    continue

                if action == 'SKIP':
                    continue

                # Hold position
                if action == 'HOLD':
                    profit_emoji = "📈" if result['profit'] > 0 else "📉"
                    print(f"{profit_emoji} {symbol:12} {format_price(result['price'])} | Profit:{result['profit']:>+7.2f}% | Buy:{format_price(result['buy_price'])} | High:{format_price(result['highest'])} | {result['reason']}")
                    continue

                # Sell (waiting for minimum)
                if action == 'SELL_WAIT':
                    print(f"{Fore.YELLOW}⏳ {symbol} | {result['reason']} but value ${result['value']:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                    continue

                # Execute Sell
                if action == 'SELL':
                    process_sell(result, exchange, {
                        'SYMBOLS_DATA':    SYMBOLS_DATA,
                        'symbols_data_lock': symbols_data_lock,
                        'storage':         storage,
                        'ai_brain':        ai_brain,
                        'exit_strategy':   exit_strategy,
                        'pattern_recognizer': pattern_recognizer,
                        'sell_cooldown':   sell_cooldown,
                    })
                    continue

                # Execute Buy
                if action == 'BUY':
                    bought = process_buy(result, exchange, {
                        'SYMBOLS_DATA':    SYMBOLS_DATA,
                        'symbols_data_lock': symbols_data_lock,
                        'storage':         storage,
                        'ai_brain':        ai_brain,
                        'smart_money_tracker': ctx['smart_money_tracker'],
                        'risk_manager':    risk_manager,
                        'anomaly_detector': anomaly_detector,
                        'exit_strategy':   exit_strategy,
                        'pattern_recognizer': pattern_recognizer,
                        'liquidity_analyzer': ctx['liquidity_analyzer'],
                    })
                    if bought:
                        active_count += 1
                        with balance_lock:
                            available -= result['amount']
                    continue

                # Display only
                if action == 'DISPLAY':
                    vol_status   = "🟢" if result['volume'] > 0.8 else "🔴"
                    news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""
                    print(f"📊 {symbol:12} ${result['price']:>8.2f} | RSI:{result['rsi']:>5.1f} | Vol:{vol_status} {result['volume']:.1f}x | MACD:{result['macd']:>+6.1f} | Conf:{result['confidence']}/120{news_display} | {result.get('reason', '')}")
                    continue

            # Report
            if should_send_report(last_report_time, REPORT_INTERVAL):
                # جمع الصفقات المفتوحة مع الأسعار الحالية
                open_positions_data = {}
                with symbols_data_lock:
                    for sym, data in SYMBOLS_DATA.items():
                        position = data.get('position')
                        if position:
                            try:
                                ticker        = exchange.fetch_ticker(sym)
                                current_price = ticker['last']
                            except:
                                current_price = position['buy_price']

                            open_positions_data[sym] = {
                                'buy_price':    position['buy_price'],
                                'current_price': current_price,
                                'amount':        position['amount']
                            }

                send_positions_report(available, invested, active_count, MAX_POSITIONS, open_positions_data)

                # Auto-cleanup old data (every report)
                try:
                    if hasattr(storage, 'cleanup_old_data'):
                        storage.cleanup_old_data()
                except Exception as e:
                    print(f"⚠️ Cleanup error: {e}")

                # Risk Report
                if risk_manager:
                    try:
                        risk_report = risk_manager.get_risk_report()
                        if risk_report:
                            print(f"\n🛡️ Risk Report:")
                            print(f"  Sharpe Ratio (7d): {risk_report['sharpe_ratio_7d']}")
                            print(f"  Max Drawdown (7d): {risk_report['max_drawdown_7d']}%")
                            print(f"  Risk Level: {risk_report['risk_level']}")

                            stop_check = risk_manager.should_stop_trading()
                            if stop_check['stop']:
                                print(f"\n⚠️ {Fore.RED}RISK ALERT: {stop_check['reason']}{Style.RESET_ALL}")
                                print(f"Severity: {stop_check['severity']}")
                                if stop_check['severity'] == 'CRITICAL':
                                    print(f"🛑 Stopping bot for safety...")
                                    break
                    except Exception as e:
                        print(f"⚠️ Risk report error: {e}")

                # Anomaly Report
                if anomaly_detector:
                    try:
                        anomaly_report = anomaly_detector.get_anomaly_report()
                        if anomaly_report and anomaly_report['total_anomalies'] > 0:
                            print(f"\n🚨 Anomaly Report (24h):")
                            print(f"  Total: {anomaly_report['total_anomalies']}")
                            print(f"  Critical: {anomaly_report['critical']}")
                            print(f"  High: {anomaly_report['high']}")
                    except Exception as e:
                        print(f"⚠️ Anomaly report error: {e}")

                # Pattern Statistics
                if pattern_recognizer:
                    try:
                        pattern_stats = pattern_recognizer.get_pattern_statistics()
                        if pattern_stats:
                            print(f"\n🧠 Pattern Statistics:")
                            print(f"  Total Patterns: {pattern_stats['total_patterns']}")
                            print(f"  Success: {pattern_stats['success_patterns']}")
                            print(f"  Traps: {pattern_stats['trap_patterns']}")
                            print(f"  Success Rate: {pattern_stats['success_rate']:.1f}%")
                    except Exception as e:
                        print(f"⚠️ Pattern stats error: {e}")

                last_report_time = datetime.now()

            # Cleanup
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
