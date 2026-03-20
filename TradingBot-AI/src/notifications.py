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

# ========== BOT STATUS (Pinned Message) ==========
# Always resolve relative to the project root (parent of src/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATUS_FILE = os.path.join(_PROJECT_ROOT, 'data', 'bot_status_message_id.txt')
_BOT_START_TIME = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')


def _parse_webhook(url):
    """Extract (webhook_id, token) from a webhook URL"""
    try:
        parts = url.rstrip('/').split('/')
        return parts[-2], parts[-1]
    except:
        return None, None


def _load_status_message_id():
    try:
        if os.path.exists(_STATUS_FILE):
            with open(_STATUS_FILE, 'r') as f:
                return f.read().strip() or None
    except:
        pass
    return None


def _save_status_message_id(msg_id):
    try:
        os.makedirs(os.path.dirname(_STATUS_FILE), exist_ok=True)
        with open(_STATUS_FILE, 'w') as f:
            f.write(str(msg_id))
        print(f"📡 [Status] ID saved to: {_STATUS_FILE}")
    except Exception as e:
        print(f"📡 [Status] ❌ Could not save message ID: {e}")


def _build_status_embed(is_online, last_heartbeat=None):
    ts = last_heartbeat or datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    if is_online:
        return {
            "title": "📡  MSA Trading Bot — Status",
            "description": "# 🟢  ONLINE",
            "color": 0x00c851,
            "fields": [
                {"name": "▸ Started",        "value": _BOT_START_TIME, "inline": True},
                {"name": "▸ Last Heartbeat", "value": ts,              "inline": True},
            ],
            "footer": {"text": "MSA Trading Bot • Updates every 5 min automatically"},
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        return {
            "title": "📡  MSA Trading Bot — Status",
            "description": "# 🔴  OFFLINE",
            "color": 0xff4444,
            "fields": [
                {"name": "▸ Was Online Since", "value": _BOT_START_TIME, "inline": True},
                {"name": "▸ Went Offline",     "value": ts,              "inline": True},
            ],
            "footer": {"text": "MSA Trading Bot • Critical Alerts"},
            "timestamp": datetime.utcnow().isoformat()
        }


def _post_or_edit_status(is_online, last_heartbeat=None):
    """Create or silently edit the persistent status message in the critical channel."""
    if not CRITICAL_WEBHOOK:
        print("⚠️ [Status] CRITICAL_WEBHOOK is empty — skipping status message")
        return

    webhook_id, token = _parse_webhook(CRITICAL_WEBHOOK)
    if not webhook_id:
        print("⚠️ [Status] Could not parse webhook URL")
        return

    embed = _build_status_embed(is_online, last_heartbeat)
    payload = {"embeds": [embed]}
    msg_id = _load_status_message_id()
    status_label = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
    print(f"📡 [Status] ID file: {_STATUS_FILE}")
    print(f"📡 [Status] Loaded ID: {msg_id}")

    try:
        if msg_id:
            url = f"https://discord.com/api/webhooks/{webhook_id}/{token}/messages/{msg_id}"
            resp = requests.patch(url, json=payload, timeout=5)
            print(f"📡 [Status] EDIT {status_label} → HTTP {resp.status_code}")
            if resp.status_code == 404:
                print("📡 [Status] Message not found — will create new one")
                msg_id = None
            elif resp.status_code not in (200, 204):
                print(f"📡 [Status] Edit error: {resp.text[:200]}")

        if not msg_id:
            url = f"https://discord.com/api/webhooks/{webhook_id}/{token}?wait=true"
            resp = requests.post(url, json=payload, timeout=5)
            print(f"📡 [Status] POST {status_label} → HTTP {resp.status_code}")
            if resp.status_code in (200, 201):
                new_id = resp.json()['id']
                _save_status_message_id(new_id)
                print(f"📡 [Status] Message ID saved: {new_id}")
            else:
                print(f"📡 [Status] Post error: {resp.text[:200]}")
    except requests.exceptions.ConnectionError:
        print("📡 [Status] ❌ Connection error — no internet?")
    except requests.exceptions.Timeout:
        print("📡 [Status] ❌ Timeout — Discord didn't respond")
    except Exception as e:
        print(f"📡 [Status] ❌ Unexpected error: {e}")


def send_bot_online_status():
    """Call once on startup — shows 🟢 ONLINE in the critical channel."""
    global _BOT_START_TIME
    _BOT_START_TIME = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    _post_or_edit_status(is_online=True)


def send_bot_offline_status():
    """Call on shutdown — switches the status message to 🔴 OFFLINE."""
    # Clear the start time to show accurate offline time
    global _BOT_START_TIME
    _BOT_START_TIME = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    # Try to edit existing message first, then create new one if needed
    _post_or_edit_status(
        is_online=False,
        last_heartbeat=datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    )


def update_status_heartbeat():
    """Call periodically — updates the 'Last Heartbeat' timestamp silently (no new messages)."""
    # Force update by clearing the message ID to create a new one
    global _BOT_START_TIME
    _BOT_START_TIME = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    _post_or_edit_status(
        is_online=True,
        last_heartbeat=datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    )


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
