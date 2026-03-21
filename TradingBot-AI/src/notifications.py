"""
📱 Notifications Module
Handles Discord messages and file logging
"""

import requests
from datetime import datetime
import os
from config_encrypted import get_discord_webhook, get_critical_webhook

DISCORD_WEBHOOK = get_discord_webhook()
CRITICAL_WEBHOOK = get_critical_webhook()

def send_discord_embed(title, fields, color='blue', thumbnail_url=None):
    """Send embed message to Discord"""
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
        embed = {
            "title": title,
            "color": colors.get(color, 0x0000ff),
            "fields": fields,
            "footer": {
                "text": "MSA Trading Bot • AI Powered"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        
        data = {"embeds": [embed]}
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

def send_buy_notification(symbol, amount, price, value, confidence, tp_target=None, sl_target=None, buy_vote_percentage=None, buy_vote_count=None, total_consultants=None):
    """Send buy notification"""
    # Discord - احترافي
    fields = [
        {"name": "Pair", "value": symbol, "inline": True},
        {"name": "Amount", "value": f"{amount:.6f}", "inline": True},
        {"name": "Price", "value": f"${price:.4f}", "inline": True},
        {"name": "Value", "value": f"${value:.2f}", "inline": True},
        {"name": "Confidence", "value": f"{confidence}/120", "inline": True}
    ]
    
    # Add buy voting results if available
    if buy_vote_percentage is not None and buy_vote_count is not None and total_consultants is not None:
        fields.append({"name": "Buy Voting", "value": f"{buy_vote_percentage:.0f}% ({buy_vote_count}/{total_consultants} voted BUY)", "inline": False})
    
    send_discord_embed("BUY SIGNAL", fields, 'green')
    
    # Log
    log_trade('BUY', symbol, amount, price, value)

def send_sell_notification(symbol, amount, price, value, profit_percent, reason):
    """Send sell notification"""
    # تحديد النوع والون حسب السبب
    if "TP" in reason or "FAST" in reason:
        signal_type = "TAKE PROFIT"
        color = 'green'
    elif "BEARISH" in reason:
        signal_type = "BEARISH EXIT"
        color = 'yellow'
    elif "STOP" in reason or "LOSS" in reason:
        signal_type = "STOP LOSS"
        color = 'yellow'  # Changed from red to yellow
    else:
        signal_type = "SELL SIGNAL"
        color = 'yellow'  # Changed from red to yellow
    
    # تحديد علامة الربح
    profit_sign = "+" if profit_percent > 0 else ""
    
    # Discord - احترافي
    fields = [
        {"name": "Pair", "value": symbol, "inline": True},
        {"name": "Amount", "value": f"{amount:.6f}", "inline": True},
        {"name": "Price", "value": f"${price:.4f}", "inline": True},
        {"name": "Value", "value": f"${value:.2f}", "inline": True},
        {"name": "Profit", "value": f"{profit_sign}{profit_percent:.2f}%", "inline": True},
        {"name": "Reason", "value": reason, "inline": False}
    ]
    
    send_discord_embed(signal_type, fields, color)
    
    # Log
    log_trade('SELL', symbol, amount, price, value, profit_percent, reason)

def send_positions_report(balance, invested, active_count, max_positions, open_positions=None):
    """Send positions report with open positions details"""
    fields = [
        {"name": "Balance", "value": f"${balance:.2f}", "inline": True},
        {"name": "Invested", "value": f"${invested:.2f}", "inline": True},
        {"name": "Active Positions", "value": f"{active_count}/{max_positions}", "inline": True},
        {"name": "Available Slots", "value": f"{max_positions - active_count}", "inline": True}
    ]
    
    # إضافة تفاصيل الصفقات المفتوحة
    if open_positions and len(open_positions) > 0:
        positions_text = ""
        for symbol, pos_data in open_positions.items():
            buy_price = pos_data.get('buy_price', 0)
            current_price = pos_data.get('current_price', buy_price)
            profit_percent = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
            profit_sign = "+" if profit_percent >= 0 else ""
            
            positions_text += f"**{symbol}**\n"
            positions_text += f"Buy: ${buy_price:.4f} | Now: ${current_price:.4f}\n"
            positions_text += f"P/L: {profit_sign}{profit_percent:.2f}%\n\n"
        
        fields.append({"name": "Open Positions", "value": positions_text.strip(), "inline": False})
    
    send_discord_embed("PORTFOLIO REPORT", fields, 'blue')

def send_startup_notification():
    """Send bot startup notification"""
    fields = [
        {"name": "AI Brain", "value": "ACTIVE", "inline": True},
        {"name": "Boost", "value": "$10-$20", "inline": True},
        {"name": "TP / SL", "value": "1% / 2%", "inline": True},
        {"name": "Confidence Range", "value": "60-75/120", "inline": True},
        {"name": "Status", "value": "Ready to trade!", "inline": False}
    ]
    
    send_discord_embed("BOT STARTED", fields, 'blue')


def send_critical_alert(error_type, message, details=None):
    """Send critical error alert to Discord"""
    if not CRITICAL_WEBHOOK:
        return
    
    fields = [
        {"name": "Bot", "value": "Trading Bot", "inline": True},
        {"name": "Error Type", "value": error_type, "inline": True},
        {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "inline": True},
        {"name": "Message", "value": message, "inline": False}
    ]
    
    if details:
        fields.append({"name": "Details", "value": str(details)[:1000], "inline": False})
    
    embed = {
        "title": "🚨 CRITICAL ALERT",
        "color": 0xff0000,  # Red
        "fields": fields,
        "footer": {
            "text": "MSA Trading Bot • System Alerts"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        requests.post(CRITICAL_WEBHOOK, json={"embeds": [embed]}, timeout=5)
    except:
        pass

def send_database_error(error_message):
    """Send database connection error alert"""
    send_critical_alert(
        "Database Connection",
        "Failed to connect to database",
        error_message
    )

def send_model_error(model_name, error_message):
    """Send model loading/prediction error alert"""
    send_critical_alert(
        f"Model Error: {model_name}",
        "Model failed to load or predict",
        error_message
    )

def send_training_error(error_message):
    """Send training failure alert"""
    send_critical_alert(
        "Training Failed",
        "Deep Learning training encountered an error",
        error_message
    )

def send_exchange_error(error_message):
    """Send exchange API error alert"""
    send_critical_alert(
        "Exchange API Error",
        "Failed to connect to Binance",
        error_message
    )

# ========== الحالة الثابتة ==========

_status_message_id = None

def _get_status_message_id():
    """قراءة message ID من ملف محلي"""
    global _status_message_id
    if _status_message_id:
        return _status_message_id
    try:
        with open('data/status_id.txt', 'r') as f:
            _status_message_id = f.read().strip()
            return _status_message_id
    except:
        return None

def _save_status_message_id(message_id):
    """حفظ message ID في ملف محلي"""
    global _status_message_id
    _status_message_id = message_id
    try:
        import os
        os.makedirs('data', exist_ok=True)
        with open('data/status_id.txt', 'w') as f:
            f.write(str(message_id))
    except:
        pass

def _build_status_embed(online=True):
    """بناء رسالة الحالة"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return {
        "title": "MSA Trading Bot",
        "color": 0x00ff00 if online else 0xff0000,
        "description": "🟢  **ONLINE**" if online else "🔴  **OFFLINE**",
        "fields": [
            {"name": "الحالة", "value": "متصل" if online else "غير متصل", "inline": False},
            {"name": "آخر تحديث", "value": now, "inline": True},
        ],
        "footer": {"text": "MSA Trading Bot • © 2026"}
    }

def update_status_online():
    """تعديل رسالة الحالة إلى ONLINE — يُستدعى كل دورة"""
    if not CRITICAL_WEBHOOK:
        return

    message_id = _get_status_message_id()

    # لو ما في رسالة — أرسل جديدة
    if not message_id:
        try:
            r = requests.post(
                CRITICAL_WEBHOOK + "?wait=true",
                json={"embeds": [_build_status_embed(online=True)]},
                timeout=5
            )
            if r.status_code == 200:
                new_id = r.json().get('id')
                _save_status_message_id(new_id)
                print(f"✅ Status message created — ID: {new_id}")
        except Exception as e:
            print(f"⚠️ Status create error: {e}")
        return

    # عدّل الرسالة الموجودة
    try:
        parts  = CRITICAL_WEBHOOK.rstrip('/').split('/')
        wh_id  = parts[-2]
        wh_tok = parts[-1]
        url    = f"https://discord.com/api/webhooks/{wh_id}/{wh_tok}/messages/{message_id}"
        r = requests.patch(url, json={"embeds": [_build_status_embed(online=True)]}, timeout=5)

        # لو الرسالة محذوفة — أنشئ جديدة
        if r.status_code == 404:
            _status_message_id_reset()
            update_status_online()
    except Exception as e:
        print(f"⚠️ Status update error: {e}")

def _status_message_id_reset():
    global _status_message_id
    _status_message_id = None
    try:
        import os
        os.remove('data/status_id.txt')
    except:
        pass
