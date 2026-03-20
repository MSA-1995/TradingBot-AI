"""
📰 News Analyzer Module
Handles news sentiment analysis from database
"""

import os

from datetime import datetime
self.last_summary_time = None

# =========================
# Declare global here
_previous_bot_status = None

class NewsAnalyzer:
    def __init__(self):

        self.database_url = os.getenv("DATABASE_URL")
        self.enabled = bool(self.database_url)
        self.cache = {}
        self.cache_duration = 600  # 10 دقائق - تحسين السرعة
        
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
