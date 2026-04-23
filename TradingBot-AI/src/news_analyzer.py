"""
📰 News Analyzer Module
Handles news sentiment analysis from database
"""

import os
from datetime import datetime
from functools import lru_cache
import json
import time
import requests
import gc

# إضافة كاش مضغوط للأخبار
try:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    memory_path = os.path.join(parent_dir, 'memory')
    if os.path.exists(memory_path) and memory_path not in sys.path:
        sys.path.insert(0, memory_path)
    from memory_cache import MemoryCache
except Exception:
    MemoryCache = None

# ================================================================
# ✅ دمج sentiment_fix.py - بيانات sentiment حقيقية من API
# ================================================================

# [تحسين الذاكرة] كاش لـ Fear & Greed Index
_fear_greed_cache = {'value': None, 'timestamp': 0, 'previous_value': None}

# [تحسين الذاكرة] كاش مضغوط للأخبار
_news_cache = MemoryCache(max_items=20) if MemoryCache else {}

def get_sentiment_data(symbol=None, analysis=None):
    """
    يجيب sentiment_score و panic_score حقيقيين

    المصادر:
    1. Fear & Greed Index → sentiment_score (-10 إلى +10)
    2. detect_panic_greed → panic_score (من التحليل التقني)
    3. optimism_penalty → من نسبة الربح

    Returns: dict بالقيم الثلاث
    """
    result = {
        'sentiment_score':    0.0,
        'sentiment_velocity': 0.0,
        'panic_score':        0.0,
        'optimism_penalty':   0.0
    }

    # ========== 1. Fear & Greed Index ==========
    try:
        now = time.time()
        if _fear_greed_cache['value'] is None or (now - _fear_greed_cache['timestamp']) > 1800:
            response = requests.get(
                'https://api.alternative.me/fng/?limit=1',
                timeout=(5, 10)
            )
            if response.status_code == 200:
                data     = response.json()
                fg_value = int(data['data'][0]['value'])
                _fear_greed_cache['previous_value'] = _fear_greed_cache['value']
                sentiment_score = (fg_value - 50) / 5.0
                _fear_greed_cache['value']     = round(sentiment_score, 2)
                _fear_greed_cache['timestamp'] = now

        result['sentiment_score'] = _fear_greed_cache['value'] if _fear_greed_cache['value'] is not None else 0.0
        if _fear_greed_cache['previous_value'] is not None:
            result['sentiment_velocity'] = result['sentiment_score'] - _fear_greed_cache['previous_value']

    except Exception as e:
        if analysis:
            try:
                rsi = analysis.get('rsi', 50)
                result['sentiment_score'] = (rsi - 50) / 5.0
            except Exception:
                result['sentiment_score'] = 0.0
        else:
            result['sentiment_score'] = 0.0

    # ========== 2. Panic Score من التحليل التقني ==========
    if analysis:
        try:
            rsi_val    = float(analysis.get('rsi', 50))
            btc_change = float(analysis.get('btc_change_1h', 0))
            vol_ratio  = float(analysis.get('volume_ratio', 1))

            panic_score = 0.0
            if rsi_val < 30:    panic_score += 3
            if rsi_val > 75:    panic_score += 2
            if btc_change < -2: panic_score += abs(btc_change) / 2
            if vol_ratio > 2.5: panic_score += 2
            if vol_ratio < 0.4: panic_score += 1

            result['panic_score'] = min(float(panic_score), 10.0)
        except Exception:
            result['panic_score'] = 0.0

    # ========== 3. Optimism Penalty ==========
    # يُحسب خارج هذه الدالة من profit_percent وقت البيع

    return result

# ================================================================
# دمج مكتمل - الان news_analyzer يدعم sentiment حقيقي
# ================================================================
def get_ttl_hash(seconds=1800):
    """[تحسين الذاكرة] إنشاء hash يعتمد على الوقت لتحديث الكاش كل 30 دقيقة"""
    return round(time.time() / seconds)

class NewsAnalyzer:
    def __init__(self, storage=None):
        self.storage = storage
        self.enabled = True if storage else False

    def get_news_sentiment(self, symbol, hours=24):
        """Requirement 2: استخدام الكاش المضغوط من StorageManager فقط"""
        if not self.storage:
            return None
        
        news_data = self.storage.get_news_data(symbol)
        result    = news_data if news_data is not None else {}

        del news_data
        gc.collect()
        return result

    def get_news_confidence_boost(self, symbol, hours=24):
        sentiment = self.get_news_sentiment(symbol, hours)
        if not sentiment:
            return 0
        news_score = sentiment.get('news_score', 0)
        total_news = sentiment.get('total', 0)
        if total_news < 2:
            return 0
        confidence_boost = int(news_score * 1.5)
        confidence_boost = max(-15, min(15, confidence_boost))
        return confidence_boost

    def should_avoid_coin(self, symbol, hours=24):
        sentiment = self.get_news_sentiment(symbol, hours)
        if not sentiment:
            return False
        total    = sentiment.get('total', 0)
        negative = sentiment.get('negative', 0)
        positive = sentiment.get('positive', 0)
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
        total = sentiment.get('total', 0)
        pos   = sentiment.get('positive', 0)
        neg   = sentiment.get('negative', 0)
        score = sentiment.get('news_score', 0)
        if score > 5:
            emoji  = "📈"
            status = "Very Bullish"
        elif score > 2:
            emoji  = "🟢"
            status = "Bullish"
        elif score < -5:
            emoji  = "📉"
            status = "Very Bearish"
        elif score < -2:
            emoji  = "🔴"
            status = "Bearish"
        else:
            emoji  = "⚪"
            status = "Neutral"

        gc.collect()

        return f"{emoji} {status}"

    # ================================================================
    # ✅ دالة جديدة: تحديث trades_history بـ sentiment حقيقي
    # ================================================================

    def update_trade_sentiment(self, trade_id, sentiment_data):
        """
        تحديث صفقة في trades_history بـ sentiment_score و panic_score الحقيقية
        يتم استدعاؤها من بوت التداول بعد انتهاء الصفقة
        """
        if not self.storage:
            return False
        try:
            self.storage.update_trade_sentiment(trade_id, sentiment_data)
            print(f"✅ Updated trade {trade_id} with real sentiment")
            return True
        except Exception as e:
            print(f"⚠️ Failed to update trade sentiment: {e}")
            return False

    # ================================================================
    # ✅ دالة مساعدة: جلب sentiment شامل (اخبار + سوق)
    # ================================================================

    def get_enhanced_sentiment(self, symbol, analysis=None, hours=24):
        """
        دمج sentiment من الاخبار + sentiment من السوق (Fear & Greed)
        """
        news_sentiment   = self.get_news_sentiment(symbol, hours)
        market_sentiment = get_sentiment_data(symbol, analysis)

        return {
            'news_score':       news_sentiment.get('news_score', 0) if news_sentiment else 0,
            'sentiment_score':  market_sentiment['sentiment_score'],
            'panic_score':      market_sentiment['panic_score'],
            'optimism_penalty': market_sentiment.get('optimism_penalty', 0),
            'news_total':       news_sentiment.get('total', 0) if news_sentiment else 0
        }


# ================================================================
# ✅ اختبار sentiment_fix - تشغيل منفصل
# ================================================================

if __name__ == '__main__':
    print("Testing sentiment_fix integration...")

    sentiment_data = get_sentiment_data()
    print(f"sentiment_score: {sentiment_data['sentiment_score']}")
    print(f"panic_score: {sentiment_data['panic_score']}")
    print(f"optimism_penalty: {sentiment_data['optimism_penalty']}")

    score = sentiment_data['sentiment_score']
    if score > 5:
        mood = "Extreme Greed - Bullish market"
    elif score > 0:
        mood = "Greed - Bullish"
    elif score > -5:
        mood = "Fear - Bearish"
    else:
        mood = "Extreme Fear - Very Bearish"
    print(f"Market Mood: {mood}")

    analyzer = NewsAnalyzer()
    if analyzer.enabled:
        test_sentiment = analyzer.get_enhanced_sentiment("BTC/USDT")
        print(f"Enhanced sentiment for BTC: {test_sentiment}")
    else:
        print("News analyzer disabled - no DATABASE_URL")