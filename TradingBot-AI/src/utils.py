"""
🛠️ Utilities Module
Helper functions
"""

from datetime import datetime, timedelta

def calculate_dynamic_confidence(analysis, mtf_analysis):
    """Calculate confidence score (0-120)"""
    confidence = 0
    reasons = []
    
    rsi = analysis['rsi']
    macd_diff = analysis['macd_diff']
    volume_ratio = analysis['volume'] / analysis['volume_sma'] if analysis['volume_sma'] > 0 else 0
    
    # Trend check
    if mtf_analysis['trend'] == 'bearish':
        return 0, ["Bearish trend"]
    
    # RSI scoring (0-30)
    if rsi < 30:
        confidence += 30
        reasons.append(f"RSI {rsi:.1f} (Strong oversold)")
    elif rsi < 40:
        confidence += 20
        reasons.append(f"RSI {rsi:.1f} (Oversold)")
    elif rsi < 50:
        confidence += 10
        reasons.append(f"RSI {rsi:.1f} (Neutral)")
    
    # MACD scoring (0-30)
    if macd_diff > 0:
        if macd_diff > 20:
            confidence += 30
            reasons.append(f"MACD {macd_diff:.1f} (Strong bullish)")
        elif macd_diff > 10:
            confidence += 20
            reasons.append(f"MACD {macd_diff:.1f} (Bullish)")
        else:
            confidence += 10
            reasons.append(f"MACD {macd_diff:.1f} (Positive)")
    
    # Volume scoring (0-30)
    if volume_ratio > 1.5:
        confidence += 30
        reasons.append(f"Volume {volume_ratio:.1f}x (High)")
    elif volume_ratio > 1.2:
        confidence += 20
        reasons.append(f"Volume {volume_ratio:.1f}x (Good)")
    elif volume_ratio > 1.0:
        confidence += 10
        reasons.append(f"Volume {volume_ratio:.1f}x (Normal)")
    
    # Trend bonus (0-30)
    if mtf_analysis['trend'] == 'bullish':
        trend_score = mtf_analysis['total'] * 10
        confidence += trend_score
        reasons.append(f"Bullish trend ({mtf_analysis['total']}/3)")
    
    return confidence, reasons

def get_active_positions_count(symbols_dict):
    """Count active positions"""
    return sum(1 for data in symbols_dict.values() if data['position'] is not None)

def get_total_invested(symbols_dict):
    """Calculate total invested amount"""
    total = 0
    for data in symbols_dict.values():
        if data['position']:
            pos = data['position']
            total += pos['amount'] * pos['buy_price']
    return total

def should_send_report(last_report_time, interval_minutes=30):
    """Check if should send periodic report"""
    if last_report_time is None:
        return True
    
    elapsed = datetime.now() - last_report_time
    return elapsed >= timedelta(minutes=interval_minutes)

def format_price(price):
    """Format price based on value"""
    if price >= 100:
        return f"${price:>8.2f}"
    elif price >= 1:
        return f"${price:>8.4f}"
    elif price >= 0.01:
        return f"${price:>8.6f}"
    else:
        return f"${price:>8.8f}"  # للعملات الرخيصة مثل SHIB

def calculate_profit_percent(current_price, buy_price):
    """Calculate profit percentage"""
    return ((current_price - buy_price) / buy_price) * 100
