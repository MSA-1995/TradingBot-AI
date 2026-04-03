"""
📊 Technical Analysis Module
Handles RSI, MACD, Volume, Momentum calculations
"""

import pandas as pd
import ta
from datetime import datetime
from functools import lru_cache
import time
from market_intelligence import get_market_regime, check_flash_crash, get_time_analysis, get_time_multiplier

# [تحسين الذاكرة] تم حذف المتغير العام _market_cache

@lru_cache(maxsize=1)
def get_market_data(exchange, ttl_hash=None):
    """[تحسين الذاكرة] جلب بيانات السوق مع تخزين مؤقت آمن باستخدام lru_cache"""
    del ttl_hash
    new_market_data = {}
    for market_coin in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
        try:
            m_ohlcv = exchange.fetch_ohlcv(market_coin, '5m', limit=13)
            if len(m_ohlcv) >= 13:
                m_current = m_ohlcv[-1][4]
                m_1h_ago = m_ohlcv[-13][4]
                change = ((m_current - m_1h_ago) / m_1h_ago) * 100
                new_market_data[market_coin] = change
            else:
                new_market_data[market_coin] = 0
        except:
            new_market_data[market_coin] = 0
    return new_market_data

def get_ttl_hash(seconds=20):
    """[تحسين الذاكرة] إنشاء hash يعتمد على الوقت لتحديث الكاش"""
    return round(time.time() / seconds)

def analyze_market_structure(df):
    """
    تحليل هيكل السوق: Higher Highs / Lower Lows
    Returns: dict with structure analysis
    """
    if df is None or len(df) < 20:
        return {'structure': 'unknown', 'score': 0, 'reason': 'Not enough data'}
    
    closes = df['close'].tolist()
    highs = df['high'].tolist()
    lows = df['low'].tolist()
    
    swing_points = []
    window = 3
    
    for i in range(window, len(closes) - window):
        is_high = all(highs[i] >= highs[j] for j in range(i - window, i + window + 1) if j != i)
        is_low = all(lows[i] <= lows[j] for j in range(i - window, i + window + 1) if j != i)
        
        if is_high:
            swing_points.append(('H', i, highs[i]))
        elif is_low:
            swing_points.append(('L', i, lows[i]))
    
    if len(swing_points) < 3:
        return {'structure': 'unclear', 'score': 0, 'reason': 'No clear swings'}
    
    recent_swings = swing_points[-6:]
    
    highs_list = [s for s in recent_swings if s[0] == 'H']
    lows_list = [s for s in recent_swings if s[0] == 'L']
    
    structure = 'neutral'
    score = 0
    reason = ''
    
    if len(lows_list) >= 2:
        last_low = lows_list[-1][2]
        prev_low = lows_list[-2][2]
        
        if last_low > prev_low * 1.002:
            if len(highs_list) >= 2 and highs_list[-1][2] > highs_list[-2][2] * 1.002:
                structure = 'higher_highs_higher_lows'
                score = 20
                reason = 'HH + HL (Bullish Structure)'
            else:
                structure = 'higher_lows'
                score = 10
                reason = 'HL (Potential Reversal)'
        elif last_low < prev_low * 0.998:
            if len(highs_list) >= 2 and highs_list[-1][2] < highs_list[-2][2] * 0.998:
                structure = 'lower_highs_lower_lows'
                score = -20
                reason = 'LH + LL (Bearish Structure)'
            else:
                structure = 'lower_lows'
                score = -10
                reason = 'LL (Downtrend)'
        else:
            structure = 'ranging'
            score = 5
            reason = 'Sideways / Ranging'
    elif len(highs_list) >= 2:
        if highs_list[-1][2] > highs_list[-2][2] * 1.002:
            structure = 'higher_highs'
            score = 10
            reason = 'HH (Uptrend)'
        else:
            structure = 'lower_highs'
            score = -10
            reason = 'LH (Weakening)'
    
    return {'structure': structure, 'score': score, 'reason': reason}

def analyze_support_resistance(df):
    """
    تحليل الدعم والمقاومة من القمم والقيعان السابقة
    Returns: dict with S/R analysis
    """
    if df is None or len(df) < 30:
        return {'at_support': False, 'at_resistance': False, 'score': 0, 'reason': 'Not enough data'}
    
    current_price = df.iloc[-1]['close']
    
    lows = df['low'].tail(60).tolist()
    highs = df['high'].tail(60).tolist()
    
    support_levels = []
    resistance_levels = []
    
    for i in range(2, len(lows) - 2):
        if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1] and lows[i] <= lows[i+2]:
            support_levels.append(lows[i])
    
    for i in range(2, len(highs) - 2):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]:
            resistance_levels.append(highs[i])
    
    tolerance = 0.008
    
    at_support = False
    at_resistance = False
    score = 0
    reason = ''
    
    for sl in support_levels:
        if abs(current_price - sl) / sl < tolerance:
            at_support = True
            score = 15
            reason = f'Near Support ({sl:.4f})'
            break
    
    for rl in resistance_levels:
        if abs(current_price - rl) / rl < tolerance:
            at_resistance = True
            score = -15
            reason = f'Near Resistance ({rl:.4f})'
            break
    
    if not at_support and not at_resistance:
        nearest_support = max([s for s in support_levels if s < current_price], default=0)
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=0)
        
        if nearest_support > 0:
            dist_to_support = (current_price - nearest_support) / nearest_support * 100
            if dist_to_support < 2:
                score = 5
                reason = f'Approaching Support ({dist_to_support:.1f}%)'
        
        if nearest_resistance > 0:
            dist_to_res = (nearest_resistance - current_price) / current_price * 100
            if dist_to_res < 2:
                score = -5
                reason = f'Approaching Resistance ({dist_to_res:.1f}%)'
    
    return {'at_support': at_support, 'at_resistance': at_resistance, 'score': score, 'reason': reason}

def analyze_mtf_confirmation(df):
    """
    تأكيد متعدد الفريمات: 5m + 15m + 1h
    Returns: dict with MTF confirmation
    """
    if df is None or len(df) < 60:
        return {'confirmed': False, 'score': 0, 'reason': 'Not enough data'}
    
    scores_5m = 0
    scores_15m = 0
    scores_1h = 0
    
    closes = df['close'].tolist()
    rsi_col = df.get('rsi')
    
    if len(closes) >= 5:
        if closes[-1] > closes[-3]:
            scores_5m += 1
        if rsi_col is not None and len(rsi_col) >= 5:
            if rsi_col.iloc[-1] < 40:
                scores_5m += 1
            elif rsi_col.iloc[-1] < 50:
                scores_5m += 0.5
    
    if len(closes) >= 15:
        closes_15m = closes[-15:]
        if closes[-1] > sum(closes_15m[:5]) / 5:
            scores_15m += 1
        if rsi_col is not None and len(rsi_col) >= 15:
            if rsi_col.iloc[-1] < 35:
                scores_15m += 1
            elif rsi_col.iloc[-1] < 45:
                scores_15m += 0.5
    
    if len(closes) >= 60:
        closes_1h = closes[-60:]
        if closes[-1] > sum(closes_1h[:12]) / 12:
            scores_1h += 1
        if rsi_col is not None and len(rsi_col) >= 60:
            if rsi_col.iloc[-1] < 30:
                scores_1h += 1
            elif rsi_col.iloc[-1] < 40:
                scores_1h += 0.5
    
    total_frames = 3
    confirmed_frames = 0
    if scores_5m >= 1: confirmed_frames += 1
    if scores_15m >= 1: confirmed_frames += 1
    if scores_1h >= 1: confirmed_frames += 1
    
    mtf_score = 0
    confirmed = False
    reason = ''
    
    if confirmed_frames >= 2:
        mtf_score = 20
        confirmed = True
        reason = f'MTF Confirmed ({confirmed_frames}/{total_frames} frames)'
    elif confirmed_frames == 1:
        mtf_score = 10
        reason = f'Partial MTF ({confirmed_frames}/{total_frames} frames)'
    else:
        mtf_score = 0
        reason = 'No MTF Confirmation'
    
    return {'confirmed': confirmed, 'score': mtf_score, 'reason': reason, 'frames': confirmed_frames}

def analyze_reversal(df, rsi):
    """
    تحليل الارتداد من القاع - نظام النقاط الذكي المحسّن (المجموع = 110 نقطة):
    - الشموع والأنماط: 30 نقطة (الأهم)
    - RSI + MACD: 25 نقطة (أقوى)
    - Market Structure: 15 نقطة (مساعد)
    - Support/Resistance: 15 نقطة
    - MTF Confirmation: 10 نقاط
    - Volume + Divergence: 15 نقطة (مهم)
    """
    from config import BOTTOM_BOUNCE_THRESHOLD, REVERSAL_CANDLES, MIN_CONFIDENCE

    base_result = {
        'confidence': 0,
        'candle_signal': False,
        'reasons': [],
        'bounce_percent': 0,
        'is_reversing': False,
        'trend': 'neutral',
        'momentum': 0,
        'score_breakdown': {}
    }

    if df is None or len(df) < 8:
        return base_result

    if rsi > 80:
        base_result['reasons'].append(f'RSI Overbought ({rsi:.0f})')
        return base_result

    try:
        total_score = 0
        reasons = []
        score_breakdown = {}
        
        # --- 1. الشموع والأنماط - 40 نقطة (أقوى للشراء السريع) ---
        candle_signal = False
        pattern_score = 0
        pattern_name = ""
        pattern_found_idx = -1
        
        for i in range(2, min(8, len(df))):
            pattern_candle = df.iloc[-i]
            
            body = abs(pattern_candle['close'] - pattern_candle['open'])
            if body == 0:
                continue
            
            candle_range = pattern_candle['high'] - pattern_candle['low']
            if candle_range == 0:
                continue
            
            upper_shadow = pattern_candle['high'] - max(pattern_candle['close'], pattern_candle['open'])
            lower_shadow = min(pattern_candle['close'], pattern_candle['open']) - pattern_candle['low']
            
            is_green = pattern_candle['close'] > pattern_candle['open']
            is_red = pattern_candle['close'] < pattern_candle['open']
            
            is_hammer = (lower_shadow >= 2.0 * body and body < candle_range * 0.3)
            
            if is_hammer:
                candle_signal = True
                pattern_score = 40
                pattern_name = "Hammer"
                pattern_found_idx = i
                reasons.append(f"{pattern_name} (+40)")
                break
            
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_red = prev_candle['close'] < prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                
                is_bullish_engulfing = (
                    prev_is_red and is_green and
                    pattern_candle['close'] > prev_candle['open'] and
                    pattern_candle['open'] < prev_candle['close'] and
                    body > prev_body * 1.2
                )
                
                if is_bullish_engulfing:
                    candle_signal = True
                    pattern_score = 40
                    pattern_name = "Bullish Engulfing"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+40)")
                    break
            
            if i + 2 < len(df) and i <= 3:
                c1 = df.iloc[-i-2]
                c2 = df.iloc[-i-1]
                c3 = pattern_candle
                
                c1_body = abs(c1['close'] - c1['open'])
                c2_body = abs(c2['close'] - c2['open'])
                c3_body = abs(c3['close'] - c3['open'])
                
                c1_range = c1['high'] - c1['low']
                c2_range = c2['high'] - c2['low']
                c3_range = c3['high'] - c3['low']
                
                is_morning_star = (
                    c1['close'] < c1['open'] and c1_body > c1_range * 0.5 and
                    c2_body < c2_range * 0.3 and
                    c3['close'] > c3['open'] and c3_body > c3_range * 0.5 and
                    c3['close'] > c1['open']
                )
                
                if is_morning_star:
                    candle_signal = True
                    pattern_score = 40
                    pattern_name = "Morning Star"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+40)")
                    break
            
            if i + 2 < len(df) and i <= 3:
                c1 = df.iloc[-i-2]
                c2 = df.iloc[-i-1]
                c3 = pattern_candle
                
                c1_body = abs(c1['close'] - c1['open'])
                c2_body = abs(c2['close'] - c2['open'])
                c3_body = abs(c3['close'] - c3['open'])
                
                is_three_soldiers = (
                    c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
                    c1_body > 0 and c2_body > 0 and c3_body > 0 and
                    c2['close'] > c1['close'] and c3['close'] > c2['close']
                )
                
                if is_three_soldiers:
                    candle_signal = True
                    pattern_score = 40
                    pattern_name = "Three White Soldiers"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+40)")
                    break
            
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_red = prev_candle['close'] < prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                prev_mid = (prev_candle['open'] + prev_candle['close']) / 2
                
                is_piercing = (
                    prev_is_red and is_green and
                    pattern_candle['open'] < prev_candle['close'] and
                    pattern_candle['close'] > prev_mid and
                    body > prev_body * 0.5
                )
                
                if is_piercing:
                    candle_signal = True
                    pattern_score = 40
                    pattern_name = "Piercing Line"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+40)")
                    break
        
        total_score += pattern_score
        score_breakdown['pattern'] = pattern_score
        
        # --- 2. RSI + MACD - 25 نقطة (محسّن) ---
        rsi_score = 0
        if rsi < 25:
            rsi_score = 15
            reasons.append(f"RSI Very Low ({rsi:.0f}) (+15)")
        elif rsi < 30:
            rsi_score = 12
            reasons.append(f"RSI Oversold ({rsi:.0f}) (+12)")
        elif rsi < 35:
            rsi_score = 9
            reasons.append(f"RSI Low ({rsi:.0f}) (+9)")
        elif rsi < 40:
            rsi_score = 6
            reasons.append(f"RSI OK ({rsi:.0f}) (+6)")
        else:
            rsi_score = 0
        
        macd_score = 0
        if 'macd_histogram' in df.columns and len(df) >= 5:
            hist_values = df['macd_histogram'].tail(5).tolist()
            if len(hist_values) >= 3:
                # تحسين: أي تحسن في MACD يُحتسب
                if hist_values[-1] < 0 and hist_values[-3] < 0:
                    if hist_values[-1] > hist_values[-3]:  # أي تحسن
                        improvement_ratio = abs(hist_values[-1] - hist_values[-3]) / abs(hist_values[-3]) if hist_values[-3] != 0 else 0
                        if improvement_ratio > 0.3:
                            macd_score = 10
                            reasons.append("MACD Strong Recovery (+10)")
                        else:
                            macd_score = 6
                            reasons.append("MACD Improving (+6)")
        
        total_score += rsi_score + macd_score
        score_breakdown['rsi_macd'] = rsi_score + macd_score
        
        # --- 3. Market Structure - 15 نقطة (مساعد) ---
        ms = analyze_market_structure(df)
        ms_score = max(0, int(ms['score'] * 0.75))  # تقليل الوزن من 20 إلى 15
        if ms['structure'] in ('lower_highs_lower_lows', 'lower_lows'):
            ms_score = 0
        total_score += ms_score
        score_breakdown['market_structure'] = ms_score
        if ms['reason']:
            reasons.append(f"🏗️ {ms['reason']} ({ms_score:+d})")
        
        # --- 4. Support/Resistance - 15 نقطة ---
        sr = analyze_support_resistance(df)
        sr_score = max(0, sr['score'])
        if sr['at_resistance']:
            sr_score = 0
        total_score += sr_score
        score_breakdown['support_resistance'] = sr_score
        if sr['reason']:
            reasons.append(f"📐 {sr['reason']} ({sr_score:+d})")
        
        # --- 5. MTF Confirmation - 10 نقطة ---
        mtf = analyze_mtf_confirmation(df)
        mtf_score = min(10, mtf['score'])
        total_score += mtf_score
        score_breakdown['mtf_confirmation'] = mtf_score
        if mtf['reason']:
            reasons.append(f"⏱️ {mtf['reason']} ({mtf_score:+d})")
        
        # --- 6. Volume + Divergence - 15 نقطة (محسّن) ---
        vol_score = 0
        if len(df) >= 2:
            current_vol = df.iloc[-1].get('volume_ratio', 1)
            if current_vol > 2.0:
                vol_score = 8
                reasons.append(f"Vol Very High {current_vol:.1f}x (+8)")
            elif current_vol > 1.5:
                vol_score = 6
                reasons.append(f"Vol High {current_vol:.1f}x (+6)")
            elif current_vol > 1.0:
                vol_score = 3
                reasons.append(f"Vol Up {current_vol:.1f}x (+3)")
        
        div_score = 0
        if len(df) >= 20:
            recent_lows = []
            recent_rsis = []
            for i in range(-20, -1):
                if i >= -len(df):
                    candle = df.iloc[i]
                    recent_lows.append(candle['low'])
                    if 'rsi' in df.columns:
                        recent_rsis.append(candle['rsi'])
            
            if len(recent_lows) >= 10 and len(recent_rsis) >= 10:
                price_window = recent_lows[-10:]
                rsi_window = recent_rsis[-10:]
                
                first_low = min(price_window[:5])
                second_low = min(price_window[5:])
                
                first_idx = price_window[:5].index(first_low)
                second_idx = 5 + price_window[5:].index(second_low)
                
                first_rsi = rsi_window[first_idx]
                second_rsi = rsi_window[second_idx]
                
                if second_low < first_low and second_rsi > first_rsi:
                    rsi_diff = second_rsi - first_rsi
                    if rsi_diff > 5:
                        div_score = 7
                        reasons.append(f"Strong Bullish Divergence (+7)")
                    elif rsi_diff > 2:
                        div_score = 4
                        reasons.append(f"Bullish Divergence (+4)")
        
        total_score += vol_score + div_score
        score_breakdown['volume_divergence'] = vol_score + div_score
        
        # --- 7. Bottom Confirmation - 10 نقطة (متوسط) ---
        high_20 = df['high'].tail(20).max()
        current_price_now = df.iloc[-1]['close']
        drop_from_high = ((high_20 - current_price_now) / high_20) * 100 if high_20 > 0 else 0
        if drop_from_high >= 2.0:   # متوسط: 2% بدل 3%
            total_score += 10
            score_breakdown['bottom_confirm'] = 10
            reasons.append(f"Bottom Confirmed (-{drop_from_high:.1f}% from high) (+10)")
        elif drop_from_high < 0.5:  # خصم فقط إذا قريب جداً من القمة
            total_score -= 10
            score_breakdown['bottom_confirm'] = -10
            reasons.append(f"Near High (-{drop_from_high:.1f}%) (-10)")
        else:
            score_breakdown['bottom_confirm'] = 0
        
        # --- Trap Detection
        n = min(REVERSAL_CANDLES, len(df))
        low_n = df['low'].tail(n).min()
        current_price = df.iloc[-1]['close']
        bounce_percent = ((current_price - low_n) / low_n) * 100 if low_n > 0 else 0
        
        # --- Trap Detection (فحص آخر 3 شموع للفخاخ)
        trap_is_filter = False
        if len(df) >= 20:
            avg_volume = df['volume'].tail(20).mean()
            for check_idx in range(1, min(4, len(df) + 1)):
                check_candle = df.iloc[-check_idx]
                check_volume = check_candle['volume']
                if avg_volume > 0 and check_volume > avg_volume * 3.5:  # متوسط: 3.5x بدل 3x
                    candle_body = abs(check_candle['close'] - check_candle['open'])
                    candle_range = check_candle['high'] - check_candle['low']
                    if candle_range > 0 and candle_body > 0:
                        upper_shadow = check_candle['high'] - max(check_candle['close'], check_candle['open'])
                        # فخ صعود وهمي: ظل علوي كبير مع حجم عالي
                        if upper_shadow > candle_body * 3.5:  # متوسط: 3.5x
                            trap_is_filter = True
                            reasons.append(f"⚠️ Fake Pump Trap (Candle-{check_idx})")
                            break

        # =========================================================
        # 🎯 القرار النهائي (المجموع = 110 نقطة)
        # =========================================================
        confidence_percent = min(total_score, 110)
        is_candle_signal = confidence_percent >= MIN_CONFIDENCE
        
        if trap_is_filter and is_candle_signal:
            is_candle_signal = False
            reasons.append("🚫 Signal Blocked by Trap")
        
        if total_score >= MIN_CONFIDENCE + 10:
            reasons.append(f"✅ STRONG ({total_score}/110)")
        elif total_score >= MIN_CONFIDENCE:
            reasons.append(f"✅ SIGNAL ({total_score}/110)")
        elif total_score >= 40:
            reasons.append(f"⏳ WEAK ({total_score}/110)")
        else:
            reasons.append(f"❌ NO SIGNAL ({total_score}/110)")
        
        base_result['is_reversing'] = bounce_percent >= BOTTOM_BOUNCE_THRESHOLD
        
        base_result.update({
            'confidence': confidence_percent,
            'candle_signal': is_candle_signal,
            'reasons': reasons,
            'bounce_percent': round(bounce_percent, 3),
            'score_breakdown': score_breakdown
        })
        return base_result

    except Exception as e:
        base_result['reasons'].append(f'Error: {e}')
        return base_result


def analyze_peak(df, rsi):
    """
    تحليل الانعكاس من القمة - نظام النقاط الذكي المحسّن (المجموع = 110 نقطة):
    - الشموع والأنماط: 30 نقطة (الأهم)
    - RSI + MACD: 25 نقطة (أقوى)
    - Market Structure: 15 نقطة (مساعد)
    - Support/Resistance: 15 نقطة
    - MTF Confirmation: 10 نقاط
    - Volume + Divergence: 15 نقطة (مهم)
    """
    from config import PEAK_DROP_THRESHOLD, REVERSAL_CANDLES, MIN_SELL_CONFIDENCE, MIN_CONFIDENCE

    base_result = {
        'confidence': 0,
        'candle_signal': False,
        'reasons': [],
        'drop_percent': 0,
        'is_peaking': False,
        'trend': 'neutral',
        'momentum': 0,
        'score_breakdown': {}
    }

    if df is None or len(df) < 8:
        return base_result

    try:
        total_score = 0
        reasons = []
        score_breakdown = {}
        
        # --- 1. الشموع والأنماط - 35 نقطة (متوازن مع تأكيد) ---
        candle_signal = False
        pattern_score = 0
        pattern_name = ""
        pattern_found_idx = -1
        
        n = min(REVERSAL_CANDLES, len(df))
        
        for i in range(2, min(n, len(df))):
            pattern_candle = df.iloc[-i]
            
            body = abs(pattern_candle['close'] - pattern_candle['open'])
            if body == 0:
                continue
            
            candle_range = pattern_candle['high'] - pattern_candle['low']
            if candle_range == 0:
                continue
            
            upper_shadow = pattern_candle['high'] - max(pattern_candle['close'], pattern_candle['open'])
            lower_shadow = min(pattern_candle['close'], pattern_candle['open']) - pattern_candle['low']
            
            is_green = pattern_candle['close'] > pattern_candle['open']
            is_red = pattern_candle['close'] < pattern_candle['open']
            
            is_shooting_star = (upper_shadow >= 2.0 * body and body < candle_range * 0.3 and is_red)
            
            if is_shooting_star:
                candle_signal = True
                pattern_score = 35
                pattern_name = "Shooting Star"
                pattern_found_idx = i
                reasons.append(f"{pattern_name} (+35)")
                break
            
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_green = prev_candle['close'] > prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                
                is_bearish_engulfing = (
                    prev_is_green and is_red and
                    pattern_candle['open'] > prev_candle['close'] and
                    pattern_candle['close'] < prev_candle['open'] and
                    body > prev_body * 1.2
                )
                
                if is_bearish_engulfing:
                    candle_signal = True
                    pattern_score = 35
                    pattern_name = "Bearish Engulfing"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+35)")
                    break
            
            if i + 2 < len(df) and i <= 3:
                c1 = df.iloc[-i-2]
                c2 = df.iloc[-i-1]
                c3 = pattern_candle
                
                c1_body = abs(c1['close'] - c1['open'])
                c2_body = abs(c2['close'] - c2['open'])
                c3_body = abs(c3['close'] - c3['open'])
                
                c1_range = c1['high'] - c1['low']
                c2_range = c2['high'] - c2['low']
                c3_range = c3['high'] - c3['low']
                
                is_evening_star = (
                    c1['close'] > c1['open'] and c1_body > c1_range * 0.5 and
                    c2_body < c2_range * 0.3 and
                    c3['close'] < c3['open'] and c3_body > c3_range * 0.5 and
                    c3['close'] < c1['open']
                )
                
                if is_evening_star:
                    candle_signal = True
                    pattern_score = 35
                    pattern_name = "Evening Star"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+35)")
                    break
            
            if i + 2 < len(df) and i <= 3:
                c1 = df.iloc[-i-2]
                c2 = df.iloc[-i-1]
                c3 = pattern_candle
                
                c1_body = abs(c1['close'] - c1['open'])
                c2_body = abs(c2['close'] - c2['open'])
                c3_body = abs(c3['close'] - c3['open'])
                
                is_three_crows = (
                    c1['close'] < c1['open'] and c2['close'] < c2['open'] and c3['close'] < c3['open'] and
                    c1_body > 0 and c2_body > 0 and c3_body > 0 and
                    c2['close'] < c1['close'] and c3['close'] < c2['close']
                )
                
                if is_three_crows:
                    candle_signal = True
                    pattern_score = 35
                    pattern_name = "Three Black Crows"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+35)")
                    break
            
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_green = prev_candle['close'] > prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                prev_mid = (prev_candle['open'] + prev_candle['close']) / 2
                
                is_dark_cloud = (
                    prev_is_green and is_red and
                    pattern_candle['open'] > prev_candle['close'] and
                    pattern_candle['close'] < prev_mid and
                    body > prev_body * 0.5
                )
                
                if is_dark_cloud:
                    candle_signal = True
                    pattern_score = 35
                    pattern_name = "Dark Cloud Cover"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+35)")
                    break
        
        total_score += pattern_score
        score_breakdown['pattern'] = pattern_score
        
        # --- 2. RSI + MACD - 25 نقطة (محسّن للسرعة) ---
        rsi_score = 0
        if rsi > 68:  # متوازن: مو صارم ومو متساهل
            rsi_score = 15
            reasons.append(f"RSI Very High ({rsi:.0f}) (+15)")
        elif rsi > 63:
            rsi_score = 12
            reasons.append(f"RSI Overbought ({rsi:.0f}) (+12)")
        elif rsi > 58:
            rsi_score = 9
            reasons.append(f"RSI High ({rsi:.0f}) (+9)")
        elif rsi > 53:
            rsi_score = 6
            reasons.append(f"RSI Elevated ({rsi:.0f}) (+6)")
        else:
            rsi_score = 0
        
        macd_score = 0
        if 'macd_histogram' in df.columns and len(df) >= 5:
            hist_values = df['macd_histogram'].tail(5).tolist()
            if len(hist_values) >= 3:
                # تحسين: أي ضعف في MACD يُحتسب
                if hist_values[-1] > 0 and hist_values[-3] > 0:
                    if hist_values[-1] < hist_values[-3]:  # ضعف
                        weakness_ratio = abs(hist_values[-1] - hist_values[-3]) / abs(hist_values[-3]) if hist_values[-3] != 0 else 0
                        if weakness_ratio > 0.3:
                            macd_score = 10
                            reasons.append("MACD Strong Weakening (+10)")
                        else:
                            macd_score = 6
                            reasons.append("MACD Weakening (+6)")
        
        total_score += rsi_score + macd_score
        score_breakdown['rsi_macd'] = rsi_score + macd_score
        
        # --- 3. Market Structure - 15 نقطة (مساعد) ---
        ms = analyze_market_structure(df)
        ms_score = 0
        if ms['structure'] in ('lower_highs_lower_lows', 'lower_lows'):
            ms_score = 15  # تقليل من 20 إلى 15
            reasons.append(f"🏗️ {ms['reason']} (+15)")
        elif ms['structure'] == 'lower_highs':
            ms_score = 8  # تقليل من 10 إلى 8
            reasons.append(f"🏗️ {ms['reason']} (+8)")
        elif ms['structure'] in ('higher_highs_higher_lows', 'higher_lows'):
            ms_score = 0
        total_score += ms_score
        score_breakdown['market_structure'] = ms_score
        if ms['reason'] and ms_score == 0:
            reasons.append(f"🏗️ {ms['reason']} (0)")
        
        # --- 4. Support/Resistance - 15 نقطة ---
        sr = analyze_support_resistance(df)
        sr_score = 0
        if sr['at_resistance']:
            sr_score = 15
            reasons.append(f"📐 {sr['reason']} (+15)")
        score_breakdown['support_resistance'] = sr_score
        total_score += sr_score
        
        # --- 5. MTF Confirmation - 10 نقطة ---
        mtf = analyze_mtf_confirmation(df)
        mtf_score = min(10, mtf['score'])
        total_score += mtf_score
        score_breakdown['mtf_confirmation'] = mtf_score
        if mtf['reason']:
            reasons.append(f"⏱️ {mtf['reason']} ({mtf_score:+d})")
        
        # --- 6. Volume + Divergence - 15 نقطة (محسّن) ---
        vol_score = 0
        if len(df) >= 2:
            current_vol = df.iloc[-1].get('volume_ratio', 1)
            if current_vol > 2.0:
                vol_score = 8
                reasons.append(f"Vol Very High {current_vol:.1f}x (+8)")
            elif current_vol > 1.5:
                vol_score = 6
                reasons.append(f"Vol High {current_vol:.1f}x (+6)")
            elif current_vol > 1.0:
                vol_score = 3
                reasons.append(f"Vol Up {current_vol:.1f}x (+3)")
        
        div_score = 0
        if len(df) >= 20:
            recent_highs = []
            recent_rsis = []
            for i in range(-20, -1):
                if i >= -len(df):
                    candle = df.iloc[i]
                    recent_highs.append(candle['high'])
                    if 'rsi' in df.columns:
                        recent_rsis.append(candle['rsi'])
            
            if len(recent_highs) >= 10 and len(recent_rsis) >= 10:
                price_window = recent_highs[-10:]
                rsi_window = recent_rsis[-10:]
                
                first_high = max(price_window[:5])
                second_high = max(price_window[5:])
                
                first_idx = price_window[:5].index(first_high)
                second_idx = 5 + price_window[5:].index(second_high)
                
                first_rsi = rsi_window[first_idx]
                second_rsi = rsi_window[second_idx]
                
                if second_high > first_high and second_rsi < first_rsi:
                    rsi_diff = first_rsi - second_rsi
                    if rsi_diff > 5:
                        div_score = 7
                        reasons.append(f"Strong Bearish Divergence (+7)")
                    elif rsi_diff > 2:
                        div_score = 4
                        reasons.append(f"Bearish Divergence (+4)")
        
        total_score += vol_score + div_score
        score_breakdown['volume_divergence'] = vol_score + div_score
        
        # --- Trap Detection (تصفية محسّنة - فحص آخر 3 شموع) ---
        trap_is_filter = False
        if len(df) >= 20:
            avg_volume = df['volume'].tail(20).mean()
            
            # فحص آخر 3 شموع للفخاخ (فخ هبوط وهمي)
            for check_idx in range(1, min(4, len(df) + 1)):
                check_candle = df.iloc[-check_idx]
                check_volume = check_candle['volume']
                
                if avg_volume > 0 and check_volume > avg_volume * 3.0:
                    candle_body = abs(check_candle['close'] - check_candle['open'])
                    candle_range = check_candle['high'] - check_candle['low']
                    
                    if candle_range > 0 and candle_body > 0:
                        upper_shadow = check_candle['high'] - max(check_candle['close'], check_candle['open'])
                        lower_shadow = min(check_candle['close'], check_candle['open']) - check_candle['low']
                        
                        # فخ هبوط وهمي: ظل سفلي كبير مع حجم عالي
                        if lower_shadow > candle_body * 3.0:
                            trap_is_filter = True
                            reasons.append(f"⚠️ Fake Dip Trap (Candle-{check_idx})")
                            break
        
        # --- حساب نسبة الهبوط من القمة ---
        n = min(REVERSAL_CANDLES, len(df))
        high_n = df['high'].tail(n).max()
        current_price = df.iloc[-1]['close']
        drop_percent = ((high_n - current_price) / high_n) * 100 if high_n > 0 else 0
        
        # =========================================================
        # 🎯 القرار النهائي (المجموع = 110 نقطة)
        # =========================================================
        confidence_percent = min(total_score, 110)
        
        # إشارة القمة (متوسطة): نقاط كافية أو RSI >= 70 مع هبوط بسيط من القمة
        is_candle_signal = (
            confidence_percent >= MIN_SELL_CONFIDENCE or
            (rsi >= 70 and drop_percent >= PEAK_DROP_THRESHOLD * 0.5)  # متوسط: رفع الحساسية
        )
        
        if trap_is_filter and is_candle_signal:
            is_candle_signal = False
            reasons.append("🚫 Signal Blocked by Trap")
        
        if total_score >= MIN_CONFIDENCE + 10:
            reasons.append(f"✅ STRONG ({total_score}/110)")
        elif total_score >= MIN_CONFIDENCE:
            reasons.append(f"✅ SIGNAL ({total_score}/110)")
        elif total_score >= 40:
            reasons.append(f"⏳ WEAK ({total_score}/110)")
        else:
            reasons.append(f"❌ NO SIGNAL ({total_score}/110)")
        
        base_result['is_peaking'] = drop_percent >= PEAK_DROP_THRESHOLD
        
        base_result.update({
            'confidence': confidence_percent,
            'candle_signal': is_candle_signal,
            'reasons': reasons,
            'drop_percent': round(drop_percent, 3),
            'score_breakdown': score_breakdown
        })
        return base_result

    except Exception as e:
        base_result['reasons'].append(f'Error: {e}')
        return base_result


def get_market_analysis(exchange, symbol, limit=120):
    """Get technical analysis for a symbol with multi-timeframe data"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=limit)
        if not ohlcv or len(ohlcv) < 35:
            return None
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi().fillna(50)
        df['rsi'] = df['rsi'].clip(1, 99)  # منع RSI=0 أو RSI=100 (edge case بيانات قليلة/ثابتة)
        
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd().fillna(0)
        df['macd_signal'] = macd.macd_signal().fillna(0)
        df['macd_diff'] = macd.macd_diff().fillna(0)
        df['macd_histogram'] = df['macd_diff']  # alias لـ analyze_peak و analyze_reversal
        
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = (df['volume'] / df['volume_sma'].replace(0, 1)).fillna(1.0)
        
        # 🛡️ Testnet Fix: إذا الحجم صفر (Binance Testnet لا يوفر حجم حقيقي)
        # نستخدم 1.0 كقيمة افتراضية محايدة بدل 0.0 التي تعطل التحليل
        if df['volume'].tail(10).sum() == 0:
            df['volume_ratio'] = df['volume_ratio'].replace(0.0, 1.0).fillna(1.0)
        
        df['price_change'] = df['close'].pct_change(10) * 100
        df['price_change'] = df['price_change'].fillna(0)
        
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], low=df['low'], close=df['close'], window=14
        ).average_true_range()
        df['atr'] = df['atr'].fillna(1.0)
        
        df['ema_9'] = ta.trend.EMAIndicator(close=df['close'], window=9, fillna=True).ema_indicator()
        df['ema_21'] = ta.trend.EMAIndicator(close=df['close'], window=21, fillna=True).ema_indicator()
        df['ema_crossover'] = (df['ema_9'] > df['ema_21']).astype(int) * 2 - 1
        
        df['volume_trend'] = df['volume'].pct_change(3) * 100
        df['volume_trend'] = df['volume_trend'].fillna(0)
        
        if len(df) >= 12:
            df['price_change_1h'] = ((df['close'] - df['close'].shift(12)) / df['close'].shift(12)) * 100
        else:
            df['price_change_1h'] = 0
        df['price_change_1h'] = df['price_change_1h'].fillna(0)
        
        btc_change_1h = 0
        eth_change_1h = 0
        bnb_change_1h = 0
        
        market_data = get_market_data(exchange, ttl_hash=get_ttl_hash())
        
        if symbol not in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
            btc_change_1h = market_data.get('BTC/USDT', 0)
            eth_change_1h = market_data.get('ETH/USDT', 0)
            bnb_change_1h = market_data.get('BNB/USDT', 0)
        
        mtf_analysis = calculate_mtf_from_5m_data(df)
        market_regime = get_market_regime(df)
        flash_crash_protection = check_flash_crash(df, symbol)
        time_analysis = get_time_analysis()
        
        latest = df.iloc[-1]
        candles = df.tail(2).to_dict('records') if len(df) >= 2 else []
        
        bid_ask_spread = 0
        try:
            ticker = exchange.fetch_ticker(symbol)
            if ticker.get('bid') and ticker.get('ask'):
                bid_ask_spread = ((ticker['ask'] - ticker['bid']) / ticker['bid']) * 100
        except:
            bid_ask_spread = 0
        
        liquidity_metrics = get_liquidity_metrics(exchange, symbol, df)

        high_24h = df['high'].tail(288).max() if len(df) >= 288 else (df['high'].max() if not df.empty else 0)
        low_24h = df['low'].tail(288).min() if len(df) >= 288 else (df['low'].min() if not df.empty else 0)

        reversal_analysis = analyze_reversal(df, latest['rsi'])
        peak_analysis = analyze_peak(df, latest['rsi'])

        price_drop = {'drop_percent': 0, 'confirmed': False}
        try:
            if len(df) >= 12:
                highest_price_1h = df['high'].tail(12).max()
                current_price_df = df['close'].iloc[-1]
                
                if highest_price_1h is not None and current_price_df is not None and highest_price_1h > 0:
                    drop_percent = ((highest_price_1h - current_price_df) / highest_price_1h) * 100
                    price_drop = {
                        'drop_percent': drop_percent,
                        'highest_1h': highest_price_1h,
                        'current': current_price_df,
                        'confirmed': drop_percent >= 2.0
                    }
        except Exception:
            pass
        
        return {
            'candles': candles,
            'rsi': latest['rsi'],
            'macd': latest['macd'],
            'macd_signal': latest['macd_signal'],
            'macd_diff': latest['macd_diff'],
            'volume': latest['volume'],
            'volume_sma': latest['volume_sma'],
            'volume_ratio': latest['volume_ratio'],
            'price_momentum': latest['price_change'],
            'close': latest['close'],
            'mtf': mtf_analysis,
            'market_regime': market_regime,
            'flash_crash_protection': flash_crash_protection,
            'time_analysis': time_analysis,
            'atr': latest['atr'],
            'ema_9': latest['ema_9'],
            'ema_21': latest['ema_21'],
            'ema_crossover': latest['ema_crossover'],
            'bid_ask_spread': bid_ask_spread,
            'volume_trend': latest['volume_trend'],
            'price_change_1h': latest['price_change_1h'],
            'reversal': reversal_analysis,
            'peak': peak_analysis,
            'price_drop': price_drop,
            'liquidity_metrics': liquidity_metrics,
            **liquidity_metrics,
            'btc_change_1h': btc_change_1h,
            'panic_greed': detect_panic_greed(latest),
            'eth_change_1h': eth_change_1h,
            'bnb_change_1h': bnb_change_1h,
            'high_24h': high_24h,
            'low_24h': low_24h
        }
    except Exception as e:
        print(f"❌ Analysis error {symbol}: {e}")
        return None

def calculate_mtf_from_5m_data(df):
    """حساب multi-timeframe analysis من بيانات 5 دقائق"""
    try:
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}
        
        df_5m = df.tail(20).copy()
        df_5m['sma_20'] = df_5m['close'].rolling(window=20).mean()
        df_5m['sma_50'] = df_5m['close'].rolling(window=min(50, len(df_5m))).mean()
        latest_5m = df_5m.iloc[-1]
        
        if latest_5m['close'] > latest_5m['sma_20'] > latest_5m['sma_50']:
            scores['bullish'] += 1
        elif latest_5m['close'] < latest_5m['sma_20'] < latest_5m['sma_50']:
            scores['bearish'] += 1
        else:
            scores['neutral'] += 1
        
        if len(df) >= 20:
            df_15m = df.iloc[::3].tail(20).copy()
            df_15m['sma_20'] = df_15m['close'].rolling(window=20).mean()
            df_15m['sma_50'] = df_15m['close'].rolling(window=min(50, len(df_15m))).mean()
            if len(df_15m) > 0:
                latest_15m = df_15m.iloc[-1]
                
                if latest_15m['close'] > latest_15m['sma_20'] > latest_15m['sma_50']:
                    scores['bullish'] += 1
                elif latest_15m['close'] < latest_15m['sma_20'] < latest_15m['sma_50']:
                    scores['bearish'] += 1
                else:
                    scores['neutral'] += 1
        
        if len(df) >= 60:
            df_1h = df.iloc[::12].tail(20).copy()
            df_1h['sma_20'] = df_1h['close'].rolling(window=20).mean()
            df_1h['sma_50'] = df_1h['close'].rolling(window=min(50, len(df_1h))).mean()
            if len(df_1h) > 0:
                latest_1h = df_1h.iloc[-1]
                
                if latest_1h['close'] > latest_1h['sma_20'] > latest_1h['sma_50']:
                    scores['bullish'] += 1
                elif latest_1h['close'] < latest_1h['sma_20'] < latest_1h['sma_50']:
                    scores['bearish'] += 1
                else:
                    scores['neutral'] += 1
        
        trend = max(scores, key=scores.get)
        return {'trend': trend, 'scores': scores, 'total': scores[trend]}
        
    except Exception as e:
        return {'trend': 'neutral', 'scores': {'bullish': 0, 'bearish': 0, 'neutral': 3}, 'total': 3}



def get_liquidity_metrics(exchange, symbol, df_5m=None):
    """
    قياس السيولة من Order Book
    Returns: dict with liquidity metrics
    """
    try:
        order_book = exchange.fetch_order_book(symbol, limit=20)
        
        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return {
                'depth_ratio': 1.0,
                'spread_percent': 0.1,
                'bid_depth': 0,
                'ask_depth': 0,
                'liquidity_score': 50,
                'price_impact': 0.5,
                'volume_consistency': 50
            }
        
        bid_depth = sum([bid[1] for bid in order_book['bids'][:10]]) if len(order_book['bids']) >= 10 else 0
        ask_depth = sum([ask[1] for ask in order_book['asks'][:10]]) if len(order_book['asks']) >= 10 else 0
        
        depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0
        
        best_bid = order_book['bids'][0][0] if order_book['bids'] else 0
        best_ask = order_book['asks'][0][0] if order_book['asks'] else 0
        spread_percent = ((best_ask - best_bid) / best_bid) * 100 if best_bid > 0 else 0.1
        
        target_cost = 15
        cumulative_cost = 0
        cumulative_volume = 0
        price_impact = 0
        
        for ask in order_book['asks']:
            price, volume = ask
            cost = price * volume
            if cumulative_cost + cost >= target_cost:
                remaining = target_cost - cumulative_cost
                final_price = price
                price_impact = ((final_price - best_ask) / best_ask) * 100 if best_ask > 0 else 0
                break
            cumulative_cost += cost
            cumulative_volume += volume
        
        liquidity_score = 100
        
        if spread_percent > 0.5:
            liquidity_score -= 30
        elif spread_percent > 0.3:
            liquidity_score -= 15
        
        if depth_ratio < 0.7 or depth_ratio > 1.5:
            liquidity_score -= 20
        
        if bid_depth < 10000:
            liquidity_score -= 20
        elif bid_depth < 50000:
            liquidity_score -= 10
        
        if price_impact > 1.0:
            liquidity_score -= 20
        elif price_impact > 0.5:
            liquidity_score -= 10
        
        liquidity_score = max(0, liquidity_score)
        
        volume_consistency = 50
        try:
            if df_5m is not None and not df_5m.empty:
                volumes = df_5m['volume'].tolist()
                import numpy as np
                volume_mean = np.mean(volumes)
                volume_std = np.std(volumes)
                
                if volume_mean > 0:
                    cv = (volume_std / volume_mean) * 100
                    if cv < 30:
                        volume_consistency = 90
                    elif cv < 50:
                        volume_consistency = 70
                    elif cv < 80:
                        volume_consistency = 50
                    else:
                        volume_consistency = 30
        except:
            volume_consistency = 50
        
        return {
            'depth_ratio': round(depth_ratio, 2),
            'spread_percent': round(spread_percent, 4),
            'bid_depth': round(bid_depth, 2),
            'ask_depth': round(ask_depth, 2),
            'liquidity_score': int(liquidity_score),
            'price_impact': round(price_impact, 4),
            'volume_consistency': int(volume_consistency)
        }
        
    except Exception as e:
        print(f"⚠️ Liquidity metrics error for {symbol}: {e}")
        return {
            'depth_ratio': 1.0,
            'spread_percent': 0.1,
            'bid_depth': 0,
            'ask_depth': 0,
            'liquidity_score': 50,
            'price_impact': 0.5,
            'volume_consistency': 50
        }

def detect_panic_greed(analysis):
    """كشف الذعر/الجشع النفسي (أقل صرامة)"""
    try:
        volume = analysis.get('volume', 0)
        avg_volume = analysis.get('volume_sma', 0)
        price_change = analysis.get('price_momentum', 0)

        if avg_volume == 0:
            return {'panic_score': 0, 'greed_score': 0}

        volume_ratio = volume / avg_volume

        panic_score = 0
        greed_score = 0

        # ذعر: حجم عالي مع انخفاض سعر
        if volume_ratio > 1.5 and price_change < -2:
            panic_score = min(volume_ratio * 10, 30)  # أقل صرامة (حد 30 بدل 50)

        # جشع: حجم عالي مع ارتفاع سعر
        if volume_ratio > 1.5 and price_change > 2:
            greed_score = min(volume_ratio * 10, 30)

        return {'panic_score': panic_score, 'greed_score': greed_score}

    except Exception as e:
        return {'panic_score': 0, 'greed_score': 0}
