"""
🤖 MSA Smart Trading Bot - Main File
Lightweight main loop that imports from organized modules
"""

# ========== LOAD ENV FILE ==========
from dotenv import load_dotenv
import os

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
from analysis import get_market_analysis, get_multi_timeframe_analysis
from trading import execute_buy, execute_sell, calculate_sell_value
from notifications import send_buy_notification, send_sell_notification, send_positions_report
from utils import calculate_dynamic_confidence, get_active_positions_count, get_total_invested, should_send_report, calculate_profit_percent, format_price
from storage import StorageManager
from capital_manager import CapitalManager  # إدارة رأس المال

# AI Brain
AI_BOUNDARIES = {}

# AI Brain has been replaced by Meta.
AI_ENABLED = False

# Advanced Models
try:
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from models.risk_manager import RiskManager
    from models.anomaly_detector import AnomalyDetector
    from models.exit_strategy_model import ExitStrategyModel
    from models.enhanced_pattern_recognition import EnhancedPatternRecognition
    from models.smart_money_tracker import SmartMoneyTracker
    from models.liquidity_analyzer import LiquidityAnalyzer
    from models.market_mood_analyzer import MarketMoodAnalyzer # <<< استيراد الخبير الجديد
    
    MODELS_ENABLED = True
except Exception as e:
    print(f"⚠️ Advanced models not loaded: {e}")
    MODELS_ENABLED = False

# Deep Learning Predictor V2 (6 Models)
try:
    from dl_client_v2 import DeepLearningClientV2
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        dl_client = DeepLearningClientV2(database_url)
        DL_ENABLED = dl_client.is_available()
        if DL_ENABLED:
            print("🧠 Deep Learning: ACTIVE")
            models_status = dl_client.get_models_status()
            for model_name, status in models_status.items():
                if model_name == 'ai_brain':
                    continue
                print(f"   {model_name}: {status['accuracy']*100:.1f}%")
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

from news_analyzer import NewsAnalyzer

try:
    news_analyzer = NewsAnalyzer()
    NEWS_ENABLED = news_analyzer.enabled
except Exception as e:
    print(f"⚠️ News Analyzer not loaded: {e}")
    news_analyzer = None
    NEWS_ENABLED = False

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

# Capital Manager
capital_manager = CapitalManager(max_capital=MAX_CAPITAL, profit_reserve=PROFIT_RESERVE)

# Rescue Scalper (تم إيقافه - غير ضروري)
rescue_scalper = None

# Advanced Models
if MODELS_ENABLED:
    risk_manager = RiskManager(storage)
    anomaly_detector = AnomalyDetector(exchange)
    exit_strategy = ExitStrategyModel(storage)
    pattern_recognizer = EnhancedPatternRecognition(storage)
    smart_money_tracker = SmartMoneyTracker(exchange)
    liquidity_analyzer = LiquidityAnalyzer(exchange)
    market_mood_analyzer = MarketMoodAnalyzer() # <<< إضافة الخبير الجديد
else:
    risk_manager = None
    anomaly_detector = None
    exit_strategy = None
    pattern_recognizer = None
    smart_money_tracker = None
    liquidity_analyzer = None
    market_mood_analyzer = None # <<< وإضافته هنا أيضاً

# AI Brain
ai_brain = None

# Initialize Meta (The King)
meta = None
if META_ENABLED:
    meta = META_CLASS(
        dl_client=dl_client,
        risk_manager=risk_manager,
        rescue_scalper=None,
        storage=storage,
        news_analyzer=news_analyzer,
        fibonacci_analyzer=None
    )

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
print("        🔍 Top 10 from 50 Fixed Coins")
print("        ✅ Version 11.0 - Deep Learning V3 🚀")
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
    print(f"🐋 Smart Money Tracker: ACTIVE")
    print(f"💧 Liquidity Analyzer: ACTIVE")
    print(f"🧐 Market Mood: ACTIVE")

if NEWS_ENABLED:
    print(f"📰 News Sentiment Analyzer: ACTIVE")

print(f"💰 Amount: ~$15 (Dynamic)")
print(f"🎯 TP: Dynamic | SL: Dynamic TSL (ATR Based, 1%-5%)")
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
COOLDOWN_MINUTES = 20

# ========== PARALLEL ANALYSIS FUNCTION ==========
def analyze_single_symbol(symbol, exchange_instance, active_count, available, invested):
    """تحليل عملة واحدة - يعمل في thread منفصل"""
    try:
        # Get symbol data (don't add if not exists)
        with symbols_data_lock:
            if symbol not in SYMBOLS_DATA:
                # Skip coins not in scanner or open positions
                return None
            symbol_data = SYMBOLS_DATA[symbol]
            position = symbol_data['position']
        
        # Get analysis
        analysis = get_market_analysis(exchange_instance, symbol)
        if not analysis:
            if position:
                return {'symbol': symbol, 'action': 'ERROR', 'message': 'Analysis failed (has position)'}
            return None
        
        current_price = analysis['close']
        
        # ========== SELL LOGIC ==========
        if position:
            buy_price = position['buy_price']
            amount = position['amount']
            highest_price = position.get('highest_price', buy_price)
            
            # Update highest
            highest_price = max(current_price, highest_price)
            with symbols_data_lock:
                position['highest_price'] = highest_price
            
            profit_percent = calculate_profit_percent(current_price, buy_price)
            
            # Check sell conditions
            sell_decision = None
            sell_reason = None
            
            # Get MTF from analysis (cache) - تحسين السرعة
            mtf = analysis.get('mtf') if analysis else None
            
            # Meta (الملك الجديد) - المسؤول عن البيع
            if meta:
                if mtf is None:
                    mtf = get_multi_timeframe_analysis(exchange_instance, symbol)
                
                sell_decision = meta.should_sell(
                    symbol, position, current_price, analysis, mtf
                )
                
                if sell_decision and sell_decision.get('action') == 'SELL':
                    sell_reason = sell_decision.get('reason')
            
            # Execute sell
            if sell_reason:
                sell_value = calculate_sell_value(amount, current_price)
                
                if sell_value < 9.99:
                    return {
                        'symbol': symbol,
                        'action': 'SELL_WAIT',
                        'reason': sell_reason,
                        'value': sell_value
                    }
                else:
                    return {
                        'symbol': symbol,
                        'action': 'SELL',
                        'amount': amount,
                        'price': current_price,
                        'profit': profit_percent,
                        'reason': sell_reason,
                        'position': position
                    }
            else:
                # HOLD position
                hold_reason = sell_decision.get('reason', 'Holding position') if sell_decision else 'Holding position'
                return {
                    'symbol': symbol,
                    'action': 'HOLD',
                    'price': current_price,
                    'profit': profit_percent,
                    'buy_price': buy_price,
                    'highest': highest_price,
                    'reason': hold_reason
                }
        
        # ========== BUY LOGIC ==========
        else:
            if active_count >= MAX_POSITIONS:
                return None
            
            # Check cooldown: Don't buy if recently sold
            if symbol in sell_cooldown:
                time_since_sell = (datetime.now() - sell_cooldown[symbol]).total_seconds() / 60
                if time_since_sell < COOLDOWN_MINUTES:
                    return {'symbol': symbol, 'action': 'COOLDOWN', 'minutes_left': COOLDOWN_MINUTES - time_since_sell}
            
            # Capital Management Check
            can_trade, reason = capital_manager.can_trade(BASE_AMOUNT, available, invested)
            if not can_trade:
                return None
            
            # Get MTF and calculate confidence
            mtf = analysis.get('mtf') or get_multi_timeframe_analysis(exchange_instance, symbol)
            
            # Smart Money Analysis (بديل MTF)
            smart_money_boost = 0
            if smart_money_tracker:
                try:
                    smart_money_boost = smart_money_tracker.get_confidence_adjustment(symbol, analysis)
                    should_avoid, avoid_reason = smart_money_tracker.should_avoid(symbol, analysis)
                    if should_avoid:
                        return {'symbol': symbol, 'action': 'SKIP', 'reason': avoid_reason}
                except Exception as e:
                    smart_money_boost = 0
            
            # Fibonacci Analysis (تم إيقافه - غير ضروري)
            fibonacci_boost = 0
            
            # Market Mood Analysis (الخبير الاستراتيجي)
            mood_adjustment = 0
            if market_mood_analyzer:
                try:
                    mood_result = market_mood_analyzer.get_mood_adjustment(symbol)
                    mood_adjustment = mood_result.get('adjustment', 0)
                except Exception as e:
                    mood_adjustment = 0
            
            # Calculate price drop
            price_drop = {'drop_percent': 0, 'confirmed': False}
            try:
                df = analysis['df']
                if len(df) >= 12:
                    highest_price_1h = df['high'].tail(12).max()
                    current_price_df = df['close'].iloc[-1]
                    
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
                    if news_analyzer.should_avoid_coin(symbol, hours=24):
                        return {'symbol': symbol, 'action': 'SKIP', 'reason': 'Negative news sentiment'}
                    
                    news_adjustment = news_analyzer.get_news_confidence_boost(symbol, hours=24) or 0
                    news_summary = news_analyzer.get_news_summary(symbol, hours=24) or "No news"
                except Exception as e:
                    news_adjustment = 0
                    news_summary = "No news"
            
            # Liquidity Check (بديل Coin Ranking)
            liquidity_adjustment = 0
            if liquidity_analyzer:
                try:
                    liquidity_result = liquidity_analyzer.should_trade_coin(symbol, analysis)
                    if not liquidity_result['trade']:
                        return {'symbol': symbol, 'action': 'SKIP', 'reason': liquidity_result['reason']}
                    liquidity_adjustment = liquidity_result.get('confidence_adjustment', 0) or 0
                except Exception as e:
                    liquidity_adjustment = 0
            
            # Anomaly Detection - نظام نقاط متوازن
            anomaly_adjustment = 0
            anomaly_score = 0
            if anomaly_detector:
                try:
                    anomaly_result = anomaly_detector.detect_anomalies(symbol, analysis)
                    
                    # فقط CRITICAL يرفض الشراء (نقاط >= 5)
                    if not anomaly_result.get('safe_to_trade', True):
                        return {'symbol': symbol, 'action': 'SKIP', 'reason': f"ANOMALY: {anomaly_result.get('severity', 'HIGH')}"}
                    
                    # تحويل النقاط إلى خصم (كل نقطة = -5 ثقة)
                    anomaly_score = anomaly_result.get('anomaly_score', 0)
                    anomaly_adjustment = -5 * anomaly_score
                    
                except Exception as e:
                    anomaly_adjustment = 0
            
            # Pattern Recognition
            pattern_adjustment = 0
            if pattern_recognizer:
                try:
                    pattern_analysis = pattern_recognizer.analyze_entry_pattern(
                        symbol, analysis, mtf, price_drop
                    )
                    if pattern_analysis:
                        if pattern_analysis.get('recommendation') == 'AVOID':
                            return {'symbol': symbol, 'action': 'SKIP', 'reason': f"PATTERN: {pattern_analysis['recommendation']}"}
                        pattern_adjustment = pattern_analysis.get('confidence_adjustment', 0) or 0
                except Exception as e:
                    pattern_adjustment = 0

            # Add scores to reasons for clarity
            reasons.append(f"News: {news_adjustment:.1f}")
            reasons.append(f"SmartMoney: {smart_money_boost:.1f}")
            # reasons.append(f"Fibonacci: {fibonacci_boost:.1f}")  # تم إيقافه
            reasons.append(f"Liquidity: {liquidity_adjustment:.1f}")
            reasons.append(f"Mood: {mood_adjustment:.1f}")
            reasons.append(f"Pattern: {pattern_adjustment:.1f}")
            reasons.append(f"Anomaly: {anomaly_adjustment:.1f}")

            # حساب الثقة النهائية مع كل التعديلات
            final_confidence = confidence + news_adjustment + smart_money_boost + fibonacci_boost + liquidity_adjustment + mood_adjustment + pattern_adjustment + anomaly_adjustment
            final_confidence = max(0, min(100, int(final_confidence)))
            
            # Meta (The King) Decision
            if meta:
                # In the BUY logic, there is no existing position, so exit_score is 0.
                # The logic to calculate it based on a position is only relevant for selling.
                exit_score = 0

                # Get all models scores
                models_scores = {
                    'risk': risk_manager.get_risk_score(analysis, final_confidence) if risk_manager else 0,
                    'anomaly': anomaly_score, # استخدام النقاط مباشرة
                    'exit': exit_score,
                    'pattern': pattern_adjustment,
                    'smart_money': smart_money_boost,
                    'fibonacci': 0,  # تم إيقافه
                    'liquidity': liquidity_adjustment,
                    'market_mood': mood_adjustment,
                    'news': news_adjustment,
                    'mtf': mtf.get('score', 0) if mtf else 0,
                    'chart_cnn': 0, # Placeholder
                    'rescue': 0, # Placeholder
                    'base_confidence': confidence # The base score from the old brain logic
                }
                
                # The King decides
                decision = meta.should_buy(symbol, analysis, models_scores)

                if decision['action'] == 'BUY':
                    # Amount already calculated by Meta with Risk Manager voting
                    amount_usd = decision['amount']
                    
                    return {
                        'symbol': symbol,
                        'action': 'BUY',
                        'amount': amount_usd,
                        'price': current_price,
                        'confidence': decision['confidence'],
                        'decision': decision,
                        'analysis': analysis,
                        'news_summary': news_summary if news_adjustment != 0 else None
                    }
                else:
                    # إذا رفض الملك الشراء، نعرضها كفرصة محتملة بدلاً من تجاهلها
                    return {
                        'symbol': symbol,
                        'action': 'DISPLAY',
                        'price': current_price,
                        'rsi': analysis.get('rsi', 0),
                        'volume': analysis.get('volume_ratio', 0),
                        'macd': analysis.get('macd_diff', 0),
                        'confidence': decision['confidence'],
                        'reason': decision['reason'],
                        'news_summary': news_summary if NEWS_ENABLED else None
                    }
            else:
                # Manual mode
                if final_confidence >= MIN_CONFIDENCE:
                    return {
                        'symbol': symbol,
                        'action': 'BUY',
                        'amount': BASE_AMOUNT,
                        'price': current_price,
                        'confidence': final_confidence,
                        'analysis': analysis
                    }
                else:
                    return {
                        'symbol': symbol,
                        'action': 'DISPLAY',
                        'price': current_price,
                        'rsi': analysis.get('rsi', 0),
                        'volume': analysis.get('volume_ratio', 0),
                        'macd': analysis.get('macd_diff', 0),
                        'confidence': final_confidence
                    }
    
    except Exception as e:
        return {'symbol': symbol, 'action': 'ERROR', 'message': str(e)}

# ========== MAIN LOOP ==========
from bot.main_loop import run_main_loop

ctx = {
    'SYMBOLS_DATA':         SYMBOLS_DATA,
    'symbols_data_lock':    symbols_data_lock,
    'balance_lock':         balance_lock,
    'sell_cooldown':        sell_cooldown,
    'storage':              storage,
    'capital_manager':      capital_manager,
    'risk_manager':         risk_manager,
    'anomaly_detector':     anomaly_detector,
    'exit_strategy':        exit_strategy,
    'pattern_recognizer':   pattern_recognizer,
    'smart_money_tracker':  smart_money_tracker,
    'liquidity_analyzer':   liquidity_analyzer,
    'analyze_fn':           analyze_single_symbol,
    'get_dynamic_symbols_fn': get_dynamic_symbols,
}

while True:
    try:
        run_main_loop(exchange, ctx)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        print(f"🔄 Restarting in 5 seconds...")
        time.sleep(5)
