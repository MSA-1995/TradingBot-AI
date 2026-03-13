"""
🤖 MSA Smart Trading Bot - Main File
Lightweight main loop that imports from organized modules
"""

# ========== AUTO-INSTALL ==========
# Disabled - Koyeb installs from requirements.txt
# def install_dependencies():
#     pass

# install_dependencies()

# ========== IMPORTS ==========
import ccxt
import time
import gc
from datetime import datetime, timedelta
from colorama import init, Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Config
from config_encrypted import get_api_keys, get_discord_webhook
from config import *

# Modules
from analysis import get_market_analysis, get_multi_timeframe_analysis, calculate_momentum
from trading import execute_buy, execute_sell, calculate_sell_value, should_sell_fast_tp, should_sell_bearish, should_sell_stop_loss, update_highest_price
from notifications import send_buy_notification, send_sell_notification, send_positions_report, send_startup_notification
from utils import calculate_dynamic_confidence, get_active_positions_count, get_total_invested, should_send_report, calculate_profit_percent, format_price
from storage import StorageManager
from coin_scanner import CoinScanner  # نظام الفحص الديناميكي
from capital_manager import CapitalManager  # إدارة رأس المال

# Smart AI (الذكاء الحقيقي)
try:
    from models.smart_ai import SmartAI
    ai_brain = SmartAI()
    AI_ENABLED = ai_brain.enabled
    print(f"🧠 Smart AI: {'ACTIVE' if AI_ENABLED else 'Training mode'}")
except Exception as e:
    print(f"❌ Smart AI failed to load: {e}")
    ai_brain = None
    AI_ENABLED = False

# Advanced Models (معطل - توفير ذاكرة)
MODELS_ENABLED = False
mtf_analyzer = None
risk_manager = None
coin_ranker = None
anomaly_detector = None
exit_strategy = None
pattern_recognizer = None

# News Analyzer
try:
    from news_analyzer import NewsAnalyzer
    news_analyzer = NewsAnalyzer()
    NEWS_ENABLED = news_analyzer.enabled
except Exception as e:
    print(f"⚠️ News Analyzer not loaded: {e}")
    news_analyzer = None
    NEWS_ENABLED = False

init(autoreset=True)

# ========== SETUP ==========
API_KEY, SECRET_KEY = get_api_keys()
if not API_KEY:
    print("❌ Failed to decrypt keys")
    exit()

DISCORD_WEBHOOK = get_discord_webhook()

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
})
exchange.set_sandbox_mode(True)

# Storage
storage = StorageManager()

# Capital Manager
capital_manager = CapitalManager(max_capital=MAX_CAPITAL, profit_reserve=PROFIT_RESERVE)

# Dynamic Coin Scanner
coin_scanner = CoinScanner(exchange, ai_brain, None, None)
coin_scanner.start()

# Threading للتحليل السريع
analysis_lock = threading.Lock()
analysis_results = {}

def analyze_symbol_threaded(symbol, exchange, symbols_data):
    """تحليل العملة في Thread منفصل"""
    try:
        symbol_data = symbols_data.get(symbol, {'position': None})
        position = symbol_data['position']
        
        # Get analysis
        analysis = get_market_analysis(exchange, symbol)
        if not analysis:
            return {'symbol': symbol, 'status': 'failed', 'has_position': position is not None}
        
        current_price = analysis['close']
        
        return {
            'symbol': symbol,
            'status': 'success',
            'analysis': analysis,
            'current_price': current_price,
            'position': position,
            'symbol_data': symbol_data
        }
    except Exception as e:
        return {'symbol': symbol, 'status': 'error', 'error': str(e), 'has_position': position is not None}

# ========== BANNER ==========
print("=" * 60)
print("\n  ███╗   ███╗███████╗ █████╗ ")
print("  ████╗ ████║██╔════╝██╔══██╗")
print("  ██╔████╔██║███████╗███████║")
print("  ██║╚██╔╝██║╚════██║██╔══██║")
print("  ██║ ╚═╝ ██║███████║██║  ██║")
print("  ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝\n")
print("  ✦•······················•✦•······················•✦")
print("        🚀 MSA Smart Trading Bot")
print("        💰 Binance Testnet - AI Powered")
print("        🧠 Smart AI (Neural Network)")
print("        📰 News Sentiment Analysis")
print("        🔍 Dynamic Coin Scanner (995 Coins)")
print("        💰 Capital Management System")
print("        ✅ Version 10.0 - Smart AI 🧠")
print("  ✦•······················•✦•······················•✦\n")
print("=" * 60)

# ========== LOAD POSITIONS ==========
# استخدام قائمة ديناميكية بدل SYMBOLS الثابتة
def get_dynamic_symbols():
    """الحصول على القائمة الديناميكية + الصفقات المفتوحة"""
    # الصفقات المفتوحة (أولوية - يجب عرضها دائماً)
    open_positions = [symbol for symbol, data in SYMBOLS_DATA.items() if data.get('position')]
    
    # القائمة الديناميكية من Scanner
    top_coins = coin_scanner.get_top_coins()
    dynamic_symbols = [coin for coin, score in top_coins]
    
    # دمج القوائم (الصفقات المفتوحة أولاً، ثم الديناميكية)
    all_symbols = open_positions + [symbol for symbol in dynamic_symbols if symbol not in open_positions]
    
    return all_symbols

SYMBOLS_DATA = init_symbols()
loaded = storage.load_positions()
for symbol, pos in loaded.items():
    if symbol in SYMBOLS_DATA:
        SYMBOLS_DATA[symbol]['position'] = pos
        print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")
    else:
        # إضافة الصفقة المفتوحة للقائمة
        SYMBOLS_DATA[symbol] = {'position': pos}
        print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f} (not in top 20)")

print(f"\n🤖 Bot started!")

# Auto-train Smart AI if not trained yet
if ai_brain and not ai_brain.enabled:
    print("\n🎓 Smart AI not trained yet - Starting initial training...")
    try:
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, 'simple_ai_trainer.py'],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            print("✅ Initial training completed!")
            # إعادة تحميل Smart AI
            from smart_ai import SmartAI
            ai_brain = SmartAI()
            AI_ENABLED = ai_brain.enabled
            if AI_ENABLED:
                print("🧠 Smart AI: NOW ACTIVE")
            else:
                print("❌ Training failed - not enough data")
                print("   Bot will collect data and train automatically")
        else:
            print(f"⚠️ Training failed: {result.stderr}")
            print("   Bot will collect data and train automatically")
    except Exception as e:
        print(f"⚠️ Auto-training error: {e}")
        print("   Bot will collect data and train automatically")

if ai_brain and ai_brain.enabled:
    print(f"🧠 Active AI: Smart AI (Neural Network) ✅")
elif ai_brain:
    print(f"📊 Active AI: Learning Mode (Collecting data...)")
else:
    print(f"❌ AI: DISABLED - Check errors above")

if NEWS_ENABLED:
    print(f"📰 News Sentiment Analyzer: ACTIVE")

print(f"💰 Trade Amount: ${BASE_AMOUNT}-${BOOST_AMOUNT}")
print(f"🎯 TP: {TAKE_PROFIT_PERCENT}% | SL: {STOP_LOSS_PERCENT}%")
print(f"💰 Max Capital: ${MAX_CAPITAL} | Profit Reserve: {PROFIT_RESERVE}\n")

# Send startup notification to Discord
send_startup_notification()

last_report_time = datetime.now()

# ========== MAIN LOOP ==========
try:
    loop_count = 0
    
    while True:
        loop_count += 1
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}\n⏰ {current_time}\n{'='*60}")
        
        # Update coin rankings every 10 loops (~100 seconds)
        if coin_ranker and loop_count % 10 == 1:
            try:
                print("\n🏆 Updating coin rankings...")
                rankings = coin_ranker.rank_all_coins(SYMBOLS)
                if rankings:
                    top_5 = coin_ranker.get_top_coins(5)
                    print(f"🌟 Top 5 Coins:")
                    for coin in top_5:
                        print(f"  {coin['rank']}. {coin['symbol']:12} | Score:{coin['score']:>5.1f} | WR:{coin['win_rate']:>5.1f}% | {coin['recommendation']}")
            except Exception as e:
                print(f"⚠️ Ranking error: {e}")
        
        # Balance
        try:
            balance = exchange.fetch_balance()
            available = balance['USDT']['free']
        except:
            available = 0
        
        active_count = get_active_positions_count(SYMBOLS_DATA)
        invested = get_total_invested(SYMBOLS_DATA)
        
        # Capital Management
        capital_status = capital_manager.get_tradable_balance(available, invested)
        tradable_balance = capital_status['tradable']
        locked_profit = capital_status['locked_profit']
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'█' * 60}")
        print(f"  💼 Balance: ${available:.2f} | Invested: ${invested:.2f} | Active: {active_count}/{MAX_POSITIONS}")
        if locked_profit > 0:
            print(f"  🔒 Locked Profit: ${locked_profit:.2f} | ✅ Tradable: ${tradable_balance:.2f}")
        else:
            print(f"  ✅ Tradable: ${tradable_balance:.2f} | Max Capital: ${MAX_CAPITAL}")
        print(f"{'█' * 60}{Style.RESET_ALL}\n")
        
        # عرض القائمة الديناميكية + الصفقات المفتوحة
        top_coins = coin_scanner.get_top_coins()
        hot_opps = coin_scanner.get_hot_opportunities()
        scan_status = coin_scanner.get_scan_status()
        
        # عرض أفضل 10 عملات للمراقبة (ديناميكية - تتغير حسب الأداء)
        if top_coins:
            monitoring_coins = [coin for coin, score in top_coins if coin not in open_positions]
            if monitoring_coins:
                display_count = min(10, len(monitoring_coins))  # أفضل 10 أو أقل إذا كان العدد أقل
                print(f"{Fore.YELLOW}🔍 Top {display_count} Best Coins (Dynamic):{Style.RESET_ALL}")
                
                displayed = 0
                for i, (symbol, score) in enumerate(top_coins, 1):
                    if symbol not in open_positions and displayed < 10:
                        print(f"  {displayed+1:2}. {symbol:12} | Score:{score:>5.0f}")
                        displayed += 1
                
                if len(monitoring_coins) > 10:
                    print(f"  ... and {len(monitoring_coins)-10} more coins being monitored")
            
            # آخر فحص
            if scan_status['last_deep_scan']:
                elapsed = (datetime.now() - scan_status['last_deep_scan']).total_seconds() / 60
                print(f"  📊 Last deep scan: {elapsed:.0f}min ago")
        
        print()
        
        # الحصول على القائمة الديناميكية
        current_symbols = get_dynamic_symbols()
        
        # تحليل متعدد الخيوط (Threading)
        print(f"📊 Analyzing {len(current_symbols)} coins with threading...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # إرسال جميع العملات للتحليل
            future_to_symbol = {
                executor.submit(analyze_symbol_threaded, symbol, exchange, SYMBOLS_DATA): symbol 
                for symbol in current_symbols
            }
            
            # جمع النتائج
            analysis_results = []
            for future in as_completed(future_to_symbol):
                result = future.result()
                analysis_results.append(result)
        
        print(f"✅ Analysis complete! Processing {len(analysis_results)} results...")
        
        # Process results
        for result in analysis_results:
            if result['status'] != 'success':
                if result.get('has_position'):
                    print(f"⚠️ {result['symbol']}: Analysis failed (has position)")
                continue
            
            symbol = result['symbol']
            analysis = result['analysis']
            current_price = result['current_price']
            position = result['position']
            symbol_data = result['symbol_data']
            
            # إضافة العملة للقائمة إذا مو موجودة
            if symbol not in SYMBOLS_DATA:
                SYMBOLS_DATA[symbol] = symbol_data
            
            # ========== SELL LOGIC ==========
            if position:
                buy_price = position['buy_price']
                amount = position['amount']
                highest_price = position.get('highest_price', buy_price)
                
                # Update highest
                highest_price = update_highest_price(current_price, highest_price)
                position['highest_price'] = highest_price
                
                profit_percent = calculate_profit_percent(current_price, buy_price)
                
                # Check sell conditions
                sell_decision = None
                
                # Exit Strategy Model (أولوية)
                mtf = None
                if exit_strategy:
                    try:
                        mtf = get_multi_timeframe_analysis(exchange, symbol)
                        exit_decision = exit_strategy.should_exit(
                            symbol, position, current_price, analysis, mtf
                        )
                        if exit_decision and exit_decision.get('action') == 'SELL':
                            sell_decision = exit_decision
                            sell_reason = exit_decision.get('reason', 'Exit Strategy')
                            profit_percent = exit_decision.get('profit', profit_percent)
                    except Exception as e:
                        print(f"⚠️ Exit Strategy error {symbol}: {e}")
                        pass
                
                # AI Smart Sell (إذا Exit Strategy ما قرر)
                if not sell_decision and ai_brain:
                    if mtf is None:
                        mtf = get_multi_timeframe_analysis(exchange, symbol)
                    
                    sell_decision = ai_brain.should_sell(symbol, position, current_price, analysis, mtf)
                    
                    if sell_decision and sell_decision.get('action') == 'SELL':
                        sell_reason = sell_decision.get('reason', 'AI Sell')
                        profit_percent = sell_decision.get('profit', profit_percent)
                    elif sell_decision and sell_decision.get('action') == 'HOLD':
                        # عرض المركز بتفاصيل كاملة
                        profit_emoji = "📈" if profit_percent > 0 else "📉"
                        print(f"{profit_emoji} {symbol:12} {format_price(current_price)} | Profit:{profit_percent:>+7.2f}% | Buy:{format_price(buy_price)} | High:{format_price(highest_price)} | {sell_decision.get('reason', 'Hold')}")
                        continue
                else:
                    # Manual sell logic
                    sell_reason = None
                    
                    # 1. Fast TP
                    should_sell, profit = should_sell_fast_tp(current_price, buy_price, position.get('partial_sold', False), TAKE_PROFIT_PERCENT)
                    if should_sell:
                        sell_reason = f"FAST TP"
                    
                    # 2. Bearish trend
                    if not sell_reason:
                        if mtf is None:
                            mtf = get_multi_timeframe_analysis(exchange, symbol)
                        should_sell, profit = should_sell_bearish(mtf, current_price, buy_price)
                        if should_sell:
                            sell_reason = "BEARISH TREND"
                    
                    # 3. Stop loss
                    if not sell_reason:
                        should_sell, profit, reason = should_sell_stop_loss(current_price, highest_price, buy_price, STOP_LOSS_PERCENT)
                        if should_sell:
                            sell_reason = reason
                    
                    if not sell_reason:
                        # عرض المركز بتفاصيل كاملة
                        profit_emoji = "📈" if profit_percent > 0 else "📉"
                        print(f"{profit_emoji} {symbol:12} {format_price(current_price)} | Profit:{profit_percent:>+7.2f}% | Buy:{format_price(buy_price)} | High:{format_price(highest_price)} | Hold")
                        continue
                
                # Execute sell
                if sell_reason:
                    sell_value = calculate_sell_value(amount, current_price)
                    
                    if sell_value < 9.99:
                        print(f"{Fore.YELLOW}⏳ {symbol} | {sell_reason} but value ${sell_value:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}🔴 SELL {symbol} | {sell_reason} | Profit: {profit_percent:+.2f}%{Style.RESET_ALL}")
                        
                        result = execute_sell(exchange, symbol, amount, sell_reason)
                        if result['success']:
                            send_sell_notification(symbol, amount, current_price, sell_value, profit_percent, sell_reason)
                            
                            # AI Learning - يتعلم من كل شيء
                            if ai_brain:
                                try:
                                    # حماية كاملة من None
                                    safe_profit = 0
                                    try:
                                        if profit_percent is not None and isinstance(profit_percent, (int, float)):
                                            safe_profit = float(profit_percent)
                                    except:
                                        safe_profit = 0
                                    
                                    # حساب hours_held بحماية من None
                                    hours_held = 24  # default
                                    try:
                                        if position.get('buy_time'):
                                            hours_held = (datetime.now() - datetime.fromisoformat(position['buy_time'])).total_seconds() / 3600
                                    except:
                                        hours_held = 24
                                    
                                    trade_result = {
                                        'symbol': symbol,
                                        'action': 'SELL',
                                        'profit_percent': safe_profit,
                                        'sell_reason': sell_reason if sell_reason else 'Unknown',
                                        'tp_target': position.get('tp_target', 1.0),
                                        'sl_target': position.get('sl_target', 2.0),
                                        'max_wait_hours': position.get('max_wait_hours', 48),
                                        'hours_held': hours_held
                                    }
                                    
                                    # إضافة ai_data إذا موجود
                                    if 'ai_data' in position:
                                        trade_result.update(position['ai_data'])
                                    
                                    ai_brain.learn_from_trade(trade_result)
                                except Exception as e:
                                    print(f"⚠️ AI Learning error: {e}")
                            
                            # Exit Strategy Learning
                            if exit_strategy:
                                try:
                                    # حماية من None
                                    safe_profit = 0
                                    try:
                                        if profit_percent is not None and isinstance(profit_percent, (int, float)):
                                            safe_profit = float(profit_percent)
                                    except:
                                        safe_profit = 0
                                    
                                    # حساب hours_held بحماية من None
                                    hours_held = 24  # default
                                    try:
                                        if position.get('buy_time'):
                                            hours_held = (datetime.now() - datetime.fromisoformat(position['buy_time'])).total_seconds() / 3600
                                    except:
                                        hours_held = 24
                                    
                                    exit_strategy.learn_from_exit(symbol, {
                                        'profit_percent': safe_profit,
                                        'sell_reason': sell_reason if sell_reason else 'Unknown',
                                        'hours_held': hours_held
                                    })
                                except Exception as e:
                                    print(f"⚠️ Exit Strategy Learning error: {e}")
                            
                            # Pattern Recognition Learning
                            if pattern_recognizer:
                                try:
                                    # حماية من None
                                    safe_profit = 0
                                    try:
                                        if profit_percent is not None and isinstance(profit_percent, (int, float)):
                                            safe_profit = float(profit_percent)
                                    except:
                                        safe_profit = 0
                                    
                                    pattern_recognizer.learn_pattern({
                                        'symbol': symbol,
                                        'profit_percent': safe_profit,
                                        'features': position.get('ai_data', {})
                                    })
                                except Exception as e:
                                    print(f"⚠️ Pattern Learning error: {e}")
                            
                            symbol_data['position'] = None
                            storage.save_positions(SYMBOLS_DATA)
                else:
                    # Hold - عرض المركز بتفاصيل كاملة
                    profit_emoji = "📈" if profit_percent > 0 else "📉"
                    print(f"{profit_emoji} {symbol:12} {format_price(current_price)} | Profit:{profit_percent:>+7.2f}% | Buy:{format_price(buy_price)} | High:{format_price(highest_price)} | Hold")
            
            # ========== BUY LOGIC ==========
            else:
                if active_count >= MAX_POSITIONS:
                    continue
                
                # Capital Management Check
                can_trade, reason = capital_manager.can_trade(BASE_AMOUNT, available, invested)
                if not can_trade:
                    continue
                
                # Get MTF and calculate confidence
                mtf = get_multi_timeframe_analysis(exchange, symbol)
                
                # Advanced MTF Analysis
                mtf_boost = 0
                if mtf_analyzer:
                    try:
                        mtf_analysis = mtf_analyzer.analyze(symbol)
                        if mtf_analysis:
                            mtf_boost = mtf_analysis.get('confidence_boost', 0) or 0
                            entry_point = mtf_analyzer.get_best_entry_point(symbol)
                            if entry_point and entry_point.get('entry') == 'EXCELLENT':
                                mtf_boost += 5
                    except Exception as e:
                        print(f"⚠️ MTF error {symbol}: {e}")
                        mtf_boost = 0
                
                # Calculate price drop
                price_drop = {'drop_percent': 0, 'confirmed': False}
                try:
                    df = analysis['df']
                    if len(df) >= 12:
                        highest_price_1h = df['high'].tail(12).max()
                        current_price_df = df['close'].iloc[-1]
                        
                        # حماية من None
                        if highest_price_1h is not None and current_price_df is not None and highest_price_1h > 0:
                            drop_percent = ((highest_price_1h - current_price_df) / highest_price_1h) * 100
                            price_drop = {
                                'drop_percent': drop_percent,
                                'highest_1h': highest_price_1h,
                                'current': current_price_df,
                                'confirmed': drop_percent >= 2.0
                            }
                except Exception as e:
                    pass
                
                confidence, reasons = calculate_dynamic_confidence(analysis, mtf)
                
                # News Sentiment Check
                news_adjustment = 0
                news_summary = "No news"
                if news_analyzer and NEWS_ENABLED:
                    try:
                        # تجنب العملة إذا الأخبار سلبية جداً
                        if news_analyzer.should_avoid_coin(symbol, hours=24):
                            print(f"📰❌ {symbol:12} | SKIP: Negative news sentiment")
                            continue
                        
                        # حساب News Boost
                        news_adjustment = news_analyzer.get_news_confidence_boost(symbol, hours=24) or 0
                        news_summary = news_analyzer.get_news_summary(symbol, hours=24) or "No news"
                    except Exception as e:
                        news_adjustment = 0
                        news_summary = "No news"
                
                # Coin Ranking Check
                coin_rank_adjustment = 0
                if coin_ranker:
                    try:
                        should_trade = coin_ranker.should_trade_coin(symbol)
                        if not should_trade['trade']:
                            print(f"❌ {symbol:12} | SKIP: {should_trade['reason']}")
                            continue
                        coin_rank_adjustment = should_trade.get('confidence_adjustment', 0) or 0
                    except Exception as e:
                        coin_rank_adjustment = 0
                
                # Anomaly Detection
                if anomaly_detector:
                    try:
                        anomaly_result = anomaly_detector.detect_anomalies(symbol, analysis)
                        if not anomaly_result['safe_to_trade']:
                            print(f"🚨 {symbol:12} | ANOMALY: {anomaly_result['severity']} - SKIP")
                            continue
                    except Exception as e:
                        pass
                
                # Pattern Recognition
                pattern_adjustment = 0
                if pattern_recognizer:
                    try:
                        pattern_analysis = pattern_recognizer.analyze_entry_pattern(
                            symbol, analysis, mtf, price_drop
                        )
                        if pattern_analysis:
                            if pattern_analysis.get('recommendation') == 'AVOID':
                                print(f"⚠️ {symbol:12} | PATTERN: {pattern_analysis['recommendation']} - SKIP")
                                continue
                            pattern_adjustment = pattern_analysis.get('confidence_adjustment', 0) or 0
                    except Exception as e:
                        pattern_adjustment = 0
                
                # AI Decision
                if ai_brain:
                    # جمع news_sentiment
                    news_sentiment_value = None
                    if news_analyzer and NEWS_ENABLED:
                        try:
                            news_sentiment_value = news_analyzer.get_news_confidence_boost(symbol, hours=24)
                        except:
                            news_sentiment_value = None
                    
                    decision = ai_brain.should_buy(symbol, analysis, mtf, price_drop, news_sentiment_value)
                    
                    # Apply all adjustments (including news) - with None protection
                    try:
                        # Ensure all adjustments are numbers
                        mtf_boost = 0 if mtf_boost is None else mtf_boost
                        coin_rank_adjustment = 0 if coin_rank_adjustment is None else coin_rank_adjustment
                        pattern_adjustment = 0 if pattern_adjustment is None else pattern_adjustment
                        news_adjustment = 0 if news_adjustment is None else news_adjustment
                        
                        total_adjustment = mtf_boost + coin_rank_adjustment + pattern_adjustment + news_adjustment
                        if total_adjustment != 0:
                            decision['confidence'] = min(75, max(60, decision['confidence'] + total_adjustment))
                    except Exception as e:
                        print(f"⚠️ Adjustment error {symbol}: {e}")
                        total_adjustment = 0
                    
                    if decision['action'] == 'BUY':
                        # Risk Manager - Calculate optimal amount
                        if risk_manager:
                            try:
                                optimal_amount = risk_manager.get_position_size(
                                    symbol, 
                                    decision['confidence'], 
                                    available + invested,
                                    MAX_POSITIONS
                                )
                                amount_usd = optimal_amount
                            except:
                                amount_usd = decision['amount']
                        else:
                            amount_usd = decision['amount']
                        
                        news_display = f" | {news_summary}" if news_adjustment != 0 else ""
                        print(f"{Fore.GREEN}🟢 BUY {symbol} 🧠 | AI Confidence:{decision['confidence']}/120 | ${amount_usd}{news_display}{Style.RESET_ALL}")
                        
                        result = execute_buy(exchange, symbol, amount_usd, current_price, decision['confidence'])
                        if result['success']:
                            send_buy_notification(symbol, result['amount'], current_price, amount_usd, decision['confidence'])
                            
                            symbol_data['position'] = {
                                'buy_price': result['price'],
                                'amount': result['amount'],
                                'highest_price': result['price'],
                                'buy_time': datetime.now().isoformat(),
                                'tp_target': decision.get('tp_target', 1.0),
                                'sl_target': decision.get('sl_target', 2.0),
                                'max_wait_hours': decision.get('max_wait_hours', 48),
                                'ai_data': {
                                    'confidence': decision['confidence'],
                                    'rsi': analysis['rsi'],
                                    'volume': analysis['volume'],
                                    'macd_diff': analysis['macd_diff']
                                }
                            }
                            active_count += 1
                            available -= amount_usd
                            storage.save_positions(SYMBOLS_DATA)
                    else:
                        # عرض التفاصيل حتى لو فشل AI
                        rsi = analysis.get('rsi', 0)
                        volume = analysis.get('volume_ratio', 0)
                        macd = analysis.get('macd_diff', 0)
                        
                        vol_status = "🟢" if volume > 0.8 else "🔴"
                        news_display = f" | {news_summary}" if NEWS_ENABLED else ""
                        print(f"📊 {symbol:12} ${current_price:>8.2f} | RSI:{rsi:>5.1f} | Vol:{vol_status} {volume:.1f}x | MACD:{macd:>+6.1f} | Conf:{decision['confidence']}/120{news_display} | {decision['reason']}")
                else:
                    # Manual mode
                    if confidence >= MIN_CONFIDENCE:
                        amount_usd = BASE_AMOUNT
                        print(f"{Fore.GREEN}🟢 BUY {symbol} | Confidence:{confidence}/120 | ${amount_usd}{Style.RESET_ALL}")
                        
                        result = execute_buy(exchange, symbol, amount_usd, current_price, confidence)
                        if result['success']:
                            send_buy_notification(symbol, result['amount'], current_price, amount_usd, confidence)
                            
                            symbol_data['position'] = {
                                'buy_price': result['price'],
                                'amount': result['amount'],
                                'highest_price': result['price'],
                                'buy_time': datetime.now().isoformat()
                            }
                            active_count += 1
                            available -= amount_usd
                            storage.save_positions(SYMBOLS_DATA)
                    else:
                        # عرض التحليل للعملات بدون مراكز
                        rsi = analysis.get('rsi', 0)
                        volume = analysis.get('volume_ratio', 0)
                        macd = analysis.get('macd_diff', 0)
                        
                        vol_status = "🟢" if volume > 0.8 else "🔴"
                        print(f"📊 {symbol:12} ${current_price:>8.2f} | RSI:{rsi:>5.1f} | Vol:{vol_status} {volume:.1f}x | MACD:{macd:>+6.1f} | Conf:{confidence}/120")
        
        # Report
        if should_send_report(last_report_time, REPORT_INTERVAL):
            send_positions_report(available, invested, active_count, MAX_POSITIONS)
            
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
                        
                        # Check if should stop trading
                        stop_check = risk_manager.should_stop_trading()
                        if stop_check['stop']:
                            print(f"\n⚠️ {Fore.RED}RISK ALERT: {stop_check['reason']}{Style.RESET_ALL}")
                            print(f"Severity: {stop_check['severity']}")
                            if stop_check['severity'] == 'CRITICAL':
                                print(f"🛑 Stopping bot for safety...")
                                break
                except Exception as e:
                    print(f"⚠️ Risk report error: {e}")
            
            # Coin Ranking Report
            if coin_ranker:
                try:
                    ranking_report = coin_ranker.get_ranking_report()
                    if ranking_report:
                        print(f"\n🏆 Coin Ranking Report:")
                        print(f"  Total Coins: {ranking_report['total_coins']}")
                        print(f"  Strong Buy: {ranking_report['strong_buy_count']}")
                        print(f"  Avoid: {ranking_report['avoid_count']}")
                        print(f"  Avg Win Rate: {ranking_report['avg_win_rate']:.1f}%")
                except Exception as e:
                    print(f"⚠️ Ranking report error: {e}")
            
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
            
            # Smart AI Statistics
            if ai_brain and ai_brain.enabled:
                try:
                    ai_stats = ai_brain.get_statistics()
                    if ai_stats:
                        print(f"\n🧠 Smart AI Statistics:")
                        print(f"  Total Predictions: {ai_stats['total_predictions']}")
                        print(f"  Correct: {ai_stats['correct']}")
                        print(f"  Accuracy: {ai_stats['accuracy']:.1f}%")
                        print(f"  Status: {'ACTIVE' if ai_stats['enabled'] else 'TRAINING'}")
                except Exception as e:
                    print(f"⚠️ Smart AI stats error: {e}")
            
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
    import time
    time.sleep(5)
