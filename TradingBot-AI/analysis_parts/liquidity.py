"""Split-out analysis helpers."""

import numpy as np

from analysis_parts.market_data import _order_book_cache


def get_liquidity_metrics(exchange, symbol, df_5m=None, order_book=None):
    try:
        if not order_book:
            _ob_ts = _order_book_cache.get(symbol, {}).get('timestamp', 0)
            if __import__('time').time() - _ob_ts < 60:
                order_book = _order_book_cache[symbol]['data']
            else:
                order_book = exchange.fetch_order_book(symbol, limit=20)
                _order_book_cache[symbol] = {'data': order_book, 'timestamp': __import__('time').time()}

        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return {
                'depth_ratio': 1.0, 'spread_percent': 0.1,
                'bid_depth'  : 0,   'ask_depth'     : 0,
                'liquidity_score': 50, 'price_impact': 0.5,
                'volume_consistency': 50
            }

        bid_depth   = sum(b[1] for b in order_book['bids'][:10]) if len(order_book['bids']) >= 10 else 0
        ask_depth   = sum(a[1] for a in order_book['asks'][:10]) if len(order_book['asks']) >= 10 else 0
        depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0

        best_bid       = order_book['bids'][0][0] if order_book['bids'] else 0
        best_ask       = order_book['asks'][0][0] if order_book['asks'] else 0
        spread_percent = ((best_ask - best_bid) / best_bid) * 100 if best_bid > 0 else 0.1

        cumulative_cost = 0
        price_impact    = 0
        target_cost     = 15

        for ask in order_book['asks']:
            price, volume = ask
            cost = price * volume
            if cumulative_cost + cost >= target_cost:
                price_impact = ((price - best_ask) / best_ask) * 100 if best_ask > 0 else 0
                break
            cumulative_cost += cost

        liquidity_score = 100
        if   spread_percent > 0.5: liquidity_score -= 30
        elif spread_percent > 0.3: liquidity_score -= 15

        if depth_ratio < 0.7 or depth_ratio > 1.5:
            liquidity_score -= 20

        if   bid_depth < 10000: liquidity_score -= 20
        elif bid_depth < 50000: liquidity_score -= 10

        if   price_impact > 1.0: liquidity_score -= 20
        elif price_impact > 0.5: liquidity_score -= 10

        liquidity_score = max(0, liquidity_score)

        volume_consistency = 50
        try:
            if df_5m is not None and not df_5m.empty:
                volumes     = df_5m['volume'].tolist()
                volume_mean = np.mean(volumes)
                volume_std  = np.std(volumes)
                if volume_mean > 0:
                    cv = (volume_std / volume_mean) * 100
                    if   cv < 30: volume_consistency = 90
                    elif cv < 50: volume_consistency = 70
                    elif cv < 80: volume_consistency = 50
                    else:         volume_consistency = 30
        except Exception as e:
            print(f"⚠️ volume_consistency error: {e}")
            volume_consistency = 50

        return {
            'depth_ratio'       : round(depth_ratio,    2),
            'spread_percent'    : round(spread_percent,  4),
            'bid_depth'         : round(bid_depth,       2),
            'ask_depth'         : round(ask_depth,       2),
            'liquidity_score'   : int(liquidity_score),
            'price_impact'      : round(price_impact,    4),
            'volume_consistency': int(volume_consistency)
        }

    except Exception as e:
        print(f"⚠️ Liquidity metrics error for {symbol}: {e}")
        return {
            'depth_ratio': 1.0, 'spread_percent': 0.1,
            'bid_depth'  : 0,   'ask_depth'     : 0,
            'liquidity_score': 50, 'price_impact': 0.5,
            'volume_consistency': 50
        }
