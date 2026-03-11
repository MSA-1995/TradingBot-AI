"""
📱 Notifications Module
Handles Discord messages and file logging
"""

import requests
from datetime import datetime
import os

DISCORD_WEBHOOK = os.getenv('DISCORD_WEBHOOK')

def send_discord(message, color='blue'):
    """Send message to Discord"""
    if not DISCORD_WEBHOOK:
        return
    
    colors = {
        'green': 0x00ff00,
        'red': 0xff0000,
        'blue': 0x0000ff,
        'yellow': 0xffff00,
        'purple': 0x800080
    }
    
    try:
        data = {
            "embeds": [{
                "description": message,
                "color": colors.get(color, 0x0000ff)
            }]
        }
        requests.post(DISCORD_WEBHOOK, json=data, timeout=5)
    except:
        pass

def log_trade(action, symbol, amount, price, value, profit_percent=None, reason=""):
    """Log trade to file"""
    try:
        import os
        os.makedirs('data/trades', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open('data/trades/trades.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] {action} {symbol}\n")
            f.write(f"Amount: {amount:.6f} | Price: ${price:.4f}\n")
            f.write(f"Value: ${value:.4f}\n")
            
            if profit_percent is not None:
                f.write(f"Profit: {profit_percent:+.2f}%\n")
            
            if reason:
                f.write(f"Reason: {reason}\n")
            
            f.write(f"{'='*60}\n")
    except Exception as e:
        print(f"❌ Log error: {e}")

def send_buy_notification(symbol, amount, price, value, confidence):
    """Send buy notification"""
    # Discord - احترافي
    message = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 **BUY SIGNAL**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Pair:** {symbol}\n"
        f"💰 **Amount:** {amount:.6f}\n"
        f"💵 **Price:** ${price:.4f}\n"
        f"💎 **Value:** ${value:.2f}\n"
        f"🎯 **Confidence:** {confidence}/120\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_discord(message, 'green')
    
    # Log
    log_trade('BUY', symbol, amount, price, value)

def send_sell_notification(symbol, amount, price, value, profit_percent, reason):
    """Send sell notification"""
    # تحديد الإيموجي والنوع حسب السبب
    if "TP" in reason or "FAST" in reason:
        emoji = "⚡"
        signal_type = "TAKE PROFIT"
        color = 'green'
    elif "BEARISH" in reason:
        emoji = "📉"
        signal_type = "BEARISH EXIT"
        color = 'yellow'
    elif "STOP" in reason or "LOSS" in reason:
        emoji = "🛑"
        signal_type = "STOP LOSS"
        color = 'red'
    else:
        emoji = "🔴"
        signal_type = "SELL SIGNAL"
        color = 'red'
    
    # تحديد لون الربح
    profit_emoji = "📈" if profit_percent > 0 else "📉"
    profit_sign = "+" if profit_percent > 0 else ""
    
    # Discord - احترافي
    message = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} **{signal_type}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Pair:** {symbol}\n"
        f"💰 **Amount:** {amount:.6f}\n"
        f"💵 **Price:** ${price:.4f}\n"
        f"💎 **Value:** ${value:.2f}\n"
        f"{profit_emoji} **Profit:** {profit_sign}{profit_percent:.2f}%\n"
        f"📝 **Reason:** {reason}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_discord(message, color)
    
    # Log
    log_trade('SELL', symbol, amount, price, value, profit_percent, reason)

def send_positions_report(balance, invested, active_count, max_positions):
    """Send positions report"""
    message = (
        f"══════════════════════════════\n"
        f"💼 **PORTFOLIO REPORT**\n"
        f"══════════════════════════════\n"
        f"💰 **Balance:** ${balance:.2f}\n"
        f"📊 **Invested:** ${invested:.2f}\n"
        f"🎯 **Active Positions:** {active_count}/{max_positions}\n"
        f"📈 **Available Slots:** {max_positions - active_count}\n"
        f"══════════════════════════════"
    )
    send_discord(message, 'blue')

def send_startup_notification():
    """Send bot startup notification"""
    message = (
        f"╔══════════════════════════════╗\n"
        f"║   🤖 BOT STARTED             ║\n"
        f"╚══════════════════════════════╝\n"
        f"🧠 **AI Brain:** ACTIVE\n"
        f"💰 **Boost:** $10-$20\n"
        f"🎯 **TP:** 1% | **SL:** 2%\n"
        f"🛡️ **Confidence Range:** 60-75/120\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Ready to trade!"
    )
    send_discord(message, 'blue')
