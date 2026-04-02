"""
🛠️ Utilities Module
Helper functions + Trading functions
"""

from datetime import datetime, timedelta
import time

# ================================================================
# 💰 TRADING FUNCTIONS (من trading.py)
# ================================================================

def execute_buy(exchange, symbol, amount_usd, price, confidence):
    """Execute buy order"""
    try:
        amount = amount_usd / price
        order = exchange.create_market_buy_order(symbol, amount)
        
        return {
            'success': True,
            'order': order,
            'amount': amount,
            'price': price,
            'confidence': confidence
        }
    except Exception as e:
        print(f"❌ Buy error {symbol}: {e}")
        return {'success': False, 'error': str(e)}

def execute_sell(exchange, symbol, amount, reason=""):
    """Execute sell order with balance check"""
    try:
        # تحقق من الرصيد المتاح قبل البيع
        balance = exchange.fetch_balance()
        base_currency = symbol.split('/')[0]
        available_amount = balance.get(base_currency, {}).get('free', 0)
        
        if available_amount < amount:
            # بيع الرصيد المتاح فقط
            amount = available_amount
            if amount <= 0:
                print(f"⚠️ No balance to sell {symbol}")
                return {'success': False, 'error': 'No balance available'}
            print(f"⚠️ Adjusted sell amount to available balance: {amount}")
        
        # فحص القيمة الإجمالية قبل البيع (Binance minimum: $10)
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker.get('last', 0)
        sell_value = amount * current_price
        
        if sell_value < 10.0:
            print(f"⚠️ Sell value ${sell_value:.2f} < $10 minimum - Skipping {symbol}")
            return {'success': False, 'error': f'NOTIONAL: Value ${sell_value:.2f} below $10 minimum'}
        
        order = exchange.create_market_sell_order(symbol, amount)
        
        return {
            'success': True,
            'order': order,
            'reason': reason
        }
    except Exception as e:
        print(f"❌ Sell error {symbol}: {e}")
        return {'success': False, 'error': str(e)}

def calculate_sell_value(amount, price):
    """Calculate sell value"""
    return amount * price


# ================================================================
# 🛠️ HELPER FUNCTIONS
# ================================================================

def save_open_positions(storage, symbols_data, symbols_data_lock):
    """Wrapper function to time the saving of open positions."""
    start_time = time.time()
    
    positions_to_save = []
    # The data structure is {'SYMBOL': {'position': {...}}}, so we need to access the inner dict.
    with symbols_data_lock: # Ensure thread safety while iterating
        for symbol, data in symbols_data.items():
            if data.get('position'):
                # THE FIX: Access the inner 'position' dictionary and ensure it's not empty.
                position = data['position']
                if not position: # If position is an empty dict {}, skip it.
                    continue
                
                # Ensure buy_time is in a consistent string format
                buy_time = position.get('buy_time', datetime.now())
                if isinstance(buy_time, datetime):
                    buy_time = buy_time.isoformat()

                pos_data = {
                    'symbol': symbol,
                    'buy_price': position.get('buy_price', 0.0), # Correctly reads from the 'position' dict.
                    'amount': position.get('amount', 0.0),
                    'highest_price': position.get('highest_price', position.get('buy_price', 0.0)),
                    'tp_level_1': position.get('tp_level_1', False),
                    'tp_level_2': position.get('tp_level_2', False),
                    'buy_time': buy_time,
                    'invested': position.get('invested', 0.0),
                    # The DB 'data' column expects the dict from 'ai_data'
                    'data': position.get('ai_data', {})
                }
                
                positions_to_save.append(pos_data)

    storage.save_positions(positions_to_save)
    
    end_time = time.time()
    duration_ms = (end_time - start_time) * 1000

def calculate_dynamic_confidence(analysis, mtf_analysis):
    """حساب نقاط الثقة (0-100)"""
    confidence = 0
    reasons = []
    
    # حماية من None
    rsi = analysis.get('rsi', 50) if analysis.get('rsi') is not None else 50
    macd_diff = analysis.get('macd_diff', 0) if analysis.get('macd_diff') is not None else 0
    volume = analysis.get('volume', 0) if analysis.get('volume') is not None else 0
    volume_sma = analysis.get('volume_sma', 1) if analysis.get('volume_sma') is not None else 1
    
    volume_ratio = volume / volume_sma if volume_sma > 0 else 0
    
    # Trend check
    if mtf_analysis.get('trend') == 'bearish':
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
    if mtf_analysis.get('trend') == 'bullish':
        trend_score = mtf_analysis.get('total', 0) * 10
        confidence += trend_score
        reasons.append(f"Bullish trend ({mtf_analysis.get('total', 0)}/3)")
    
    return confidence, reasons

def get_active_positions_count(symbols_dict):
    """Count active positions"""
    return sum(1 for data in symbols_dict.values() if data['position'] is not None)

def get_total_invested(symbols_dict):
    """حساب إجمالي المبلغ المستثمر"""
    total = 0
    for data in symbols_dict.values():
        if data['position']:
            pos = data['position']
            # حماية من None
            amount = pos.get('amount', 0) if pos.get('amount') is not None else 0
            buy_price = pos.get('buy_price', 0) if pos.get('buy_price') is not None else 0
            total += amount * buy_price
    return total

def should_send_report(last_report_time, interval_seconds=1800):
    """Check if should send periodic report. Interval is in seconds."""
    if last_report_time is None:
        return True
    
    elapsed = datetime.now() - last_report_time
    return elapsed >= timedelta(seconds=interval_seconds)

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
    """حساب نسبة الربح"""
    # حماية من None
    if current_price is None or buy_price is None or buy_price == 0:
        return 0
    return ((current_price - buy_price) / buy_price) * 100