"""
🤖 MSA Smart Trading Bot - Main File
Lightweight main loop that imports from organized modules
"""

# ========== AUTO-INSTALL ==========
def install_dependencies():
    import sys
    required = ['ccxt', 'cryptography', 'requests', 'pandas', 'ta', 'colorama']
    for package in required:
        try:
            __import__(package)
        except ImportError:
            print(f"📦 Installing {package}...")
            import subprocess
            subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                         shell=False, capture_output=True)

install_dependencies()

# ========== IMPORTS ==========
import ccxt
import time
import gc
from datetime import datetime, timedelta
from colorama import init, Fore, Style

# Config
from config_encrypted import get_api_keys, get_discord_webhook
from config import *

# Modules
from analysis import get_market_analysis, get_multi_timeframe_analysis, calculate_momentum
from trading import execute_buy, execute_sell, calculate_sell_value, should_sell_fast_tp, should_sell_bearish, should_sell_stop_loss, update_highest_price
from notifications import send_buy_notification, send_sell_notification, send_positions_report, send_startup_notification
from utils import calculate_dynamic_confidence, get_active_positions_count, get_total_invested, should_send_report, calculate_profit_percent, format_price
from storage import StorageManager

# AI Brain
AI_BOUNDARIES = {
    'min_confidence': 60,
    'max_confidence': 75,
    'min_volume': 0.8,
    'max_volume': 3.0,
    'min_amount': 10,
    'max_amount': 20,
    'max_loss_per_trade': 2.0,
    'max_daily_loss': 5.0
}

try:
    from ai_brain import AIBrain
    AI_ENABLED = True
except:
    AI_ENABLED = False

# Advanced Models
try:
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from models.multi_timeframe_analyzer import MultiTimeframeAnalyzer
    from models.risk_manager import RiskManager
    from models.coin_ranking_model import CoinRankingModel
    from models.anomaly_detector import AnomalyDetector
    from models.exit_strategy_model import ExitStrategyModel
    from models.enhanced_pattern_recognition import EnhancedPatternRecognition
    
    MODELS_ENABLED = True
except Exception as e:
    print(f"⚠️ Advanced models not loaded: {e}")
    MODELS_ENABLED = False

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

# AI Brain
ai_brain = AIBrain(AI_BOUNDARIES) if AI_ENABLED else None

# Advanced Models
if MODELS_ENABLED:
    mtf_analyzer = MultiTimeframeAnalyzer(exchange)
    risk_manager = RiskManager(storage)
    coin_ranker = CoinRankingModel(storage)
    anomaly_detector = AnomalyDetector(exchange)
    exit_strategy = ExitStrategyModel(storage)
    pattern_recognizer = EnhancedPatternRecognition(storage)
else:
    mtf_analyzer = None
    risk_manager = None
    coin_ranker = None
    anomaly_detector = None
    exit_strategy = None
    pattern_recognizer = None

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
print("        📊 6 Advanced Models Integrated")
print("        🧠 Multi-Timeframe + Risk Manager")
print("        🏆 Coin Ranking + Anomaly Detection")
print("        🎯 Exit Strategy + Pattern Recognition")
print("        📰 News Sentiment Analysis")
print("        ✅ Version 8.0 - AI + News Integration 🤖📰")
print("  ✦•······················•✦•······················•✦\n")
print("=" * 60)

# ========== LOAD POSITIONS ==========
SYMBOLS_DATA = init_symbols()
loaded = storage.load_positions()
for symbol, pos in loaded.items():
    if symbol in SYMBOLS_DATA:
        SYMBOLS_DATA[symbol]['position'] = pos
        print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")

print(f"\n🤖 Bot started!")
if ai_brain:
    print(f"🧠 AI Brain: ACTIVE")
else:
    print(f"⚙️ AI Brain: DISABLED")

if MODELS_ENABLED:
    print(f"📊 Multi-Timeframe Analyzer: ACTIVE")
    print(f"🛡️ Risk Manager: ACTIVE")
    print(f"🏆 Coin Ranking: ACTIVE")
    print(f"🚨 Anomaly Detector: ACTIVE")
    print(f"🎯 Exit Strategy: ACTIVE")
    print(f"🧠 Pattern Recognition: ACTIVE")

if NEWS_ENABLED:
    print(f"📰 News Sentiment Analyzer: ACTIVE")

print(f"💰 Boost: ${BASE_AMOUNT}-${BOOST_AMOUNT}")
print(f"🎯 TP: {TAKE_PROFIT_PERCENT}% | SL: {STOP_LOSS_PERCENT}%")
print(f"🎯 Min Confidence: {MIN_CONFIDENCE}/120")
print(f"🔺 Max Confidence: {AI_BOUNDARIES['max_confidence']}/120\n")

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
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'█' * 60}")
        print(f"  💼 Balance: ${available:.2f} | Invested: ${invested:.2f} | Active: {active_count}/{MAX_POSITIONS}")
        print(f"{'█' * 60}{Style.RESET_ALL}\n")
        
        # Process each symbol
        for symbol in SYMBOLS:
            symbol_data = SYMBOLS_DATA[symbol]
            position = symbol_data['position']
            
            # Get analysis
            analysis = get_market_analysis(exchange, symbol)
            if not analysis:
                if position:
                    print(f"⚠️ {symbol}: Analysis failed (has position)")
                continue
            
            current_price = analysis['close']
            
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
                if exit_strategy:
                    try:
                        exit_decision = exit_strategy.should_exit(
                            symbol, position, current_price, analysis, mtf
                        )
                        if exit_decision['action'] == 'SELL':
                            sell_decision = exit_decision
                            sell_reason = exit_decision['reason']
                            profit_percent = exit_decision['profit']
                    except Exception as e:
                        pass
                
                # AI Smart Sell (إذا Exit Strategy ما قرر)
                if not sell_decision and ai_brain:
                    mtf = get_multi_timeframe_analysis(exchange, symbol)
                    sell_decision = ai_brain.should_sell(symbol, position, current_price, analysis, mtf)
                    
                    if sell_decision['action'] == 'SELL':
                        sell_reason = sell_decision['reason']
                        profit_percent = sell_decision['profit']
                    elif sell_decision['action'] == 'HOLD':
                        # عرض المركز بتفاصيل كاملة
                        profit_emoji = "📈" if profit_percent > 0 else "📉"
                        print(f"{profit_emoji} {symbol:12} {format_price(current_price)} | Profit:{profit_percent:>+7.2f}% | Buy:{format_price(buy_price)} | High:{format_price(highest_price)} | {sell_decision['reason']}")
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
                                trade_result = {
                                    'symbol': symbol,
                                    'action': 'SELL',
                                    'profit_percent': profit_percent,
                                    'sell_reason': sell_reason,
                                    'tp_target': position.get('tp_target', 1.0),
                                    'sl_target': position.get('sl_target', 2.0),
                                    'max_wait_hours': position.get('max_wait_hours', 48),
                                    'hours_held': (datetime.now() - datetime.fromisoformat(position['buy_time'])).total_seconds() / 3600
                                }
                                
                                # إضافة ai_data إذا موجود
                                if 'ai_data' in position:
                                    trade_result.update(position['ai_data'])
                                
                                ai_brain.learn_from_trade(trade_result)
                            
                            # Exit Strategy Learning
                            if exit_strategy:
                                try:
                                    exit_strategy.learn_from_exit(symbol, {
                                        'profit_percent': profit_percent,
                                        'sell_reason': sell_reason,
                                        'hours_held': (datetime.now() - datetime.fromisoformat(position['buy_time'])).total_seconds() / 3600
                                    })
                                except:
                                    pass
                            
                            # Pattern Recognition Learning
                            if pattern_recognizer:
                                try:
                                    pattern_recognizer.learn_pattern({
                                        'symbol': symbol,
                                        'profit_percent': profit_percent,
                                        'features': position.get('ai_data', {})
                                    })
                                except:
                                    pass
                            
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
                
                if available < BASE_AMOUNT:
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
                        highest_price = df['high'].tail(12).max()
                        current_price = df['close'].iloc[-1]
                        drop_percent = ((highest_price - current_price) / highest_price) * 100
                        price_drop = {
                            'drop_percent': drop_percent,
                            'highest_1h': highest_price,
                            'current': current_price,
                            'confirmed': drop_percent >= 2.0
                        }
                except:
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
                    decision = ai_brain.should_buy(symbol, analysis, mtf, price_drop)
                    
                    # Apply all adjustments (including news)
                    total_adjustment = mtf_boost + coin_rank_adjustment + pattern_adjustment + news_adjustment
                    if total_adjustment != 0:
                        decision['confidence'] = min(75, max(60, decision['confidence'] + total_adjustment))
                    
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
            
            last_report_time = datetime.now()
        
        # Cleanup
        gc.collect()
        
        time.sleep(LOOP_SLEEP)

except KeyboardInterrupt:
    print("\n\n🛑 Bot stopped")
except Exception as e:
    print(f"\n❌ Error: {e}")
