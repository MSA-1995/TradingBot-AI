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
    del ttl_hash # يستخدم فقط لتحديث الكاش
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

def analyze_reversal(df, rsi):
    """
    تحليل الارتداد من القاع - نظام النقاط الذكي:
    - الشمعات (0-25 نقطة)
    - الترند (0-20 نقطة) - 5 شمعات
    - الزخم (0-30 نقطة)
    - التأكيد (0-15 نقطة)
    - الفوليوم (0-10 نقطة)
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

    if rsi > 75:
        base_result['reasons'].append(f'RSI Overbought ({rsi:.0f})')
        return base_result

    try:
        total_score = 0
        reasons = []
        score_breakdown = {}
        
        # =========================================================
        # 📊 نظام النقاط الذكي (المجموع = 100 نقطة)
        # =========================================================
        
        # --- 1. فحص الترند (5 شمعات) - 20 نقطة ---
        lookback = min(5, len(df))
        trend_start = df.iloc[-lookback]['open']
        trend_end = df.iloc[-1]['close']
        trend_change = ((trend_end - trend_start) / trend_start) * 100
        
        if trend_change < -2.0:
            trend_score = 20
            base_result['trend'] = 'strong_downtrend'
        elif trend_change < -1.0:
            trend_score = 15
            base_result['trend'] = 'downtrend'
        elif trend_change < -0.5:
            trend_score = 10
            base_result['trend'] = 'weak_downtrend'
        elif abs(trend_change) <= 0.5:
            trend_score = 5
            base_result['trend'] = 'sideways'
        else:
            trend_score = 0
            base_result['trend'] = 'uptrend'
            
        total_score += trend_score
        score_breakdown['trend'] = trend_score
        if trend_score > 0:
            reasons.append(f"Trend {trend_change:.1f}% (+{trend_score})")
        
        base_result['momentum'] = trend_change
        
        # --- 2. فحص الزخم (RSI) - 30 نقطة ---
        if rsi < 25:
            rsi_score = 30
            reasons.append(f"RSI Very Low ({rsi:.0f}) (+30)")
        elif rsi < 30:
            rsi_score = 25
            reasons.append(f"RSI Oversold ({rsi:.0f}) (+25)")
        elif rsi < 35:
            rsi_score = 18
            reasons.append(f"RSI Low ({rsi:.0f}) (+18)")
        elif rsi < 40:
            rsi_score = 10
            reasons.append(f"RSI OK ({rsi:.0f}) (+10)")
        elif rsi < 45:
            rsi_score = 5
            reasons.append(f"RSI Neutral ({rsi:.0f}) (+5)")
        else:
            rsi_score = 0
            
        total_score += rsi_score
        score_breakdown['rsi'] = rsi_score
        
        # --- 3. فحص الشمعات (Pattern) - 25 نقطة ---
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
            
            # 1. Hammer: ظل سفلي طويل
            is_hammer = (
                lower_shadow >= 2.0 * body and 
                body < candle_range * 0.3
            )
            
            if is_hammer:
                candle_signal = True
                pattern_score = 25
                pattern_name = "Hammer"
                pattern_found_idx = i
                reasons.append(f"{pattern_name} (+25)")
                break
            
            # 2. Bullish Engulfing: شمعة حمراء ثم خضراء أكبر
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_red = prev_candle['close'] < prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                
                is_bullish_engulfing = (
                    prev_is_red and
                    is_green and
                    pattern_candle['close'] > prev_candle['open'] and
                    pattern_candle['open'] < prev_candle['close'] and
                    body > prev_body * 1.2
                )
                
                if is_bullish_engulfing:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Bullish Engulfing"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
            
            # 3. Morning Star: 3 شموع (حمراء كبيرة + صغيرة + خضراء كبيرة)
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
                    c1['close'] < c1['open'] and
                    c1_body > c1_range * 0.5 and
                    c2_body < c2_range * 0.3 and
                    c3['close'] > c3['open'] and
                    c3_body > c3_range * 0.5 and
                    c3['close'] > c1['open']
                )
                
                if is_morning_star:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Morning Star"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
            
            # 4. Three White Soldiers: 3 شموع خضراء متتالية
            if i + 2 < len(df) and i <= 3:
                c1 = df.iloc[-i-2]
                c2 = df.iloc[-i-1]
                c3 = pattern_candle
                
                c1_body = abs(c1['close'] - c1['open'])
                c2_body = abs(c2['close'] - c2['open'])
                c3_body = abs(c3['close'] - c3['open'])
                
                is_three_soldiers = (
                    c1['close'] > c1['open'] and
                    c2['close'] > c2['open'] and
                    c3['close'] > c3['open'] and
                    c1_body > 0 and
                    c2_body > 0 and
                    c3_body > 0 and
                    c2['close'] > c1['close'] and
                    c3['close'] > c2['close']
                )
                
                if is_three_soldiers:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Three White Soldiers"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
            
            # 5. Piercing Line: شمعة حمراء ثم خضراء تخترق أكثر من نصفها
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_red = prev_candle['close'] < prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                prev_mid = (prev_candle['open'] + prev_candle['close']) / 2
                
                is_piercing = (
                    prev_is_red and
                    is_green and
                    pattern_candle['open'] < prev_candle['close'] and
                    pattern_candle['close'] > prev_mid and
                    body > prev_body * 0.5
                )
                
                if is_piercing:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Piercing Line"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
        
        total_score += pattern_score
        score_breakdown['pattern'] = pattern_score
        
        # --- 4. Confirmation (شمعة خضراء بعد النمط فعلاً) - 15 نقطة ---
        confirmation_score = 0
        if candle_signal and pattern_found_idx > 1 and len(df) >= 2:
            confirm_candle = df.iloc[-(pattern_found_idx - 1)] if pattern_found_idx > 1 else df.iloc[-1]
            if confirm_candle['close'] > confirm_candle['open']:
                confirmation_score = 15
                reasons.append("Confirmation ✓ (+15)")
        
        total_score += confirmation_score
        score_breakdown['confirmation'] = confirmation_score
        
        # --- 5. Volume - 10 نقطة ---
        volume_score = 0
        if len(df) >= 2:
            current_vol = df.iloc[-1].get('volume_ratio', 1)
            if current_vol > 1.5:
                volume_score = 10
                reasons.append(f"Vol {current_vol:.1f}x (+10)")
            elif current_vol > 1.0:
                volume_score = 5
                reasons.append(f"Vol {current_vol:.1f}x (+5)")
        
        total_score += volume_score
        score_breakdown['volume'] = volume_score
        
        # --- 6. Trap Detection (تصفية لا خصم) - 15 نقاط ---
        # في القاع: ظل سفلي طويل = رفض هبوطي (إيجابي)
        # في القاع: ظل علوي طويل = فخ (تصفية لا خصم)
        trap_score = 0
        trap_is_filter = False
        if len(df) >= 20:
            current_candle = df.iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            current_volume = current_candle['volume']
            
            if avg_volume > 0 and current_volume > avg_volume * 3.0:
                candle_body = abs(current_candle['close'] - current_candle['open'])
                candle_range = current_candle['high'] - current_candle['low']
                
                if candle_range > 0 and candle_body > 0:
                    upper_shadow = current_candle['high'] - max(current_candle['close'], current_candle['open'])
                    lower_shadow = min(current_candle['close'], current_candle['open']) - current_candle['low']
                    
                    if upper_shadow > candle_body * 3.0:
                        trap_is_filter = True
                        reasons.append("⚠️ Trap Warning (High Vol + Upper Wick)")
                    elif lower_shadow > candle_body * 3.0:
                        trap_score = 10
                        reasons.append("✅ Rejection Detected (Long Lower Wick) (+10)")
        
        total_score += trap_score
        score_breakdown['trap_detection'] = trap_score
        
        # --- 7. Volume Divergence (محسّن - يكشف الحالتين) - 10 نقاط ---
        vol_div_score = 0
        if len(df) >= 10:
            recent_lows_idx = []
            recent_vols = []
            for i in range(-10, 0):
                if i >= -len(df):
                    candle = df.iloc[i]
                    recent_lows_idx.append((i, candle['low']))
                    recent_vols.append(candle.get('volume', 0))
            
            if len(recent_lows_idx) >= 5:
                sorted_by_low = sorted(recent_lows_idx, key=lambda x: x[1])[:2]
                if len(sorted_by_low) >= 2:
                    idx1, low1 = sorted_by_low[0]
                    idx2, low2 = sorted_by_low[1]
                    
                    vol1 = recent_vols[idx1 + 10] if (idx1 + 10) < len(recent_vols) else 0
                    vol2 = recent_vols[idx2 + 10] if (idx2 + 10) < len(recent_vols) else 0
                    
                    if low2 < low1 and vol2 < vol1 * 0.8:
                        vol_div_score = 10
                        reasons.append("Volume Divergence: Sellers Exhausted (+10)")
                    elif low1 < low2 and vol1 < vol2 * 0.8:
                        vol_div_score = 5
                        reasons.append("Volume Divergence: Weak Recovery (+5)")
        
        total_score += vol_div_score
        score_breakdown['vol_divergence'] = vol_div_score
        
        # --- 8. Bullish RSI Divergence (الانزياح) - 15 نقطة ---
        divergence_score = 0
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
                        divergence_score = 15
                        reasons.append(f"Bullish Divergence ({rsi_diff:.0f}pts) (+15)")
                    elif rsi_diff > 2:
                        divergence_score = 10
                        reasons.append(f"Weak Bullish Divergence ({rsi_diff:.0f}pts) (+10)")
        
        total_score += divergence_score
        score_breakdown['divergence'] = divergence_score
        
        # --- 9. MACD Histogram Contraction (تقلص الزخم) - 10 نقاط ---
        macd_score = 0
        if 'macd_histogram' in df.columns and len(df) >= 5:
            hist_values = df['macd_histogram'].tail(5).tolist()
            if len(hist_values) >= 3:
                if hist_values[-1] < 0 and hist_values[-3] < 0:
                    if hist_values[-1] > hist_values[-3] * 0.7:
                        macd_score = 10
                        reasons.append("MACD Strengthening (+10)")
        
        total_score += macd_score
        score_breakdown['macd_strong'] = macd_score
        
        # --- حساب نسبة الارتداد ---
        n = min(REVERSAL_CANDLES, len(df))
        low_n = df['low'].tail(n).min()
        current_price = df.iloc[-1]['close']
        bounce_percent = ((current_price - low_n) / low_n) * 100 if low_n > 0 else 0
        
        # =========================================================
        # 🎯 القرار النهائي (المجموع = 145 نقطة)
        # =========================================================
        confidence_percent = min(int((total_score / 145) * 100), 100)
        is_candle_signal = confidence_percent >= MIN_CONFIDENCE
        
        if trap_is_filter and is_candle_signal:
            is_candle_signal = False
            reasons.append("🚫 Signal Blocked by Trap")
        
        if total_score >= MIN_CONFIDENCE + 10:
            reasons.append(f"✅ STRONG ({total_score}/145)")
        elif total_score >= MIN_CONFIDENCE:
            reasons.append(f"✅ SIGNAL ({total_score}/145)")
        elif total_score >= 40:
            reasons.append(f"⏳ WEAK ({total_score}/145)")
        else:
            reasons.append(f"❌ NO SIGNAL ({total_score}/145)")
        
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
    تحليل الانعكاس من القمة - نظام النقاط الذكي:
    - الشمعات (0-25 نقطة)
    - الترند (0-20 نقطة) - 10 شمعات
    - الزخم (0-30 نقطة)
    - التأكيد (0-15 نقطة)
    - الفوليوم (0-10 نقطة)
    """
    from config import PEAK_DROP_THRESHOLD, REVERSAL_CANDLES, MIN_CONFIDENCE

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

    if rsi > 75:
        base_result['reasons'].append(f'RSI Overbought ({rsi:.0f})')
        return base_result

    try:
        total_score = 0
        reasons = []
        score_breakdown = {}
        
        # =========================================================
        # 📊 نظام النقاط الذكي (المجموع = 100 نقطة)
        # =========================================================
        
        # --- 1. فحص الترند (10 شمعات) - 20 نقطة ---
        n = min(REVERSAL_CANDLES, len(df))
        trend_start = df.iloc[-n]['open']
        trend_end = df.iloc[-1]['close']
        trend_change = ((trend_end - trend_start) / trend_start) * 100

        if trend_change > 3.0:
            trend_score = 20
            base_result['trend'] = 'strong_uptrend'
        elif trend_change > 2.0:
            trend_score = 15
            base_result['trend'] = 'uptrend'
        elif trend_change > 1.0:
            trend_score = 10
            base_result['trend'] = 'weak_uptrend'
        elif abs(trend_change) <= 1.0:
            trend_score = 5
            base_result['trend'] = 'sideways'
        else:
            trend_score = 0
            base_result['trend'] = 'downtrend'
            
        total_score += trend_score
        score_breakdown['trend'] = trend_score
        if trend_score > 0:
            reasons.append(f"Trend +{trend_change:.1f}% (+{trend_score})")
        
        base_result['momentum'] = trend_change
        
        # --- 2. فحص الزخم (RSI) - 30 نقطة ---
        if rsi > 80:
            rsi_score = 30
            reasons.append(f"RSI Very High ({rsi:.0f}) (+30)")
        elif rsi > 70:
            rsi_score = 25
            reasons.append(f"RSI Overbought ({rsi:.0f}) (+25)")
        elif rsi > 65:
            rsi_score = 18
            reasons.append(f"RSI High ({rsi:.0f}) (+18)")
        elif rsi > 60:
            rsi_score = 10
            reasons.append(f"RSI OK ({rsi:.0f}) (+10)")
        elif rsi > 55:
            rsi_score = 5
            reasons.append(f"RSI Neutral ({rsi:.0f}) (+5)")
        else:
            rsi_score = 0
            
        total_score += rsi_score
        score_breakdown['rsi'] = rsi_score
        
        # --- 3. فحص الشمعات (Pattern) - 25 نقطة ---
        candle_signal = False
        pattern_score = 0
        pattern_name = ""
        pattern_found_idx = -1
        
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
            
            # 1. Shooting Star: ظل علوي طويل + أحمر
            is_shooting_star = (
                upper_shadow >= 2.0 * body and 
                body < candle_range * 0.3 and
                is_red
            )
            
            if is_shooting_star:
                candle_signal = True
                pattern_score = 25
                pattern_name = "Shooting Star"
                pattern_found_idx = i
                reasons.append(f"{pattern_name} (+25)")
                break
            
            # 2. Bearish Engulfing: شمعة خضراء ثم حمراء أكبر
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_green = prev_candle['close'] > prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                
                is_bearish_engulfing = (
                    prev_is_green and
                    is_red and
                    pattern_candle['open'] > prev_candle['close'] and
                    pattern_candle['close'] < prev_candle['open'] and
                    body > prev_body * 1.2
                )
                
                if is_bearish_engulfing:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Bearish Engulfing"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
            
            # 3. Evening Star: 3 شموع (خضراء كبيرة + صغيرة + حمراء كبيرة)
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
                    c1['close'] > c1['open'] and
                    c1_body > c1_range * 0.5 and
                    c2_body < c2_range * 0.3 and
                    c3['close'] < c3['open'] and
                    c3_body > c3_range * 0.5 and
                    c3['close'] < c1['open']
                )
                
                if is_evening_star:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Evening Star"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
            
            # 4. Three Black Crows: 3 شموع حمراء متتالية
            if i + 2 < len(df) and i <= 3:
                c1 = df.iloc[-i-2]
                c2 = df.iloc[-i-1]
                c3 = pattern_candle
                
                c1_body = abs(c1['close'] - c1['open'])
                c2_body = abs(c2['close'] - c2['open'])
                c3_body = abs(c3['close'] - c3['open'])
                
                is_three_crows = (
                    c1['close'] < c1['open'] and
                    c2['close'] < c2['open'] and
                    c3['close'] < c3['open'] and
                    c1_body > 0 and
                    c2_body > 0 and
                    c3_body > 0 and
                    c2['close'] < c1['close'] and
                    c3['close'] < c2['close']
                )
                
                if is_three_crows:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Three Black Crows"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
            
            # 5. Dark Cloud Cover: شمعة خضراء ثم حمراء تغلق تحت منتصفها
            if i + 1 < len(df):
                prev_candle = df.iloc[-i-1]
                prev_is_green = prev_candle['close'] > prev_candle['open']
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                prev_mid = (prev_candle['open'] + prev_candle['close']) / 2
                
                is_dark_cloud = (
                    prev_is_green and
                    is_red and
                    pattern_candle['open'] > prev_candle['close'] and
                    pattern_candle['close'] < prev_mid and
                    body > prev_body * 0.5
                )
                
                if is_dark_cloud:
                    candle_signal = True
                    pattern_score = 25
                    pattern_name = "Dark Cloud Cover"
                    pattern_found_idx = i
                    reasons.append(f"{pattern_name} (+25)")
                    break
        
        total_score += pattern_score
        score_breakdown['pattern'] = pattern_score
        
        # --- 4. Confirmation (شمعة حمراء بعد النمط فعلاً) - 15 نقطة ---
        confirmation_score = 0
        if candle_signal and pattern_found_idx > 1 and len(df) >= 2:
            confirm_candle = df.iloc[-(pattern_found_idx - 1)] if pattern_found_idx > 1 else df.iloc[-1]
            if confirm_candle['close'] < confirm_candle['open']:
                confirmation_score = 15
                reasons.append("Confirmation ✓ (+15)")
        
        total_score += confirmation_score
        score_breakdown['confirmation'] = confirmation_score
        
        # --- 5. Volume - 10 نقطة ---
        volume_score = 0
        if len(df) >= 2:
            current_vol = df.iloc[-1].get('volume_ratio', 1)
            if current_vol > 1.5:
                volume_score = 10
                reasons.append(f"Vol {current_vol:.1f}x (+10)")
            elif current_vol > 1.0:
                volume_score = 5
                reasons.append(f"Vol {current_vol:.1f}x (+5)")
        
        total_score += volume_score
        score_breakdown['volume'] = volume_score
        
        # --- 6. Trap Detection (تصفية لا خصم) - 15 نقاط ---
        # في القمة: ظل علوي طويل = رفض صعودي (إيجابي للبيع)
        # في القمة: ظل سفلي طويل = فخ (تصفية لا خصم)
        trap_score = 0
        trap_is_filter = False
        if len(df) >= 20:
            current_candle = df.iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            current_volume = current_candle['volume']
            
            if avg_volume > 0 and current_volume > avg_volume * 3.0:
                candle_body = abs(current_candle['close'] - current_candle['open'])
                candle_range = current_candle['high'] - current_candle['low']
                
                if candle_range > 0 and candle_body > 0:
                    upper_shadow = current_candle['high'] - max(current_candle['close'], current_candle['open'])
                    lower_shadow = min(current_candle['close'], current_candle['open']) - current_candle['low']
                    
                    if upper_shadow > candle_body * 3.0:
                        trap_score = 10
                        reasons.append("✅ Wick Rejection at Peak (Long Upper Wick) (+10)")
                    elif lower_shadow > candle_body * 3.0:
                        trap_is_filter = True
                        reasons.append("⚠️ Fake Dip Trap (Long Lower Wick)")
        
        total_score += trap_score
        score_breakdown['trap_detection'] = trap_score
        
        # --- 7. Volume Divergence (محسّن - يكشف الحالتين) - 10 نقاط ---
        vol_div_score = 0
        if len(df) >= 10:
            recent_highs_idx = []
            recent_vols = []
            for i in range(-10, 0):
                if i >= -len(df):
                    candle = df.iloc[i]
                    recent_highs_idx.append((i, candle['high']))
                    recent_vols.append(candle.get('volume', 0))
            
            if len(recent_highs_idx) >= 5:
                sorted_by_high = sorted(recent_highs_idx, key=lambda x: x[1], reverse=True)[:2]
                if len(sorted_by_high) >= 2:
                    idx1, high1 = sorted_by_high[0]
                    idx2, high2 = sorted_by_high[1]
                    
                    vol1 = recent_vols[idx1 + 10] if (idx1 + 10) < len(recent_vols) else 0
                    vol2 = recent_vols[idx2 + 10] if (idx2 + 10) < len(recent_vols) else 0
                    
                    if high2 > high1 and vol2 < vol1 * 0.8:
                        vol_div_score = 10
                        reasons.append("Volume Divergence: Hidden Weakness (+10)")
                    elif high1 > high2 and vol1 < vol2 * 0.8:
                        vol_div_score = 5
                        reasons.append("Volume Divergence: First Peak Weaker (+5)")
        
        total_score += vol_div_score
        score_breakdown['vol_divergence'] = vol_div_score
        
        # --- 8. RSI Divergence (الانزياح) - 15 نقطة ---
        divergence_score = 0
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
                        divergence_score = 15
                        reasons.append(f"RSI Divergence ({rsi_diff:.0f}pts) (+15)")
                    elif rsi_diff > 2:
                        divergence_score = 10
                        reasons.append(f"RSI Weak Divergence ({rsi_diff:.0f}pts) (+10)")
        
        total_score += divergence_score
        score_breakdown['divergence'] = divergence_score
        
        # --- 9. MACD Histogram Contraction (تقلص الزخم) - 10 نقاط ---
        macd_score = 0
        if 'macd_histogram' in df.columns and len(df) >= 5:
            hist_values = df['macd_histogram'].tail(5).tolist()
            if len(hist_values) >= 3:
                if hist_values[-1] > 0 and hist_values[-3] > 0:
                    if hist_values[-1] < hist_values[-3] * 0.7:
                        macd_score = 10
                        reasons.append("MACD Weakening (+10)")
        
        total_score += macd_score
        score_breakdown['macd_weak'] = macd_score
        
        # --- حساب نسبة الهبوط من القمة ---
        n = min(REVERSAL_CANDLES, len(df))
        high_n = df['high'].tail(n).max()
        current_price = df.iloc[-1]['close']
        drop_percent = ((high_n - current_price) / high_n) * 100 if high_n > 0 else 0
        
        # =========================================================
        # 🎯 القرار النهائي (المجموع = 145 نقطة)
        # =========================================================
        confidence_percent = min(int((total_score / 145) * 100), 100)
        is_candle_signal = confidence_percent >= MIN_CONFIDENCE
        
        if trap_is_filter and is_candle_signal:
            is_candle_signal = False
            reasons.append("🚫 Signal Blocked by Trap")
        
        if total_score >= MIN_CONFIDENCE + 10:
            reasons.append(f"✅ STRONG ({total_score}/145)")
        elif total_score >= MIN_CONFIDENCE:
            reasons.append(f"✅ SIGNAL ({total_score}/145)")
        elif total_score >= 40:
            reasons.append(f"⏳ WEAK ({total_score}/145)")
        else:
            reasons.append(f"❌ NO SIGNAL ({total_score}/145)")
        
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
        
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd().fillna(0)
        df['macd_signal'] = macd.macd_signal().fillna(0)
        df['macd_diff'] = macd.macd_diff().fillna(0)
        
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = (df['volume'] / df['volume_sma'].replace(0, 1)).fillna(1.0)
        
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
