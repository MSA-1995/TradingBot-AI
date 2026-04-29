"""
📊 Technical Analysis Module
Handles RSI, MACD, Volume, Momentum calculations
"""

import pandas as pd
import ta
from datetime import datetime, timezone
import time
import numpy as np
from market_intelligence import get_market_regime, check_flash_crash, get_time_analysis, get_time_multiplier
from news_analyzer import get_sentiment_data

_market_cache = {'data': {}, 'timestamp': 0}

def get_market_data(exchange, ttl_hash=None):
    global _market_cache
    current_time = time.time()
    if current_time - _market_cache['timestamp'] < 20:
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

def analyze_market_structure(df):
    if df is None or len(df) < 20:
        return {'structure': 'unknown', 'score': 0, 'reason': 'Not enough data'}

    closes = df['close'].tolist()
    highs  = df['high'].tolist()
    lows   = df['low'].tolist()

    swing_points = []
    window = 3

    for i in range(window, len(closes) - window):
        is_high = all(highs[i] >= highs[j] for j in range(i - window, i + window + 1) if j != i)
        is_low  = all(lows[i]  <= lows[j]  for j in range(i - window, i + window + 1) if j != i)
        if is_high:
            swing_points.append(('H', i, highs[i]))
        elif is_low:
            swing_points.append(('L', i, lows[i]))

    if len(swing_points) < 3:
        return {'structure': 'unclear', 'score': 0, 'reason': 'No clear swings'}

    recent_swings = swing_points[-6:]
    highs_list    = [s for s in recent_swings if s[0] == 'H']
    lows_list     = [s for s in recent_swings if s[0] == 'L']

    structure = 'neutral'
    score     = 0
    reason    = ''

    if len(lows_list) >= 2:
        last_low = lows_list[-1][2]
        prev_low = lows_list[-2][2]

        if last_low > prev_low * 1.002:
            if len(highs_list) >= 2 and highs_list[-1][2] > highs_list[-2][2] * 1.002:
                structure = 'higher_highs_higher_lows'
                score     = 20
                reason    = 'HH + HL (Bullish Structure)'
            else:
                structure = 'higher_lows'
                score     = 10
                reason    = 'HL (Potential Reversal)'
        elif last_low < prev_low * 0.998:
            if len(highs_list) >= 2 and highs_list[-1][2] < highs_list[-2][2] * 0.998:
                structure = 'lower_highs_lower_lows'
                score     = -20
                reason    = 'LH + LL (Bearish Structure)'
            else:
                structure = 'lower_lows'
                score     = -10
                reason    = 'LL (Downtrend)'
        else:
            structure = 'ranging'
            score     = 5
            reason    = 'Sideways / Ranging'
    elif len(highs_list) >= 2:
        if highs_list[-1][2] > highs_list[-2][2] * 1.002:
            structure = 'higher_highs'
            score     = 10
            reason    = 'HH (Uptrend)'
        else:
            structure = 'lower_highs'
            score     = -10
            reason    = 'LH (Weakening)'

    return {'structure': structure, 'score': score, 'reason': reason}


def analyze_support_resistance(df):
    if df is None or len(df) < 30:
        return {'at_support': False, 'at_resistance': False, 'score': 0, 'reason': 'Not enough data'}

    current_price     = df.iloc[-1]['close']
    lows              = df['low'].tail(60).tolist()
    highs             = df['high'].tail(60).tolist()
    support_levels    = []
    resistance_levels = []

    for i in range(2, len(lows) - 2):
        if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1] and lows[i] <= lows[i+2]:
            support_levels.append(lows[i])

    for i in range(2, len(highs) - 2):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]:
            resistance_levels.append(highs[i])

    tolerance     = 0.008
    at_support    = False
    at_resistance = False
    score         = 0
    reason        = ''

    for sl in support_levels:
        if abs(current_price - sl) / sl < tolerance:
            at_support = True
            score      = 15
            reason     = f'Near Support ({sl:.4f})'
            break

    for rl in resistance_levels:
        if abs(current_price - rl) / rl < tolerance:
            at_resistance = True
            score         = -15
            reason        = f'Near Resistance ({rl:.4f})'
            break

    if not at_support and not at_resistance:
        nearest_support    = max([s for s in support_levels    if s < current_price], default=0)
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=0)

        if nearest_support > 0:
            dist_to_support = (current_price - nearest_support) / nearest_support * 100
            if dist_to_support < 2:
                score  = 5
                reason = f'Approaching Support ({dist_to_support:.1f}%)'

        if nearest_resistance > 0:
            dist_to_res = (nearest_resistance - current_price) / current_price * 100
            if dist_to_res < 2:
                score  = -5
                reason = f'Approaching Resistance ({dist_to_res:.1f}%)'

    return {'at_support': at_support, 'at_resistance': at_resistance, 'score': score, 'reason': reason}


def analyze_mtf_confirmation(df):
    if df is None or len(df) < 60:
        return {'confirmed': False, 'score': 0, 'reason': 'Not enough data'}

    scores_5m  = 0
    scores_15m = 0
    scores_1h  = 0
    closes     = df['close'].tolist()
    rsi_col    = df.get('rsi')

    if len(closes) >= 5:
        if closes[-1] > closes[-3]:
            scores_5m += 1
        if rsi_col is not None and len(rsi_col) >= 5:
            if   rsi_col.iloc[-1] < 40: scores_5m += 1
            elif rsi_col.iloc[-1] < 50: scores_5m += 0.5

    if len(closes) >= 15:
        closes_15m = closes[-15:]
        if closes[-1] > sum(closes_15m[:5]) / 5:
            scores_15m += 1
        if rsi_col is not None and len(rsi_col) >= 15:
            if   rsi_col.iloc[-1] < 35: scores_15m += 1
            elif rsi_col.iloc[-1] < 45: scores_15m += 0.5

    if len(closes) >= 60:
        closes_1h = closes[-60:]
        if closes[-1] > sum(closes_1h[:12]) / 12:
            scores_1h += 1
        if rsi_col is not None and len(rsi_col) >= 60:
            if   rsi_col.iloc[-1] < 30: scores_1h += 1
            elif rsi_col.iloc[-1] < 40: scores_1h += 0.5

    confirmed_frames = 0
    if scores_5m  >= 1: confirmed_frames += 1
    if scores_15m >= 1: confirmed_frames += 1
    if scores_1h  >= 1: confirmed_frames += 1

    mtf_score = 0
    confirmed = False
    reason    = ''

    if confirmed_frames >= 2:
        mtf_score = 20
        confirmed = True
        reason    = f'MTF Confirmed ({confirmed_frames}/3 frames)'
    elif confirmed_frames == 1:
        mtf_score = 10
        reason    = f'Partial MTF ({confirmed_frames}/3 frames)'
    else:
        mtf_score = 0
        reason    = 'No MTF Confirmation'

    return {'confirmed': confirmed, 'score': mtf_score, 'reason': reason, 'frames': confirmed_frames}


def analyze_reversal(df, rsi):
    from config import BOTTOM_BOUNCE_THRESHOLD, REVERSAL_CANDLES, MIN_BUY_CONFIDENCE

    base_result = {
        'confidence': 0, 'candle_signal': False, 'reasons': [],
        'bounce_percent': 0, 'is_reversing': False, 'trend': 'neutral',
        'momentum': 0, 'score_breakdown': {}, 'reversal_signals': 0
    }

    if df is None or len(df) < 10:
        return base_result

    if rsi > 80:
        base_result['reasons'].append(f'RSI Overbought ({rsi:.0f}) — not a bottom')
        return base_result

    try:
        total_score      = 0
        reasons          = []
        score_breakdown  = {}
        reversal_signals = 0

        rsi_score    = 0
        rsi_reversal = False
        if len(df) >= 5 and 'rsi' in df.columns:
            rsi_values = df['rsi'].tail(5).tolist()
            rsi_bottom = min(rsi_values[:-1])
            rsi_now    = rsi_values[-1]
            rsi_prev   = rsi_values[-2]

            if rsi_bottom < 45 and rsi_now > rsi_prev:
                rsi_rise = rsi_now - rsi_bottom
                if rsi_rise >= 5 and rsi_bottom < 30:
                    rsi_score = 30
                    reasons.append(f"RSI Reversal: {rsi_bottom:.0f}→{rsi_now:.0f} (+{rsi_rise:.0f}) (+30)")
                    rsi_reversal = True
                    reversal_signals += 1
                elif rsi_rise >= 3 and rsi_bottom < 40:
                    rsi_score = 20
                    reasons.append(f"RSI Recovering: {rsi_bottom:.0f}→{rsi_now:.0f} (+20)")
                    rsi_reversal = True
                    reversal_signals += 1
                elif rsi_rise >= 2 and rsi_bottom < 45:
                    rsi_score = 10
                    reasons.append(f"RSI Bouncing: {rsi_bottom:.0f}→{rsi_now:.0f} (+10)")
            elif rsi < 30:
                rsi_score = 8
                reasons.append(f"RSI Oversold ({rsi:.0f}) (+8)")

        total_score += rsi_score
        score_breakdown['rsi_reversal'] = rsi_score

        macd_score    = 0
        macd_reversal = False
        if 'macd_histogram' in df.columns and len(df) >= 6:
            hist        = df['macd_histogram'].tail(6).tolist()
            hist_bottom = min(hist[:-2])
            hist_now    = hist[-1]
            hist_prev   = hist[-2]

            if hist_bottom < 0 and hist_now > hist_prev:
                recovery = (hist_now - hist_bottom) / abs(hist_bottom) if hist_bottom != 0 else 0
                if recovery > 0.5 and hist_now < 0:
                    macd_score = 25
                    reasons.append(f"MACD Strong Recovery ({hist_bottom:.3f}→{hist_now:.3f}) (+25)")
                    macd_reversal = True
                    reversal_signals += 1
                elif recovery > 0.3 and hist_now < 0:
                    macd_score = 15
                    reasons.append(f"MACD Recovering (+15)")
                    macd_reversal = True
                    reversal_signals += 1
                elif hist_now > 0 and hist_prev < 0:
                    macd_score = 20
                    reasons.append(f"MACD Crossed Above Zero (+20)")
                    macd_reversal = True
                    reversal_signals += 1
                elif recovery > 0.15:
                    macd_score = 8
                    reasons.append(f"MACD Improving (+8)")

        total_score += macd_score
        score_breakdown['macd_reversal'] = macd_score

        momentum_score    = 0
        momentum_reversal = False
        if len(df) >= 6:
            closes          = df['close'].tail(6).tolist()
            momentum_recent = (closes[-1] - closes[-3]) / closes[-3] * 100 if closes[-3] > 0 else 0
            momentum_prev   = (closes[-3] - closes[-6]) / closes[-6] * 100 if closes[-6] > 0 else 0

            if momentum_prev < -0.3 and momentum_recent > momentum_prev:
                accel = momentum_recent - momentum_prev
                if accel > 1.0 and momentum_recent >= 0:
                    momentum_score = 20
                    reasons.append(f"Momentum Reversed: {momentum_prev:.2f}%→{momentum_recent:.2f}% (+20)")
                    momentum_reversal = True
                    reversal_signals += 1
                elif accel > 0.5:
                    momentum_score = 12
                    reasons.append(f"Momentum Recovering (+12)")
                    momentum_reversal = True
                    reversal_signals += 1
                elif accel > 0.2:
                    momentum_score = 6
                    reasons.append(f"Momentum Slowing Down (+6)")

        total_score += momentum_score
        score_breakdown['momentum_reversal'] = momentum_score

        _now = datetime.now(timezone.utc)
        _hour = _now.hour
        is_quiet_time = (0 <= _hour < 8)

        vol_score      = 0
        volume_reversal = False
        if len(df) >= 4:
            current_vol = float(df.iloc[-1].get('volume_ratio', 1))
            last_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            is_bullish  = last_candle['close'] > last_candle['open']
            was_bearish = prev_candle['close'] < prev_candle['open']

            threshold_high = 1.5 if is_quiet_time else 2.0
            threshold_mid  = 1.2 if is_quiet_time else 1.5
            threshold_low  = 1.0 if is_quiet_time else 1.2

            if current_vol > threshold_high and is_bullish and was_bearish:
                vol_score = 20
                reasons.append(f"Vol Bullish Reversal {current_vol:.1f}x (+20)")
                volume_reversal = True
                reversal_signals += 1
            elif current_vol > threshold_mid and is_bullish:
                vol_score = 12
                reasons.append(f"Vol Bullish {current_vol:.1f}x (+12)")
                volume_reversal = True
                reversal_signals += 1
            elif current_vol > threshold_low and is_bullish:
                vol_score = 6
                reasons.append(f"Vol Rising on Bounce {current_vol:.1f}x (+6)")

        total_score += vol_score
        score_breakdown['volume_reversal'] = vol_score

        div_score = 0
        if len(df) >= 20 and 'rsi' in df.columns:
            recent_lows = df['low'].tail(20).tolist()
            recent_rsis = df['rsi'].tail(20).tolist()

            if len(recent_lows) >= 10:
                first_low  = min(recent_lows[:10])
                second_low = min(recent_lows[10:])
                first_idx  = recent_lows[:10].index(first_low)
                second_idx = 10 + recent_lows[10:].index(second_low)
                first_rsi  = recent_rsis[first_idx]
                second_rsi = recent_rsis[second_idx]

                if second_low < first_low * 0.999 and second_rsi > first_rsi + 3:
                    rsi_diff = second_rsi - first_rsi
                    if rsi_diff > 8:
                        div_score = 20
                        reasons.append(f"Strong Bullish Divergence (price↓ RSI↑{rsi_diff:.0f}) (+20)")
                        reversal_signals += 1
                    elif rsi_diff > 4:
                        div_score = 12
                        reasons.append(f"Bullish Divergence (+12)")
                        reversal_signals += 1

        total_score += div_score
        score_breakdown['divergence'] = div_score

        ms       = analyze_market_structure(df)
        ms_score = 0
        if ms['structure'] == 'higher_highs_higher_lows':
            ms_score = 15
            reasons.append(f"🏗️ {ms['reason']} (+15)")
            reversal_signals += 1
        elif ms['structure'] == 'higher_lows':
            ms_score = 10
            reasons.append(f"🏗️ {ms['reason']} (+10)")
        total_score += ms_score
        score_breakdown['market_structure'] = ms_score

        sr       = analyze_support_resistance(df)
        sr_score = 0
        if sr['at_support']:
            sr_score = 10
            reasons.append(f"📐 {sr['reason']} (+10)")
        total_score += sr_score
        score_breakdown['support'] = sr_score

        if reversal_signals < 2:
            total_score = min(total_score, 40)
            reasons.append(f"⚠️ Only {reversal_signals} reversal signal(s) — possible noise")
        elif reversal_signals == 2:
            reasons.append(f"🟡 {reversal_signals} reversal signals — moderate bottom")
        else:
            reasons.append(f"🟢 {reversal_signals} reversal signals — strong bottom")

        trap_is_filter = False
        if len(df) >= 20:
            avg_volume = df['volume'].tail(20).mean()
            for check_idx in range(1, min(4, len(df) + 1)):
                check_candle = df.iloc[-check_idx]
                check_volume = check_candle['volume']
                if avg_volume > 0 and check_volume > avg_volume * 3.5:
                    candle_body  = abs(check_candle['close'] - check_candle['open'])
                    candle_range = check_candle['high'] - check_candle['low']
                    if candle_range > 0 and candle_body > 0:
                        upper_shadow = check_candle['high'] - max(check_candle['close'], check_candle['open'])
                        if upper_shadow > candle_body * 3.5:
                            trap_is_filter = True
                            reasons.append(f"⚠️ Fake Pump Trap (Candle-{check_idx})")
                            break

        n              = min(REVERSAL_CANDLES, len(df))
        low_n          = df['low'].tail(n).min()
        current_price  = df.iloc[-1]['close']
        bounce_percent = ((current_price - low_n) / low_n) * 100 if low_n > 0 else 0
        confidence_percent = min(total_score, 150)
        is_candle_signal   = (confidence_percent >= MIN_BUY_CONFIDENCE and reversal_signals >= 2)

        if trap_is_filter and is_candle_signal:
            is_candle_signal = False
            reasons.append("🚫 Signal Blocked by Trap")

        if confidence_percent >= MIN_BUY_CONFIDENCE and reversal_signals >= 3:
            reasons.append(f"✅ STRONG BOTTOM ({total_score}/150, {reversal_signals} signals)")
        elif confidence_percent >= MIN_BUY_CONFIDENCE and reversal_signals >= 2:
            reasons.append(f"✅ BOTTOM SIGNAL ({total_score}/150, {reversal_signals} signals)")
        elif total_score >= 40:
            reasons.append(f"⏳ WEAK ({total_score}/150, {reversal_signals} signals)")
        else:
            reasons.append(f"❌ NO SIGNAL ({total_score}/150, {reversal_signals} signals)")

        base_result['is_reversing'] = bounce_percent >= BOTTOM_BOUNCE_THRESHOLD
        base_result.update({
            'confidence'      : confidence_percent,
            'candle_signal'   : is_candle_signal,
            'reasons'         : reasons,
            'bounce_percent'  : round(bounce_percent, 3),
            'score_breakdown' : score_breakdown,
            'reversal_signals': reversal_signals
        })
        return base_result

    except Exception as e:
        base_result['reasons'].append(f'Error: {e}')
        return base_result


def analyze_peak(df, rsi):
    from config import PEAK_DROP_THRESHOLD, REVERSAL_CANDLES, MIN_SELL_CONFIDENCE, MIN_BUY_CONFIDENCE

    base_result = {
        'confidence': 0, 'candle_signal': False, 'reasons': [],
        'drop_percent': 0, 'is_peaking': False, 'trend': 'neutral',
        'momentum': 0, 'score_breakdown': {}, 'reversal_signals': 0
    }

    if df is None or len(df) < 10:
        return base_result

    try:
        total_score      = 0
        reasons          = []
        score_breakdown  = {}
        reversal_signals = 0

        rsi_score    = 0
        rsi_reversal = False
        if len(df) >= 5 and 'rsi' in df.columns:
            rsi_values = df['rsi'].tail(5).tolist()
            rsi_peak   = max(rsi_values[:-1])
            rsi_now    = rsi_values[-1]
            rsi_prev   = rsi_values[-2]

            if rsi_peak > 60 and rsi_now < rsi_prev:
                rsi_drop = rsi_peak - rsi_now
                if rsi_drop >= 5 and rsi_peak > 70:
                    rsi_score = 30
                    reasons.append(f"RSI Reversal: {rsi_peak:.0f}→{rsi_now:.0f} (-{rsi_drop:.0f}) (+30)")
                    rsi_reversal = True
                    reversal_signals += 1
                elif rsi_drop >= 3 and rsi_peak > 65:
                    rsi_score = 20
                    reasons.append(f"RSI Weakening: {rsi_peak:.0f}→{rsi_now:.0f} (+20)")
                    rsi_reversal = True
                    reversal_signals += 1
                elif rsi_drop >= 2 and rsi_peak > 60:
                    rsi_score = 10
                    reasons.append(f"RSI Softening: {rsi_peak:.0f}→{rsi_now:.0f} (+10)")
            elif rsi > 75:
                rsi_score = 8
                reasons.append(f"RSI Extreme ({rsi:.0f}) (+8)")

        total_score += rsi_score
        score_breakdown['rsi_reversal'] = rsi_score

        macd_score    = 0
        macd_reversal = False
        if 'macd_histogram' in df.columns and len(df) >= 6:
            hist      = df['macd_histogram'].tail(6).tolist()
            hist_peak = max(hist[:-2])
            hist_now  = hist[-1]
            hist_prev = hist[-2]

            if hist_peak > 0 and hist_now < hist_prev:
                weakness = (hist_peak - hist_now) / abs(hist_peak) if hist_peak != 0 else 0
                if weakness > 0.5 and hist_now > 0:
                    macd_score = 25
                    reasons.append(f"MACD Strong Weakening ({hist_peak:.3f}→{hist_now:.3f}) (+25)")
                    macd_reversal = True
                    reversal_signals += 1
                elif weakness > 0.3 and hist_now > 0:
                    macd_score = 15
                    reasons.append(f"MACD Weakening (+15)")
                    macd_reversal = True
                    reversal_signals += 1
                elif hist_now < 0 and hist_prev > 0:
                    macd_score = 20
                    reasons.append(f"MACD Crossed Below Zero (+20)")
                    macd_reversal = True
                    reversal_signals += 1
                elif weakness > 0.15:
                    macd_score = 8
                    reasons.append(f"MACD Softening (+8)")

        total_score += macd_score
        score_breakdown['macd_reversal'] = macd_score

        momentum_score    = 0
        momentum_reversal = False
        if len(df) >= 6:
            closes          = df['close'].tail(6).tolist()
            momentum_recent = (closes[-1] - closes[-3]) / closes[-3] * 100 if closes[-3] > 0 else 0
            momentum_prev   = (closes[-3] - closes[-6]) / closes[-6] * 100 if closes[-6] > 0 else 0

            if momentum_prev > 0.3 and momentum_recent < momentum_prev:
                decel = momentum_prev - momentum_recent
                if decel > 1.0 and momentum_recent <= 0:
                    momentum_score = 20
                    reasons.append(f"Momentum Reversed: {momentum_prev:.2f}%→{momentum_recent:.2f}% (+20)")
                    momentum_reversal = True
                    reversal_signals += 1
                elif decel > 0.5:
                    momentum_score = 12
                    reasons.append(f"Momentum Decelerating (+12)")
                    momentum_reversal = True
                    reversal_signals += 1
                elif decel > 0.2:
                    momentum_score = 6
                    reasons.append(f"Momentum Softening (+6)")

        total_score += momentum_score
        score_breakdown['momentum_reversal'] = momentum_score

        _now = datetime.now(timezone.utc)
        _hour = _now.hour
        is_quiet_time = (0 <= _hour < 8)

        vol_score       = 0
        volume_reversal = False
        if len(df) >= 4:
            current_vol = float(df.iloc[-1].get('volume_ratio', 1))
            last_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            is_bearish  = last_candle['close'] < last_candle['open']
            was_bullish = prev_candle['close'] > prev_candle['open']

            threshold_high = 1.5 if is_quiet_time else 2.0
            threshold_mid  = 1.2 if is_quiet_time else 1.5
            if current_vol > threshold_high and is_bearish and was_bullish:
                vol_score = 20
                reasons.append(f"Vol Bearish Reversal {current_vol:.1f}x (+20)")
                volume_reversal = True
                reversal_signals += 1
            elif current_vol > threshold_mid and is_bearish:
                vol_score = 12
                reasons.append(f"Vol Bearish {current_vol:.1f}x (+12)")
                volume_reversal = True
                reversal_signals += 1
            elif current_vol < 0.6 and not is_bearish:
                vol_score = 8
                reasons.append(f"Vol Drying Up on Rally {current_vol:.1f}x (+8)")

        total_score += vol_score
        score_breakdown['volume_reversal'] = vol_score

        div_score = 0
        if len(df) >= 20 and 'rsi' in df.columns:
            recent_highs = df['high'].tail(20).tolist()
            recent_rsis  = df['rsi'].tail(20).tolist()

            if len(recent_highs) >= 10:
                first_high  = max(recent_highs[:10])
                second_high = max(recent_highs[10:])
                first_idx   = recent_highs[:10].index(first_high)
                second_idx  = 10 + recent_highs[10:].index(second_high)
                first_rsi   = recent_rsis[first_idx]
                second_rsi  = recent_rsis[second_idx]

                if second_high > first_high * 1.001 and second_rsi < first_rsi - 3:
                    rsi_diff = first_rsi - second_rsi
                    if rsi_diff > 8:
                        div_score = 20
                        reasons.append(f"Strong Bearish Divergence (price↑ RSI↓{rsi_diff:.0f}) (+20)")
                        reversal_signals += 1
                    elif rsi_diff > 4:
                        div_score = 12
                        reasons.append(f"Bearish Divergence (+12)")
                        reversal_signals += 1

        total_score += div_score
        score_breakdown['divergence'] = div_score

        ms       = analyze_market_structure(df)
        ms_score = 0
        if ms['structure'] in ('lower_highs_lower_lows', 'lower_lows'):
            ms_score = 15
            reasons.append(f"🏗️ {ms['reason']} (+15)")
            reversal_signals += 1
        elif ms['structure'] == 'lower_highs':
            ms_score = 8
            reasons.append(f"🏗️ {ms['reason']} (+8)")
        total_score += ms_score
        score_breakdown['market_structure'] = ms_score

        sr       = analyze_support_resistance(df)
        sr_score = 0
        if sr['at_resistance']:
            sr_score = 10
            reasons.append(f"📐 {sr['reason']} (+10)")
        total_score += sr_score
        score_breakdown['resistance'] = sr_score

        if reversal_signals < 2:
            total_score = min(total_score, 40)
            reasons.append(f"⚠️ Only {reversal_signals} reversal signal(s) — possible noise")
        elif reversal_signals == 2:
            reasons.append(f"🟡 {reversal_signals} reversal signals — moderate peak")
        else:
            reasons.append(f"🔴 {reversal_signals} reversal signals — strong peak")

        trap_is_filter = False
        if len(df) >= 20:
            avg_volume = df['volume'].tail(20).mean()
            for check_idx in range(1, min(4, len(df) + 1)):
                check_candle = df.iloc[-check_idx]
                check_volume = check_candle['volume']
                if avg_volume > 0 and check_volume > avg_volume * 3.0:
                    candle_body  = abs(check_candle['close'] - check_candle['open'])
                    candle_range = check_candle['high'] - check_candle['low']
                    if candle_range > 0 and candle_body > 0:
                        lower_shadow = min(check_candle['close'], check_candle['open']) - check_candle['low']
                        if lower_shadow > candle_body * 3.0:
                            trap_is_filter = True
                            reasons.append(f"⚠️ Fake Dip Trap (Candle-{check_idx})")
                            break

        n                  = min(REVERSAL_CANDLES, len(df))
        high_n             = df['high'].tail(n).max()
        current_price      = df.iloc[-1]['close']
        drop_percent       = ((high_n - current_price) / high_n) * 100 if high_n > 0 else 0
        confidence_percent = min(total_score, 140)
        is_candle_signal   = (confidence_percent >= MIN_SELL_CONFIDENCE and reversal_signals >= 3)

        if trap_is_filter and is_candle_signal:
            is_candle_signal = False
            reasons.append("🚫 Signal Blocked by Trap")

        if confidence_percent >= MIN_SELL_CONFIDENCE and reversal_signals >= 3:
            reasons.append(f"✅ STRONG PEAK ({total_score}/140, {reversal_signals} signals)")
        elif confidence_percent >= MIN_SELL_CONFIDENCE and reversal_signals >= 2:
            reasons.append(f"✅ PEAK SIGNAL ({total_score}/140, {reversal_signals} signals)")
        elif total_score >= 40:
            reasons.append(f"⏳ WEAK ({total_score}/140, {reversal_signals} signals)")
        else:
            reasons.append(f"❌ NO PEAK ({total_score}/140, {reversal_signals} signals)")

        base_result['is_peaking'] = drop_percent >= PEAK_DROP_THRESHOLD
        base_result.update({
            'confidence'      : confidence_percent,
            'candle_signal'   : is_candle_signal,
            'reasons'         : reasons,
            'drop_percent'    : round(drop_percent, 3),
            'score_breakdown' : score_breakdown,
            'reversal_signals': reversal_signals
        })
        return base_result

    except Exception as e:
        base_result['reasons'].append(f'Error: {e}')
        return base_result


# ═══════════════════════════════════════════════════════════════
def get_market_analysis(exchange, symbol, limit=120, external_client=None):
    """Get technical analysis for a symbol with multi-timeframe data"""
    analysis_start = time.time()
    try:
        # ─────────────────────────────────────────────
        # 1️⃣ جلب بيانات OHLCV
        # ─────────────────────────────────────────────
        ohlcv_5m  = None
        ohlcv_15m = None
        ohlcv_1h  = None
        ohlcv_4h  = None
        ohlcv_1d  = None

        try:
            ohlcv_5m = exchange.fetch_ohlcv(symbol, '5m', limit=limit)
        except Exception as e:
            print(f"⚠️ Failed to fetch 5m candles for {symbol}: {e}")
            return None

        try:
            ohlcv_15m = exchange.fetch_ohlcv(symbol, '15m', limit=60)
        except Exception as e:
            print(f"⚠️ Failed to fetch 15m candles for {symbol}: {e}")

        try:
            ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=24)
        except Exception as e:
            print(f"⚠️ Failed to fetch 1h candles for {symbol}: {e}")

        try:
            ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
        except Exception as e:
            print(f"⚠️ Failed to fetch 4h candles for {symbol}: {e}")

        try:
            ohlcv_1d = exchange.fetch_ohlcv(symbol, '1d', limit=14)
        except Exception as e:
            print(f"⚠️ Failed to fetch 1d candles for {symbol}: {e}")

        if not ohlcv_5m or len(ohlcv_5m) < 20:
            print(f"⚠️ Not enough 5m data for {symbol}")
            return None

        # ─────────────────────────────────────────────
        # 2️⃣ بناء DataFrame الرئيسي (5m)
        # ─────────────────────────────────────────────
        df = pd.DataFrame(
            ohlcv_5m,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # ── EMA ──────────────────────────────────────
        df['ema_9']  = df['close'].ewm(span=9,  adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()

        ema_cross_series  = (
            (df['ema_9'] > df['ema_21']).astype(int) -
            (df['ema_9'] < df['ema_21']).astype(int)
        )
        df['ema_crossover'] = ema_cross_series

        # ── RSI ──────────────────────────────────────
        delta     = df['close'].diff()
        gain      = delta.clip(lower=0).rolling(14).mean()
        loss      = (-delta.clip(upper=0)).rolling(14).mean()
        rs        = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df.loc[(gain > 0) & (loss == 0), 'rsi'] = 100
        df.loc[(gain == 0) & (loss > 0), 'rsi'] = 0
        df.loc[(gain == 0) & (loss == 0), 'rsi'] = 50

        # ── MACD ─────────────────────────────────────
        ema_12              = df['close'].ewm(span=12, adjust=False).mean()
        ema_26              = df['close'].ewm(span=26, adjust=False).mean()
        df['macd']          = ema_12 - ema_26
        df['macd_signal']   = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_diff']     = df['macd'] - df['macd_signal']
        df['macd_histogram']= df['macd_diff']
        df['macd_diff_pct']  = (df['macd_diff'] / df['close'].replace(0, 1)) * 100

        # ── ATR ──────────────────────────────────────
        tr        = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift()).abs(),
            (df['low']  - df['close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        # ── Volume ───────────────────────────────────
        df['volume_sma']   = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma'].replace(0, 1)
        vol_trend_val      = df['volume_ratio'].rolling(5).mean().iloc[-1] - 1.0
        df['volume_trend'] = vol_trend_val

        # ── Price Change ─────────────────────────────
        df['price_change']    = df['close'].pct_change() * 100
        df['price_change_1h'] = df['close'].pct_change(12) * 100   # 12 x 5m = 1h

        # ── Noise / Fake Break ───────────────────────
        df['is_noise']   = df['atr'] > df['close'] * 0.005
        df['fake_break'] = (
            (df['high'] > df['high'].shift(1)) &
            (df['close'] < df['high'].shift(1))
        )

        # ─────────────────────────────────────────────
        # 3️⃣ latest (آخر شمعة)
        # ─────────────────────────────────────────────
        def _safe(val, default=0.0):
            try:
                return float(val) if not pd.isna(val) else default
            except Exception:
                return default

        lr     = df.iloc[-1]   # last row
        latest = {
            'close'          : _safe(lr['close']),
            'open'           : _safe(lr['open']),
            'high'           : _safe(lr['high']),
            'low'            : _safe(lr['low']),
            'volume'         : _safe(lr['volume']),
            'rsi'            : _safe(lr['rsi'],            50.0),
            'macd'           : _safe(lr['macd'],           0.0),
            'macd_signal'    : _safe(lr['macd_signal'],    0.0),
            'macd_diff'      : _safe(lr['macd_diff'],      0.0),
            'macd_diff_pct'  : _safe(lr['macd_diff_pct'],  0.0),
            'atr'            : _safe(lr['atr'],            0.0),
            'ema_9'          : _safe(lr['ema_9'],          _safe(lr['close'])),
            'ema_21'         : _safe(lr['ema_21'],         _safe(lr['close'])),
            'ema_crossover'  : int(_safe(lr['ema_crossover'], 0)),
            'volume_sma'     : _safe(lr['volume_sma'],    _safe(lr['volume'])),
            'volume_ratio'   : _safe(lr['volume_ratio'],  1.0),
            'volume_trend'   : _safe(vol_trend_val,       0.0),
            'price_change'   : _safe(lr['price_change'],  0.0),
            'price_change_1h': _safe(lr['price_change_1h'], 0.0),
            'is_noise'       : bool(lr['is_noise']),
            'fake_break'     : bool(lr['fake_break']),
        }

        # ─────────────────────────────────────────────
        # 4️⃣ Candles للـ UI
        # ─────────────────────────────────────────────
        candles    = df[['timestamp','open','high','low','close','volume']].tail(50).to_dict('records')
        candles_5m = candles

        candles_15m = []
        if ohlcv_15m and len(ohlcv_15m) > 0:
            df_15m = pd.DataFrame(ohlcv_15m, columns=['timestamp','open','high','low','close','volume'])
            df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            candles_15m = df_15m[['timestamp','open','high','low','close','volume']].tail(50).to_dict('records')

        candles_1h = []
        df_1h_ohlcv = None
        if ohlcv_1h and len(ohlcv_1h) > 0:
            df_1h_ohlcv = pd.DataFrame(ohlcv_1h, columns=['timestamp','open','high','low','close','volume'])
            df_1h_ohlcv['timestamp'] = pd.to_datetime(df_1h_ohlcv['timestamp'], unit='ms')
            candles_1h = df_1h_ohlcv[['timestamp','open','high','low','close','volume']].tail(24).to_dict('records')

        # ─────────────────────────────────────────────
        # 5️⃣ High / Low 24h
        # ─────────────────────────────────────────────
        df_24h   = df.tail(288)   # 288 x 5m = 24h
        high_24h = float(df_24h['high'].max())
        low_24h  = float(df_24h['low'].min())

        # ─────────────────────────────────────────────
        # 6️⃣ BTC / ETH / BNB تغيرات السوق
        # ─────────────────────────────────────────────
        market_data   = get_market_data(exchange, ttl_hash=get_ttl_hash())
        btc_change_1h = market_data.get('BTC/USDT', 0.0)
        eth_change_1h = market_data.get('ETH/USDT', 0.0)
        bnb_change_1h = market_data.get('BNB/USDT', 0.0)

        # ─────────────────────────────────────────────
        # 7️⃣ Order Book
        # ─────────────────────────────────────────────
        order_book     = {'bids': [], 'asks': []}
        bid_ask_spread = 0.0
        average_spread = 0.001
        try:
            order_book = exchange.fetch_order_book(symbol, limit=20)
            best_bid   = order_book['bids'][0][0] if order_book.get('bids') else latest['close']
            best_ask   = order_book['asks'][0][0] if order_book.get('asks') else latest['close']
            bid_ask_spread = (best_ask - best_bid) / best_bid * 100 if best_bid > 0 else 0.0
            average_spread = bid_ask_spread if bid_ask_spread > 0 else 0.001
        except Exception as e:
            print(f"⚠️ Order book error {symbol}: {e}")

        # ─────────────────────────────────────────────
        # 8️⃣ MTF Analysis
        # ─────────────────────────────────────────────
        try:
            mtf_analysis = calculate_mtf_from_5m_data(df)
        except Exception:
            mtf_analysis = {'trend': 'neutral', 'scores': {}, 'total': 0}

        # ─────────────────────────────────────────────
        # 9️⃣ Market Regime
        # ─────────────────────────────────────────────
        try:
            market_regime = get_market_regime(df)
        except Exception:
            atr_pct       = latest['atr'] / latest['close'] * 100 if latest['close'] > 0 else 0
            market_regime = (
                'high_volatility' if atr_pct > 2.0
                else 'low_volatility' if atr_pct < 0.5
                else 'normal'
            )

        # ─────────────────────────────────────────────
        # 🔟 Flash Crash Protection
        # ─────────────────────────────────────────────
        try:
            flash_crash_protection = check_flash_crash(df)
        except Exception:
            flash_crash_protection = {
                'triggered': latest['price_change'] < -3.0,
                'drop_pct' : latest['price_change']
            }

        # ─────────────────────────────────────────────
        # 1️⃣1️⃣ Time Analysis
        # ─────────────────────────────────────────────
        try:
            time_analysis = get_time_analysis()
        except Exception:
            now           = datetime.now(timezone.utc)
            time_analysis = {
                'hour'       : now.hour,
                'is_weekend' : now.weekday() >= 5,
                'session'    : (
                    'asia'    if 0  <= now.hour < 8
                    else 'europe' if 8  <= now.hour < 14
                    else 'us'
                )
            }

        # ─────────────────────────────────────────────
        # 1️⃣2️⃣ Liquidity Metrics
        # ─────────────────────────────────────────────
        try:
            liquidity_metrics = get_liquidity_metrics(
                exchange, symbol, df_5m=df, order_book=order_book
            )
        except Exception:
            liquidity_metrics = {
                'depth_ratio': 1.0, 'spread_percent': 0.1,
                'bid_depth': 0, 'ask_depth': 0,
                'liquidity_score': 50, 'price_impact': 0.5,
                'volume_consistency': 50
            }

        # ─────────────────────────────────────────────
        # 1️⃣3️⃣ Reversal / Peak / Price Drop
        # ─────────────────────────────────────────────
        try:
            reversal_analysis = analyze_reversal(df, latest['rsi'])
        except Exception:
            reversal_analysis = {'confidence': 0, 'candle_signal': False, 'reasons': []}

        try:
            peak_analysis = analyze_peak(df, latest['rsi'])
        except Exception:
            peak_analysis = {'confidence': 0, 'candle_signal': False, 'reasons': []}

        price_drop = max(0.0, (high_24h - latest['close']) / high_24h * 100) if high_24h > 0 else 0.0

        # ─────────────────────────────────────────────
        # 1️⃣4️⃣ Optimism Penalty
        # ─────────────────────────────────────────────
        opt_penalty = 0.0
        try:
            time_mult = get_time_multiplier()
            if latest['rsi'] > 70 and latest['price_change'] > 2:
                opt_penalty = (latest['rsi'] - 70) * 0.5 * time_mult
        except Exception:
            pass

        # ─────────────────────────────────────────────
        # 1️⃣5️⃣ External Impact
        # ─────────────────────────────────────────────
        external_impact = {'score': 50, 'sentiment': 'Neutral', 'fear_greed_value': 50}
        if external_client:
            try:
                external_impact = external_client.analyze_impact(symbol)
            except Exception as e:
                print(f"⚠️ External impact error: {e}")
        else:
            # الجديد ✅
            try:
                from external_apis import get_global_external_client
                _ec             = get_global_external_client()
                external_impact = _ec.analyze_impact(symbol)
            except Exception as e:
                print(f"⚠️ External direct error: {e}")

        # ─────────────────────────────────────────────
        # 1️⃣6️⃣ Sentiment Data
        # ─────────────────────────────────────────────
        try:
            sentiment_data = get_sentiment_data(
                symbol,
                {'close': latest['close'], 'rsi': latest['rsi']}
            )
        except Exception:
            sentiment_data = {
                'fear_greed_index'   : 50,
                'positive_news_count': 0,
                'negative_news_count': 0,
            }

        # ═════════════════════════════════════════════
        # 1️⃣7️⃣ بناء analysis_dict
        # ═════════════════════════════════════════════
        analysis_dict = {
            'relative_strength_btc'  : latest['price_change'] - btc_change_1h,
            'liquidity_trap'         : (latest['volume_ratio'] > 3.0 and abs(latest['price_change']) < 0.5),
            'liquidity_sweep'        : (latest['low'] <= low_24h * 1.005 and latest['price_change'] > 1.0 and latest['volume_ratio'] > 2.0),
            'candles'     : candles,
            'candles_5m'  : candles_5m,
            'candles_15m' : candles_15m,
            'candles_1h'  : candles_1h,
            'candles_4h'  : ohlcv_4h,
            'candles_1d'  : ohlcv_1d,
            'rsi'             : latest['rsi'],
            'macd'            : latest['macd'],
            'macd_signal'     : latest['macd_signal'],
            'macd_diff'       : latest['macd_diff'],
            'macd_diff_pct'   : latest['macd_diff_pct'],
            'latest'          : latest,
            'volume'          : latest['volume'],
            'volume_sma'      : latest['volume_sma'],
            'volume_ratio'    : latest['volume_ratio'],
            'price_momentum'  : latest['price_change'],
            'close'           : latest['close'],
            'high'            : latest['high'],
            'low'             : latest['low'],
            'mtf'             : mtf_analysis,
            'market_regime'   : market_regime,
            'flash_crash_protection': flash_crash_protection,
            'time_analysis'   : time_analysis,
            'atr'             : latest['atr'],
            'ema_9'           : latest['ema_9'],
            'ema_21'          : latest['ema_21'],
            'ema_crossover'   : latest['ema_crossover'],
            'bid_ask_spread'  : bid_ask_spread,
            'volume_trend'    : latest['volume_trend'],
            'price_change_1h' : latest['price_change_1h'],
            'reversal'        : reversal_analysis,
            'peak'            : peak_analysis,
            'price_drop'      : price_drop,
            'liquidity_metrics': liquidity_metrics,
            **liquidity_metrics,
            'atr_value'            : latest['atr'],
            'optimism_penalty'     : opt_penalty,
            'psychological_analysis': f"Panic:{detect_panic_greed(latest)['panic_score']:.1f}, RSI:{latest['rsi']:.1f}",
            'btc_change_1h'    : btc_change_1h,
            'panic_greed'      : detect_panic_greed(latest),
            'eth_change_1h'    : eth_change_1h,
            'bnb_change_1h'    : bnb_change_1h,
            'high_24h'         : high_24h,
            'low_24h'          : low_24h,
            'is_noise'         : latest['is_noise'],
            'fake_break'       : latest['fake_break'],
            'external_impact'  : external_impact,
            'external_score'   : external_impact.get('score', 50),
            'order_book'       : order_book,
            'average_spread'   : average_spread,
            **sentiment_data,
        }

        # ─────────────────────────────────────────────
        # Fix 2: sentiment.fear_greed
        # ─────────────────────────────────────────────
        fear_greed_value = (
            sentiment_data.get('fear_greed_index')
            or sentiment_data.get('fear_greed')
            or 50
        )

        if fear_greed_value == 50:
            fng_val = external_impact.get('fear_greed_value')
            if fng_val and fng_val != 50:
                fear_greed_value = fng_val
            # ✅ لا نستدعي API جديد - نأخذ من external_impact مباشرة
            # لأنه يستدعي get_market_sentiment_global بالفعل داخل analyze_impact

        analysis_dict['sentiment'] = {'fear_greed': fear_greed_value}

        # ─────────────────────────────────────────────
        # Fix 3: market_intelligence (UPGRADED - uses MarketRegimeDetector)
        # ─────────────────────────────────────────────
        try:
            _regime = market_regime if isinstance(market_regime, dict) else {}
            _regime_name = _regime.get('regime', 'RANGING')
            _advice = _regime.get('trading_advice', {}) if isinstance(_regime.get('trading_advice'), dict) else {}
            
            # تم تحييد صلاحية هذا الموديول في تقييم إيجابية السوق
            # القرار الآن مركزي في meta_buy بناءً على MacroTrendAdvisor فقط
            analysis_dict['market_intelligence'] = {
                'bullish_score': 0, 
                'bearish_score': 0,
                'regime': _regime_name,
                'trend': _regime.get('trend_strength', 'neutral'),
                'adx': _regime.get('adx', 20),
                'can_trade': _advice.get('can_trade', True),
                'position_size_mult': _advice.get('position_size', 1.0),
            }
        except Exception:
            analysis_dict['market_intelligence'] = {
                'bullish_score': max(0, min(100, 50 + btc_change_1h * 10)),
                'bearish_score': max(0, min(100, 50 - btc_change_1h * 10)),
            }

        # ─────────────────────────────────────────────
        # Fix 4: external_signal
        # ─────────────────────────────────────────────
        ext_score = external_impact.get('score', 50)
        analysis_dict['external_signal'] = {
            'bullish': 1 if ext_score > 65 else 0,
            'bearish': 1 if ext_score < 35 else 0,
        }

        # ─────────────────────────────────────────────
        # Fix 5: news
        # ─────────────────────────────────────────────
        analysis_dict['news'] = {
            'positive': sentiment_data.get('positive_news_count', 0),
            'negative': sentiment_data.get('negative_news_count', 0),
        }

        # ═════════════════════════════════════════════
        # الأعمدة الإضافية
        # ═════════════════════════════════════════════
        bids_volume  = sum(float(l[1]) for l in order_book.get('bids', [])[:10])
        asks_volume  = sum(float(l[1]) for l in order_book.get('asks', [])[:10])
        total_vol_ob = bids_volume + asks_volume

        analysis_dict['order_book_imbalance'] = (
            (bids_volume - asks_volume) / max(total_vol_ob, 1) if total_vol_ob > 0 else 0
        )
        analysis_dict['spread_volatility'] = (
            abs(bid_ask_spread - average_spread) / max(average_spread, 0.0001)
        )
        analysis_dict['depth_at_1pct'] = sum(
            float(l[1])
            for l in order_book.get('bids', []) + order_book.get('asks', [])
            if abs(float(l[0]) - latest['close']) / latest['close'] <= 0.01
        )
        analysis_dict['market_impact_score'] = min(latest['volume_ratio'] / 10, 1.0)
        analysis_dict['liquidity_trends'] = (
            1  if latest['volume_ratio'] > 1.5 and analysis_dict['spread_volatility'] < 0.5
            else -1 if latest['volume_ratio'] < 0.7 or analysis_dict['spread_volatility'] > 1.0
            else 0
        )

        # Risk
        analysis_dict['volatility_risk_score']  = (latest['atr'] / latest['close']) * 100 if latest['close'] > 0 else 0
        analysis_dict['correlation_risk']        = abs(btc_change_1h) / 5.0
        analysis_dict['gap_risk_score']          = abs(latest['high'] - latest['low']) / latest['close'] * 100 if latest['close'] > 0 else 0
        analysis_dict['black_swan_probability']  = 1.0 if abs(latest['price_change_1h']) > 5 else abs(latest['price_change_1h']) / 5.0
        analysis_dict['behavioral_risk']         = max(0, 1.0 - latest['volume_ratio'])
        analysis_dict['systemic_risk']           = abs(eth_change_1h) / 10.0

        # Exit
        analysis_dict['profit_optimization_score'] = max(0, (latest['rsi'] - 50) / 30)
        analysis_dict['time_decay_signals']         = 0.3 + (latest['rsi'] / 200)
        analysis_dict['opportunity_cost_exits']     = abs(min(0, latest['macd_diff'])) * 100
        analysis_dict['market_condition_exits']     = btc_change_1h / 10.0 if btc_change_1h < 0 else 0.0

        # Pattern
        analysis_dict['harmonic_patterns_score'] = abs(latest['price_change_1h']) / 2.0
        analysis_dict['elliott_wave_signals']    = float(latest['ema_crossover'])
        analysis_dict['fractal_patterns']        = latest['volume_ratio'] / 3.0
        analysis_dict['cycle_patterns']          = abs(50 - latest['rsi']) / 50.0
        analysis_dict['momentum_patterns']       = abs(latest['price_change']) / 3.0

        # Smart Money
        analysis_dict['whale_wallet_changes']       = latest['volume_ratio'] / 2.0
        analysis_dict['institutional_accumulation'] = (
            1.0 if bid_ask_spread < 0.05
            else 0.5 if bid_ask_spread < 0.1
            else 0.0
        )
        analysis_dict['smart_money_ratio']    = min(latest['volume_ratio'] / 2.0, 1.0)
        analysis_dict['exchange_whale_flows'] = 1.0 if latest['volume_ratio'] < 0.3 else 0.0

        # Anomaly
        analysis_dict['statistical_outliers'] = abs(latest['close'] - latest['ema_21']) / latest['close'] * 100
        analysis_dict['pattern_anomalies']    = abs(latest['macd_diff'] * latest['price_change'])
        analysis_dict['behavioral_anomalies'] = max(0, latest['volume_ratio'] - 2.0)
        analysis_dict['volume_anomalies']     = abs(1.0 - latest['volume_ratio'])

        # Chart pattern features
        volume_signal = min(max((latest['volume_ratio'] - 1.0) / 2.0, 0.0), 1.0)
        macd_signal   = min(abs(latest['macd_diff_pct']) / 0.5, 1.0)
        temporal_sig  = min(abs(latest['price_change_1h']) / 5.0, 1.0)
        analysis_dict['attention_mechanism_score'] = volume_signal
        analysis_dict['multi_scale_features']      = macd_signal
        analysis_dict['temporal_features']         = temporal_sig

        rsi_buy_signal  = max(0.0, min((45.0 - latest['rsi']) / 25.0, 1.0))
        rsi_sell_signal = max(0.0, min((latest['rsi'] - 55.0) / 25.0, 1.0))
        macd_buy_signal = max(0.0, min(latest['macd_diff_pct'] / 0.5, 1.0))
        macd_sell_signal = max(0.0, min(-latest['macd_diff_pct'] / 0.5, 1.0))
        momentum_buy_signal = max(0.0, min(latest['price_change_1h'] / 5.0, 1.0))
        momentum_sell_signal = max(0.0, min(-latest['price_change_1h'] / 5.0, 1.0))
        ema_buy_signal = 1.0 if latest['ema_crossover'] > 0 else 0.0
        ema_sell_signal = 1.0 if latest['ema_crossover'] < 0 else 0.0

        analysis_dict['chart_cnn_buy_score'] = round(min(100.0, (
            volume_signal * 25
            + rsi_buy_signal * 25
            + macd_buy_signal * 20
            + momentum_buy_signal * 20
            + ema_buy_signal * 10
        )), 1)
        analysis_dict['chart_cnn_sell_score'] = round(min(100.0, (
            volume_signal * 25
            + rsi_sell_signal * 25
            + macd_sell_signal * 20
            + momentum_sell_signal * 20
            + ema_sell_signal * 10
        )), 1)
        analysis_dict['chart_cnn_score'] = max(
            analysis_dict['chart_cnn_buy_score'],
            analysis_dict['chart_cnn_sell_score']
        )

        # Volume
        analysis_dict['volume_trend_strength'] = latest['volume_trend']
        analysis_dict['volume_volatility']     = (
            abs(latest['volume'] - latest['volume_sma'])
            / max(latest['volume_sma'], 1)
        )
        analysis_dict['volume_momentum']    = min(latest['volume_ratio'] / 2.0, 1.0)
        analysis_dict['volume_seasonality'] = 0.5
        analysis_dict['volume_correlation'] = min(
            abs(latest['price_change_1h'])
            / max(latest['volume_ratio'], 0.1)
            / 10.0,
            1.0
        )

        # Meta
        analysis_dict['dynamic_consultant_weights'] = 0.7
        analysis_dict['uncertainty_quantification'] = abs(50 - latest['rsi']) / 50.0
        analysis_dict['context_aware_score']        = 1.0 - abs(btc_change_1h) / 10.0

        # Whale Confidence
        v_ratio      = latest['volume_ratio']
        ob_imbalance = analysis_dict.get('order_book_imbalance', 0)
        price_change = latest['price_change']
        rsi_val      = latest['rsi']

        w_base   = (price_change * 10) if abs(price_change) > 0.1 else 0
        w_volume = (v_ratio - 1.0) * 5
        w_rsi    = (rsi_val - 50) / 2
        w_ob     = (ob_imbalance * 10) if abs(ob_imbalance) > 0.1 else 0

        analysis_dict['whale_confidence'] = round(
            max(-25, min(25, w_base + w_volume + w_rsi + w_ob)), 2
        )

        elapsed = time.time() - analysis_start
        #print(f"✅ Analysis done {symbol} in {elapsed:.2f}s")

        return analysis_dict

    except Exception as e:
        print(f"❌ Analysis error {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════
def calculate_mtf_from_5m_data(df):
    try:
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}

        df_5m           = df.tail(20).copy()
        df_5m['sma_20'] = df_5m['close'].rolling(window=20).mean()
        df_5m['sma_50'] = df_5m['close'].rolling(window=min(50, len(df_5m))).mean()
        latest_5m       = df_5m.iloc[-1]

        if   latest_5m['close'] > latest_5m['sma_20'] > latest_5m['sma_50']: scores['bullish'] += 1
        elif latest_5m['close'] < latest_5m['sma_20'] < latest_5m['sma_50']: scores['bearish'] += 1
        else:                                                                   scores['neutral'] += 1

        if len(df) >= 20:
            df_15m            = df.iloc[::3].tail(20).copy()
            df_15m['sma_20']  = df_15m['close'].rolling(window=20).mean()
            df_15m['sma_50']  = df_15m['close'].rolling(window=min(50, len(df_15m))).mean()
            if len(df_15m) > 0:
                latest_15m = df_15m.iloc[-1]
                if   latest_15m['close'] > latest_15m['sma_20'] > latest_15m['sma_50']: scores['bullish'] += 1
                elif latest_15m['close'] < latest_15m['sma_20'] < latest_15m['sma_50']: scores['bearish'] += 1
                else:                                                                     scores['neutral'] += 1

        if len(df) >= 60:
            df_1h            = df.iloc[::12].tail(20).copy()
            df_1h['sma_20']  = df_1h['close'].rolling(window=20).mean()
            df_1h['sma_50']  = df_1h['close'].rolling(window=min(50, len(df_1h))).mean()
            if len(df_1h) > 0:
                latest_1h = df_1h.iloc[-1]
                if   latest_1h['close'] > latest_1h['sma_20'] > latest_1h['sma_50']: scores['bullish'] += 1
                elif latest_1h['close'] < latest_1h['sma_20'] < latest_1h['sma_50']: scores['bearish'] += 1
                else:                                                                  scores['neutral'] += 1

        trend = max(scores, key=scores.get)
        return {'trend': trend, 'scores': scores, 'total': scores[trend]}

    except Exception as e:
        return {'trend': 'neutral', 'scores': {'bullish': 0, 'bearish': 0, 'neutral': 3}, 'total': 3}


# ═══════════════════════════════════════════════════════════════
def get_liquidity_metrics(exchange, symbol, df_5m=None, order_book=None):
    try:
        if not order_book:
            order_book = exchange.fetch_order_book(symbol, limit=20)

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


# ═══════════════════════════════════════════════════════════════
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
