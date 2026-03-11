"""
💰 Trading Module
Handles buy and sell order execution
"""

import time

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
    """Execute sell order"""
    try:
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

def should_sell_fast_tp(current_price, buy_price, partial_sold, target_percent=1.0):
    """Check if should sell at fast TP"""
    profit_percent = ((current_price - buy_price) / buy_price) * 100
    
    if not partial_sold and profit_percent >= target_percent:
        return True, profit_percent
    
    return False, profit_percent

def should_sell_bearish(mtf_analysis, current_price, buy_price):
    """Check if should sell on bearish trend"""
    if mtf_analysis['trend'] == 'bearish' and mtf_analysis['total'] >= 2:
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        return True, profit_percent
    
    return False, 0

def should_sell_stop_loss(current_price, highest_price, buy_price, stop_loss_percent=2.0):
    """Check trailing stop loss"""
    trailing_stop = highest_price * (1 - stop_loss_percent / 100)
    
    if current_price <= trailing_stop:
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        return True, profit_percent, "Trailing Stop Loss"
    
    return False, 0, ""

def update_highest_price(current_price, highest_price):
    """Update highest price for trailing stop"""
    return max(current_price, highest_price)
