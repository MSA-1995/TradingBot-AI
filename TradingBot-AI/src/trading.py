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
