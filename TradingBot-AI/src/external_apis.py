"""
🌐 External APIs Manager - محرك جلب البيانات الخارجية
مسؤول عن جلب أخبار السيولة، تحركات الحيتان، ومشاعير السوق.
"""
import os
import requests
from datetime import datetime, timedelta

# إضافة كاش مضغوط لنتائج external APIs
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

class ExternalAPIClient:
    def __init__(self):
        self.news_key = os.getenv("NEWS_API_KEY")
        self.whale_key = os.getenv("WHALE_ALERT_API_KEY")
        self.alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.api_cache = MemoryCache(max_items=30) if MemoryCache else {}

    def get_whale_activity(self, min_value=500000):
        """جلب تحركات الحيتان الكبيرة في آخر ساعة"""
        if not self.whale_key:
            return []

        cache_key = f"whale_{min_value}"
        cached_result = self.api_cache.get(cache_key) if MemoryCache else None
        if cached_result:
            return cached_result

        url = f"https://api.whale-alert.io/v1/transactions?api_key={self.whale_key}&min_value={min_value}"
        for attempt in range(3):  # Retry up to 3 times with backoff
            try:
                response = requests.get(url, timeout=(5, 10))
                if response.status_code == 200:
                    result = response.json().get('transactions', [])
                    if MemoryCache:
                        self.api_cache.set(cache_key, result, expiry_seconds=300)  # 5 دقائق
                    return result
                return []
            except Exception as e:
                if attempt < 2:  # Don't sleep on last attempt
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
                else:
                    print(f"⚠️ Whale Alert Error after retries: {e}")
                    return []
        
        url = f"https://api.whale-alert.io/v1/transactions?api_key={self.whale_key}&min_value={min_value}"
        for attempt in range(3):  # Retry up to 3 times with backoff
            try:
                response = requests.get(url, timeout=(5, 10))  # connect=5s, read=10s
                if response.status_code == 200:
                    return response.json().get('transactions', [])
                return []
            except Exception as e:
                if attempt < 2:  # Don't sleep on last attempt
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
                else:
                    print(f"⚠️ Whale Alert Error after retries: {e}")
                    return []

    def get_crypto_news(self, query="bitcoin"):
        """جلب الأخبار العاجلة لعملة معينة لتحليل المشاعر"""
        if not self.news_key:
            return []
        
        # جلب أخبار آخر 24 ساعة فقط
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        url = f"https://newsapi.org/v2/everything?q={query}&from={yesterday}&sortBy=publishedAt&apiKey={self.news_key}"
        
        try:
            response = requests.get(url, timeout=(5, 10))  # connect=5s, read=10s
            if response.status_code == 200:
                articles = response.json().get('articles', [])
                # نأخذ العناوين فقط لتقليل استهلاك الرام
                return [a['title'] for a in articles[:5]]
            return []
        except Exception as e:
            print(f"⚠️ NewsAPI Error: {e}")
            return []

    def get_market_sentiment_global(self):
        """جلب مؤشر الخوف والطمع (Fear & Greed Index)"""
        url = "https://api.alternative.me/fng/"
        try:
            response = requests.get(url, timeout=(5, 10))  # connect=5s, read=10s
            if response.status_code == 200:
                data = response.json().get('data', [{}])[0]
                return {
                    'value': int(data.get('value', 50)),
                    'classification': data.get('value_classification', 'Neutral')
                }
            return {'value': 50, 'classification': 'Neutral'}
        except Exception as e:
            print(f"⚠️ Global sentiment error: {e}")
            return {'value': 50, 'classification': 'Neutral'}

    def get_global_price_check(self, symbol):
        """التحقق المتقاطع: جلب السعر من CoinGecko للمقارنة"""
        try:
            coin_id = symbol.split('/')[0].lower()
            # خريطة تحويل الأسماء لـ CoinGecko IDs
            mapping = {'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana', 'bnb': 'binancecoin', 'xrp': 'ripple'}
            cg_id = mapping.get(coin_id, coin_id)
            
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json().get(cg_id, {}).get('usd')
            return None
        except Exception as e:
            print(f"⚠️ Global price check error: {e}")
            return None

    def get_global_data(self):
        """جلب القيمة السوقية الإجمالية وسيطرة البيتكوين عبر CoinGecko"""
        url = "https://api.coingecko.com/api/v3/global"
        try:
            response = requests.get(url, timeout=(5, 10))  # connect=5s, read=10s
            if response.status_code == 200:
                data = response.json().get('data', {})
                return {
                    'market_cap_change': data.get('market_cap_change_percentage_24h_usd', 0),
                    'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)
                }
            return {}
        except Exception as e:
            print(f"⚠️ Global data error: {e}")
            return {}

    def analyze_impact(self, symbol):
        """تحليل شامل لتأثير البيانات الخارجية على عملة معينة"""
        news = self.get_crypto_news(symbol)
        fng = self.get_market_sentiment_global()
        global_data = self.get_global_data()
        global_price = self.get_global_price_check(symbol)

        # حساب درجة التأثير (Score) من 0 لـ 100
        impact_score = 50 # نقطة التعادل
        
        if fng['value'] > 70: impact_score += 10 # طمع عالي (إيجابي لكن حذر)
        if fng['value'] < 30: impact_score -= 15 # خوف شديد
        
        if global_data.get('market_cap_change', 0) > 0: impact_score += 5
        
        return {
            'score': impact_score,
            'sentiment': fng['classification'],
            'headlines': news,
            'global_price': global_price,
            'btc_dominance': global_data.get('btc_dominance', 0),
            'timestamp': datetime.now().isoformat()
        }

    def get_external_atr(self, symbol):
        """جلب ATR الخارجي من Alpha Vantage للتأكيد"""
        if not self.alpha_key:
            return None
        
        base_symbol = symbol.split('/')[0]
        url = f"https://www.alphavantage.co/query?function=ATR&symbol={base_symbol}&interval=daily&time_period=14&apikey={self.alpha_key}"
        try:
            response = requests.get(url, timeout=(5, 10))  # connect=5s, read=10s
            data = response.json()
            atr_data = data.get("Technical Analysis: ATR", {})
            if atr_data:
                latest_date = max(atr_data.keys())
                return float(atr_data[latest_date]["ATR"])
            return None
        except Exception as e:
            print(f"⚠️ Global price check error: {e}")
            return None

    def get_global_liquidity(self):
        """جلب بيانات السيولة العالمية للماركت (مطلوبة لمحلل السيولة)"""
        data = self.get_global_data()
        return data.get('market_cap_change', 0)

# ========== Standalone Functions (للتوافق مع باقي الموديولات) ==========
def get_external_news_sentiment(symbol):
    """دالة مستقلة لجلب المشاعر للأخبار الخارجية"""
    client = ExternalAPIClient()
    return client.analyze_impact(symbol)

def get_external_atr(symbol):
    """دالة مستقلة لجلب ATR من مصدر خارجي"""
    client = ExternalAPIClient()
    return client.get_external_atr(symbol)