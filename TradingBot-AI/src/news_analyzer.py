"""
📰 News Sentiment Analyzer
يقرأ الأخبار من Database ويحللها لاتخاذ قرارات التداول
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote

class NewsAnalyzer:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.enabled = bool(self.database_url)
        self.cache = {}  # Cache للأخبار
        self.cache_duration = 30  # 30 ثانية - تحديث سريع
        
        if self.enabled:
            print("📰 News Analyzer: ACTIVE")
        else:
            print("⚠️ News Analyzer: DISABLED (No DATABASE_URL)")
    
    def get_db_connection(self):
        """الاتصال بقاعدة البيانات"""
        if not self.enabled:
            return None
        
        try:
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
        """
        جلب أخبار العملة من آخر X ساعة (مع Cache)
        Returns: {'positive': 5, 'negative': 1, 'neutral': 3, 'score': 0.45}
        """
        if not self.enabled:
            return None
        
        # فحص Cache
        cache_key = f"{symbol}_{hours}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_duration:
                return cached_data
        
        try:
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
            
            # حساب الإحصائيات
            positive = sum(1 for n in news if n['sentiment'] == 'POSITIVE')
            negative = sum(1 for n in news if n['sentiment'] == 'NEGATIVE')
            neutral = sum(1 for n in news if n['sentiment'] == 'NEUTRAL')
            
            # حساب متوسط Score
            avg_score = sum(n['score'] for n in news) / len(news) if news else 0
            
            # حساب News Score (-10 to +10)
            total = len(news)
            if total == 0:
                news_score = 0
            else:
                # النسب المئوية
                pos_ratio = positive / total
                neg_ratio = negative / total
                
                # Score من -10 إلى +10
                news_score = (pos_ratio - neg_ratio) * 10
            
            result = {
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'total': total,
                'avg_score': avg_score,
                'news_score': news_score,  # -10 to +10
                'latest_news': news[:3]  # آخر 3 أخبار
            }
            
            # حفظ في Cache
            self.cache[cache_key] = (result, datetime.now())
            
            return result
            
        except Exception as e:
            print(f"⚠️ News sentiment error for {symbol}: {e}")
            return None
    
    def get_news_confidence_boost(self, symbol, hours=24):
        """
        حساب Confidence Boost بناءً على الأخبار
        Returns: -15 to +15
        """
        sentiment = self.get_news_sentiment(symbol, hours)
        
        if not sentiment:
            return 0
        
        news_score = sentiment['news_score']
        total_news = sentiment['total']
        
        # لو ما فيه أخبار كافية
        if total_news < 2:
            return 0
        
        # تحويل News Score (-10 to +10) إلى Confidence Boost (-15 to +15)
        confidence_boost = int(news_score * 1.5)
        
        # حد أقصى وأدنى
        confidence_boost = max(-15, min(15, confidence_boost))
        
        return confidence_boost
    
    def should_avoid_coin(self, symbol, hours=24):
        """
        هل يجب تجنب العملة بسبب الأخبار السلبية؟
        """
        sentiment = self.get_news_sentiment(symbol, hours)
        
        if not sentiment:
            return False
        
        # تجنب إذا:
        # 1. أكثر من 80% أخبار سلبية (Changed from 70%)
        # 2. فيه 3+ أخبار سلبية وما فيه إيجابية
        
        total = sentiment['total']
        negative = sentiment['negative']
        positive = sentiment['positive']
        
        if total >= 3:
            neg_ratio = negative / total
            if neg_ratio > 0.8:  # Changed from 0.7
                return True
            
            if negative >= 3 and positive == 0:
                return True
        
        return False
    
    def get_market_sentiment(self, symbols, hours=24):
        """
        حساب sentiment السوق العام
        """
        if not self.enabled:
            return None
        
        try:
            conn = self.get_db_connection()
            if not conn:
                return None
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # جلب كل الأخبار للعملات المحددة
            placeholders = ','.join(['%s'] * len(symbols))
            cursor.execute(f"""
                SELECT sentiment, score
                FROM news_sentiment
                WHERE symbol IN ({placeholders})
                AND timestamp > NOW() - INTERVAL '%s hours'
            """, (*symbols, hours))
            
            news = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if not news:
                return None
            
            positive = sum(1 for n in news if n['sentiment'] == 'POSITIVE')
            negative = sum(1 for n in news if n['sentiment'] == 'NEGATIVE')
            neutral = sum(1 for n in news if n['sentiment'] == 'NEUTRAL')
            total = len(news)
            
            # تحديد sentiment السوق
            pos_ratio = positive / total if total > 0 else 0
            neg_ratio = negative / total if total > 0 else 0
            
            if pos_ratio > 0.6:
                market_sentiment = "BULLISH"
            elif neg_ratio > 0.6:
                market_sentiment = "BEARISH"
            else:
                market_sentiment = "NEUTRAL"
            
            return {
                'sentiment': market_sentiment,
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'total': total,
                'pos_ratio': pos_ratio,
                'neg_ratio': neg_ratio
            }
            
        except Exception as e:
            print(f"⚠️ Market sentiment error: {e}")
            return None
    
    def get_news_summary(self, symbol, hours=24):
        """
        ملخص الأخبار للعرض
        """
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
