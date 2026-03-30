"""
📰 News Analyzer Module
Handles news sentiment analysis from database
"""

import os
from datetime import datetime
from functools import lru_cache
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

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
            print("⚠️ News Analyzer: DISABLED (No DATABASE_URL)")
    
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
        return f"{emoji} {status}"
