"""
🤖 MSA Smart Trading Bot - Main File
Lightweight main loop that imports from organized modules
"""

# ========== LOAD ENV FILE ==========
from dotenv import load_dotenv
import os
import sys
import logging

# ========== LOGGING SETUP ==========
logging.basicConfig(
    filename='bot_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# إضافة المسار الرئيسي للمشروع حتى يتعرف على مجلدات models و memory
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# ابحث عن ملف .env في المجلد الحالي أو المجلدات الأعلى
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    print("[OK] Environment variables loaded from root .env file")
else:
    load_dotenv()
    print("[OK] Environment variables loaded")

# ========== IMPORTS ==========
import ccxt
import time
from datetime import datetime, timezone
from colorama import init, Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Config
from config_encrypted import get_api_keys, get_discord_webhook

# ✅ استيراد صريح بدل Wildcard
from config import (
    MAX_CAPITAL,
    PROFIT_RESERVE,
    MAX_POSITIONS,
    MIN_TRADE_AMOUNT,
    SYMBOLS,
    MEMORY_CLEANUP_INTERVAL,
    MEMORY_USAGE_THRESHOLD,
    init_symbols
)

# ✅ قيمة ثابتة - انقلها لـ config.py لاحقاً
MIN_SELL_VALUE = 10.0
COOLDOWN_MINUTES = 15

# Modules
from analysis import get_market_analysis
from notifications import send_buy_notification, send_sell_notification, send_positions_report
from utils import (
    execute_buy,
    execute_sell,
    calculate_sell_value,
    calculate_dynamic_confidence,
    get_active_positions_count,
    get_total_invested,
    should_send_report,
    calculate_profit_percent,
    format_price
)
from storage import StorageManager
from capital_manager import CapitalManager
from external_apis import ExternalAPIClient

# Advisor Manager
from bot.advisor_manager import AdvisorManager
MODELS_ENABLED = True

from memory.memory_optimizer import MemoryOptimizer

# ========== META (THE KING) ==========
META_CLASS = None
META_ENABLED = False

try:
    from meta import Meta
    META_CLASS = Meta
    META_ENABLED = True
except Exception as e:
    print(f"⚠️ Meta module not loaded: {e}")

init(autoreset=True)

# ========== SETUP ==========
API_KEY, SECRET_KEY = get_api_keys()
if not API_KEY:
    print("❌ Failed to decrypt keys")
    exit()

DISCORD_WEBHOOK = get_discord_webhook()

exchange_config = {
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'timeout': 5000,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
}

exchange = ccxt.binance(exchange_config)
exchange.set_sandbox_mode(True)

# ========== STORAGE ==========
storage = StorageManager()

test_conn = None
try:
    test_conn = storage.storage._get_conn()
    if not test_conn or test_conn.closed:
        print("❌ Database: Connection failed")
except Exception as e:
    logging.error(f"Database connection error: {e}", exc_info=True)
    print(f"❌ Database: Connection error - {e}")
finally:
    if test_conn:
        test_conn.rollback()
        storage.storage._put_conn(test_conn)

storage.print_cache_stats()

# ========== DEEP LEARNING ==========
DL_ENABLED = False
dl_client = None

try:
    from src.dl_client_v2 import DeepLearningClientV2
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        dl_client = DeepLearningClientV2(database_url, load_models=True)
        DL_ENABLED = True
        print("✅ DeepLearningClientV2 created successfully")
    else:
        print("⚠️ No DATABASE_URL, Deep Learning disabled")
except Exception as e:
    logging.error(f"Failed to load Deep Learning Client: {e}", exc_info=True)
    print(f"❌ Failed to load Deep Learning Client: {e}")

# ========== CAPITAL MANAGER ==========
capital_manager = CapitalManager(max_capital=MAX_CAPITAL, profit_reserve=PROFIT_RESERVE)

# ========== EXTERNAL APIs ==========
external_client = ExternalAPIClient()

if os.getenv("NEWS_API_KEY") and os.getenv("WHALE_ALERT_API_KEY"):
    print("✅ External APIs: Authentication Successful")
else:
    print("⚠️ External APIs: Some keys are missing in .env")

# ========== LOAD DEEP LEARNING MODELS ==========
if dl_client:
    DL_ENABLED = dl_client.is_available()

    if DL_ENABLED:
        if hasattr(dl_client._models, 'cache'):
            loaded_models = len(dl_client._models.cache)
        else:
            loaded_models = len([m for m in dl_client._models.values() if m is not None])

        if loaded_models > 0:
            print(f"🧠 Deep Learning: {loaded_models}/12 models loaded successfully")
        else:
            print("⚠️ Deep Learning: Models not trained yet")
            DL_ENABLED = False

# ========== ADVISOR MANAGER ==========
advisor_manager = AdvisorManager(
    storage=storage,
    capital_manager=capital_manager,
    exchange=exchange,
    dl_client=dl_client
)

# ========== MEMORY OPTIMIZER ==========
memory_optimizer = MemoryOptimizer(
    cleanup_interval=MEMORY_CLEANUP_INTERVAL,
    memory_threshold=MEMORY_USAGE_THRESHOLD
)

# ========== META INIT ==========
meta = None
if META_ENABLED:
    meta = META_CLASS(advisor_manager, storage)

# ========== BANNER ==========
print("")
print("")
C = "\033[1;36m"
G = "\033[1;32m"
Y = "\033[1;33m"
W = "\033[1;37m"
P = "\033[1;35m"
R = "\033[0m"
print(f"{C}   ·•● MSA ●•·{R}")
print("")
print(f"{C}    ███╗   ███╗ ███████╗  █████╗{R}")
print(f"{C}    ████╗ ████║ ██╔════╝ ██╔══██╗{R}")
print(f"{W}    ██╔████╔██║ ███████╗ ███████║{R}")
print(f"{W}    ██║╚██╔╝██║ ╚════██║ ██╔══██║{R}")
print(f"{C}    ██║ ╚═╝ ██║ ███████║ ██║  ██║{R}")
print(f"{C}    ╚═╝     ╚═╝ ╚══════╝ ╚═╝  ╚═╝{R}")
print("")
print(f"{W}    Smart Trading Bot {Y}V5.1{R}")
print(f"{C}    ── 9-State Matrix · Smart Decision Engine ──{R}")
print("")
print(f"   {G}🧠{W} 12 AI Models · Symbol Memory & Learning{R}")
print(f"   {Y}👑{W} Meta King · 49 Features + Symbol Memory{R}")
print(f"   {C}📊{W} Deep Learning · 9-State Market Matrix{R}")
print(f"   {P}🎯{W} Loss/Profit Spike Catcher · Fibonacci Guard{R}")
print(f"   {Y}💎{W} 20 Coins · Smart Entry & Exit{R}")
print("")
print(f"   {G}⚡ All Systems Online{R}")
print("")

# ========== LOAD POSITIONS ==========
SYMBOLS_DATA = init_symbols()

# Thread locks
balance_lock = threading.Lock()
symbols_data_lock = threading.Lock()
sell_cooldown_lock = threading.Lock()

# Cooldown tracking
sell_cooldown = {}

def get_dynamic_symbols():
    """الحصول على قائمة العملات + الصفقات المفتوحة"""
    with symbols_data_lock:
        open_positions = [s for s, d in SYMBOLS_DATA.items() if d.get('position')]
        for symbol in SYMBOLS:
            if symbol not in SYMBOLS_DATA:
                SYMBOLS_DATA[symbol] = {'position': None}

    all_symbols = list(set(SYMBOLS + open_positions))
    return all_symbols

loaded = storage.load_positions()
for symbol, pos in loaded.items():
    if symbol not in SYMBOLS_DATA:
        SYMBOLS_DATA[symbol] = {'position': None}
    SYMBOLS_DATA[symbol]['position'] = pos
    print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")

print("   ── Ready · Watching Markets ──\n")

last_report_time = datetime.now(timezone.utc)

# ========== PARALLEL ANALYSIS FUNCTION ==========
def analyze_single_symbol(
    symbol, exchange_instance, active_count,
    available, invested, meta, preloaded_advisors,
    storage=None
):
    """تحليل عملة واحدة - يعمل في thread منفصل"""
    try:
        # Get symbol data
        with symbols_data_lock:
            if symbol not in SYMBOLS_DATA:
                return None
            symbol_data = SYMBOLS_DATA[symbol]
            position = symbol_data['position']

        # Get analysis
        analysis = get_market_analysis(exchange_instance, symbol)
        if not analysis:
            return None

        current_price = analysis['close']

        # ========== SELL LOGIC ==========
        if position:
            if meta:
                decision = meta.should_sell(
                    symbol, position, current_price,
                    analysis, analysis.get('mtf', {}),
                    preloaded_advisors=preloaded_advisors
                )
            else:
                decision = {'action': 'HOLD', 'reason': 'Meta module not loaded'}

            if decision and decision.get('action') == 'SELL':
                amount = position['amount']
                sell_value = calculate_sell_value(amount, current_price)

                if sell_value < MIN_SELL_VALUE:
                    return {
                        'symbol': symbol,
                        'action': 'SELL_WAIT',
                        'reason': decision.get('reason'),
                        'value': sell_value
                    }
                else:
                    profit_pct = calculate_profit_percent(current_price, position.get('buy_price', 0))
                    return {
                        'symbol':           symbol,
                        'action':           'SELL',
                        'amount':           amount,
                        'profit_percent':   profit_pct,
                        'profit':           profit_pct,
                        'rsi':              analysis.get('rsi', 50),
                        'volume_ratio':     analysis.get('volume_ratio', 1.0),
                        'price':            current_price,
                        'reason':           decision.get('reason'),
                        'optimism_penalty': decision.get('optimism_penalty', 0),
                        'position':         position,
                        'sell_votes':       decision.get('sell_votes', {}),
                        'analysis':         analysis,
                    }

            else:  # HOLD
                with symbols_data_lock:
                    SYMBOLS_DATA[symbol]['position']['highest_price'] = max(
                        current_price, position.get('highest_price', current_price)
                    )
                    threshold = decision.get('stop_loss_threshold')
                    if threshold is not None and threshold > 0:
                        SYMBOLS_DATA[symbol]['position']['stop_loss_threshold'] = threshold

                return {
                    'symbol':          symbol,
                    'action':          'HOLD',
                    'price':           current_price,
                    'profit':          calculate_profit_percent(current_price, position.get('buy_price', 0)),
                    'buy_price':       position.get('buy_price', 0),
                    'highest':         SYMBOLS_DATA[symbol]['position'].get('highest_price', current_price),
                    'reason':          decision.get('reason', 'Holding'),
                    'coin_forecast':   decision.get('coin_forecast', {}),
                    'market_forecast': decision.get('market_forecast', {}),
                    'stop_loss_threshold': decision.get('stop_loss_threshold'),
                }

        # ========== BUY LOGIC ==========
        else:
            if active_count >= MAX_POSITIONS:
                if meta:
                    decision = meta.should_buy(symbol, analysis, preloaded_advisors=preloaded_advisors)
                else:
                    decision = {'action': 'DISPLAY', 'reason': 'Meta not loaded'}

                meta_action = decision.get('action', 'DISPLAY') if decision else 'DISPLAY'
                meta_conf   = decision.get('confidence', 0) if decision else 0
                display_action = meta_action if meta_action == 'STRONG' else 'DISPLAY'

                return {
                    'symbol':       symbol,
                    'action':       display_action,
                    'price':        analysis.get('close', 0),
                    'rsi':          analysis.get('rsi', 0),
                    'volume':       min(analysis.get('volume_ratio', 0), 100),
                    'macd':         analysis.get('macd_diff', 0),
                    'confidence':   meta_conf,
                    'reason':       decision.get('reason', 'Monitoring') if decision else 'Monitoring',
                    'news_summary': decision.get('news_summary') if decision else None,
                    'advisors_intelligence': decision.get('advisors_intelligence', {}) if decision else {},
                }

            with sell_cooldown_lock:
                if symbol in sell_cooldown:
                    elapsed = (datetime.now(timezone.utc) - sell_cooldown[symbol]).total_seconds() / 60
                    if elapsed < COOLDOWN_MINUTES:
                        return {
                            'symbol':       symbol,
                            'action':       'COOLDOWN',
                            'minutes_left': COOLDOWN_MINUTES - elapsed
                        }

            can_trade, reason = capital_manager.can_trade(MIN_TRADE_AMOUNT, available, invested)
            if not can_trade:
                return None

            if meta:
                decision = meta.should_buy(symbol, analysis, preloaded_advisors=preloaded_advisors)
            else:
                decision = {'action': 'DISPLAY', 'reason': 'Meta not loaded'}

            meta_action = decision.get('action', 'DISPLAY') if decision else 'DISPLAY'
            meta_conf   = decision.get('confidence', 0) if decision else 0

            # BUY
            if decision and meta_action == 'BUY':
                return {
                    'symbol':        symbol,
                    'action':        'BUY',
                    'price':         current_price,
                    'amount':        decision.get('amount', MIN_TRADE_AMOUNT),
                    'confidence':    meta_conf,
                    'reason':        decision.get('reason', ''),
                    'decision':      decision,
                    'rsi':           analysis.get('rsi', 0),
                    'volume':        min(analysis.get('volume_ratio', 0), 100),
                    'macd_diff':     analysis.get('macd_diff', 0),
                    'news_summary':  decision.get('news_summary'),
                    'models_scores': decision.get('meta_scores', {}),
                    'analysis':      analysis,
                    'advisors_intelligence': decision.get('advisors_intelligence', {}),
                }

            # STRONG
            if decision and meta_action == 'STRONG':
                return {
                    'symbol':       symbol,
                    'action':       'STRONG',
                    'price':        analysis.get('close', 0),
                    'rsi':          analysis.get('rsi', 0),
                    'volume':       min(analysis.get('volume_ratio', 0), 100),
                    'macd':         analysis.get('macd_diff', 0),
                    'confidence':   meta_conf,
                    'reason':       decision.get('reason', ''),
                    'news_summary': decision.get('news_summary') if decision else None,
                    'analysis':     analysis,
                    'advisors_intelligence': decision.get('advisors_intelligence', {}) if decision else {},
                }

            # SKIP
            if decision and meta_action == 'SKIP':
                return {
                    'symbol': symbol,
                    'action': 'SKIP',
                    'reason': decision.get('reason')
                }

            # DISPLAY
            return {
                'symbol':       symbol,
                'action':       'DISPLAY',
                'price':        analysis.get('close', 0),
                'rsi':          analysis.get('rsi', 0),
                'volume':       analysis.get('volume_ratio', 0),
                'macd':         analysis.get('macd_diff', 0),
                'confidence':   meta_conf,
                'reason':       decision.get('reason', 'Monitoring') if decision else 'Monitoring',
                'news_summary': decision.get('news_summary') if decision else None,
                'analysis':     analysis,
                'advisors_intelligence': decision.get('advisors_intelligence', {}) if decision else {},
            }

    except Exception as e:
        import traceback
        logging.error(f"analyze_single_symbol error [{symbol}]: {e}", exc_info=True)
        print(f"❌ Error in analyze_single_symbol for {symbol}: {e}")
        traceback.print_exc()
        return {'symbol': symbol, 'action': 'ERROR', 'message': str(e)}

# ========== MAIN LOOP ==========
from bot.main_loop import run_main_loop

ctx = {
    'SYMBOLS_DATA':           SYMBOLS_DATA,
    'symbols_data_lock':      symbols_data_lock,
    'balance_lock':           balance_lock,
    'sell_cooldown':          sell_cooldown,
    'sell_cooldown_lock':     sell_cooldown_lock,
    'storage':                storage,
    'capital_manager':        capital_manager,
    'advisor_manager':        advisor_manager,
    'meta':                   meta,
    'dl_client':              dl_client,
    'external_client':        external_client,
    'memory_optimizer':       memory_optimizer,
    'analyze_fn':             analyze_single_symbol,
    'get_dynamic_symbols_fn': get_dynamic_symbols,
}

while True:
    try:
        run_main_loop(exchange, ctx)
    except KeyboardInterrupt:
        print("⏹️ Bot stopped by user")
        break
    except SystemExit as e:
        print(f"🔚 System exit: {e}")
        break
    except Exception as e:
        import traceback
        logging.error(f"Critical error in main loop: {e}", exc_info=True)
        print(f"❌ Critical error: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        print(f"🔄 Restarting in 5 seconds...")
        time.sleep(5)
