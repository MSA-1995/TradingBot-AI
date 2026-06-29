"""Split-out analysis helpers."""



def detect_panic_greed(analysis):
    try:
        volume       = analysis.get('volume',       0)
        avg_volume   = analysis.get('volume_sma',   0)
        price_change = analysis.get('price_momentum', 0)

        if avg_volume == 0:
            return {'panic_score': 0, 'greed_score': 0}

        volume_ratio = volume / avg_volume
        panic_score  = 0
        greed_score  = 0

        if volume_ratio > 1.5 and price_change < -2:
            panic_score = min(volume_ratio * 10, 30)

        if volume_ratio > 1.5 and price_change > 2:
            greed_score = min(volume_ratio * 10, 30)

        return {'panic_score': panic_score, 'greed_score': greed_score}

    except Exception:
        return {'panic_score': 0, 'greed_score': 0}
