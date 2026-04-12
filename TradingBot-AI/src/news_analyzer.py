"""
📰 News Analyzer Module
Handles news sentiment analysis from database
"""

import os
from datetime import datetime
from functools import lru_cache
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

# ================================================================
# ✅ دمج sentiment_fix.py - بيانات sentiment حقيقية من API
# ================================================================

# [تحسين الذاكرة] كاش لـ Fear & Greed Index
_fear_greed_cache = {'value': None, 'timestamp': 0}

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
        'sentiment_score': 0.0,
        'panic_score': 0.0,
        'optimism_penalty': 0.0
    }

    # ========== 1. Fear & Greed Index ==========
    try:
        now = time.time()
        # كاش لمدة 10 دقائق - يحفظ على الـ Egress
        if _fear_greed_cache['value'] is None or (now - _fear_greed_cache['timestamp']) > 600:
            response = requests.get(
                'https://api.alternative.me/fng/?limit=1',
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                fg_value = int(data['data'][0]['value'])  # 0-100
                # تحويل من 0-100 إلى -10 إلى +10
                sentiment_score = (fg_value - 50) / 5.0  # -10 إلى +10
                _fear_greed_cache['value'] = round(sentiment_score, 2)
                _fear_greed_cache['timestamp'] = now

        result['sentiment_score'] = _fear_greed_cache['value'] or 0.0

    except Exception as e:
        print(f"⚠️ Fear & Greed API error: {e}")
        result['sentiment_score'] = 0.0

    # ========== 2. Panic Score من التحليل التقني ==========
    if analysis:
        try:
            # Calculate panic score directly from real data
            rsi_val = float(analysis.get('rsi', 50))
            btc_change = float(analysis.get('btc_change_1h', 0))
            vol_ratio = float(analysis.get('volume_ratio', 1))
            
            panic_score = 0.0
            if rsi_val < 30: panic_score += 3
            if rsi_val > 75: panic_score += 2
            if btc_change < -2: panic_score += abs(btc_change) / 2
            if vol_ratio > 2.5: panic_score += 2
            if vol_ratio < 0.4: panic_score += 1
            
            result['panic_score'] = min(float(panic_score), 10.0)
        except Exception as e:
            result['panic_score'] = 0.0

    # ========== 3. Optimism Penalty ==========
    # يُحسب خارج هذه الدالة من profit_percent وقت البيع

    return result

# ================================================================
# دمج مكتمل - الان news_analyzer يدعم sentiment حقيقي
# ================================================================

# [تحسين الذاكرة] دالة مستقلة مع تخزين مؤقت آمن
@lru_cache(maxsize=32) # تخزين آخر 32 نتيجة فقط
def get_news_sentiment_cached(database_url, symbol, hours, ttl_hash=None):
    del ttl_hash # يستخدم فقط لتحديث الكاش
    try:
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password)
        )
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
        return {
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'total': total,
            'news_score': news_score,
            'latest_news': news[:3]
        }
    except Exception as e:
        # print(f"❌ News DB query error: {e}") # Debug
        return None

def get_ttl_hash(seconds=600):
    """[تحسين الذاكرة] إنشاء hash يعتمد على الوقت لتحديث الكاش كل 10 دقائق"""
    return round(time.time() / seconds)

class NewsAnalyzer:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.enabled = bool(self.database_url)
        if self.enabled:
            print("📰 News Analyzer: ACTIVE (with LRU Cache)")
        else:
            print("News Analyzer: DISABLED (No DATABASE_URL)")
    
    def get_news_sentiment(self, symbol, hours=24):
        if not self.enabled:
            return None
        # [تحسين الذاكرة] استدعاء الدالة المؤمنة بالذاكرة
        return get_news_sentiment_cached(
            self.database_url, 
            symbol, 
            hours, 
            ttl_hash=get_ttl_hash()
        )
    
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
            emoji = "🟢"
            status = "Bullish"
        elif score < -5:
            emoji = "📉"
            status = "Very Bearish"
        elif score < -2:
            emoji = "🔴"
            status = "Bearish"
        else:
            emoji = "⚪"
            status = "Neutral"
        return f"{emoji} {status}"

    # ================================================================
    # ✅ دالة جديدة: تحديث trades_history بـ sentiment حقيقي
    # ================================================================

    def update_trade_sentiment(self, trade_id, sentiment_data):
        """
        تحديث صفقة في trades_history بـ sentiment_score و panic_score الحقيقية
        يتم استدعاؤها من بوت التداول بعد انتهاء الصفقة
        """
        if not self.enabled:
            return False

        try:
            conn = psycopg2.connect(
                host=urlparse(self.database_url).hostname,
                port=urlparse(self.database_url).port,
                user=urlparse(self.database_url).username,
                password=unquote(urlparse(self.database_url).password),
                database=urlparse(self.database_url).path[1:]
            )
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE trades_history
                SET sentiment_score = %s,
                    panic_score = %s,
                    optimism_penalty = %s
                WHERE id = %s
            """, (
                sentiment_data['sentiment_score'],
                sentiment_data['panic_score'],
                sentiment_data.get('optimism_penalty', 0),
                trade_id
            ))

            conn.commit()
            cursor.close()
            conn.close()

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
        # sentiment من الاخبار
        news_sentiment = self.get_news_sentiment(symbol, hours)

        # sentiment من السوق (API حقيقي)
        market_sentiment = get_sentiment_data(symbol, analysis)

        return {
            'news_score': news_sentiment['news_score'] if news_sentiment else 0,
            'sentiment_score': market_sentiment['sentiment_score'],
            'panic_score': market_sentiment['panic_score'],
            'optimism_penalty': market_sentiment.get('optimism_penalty', 0),
            'news_total': news_sentiment['total'] if news_sentiment else 0
        }


# ================================================================
# ✅ اختبار sentiment_fix - تشغيل منفصل
# ================================================================

if __name__ == '__main__':
    print("Testing sentiment_fix integration...")

    # اختبار Fear & Greed API
    sentiment_data = get_sentiment_data()
    print(f"sentiment_score: {sentiment_data['sentiment_score']}")
    print(f"panic_score: {sentiment_data['panic_score']}")
    print(f"optimism_penalty: {sentiment_data['optimism_penalty']}")

    # ترجمة القيمة
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

    # اختبار news_analyzer
    analyzer = NewsAnalyzer()
    if analyzer.enabled:
        test_sentiment = analyzer.get_enhanced_sentiment("BTC/USDT")
        print(f"Enhanced sentiment for BTC: {test_sentiment}")
    else:
        print("News analyzer disabled - no DATABASE_URL")
