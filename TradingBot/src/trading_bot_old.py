# ========== AUTO-INSTALL DEPENDENCIES ==========
def install_dependencies():
    """تثبيت المكتبات المطلوبة تلقائياً"""
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
            print(f"✅ Installed {package}")

install_dependencies()

import ccxt
import pandas as pd
import ta
import time
import json
import os
import requests
import gc
from datetime import datetime
from colorama import init, Fore, Style
from config_encrypted import get_api_keys, get_discord_webhook
from storage import StorageManager

# ========== IMPORT MODULES ==========
from analysis import (
    get_market_analysis,
    get_multi_timeframe_analysis,
    check_price_drop_from_peak,
    check_profit_drop_from_peak,
    calculate_volatility,
    calculate_dynamic_confidence
)
from trading import (
    buy_order,
    sell_order,
    get_boost_amount,
    check_volume_smart,
    adjust_confidence_for_oversold,
    get_adaptive_settings
)
from utils import (
    send_discord,
    log_trade,
    get_available_balance,
    get_total_invested,
    get_max_coins_to_trade,
    is_blacklisted,
    check_market_crash,
    should_sell_at_loss_simple,
    send_positions_report
)

# ========== AI BRAIN IMPORT ==========
try:
    from ai_brain import AIBrain
    AI_ENABLED = True
    print("🧠 AI Brain loaded successfully")
except Exception as e:
    AI_ENABLED = False
    print(f"⚠️ AI Brain not available: {e}")

init(autoreset=True)

# ========== INITIALIZE STORAGE ==========
storage = StorageManager()

# ========== SECURE API KEYS ==========
API_KEY, SECRET_KEY = get_api_keys()
if not API_KEY:
    print("❌ Failed to decrypt keys. Exiting...")
    exit()

# ========== DISCORD WEBHOOK (ENCRYPTED) ==========
DISCORD_WEBHOOK = get_discord_webhook()
if not DISCORD_WEBHOOK:
    print("⚠️ Discord webhook decryption failed. Notifications disabled.")
    DISCORD_WEBHOOK = None

# ========== DISCORD WRAPPER ==========
def send_discord_message(message, color=None):
    """Wrapper for send_discord"""
    send_discord(DISCORD_WEBHOOK, message, color)

# ========== MULTI-COIN CONFIGURATION ==========
TRADE_AMOUNT = 10  # المبلغ الأساسي لكل عملة (الحد الأدنى)
MAX_COINS = 20  # الحد الأقصى للعملات
TARGET_CAPITAL = 120  # رأس المال المستهدف ($120 = 450 ريال)

# ========== SMART BOOST SYSTEM (CONFIDENCE-BASED) ==========
BOOST_ENABLED = True  # تفعيل نظام التعزيز الذكي
BOOST_AMOUNTS = {
    60: 10,   # Confidence 60-69  → $10 (عادي)
    70: 12,   # Confidence 70-79  → $12 (+20%)
    80: 14,   # Confidence 80-89  → $14 (+40%)
    90: 16,   # Confidence 90-99  → $16 (+60%)
    100: 18,  # Confidence 100-109 → $18 (+80%)
    110: 20   # Confidence 110-120 → $20 (+100%)
}

# ========== SMART FILTERS (ANTI-TRAP PROTECTION) ==========
MIN_CONFIDENCE = 60  # الحد الأدنى للشراء (الفلاتر الذكية تحمي من الفخاخ)

# ========== AI BOUNDARIES ==========
AI_BOUNDARIES = {
    'min_confidence': 50,
    'max_confidence': 70,
    'min_volume': 0.8,
    'max_volume': 3.0,
    'min_amount': 10,
    'max_amount': 20,
    'max_loss_per_trade': 2.0,
    'max_daily_loss': 5.0
}

# العملات التي تحتاج $10 كحد أدنى (يتعلم تلقائياً)
HIGH_NOTIONAL_COINS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'LTC/USDT', 'FIL/USDT', 'ARB/USDT', 'APT/USDT', 'DOT/USDT', 'UNI/USDT', 'INJ/USDT', 'SOL/USDT', 'XRP/USDT', 'AVAX/USDT']

SYMBOLS = {
    'BTC/USDT': {'position': None, 'priority': 1, 'losses': 0, 'blacklisted_until': None},
    'ETH/USDT': {'position': None, 'priority': 2, 'losses': 0, 'blacklisted_until': None},
    'BNB/USDT': {'position': None, 'priority': 3, 'losses': 0, 'blacklisted_until': None},
    'SOL/USDT': {'position': None, 'priority': 4, 'losses': 0, 'blacklisted_until': None},
    'XRP/USDT': {'position': None, 'priority': 5, 'losses': 0, 'blacklisted_until': None},
    'ADA/USDT': {'position': None, 'priority': 6, 'losses': 0, 'blacklisted_until': None},
    'AVAX/USDT': {'position': None, 'priority': 7, 'losses': 0, 'blacklisted_until': None},
    'LINK/USDT': {'position': None, 'priority': 8, 'losses': 0, 'blacklisted_until': None},
    'DOT/USDT': {'position': None, 'priority': 9, 'losses': 0, 'blacklisted_until': None},
    'DOGE/USDT': {'position': None, 'priority': 10, 'losses': 0, 'blacklisted_until': None},
    'UNI/USDT': {'position': None, 'priority': 11, 'losses': 0, 'blacklisted_until': None},
    'ATOM/USDT': {'position': None, 'priority': 12, 'losses': 0, 'blacklisted_until': None},
    'LTC/USDT': {'position': None, 'priority': 13, 'losses': 0, 'blacklisted_until': None},
    'ETC/USDT': {'position': None, 'priority': 14, 'losses': 0, 'blacklisted_until': None},
    'NEAR/USDT': {'position': None, 'priority': 15, 'losses': 0, 'blacklisted_until': None},
    'FIL/USDT': {'position': None, 'priority': 16, 'losses': 0, 'blacklisted_until': None},
    'APT/USDT': {'position': None, 'priority': 17, 'losses': 0, 'blacklisted_until': None},
    'ARB/USDT': {'position': None, 'priority': 18, 'losses': 0, 'blacklisted_until': None},
    'OP/USDT': {'position': None, 'priority': 19, 'losses': 0, 'blacklisted_until': None},
    'INJ/USDT': {'position': None, 'priority': 20, 'losses': 0, 'blacklisted_until': None}
}

RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
# ========== ADAPTIVE SETTINGS (Auto-Adjust) - FAST & BOLD ==========
BASE_STOP_LOSS = 0.8  # Stop Loss سريع (كان 2%)
BASE_TP_LEVELS = [1, 1.5, 2]  # Take Profit سريع 1-2% (كان 3%)
TP_AMOUNTS = [1.0]  # 100% مرة واحدة
TRAILING_STOP_PERCENT = 0.8  # أسرع (كان 2%)
MARKET_CRASH_THRESHOLD = -5
BLACKLIST_LOSSES = 3
BLACKLIST_DAYS = 7

# ========== LOSS PROTECTION ==========
MAX_LOSS_PERCENT = 2  # أقصى خسارة مسموحة
WAIT_FOR_RECOVERY = True  # ينتظر الانتعاش بدل البيع بخسارة
RECOVERY_TIMEOUT_HOURS = 48  # ينتظر 48 ساعة قبل البيع الإجباري

# ========== INITIALIZE EXCHANGE ==========
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
})
exchange.set_sandbox_mode(True)

print("=" * 60)
print("")
print("  ███╗   ███╗███████╗ █████╗ ")
print("  ████╗ ████║██╔════╝██╔══██╗")
print("  ██╔████╔██║███████╗███████║")
print("  ██║╚██╔╝██║╚════██║██╔══██║")
print("  ██║ ╚═╝ ██║███████║██║  ██║")
print("  ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝")
print("")
print("  ✦•······················•✦•······················•✦")
print("        🚀 MSA Smart Trading Bot")
print("        💰 Binance Testnet - Priority System")
print("        📊 20 Coins | Smart Boost System")
print("        🧠 Auto-Adjust + Multi-Timeframe")
print("        🛡️ Loss Protection System")
print("        ⚡ Score-Based Investment")
print("        ✅ Version 6.0 - Smart & Bold 🧠⚡")
print("  ✦•······················•✦•······················•✦")
print("")
print("=" * 60)

# ========== FUNCTIONS ==========
def get_available_balance():
    """حساب الرصيد المتاح"""
    try:
        balance = exchange.fetch_balance()
        return balance['USDT']['free']
    except:
        return 0

def get_total_invested():
    """حساب رأس المال المستثمر"""
    total = 0
    for config in SYMBOLS.values():
        if config['position']:
            total += config['position']['buy_price'] * config['position']['amount']
    return total

def can_buy_more_coins():
    """فحص إذا ممكن شراء عملات إضافية"""
    total_invested = get_total_invested()
    return total_invested < TARGET_CAPITAL

def get_max_coins_to_trade():
    """حساب عدد العملات المسموح التداول فيها"""
    available = get_available_balance()
    total_invested = get_total_invested()
    total_capital = available + total_invested
    max_coins = int(total_capital / TRADE_AMOUNT)
    return min(max_coins, MAX_COINS)

def save_positions():
    """حفظ المراكز (JSON أو PostgreSQL)"""
    try:
        storage.save_positions(SYMBOLS)
    except Exception as e:
        print(f"Error saving: {e}")

def load_positions():
    """تحميل المراكز (JSON أو PostgreSQL)"""
    try:
        data = storage.load_positions()
        for symbol, pos in data.items():
            if symbol in SYMBOLS:
                SYMBOLS[symbol]['position'] = pos
                print(f"📂 Loaded {symbol}: ${pos['buy_price']:.2f}")
    except Exception as e:
        print(f"Error loading: {e}")

def send_discord(message, color=None):
    """إرسال رسالة لـ Discord"""
    if not DISCORD_WEBHOOK:
        return
    try:
        colors = {'green': 0x00ff00, 'red': 0xff0000, 'yellow': 0xffff00, 'blue': 0x00ffff}
        data = {
            "embeds": [{
                "description": message,
                "color": colors.get(color, 0x00ffff)
            }]
        }
        requests.post(DISCORD_WEBHOOK, json=data, timeout=5)
    except:
        pass

def send_positions_report():
    """إرسال تقرير المراكز لـ Discord"""
    try:
        positions = []
        total_profit = 0
        
        for symbol, config in SYMBOLS.items():
            if config['position']:
                pos = config['position']
                analysis = get_market_analysis(symbol)
                if analysis:
                    current_price = analysis['price']
                    buy_price = pos['buy_price']
                    profit_percent = ((current_price - buy_price) / buy_price) * 100
                    total_profit += profit_percent
                    
                    emoji = "🟢" if profit_percent > 0 else "🔴"
                    positions.append(f"{emoji} **{symbol}**\n┌ Buy: ${buy_price:.2f}\n└ Now: ${current_price:.2f} ({profit_percent:+.2f}%)")
        
        if positions:
            avg_profit = total_profit / len(positions)
            color = 'green' if avg_profit > 0 else 'red' if avg_profit < 0 else 'yellow'
            
            report = f"📊 **Portfolio Report**\n\n"
            report += "\n\n".join(positions)
            report += f"\n\n💰 **Total:** {len(positions)} positions\n📈 **Avg P/L:** {avg_profit:+.2f}%"
            
            send_discord(report, color)
    except Exception as e:
        print(f"⚠️ Report error: {e}")

def log_trade(action, symbol, amount, price, profit=None, highest_price=None, reason=None):
    try:
        # إنشاء المجلد لو مو موجود
        os.makedirs('../data', exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('../data/trades.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n[{timestamp}] {action} {symbol}\n")
            f.write(f"Amount: {amount} | Price: ${price:.2f}")
            if profit:
                f.write(f" | Profit: {profit:.2f}%")
            if highest_price:
                f.write(f" | Highest: ${highest_price:.2f}")
            if reason:
                f.write(f" | Reason: {reason}")
            f.write(f"\n{'='*60}\n")
    except:
        pass

def check_overall_market():
    """فحص السوق العام قبل الشراء"""
    try:
        # فحص BTC كمؤشر للسوق
        btc_analysis = get_market_analysis('BTC/USDT')
        if btc_analysis:
            # لو BTC في هبوط قوي
            if btc_analysis['price_momentum'] < -3 and btc_analysis['rsi'] < 35:
                return 'crash'
            # لو BTC في صعود
            elif btc_analysis['price_momentum'] > 2 and btc_analysis['rsi'] > 50:
                return 'bullish'
        return 'neutral'
    except:
        return 'neutral'

def check_market_crash():
    """فحص انهيار السوق"""
    positions_count = sum(1 for s in SYMBOLS.values() if s['position'])
    
    # لو ما في مراكز مفتوحة، ما نفحص الانهيار
    if positions_count == 0:
        return False
    
    crash_count = 0
    for symbol, config in SYMBOLS.items():
        if config['position']:
            pos = config['position']
            analysis = get_market_analysis(symbol)
            if analysis:
                profit = ((analysis['price'] - pos['buy_price']) / pos['buy_price']) * 100
                if profit <= MARKET_CRASH_THRESHOLD:
                    crash_count += 1
    
    # إذا 50% من العملات في خسارة كبيرة
    if crash_count >= positions_count / 2:
        return True
    return False

def is_blacklisted(symbol):
    """فحص إذا العملة محظورة"""
    config = SYMBOLS[symbol]
    if config['blacklisted_until']:
        if datetime.now() < datetime.fromisoformat(config['blacklisted_until']):
            return True
        else:
            config['blacklisted_until'] = None
            config['losses'] = 0
    return False

def check_price_drop_from_peak(symbol):
    """فحص انخفاض السعر من آخر ساعة (للشراء الذكي)"""
    try:
        # جلب بيانات آخر ساعة
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=12)  # 12 × 5min = 60min
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # أعلى سعر في آخر ساعة
        highest_price = df['high'].max()
        current_price = df['close'].iloc[-1]
        
        # حساب نسبة الانخفاض
        drop_percent = ((highest_price - current_price) / highest_price) * 100
        
        return {
            'drop_percent': drop_percent,
            'highest_1h': highest_price,
            'current': current_price,
            'confirmed': drop_percent >= 2.0  # نزل 2% أو أكثر
        }
    except:
        return {'drop_percent': 0, 'confirmed': False}

def check_profit_drop_from_peak(position, current_price):
    """فحص انخفاض الربح من القمة (للبيع الذكي)"""
    try:
        buy_price = position['buy_price']
        highest_price = position['highest_price']
        
        # أعلى ربح وصل له
        highest_profit = ((highest_price - buy_price) / buy_price) * 100
        
        # الربح الحالي
        current_profit = ((current_price - buy_price) / buy_price) * 100
        
        # الانخفاض من القمة
        drop_from_peak = highest_profit - current_profit
        
        return {
            'highest_profit': highest_profit,
            'current_profit': current_profit,
            'drop_from_peak': drop_from_peak,
            'should_sell': drop_from_peak >= 0.5  # نزل 0.5% من القمة
        }
    except:
        return {'should_sell': False}



def calculate_dynamic_confidence(symbol, analysis, mtf, price_drop):
    """حساب نقاط الثقة الديناميكي للشراء (مع حماية)"""
    try:
        rsi = analysis['rsi']
        macd_diff = analysis['macd_diff']
        momentum = analysis['price_momentum']
        volume_ratio = analysis['volume_ratio']
        trend = mtf['trend']
        drop_percent = price_drop['drop_percent']
        
        # الحدود الدنيا (حماية من الفخاخ)
        if rsi > 70:  # overbought
            return 0, "RSI too high (overbought)"
        if volume_ratio < 0.6:  # حجم ضعيف جداً
            return 0, "Volume too low"
        if trend == 'bearish':  # ممنوع
            return 0, "Bearish trend"
        if macd_diff < -30:  # ضعيف جداً
            return 0, "MACD too negative"
        
        # حساب النقاط (مع حدود قصوى)
        confidence = 0
        details = []
        
        # 1. RSI (0-30 نقطة)
        if rsi < 25:
            rsi_points = 30
            details.append("RSI<25:+30")
        elif rsi < 30:
            rsi_points = 25
            details.append("RSI<30:+25")
        elif rsi < 35:
            rsi_points = 20
            details.append("RSI<35:+20")
        elif rsi < 40:
            rsi_points = 15
            details.append("RSI<40:+15")
        elif rsi < 45:
            rsi_points = 10
            details.append("RSI<45:+10")
        else:
            rsi_points = 5
            details.append("RSI:+5")
        confidence += rsi_points
        
        # 2. Volume (0-25 نقطة)
        volume_points = min(int((volume_ratio - 0.6) * 20), 25)
        confidence += volume_points
        details.append(f"Vol:{volume_points}")
        
        # 3. Trend (0-20 نقطة)
        if trend == 'bullish':
            trend_points = 20
            details.append("Trend:+20")
        elif trend == 'neutral':
            trend_points = 10
            details.append("Trend:+10")
        else:
            trend_points = 0
        confidence += trend_points
        
        # 4. MACD (0-15 نقطة)
        if macd_diff > 5:
            macd_points = 15
            details.append("MACD:+15")
        elif macd_diff > 0:
            macd_points = 10
            details.append("MACD:+10")
        else:
            macd_points = 5
            details.append("MACD:+5")
        confidence += macd_points
        
        # 5. Momentum (0-15 نقطة)
        if momentum < -5:
            momentum_points = 15
            details.append("Mom:+15")
        elif momentum < -3:
            momentum_points = 12
            details.append("Mom:+12")
        elif momentum < -2:
            momentum_points = 8
            details.append("Mom:+8")
        else:
            momentum_points = 0
        confidence += momentum_points
        
        # 6. Price Drop (0-15 نقطة)
        if drop_percent >= 3:
            drop_points = 15
            details.append("Drop:+15")
        elif drop_percent >= 2:
            drop_points = 10
            details.append("Drop:+10")
        elif drop_percent >= 1:
            drop_points = 5
            details.append("Drop:+5")
        else:
            drop_points = 0
        confidence += drop_points
        
        # المجموع: 0-120 نقطة
        details_str = " | ".join(details)
        return confidence, details_str
        
    except Exception as e:
        return 0, f"Error: {e}"

def calculate_volatility(symbol):
    """حساب التقلبات (ATR) للتعديل التلقائي"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=24)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
        atr_percent = (atr.iloc[-1] / df['close'].iloc[-1]) * 100
        
        if atr_percent < 1:
            return 'low'  # سوق هادئ
        elif atr_percent < 2:
            return 'medium'  # سوق عادي
        else:
            return 'high'  # سوق متقلب
    except:
        return 'medium'

def get_adaptive_settings(symbol, volatility, profit_percent=0):
    """تعديل الإعدادات حسب التقلبات والربح (Fast & Bold Mode)"""
    # Trailing Stop سريع 0.8%
    trailing_stop = 0.8
    
    # تعديل حسب التقلبات (سريع وذكي)
    if volatility == 'low':
        return {
            'stop_loss': 0.8,
            'tp_levels': [1]  # TP سريع 1%
        }
    elif volatility == 'high':
        return {
            'stop_loss': 0.8,
            'tp_levels': [1.5]  # TP 1.5% للسوق المتقلب
        }
    else:  # medium
        return {
            'stop_loss': 0.8,
            'tp_levels': [1]  # TP 1% عادي
        }

def get_multi_timeframe_analysis(symbol):
    """تحليل متعدد الأطر الزمنية (Multi-Timeframe)"""
    try:
        scores = {'5m': 0, '15m': 0, '1h': 0}
        
        # تحليل 5 دقائق
        ohlcv_5m = exchange.fetch_ohlcv(symbol, '5m', limit=100)
        df_5m = pd.DataFrame(ohlcv_5m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_5m['rsi'] = ta.momentum.RSIIndicator(df_5m['close'], window=14).rsi()
        macd_5m = ta.trend.MACD(df_5m['close'])
        
        if df_5m['rsi'].iloc[-1] < 35:
            scores['5m'] += 2
        elif df_5m['rsi'].iloc[-1] < 45:
            scores['5m'] += 1
        if macd_5m.macd_diff().iloc[-1] > 0:
            scores['5m'] += 1
        
        # تحليل 15 دقيقة
        ohlcv_15m = exchange.fetch_ohlcv(symbol, '15m', limit=50)
        df_15m = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_15m['ma20'] = df_15m['close'].rolling(window=20).mean()
        df_15m['ma50'] = df_15m['close'].rolling(window=50).mean()
        
        if df_15m['close'].iloc[-1] > df_15m['ma20'].iloc[-1]:
            scores['15m'] += 1
        if df_15m['ma20'].iloc[-1] > df_15m['ma50'].iloc[-1]:
            scores['15m'] += 2
        
        # تحليل 1 ساعة
        ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1h['rsi'] = ta.momentum.RSIIndicator(df_1h['close'], window=14).rsi()
        df_1h['trend'] = df_1h['close'].rolling(window=10).mean()
        
        if df_1h['close'].iloc[-1] > df_1h['trend'].iloc[-1]:
            scores['1h'] += 2
        if df_1h['rsi'].iloc[-1] < 50:
            scores['1h'] += 1
        
        total_score = sum(scores.values())
        trend = 'bullish' if total_score >= 5 else 'bearish' if total_score <= 2 else 'neutral'
        
        return {
            'scores': scores,
            'total': total_score,
            'trend': trend
        }
    except:
        return {'scores': {}, 'total': 0, 'trend': 'neutral'}

def should_sell_at_loss_simple(position, current_price, symbol, profit_percent, analysis=None):
    """قرار البيع بخسارة - مبسط وسريع مع تحليل بسيط + Volume"""
    # لو الربح إيجابي، ما نبيع بخسارة
    if profit_percent >= 0:
        return False
    
    # لو الخسارة أقل من الحد الأقصى، ننتظر
    if abs(profit_percent) < MAX_LOSS_PERCENT:
        return False
    
    # فحص Volume - لو عالي جداً = خطر!
    if analysis and analysis.get('volume_ratio'):
        volume_ratio = analysis['volume_ratio']
        if volume_ratio > 2.0:
            # Volume عالي جداً = panic selling = يبيع فوراً!
            print(f"{Fore.RED}⚠️ {symbol} | Loss:{profit_percent:.2f}% | High Volume:{volume_ratio:.1f}x (Panic!) - SELLING{Style.RESET_ALL}")
            return True
    
    # فحص بسيط للسوق (بدون Multi-Timeframe البطيء)
    if analysis:
        # لو RSI منخفض جداً (فرصة ارتداد)، ننتظر
        if analysis.get('rsi') and analysis['rsi'] < 30:
            print(f"{Fore.CYAN}🔄 {symbol} | Loss:{profit_percent:.2f}% but RSI:{analysis['rsi']:.1f} (oversold) - HOLDING{Style.RESET_ALL}")
            return False
        # لو MACD إيجابي (اتجاه صاعد)، ننتظر
        if analysis.get('macd_diff') and analysis['macd_diff'] > 0:
            print(f"{Fore.CYAN}🔄 {symbol} | Loss:{profit_percent:.2f}% but MACD positive - HOLDING{Style.RESET_ALL}")
            return False
    
    # فحص المدة (لو مر 48 ساعة، نبيع إجبارياً)
    if 'buy_time' in position:
        buy_time = datetime.fromisoformat(position['buy_time'])
        hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        
        if hours_held < RECOVERY_TIMEOUT_HOURS:
            print(f"{Fore.YELLOW}⏳ {symbol} | Loss:{profit_percent:.2f}% | Waiting {RECOVERY_TIMEOUT_HOURS - hours_held:.1f}h for recovery{Style.RESET_ALL}")
            return False  # ننتظر
    
    # بعد 48 ساعة، نبيع
    print(f"{Fore.RED}⚠️ {symbol} | Loss:{profit_percent:.2f}% | Timeout reached - SELLING{Style.RESET_ALL}")
    return True

def get_market_analysis(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=RSI_PERIOD).rsi()
        macd = ta.trend.MACD(df['close'], window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
        df['macd_diff'] = macd.macd_diff()
        df['price_change'] = df['close'].pct_change(10) * 100
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        return {
            'rsi': df['rsi'].iloc[-1],
            'macd_diff': df['macd_diff'].iloc[-1],
            'price_momentum': df['price_change'].iloc[-1],
            'volume_ratio': df['volume_ratio'].iloc[-1],
            'price': df['close'].iloc[-1]
        }
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return None

def get_boost_amount(confidence, symbol):
    """حساب المبلغ حسب قوة الإشارة (Confidence-Based Boost)"""
    if not BOOST_ENABLED:
        return TRADE_AMOUNT
    
    # تحديد المبلغ حسب Confidence
    if confidence >= 110:
        amount = 20
    elif confidence >= 100:
        amount = 18
    elif confidence >= 90:
        amount = 16
    elif confidence >= 80:
        amount = 14
    elif confidence >= 70:
        amount = 12
    else:  # 60-69
        amount = 10
    
    # لو العملة تحتاج $10 كحد أدنى
    if symbol in HIGH_NOTIONAL_COINS and amount < 10:
        return 10
    
    return amount

def check_volume_smart(confidence, volume_ratio):
    """فلتر Volume الذكي - يتكيف مع Confidence"""
    if confidence < 70:
        # Confidence ضعيف → يحتاج Volume قوي
        return volume_ratio >= 1.2
    else:
        # Confidence قوي → مرن أكثر
        return volume_ratio >= 0.8

def adjust_confidence_for_oversold(confidence, rsi, macd_diff):
    """حماية من فخ Oversold الشديد"""
    if rsi < 25 and macd_diff < 10:
        # RSI منخفض جداً + MACD ضعيف = خطر!
        return confidence * 0.7  # نخفض الثقة بـ30%
    return confidence

def buy_order(symbol, trade_amount=None, retry_count=0):
    global HIGH_NOTIONAL_COINS
    try:
        # استخدام المبلغ المحدد أو الافتراضي
        amount_usd = trade_amount if trade_amount else TRADE_AMOUNT
        
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        amount = amount_usd / price
        order = exchange.create_market_buy_order(symbol, amount)
        print(f"✅ BUY {symbol}: {amount:.6f} at ${price:.2f} (${amount_usd})")
        send_discord(f"🟢 **BUY** {symbol}\n💰 Amount: ${amount_usd}\n📊 Price: ${price:.2f}", 'green')
        return {'amount': amount, 'price': price, 'invested': amount_usd}
    except Exception as e:
        error_msg = str(e)
        # لو فشل بسبب NOTIONAL
        if 'NOTIONAL' in error_msg and retry_count < 4:
            if symbol not in HIGH_NOTIONAL_COINS:
                print(f"🧠 Learning: {symbol} needs higher minimum")
                HIGH_NOTIONAL_COINS.append(symbol)
            
            # يحاول بمبالغ أعلى: 5 → 10 → 15 → 20
            retry_amounts = [5, 10, 15, 20]
            next_amount = retry_amounts[retry_count]
            
            if trade_amount and trade_amount < next_amount:
                print(f"🔄 Retry {retry_count + 1}/4: {symbol} with ${next_amount}...")
                return buy_order(symbol, next_amount, retry_count + 1)
        
        print(f"❌ Buy failed {symbol}: {e}")
        return None

def sell_order(symbol, amount):
    try:
        # حساب قيمة البيع
        ticker = exchange.fetch_ticker(symbol)
        sell_value = amount * ticker['last']
        
        # فحص الحد الأدنى ($10) مع هامش أمان
        if sell_value < 9.99:
            print(f"⚠️ {symbol} sell value ${sell_value:.4f} < $10 minimum - Waiting for higher price")
            return None
        
        order = exchange.create_market_sell_order(symbol, amount)
        print(f"✅ SELL {symbol}: {amount:.6f} at ${order['price']:.2f} (${sell_value:.2f})")
        send_discord(f"🔴 **SELL** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${order['price']:.2f}", 'red')
        return order
    except Exception as e:
        print(f"❌ Sell failed {symbol}: {e}")
        return None

# ========== INITIALIZE AI BRAIN ==========
ai_brain = None
if AI_ENABLED:
    try:
        ai_brain = AIBrain(AI_BOUNDARIES)
    except Exception as e:
        print(f"⚠️ AI Brain initialization failed: {e}")
        ai_brain = None

load_positions()
print(f"\n🤖 Bot started! Smart & Bold Mode ⚡")
if ai_brain:
    print(f"🧠 AI Brain: ACTIVE (Learning Mode)")
else:
    print(f"⚙️ AI Brain: DISABLED (Manual Mode)")
print(f"💰 Boost: $10-20 (Confidence 60-110+)")
print(f"🎯 TP: 1% (Fast!) | SL: -0.8% (Smart Exit!)")
print(f"🎯 Min Confidence: {MIN_CONFIDENCE}/120 (Aggressive + Smart!)")
print(f"🛡️ Anti-Trap: Smart Volume + Oversold Protection")
print(f"🎯 Target: {MAX_COINS} coins (${TARGET_CAPITAL} = 450 SAR)")
print(f"📱 Discord: Connected ✅")
print(f"📊 Reports: Every 30 minutes\n")
send_discord("🤖 **MSA Trading Bot Started!**\n⚡ Smart & Bold Mode\n🛡️ Anti-Trap Protection\n📊 Confidence-Based Boost\n📊 Reports every 30min", 'blue')

# متغير لتتبع آخر تقرير
last_report_time = datetime.now()

# ========== MAIN LOOP ==========
try:
    while True:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}\n⏰ {current_time}\n{'='*60}")
        
        # ترتيب العملات حسب الأولوية
        sorted_symbols = sorted(SYMBOLS.items(), key=lambda x: x[1]['priority'])
        
        # حساب عدد العملات المسموح بها
        max_coins = get_max_coins_to_trade()
        active_positions = sum(1 for s in SYMBOLS.values() if s['position'])
        available_balance = get_available_balance()
        total_invested = get_total_invested()
        
        # عرض الرصيد بشكل بارز
        balance_line = f"💼 Balance: ${available_balance:.2f} | Invested: ${total_invested:.2f} | Active: {active_positions}/{max_coins}"
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'█' * 60}")
        print(f"  {balance_line}")
        print(f"{'█' * 60}{Style.RESET_ALL}\n")
        
        # معالجة جميع العملات (بدون Threading - أضمن)
        coin_count = 0
        for symbol, config in sorted_symbols:
            coin_count += 1
            position = config['position']
            
            # Debug: طباعة كل عملة
            # print(f"🔍 [{coin_count}/20] Processing {symbol}... (Position: {'Yes' if position else 'No'})")
            
            # تحليل العملة
            analysis = get_market_analysis(symbol)
            
            # لو في مركز مفتوح، نعرضه حتى لو فشل التحليل
            if position:
                if analysis:
                    # عندنا تحليل كامل
                    current_price = analysis['price']
                    
                    # الحماية الهجينة للبيع (نزول من القمة + bearish)
                    mtf = get_multi_timeframe_analysis(symbol)
                    profit_drop = check_profit_drop_from_peak(position, current_price)
                    if profit_drop['should_sell'] and mtf['trend'] == 'bearish':
                        buy_price = position['buy_price']
                        profit_percent = ((current_price - buy_price) / buy_price) * 100
                        
                        # فحص قيمة البيع قبل المحاولة
                        sell_value = position['amount'] * current_price
                        if sell_value < 9.99:  # هامش أمان للمنصة
                            print(f"{Fore.YELLOW}⏳ {symbol} | Hybrid sell signal but value ${sell_value:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}⚡ HYBRID SELL {symbol} | Profit:{profit_percent:.2f}% | Drop:{profit_drop['drop_from_peak']:.2f}% from peak + bearish{Style.RESET_ALL}")
                            result = sell_order(symbol, position['amount'])
                            if result:
                                # إرسال Discord مع التفاصيل
                                send_discord(f"⚡ **HYBRID SELL** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${current_price:.2f}\n📈 Profit: {profit_percent:+.2f}%\n📉 Drop: {profit_drop['drop_from_peak']:.2f}% from peak\n⚠️ Reason: Hybrid (Drop + Bearish)", 'yellow')
                                log_trade('SELL', symbol, position['amount'], current_price, profit_percent, position['highest_price'], 'Hybrid: Drop from peak + Bearish')
                                config['position'] = None
                                active_positions -= 1
                                save_positions()
                        continue
                    
                    # بيع فوراً لو Trend = bearish
                    if mtf['trend'] == 'bearish':
                        buy_price = position['buy_price']
                        profit_percent = ((current_price - buy_price) / buy_price) * 100
                        
                        # فحص قيمة البيع قبل المحاولة
                        sell_value = position['amount'] * current_price
                        if sell_value < 9.99:  # هامش أمان للمنصة
                            print(f"{Fore.YELLOW}⏳ {symbol} | Bearish trend but value ${sell_value:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}🔴 BEARISH TREND {symbol} | Profit:{profit_percent:.2f}% - SELLING NOW{Style.RESET_ALL}")
                            result = sell_order(symbol, position['amount'])
                            if result:
                                # إرسال Discord مع التفاصيل
                                send_discord(f"🔴 **BEARISH TREND** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${current_price:.2f}\n📈 Profit: {profit_percent:+.2f}%\n⚠️ Reason: Bearish Trend", 'red')
                                log_trade('SELL', symbol, position['amount'], current_price, profit_percent, position['highest_price'], 'Bearish Trend')
                                config['position'] = None
                                active_positions -= 1
                                save_positions()
                        continue
                else:
                    # ما في تحليل، نجيب السعر مباشرة
                    try:
                        ticker = exchange.fetch_ticker(symbol)
                        current_price = ticker['last']
                    except:
                        print(f"⚠️ {symbol}: Failed to get price (has position)")
                        continue
                
                # print(f"✅ {symbol}: Displaying position")
                
                try:
                    # print(f"🔍 {symbol}: Getting position data...")
                    buy_price = position['buy_price']
                    amount = position['amount']
                    highest_price = position['highest_price']
                    profit_percent = ((current_price - buy_price) / buy_price) * 100
                    # print(f"🔍 {symbol}: Calculated profit: {profit_percent:.2f}%")
                    
                    # تحديث أعلى سعر
                    if current_price > highest_price:
                        highest_price = current_price
                        position['highest_price'] = highest_price
                        save_positions()
                    
                    # print(f"🔍 {symbol}: Calculating volatility...")
                    # Auto-Adjust (مع حماية من الأخطاء)
                    try:
                        volatility = calculate_volatility(symbol)
                        adaptive = get_adaptive_settings(symbol, volatility, profit_percent)
                        stop_loss_percent = adaptive['stop_loss']
                        tp_levels = adaptive['tp_levels']
                        trailing_stop = highest_price * (1 - stop_loss_percent / 100)
                    except Exception as e:
                        print(f"⚠️ {symbol}: Volatility calc failed ({e}), using defaults")
                        volatility = 'medium'
                        stop_loss_percent = 0.8
                        tp_levels = [1.5]
                        trailing_stop = highest_price * (1 - stop_loss_percent / 100)
                    
                    # print(f"🔍 {symbol}: Checking TP/SL conditions...")
                    # Take Profit
                    if profit_percent >= tp_levels[0]:
                        # فحص قيمة البيع قبل المحاولة
                        sell_value = amount * current_price
                        if sell_value < 9.99:  # هامش أمان للمنصة
                            print(f"{Fore.YELLOW}⏳ {symbol} | TP reached but value ${sell_value:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                            tp_status = "100%"
                            vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                            print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                        else:
                            print(f"{Fore.GREEN}⚡ FAST TP {symbol} | Profit: {profit_percent:.2f}% | Target: {tp_levels[0]}%{Style.RESET_ALL}")
                            result = sell_order(symbol, amount)
                            if result:
                                # إرسال Discord مع التفاصيل
                                send_discord(f"⚡ **FAST TP** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${current_price:.2f}\n📈 Profit: {profit_percent:+.2f}%\n🎯 Target: {tp_levels[0]}%", 'green')
                                log_trade('SELL', symbol, amount, current_price, profit_percent, highest_price, f'Fast Take Profit {tp_levels[0]}%')
                                
                                # AI Learning من الصفقة
                                if ai_brain and 'ai_data' in position:
                                    trade_result = {
                                        'symbol': symbol,
                                        'action': 'SELL',
                                        'profit_percent': profit_percent,
                                        'reason': 'Fast TP',
                                        **position['ai_data']
                                    }
                                    ai_brain.learn_from_trade(trade_result)
                                
                                config['position'] = None
                                config['losses'] = 0
                                active_positions -= 1
                                save_positions()
                    # Stop Loss
                    elif current_price <= trailing_stop:
                        # فحص ذكي قبل البيع بربح
                        if profit_percent > 0 and analysis:
                            # لو السوق لسه قوي - ما تبيع!
                            if analysis.get('rsi') and analysis['rsi'] > 50 and analysis.get('macd_diff') and analysis['macd_diff'] > 0:
                                print(f"{Fore.CYAN}⚡ {symbol} | Profit:{profit_percent:.2f}% | Market strong (RSI:{analysis['rsi']:.1f}, MACD+) - HOLDING{Style.RESET_ALL}")
                                tp_status = "100%"
                                vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                                print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                            else:
                                # السوق ضعيف - بيع فوراً
                                sell_value = amount * current_price
                                if sell_value < 9.99:  # هامش أمان للمنصة
                                    print(f"{Fore.YELLOW}⏳ {symbol} | Stop loss but value ${sell_value:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                                    tp_status = "100%"
                                    vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                                    print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                                else:
                                    print(f"{Fore.RED}🛑 STOP {symbol} | Profit: {profit_percent:.2f}%{Style.RESET_ALL}")
                                    result = sell_order(symbol, amount)
                                    if result:
                                        # إرسال Discord مع التفاصيل
                                        send_discord(f"🛑 **STOP LOSS** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${current_price:.2f}\n📈 Profit: {profit_percent:+.2f}%\n⚠️ Reason: Stop Loss (Weak Market)", 'red')
                                        log_trade('SELL', symbol, amount, current_price, profit_percent, highest_price, 'Stop Loss')
                                        config['position'] = None
                                        active_positions -= 1
                                        save_positions()
                        elif profit_percent < 0 and WAIT_FOR_RECOVERY:
                            # فحص ذكي مبسط - بدون Multi-Timeframe
                            if not should_sell_at_loss_simple(position, current_price, symbol, profit_percent, analysis):
                                # ننتظر الانتعاش - نعرض عادي
                                tp_status = "100%"
                                vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                                print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                            else:
                                print(f"{Fore.RED}🛑 FORCED SELL {symbol} | Loss: {profit_percent:.2f}%{Style.RESET_ALL}")
                                sell_value = amount * current_price
                                if sell_value < 9.99:  # هامش أمان للمنصة
                                    print(f"{Fore.YELLOW}⏳ {symbol} | Forced sell but value ${sell_value:.4f} < $10 minimum - Keeping position{Style.RESET_ALL}")
                                    tp_status = "100%"
                                    vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                                    print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                                else:
                                    result = sell_order(symbol, amount)
                                    if result:
                                        # إرسال Discord مع التفاصيل
                                        send_discord(f"🛑 **FORCED SELL** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${current_price:.2f}\n📉 Loss: {profit_percent:.2f}%\n⚠️ Reason: Forced Stop Loss (Timeout)", 'red')
                                        log_trade('SELL', symbol, amount, current_price, profit_percent, highest_price, 'Forced Stop Loss')
                                        config['position'] = None
                                        active_positions -= 1
                                        config['losses'] += 1
                                        if config['losses'] >= BLACKLIST_LOSSES:
                                            blacklist_until = (datetime.now() + pd.Timedelta(days=BLACKLIST_DAYS)).isoformat()
                                            config['blacklisted_until'] = blacklist_until
                                            print(f"{Fore.RED}🚫 {symbol} BLACKLISTED for {BLACKLIST_DAYS} days{Style.RESET_ALL}")
                                        save_positions()
                        else:
                            print(f"{Fore.RED}🛑 STOP {symbol} | Profit: {profit_percent:.2f}%{Style.RESET_ALL}")
                            sell_value = amount * current_price
                            if sell_value < 9.99:  # هامش أمان للمنصة
                                print(f"{Fore.YELLOW}⏳ {symbol} | Stop loss but value ${sell_value:.4f} < $10 minimum - Waiting{Style.RESET_ALL}")
                                tp_status = "100%"
                                vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                                print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                            else:
                                result = sell_order(symbol, amount)
                                if result:
                                    # إرسال Discord مع التفاصيل
                                    send_discord(f"🛑 **STOP LOSS** {symbol}\n💵 Value: ${sell_value:.2f}\n📊 Price: ${current_price:.2f}\n📈 Profit: {profit_percent:+.2f}%\n⚠️ Reason: Stop Loss", 'red')
                                    log_trade('SELL', symbol, amount, current_price, profit_percent, highest_price, 'Stop Loss')
                                    config['position'] = None
                                    active_positions -= 1
                                    if profit_percent < 0:
                                        config['losses'] += 1
                                    save_positions()
                    else:
                        tp_status = "100%"
                        vol_emoji = "🔥" if volatility == 'high' else "❄️" if volatility == 'low' else "📊"
                        print(f"💎 {symbol:12} ${current_price:>8.2f} | Profit:{profit_percent:>+6.2f}% | {vol_emoji} | Hold:{tp_status}")
                except Exception as e:
                    print(f"❌ {symbol}: Error displaying position - {e}")
            
            # لو ما في مركز، نعرض التحليل
            elif analysis:  # لو في تحليل كامل
                current_price = analysis['price']
                rsi = analysis['rsi']
                macd_diff = analysis['macd_diff']
                momentum = analysis['price_momentum']
                volume_ratio = analysis['volume_ratio']
                
                if not position:
                    # فحص إذا وصلنا للحد الأقصى
                    if active_positions >= max_coins:
                        continue
                    
                    # فحص الرصيد المتاح
                    if available_balance < TRADE_AMOUNT:
                        continue
                    
                    # فحص Blacklist
                    if is_blacklisted(symbol):
                        print(f"🚫 {symbol}: BLACKLISTED")
                        continue
                    
                    # فحص انهيار السوق
                    if check_market_crash():
                        print(f"{Fore.RED}⚠️ MARKET CRASH DETECTED - Pausing new buys{Style.RESET_ALL}")
                        continue
                    
                    # النظام الديناميكي للشراء
                    buy_score = 0
                    if rsi < 30: buy_score += 3
                    elif rsi < 40: buy_score += 2
                    elif rsi < 45: buy_score += 1
                    if macd_diff > 0: buy_score += 2
                    if momentum < -3: buy_score += 2
                    elif momentum < -2: buy_score += 1
                    if volume_ratio > 1.5: buy_score += 1
                    
                    # Volume Confirmation - تأكيد الحجم (قوي - 0.8)
                    volume_confirmed = volume_ratio > 0.8
                    
                    # فحص الاتجاه والنزول
                    mtf = get_multi_timeframe_analysis(symbol)
                    price_drop = check_price_drop_from_peak(symbol)
                    
                    # ========== AI BRAIN DECISION ==========
                    if ai_brain:
                        # استخدام AI Brain للقرار
                        ai_decision = ai_brain.should_buy(symbol, analysis, mtf, price_drop)
                        
                        if ai_decision['action'] == 'BUY':
                            confidence = ai_decision['confidence']
                            boost_amount = ai_decision['amount']
                            boost_emoji = "🧠🚀" if boost_amount > TRADE_AMOUNT else "🧠"
                            
                            # فحص الرصيد المتاح
                            if available_balance < boost_amount:
                                boost_amount = TRADE_AMOUNT
                            
                            print(f"{Fore.YELLOW}🟢 BUY {symbol} {boost_emoji} | AI Confidence:{confidence}/120 | {ai_decision['reason']} | Amount:${boost_amount}{Style.RESET_ALL}")
                            result = buy_order(symbol, boost_amount)
                        else:
                            # AI قرر SKIP
                            vol_status = "🟢" if volume_ratio > 0.8 else "🔴"
                            print(f"📊 {symbol:12} ${current_price:>8.2f} | AI: {ai_decision['reason']} | Vol:{vol_status}")
                            continue
                    else:
                        # النظام اليدوي (بدون AI)
                        confidence, details = calculate_dynamic_confidence(symbol, analysis, mtf, price_drop)
                        confidence = adjust_confidence_for_oversold(confidence, rsi, macd_diff)
                        
                        if not check_volume_smart(confidence, volume_ratio):
                            vol_status = "🟢" if volume_ratio > 0.8 else "🔴"
                            print(f"📊 {symbol:12} ${current_price:>8.2f} | Confidence:{confidence:.0f}/120 | Vol:{volume_ratio:.1f} < required - SKIP | Vol:{vol_status}")
                            continue
                        
                        if confidence >= MIN_CONFIDENCE:
                            boost_amount = get_boost_amount(confidence, symbol)
                            boost_emoji = "🚀" if boost_amount > TRADE_AMOUNT else ""
                            
                            if available_balance < boost_amount:
                                boost_amount = TRADE_AMOUNT
                            
                            print(f"{Fore.YELLOW}🟢 BUY {symbol} {boost_emoji} | Confidence:{confidence}/120 | {details} | Amount:${boost_amount}{Style.RESET_ALL}")
                            result = buy_order(symbol, boost_amount)
                        else:
                            vol_status = "🟢" if volume_confirmed else "🔴"
                            if confidence > 0:
                                print(f"📊 {symbol:12} ${current_price:>8.2f} | Confidence:{confidence}/120 ({details}) | Vol:{vol_status}")
                            else:
                                print(f"📊 {symbol:12} ${current_price:>8.2f} | RSI:{rsi:>5.1f} | Score:{buy_score}/9 | Vol:{vol_status}")
                            continue
                    
                    # إذا تم الشراء (سواء AI أو Manual)
                    if 'result' in locals() and result:
                        if result:
                            config['position'] = {
                                'buy_price': result['price'],
                                'amount': result['amount'],
                                'highest_price': result['price'],
                                'tp_level_1': False,
                                'tp_level_2': False,
                                'buy_time': datetime.now().isoformat(),
                                'invested': result['invested']  # المبلغ المستثمر
                            }
                            active_positions += 1
                            available_balance -= result['invested']
                            save_positions()
                            log_trade('BUY', symbol, result['amount'], result['price'], highest_price=result['price'])
                            
                            # حفظ بيانات الشراء للتعلم
                            if ai_brain:
                                config['position']['ai_data'] = {
                                    'confidence': confidence,
                                    'rsi': rsi,
                                    'volume_ratio': volume_ratio,
                                    'macd_diff': macd_diff,
                                    'momentum': momentum,
                                    'trend': mtf['trend']
                                }
                    else:
                        # عرض التحليل للكل (حتى لو confidence = 0)
                        vol_status = "🟢" if volume_confirmed else "🔴"
                        if confidence > 0:
                            print(f"📊 {symbol:12} ${current_price:>8.2f} | Confidence:{confidence}/120 ({details}) | Vol:{vol_status}")
                        else:
                            print(f"📊 {symbol:12} ${current_price:>8.2f} | RSI:{rsi:>5.1f} | Score:{buy_score}/9 | Vol:{vol_status}")
            else:
                print(f"⚠️ {symbol}: Analysis failed")
        
        # print(f"\n✅ Total coins processed: {coin_count}/20\n")
        
        # إرسال تقرير كل 30 دقيقة
        minutes_since_report = (datetime.now() - last_report_time).total_seconds() / 60
        if minutes_since_report >= 30:
            send_positions_report()
            last_report_time = datetime.now()
        
        # تنظيف الذاكرة
        gc.collect()
        
        time.sleep(10)  # فحص كل 10 ثواني (متوازن)

except KeyboardInterrupt:
    print("\n\n🛑 Bot stopped")
except Exception as e:
    print(f"\n❌ Error: {e}")
