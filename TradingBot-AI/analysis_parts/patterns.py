"""Split-out analysis helpers."""

import numpy as np
from datetime import datetime, timezone


def analyze_market_structure(df):
    """Analyze market structure for bullish/bearish patterns"""
    try:
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
    except Exception as e:
        return {'structure': 'error', 'score': 0, 'reason': str(e)}


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


def analyze_reversal(df, rsi):
    from app_config.config import BOTTOM_BOUNCE_THRESHOLD, REVERSAL_CANDLES, MIN_BUY_CONFIDENCE

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
    from app_config.config import PEAK_DROP_THRESHOLD, REVERSAL_CANDLES, MIN_SELL_CONFIDENCE, MIN_BUY_CONFIDENCE

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
