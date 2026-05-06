"""Split-out analysis helpers."""

import time
import pickle
import zlib

_market_cache = {'data': {}, 'timestamp': 0}
_order_book_cache = {}
_impact_cache = {}
_last_cleanup = 0


def _pack_candles(data):
    """Compress OHLCV candles in RAM cache."""
    try:
        return zlib.compress(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL), level=3)
    except Exception:
        return data


def _unpack_candles(data):
    """Read compressed or legacy uncompressed OHLCV candles."""
    try:
        if isinstance(data, (bytes, bytearray)):
            return pickle.loads(zlib.decompress(data))
    except Exception:
        return None
    return data


def cleanup_caches():
    """Clean old entries from all caches periodically"""
    global _order_book_cache, _impact_cache, _last_cleanup
    now = time.time()
    
    # Cleanup every 5 minutes
    if now - _last_cleanup < 300:
        return
    
    _last_cleanup = now
    
    # Clean order book cache (older than 1 hour)
    expired_keys = []
    for key, entry in list(_order_book_cache.items()):
        ts = entry.get('ts', 0) or entry.get('timestamp', 0)
        if now - ts > 3600:  # 1 hour expiry
            expired_keys.append(key)
    for key in expired_keys:
        del _order_book_cache[key]
    
    # Clean impact cache (older than 1 hour)
    expired_keys = []
    for key, entry in list(_impact_cache.items()):
        ts = entry.get('ts', 0)
        if now - ts > 3600:
            expired_keys.append(key)
    for key in expired_keys:
        del _impact_cache[key]


def get_market_data(exchange, ttl_hash=None):
    global _market_cache
    # Periodic cleanup
    cleanup_caches()
    
    current_time = time.time()
    if current_time - _market_cache['timestamp'] < 60:
        return _market_cache['data']

    new_market_data = {}
    for market_coin in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
        try:
            m_ohlcv = exchange.fetch_ohlcv(market_coin, '5m', limit=13)
            if len(m_ohlcv) >= 13:
                m_current = m_ohlcv[-1][4]
                m_1h_ago  = m_ohlcv[-13][4]
                change    = ((m_current - m_1h_ago) / m_1h_ago) * 100
                new_market_data[market_coin] = change
            else:
                new_market_data[market_coin] = 0
        except Exception as e:
            print(f"⚠️ Market data error {market_coin}: {e}")
            new_market_data[market_coin] = 0

    _market_cache = {'data': new_market_data, 'timestamp': current_time}
    return new_market_data


def get_ttl_hash(seconds=20):
    return round(time.time() / seconds)


def _fetch_ohlcv_cached(exchange, symbol, timeframe, cache_key, limit=None):
    """Fetch OHLCV with caching to reduce API delay"""
    try:
        _cv = _order_book_cache.get(cache_key, {})
        _now = time.time()
        _expiry = {'5m': 240, '15m': 840, '1h': 3540, '4h': 14340, '1d': 86340}.get(timeframe, 240)
        
        if _cv and _now - _cv.get('ts', 0) < _expiry:
            return _unpack_candles(_cv.get('d'))
        
        _data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit) if limit else exchange.fetch_ohlcv(symbol, timeframe)
        _order_book_cache[cache_key] = {'d': _pack_candles(_data), 'ts': _now}
        return _data
    except Exception as e:
        print(f"⚠️ Failed to fetch {timeframe} candles for {symbol}: {e}")
        return None
