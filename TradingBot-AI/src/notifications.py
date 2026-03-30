"""
📱 Notifications Module
Handles Discord messages and file logging
"""

import requests
from datetime import datetime, timezone, timedelta
import os
from config import STATUS_STORAGE_METHOD
from config_encrypted import get_discord_webhook, get_critical_webhook

DISCORD_WEBHOOK = get_discord_webhook()
CRITICAL_WEBHOOK = get_critical_webhook()
STATUS_MESSAGE_ID = None # Global variable to hold the message ID
STATUS_MESSAGE_ID_FILE = os.path.join('data', 'bot_status_message_id.txt')

def load_status_message_id():
    """Load the status message ID from the configured storage (db or file)."""
    global STATUS_MESSAGE_ID
    if STATUS_STORAGE_METHOD == 'database':
        from database import get_db_connection # Conditional import
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_settings WHERE key = 'status_message_id'")
            row = cursor.fetchone()
            conn.close()
            if row:
                STATUS_MESSAGE_ID = row[0]
                print(f"✅ Loaded status message ID from database: {STATUS_MESSAGE_ID}")
            else:
                print("🤔 No status message ID found in database. A new one will be created.")
        except Exception as e:
            print(f"❌ Error loading status message ID from database: {e}")
            STATUS_MESSAGE_ID = None
    else: # file method
        try:
            if os.path.exists(STATUS_MESSAGE_ID_FILE):
                with open(STATUS_MESSAGE_ID_FILE, 'r') as f:
                    STATUS_MESSAGE_ID = f.read().strip()
                    print(f"✅ Loaded status message ID from file: {STATUS_MESSAGE_ID}")
            else:
                print("🤔 No status message ID file found. A new one will be created.")
        except Exception as e:
            print(f"❌ Error loading status message ID from file: {e}")
            STATUS_MESSAGE_ID = None

def save_status_message_id(message_id):
    """Save the status message ID to the configured storage (db or file)."""
    global STATUS_MESSAGE_ID
    if STATUS_STORAGE_METHOD == 'database':
        from database import get_db_connection # Conditional import
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, ('status_message_id', message_id))
            conn.commit()
            conn.close()
            STATUS_MESSAGE_ID = message_id
            print(f"💾 Saved status message ID to database: {message_id}")
        except Exception as e:
            print(f"❌ Error saving status message ID to database: {e}")
    else: # file method
        try:
            os.makedirs('data', exist_ok=True)
            with open(STATUS_MESSAGE_ID_FILE, 'w') as f:
                f.write(str(message_id))
            STATUS_MESSAGE_ID = str(message_id)
            #print(f"💾 Saved status message ID to file: {message_id}")
        except Exception as e:
            print(f"❌ Error saving status message ID to file: {e}")

def send_discord_embed(title, fields, color='blue', thumbnail_url=None, message_id=None, webhook_url=None):
    """Send or edit an embed message on Discord."""
    target_webhook = webhook_url if webhook_url else DISCORD_WEBHOOK
    if not target_webhook:
        return None

    colors = {
        'green': 0x00ff00,
        'red': 0xff0000,
        'blue': 0x0000ff,
        'yellow': 0xffff00,
        'purple': 0x800080
    }

    embed = {
        "title": title,
        "color": colors.get(color, 0x0000ff),
        "fields": fields,
        "footer": {
            "text": "MSA Trading Bot • AI Powered"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    data = {"embeds": [embed]}
    
    if message_id:
        url = f"{target_webhook}/messages/{message_id}"
        method = 'patch'
    else:
        # wait=true is required to get the message object back, which contains the ID.
        url = f"{target_webhook}?wait=true"
        method = 'post'

    try:
        response = requests.request(method, url, json=data, timeout=10)
        response.raise_for_status()

        # If the response is empty, we can't get an ID from it.
        if not response.text:
            return None
            
        return response.json()  # Return the JSON response which includes the message ID
    except requests.exceptions.RequestException as e:
        # If the message is not found, it's a 404 error.
        if e.response and e.response.status_code == 404:
            print(f"ℹ️ Discord message {message_id} not found. It might have been deleted.")
        else:
            print(f"❌ Discord API Error: {e}")
        return None # Return None on failure
    except Exception as e:
        print(f"❌ An unexpected error occurred while sending to Discord: {e}")
        return None

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
        {"name": "Confidence", "value": f"{confidence}/100", "inline": True}
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

# Cooldown for the report to avoid rate limiting
last_report_sent_time = None
REPORT_COOLDOWN = timedelta(seconds=60)

def send_positions_report(balance, invested, active_count, max_positions, open_positions=None):
    """Send positions report with open positions details, respecting a cooldown."""
    global last_report_sent_time

    # Check cooldown
    if last_report_sent_time and (datetime.now() - last_report_sent_time) < REPORT_COOLDOWN:
        return # Exit if we are in the cooldown period

    fields = [
        {"name": "Balance", "value": f"${balance:.2f}", "inline": True},
        {"name": "Invested", "value": f"${invested:.2f}", "inline": True},
        {"name": "Active Positions", "value": f"{active_count}/{max_positions}", "inline": True},
        {"name": "Available Slots", "value": f"{max_positions - active_count}", "inline": True}
    ]
    
    # إضافة تفاصيل الصفقات المفتوحة (مع تقسيم الحقول لتجنب حدود Discord)
    if open_positions and len(open_positions) > 0:
        positions_text = ""
        field_count = 1
        # Sort positions for consistent reporting
        sorted_positions = sorted(open_positions.items(), key=lambda item: item[0])

        for i, (symbol, pos_data) in enumerate(sorted_positions):
            buy_price = pos_data.get('buy_price', 0)
            current_price = pos_data.get('current_price', buy_price)
            profit_percent = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
            profit_sign = "+" if profit_percent >= 0 else ""
            
            # نفرق بين الصفقات المفتوحة وفرص الشراء
            is_opportunity = pos_data.get('is_opportunity', False)
            
            if is_opportunity:
                # فرصة شراء قوية
                entry = (
                    f"🎯 **{symbol}** (فرصة شراء)\n"
                    f"السعر الحالي: ${current_price:.4f}\n"
                    f"السبب: {pos_data.get('strength_reason', 'تحليل فني قوي')}\n\n"
                )
            else:
                # صفقة مفتوحة
                entry = (
                    f"**{symbol}**\n"
                    f"Buy: ${buy_price:.4f} | Now: ${current_price:.4f}\n"
                    f"P/L: {profit_sign}{profit_percent:.2f}%\n\n"
                )
            
            # Discord embed field value limit is 1024 chars
            if len(positions_text) + len(entry) > 1024:
                field_name = f"Open Positions ({field_count})"
                fields.append({"name": field_name, "value": positions_text.strip(), "inline": False})
                positions_text = "" # Reset for the next field
                field_count += 1

            positions_text += entry

        # Add the last or only field
        if positions_text:
            field_name = f"Open Positions ({field_count})" if field_count > 1 else "Open Positions"
            fields.append({"name": field_name, "value": positions_text.strip(), "inline": False})
    
    # --- FIX: Send the actual embed message ---
    global STATUS_MESSAGE_ID
    # Try to edit the existing message, or create a new one
    response_data = send_discord_embed(
        "PORTFOLIO REPORT",
        fields,
        color='blue',
        message_id=None # دائماً أرسل رسالة جديدة
    )

    if response_data:
        new_message_id = response_data.get('id')
        if new_message_id and new_message_id != STATUS_MESSAGE_ID:
            save_status_message_id(new_message_id)
    else:
        # If sending failed (e.g., message was deleted), clear the ID
        # so we create a new one next time.
        if STATUS_MESSAGE_ID:
            print("ℹ️ Failed to update status message. Will create a new one on next report.")
            save_status_message_id(None) # Clear the invalid ID
    # --- END FIX ---

    # Update the last sent time at the end of the function
    last_report_sent_time = datetime.now()




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
        "timestamp": datetime.now(timezone.utc).isoformat()
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


def send_exchange_error(error_message):
    """Send exchange API error alert"""
    send_critical_alert(
        "Exchange API Error",
        "Failed to connect to Binance",
        error_message
    )
