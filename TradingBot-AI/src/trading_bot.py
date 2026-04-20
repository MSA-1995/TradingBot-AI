"""
🤖 MSA Smart Trading Bot - Main File
Lightweight main loop that imports from organized modules
"""

# ========== LOAD ENV FILE ==========
from dotenv import load_dotenv
import os
import sys

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
            # إذا لم يتم العثور عليه، جرب تحميله بالطريقة الافتراضية
            load_dotenv()
            print("[OK] Environment variables loaded")

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
from analysis import get_market_analysis
from notifications import send_buy_notification, send_sell_notification, send_positions_report
from utils import execute_buy, execute_sell, calculate_sell_value, calculate_dynamic_confidence, get_active_positions_count, get_total_invested, should_send_report, calculate_profit_percent, format_price
from storage import StorageManager
from capital_manager import CapitalManager  # إدارة رأس المال
from external_apis import ExternalAPIClient # <<< استيراد المحرك الجديد

# AI Brain
AI_BOUNDARIES = {}

# AI Brain has been replaced by Meta.
AI_ENABLED = False

# Advisor Manager (The Smart Secretary)
from bot.advisor_manager import AdvisorManager # <<< توظيف السكرتير الذكي
MODELS_ENABLED = True # Assume enabled, manager will handle individual failures

from memory.memory_optimizer import MemoryOptimizer # <<< استيراد المدير الصحي
# ================================================================
# Deep Learning Predictor V2 (6 Models)
try:
    from src.dl_client_v2 import DeepLearningClientV2
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        dl_client = DeepLearningClientV2(database_url, load_models=False)
        print("✅ DeepLearningClientV2 created successfully")
    else:
        dl_client = None
        DL_ENABLED = False
        print("⚠️ No DATABASE_URL, Deep Learning disabled")
except Exception as e:
    print(f"❌ Failed to load Deep Learning Client: {e}")
    dl_client = None
    DL_ENABLED = False

# News analyzer is now managed by AdvisorManager
NEWS_ENABLED = True
news_analyzer = None # To be loaded by AdvisorManager

# Meta (The King)
try:
    from meta import Meta
    # سيتم تهيئته لاحقاً بعد تهيئة باقي الكائنات
    META_CLASS = Meta
    META_ENABLED = True
except Exception as e:
    print(f"⚠️ Meta module not loaded: {e}")
    META_CLASS = None
    META_ENABLED = False

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
    'timeout': 5000,  # 5 seconds timeout for API calls
    'enableRateLimit': True,
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
}

exchange = ccxt.binance(exchange_config)
exchange.set_sandbox_mode(True)

# Storage
storage = StorageManager()

# Test database connection
test_conn = None
try:
    test_conn = storage.storage._get_conn()
    if test_conn and not test_conn.closed:
        cursor = test_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        print("✅ Database: Connected Successfully")
    else:
        print("❌ Database: Connection failed")
except Exception as e:
    print(f"❌ Database: Connection error - {e}")
finally:
    if test_conn:
        test_conn.rollback()
        storage.storage._put_conn(test_conn)

# Capital Manager
capital_manager = CapitalManager(max_capital=MAX_CAPITAL, profit_reserve=PROFIT_RESERVE)

# External APIs Client
external_client = ExternalAPIClient()

# فحص الاتصال بالـ APIs الخارجية بصمت
if os.getenv("NEWS_API_KEY") and os.getenv("WHALE_ALERT_API_KEY"):
    print("✅ External APIs: Authentication Successful")
else:
    print("⚠️ External APIs: Some keys are missing in .env")

# Load models after database test
if dl_client:
    dl_client._load_all_models_from_db()
    dl_client._print_models_status()
    DL_ENABLED = dl_client.is_available()
    if DL_ENABLED:
        # ✅ فحص إذا تم تحميل الموديلات فعلاً
        if hasattr(dl_client._models, 'cache'):
            # التعامل مع كلاس MemoryCache الجديد
            loaded_models = len(dl_client._models.cache)
        else:
            # التعامل مع ديكشنري عادي (للاحتياط)
            loaded_models = len([m for m in dl_client._models.values() if m is not None])
            
        if loaded_models > 0:
            print(f"🧠 Deep Learning: {loaded_models}/12 models loaded successfully")
        else:
            print("⚠️ Deep Learning: Models not trained yet")
    else:
        DL_ENABLED = False

# Advisor Manager (The Smart Secretary)
# Instantiates all advisors on demand.
advisor_manager = AdvisorManager(storage=storage, capital_manager=capital_manager, exchange=exchange, dl_client=dl_client)

# Individual models are no longer instantiated here.
# They are loaded on-demand by the AdvisorManager.
risk_manager = None
anomaly_detector = None
exit_strategy = None
pattern_recognizer = None
fibonacci_analyzer = None
smart_money_tracker = None
liquidity_analyzer = None
market_mood_analyzer = None

# Memory optimizer is still needed
memory_optimizer = MemoryOptimizer(
    cleanup_interval=MEMORY_CLEANUP_INTERVAL,
    memory_threshold=MEMORY_USAGE_THRESHOLD
)

# Initialize Meta (The King)
meta = None
if META_ENABLED:
    # The Meta class now gets the advisor_manager and fetches advisors as needed.
    meta = META_CLASS(advisor_manager, storage)

# ========== BANNER ==========
print("✦•······················•✦•······················•✦")
print("\n  ███╗   ███╗███████╗ █████╗ ")
print("  ████╗ ████║██╔════╝██╔══██╗")
print("  ██╔████╔██║███████╗███████║")
print("  ██║╚██╔╝██║╚════██║██╔══██║")
print("  ██║ ╚═╝ ██║███████║██║  ██║")
print("  ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝\n")
print("  ✦•······················•✦•······················•✦")
print("  🚀 MSA Smart Trading Bot V4.0 (Deep Learning)")
print("  💰 Binance Testnet - AI-Powered Decision Engine")
print("  👑 Meta King: 20-Point Exclusive System")
print("  🧠 12 LightGBM Models (16K+ Trades Trained)")
print("  📊 Smart Money, Risk, Anomaly, Exit, Pattern")
print("  💧 Liquidity, Chart CNN, Candle Expert, Volume Predictor")
print("  📰 Sentiment & Crypto News Analysis")
print("  🛡️ 5 Elite Advisors: Adaptive Intelligence")
print("  🔥 Liquidation Shield, Volume Forecast Engine")
print("  🎯 Trend Early Detector, Self-Analysis Dashboard")
print("  📈 Macro Trend Advisor (Multi-Timeframe)")
print("  🎯 Enhanced Peak/Valley Catcher Strategy (Target: 50-80%)")
print("  🏆 The Golden Five (BTC, ETH, BNB, SOL, XRP)")
print("  ✅ Version 4.0 - Deep Learning Active")
print("  ✦•······················•✦•······················•✦\n")
print("  ✦•······················•✦•······················•✦")

# ========== LOAD POSITIONS ==========

def get_dynamic_symbols():
    """الحصول على قائمة العملات + الصفقات المفتوحة"""
    # الصفقات المفتوحة دائماً تُضاف
    with symbols_data_lock:
        open_positions = [s for s, d in SYMBOLS_DATA.items() if d.get('position')]
        # تحديث SYMBOLS_DATA بالعملات الثابتة
        for symbol in SYMBOLS:
            if symbol not in SYMBOLS_DATA:
                SYMBOLS_DATA[symbol] = {'position': None}

    # دمج العملات الثابتة + الصفقات المفتوحة
    all_symbols = list(set(SYMBOLS + open_positions))
    return all_symbols

SYMBOLS_DATA = init_symbols()
loaded = storage.load_positions()
for symbol, pos in loaded.items():
    if symbol not in SYMBOLS_DATA:
        SYMBOLS_DATA[symbol] = {'position': None}
    SYMBOLS_DATA[symbol]['position'] = pos
    print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")

print(f"\n🤖 Bot started!")



# Startup notification calls removed for simplification.
# load_status_message_id()
# send_startup_notification()

last_report_time = datetime.now()

# Thread lock for shared variables
balance_lock = threading.Lock()
symbols_data_lock = threading.Lock()

# Cooldown tracking: {symbol: sell_timestamp}
sell_cooldown = {}
sell_cooldown_lock = threading.Lock()
COOLDOWN_MINUTES = 15

# ========== PARALLEL ANALYSIS FUNCTION ==========
def analyze_single_symbol(symbol, exchange_instance, active_count, available, invested, meta, preloaded_advisors, storage=None, external_client=None):
    """تحليل عملة واحدة - يعمل في thread منفصل"""
    start_time = time.time()
    timing_data = {}
    try:
        # Get symbol data
        with symbols_data_lock:
            if symbol not in SYMBOLS_DATA:
                return None
            symbol_data = SYMBOLS_DATA[symbol]
            position = symbol_data['position']

        # Get analysis
        analysis_start = time.time()
        analysis = get_market_analysis(exchange_instance, symbol, external_client=external_client)
        timing_data['get_market_analysis'] = (time.time() - analysis_start) * 1000
        if not analysis:
            # إذا فشل التحليل (بيانات غير كافية)، تجاهل العملة في هذه الدورة
            # print(f"🔍 DEBUG: {symbol} - get_market_analysis returned None (insufficient data)")
            return None

        current_price = analysis['close']

        # ========== SELL LOGIC (Delegated to Meta) ==========
        if position:
            # Special exception for profit spike: sell immediately without meta or voting
            if storage and preloaded_advisors:
                try:
                    # 🔒 استخدام المستشار المحمل مسبقاً في الكاش لتجنب استهلاك الرام والاتصال بالداتابيز
                    exit_advisor = preloaded_advisors.get('ExitStrategyModel')
                    if exit_advisor:
                        exit_decision = exit_advisor.should_exit(symbol, position, current_price, analysis, analysis.get('mtf', {}))
                    if exit_decision['action'] == 'SELL' and 'SPIKE' in exit_decision['reason'].upper():
                        # Sell immediately due to spike
                        amount = position['amount']
                        sell_value = calculate_sell_value(amount, current_price)
                        if sell_value < 9.99:
                            return {'symbol': symbol, 'action': 'SELL_WAIT', 'reason': exit_decision['reason'], 'value': sell_value}
                        else:
                            return {
                                'symbol': symbol,
                                'action': 'SELL',
                                'amount': amount,
                                'profit_percent': calculate_profit_percent(current_price, position.get('buy_price', 0)),
                                'rsi': analysis.get('rsi', 50),
                                'volume_ratio': analysis.get('volume_ratio', 1.0),
                                'price': current_price,
                                'profit': calculate_profit_percent(current_price, position.get('buy_price', 0)),
                                'reason': exit_decision['reason'],
                                'position': position,
                                'analysis': analysis,
                                **analysis
                            }
                except Exception as e:
                    print(f"⚠️ Spike check error for {symbol}: {e}")

            sell_logic_start = time.time()
            if meta:
                decision = meta.should_sell(symbol, position, current_price, analysis, analysis.get('mtf', {}), preloaded_advisors=preloaded_advisors)
            else:
                decision = {'action': 'HOLD', 'reason': 'Meta module not loaded'}
                
            timing_data['meta_should_sell'] = (time.time() - sell_logic_start) * 1000

            if decision and decision.get('action') == 'SELL':
                amount = position['amount']
                sell_value = calculate_sell_value(amount, current_price)
                if sell_value < 9.99:
                    return {'symbol': symbol, 'action': 'SELL_WAIT', 'reason': decision.get('reason'), 'value': sell_value}
                else:
                    return {
                        'symbol': symbol,
                        'action': 'SELL',
                        'amount': amount,
                        'profit_percent': calculate_profit_percent(current_price, position.get('buy_price', 0)),
                        'rsi': analysis.get('rsi', 50),
                        'volume_ratio': analysis.get('volume_ratio', 1.0),
                        'price': current_price,
                        'profit': calculate_profit_percent(current_price, position.get('buy_price', 0)),
                        'reason': decision.get('reason'),
                        'optimism_penalty': decision.get('optimism_penalty', 0),
                        'position': position,
                        'sell_votes': decision.get('sell_votes', {}),
                        'analysis': analysis, # ✅ تمرير التحليل الكامل (يحتوي على الـ 42 ميزة)
                        **analysis
                    }
            else: # HOLD
                with symbols_data_lock:
                    SYMBOLS_DATA[symbol]['position']['highest_price'] = max(current_price, position.get('highest_price', current_price))
                return {
                    'symbol': symbol,
                    'action': 'HOLD',
                    'price': current_price,
                    'profit': calculate_profit_percent(current_price, position.get('buy_price', 0)),
                    'buy_price': position.get('buy_price', 0),
                    'highest': SYMBOLS_DATA[symbol]['position'].get('highest_price', current_price),
                    'reason': decision.get('reason', 'Holding')
                }

        # ========== BUY LOGIC (Delegated to Meta) ==========
        else:
            if active_count >= MAX_POSITIONS:
                # الصفقات ممتلئة - لا نشتري لكن نحلل ونعرض STRONG إذا العملة قوية
                if meta:
                    decision = meta.should_buy(symbol, analysis, preloaded_advisors=preloaded_advisors)
                else:
                    decision = {'action': 'DISPLAY', 'reason': 'Meta not loaded'}
                meta_action = decision.get('action', 'DISPLAY') if decision else 'DISPLAY'
                meta_conf   = decision.get('confidence', 0) if decision else 0
                #print(f"🔍 DEBUG FULL [{symbol}] → Meta={meta_action} Conf={meta_conf} | RSI={analysis.get('rsi',0):.0f} Vol={analysis.get('volume_ratio',0):.1f}x")
                display_action = meta_action if meta_action == 'STRONG' else 'DISPLAY'
                return {
                    'symbol': symbol,
                    'action': display_action,
                    'price': analysis.get('close', 0),
                    'rsi': analysis.get('rsi', 0),
                        'volume': min(analysis.get('volume_ratio', 0), 100),
                    'macd': analysis.get('macd_diff', 0),
                    'confidence': meta_conf,
                    'reason': (decision.get('reason', 'Monitoring') if decision else 'Monitoring'),
                    'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None
                }

            with sell_cooldown_lock:
                if symbol in sell_cooldown and (datetime.now() - sell_cooldown[symbol]).total_seconds() / 60 < COOLDOWN_MINUTES:
                    return {'symbol': symbol, 'action': 'COOLDOWN', 'minutes_left': COOLDOWN_MINUTES - ((datetime.now() - sell_cooldown[symbol]).total_seconds() / 60)}

            can_trade, reason = capital_manager.can_trade(MIN_TRADE_AMOUNT, available, invested)
            if not can_trade:
                return None # Not returning a message to avoid clutter

            buy_logic_start = time.time()
            if meta:
                decision = meta.should_buy(symbol, analysis, preloaded_advisors=preloaded_advisors)
            else:
                decision = {'action': 'DISPLAY', 'reason': 'Meta not loaded'}
            timing_data['meta_should_buy'] = (time.time() - buy_logic_start) * 1000

            meta_action = decision.get('action', 'DISPLAY') if decision else 'DISPLAY'
            meta_conf   = decision.get('confidence', 0) if decision else 0

            if decision and meta_action == 'BUY':
                return {
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_price,
                    'amount': decision.get('amount', MIN_TRADE_AMOUNT),
                    'confidence': meta_conf,
                    'reason': decision.get('reason', ''),
                    'decision': decision,
                    'rsi': analysis.get('rsi', 0),
                        'volume': min(analysis.get('volume_ratio', 0), 100),
                    'macd_diff': analysis.get('macd_diff', 0),
                    'news_summary': decision.get('news_summary'),
                    'models_scores': decision.get('meta_scores', {}),
                    **analysis  # ✅ سحب كافة الميزات المتقدمة مباشرة من المحلل الفني
                }

            # عملة قوية - الملك راضي لكن الأصوات ناقصة
            if decision and meta_action == 'STRONG':
                return {
                    'symbol': symbol,
                    'action': 'STRONG',
                    'price': analysis.get('close', 0),
                    'rsi': analysis.get('rsi', 0),
                        'volume': min(analysis.get('volume_ratio', 0), 100),
                    'macd': analysis.get('macd_diff', 0),
                    'confidence': meta_conf,
                    'reason': decision.get('reason', ''),
                    'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None,
                    'analysis': analysis,
                    **analysis
                }

            # If meta explicitly says to SKIP, then skip it.
            if decision and meta_action == 'SKIP':
                return {'symbol': symbol, 'action': 'SKIP', 'reason': decision.get('reason')}

            # DISPLAY - عملة عادية
            return {
                'symbol': symbol,
                'action': 'DISPLAY',
                'price': analysis.get('close', 0),
                'rsi': analysis.get('rsi', 0),
                'volume': analysis.get('volume_ratio', 0),
                'macd': analysis.get('macd_diff', 0),
                'confidence': meta_conf,
                'reason': (
                    f"🚀 Peak/Valley Catcher (Target: 80%)" if position else 
                    (decision.get('reason', 'Monitoring') if decision else 'Monitoring')
                ),
                'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None,
                'analysis': analysis,
                **analysis
            }

    except Exception as e:
        import traceback
        print(f"❌ Error in analyze_single_symbol for {symbol}: {e}")
        traceback.print_exc()
        return {'symbol': symbol, 'action': 'ERROR', 'message': str(e)}
    finally:
        # Timing display logic removed as per instruction.
        pass

# ========== MAIN LOOP ==========
from bot.main_loop import run_main_loop

ctx = {
    'SYMBOLS_DATA':         SYMBOLS_DATA,
    'symbols_data_lock':    symbols_data_lock,
    'balance_lock':         balance_lock,
    'sell_cooldown':        sell_cooldown,
    'sell_cooldown_lock':   sell_cooldown_lock,
    'storage':              storage,
    'capital_manager':      capital_manager,
    'advisor_manager':      advisor_manager, # <<< إضافة مدير المستشارين إلى السياق
    'meta':                 meta,
    'dl_client':            dl_client,  # <<< إضافة dl_client لفحص التحديثات
    'external_client':      external_client, # تمرير المحرك للـ Loop
    'memory_optimizer':     memory_optimizer,
    'analyze_fn':           analyze_single_symbol,
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
        print(f"❌ Critical error: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        print(f"🔄 Restarting in 5 seconds...")
        time.sleep(5)
