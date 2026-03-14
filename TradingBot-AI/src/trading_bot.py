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

# AI Brain
AI_BOUNDARIES = {
    'min_confidence': 55,  # Changed from 60 - more aggressive for Testnet learning
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

# News Analyzer - Inline to avoid import issues
class NewsAnalyzer:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.enabled = bool(self.database_url)
        self.cache = {}
        self.cache_duration = 30
        
        if self.enabled:
            print("📰 News Analyzer: ACTIVE")
        else:
            print("⚠️ News Analyzer: DISABLED (No DATABASE_URL)")
    
    def get_db_connection(self):
        if not self.enabled:
            return None
        try:
            import psycopg2
            from urllib.parse import urlparse, unquote
            parsed = urlparse(self.database_url)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=unquote(parsed.password)
            )
            return conn
        except Exception as e:
            print(f"❌ News DB connection error: {e}")
            return None
    
    def get_news_sentiment(self, symbol, hours=24):
        if not self.enabled:
            return None
        cache_key = f"{symbol}_{hours}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_duration:
                return cached_data
        try:
            from psycopg2.extras import RealDictCursor
            conn = self.get_db_connection()
            if not conn:
                return None
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT sentiment, score, headline, timestamp
                FROM news_sentiment
                WHERE symbol = %s
                AND timestamp > NOW() - INTERVAL '%s hours'
                ORDER BY timestamp DESC
            """, (symbol, hours))
            news = cursor.fetchall()
            cursor.close()
            conn.close()
            if not news:
                return None
            positive = sum(1 for n in news if n['sentiment'] == 'POSITIVE')
            negative = sum(1 for n in news if n['sentiment'] == 'NEGATIVE')
            neutral = sum(1 for n in news if n['sentiment'] == 'NEUTRAL')
            total = len(news)
            if total == 0:
                news_score = 0
            else:
                pos_ratio = positive / total
                neg_ratio = negative / total
                news_score = (pos_ratio - neg_ratio) * 10
            result = {
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'total': total,
                'news_score': news_score,
                'latest_news': news[:3]
            }
            self.cache[cache_key] = (result, datetime.now())
            return result
        except Exception as e:
            return None
    
    def get_news_confidence_boost(self, symbol, hours=24):
        sentiment = self.get_news_sentiment(symbol, hours)
        if not sentiment:
            return 0
        news_score = sentiment['news_score']
        total_news = sentiment['total']
        if total_news < 2:
            return 0
        confidence_boost = int(news_score * 1.5)
        confidence_boost = max(-15, min(15, confidence_boost))
        return confidence_boost
    
    def should_avoid_coin(self, symbol, hours=24):
        sentiment = self.get_news_sentiment(symbol, hours)
        if not sentiment:
            return False
        total = sentiment['total']
        negative = sentiment['negative']
        positive = sentiment['positive']
        if total >= 3:
            neg_ratio = negative / total
            if neg_ratio > 0.8:
                return True
            if negative >= 3 and positive == 0:
                return True
        return False
    
    def get_news_summary(self, symbol, hours=24):
        sentiment = self.get_news_sentiment(symbol, hours)
        if not sentiment:
            return "No news"
        total = sentiment['total']
        pos = sentiment['positive']
        neg = sentiment['negative']
        score = sentiment['news_score']
        if score > 5:
            emoji = "📈"
            status = "Very Bullish"
        elif score > 2:
            emoji = "✅"
            status = "Bullish"
        elif score < -5:
            emoji = "📉"
            status = "Very Bearish"
        elif score < -2:
            emoji = "❌"
            status = "Bearish"
        else:
            emoji = "⚪"
            status = "Neutral"
        return f"{emoji} {status} ({pos}+ {neg}- / {total})"

try:
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

# Dynamic Coin Scanner (20 عملة مشهورة ثابتة)
coin_scanner = CoinScanner(exchange, ai_brain, mtf_analyzer, risk_manager)
# لا نحتاج start() - النظام الجديد بسيط

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
print("        🔍 Dynamic Coin Scanner (Top 20)")
print("        ✅ Version 9.0 - Dynamic 20 Coins 🚀")
print("  ✦•······················•✦•······················•✦\n")
print("=" * 60)

# ========== LOAD POSITIONS ==========
# استخدام قائمة ديناميكية بدل SYMBOLS الثابتة
def get_dynamic_symbols():
    """الحصول على القائمة الديناميكية + الصفقات المفتوحة"""
    # القائمة الديناميكية من Scanner
    top_coins = coin_scanner.get_top_coins()
    dynamic_symbols = [coin for coin, score in top_coins]
    
    print(f"\n🔍 DEBUG: Scanner returned {len(dynamic_symbols)} coins")
    print(f"📋 Scanner coins (first 20): {', '.join(dynamic_symbols[:20])}")
    print(f"📋 Scanner coins (all): {', '.join(sorted(dynamic_symbols))}\n")
    
    print(f"🔍 DEBUG: SYMBOLS_DATA before cleanup has {len(SYMBOLS_DATA)} coins:")
    print(f"   {', '.join(sorted(list(SYMBOLS_DATA.keys())[:20]))}...")
    
    # تنظيف SYMBOLS_DATA أولاً - حذف كل العملات القديمة
    with symbols_data_lock:
        # حفظ الصفقات المفتوحة فقط
        open_positions_data = {symbol: data for symbol, data in SYMBOLS_DATA.items() if data.get('position')}
        
        # مسح SYMBOLS_DATA بالكامل
        SYMBOLS_DATA.clear()
        
        # إعادة بناء SYMBOLS_DATA من الصفر
        # 1. إضافة الصفقات المفتوحة
        for symbol, data in open_positions_data.items():
            SYMBOLS_DATA[symbol] = data
        
        # 2. إضافة العملات من السكانر
        for symbol in dynamic_symbols:
            if symbol not in SYMBOLS_DATA:
                SYMBOLS_DATA[symbol] = {'position': None}
    
    # الحصول على القائمة النهائية
    open_positions = list(open_positions_data.keys())
    all_symbols = list(set(dynamic_symbols + open_positions))
    
    print(f"📂 Open positions: {len(open_positions)} - {', '.join(open_positions) if open_positions else 'None'}")
    print(f"✅ SYMBOLS_DATA rebuilt: {len(SYMBOLS_DATA)} coins")
    print(f"   Rebuilt with: {', '.join(sorted(list(SYMBOLS_DATA.keys())[:20]))}...")
    print(f"🎯 all_symbols to return: {', '.join(sorted(all_symbols)[:20])}...")
    print(f"🎯 Final symbols to analyze: {len(all_symbols)}\n")
    
    return all_symbols

SYMBOLS_DATA = init_symbols()
loaded = storage.load_positions()

print(f"\n📥 Loading positions from database...")
print(f"📊 Found {len(loaded)} positions in database")

for symbol, pos in loaded.items():
    print(f"  📂 Loading: {symbol} - ${pos['buy_price']:.2f}")
    if symbol in SYMBOLS_DATA:
        SYMBOLS_DATA[symbol]['position'] = pos
    else:
        # إضافة الصفقة المفتوحة للقائمة
        SYMBOLS_DATA[symbol] = {'position': pos}

print(f"✅ SYMBOLS_DATA initialized with {len(SYMBOLS_DATA)} coins\n")

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

# Thread lock for shared variables
balance_lock = threading.Lock()
symbols_data_lock = threading.Lock()

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
            highest_price = update_highest_price(current_price, highest_price)
            with symbols_data_lock:
                position['highest_price'] = highest_price
            
            profit_percent = calculate_profit_percent(current_price, buy_price)
            
            # Check sell conditions
            sell_decision = None
            
            # Exit Strategy Model (أولوية)
            mtf = None
            if exit_strategy:
                try:
                    mtf = get_multi_timeframe_analysis(exchange_instance, symbol)
                    exit_decision = exit_strategy.should_exit(
                        symbol, position, current_price, analysis, mtf
                    )
                    if exit_decision and exit_decision.get('action') == 'SELL':
                        sell_decision = exit_decision
                        sell_reason = exit_decision.get('reason', 'Exit Strategy')
                        profit_percent = exit_decision.get('profit', profit_percent)
                except Exception as e:
                    pass
            
            # AI Smart Sell (إذا Exit Strategy ما قرر)
            if not sell_decision and ai_brain:
                if mtf is None:
                    mtf = get_multi_timeframe_analysis(exchange_instance, symbol)
                
                sell_decision = ai_brain.should_sell(symbol, position, current_price, analysis, mtf)
                
                if sell_decision and sell_decision.get('action') == 'SELL':
                    sell_reason = sell_decision.get('reason', 'AI Sell')
                    profit_percent = sell_decision.get('profit', profit_percent)
                elif sell_decision and sell_decision.get('action') == 'HOLD':
                    return {
                        'symbol': symbol,
                        'action': 'HOLD',
                        'price': current_price,
                        'profit': profit_percent,
                        'buy_price': buy_price,
                        'highest': highest_price,
                        'reason': sell_decision.get('reason', 'Hold')
                    }
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
                        mtf = get_multi_timeframe_analysis(exchange_instance, symbol)
                    should_sell, profit = should_sell_bearish(mtf, current_price, buy_price)
                    if should_sell:
                        sell_reason = "BEARISH TREND"
                
                # 3. Stop loss
                if not sell_reason:
                    should_sell, profit, reason = should_sell_stop_loss(current_price, highest_price, buy_price, STOP_LOSS_PERCENT)
                    if should_sell:
                        sell_reason = reason
                
                if not sell_reason:
                    return {
                        'symbol': symbol,
                        'action': 'HOLD',
                        'price': current_price,
                        'profit': profit_percent,
                        'buy_price': buy_price,
                        'highest': highest_price,
                        'reason': 'Hold'
                    }
            
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
        
        # ========== BUY LOGIC ==========
        else:
            if active_count >= MAX_POSITIONS:
                return None
            
            # Capital Management Check
            can_trade, reason = capital_manager.can_trade(BASE_AMOUNT, available, invested)
            if not can_trade:
                return None
            
            # Get MTF and calculate confidence
            mtf = get_multi_timeframe_analysis(exchange_instance, symbol)
            
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
                    mtf_boost = 0
            
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
            
            # Coin Ranking Check
            coin_rank_adjustment = 0
            if coin_ranker:
                try:
                    should_trade = coin_ranker.should_trade_coin(symbol)
                    if not should_trade['trade']:
                        return {'symbol': symbol, 'action': 'SKIP', 'reason': should_trade['reason']}
                    coin_rank_adjustment = should_trade.get('confidence_adjustment', 0) or 0
                except Exception as e:
                    coin_rank_adjustment = 0
            
            # Anomaly Detection
            if anomaly_detector:
                try:
                    anomaly_result = anomaly_detector.detect_anomalies(symbol, analysis)
                    if not anomaly_result['safe_to_trade']:
                        return {'symbol': symbol, 'action': 'SKIP', 'reason': f"ANOMALY: {anomaly_result['severity']}"}
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
                            return {'symbol': symbol, 'action': 'SKIP', 'reason': f"PATTERN: {pattern_analysis['recommendation']}"}
                        pattern_adjustment = pattern_analysis.get('confidence_adjustment', 0) or 0
                except Exception as e:
                    pattern_adjustment = 0
            
            # AI Decision
            if ai_brain:
                decision = ai_brain.should_buy(symbol, analysis, mtf, price_drop)
                
                # Apply all adjustments
                try:
                    mtf_boost = 0 if mtf_boost is None else mtf_boost
                    coin_rank_adjustment = 0 if coin_rank_adjustment is None else coin_rank_adjustment
                    pattern_adjustment = 0 if pattern_adjustment is None else pattern_adjustment
                    news_adjustment = 0 if news_adjustment is None else news_adjustment
                    
                    total_adjustment = mtf_boost + coin_rank_adjustment + pattern_adjustment + news_adjustment
                    if total_adjustment != 0:
                        decision['confidence'] = min(75, max(60, decision['confidence'] + total_adjustment))
                except Exception as e:
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
                if confidence >= MIN_CONFIDENCE:
                    return {
                        'symbol': symbol,
                        'action': 'BUY',
                        'amount': BASE_AMOUNT,
                        'price': current_price,
                        'confidence': confidence,
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
                        'confidence': confidence
                    }
    
    except Exception as e:
        return {'symbol': symbol, 'action': 'ERROR', 'message': str(e)}

# ========== MAIN LOOP ==========
try:
    loop_count = 0
    
    while True:
        loop_count += 1
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}\n⏰ {current_time}\n{'='*60}")
        
        # Update coin rankings (صامت) - استخدام العملات الديناميكية
        if coin_ranker and loop_count % 60 == 1:
            try:
                current_symbols = get_dynamic_symbols()
                rankings = coin_ranker.rank_all_coins(current_symbols)
            except Exception as e:
                pass
        
        # Balance (cached - update every 10 seconds)
        if loop_count == 1 or loop_count % 10 == 0:
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
        
        # عرض العملات (صامت)
        top_coins = coin_scanner.get_top_coins()
        
        # الحصول على القائمة الديناميكية
        current_symbols = get_dynamic_symbols()
        
        print(f"🔍 DEBUG: current_symbols returned from get_dynamic_symbols():")
        print(f"   {', '.join(sorted(current_symbols)[:20])}...")
        print(f"   Total: {len(current_symbols)} coins\n")
        
        print(f"🎯 About to analyze these {len(current_symbols)} symbols:")
        print(f"   {', '.join(sorted(current_symbols))}\n")
        
        # ========== PARALLEL PROCESSING ==========
        # Process symbols in parallel (5 threads at a time)
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all symbols for analysis
            future_to_symbol = {
                executor.submit(analyze_single_symbol, symbol, exchange, active_count, available, invested): symbol
                for symbol in current_symbols
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_symbol):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    symbol = future_to_symbol[future]
                    print(f"⚠️ {symbol}: Thread error - {e}")
        
        # ========== PROCESS RESULTS ==========
        # Filter: Show only active coins and open positions
        active_results = []
        for result in results:
            if not result:
                continue
            
            symbol = result['symbol']
            action = result['action']
            
            # Always show open positions (HOLD, SELL, SELL_WAIT)
            if action in ['HOLD', 'SELL', 'SELL_WAIT']:
                active_results.append(result)
                continue
            
            # Show BUY signals (active trading opportunities)
            if action == 'BUY':
                active_results.append(result)
                continue
            
            # Show DISPLAY only if confidence is good (active coin)
            if action == 'DISPLAY':
                if result.get('confidence', 0) >= 55:  # Active threshold
                    active_results.append(result)
                continue
            
            # Skip errors and low-confidence coins silently
        
        # Process and display active results
        for result in active_results:
            symbol = result['symbol']
            action = result['action']
            
            # Error handling (silent - already filtered)
            if action == 'ERROR':
                continue
            
            # Skip (silent - already filtered)
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
                print(f"{Fore.RED}🔴 SELL {symbol} | {result['reason']} | Profit: {result['profit']:+.2f}%{Style.RESET_ALL}")
                
                sell_result = execute_sell(exchange, symbol, result['amount'], result['reason'])
                if sell_result['success']:
                    sell_value = calculate_sell_value(result['amount'], result['price'])
                    send_sell_notification(symbol, result['amount'], result['price'], sell_value, result['profit'], result['reason'])
                    
                    # AI Learning
                    position = result['position']
                    if ai_brain:
                        try:
                            safe_profit = float(result['profit']) if result['profit'] is not None else 0
                            hours_held = 24
                            try:
                                buy_time_str = position.get('buy_time')
                                if buy_time_str:
                                    buy_time = datetime.fromisoformat(buy_time_str)
                                    hours_held = (datetime.now() - buy_time).total_seconds() / 3600
                            except:
                                pass
                            
                            trade_result = {
                                'symbol': symbol,
                                'action': 'SELL',
                                'profit_percent': safe_profit,
                                'sell_reason': result['reason'],
                                'tp_target': position.get('tp_target', 1.0),
                                'sl_target': position.get('sl_target', 2.0),
                                'max_wait_hours': position.get('max_wait_hours', 48),
                                'hours_held': hours_held
                            }
                            
                            if 'ai_data' in position:
                                trade_result.update(position['ai_data'])
                            
                            ai_brain.learn_from_trade(trade_result)
                        except Exception as e:
                            pass
                    
                    # Exit Strategy Learning
                    if exit_strategy:
                        try:
                            safe_profit = float(result['profit']) if result['profit'] is not None else 0
                            hours_held = 24
                            try:
                                buy_time_str = position.get('buy_time')
                                if buy_time_str:
                                    buy_time = datetime.fromisoformat(buy_time_str)
                                    hours_held = (datetime.now() - buy_time).total_seconds() / 3600
                            except:
                                pass
                            
                            exit_strategy.learn_from_exit(symbol, {
                                'profit_percent': safe_profit,
                                'sell_reason': result['reason'],
                                'hours_held': hours_held
                            })
                        except Exception as e:
                            pass
                    
                    # Pattern Recognition Learning
                    if pattern_recognizer:
                        try:
                            safe_profit = float(result['profit']) if result['profit'] is not None else 0
                            pattern_recognizer.learn_pattern({
                                'symbol': symbol,
                                'profit_percent': safe_profit,
                                'features': position.get('ai_data', {})
                            })
                        except Exception as e:
                            pass
                    
                    with symbols_data_lock:
                        SYMBOLS_DATA[symbol]['position'] = None
                    storage.save_positions(SYMBOLS_DATA)
                continue
            
            # Execute Buy
            if action == 'BUY':
                news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""
                
                if 'decision' in result:
                    print(f"{Fore.GREEN}🟢 BUY {symbol} 🧠 | AI Confidence:{result['confidence']}/120 | ${result['amount']}{news_display}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.GREEN}🟢 BUY {symbol} | Confidence:{result['confidence']}/120 | ${result['amount']}{Style.RESET_ALL}")
                
                buy_result = execute_buy(exchange, symbol, result['amount'], result['price'], result['confidence'])
                if buy_result['success']:
                    send_buy_notification(symbol, buy_result['amount'], result['price'], result['amount'], result['confidence'])
                    
                    position_data = {
                        'buy_price': buy_result['price'],
                        'amount': buy_result['amount'],
                        'highest_price': buy_result['price'],
                        'buy_time': datetime.now().isoformat()
                    }
                    
                    if 'decision' in result:
                        decision = result['decision']
                        position_data.update({
                            'tp_target': decision.get('tp_target', 1.0),
                            'sl_target': decision.get('sl_target', 2.0),
                            'max_wait_hours': decision.get('max_wait_hours', 48),
                            'ai_data': {
                                'confidence': result['confidence'],
                                'rsi': result['analysis']['rsi'],
                                'volume': result['analysis']['volume'],
                                'macd_diff': result['analysis']['macd_diff']
                            }
                        })
                    
                    with symbols_data_lock:
                        SYMBOLS_DATA[symbol]['position'] = position_data
                    active_count += 1
                    with balance_lock:
                        available -= result['amount']
                    storage.save_positions(SYMBOLS_DATA)
                continue
            
            # Display only
            if action == 'DISPLAY':
                vol_status = "🟢" if result['volume'] > 0.8 else "🔴"
                news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""
                print(f"📊 {symbol:12} ${result['price']:>8.2f} | RSI:{result['rsi']:>5.1f} | Vol:{vol_status} {result['volume']:.1f}x | MACD:{result['macd']:>+6.1f} | Conf:{result['confidence']}/120{news_display} | {result.get('reason', '')}")
                continue
        
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
    import traceback
    print(f"\n❌ Error: {e}")
    print(f"\n📍 Full traceback:")
    traceback.print_exc()
    print(f"\n🔄 Restarting in 5 seconds...")
    import time
    time.sleep(5)
