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

from memory.memory_optimizer import MemoryOptimizer # <<< استيراد المدير الصحي

# ================================================================
# ✅ دوال حساب الأعمدة الجديدة لتطوير النماذج
# ================================================================

def calculate_liquidity_features(symbol, analysis):
    """حساب ميزات السيولة المتقدمة"""
    try:
        # Order Book Imbalance
        order_book = analysis.get('order_book', {})
        bids_volume = sum(float(level[1]) for level in order_book.get('bids', [])[:10])
        asks_volume = sum(float(level[1]) for level in order_book.get('asks', [])[:10])
        total_volume = bids_volume + asks_volume
        order_book_imbalance = (bids_volume - asks_volume) / max(total_volume, 1) if total_volume > 0 else 0

        # Spread Volatility
        spread = analysis.get('spread', 0.001)
        avg_spread = analysis.get('average_spread', 0.001)
        spread_volatility = abs(spread - avg_spread) / max(avg_spread, 0.0001)

        # Depth at 1%
        price = analysis.get('price', 1)
        depth_1pct = 0
        for level in order_book.get('bids', []):
            if abs(float(level[0]) - price) / price <= 0.01:
                depth_1pct += float(level[1])
        for level in order_book.get('asks', []):
            if abs(float(level[0]) - price) / price <= 0.01:
                depth_1pct += float(level[1])

        # Market Impact Score
        volume_ratio = analysis.get('volume_ratio', 1)
        market_impact = min(volume_ratio / 10, 1.0)  # تطبيع

        # Liquidity Trends
        liquidity_trend = 0
        if volume_ratio > 1.5 and spread_volatility < 0.5:
            liquidity_trend = 1  # سيولة جيدة
        elif volume_ratio < 0.7 or spread_volatility > 1.0:
            liquidity_trend = -1  # سيولة سيئة

        return {
            'order_book_imbalance': round(order_book_imbalance, 4),
            'spread_volatility': round(spread_volatility, 4),
            'depth_at_1pct': round(depth_1pct, 2),
            'market_impact_score': round(market_impact, 4),
            'liquidity_trends': liquidity_trend
        }
    except Exception as e:
        print(f"⚠️ Liquidity features error: {e}")
        return {
            'order_book_imbalance': 0,
            'spread_volatility': 0,
            'depth_at_1pct': 0,
            'market_impact_score': 0,
            'liquidity_trends': 0
        }

def calculate_risk_features(symbol, analysis, market_data):
    """حساب ميزات المخاطر المتقدمة"""
    try:
        # Volatility Risk Score
        volatility = analysis.get('volatility', 0)
        avg_volatility = analysis.get('avg_volatility', 1)
        volatility_risk = min(volatility / max(avg_volatility, 0.1), 5.0)

        # Correlation Risk
        btc_corr = market_data.get('btc_correlation', 0)
        correlation_risk = abs(btc_corr) * 0.5  # مخاطر الارتباط

        # Gap Risk Score
        price = analysis.get('price', 1)
        prev_close = analysis.get('prev_close', price)
        gap_percent = abs(price - prev_close) / max(prev_close, 0.0001)
        gap_risk = min(gap_percent * 100, 10.0)

        # Black Swan Probability
        extreme_volatility = 1 if volatility > 5 else 0
        extreme_gap = 1 if gap_percent > 0.05 else 0
        black_swan_probability = (extreme_volatility + extreme_gap) * 0.3

        # Behavioral Risk
        sentiment = analysis.get('sentiment_score', 0)
        behavioral_risk = max(0, -sentiment)  # مخاطر نفسية

        # Systemic Risk
        market_volatility = market_data.get('market_volatility', 1)
        systemic_risk = min(market_volatility / 2, 3.0)

        return {
            'volatility_risk_score': round(volatility_risk, 4),
            'correlation_risk': round(correlation_risk, 4),
            'gap_risk_score': round(gap_risk, 4),
            'black_swan_probability': round(black_swan_probability, 4),
            'behavioral_risk': round(behavioral_risk, 4),
            'systemic_risk': round(systemic_risk, 4)
        }
    except Exception as e:
        print(f"⚠️ Risk features error: {e}")
        return {
            'volatility_risk_score': 0,
            'correlation_risk': 0,
            'gap_risk_score': 0,
            'black_swan_probability': 0,
            'behavioral_risk': 0,
            'systemic_risk': 0
        }

def calculate_exit_features(symbol, analysis, profit_percent):
    """حساب ميزات الخروج المتقدمة"""
    try:
        # Profit Optimization Score
        optimal_profit = 3.0  # هدف ربح مثالي
        profit_optimization = min(profit_percent / optimal_profit, 2.0)

        # Time Decay Signals
        hours_held = analysis.get('hours_held', 24)
        time_decay = max(0, 1 - (hours_held / 168))  # 168 ساعة = أسبوع

        # Opportunity Cost Exits
        market_trend = analysis.get('market_trend', 0)
        opportunity_cost = max(0, market_trend - profit_percent) * 0.1

        # Market Condition Exits
        rsi = analysis.get('rsi', 50)
        macd = analysis.get('macd_diff', 0)
        market_condition = 0
        if rsi > 75 and macd < -0.5:
            market_condition = 1  # إشارة بيع قوية
        elif rsi < 25 and macd > 0.5:
            market_condition = -1  # إشارة شراء

        return {
            'profit_optimization_score': round(profit_optimization, 4),
            'time_decay_signals': round(time_decay, 4),
            'opportunity_cost_exits': round(opportunity_cost, 4),
            'market_condition_exits': market_condition
        }
    except Exception as e:
        print(f"⚠️ Exit features error: {e}")
        return {
            'profit_optimization_score': 0,
            'time_decay_signals': 0,
            'opportunity_cost_exits': 0,
            'market_condition_exits': 0
        }

def calculate_pattern_features(symbol, analysis, candles):
    """حساب ميزات الأنماط المتقدمة"""
    try:
        # Harmonic Patterns Score
        harmonic_score = 0
        # منطق بسيط للكشف عن أنماط هارمونيك
        if len(candles) >= 5:
            # Fibonacci ratios check
            ratios = []
            for i in range(len(candles)-1):
                if candles[i]['high'] != candles[i]['low']:
                    ratio = (candles[i+1]['close'] - candles[i]['close']) / (candles[i]['high'] - candles[i]['low'])
                    ratios.append(abs(ratio))
            # Check for golden ratio patterns
            golden_ratios = [0.618, 1.618, 2.618]
            for ratio in ratios:
                for golden in golden_ratios:
                    if abs(ratio - golden) < 0.1:
                        harmonic_score += 0.2

        # Elliott Wave Signals
        elliott_signals = 0
        # بسيط: كشف موجات تصاعدية/هابطة
        trend = analysis.get('trend', 'neutral')
        if trend == 'bullish':
            elliott_signals = 1
        elif trend == 'bearish':
            elliott_signals = -1

        # Fractal Patterns
        fractal_patterns = 0
        if len(candles) >= 5:
            # كشف fractals بسيط
            for i in range(2, len(candles)-2):
                high = candles[i]['high']
                if all(high > c['high'] for c in candles[i-2:i]) and all(high > c['high'] for c in candles[i+1:i+3]):
                    fractal_patterns = 1  # قمة
                    break
                low = candles[i]['low']
                if all(low < c['low'] for c in candles[i-2:i]) and all(low < c['low'] for c in candles[i+1:i+3]):
                    fractal_patterns = -1  # قاع
                    break

        # Cycle Patterns
        cycle_patterns = 0
        # كشف دورات بسيطة بناءً على RSI
        rsi_values = [c.get('rsi', 50) for c in candles[-10:]]
        if len(rsi_values) >= 5:
            # كشف دورات overbought/oversold
            oversold_count = sum(1 for r in rsi_values if r < 30)
            overbought_count = sum(1 for r in rsi_values if r > 70)
            cycle_patterns = (overbought_count - oversold_count) * 0.1

        # Momentum Patterns
        momentum_patterns = 0
        momentum = analysis.get('price_momentum', 0)
        volume_trend = analysis.get('volume_trend', 0)
        if momentum > 0.5 and volume_trend > 0:
            momentum_patterns = 1  # زخم صاعد قوي
        elif momentum < -0.5 and volume_trend < 0:
            momentum_patterns = -1  # زخم هابط قوي

        return {
            'harmonic_patterns_score': round(harmonic_score, 4),
            'elliott_wave_signals': elliott_signals,
            'fractal_patterns': fractal_patterns,
            'cycle_patterns': round(cycle_patterns, 4),
            'momentum_patterns': momentum_patterns
        }
    except Exception as e:
        print(f"⚠️ Pattern features error: {e}")
        return {
            'harmonic_patterns_score': 0,
            'elliott_wave_signals': 0,
            'fractal_patterns': 0,
            'cycle_patterns': 0,
            'momentum_patterns': 0
        }

def calculate_smart_money_features(symbol, analysis):
    """حساب ميزات الأموال الذكية"""
    try:
        # Whale Wallet Changes
        large_orders = analysis.get('large_orders', [])
        whale_changes = sum(abs(order['amount']) for order in large_orders if abs(order['amount']) > 1000)

        # Institutional Accumulation
        institutional_flow = analysis.get('institutional_flow', 0)
        institutional_accumulation = institutional_flow * 0.001  # تطبيع

        # Smart Money Ratio
        whale_activity = analysis.get('whale_activity', 0)
        retail_activity = analysis.get('retail_activity', 1)
        smart_money_ratio = whale_activity / max(retail_activity, 0.1)

        # Exchange Whale Flows
        exchange_flows = analysis.get('exchange_whale_flows', 0)
        exchange_whale_flows = exchange_flows * 0.01  # تطبيع

        return {

            'smart_money_ratio': round(smart_money_ratio, 4),
            'exchange_whale_flows': round(exchange_whale_flows, 4)
        }
    except Exception as e:
        print(f"⚠️ Smart money features error: {e}")
        return {

            'smart_money_ratio': 0,
            'exchange_whale_flows': 0
        }

def calculate_anomaly_features(symbol, analysis):
    """حساب ميزات الشذوذ"""
    try:
        # Statistical Outliers
        price_changes = analysis.get('price_changes', [])
        if price_changes:
            mean_change = sum(price_changes) / len(price_changes)
            std_change = (sum((x - mean_change)**2 for x in price_changes) / len(price_changes))**0.5
            current_change = price_changes[-1] if price_changes else 0
            statistical_outliers = abs(current_change - mean_change) / max(std_change, 0.001)
        else:
            statistical_outliers = 0

        # Pattern Anomalies
        pattern_score = analysis.get('pattern_score', 0)
        avg_pattern_score = analysis.get('avg_pattern_score', 0)
        pattern_anomalies = abs(pattern_score - avg_pattern_score)

        # Behavioral Anomalies
        volume_ratio = analysis.get('volume_ratio', 1)
        unusual_volume = 1 if volume_ratio > 3 or volume_ratio < 0.3 else 0
        behavioral_anomalies = unusual_volume * 2

        # Volume Anomalies
        volume_changes = analysis.get('volume_changes', [])
        if volume_changes:
            volume_anomalies = max(volume_changes) / max(min(volume_changes), 1) - 1
        else:
            volume_anomalies = 0

        return {
            'statistical_outliers': round(statistical_outliers, 4),
            'pattern_anomalies': round(pattern_anomalies, 4),
            'behavioral_anomalies': behavioral_anomalies,
            'volume_anomalies': round(volume_anomalies, 4)
        }
    except Exception as e:
        print(f"⚠️ Anomaly features error: {e}")
        return {
            'statistical_outliers': 0,
            'pattern_anomalies': 0,
            'behavioral_anomalies': 0,
            'volume_anomalies': 0
        }

def calculate_chart_cnn_features(symbol, analysis, candles):
    """حساب ميزات Chart CNN"""
    try:
        # Attention Mechanism Score
        # بسيط: التركيز على الشموع الأخيرة
        recent_candles = candles[-10:] if len(candles) >= 10 else candles
        attention_weights = []
        for i, candle in enumerate(recent_candles):
            weight = 1 / (len(recent_candles) - i + 1)  # أهمية أكبر للشموع الأحدث
            attention_weights.append(weight)
        attention_mechanism_score = sum(attention_weights) / len(attention_weights)

        # Multi-scale Features
        # تحليل متعدد المقاييس
        scales = [5, 10, 20]  # مقاييس مختلفة
        multi_scale_score = 0
        for scale in scales:
            if len(candles) >= scale:
                scale_data = candles[-scale:]
                volatility = sum(abs(c['close'] - c['open']) for c in scale_data) / scale
                multi_scale_score += volatility * (scale / 20)  # وزن حسب المقياس
        multi_scale_features = multi_scale_score / len(scales)

        # Temporal Features
        # ميزات زمنية
        if len(candles) >= 5:
            temporal_patterns = 0
            # كشف أنماط زمنية بسيطة
            for i in range(len(candles)-4):
                sequence = [c['close'] > c['open'] for c in candles[i:i+5]]
                if sequence == [True, True, True, False, False]:  # نمط تصاعدي ثم هابط
                    temporal_patterns += 1
                elif sequence == [False, False, False, True, True]:  # نمط هابط ثم صاعد
                    temporal_patterns -= 1
            temporal_features = temporal_patterns * 0.1
        else:
            temporal_features = 0

        return {
            'attention_mechanism_score': round(attention_mechanism_score, 4),
            'multi_scale_features': round(multi_scale_features, 4),
            'temporal_features': round(temporal_features, 4)
        }
    except Exception as e:
        print(f"⚠️ Chart CNN features error: {e}")
        return {
            'attention_mechanism_score': 0,
            'multi_scale_features': 0,
            'temporal_features': 0
        }

def calculate_meta_learner_features(symbol, analysis, consultant_votes):
    """حساب ميزات Meta-Learner"""
    try:
        # Dynamic Consultant Weights
        total_votes = len(consultant_votes)
        if total_votes > 0:
            positive_votes = sum(1 for v in consultant_votes.values() if v == 1)
            agreement_ratio = positive_votes / total_votes
            dynamic_consultant_weights = agreement_ratio * 2 - 1  # -1 إلى 1
        else:
            dynamic_consultant_weights = 0

        # Uncertainty Quantification
        vote_variance = 0
        if total_votes > 1:
            mean_vote = sum(consultant_votes.values()) / total_votes
            vote_variance = sum((v - mean_vote)**2 for v in consultant_votes.values()) / total_votes
        uncertainty_quantification = vote_variance * 10  # تطبيع

        # Context Aware Score
        market_context = analysis.get('market_context', 0)
        technical_context = analysis.get('technical_context', 0)
        context_aware_score = (market_context + technical_context) / 2

        return {
            'dynamic_consultant_weights': round(dynamic_consultant_weights, 4),
            'uncertainty_quantification': round(uncertainty_quantification, 4),
            'context_aware_score': round(context_aware_score, 4)
        }
    except Exception as e:
        print(f"⚠️ Meta-learner features error: {e}")
        return {
            'dynamic_consultant_weights': 0,
            'uncertainty_quantification': 0,
            'context_aware_score': 0
        }

def calculate_volume_features(symbol, analysis, candles):
    """حساب ميزات حجم التداول المتقدمة"""
    try:
        volume_ratios = []
        if candles:
            for i in range(1, min(21, len(candles))):  # آخر 20 شمعة
                if candles[i-1]['volume'] > 0:
                    ratio = candles[i]['volume'] / candles[i-1]['volume']
                    volume_ratios.append(ratio)

        # Volume Trend Strength
        if volume_ratios:
            avg_ratio = sum(volume_ratios) / len(volume_ratios)
            volume_trend_strength = (avg_ratio - 1) * 10  # تطبيع
        else:
            volume_trend_strength = 0

        # Volume Volatility
        if len(volume_ratios) > 1:
            mean_ratio = sum(volume_ratios) / len(volume_ratios)
            variance = sum((r - mean_ratio)**2 for r in volume_ratios) / len(volume_ratios)
            volume_volatility = variance * 100  # تطبيع
        else:
            volume_volatility = 0

        # Volume Momentum
        volume_momentum = 0
        if len(candles) >= 10:
            recent_avg = sum(c['volume'] for c in candles[-5:]) / 5
            older_avg = sum(c['volume'] for c in candles[-10:-5]) / 5
            if older_avg > 0:
                volume_momentum = ((recent_avg - older_avg) / older_avg) * 100

        # Volume Seasonality (افتراضي - يمكن تحسينه بتحليل زمني)
        current_hour = analysis.get('hour', 12)
        if 9 <= current_hour <= 15:  # ساعات التداول النشطة
            volume_seasonality = 1.0
        else:
            volume_seasonality = 0.5

        # Volume Correlation (ارتباط الحجم مع السعر)
        price_changes = []
        volume_changes = []
        if len(candles) >= 5:
            for i in range(1, 6):
                if candles[i-1]['close'] > 0 and candles[i-1]['volume'] > 0:
                    price_change = (candles[i]['close'] - candles[i-1]['close']) / candles[i-1]['close']
                    volume_change = (candles[i]['volume'] - candles[i-1]['volume']) / candles[i-1]['volume']
                    price_changes.append(price_change)
                    volume_changes.append(volume_change)

        if len(price_changes) >= 3:
            # حساب معامل الارتباط البسيط
            n = len(price_changes)
            sum_xy = sum(p * v for p, v in zip(price_changes, volume_changes))
            sum_x = sum(price_changes)
            sum_y = sum(volume_changes)
            sum_x2 = sum(p**2 for p in price_changes)
            sum_y2 = sum(v**2 for v in volume_changes)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2)) ** 0.5

            volume_correlation = numerator / denominator if denominator != 0 else 0
        else:
            volume_correlation = 0

        return {
            'volume_trend_strength': round(volume_trend_strength, 4),
            'volume_volatility': round(volume_volatility, 4),
            'volume_momentum': round(volume_momentum, 4),
            'volume_seasonality': round(volume_seasonality, 4),
            'volume_correlation': round(volume_correlation, 4)
        }
    except Exception as e:
        print(f"⚠️ Volume features error: {e}")
        return {
            'volume_trend_strength': 0,
            'volume_volatility': 0,
            'volume_momentum': 0,
            'volume_seasonality': 0,
            'volume_correlation': 0
        }

# ================================================================
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
print("        🚀 MSA Smart Trading Bot V2.0")
print("        💰 Binance Testnet - Enhanced AI & Whale Tracking")
if meta:
    print("        👑 The King (Meta): ACTIVE with King Memory")
print("        🧠 Deep Learning Models (LightGBM) - 41 Features")
print("        📊 Multi-Timeframe + Advanced Risk Manager")
print("        🐋 Whale Tracking + Sentiment Analysis")
print("        🏆 Coin Ranking + Enhanced Anomaly Detection")
print("        🎯 Smart Exit Strategy + Pattern Recognition")
print("        📰 News Sentiment + Panic/Greed Analysis")
print("        🔍 Top 10 from 50 Coins with King Memory")
print("        ✅ Version 2.0 - AI Learning V4 with External APIs")
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
            decision = meta.should_sell(symbol, position, current_price, analysis, analysis.get('mtf', {}), preloaded_advisors)
            timing_data['meta_should_sell'] = (time.time() - sell_logic_start) * 1000

            if decision and decision.get('action') == 'SELL':
                amount = position['amount']
                sell_value = calculate_sell_value(amount, current_price)
                if sell_value < 9.99:
                    return {'symbol': symbol, 'action': 'SELL_WAIT', 'reason': decision.get('reason'), 'value': sell_value}
                else:
                    # ✅ حساب whale_confidence و atr_value بشكل مباشر من البيانات الحقيقية
                    whale_confidence = 0
                    atr_value = 0
                    sentiment_score = 0

                    # حساب ATR من candles إذا كانت متوفرة
                    candles = analysis.get('candles', [])
                    if candles and len(candles) >= 14:
                        try:
                            # حساب ATR بسيط (14 فترة)
                            tr_values = []
                            for i in range(1, min(15, len(candles))):
                                high = candles[i]['high']
                                low = candles[i]['low']
                                prev_close = candles[i-1]['close']
                                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                                tr_values.append(tr)
                            atr_value = sum(tr_values) / len(tr_values) if tr_values else 0
                            atr_value = round(atr_value, 6)
                        except Exception as e:
                            print(f"⚠️ ATR calculation error: {e}")
                            atr_value = 0

                    # حساب whale_confidence من حجم التداول والسعر
                    try:
                        volume_ratio = analysis.get('volume_ratio', 1)
                        price_change = analysis.get('price_momentum', 0)

                        # Whale confidence بناءً على حجم واتجاه السعر
                        if volume_ratio > 3 and price_change > 0.5:
                            whale_confidence = 15  # حيتان تشتري بقوة
                        elif volume_ratio > 3 and price_change < -0.5:
                            whale_confidence = -15  # حيتان تبيع بقوة
                        elif volume_ratio > 2 and price_change > 0:
                            whale_confidence = 8   # حيتان تشتري
                        elif volume_ratio > 2 and price_change < 0:
                            whale_confidence = -8  # حيتان تبيع
                        elif volume_ratio < 0.5:
                            whale_confidence = -5  # حجم منخفض = عدم اهتمام

                        whale_confidence = max(-20, min(20, whale_confidence))
                    except Exception as e:
                        print(f"⚠️ whale_confidence calculation error: {e}")
                        whale_confidence = 0

                    # جلب sentiment إضافي من الأخبار
                    try:
                        from src.news_analyzer import NewsAnalyzer
                        news_analyzer = NewsAnalyzer()
                        sentiment_data = news_analyzer.get_news_sentiment(symbol, hours=24)
                        sentiment_score = sentiment_data['news_score'] if sentiment_data else 0
                    except Exception as e:
                        print(f"⚠️ sentiment calculation error: {e}")
                        sentiment_score = 0

                    # ✅ حساب الأعمدة الجديدة عند البيع أيضاً
                    try:
                        sell_profit = calculate_profit_percent(current_price, position['buy_price'])
                        market_data = {'btc_correlation': 0, 'market_volatility': 1}
                        consultant_votes = decision.get('sell_votes', {})

                        liquidity_data   = calculate_liquidity_features(symbol, analysis)
                        risk_data        = calculate_risk_features(symbol, analysis, market_data)
                        exit_data        = calculate_exit_features(symbol, analysis, sell_profit)
                        pattern_data     = calculate_pattern_features(symbol, analysis, candles)
                        smart_money_data = calculate_smart_money_features(symbol, analysis)
                        anomaly_data     = calculate_anomaly_features(symbol, analysis)
                        cnn_data         = calculate_chart_cnn_features(symbol, analysis, candles)
                        volume_data      = calculate_volume_features(symbol, analysis, candles)
                        meta_feat_data   = calculate_meta_learner_features(symbol, analysis, consultant_votes)

                        advanced_features = {
                            **liquidity_data, **risk_data, **exit_data,
                            **pattern_data, **smart_money_data, **anomaly_data,
                            **cnn_data, **volume_data, **meta_feat_data
                        }
                    except Exception as e:
                        print(f"⚠️ advanced_features (sell) error: {e}")
                        advanced_features = {}

                    return {
                        'symbol': symbol,
                        'action': 'SELL',
                        'amount': amount,
                        'price': current_price,
                        'profit': calculate_profit_percent(current_price, position['buy_price']),
                        'reason': decision.get('reason'),
                        'position': position,
                        'sell_votes': decision.get('sell_votes', {}),
                        'whale_confidence': whale_confidence,
                        'atr_value': atr_value,
                        'sentiment_score': sentiment_score,
                        'panic_score': analysis.get('panic_greed', {}).get('panic_score', 0),
                        'optimism_penalty': 15 if calculate_profit_percent(current_price, position['buy_price']) > 15 else 0,
                        'psychological_analysis': f"Panic:{analysis.get('panic_greed', {}).get('panic_score', 0)}, Greed:{analysis.get('panic_greed', {}).get('greed_score', 0)}",
                        'analysis': analysis,                    # ✅ للحسابات في sell_handler
                        'candles': candles,                      # ✅ للحسابات في sell_handler
                        **advanced_features
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
                # الصفقات ممتلئة - لا نشتري لكن نحلل ونعرض STRONG إذا العملة قوية
                decision = meta.should_buy(symbol, analysis, preloaded_advisors)
                meta_action = decision.get('action', 'DISPLAY') if decision else 'DISPLAY'
                meta_conf   = decision.get('confidence', 0) if decision else 0
                #print(f"🔍 DEBUG FULL [{symbol}] → Meta={meta_action} Conf={meta_conf} | RSI={analysis.get('rsi',0):.0f} Vol={analysis.get('volume_ratio',0):.1f}x")
                display_action = meta_action if meta_action == 'STRONG' else 'DISPLAY'
                return {
                    'symbol': symbol,
                    'action': display_action,
                    'price': analysis.get('close', 0),
                    'rsi': analysis.get('rsi', 0),
                    'volume': analysis.get('volume_ratio', 0),
                    'macd': analysis.get('macd_diff', 0),
                    'confidence': meta_conf,
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

            meta_action = decision.get('action', 'DISPLAY') if decision else 'DISPLAY'
            meta_conf   = decision.get('confidence', 0) if decision else 0
            #print(f"🔍 DEBUG FREE [{symbol}] → Meta={meta_action} Conf={meta_conf} | RSI={analysis.get('rsi',0):.0f} Vol={analysis.get('volume_ratio',0):.1f}x")

            if decision and meta_action == 'BUY':
                # ✅ حساب الأعمدة الجديدة للنماذج
                market_data = {'btc_correlation': 0, 'market_volatility': 1}  # بيانات سوق مؤقتة
                candles = analysis.get('candles', [])
                consultant_votes = decision.get('consultant_votes', {})

                # حساب جميع الميزات الجديدة
                liquidity_data = calculate_liquidity_features(symbol, analysis)
                risk_data = calculate_risk_features(symbol, analysis, market_data)
                exit_data = calculate_exit_features(symbol, analysis, 0)  # profit = 0 للشراء
                pattern_data = calculate_pattern_features(symbol, analysis, candles)
                smart_money_data = calculate_smart_money_features(symbol, analysis)
                anomaly_data = calculate_anomaly_features(symbol, analysis)
                cnn_data = calculate_chart_cnn_features(symbol, analysis, candles)
                meta_data = calculate_meta_learner_features(symbol, analysis, consultant_votes)

                # دمج البيانات
                advanced_features = {
                    **liquidity_data,
                    **risk_data,
                    **exit_data,
                    **pattern_data,
                    **smart_money_data,
                    **anomaly_data,
                    **cnn_data,
                    **meta_data
                }

                return {
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_price,
                    'amount': decision.get('amount', MIN_TRADE_AMOUNT),
                    'confidence': meta_conf,
                    'reason': decision.get('reason', ''),
                    'decision': decision,
                    'rsi': analysis.get('rsi', 0),
                    'volume': analysis.get('volume_ratio', 0),
                    'macd_diff': analysis.get('macd_diff', 0),
                    'news_summary': decision.get('news_summary'),
                    'models_scores': decision.get('meta_scores', {}),
                    **advanced_features  # ✅ إضافة جميع الميزات الجديدة
                }

            # عملة قوية - الملك راضي لكن الأصوات ناقصة
            if decision and meta_action == 'STRONG':
                # ✅ حساب الأعمدة الجديدة للنماذج
                market_data = {'btc_correlation': 0, 'market_volatility': 1}
                candles = analysis.get('candles', [])
                consultant_votes = decision.get('consultant_votes', {})

                liquidity_data = calculate_liquidity_features(symbol, analysis)
                risk_data = calculate_risk_features(symbol, analysis, market_data)
                exit_data = calculate_exit_features(symbol, analysis, 0)
                pattern_data = calculate_pattern_features(symbol, analysis, candles)
                smart_money_data = calculate_smart_money_features(symbol, analysis)
                anomaly_data = calculate_anomaly_features(symbol, analysis)
                cnn_data = calculate_chart_cnn_features(symbol, analysis, candles)
                volume_data = calculate_volume_features(symbol, analysis, candles)
                meta_data = calculate_meta_learner_features(symbol, analysis, consultant_votes)

                advanced_features = {
                    **liquidity_data,
                    **risk_data,
                    **exit_data,
                    **pattern_data,
                    **smart_money_data,
                    **anomaly_data,
                    **cnn_data,
                    **volume_data,
                    **meta_data
                }

                return {
                    'symbol': symbol,
                    'action': 'STRONG',
                    'price': analysis.get('close', 0),
                    'rsi': analysis.get('rsi', 0),
                    'volume': analysis.get('volume_ratio', 0),
                    'macd': analysis.get('macd_diff', 0),
                    'confidence': meta_conf,
                    'reason': decision.get('reason', ''),
                    'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None,
                    **advanced_features
                }

            # If meta explicitly says to SKIP, then skip it.
            if decision and meta_action == 'SKIP':
                return {'symbol': symbol, 'action': 'SKIP', 'reason': decision.get('reason')}

            # DISPLAY - عملة عادية
            # ✅ حساب الأعمدة الجديدة للنماذج
            market_data = {'btc_correlation': 0, 'market_volatility': 1}
            candles = analysis.get('candles', [])
            consultant_votes = decision.get('consultant_votes', {}) if decision else {}

            liquidity_data = calculate_liquidity_features(symbol, analysis)
            risk_data = calculate_risk_features(symbol, analysis, market_data)
            exit_data = calculate_exit_features(symbol, analysis, 0)
            pattern_data = calculate_pattern_features(symbol, analysis, candles)
            smart_money_data = calculate_smart_money_features(symbol, analysis)
            anomaly_data = calculate_anomaly_features(symbol, analysis)
            cnn_data = calculate_chart_cnn_features(symbol, analysis, candles)
            volume_data = calculate_volume_features(symbol, analysis, candles)
            meta_data = calculate_meta_learner_features(symbol, analysis, consultant_votes)

            advanced_features = {
                **liquidity_data,
                **risk_data,
                **exit_data,
                **pattern_data,
                **smart_money_data,
                **anomaly_data,
                **cnn_data,
                **volume_data,
                **meta_data
            }

            return {
                'symbol': symbol,
                'action': 'DISPLAY',
                'price': analysis.get('close', 0),
                'rsi': analysis.get('rsi', 0),
                'volume': analysis.get('volume_ratio', 0),
                'macd': analysis.get('macd_diff', 0),
                'confidence': meta_conf,
                'reason': decision.get('reason', 'Monitoring') if decision else 'Monitoring',
                'news_summary': decision.get('news_summary') if decision and 'news_summary' in decision else None,
                **advanced_features
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

# طباعة رسالة البداية المحدثة
print("🤖 MSA Trading Bot V2.0 - Enhanced AI Learning, Whale Tracking, Sentiment Analysis")
print("🔗 External APIs: NewsAPI, Alpha Vantage, CoinGecko, Whale Alert")
print("🧠 Features: Panic/Greed Detection, Optimism Avoidance, King Memory")
print("🚀 Ready for Smart Trading!")

while True:
    try:
        run_main_loop(exchange, ctx)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        print(f"🔄 Restarting in 5 seconds...")
        time.sleep(5)
