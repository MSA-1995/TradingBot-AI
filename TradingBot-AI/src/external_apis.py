"""
External APIs Module
Handles external API calls for additional data like ATR, news sentiment, liquidity.
"""

import requests
from datetime import datetime

def get_external_atr(symbol):
    """جلب ATR من Alpha Vantage API (مجاني محدود، يحتاج مفتاح)"""
    try:
        api_key = "Y3ZKLD9NZV8L62DV"  # مفتاح Alpha Vantage
        base_symbol = symbol.replace('/USDT', '')
        url = f"https://www.alphavantage.co/query?function=ATR&symbol={base_symbol}&interval=daily&time_period=14&apikey={api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'Technical Analysis: ATR' in data:
            latest = list(data['Technical Analysis: ATR'].values())[0]
            return float(latest['ATR'])
        return 0
    except:
        return 0

def get_external_news_sentiment(symbol):
    """جلب sentiment من NewsAPI (مجاني محدود، يحتاج مفتاح)"""
    try:
        api_key = "62b8fc28dd2647b3ae306e03de639e19"  # مفتاح NewsAPI
        base_symbol = symbol.replace('/USDT', '')
        url = f"https://newsapi.org/v2/everything?q={base_symbol}+crypto&apiKey={api_key}&pageSize=10"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        articles = data.get('articles', [])

        positive_words = ['bullish', 'surge', 'growth', 'adoption']
        negative_words = ['crash', 'ban', 'hack', 'sell-off']
        pos_count = neg_count = 0

        for article in articles:
            title = article.get('title', '').lower()
            for word in positive_words:
                if word in title:
                    pos_count += 1
            for word in negative_words:
                if word in title:
                    neg_count += 1

        total = pos_count + neg_count
        if total == 0:
            score = 0
        else:
            score = (pos_count - neg_count) / total * 10  # normalize to -10 to 10

        return {'score': score}

    except:
        return {'score': 0}

def get_global_liquidity():
    """جلب سيولة عالمية من CoinGecko API (مجاني)"""
    try:
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        total_market_cap = data['data']['total_market_cap']['usd']
        # تحويل حجم السوق إلى score (مثال: >1T = 80, <500B = 20)
        if total_market_cap > 1e12:
            return 80
        elif total_market_cap > 5e11:
            return 60
        elif total_market_cap > 1e11:
            return 40
        else:
            return 20
    except:
        return 50