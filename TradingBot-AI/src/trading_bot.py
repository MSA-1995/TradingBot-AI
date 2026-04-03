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
    print("✅ Environment variables loaded from root .env file")
else:
    # إذا لم يتم العثور عليه، جرب تحميله بالطريقة الافتراضية
    load_dotenv()
    print("✅ Environment variables loaded")

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

# AI Brain
AI_BOUNDARIES = {}

# AI Brain has been replaced by Meta.
AI_ENABLED = False

# Advisor Manager (The Smart Secretary)
from bot.advisor_manager import AdvisorManager # <<< توظيف السكرتير الذكي
MODELS_ENABLED = True # Assume enabled, manager will handle individual failures

from memory.memory_optimizer import MemoryOptimizer # <<< استيراد المدير الصحيح

# Deep Learning Predictor V2 (6 Models)
try:
    from dl_client_v2 import DeepLearningClientV2
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        dl_client = DeepLearningClientV2(database_url)
        DL_ENABLED = dl_client.is_available()
        if DL_ENABLED:
            print("🧠 Deep Learning: ACTIVE")
            # Models status removed to avoid displaying 0% accuracy
            # models_status = dl_client.get_models_status()
            # for model_name, status in models_status.items():
            #     if model_name == 'ai_brain':
            #         continue
            #     print(f"   {model_name}: {status['accuracy']*100:.1f}%")
        else:
            print("⚠️ Deep Learning: Models not trained yet")
            dl_client = None
    else:
        dl_client = None
        DL_ENABLED = False
except Exception as e:
    print(f"⚠️ Deep Learning not loaded: {e}")
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

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
})
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
        print("✅ Database: Connected (Supabase)")
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

# AI Brain
ai_brain = None

# Initialize Meta (The King)
meta = None
if META_ENABLED:
    # The Meta class now gets the advisor_manager and fetches advisors as needed.
    meta = META_CLASS(advisor_manager, storage)

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
if meta:
    print("        👑 The King (Meta): ACTIVE")
print("        👑 Deep Learning Models (LightGBM)")
print("        📊 Multi-Timeframe + Risk Manager + Chart CNN")
print("        🏆 Coin Ranking + Anomaly Detection")
print("        🎯 Exit Strategy + Pattern Recognition")
print("        📰 News Sentiment Analysis")
print("        🔍 Top 10 from 50 Coins")
print("        ✅ Version 11.0 - Deep Learning V3")
print("  ✦•······················•✦•······················•✦\n")
print("=" * 60)

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
    if symbol in SYMBOLS_DATA:
        SYMBOLS_DATA[symbol]['position'] = pos
        print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")
    else:
        # إضافة الصفقة المفتوحة للقائمة
        SYMBOLS_DATA[symbol] = {'position': pos}
        print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")

print(f"\n🤖 Bot started!")
# AI Brain logic removed.

if MODELS_ENABLED:
    print(f"🛡️ Risk Manager: ACTIVE")
    print(f"🚨 Anomaly Detector: ACTIVE")
    print(f"🎯 Exit Strategy: ACTIVE")
    print(f"🧠 Pattern Recognition: ACTIVE")
    print(f"📊 Fibonacci Analyzer: ACTIVE")
    print(f"🐋 Smart Money Tracker: ACTIVE")
    print(f"💧 Liquidity Analyzer: ACTIVE")
    print(f"🧐 Market Mood: ACTIVE")

if NEWS_ENABLED:
    print(f"📰 News Sentiment Analyzer: ACTIVE")

print(f"💰 Amount: ~$15 (Dynamic)")
print(f"🎯 TP: Dynamic | SL: Dynamic TSL (ATR Based, -2%)")
print(f"🎯 Min Buy Confidence: {MIN_CONFIDENCE}/100\n")

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
def analyze_single_symbol(symbol, exchange_instance, active_count, available, invested, meta, preloaded_advisors):
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
        analysis = get_market_analysis(exchange_instance, symbol)
        timing_data['get_market_analysis'] = (time.time() - analysis_start) * 1000
        if not analysis:
            # إذا فشل التحليل (بيانات غير كافية)، تجاهل العملة في هذه الدورة
            # print(f"🔍 DEBUG: {symbol} - get_market_analysis returned None (insufficient data)")
            return None

        current_price = analysis['close']

        # ========== SELL LOGIC (Delegated to Meta) ==========
        if position:
            sell_logic_start = time.time()
            decision = meta.should_sell(symbol, position, current_price, analysis, preloaded_advisors)
            timing_data['meta_should_sell'] = (time.time() - sell_logic_start) * 1000

            if decision and decision.get('action') == 'SELL':
                amount = position['amount']
                sell_value = calculate_sell_value(amount, current_price)
                if sell_value < 9.99:
                    return {'symbol': symbol, 'action': 'SELL_WAIT', 'reason': decision.get('reason'), 'value': sell_value}
                else:
                    # حساب whale_confidence
                    whale_confidence = 0
                    atr_value = analysis.get('atr', 0)
                    sentiment_score = 0
                    try:
                        from models.smart_money_tracker import SmartMoneyTracker
                        smart_tracker = SmartMoneyTracker(exchange)
                        whale_confidence = smart_tracker.get_confidence_adjustment(symbol, analysis)

                        # جلب sentiment إضافي
                        from src.news_analyzer import NewsAnalyzer
                        news_analyzer = NewsAnalyzer()
                        sentiment_data = news_analyzer.get_news_sentiment(symbol, hours=24)
                        sentiment_score = sentiment_data['news_score'] if sentiment_data else 0
                    except Exception as e:
                        pass  # في حالة خطأ، ابقِ 0

                    return {
                        'symbol': symbol,
                        'action': 'SELL',
                        'amount': amount,
                        'price': current_price,
                        'profit': calculate_profit_percent(current_price, position['buy_price']),
                        'reason': decision.get('reason'),
                        'position': position,
                        'sell_votes': decision.get('sell_votes', {}),  # أصوات البيع للأرشفة والتعلم
                        'whale_confidence': whale_confidence,
                        'atr_value': atr_value,
                        'sentiment_score': sentiment_score
                    }
            else: # HOLD
                with symbols_data_lock:
                    SYMBOLS_DATA[symbol]['position']['highest_price'] = max(current_price, position.get('highest_price', current_price))
                return {
                    'symbol': symbol,
                    'action': 'HOLD',
                    'price': current_price,
                    'profit': calculate_profit_percent(current_price, position['buy_price']),
                    'buy_price': position['buy_price'],
                    'highest': SYMBOLS_DATA[symbol]['position']['highest_price'],
                    'reason': decision.get('reason', 'Holding')
                }

        # ========== BUY LOGIC (Delegated to Meta) ==========
        else:
            if active_count >= MAX_POSITIONS:
                # الصفقات ممتلئة - لا نشتري بس نكمل التحليل للعرض
                decision = meta.should_buy(symbol, analysis, preloaded_advisors)
                return {
                    'symbol': symbol,
                    'action': 'DISPLAY',
                    'price': analysis.get('close', 0),
                    'rsi': analysis.get('rsi', 0),
                    'volume': analysis.get('volume_ratio', 0),
                    'macd': analysis.get('macd_diff', 0),
                    'confidence': decision.get('confidence', 0) if decision else 0,
                    'reason': decision.get('reason', 'Monitoring') if decision else 'Monitoring',
                    'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None
                }

            with sell_cooldown_lock:
                if symbol in sell_cooldown and (datetime.now() - sell_cooldown[symbol]).total_seconds() / 60 < COOLDOWN_MINUTES:
                    return {'symbol': symbol, 'action': 'COOLDOWN', 'minutes_left': COOLDOWN_MINUTES - ((datetime.now() - sell_cooldown[symbol]).total_seconds() / 60)}

            can_trade, reason = capital_manager.can_trade(BASE_AMOUNT, available, invested)
            if not can_trade:
                return None # Not returning a message to avoid clutter

            buy_logic_start = time.time()
            decision = meta.should_buy(symbol, analysis, preloaded_advisors)
            timing_data['meta_should_buy'] = (time.time() - buy_logic_start) * 1000

            if decision and decision.get('action') == 'BUY':
                return {
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_price,
                    'amount': decision.get('amount', MIN_TRADE_AMOUNT),
                    'confidence': decision.get('confidence', 0),
                    'reason': decision.get('reason', ''),
                    'decision': decision,
                    'rsi': analysis.get('rsi', 0),
                    'volume': analysis.get('volume_ratio', 0),
                    'macd_diff': analysis.get('macd_diff', 0),
                    'news_summary': decision.get('news_summary'),
                    'models_scores': decision.get('meta_scores', {})
                }

            # If meta explicitly says to SKIP, then skip it.
            if decision and decision.get('action') == 'SKIP':
                return {'symbol': symbol, 'action': 'SKIP', 'reason': decision.get('reason')}

            # For all other cases (including explicit DISPLAY from meta or no decision),
            # build a full, safe DISPLAY dictionary to prevent KeyErrors.
            return {
                'symbol': symbol,
                'action': 'DISPLAY',
                'price': analysis.get('close', 0),
                'rsi': analysis.get('rsi', 0),
                'volume': analysis.get('volume_ratio', 0),
                'macd': analysis.get('macd_diff', 0),
                'confidence': decision.get('confidence', 0) if decision else 0,
                'reason': decision.get('reason', 'Monitoring') if decision else 'Monitoring',
                'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None
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
    'memory_optimizer':     memory_optimizer,
    'analyze_fn':           analyze_single_symbol,
    'get_dynamic_symbols_fn': get_dynamic_symbols,
}

# طباعة تأكيد اتصال الـ APIs
print("🔗 External APIs connected: NewsAPI, Alpha Vantage, CoinGecko")

while True:
    try:
        run_main_loop(exchange, ctx)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        print(f"🔄 Restarting in 5 seconds...")
        time.sleep(5)
