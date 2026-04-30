"""
🌐 External APIs Manager - محرك جلب البيانات الخارجية
مسؤول عن جلب أخبار السيولة، تحركات الحيتان، ومشاعير السوق.
"""
import os
import requests
from datetime import datetime, timedelta, timezone
import time
import threading

# Global lock للـ Fear & Greed - مرة واحدة فقط بين كل الـ threads
_fear_greed_lock   = threading.Lock()
_fear_greed_shared = {'value': None, 'classification': 'Neutral', 'timestamp': 0}

# إضافة كاش مضغوط لنتائج external APIs
try:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir  = os.path.dirname(current_dir)
    memory_path = os.path.join(parent_dir, 'memory')
    if os.path.exists(memory_path) and memory_path not in sys.path:
        sys.path.insert(0, memory_path)
    from memory_cache import MemoryCache
except Exception:
    MemoryCache = None


# Rate Limiter لتجنب API Limits
class RateLimiter:
    def __init__(self, calls_per_minute=60):
        self.calls = []
        self.limit = calls_per_minute
        self.lock  = threading.Lock()

    def wait_if_needed(self):
        with self.lock:
            now        = time.time()
            self.calls = [c for c in self.calls if now - c < 60]
            if len(self.calls) >= self.limit:
                time.sleep(60 - (now - self.calls[0]))
            self.calls.append(now)


class ExternalAPIClient:
    def __init__(self):
        self.news_key     = os.getenv("NEWS_API_KEY")
        self.whale_key    = os.getenv("WHALE_ALERT_API_KEY")
        self.alpha_key    = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.api_cache    = MemoryCache(max_items=30) if MemoryCache else {}
        self.rate_limiter = RateLimiter(calls_per_minute=60)

    # ─────────────────────────────────────────────
    def _cache_get(self, key):
        if MemoryCache:
            return self.api_cache.get(key)
        return self.api_cache.get(key)

    def _cache_set(self, key, value, expiry_seconds=300):
        if MemoryCache:
            self.api_cache.set(key, value, expiry_seconds=expiry_seconds)
        else:
            self.api_cache[key] = value

    # ─────────────────────────────────────────────
    def get_whale_activity(self, min_value=500000):
        """جلب تحركات الحيتان الكبيرة في آخر ساعة"""
        if not self.whale_key:
            return []

        cache_key = f"whale_{min_value}"
        cached    = self._cache_get(cache_key)
        if cached:
            return cached

        self.rate_limiter.wait_if_needed()
        url = (
            f"https://api.whale-alert.io/v1/transactions"
            f"?api_key={self.whale_key}&min_value={min_value}"
        )
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=(5, 10))
                if response.status_code == 200:
                    result = response.json().get('transactions', [])
                    self._cache_set(cache_key, result, expiry_seconds=300)
                    return result
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print(f"⚠️ Whale Alert Error after retries: {e}")
        return []

    # ─────────────────────────────────────────────
    def get_crypto_news(self, query="bitcoin"):
        """جلب الأخبار العاجلة لعملة معينة لتحليل المشاعر"""
        if not self.news_key:
            return []

        cache_key = f"news_{query}"
        cached    = self._cache_get(cache_key)
        if cached:
            return cached

        self.rate_limiter.wait_if_needed()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={query}&from={yesterday}&sortBy=publishedAt&apiKey={self.news_key}"
        )
        try:
            response = requests.get(url, timeout=(5, 10))
            if response.status_code == 200:
                articles = response.json().get('articles', [])
                result   = [a['title'] for a in articles[:5]]
                self._cache_set(cache_key, result, expiry_seconds=300)
                return result
            return []
        except Exception as e:
            print(f"⚠️ NewsAPI Error: {e}")
            return []

    # ─────────────────────────────────────────────
    def get_market_sentiment_global(self):
        """جلب مؤشر الخوف والطمع - مرة واحدة فقط بالـ lock"""
        global _fear_greed_shared

        now = time.time()

        # قراءة سريعة بدون lock
        if (_fear_greed_shared['value'] is not None and
                (now - _fear_greed_shared['timestamp']) < 600):
            return {
                'value':          _fear_greed_shared['value'],
                'classification': _fear_greed_shared['classification']
            }

        # تحديث مع lock - مرة واحدة فقط!
        with _fear_greed_lock:
            now = time.time()
            if (_fear_greed_shared['value'] is not None and
                    (now - _fear_greed_shared['timestamp']) < 600):
                return {
                    'value':          _fear_greed_shared['value'],
                    'classification': _fear_greed_shared['classification']
                }

            self.rate_limiter.wait_if_needed()
            url = "https://api.alternative.me/fng/"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data   = response.json().get('data', [{}])[0]
                    result = {
                        'value':          int(data.get('value', 50)),
                        'classification': data.get('value_classification', 'Neutral')
                    }
                    _fear_greed_shared['value']          = result['value']
                    _fear_greed_shared['classification'] = result['classification']
                    _fear_greed_shared['timestamp']      = time.time()
                    self._cache_set("fear_greed", result, expiry_seconds=600)
                    return result
            except Exception as e:
                pass

            return {'value': 50, 'classification': 'Neutral'}

    # ─────────────────────────────────────────────
    def get_global_price_check(self, symbol):
        """التحقق المتقاطع: جلب السعر من CoinGecko للمقارنة"""
        try:
            coin_id = symbol.split('/')[0].lower()
            mapping = {
                'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana',
                'bnb': 'binancecoin', 'xrp': 'ripple'
            }
            cg_id = mapping.get(coin_id, coin_id)

            cache_key = f"price_{cg_id}"
            cached    = self._cache_get(cache_key)
            if cached:
                return cached

            self.rate_limiter.wait_if_needed()
            url = (
                f"https://api.coingecko.com/api/v3/simple/price"
                f"?ids={cg_id}&vs_currencies=usd"
            )
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                result = response.json().get(cg_id, {}).get('usd')
                if result:
                    self._cache_set(cache_key, result, expiry_seconds=300)
                return result
            return None
        except Exception as e:
            print(f"⚠️ Global price check error: {e}")
            return None

    # ─────────────────────────────────────────────
    def get_global_data(self):
        """جلب القيمة السوقية الإجمالية وسيطرة البيتكوين عبر CoinGecko"""
        cache_key = "global_data"
        cached    = self._cache_get(cache_key)
        if cached:
            return cached

        self.rate_limiter.wait_if_needed()
        url = "https://api.coingecko.com/api/v3/global"
        try:
            response = requests.get(url, timeout=(5, 10))
            if response.status_code == 200:
                data   = response.json().get('data', {})
                result = {
                    'market_cap_change': data.get('market_cap_change_percentage_24h_usd', 0),
                    'btc_dominance':     data.get('market_cap_percentage', {}).get('btc', 0),
                    'total_volume':      data.get('total_volume', {}).get('usd', 0)
                }
                self._cache_set(cache_key, result, expiry_seconds=300)
                return result
            return {}
        except Exception as e:
            print(f"⚠️ Global data error: {e}")
            return {}

    # ─────────────────────────────────────────────
    def analyze_impact(self, symbol=None, **kwargs):
        """تحليل شامل لتأثير البيانات الخارجية على عملة معينة"""
        try:
            news         = self.get_crypto_news(symbol) if symbol else []
            fng          = self.get_market_sentiment_global()
            global_data  = self.get_global_data()
            global_price = self.get_global_price_check(symbol) if symbol else None

            impact_score = 50  # نقطة التعادل

            fng_value = fng.get('value', 50) if isinstance(fng, dict) else 50
            if fng_value > 70:
                impact_score += 10
            if fng_value < 30:
                impact_score -= 15

            if global_data.get('market_cap_change', 0) > 0:
                impact_score += 5

            positive_keywords = ['bullish', 'surge', 'rally', 'gain', 'up', 'high', 'record']
            negative_keywords = ['bearish', 'crash', 'drop', 'fall', 'down', 'low', 'ban']
            positive_count = 0
            negative_count = 0
            for headline in news:
                h = headline.lower()
                if any(k in h for k in positive_keywords):
                    positive_count += 1
                    impact_score   += 3
                if any(k in h for k in negative_keywords):
                    negative_count += 1
                    impact_score   -= 3

            impact_score = max(0, min(100, impact_score))

            return {
                'score':               impact_score,
                'sentiment':           fng.get('classification', 'Neutral') if isinstance(fng, dict) else 'Neutral',
                'fear_greed_value':    fng_value,
                'headlines':           news,
                'positive_news_count': positive_count,
                'negative_news_count': negative_count,
                'global_price':        global_price,
                'btc_dominance':       global_data.get('btc_dominance', 0),
                'timestamp':           datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            print(f"⚠️ analyze_impact error: {e}")
            return {
                'score':               50,
                'sentiment':           'Neutral',
                'fear_greed_value':    50,
                'headlines':           [],
                'positive_news_count': 0,
                'negative_news_count': 0,
                'global_price':        None,
                'btc_dominance':       0,
                'timestamp':           datetime.now(timezone.utc).isoformat()
            }

    # ─────────────────────────────────────────────
    def get_external_atr(self, symbol):
        """جلب ATR الخارجي من Alpha Vantage للتأكيد"""
        if not self.alpha_key:
            return None

        base_symbol = symbol.split('/')[0]
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=ATR&symbol={base_symbol}&interval=daily"
            f"&time_period=14&apikey={self.alpha_key}"
        )
        try:
            response = requests.get(url, timeout=(5, 10))
            if response.status_code != 200:
                return None
            data     = response.json()
            atr_data = data.get("Technical Analysis: ATR", {})
            if atr_data:
                latest_date = max(atr_data.keys())
                return float(atr_data[latest_date]["ATR"])
            return None
        except Exception as e:
            print(f"⚠️ External ATR error: {e}")
            return None

    # ─────────────────────────────────────────────
    def get_global_liquidity(self):
        """جلب بيانات السيولة العالمية للماركت"""
        data              = self.get_global_data()
        market_cap_change = data.get('market_cap_change', 0)
        total_volume      = data.get('total_volume', 0)
        if total_volume > 80_000_000_000:
            outflow_signal = -15
        elif total_volume > 50_000_000_000:
            outflow_signal = 0
        else:
            outflow_signal = +10
        return market_cap_change + outflow_signal


# ═══════════════════════════════════════════════════
# ✅ Singleton - كاش مشترك بين جميع العملات
# ═══════════════════════════════════════════════════
_global_external_client = None

def get_global_external_client():
    """Singleton للـ ExternalAPIClient حتى يشارك الكاش"""
    global _global_external_client
    if _global_external_client is None:
        _global_external_client = ExternalAPIClient()
    return _global_external_client


# ═══════════════════════════════════════════════════
# Standalone Functions (للتوافق مع باقي الموديولات)
# ═══════════════════════════════════════════════════
def get_external_news_sentiment(symbol):
    """دالة مستقلة لجلب المشاعر للأخبار الخارجية"""
    client = get_global_external_client()
    return client.analyze_impact(symbol)


def get_external_atr(symbol):
    """دالة مستقلة لجلب ATR من مصدر خارجي"""
    client = get_global_external_client()
    return client.get_external_atr(symbol)
