"""
🔄 Main Trading Loop
Runs the continuous analysis and execution cycle.
"""

import time
import gc
import os
import sys
from datetime import datetime, timedelta
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import get_active_positions_count, get_total_invested, should_send_report, format_price
from notifications import send_positions_report
from config import MAX_POSITIONS, LOOP_SLEEP, REPORT_INTERVAL, TOP_COINS_TO_TRADE, MAX_CAPITAL, BATCH_SIZE, MAX_WORKERS

from bot.sell_handler import process_sell
from bot.buy_handler import process_buy

   


def chunker(seq, size):
    """Yield successive n-sized chunks from a sequence."""
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def run_main_loop(exchange, ctx):
    """
    Main trading loop.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, balance_lock, sell_cooldown,
              storage, capital_manager, risk_manager, anomaly_detector,
              exit_strategy, pattern_recognizer, smart_money_tracker, liquidity_analyzer,
              memory_optimizer, analyze_fn, get_dynamic_symbols_fn, advisor_manager
    """
    SYMBOLS_DATA       = ctx['SYMBOLS_DATA']
    symbols_data_lock  = ctx['symbols_data_lock']
    balance_lock       = ctx['balance_lock']
    sell_cooldown      = ctx['sell_cooldown']
    storage            = ctx['storage']
    capital_manager    = ctx['capital_manager']
    memory_optimizer   = ctx['memory_optimizer']
    meta               = ctx.get('meta')
    analyze_fn         = ctx['analyze_fn']
    get_dynamic_symbols_fn = ctx['get_dynamic_symbols_fn']
    advisor_manager    = ctx['advisor_manager']

    # ========== PRE-LOAD ADVISORS ==========
    # Silently pre-load all necessary advisors for the loop.
    advisors_to_preload = [
        'SmartMoneyTracker', 'FibonacciAnalyzer',
        'NewsAnalyzer', 'LiquidityAnalyzer', 'AnomalyDetector',
        'EnhancedPatternRecognition', 'RiskManager'
    ]
    preloaded_advisors = {}
    for name in advisors_to_preload:
        try:
            preloaded_advisors[name] = advisor_manager.get(name)
        except Exception as e:
            print(f"  ❌ Failed to pre-load {name}: {e}")

    try:
        loop_count = 0
        available  = 0
        last_report_time = datetime.now()

        # ⏰ مؤقت فحص تحديثات النماذج كل 7 ساعات
        _last_model_check = datetime.now()
        _MODEL_CHECK_HOURS = 7

        while True:
            loop_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n{'='*60}\n⏰ {current_time}\n{'='*60}")

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

            # 🌐 فحص حالة الماكرو للعرض
            macro_advisor = advisor_manager.get('MacroTrendAdvisor')
            macro_status = macro_advisor.get_macro_status()
            macro_emoji = "🟢" if "BULL" in macro_status else "🔴" if "BEAR" in macro_status else "⚪"

            print(f"\n{Fore.CYAN}{Style.BRIGHT}{'█' * 60}")
            print(f"  💼 Balance: ${available:.2f} | Invested: ${invested:.2f} | Active: {active_count}/{MAX_POSITIONS}")
            print(f"  🌐 Macro Trend: {macro_emoji} {macro_status}")
            if locked_profit > 0:
                print(f"  🔒 Locked Profit: ${locked_profit:.2f} | ✅ Tradable: ${tradable_balance:.2f}")
            else:
                print(f"  ✅ Tradable: ${tradable_balance:.2f} | Max Capital: ${MAX_CAPITAL}")
            print(f"{'█' * 60}{Style.RESET_ALL}\n")

            # الحصول على القائمة الديناميكية
            current_symbols = get_dynamic_symbols_fn()

            # ========== PARALLEL PROCESSING (IN BATCHES) ==========
            results = []
            # Process symbols in batches to conserve memory
            for symbol_batch in chunker(current_symbols, BATCH_SIZE):
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    future_to_symbol = {
                        executor.submit(analyze_fn, symbol, exchange, active_count, available, invested, meta, preloaded_advisors): symbol
                        for symbol in symbol_batch
                    }

                    for future in as_completed(future_to_symbol):
                        try:
                            result = future.result()
                            if result:
                                results.append(result)
                        except Exception as e:
                            symbol = future_to_symbol[future]
                            print(f"⚠️ {symbol}: Thread error - {e}")
                
                # A short sleep to prevent overwhelming the API and to allow memory to be freed
                time.sleep(0.1)
                gc.collect()



            # ========== PROCESS RESULTS ==========
            # اختيار أفضل 10 عملات للتداول (الأعلى confidence)
            display_results  = [r for r in results if r and r.get('action') == 'DISPLAY']
            buy_results      = [r for r in results if r and r.get('action') == 'BUY']
            strong_results   = [r for r in results if r and r.get('action') == 'STRONG']
            position_results = [r for r in results if r and r.get('action') in ['HOLD', 'SELL', 'SELL_WAIT']]

            buy_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            strong_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            display_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            top_buy     = buy_results
            top_strong  = strong_results
            top_display = display_results

            results = position_results + top_buy + top_strong + top_display

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

                if action == 'STRONG':
                    active_results.append(result)
                    continue

                if action == 'DISPLAY':
                    active_results.append(result)
                    continue
                
                # إظهار الأخطاء للمساعدة في التشخيص
                if action == 'ERROR':
                    active_results.append(result)
                    continue

            # عداد العملات التي تم فحصها ولكن تم تجاهلها
            skipped_count = len(results) - len(active_results)

            # Process and display active results
            for result in active_results:
                symbol = result['symbol']
                action = result['action']

                if action == 'ERROR':
                    print(f"❌ {symbol}: {result.get('message', 'Unknown error')}")
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
                        'advisor_manager': advisor_manager,
                        'meta':            meta,
                        'sell_cooldown':   sell_cooldown,
                        'last_analysis':   result.get('analysis', {})
                    })
                    continue

                # Execute Buy
                if action == 'BUY':
                    bought = process_buy(result, exchange, {
                        'SYMBOLS_DATA':    SYMBOLS_DATA,
                        'symbols_data_lock': symbols_data_lock,
                        'storage':         storage,
                        'advisor_manager': advisor_manager,
                        'meta':            meta,
                    })
                    if bought:
                        active_count += 1
                        with balance_lock:
                            available -= result['amount']
                    continue

                # 💪 Strong coins (King approved, waiting for votes)
                if action == 'STRONG':
                    vol_status   = "🟢" if result['volume'] > 0.8 else "🔴"
                    news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""
                    print(f"{Fore.GREEN}💪 {result['symbol']:12} {format_price(result['price'])} | RSI:{result['rsi']:>5.1f} | Vol:{vol_status} {result['volume']:.1f}x | MACD:{result['macd']:>+6.1f} | Conf:{result['confidence']}/100{news_display} | {result.get('reason', '')}{Style.RESET_ALL}")
                    continue

                # Display only
                if action == 'DISPLAY':
                    if result.get('confidence', 0) >= 40:  # فقط العملات القوية
                        vol_status   = "🟢" if result['volume'] > 0.8 else "🔴"
                        news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""
                        print(f"📊 {symbol:12} ${result['price']:>8.2f} | RSI:{result['rsi']:>5.1f} | Vol:{vol_status} {result['volume']:.1f}x | MACD:{result['macd']:>+6.1f} | Conf:{result['confidence']}/100{news_display} | {result.get('reason', '')}")
                    continue
            
            # طباعة ملخص المسح إذا لم يتم عرض أي عملة جديدة
            if len(active_results) <= active_count and skipped_count > 0:
                print(f"{Fore.CYAN}ℹ️  Scanned {skipped_count} other coins... (No opportunities found){Style.RESET_ALL}")

            # Report
            if should_send_report(last_report_time, REPORT_INTERVAL):
                # 🔄 فحص تحديثات النماذج كل 7 ساعات
                try:
                    dl_client = ctx.get('dl_client')
                    hours_since_check = (datetime.now() - _last_model_check).total_seconds() / 3600

                    if dl_client and hours_since_check >= _MODEL_CHECK_HOURS:
                        print(f"🕐 7 hours passed — checking for model updates...")
                        _last_model_check = datetime.now()
                        has_update = dl_client.check_for_updates()

                        if has_update:
                            print("🔄 New models found! Restarting bot to load them...")
                            time.sleep(2)
                            os.execv(sys.executable, [sys.executable] + sys.argv)
                        # إذا ما في تحديث يكمل طبيعي بدون أي شيء
                except Exception as e:
                    print(f"⚠️ Model update check error: {e}")
                
                # --- Network Convoy for Reporting ---
                # Fetch all tickers at once to reduce network requests.
                open_positions_data = {}
                symbols_to_fetch = []
                with symbols_data_lock:
                    for sym, data in SYMBOLS_DATA.items():
                        if data.get('position'):
                            symbols_to_fetch.append(sym)
                
                if symbols_to_fetch:
                    try:
                        # Fetch all tickers in a single network request
                        all_tickers = exchange.fetch_tickers(symbols_to_fetch)
                    except Exception as e:
                        print(f"⚠️ Report: Could not fetch tickers in batch, will use fallback. Error: {e}")
                        all_tickers = {}

                    with symbols_data_lock:
                        for sym in symbols_to_fetch:
                            # Ensure the symbol still exists in SYMBOLS_DATA
                            if sym not in SYMBOLS_DATA:
                                continue
                            
                            position = SYMBOLS_DATA[sym].get('position')
                            if not position or not isinstance(position, dict):
                                continue

                            current_price = position.get('buy_price') # Fallback price
                            if sym in all_tickers and all_tickers[sym].get('last') is not None:
                                current_price = all_tickers[sym]['last']
                            
                            if 'buy_price' in position and 'amount' in position:
                                open_positions_data[sym] = {
                                    'buy_price':    position['buy_price'],
                                    'current_price': current_price,
                                    'amount':        position['amount']
                                }
                            else:
                                print(f"⚠️ Report: Skipping {sym} due to incomplete position data.")

                # Only send report and update time if there are positions to report
                if open_positions_data:
                    send_positions_report(available, invested, active_count, MAX_POSITIONS, open_positions_data)
                    last_report_time = datetime.now() # Update time ONLY after sending

                # Auto-cleanup old data (every report interval)
                try:
                    if hasattr(storage, 'cleanup_old_data'):
                        storage.cleanup_old_data()
                except Exception as e:
                    print(f"⚠️ Cleanup error: {e}")

            # Memory Optimization
            try:
                cleanup_status = memory_optimizer.periodic_cleanup()
                if cleanup_status != "No cleanup needed":
                    pass  # Memory cleanup completed silently
            except Exception as e:
                print(f"⚠️ Memory optimizer error: {e}")

            # Risk / Anomaly / Pattern Reports (عند كل report interval)
            if should_send_report(last_report_time, REPORT_INTERVAL):
                risk_manager       = preloaded_advisors.get('RiskManager')
                anomaly_detector   = preloaded_advisors.get('AnomalyDetector')
                pattern_recognizer = preloaded_advisors.get('EnhancedPatternRecognition')

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
