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
from notifications import send_buy_notification, send_sell_notification, send_positions_report
from utils import calculate_dynamic_confidence, get_active_positions_count, get_total_invested, should_send_report, calculate_profit_percent
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
print("        💰 Binance Testnet - Priority System")
print("        📊 20 Coins | Smart Boost System")
print("        🧠 Auto-Adjust + Multi-Timeframe")
print("        🛡️ Loss Protection System")
print("        ⚡ Score-Based Investment")
print("        ✅ Version 6.0 - Smart & Bold 🧠⚡")
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
print(f"💰 Boost: ${BASE_AMOUNT}-${BOOST_AMOUNT}")
print(f"🎯 TP: {TAKE_PROFIT_PERCENT}% | SL: {STOP_LOSS_PERCENT}%")
print(f"🎯 Min Confidence: 60/120")
print(f"🔺 Max Confidence: 75/120\n")

last_report_time = datetime.now()

# ========== MAIN LOOP ==========
try:
    while True:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}\n⏰ {current_time}\n{'='*60}")
        
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
                
                # AI Smart Sell
                if ai_brain:
                    mtf = get_multi_timeframe_analysis(exchange, symbol)
                    sell_decision = ai_brain.should_sell(symbol, position, current_price, analysis, mtf)
                    
                    if sell_decision['action'] == 'SELL':
                        sell_reason = sell_decision['reason']
                        profit_percent = sell_decision['profit']
                    elif sell_decision['action'] == 'HOLD':
                        print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {sell_decision['reason']}")
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
                        print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | Hold")
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
                            if ai_brain and 'ai_data' in position:
                                trade_result = {
                                    'symbol': symbol,
                                    'profit_percent': profit_percent,
                                    'sell_reason': sell_reason,
                                    'tp_target': position.get('tp_target', 1.0),
                                    'sl_target': position.get('sl_target', 2.0),
                                    'max_wait_hours': position.get('max_wait_hours', 48),
                                    'hours_held': (datetime.now() - datetime.fromisoformat(position['buy_time'])).total_seconds() / 3600,
                                    **position['ai_data']
                                }
                                ai_brain.learn_from_trade(trade_result)
                            
                            symbol_data['position'] = None
                            storage.save_positions(SYMBOLS_DATA)
                else:
                    # Hold
                    print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | Hold")
            
            # ========== BUY LOGIC ==========
            else:
                if active_count >= MAX_POSITIONS:
                    continue
                
                if available < BASE_AMOUNT:
                    continue
                
                # Get MTF and calculate confidence
                mtf = get_multi_timeframe_analysis(exchange, symbol)
                
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
                
                # AI Decision
                if ai_brain:
                    decision = ai_brain.should_buy(symbol, analysis, mtf, price_drop)
                    if decision['action'] == 'BUY':
                        amount_usd = decision['amount']
                        print(f"{Fore.GREEN}🟢 BUY {symbol} 🧠 | AI Confidence:{decision['confidence']}/120 | ${amount_usd}{Style.RESET_ALL}")
                        
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
                        print(f"📊 {symbol:12} ${current_price:>8.2f} | AI: {decision['reason']}")
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
                        print(f"📊 {symbol:12} ${current_price:>8.2f} | Confidence:{confidence}/120 - SKIP")
        
        # Report
        if should_send_report(last_report_time, REPORT_INTERVAL):
            send_positions_report(available, invested, active_count, MAX_POSITIONS)
            last_report_time = datetime.now()
        
        # Cleanup
        gc.collect()
        
        time.sleep(LOOP_SLEEP)

except KeyboardInterrupt:
    print("\n\n🛑 Bot stopped")
except Exception as e:
    print(f"\n❌ Error: {e}")
