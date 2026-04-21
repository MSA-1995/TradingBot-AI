"""
📱 Notifications Module
Handles Discord messages and file logging
"""

import requests
from datetime import datetime, timezone, timedelta
import os
from config_encrypted import get_discord_webhook, get_critical_webhook

DISCORD_WEBHOOK = get_discord_webhook()
CRITICAL_WEBHOOK = get_critical_webhook()

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
        import logging
        logging.exception("Discord send error")
        return None

def log_trade(action, symbol, amount, price, value, profit_percent=None, reason=""):
    """Log trade to file"""
    try:
        import os
        os.makedirs('data/trades', exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
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
        import logging
        logging.exception("Trade log error")

def send_buy_notification(symbol, amount, price, value, confidence, tp_target=None, sl_target=None, buy_vote_percentage=None, buy_vote_count=None, total_consultants=None, realtime_data=None):
    """Send buy notification
    
    Args:
        symbol: زوج التداول (مثل BTC/USDT)
        amount: الكمية بالعملة (مثل 0.00026 BTC)
        price: السعر الحالي (مثل $76208.03)
        value: القيمة الإجمالية بالدولار (مثل $20.58)
        confidence: نسبة الثقة (0-100)
        realtime_data: Real-time Multi-Timeframe data
    """
    # تحديد عدد الأرقام العشرية بناءً على حجم الكمية
    if amount >= 1:
        amount_format = f"{amount:.2f}"  # عملات كبيرة مثل BNB
    elif amount >= 0.01:
        amount_format = f"{amount:.4f}"  # عملات متوسطة
    elif amount >= 0.0001:
        amount_format = f"{amount:.6f}"  # عملات صغيرة مثل BTC
    else:
        amount_format = f"{amount:.8f}"  # عملات صغيرة جداً
    
    # Discord - احترافي
    fields = [
        {"name": "Pair", "value": symbol, "inline": True},
        {"name": "Quantity", "value": amount_format, "inline": True},
        {"name": "Price", "value": f"${price:,.0f}", "inline": True},  # بدون أرقام عشرية
        {"name": "Total Value", "value": f"${value:.2f}", "inline": True},
        {"name": "Confidence", "value": f"{confidence:.0f}/100", "inline": True}
    ]
    
    # Add buy voting results if available
    if buy_vote_percentage is not None and buy_vote_count is not None and total_consultants is not None:
        fields.append({"name": "Buy Voting", "value": f"{buy_vote_percentage:.0f}% ({buy_vote_count}/{total_consultants} voted BUY)", "inline": False})
    
    # ⚡ Add Real-time Multi-Timeframe data if available
    if realtime_data and realtime_data.get('is_bottom'):
        rt_conf = realtime_data.get('confidence', 0)
        confirmations = realtime_data.get('confirmations', 0)
        market_ctx = realtime_data.get('market_context', 'N/A')
        threshold = realtime_data.get('threshold_used', 60)
        
        rt_text = f"⚡ **Multi-TF Bottom**: {rt_conf:.0f}% ({confirmations}/3 TF)\n"
        rt_text += f"Market: {market_ctx} | Threshold: {threshold}%"
        
        fields.append({"name": "Real-time Analysis", "value": rt_text, "inline": False})
    
    send_discord_embed("BUY SIGNAL", fields, 'green')
    
    # Log
    log_trade('BUY', symbol, amount, price, value)

def send_sell_notification(symbol, amount, price, value, profit_percent, reason, realtime_data=None):
    """Send sell notification
    
    Args:
        symbol: زوج التداول (مثل BTC/USDT)
        amount: الكمية بالعملة (مثل 0.00026 BTC)
        price: السعر الحالي (مثل $76208.03)
        value: القيمة الإجمالية بالدولار (مثل $20.58)
        profit_percent: نسبة الربح (مثل +1.0%)
        reason: سبب البيع
        realtime_data: Real-time Multi-Timeframe data
    """
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
    
    # تحديد عدد الأرقام العشرية بناءً على حجم الكمية
    if amount >= 1:
        amount_format = f"{amount:.2f}"  # عملات كبيرة مثل BNB
    elif amount >= 0.01:
        amount_format = f"{amount:.4f}"  # عملات متوسطة
    elif amount >= 0.0001:
        amount_format = f"{amount:.6f}"  # عملات صغيرة مثل BTC
    else:
        amount_format = f"{amount:.8f}"  # عملات صغيرة جداً
    
    # Discord - احترافي مع القيم الصحيحة
    fields = [
        {"name": "Pair", "value": symbol, "inline": True},
        {"name": "Quantity", "value": amount_format, "inline": True},  # الكمية بالعملة
        {"name": "Price", "value": f"${price:,.0f}", "inline": True},  # بدون أرقام عشرية
        {"name": "Total Value", "value": f"${value:.2f}", "inline": True},  # القيمة الإجمالية
        {"name": "Profit", "value": f"{profit_sign}{profit_percent:.1f}%", "inline": True},
        {"name": "Reason", "value": reason, "inline": False}
    ]
    
    # ⚡ Add Real-time Multi-Timeframe data if available
    if realtime_data and realtime_data.get('is_peak'):
        rt_conf = realtime_data.get('confidence', 0)
        confirmations = realtime_data.get('confirmations', 0)
        market_ctx = realtime_data.get('market_context', 'N/A')
        threshold = realtime_data.get('threshold_used', 60)
        
        rt_text = f"⚡ **Multi-TF Peak**: {rt_conf:.0f}% ({confirmations}/3 TF)\n"
        rt_text += f"Market: {market_ctx} | Threshold: {threshold}%"
        
        fields.append({"name": "Real-time Analysis", "value": rt_text, "inline": False})
    
    send_discord_embed(signal_type, fields, color)
    
    # Log
    log_trade('SELL', symbol, amount, price, value, profit_percent, reason)

# Cooldown for the report to avoid rate limiting
last_report_sent_time = None
REPORT_COOLDOWN = timedelta(minutes=30)  # 30 دقيقة

def send_positions_report(balance, invested, active_count, max_positions, open_positions=None, exchange=None):
    """Send positions report with open positions details, respecting a cooldown."""
    global last_report_sent_time

    # ✅ لا ترسل التقرير إذا لم تكن هناك صفقات مفتوحة
    if not open_positions or len(open_positions) == 0:
        return

    # Check cooldown - كل 30 دقيقة
    if last_report_sent_time and (datetime.now(timezone.utc) - last_report_sent_time) < REPORT_COOLDOWN:
        return

    fields = [
        {"name": "Balance", "value": f"${balance:.2f}", "inline": True},
        {"name": "Invested", "value": f"${invested:.2f}", "inline": True},
        {"name": "Active Positions", "value": f"{active_count}/{max_positions}", "inline": True},
        {"name": "Available Slots", "value": f"{max_positions - active_count}", "inline": True}
    ]
    
    # إضافة تفاصيل الصفقات المفتوحة (مع تقسيم الحقول لتجنب حدود Discord)
    positions_text = ""
    field_count = 1
    sorted_positions = sorted(open_positions.items(), key=lambda item: item[0])

    for i, (symbol, pos_data) in enumerate(sorted_positions):
        buy_price = pos_data.get('buy_price', 0)
        current_price = pos_data.get('current_price', buy_price)
        profit_percent = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
        profit_sign = "+" if profit_percent >= 0 else ""
        
        # 🔄 جلب التحليل الحالي بدلاً من البيانات القديمة
        current_analysis = None
        if exchange:
            try:
                from analysis import get_market_analysis
                current_analysis = get_market_analysis(exchange, symbol, limit=120)
            except Exception as e:
                print(f"⚠️ Failed to get current analysis for {symbol}: {e}")
        
        # استخدام التحليل الحالي إذا متوفر، وإلا استخدام البيانات القديمة
        if current_analysis:
            atr = current_analysis.get('atr_percent', 2.5)
            rsi = current_analysis.get('rsi', 50)
            volume_ratio = current_analysis.get('volume_ratio', 1.0)
            whale_score = current_analysis.get('whale_confidence', 0)
            sentiment = current_analysis.get('sentiment_score', 0)
            
            # حساب risk_level من المؤشرات الحالية
            risk = 50
            if rsi > 70: risk += 20
            elif rsi < 30: risk -= 20
            if volume_ratio < 0.5: risk += 15
            elif volume_ratio > 3: risk += 10
        else:
            # Fallback للبيانات القديمة
            ai_data = pos_data.get('ai_data', {})
            atr = ai_data.get('atr_percent', 2.5)
            risk = ai_data.get('risk_level', 50)
            whale_score = ai_data.get('whale_confidence', 0)
            sentiment = ai_data.get('sentiment_score', 0)
            volume_ratio = ai_data.get('volume_ratio', 1.0)
            rsi = ai_data.get('rsi', 50)
        
        buy_confidence = pos_data.get('buy_confidence', 0)
        buy_amount = pos_data.get('buy_amount', 0)
        
        # 🛡️ قراءة Stop Loss من position (محفوظ من meta.py)
        sl_threshold = pos_data.get('stop_loss_threshold')
        
        # إذا غير موجود (صفقات قديمة)، احسبه
        if sl_threshold is None:
            # حساب Stop Loss ديناميكياً (نفس meta.py)
            base_threshold = atr * 2.5
            min_threshold = risk / 25
            base_threshold = max(min_threshold, base_threshold)
            risk_modifier = (risk - 50) / 100
            base_threshold += risk_modifier * 3
            whale_modifier = whale_score / 200
            base_threshold -= whale_modifier * 2
            sentiment_modifier = max(-10, min(10, sentiment)) / 100
            base_threshold += sentiment_modifier * 2
            sl_threshold = max(1.0, min(15.0, base_threshold))
        
        highest_price = pos_data.get('highest_price', buy_price)
        stop_price = highest_price * (1 - sl_threshold / 100)
        
        # ⚡ تحذير Stop Loss فقط للصفقات الخاسرة أكثر من 1.0%
        sl_warning = ""
        sl_display = ""  # عرض Stop Loss فقط للخاسرة
        if profit_percent < -1.0:
            drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
            remaining = sl_threshold - drop_from_peak
            
            # عرض Stop Loss
            sl_display = f" | Stop: {sl_threshold:.1f}% (${stop_price:.4f})"
            
            if remaining < 0.5:
                sl_warning = f" 🚨 CRITICAL ({remaining:.1f}% left)"
            elif remaining < 1.5:
                sl_warning = f" ⚡ NEAR STOP ({remaining:.1f}% left)"
        
        # جلب بيانات التصويت (إذا متوفرة)
        advisor_votes = pos_data.get('advisor_votes', {})
        buy_vote_count = sum(1 for v in advisor_votes.values() if v == 1) if advisor_votes else 0
        total_advisors = len(advisor_votes) if advisor_votes else 0
        vote_percentage = (buy_vote_count / total_advisors * 100) if total_advisors > 0 else 0
        
        entry = (
            f"**{symbol}**\n"
            f"Buy: ${buy_price:.4f} | Amount: ${buy_amount:.2f} | Now: ${current_price:.4f}\n"
            f"P/L: {profit_sign}{profit_percent:.2f}%{sl_display}{sl_warning}\n"
            f"Confidence: {buy_confidence:.0f}% | Votes: {buy_vote_count}/{total_advisors} ({vote_percentage:.0f}%)\n"
            f"RSI: {rsi:.0f} | Vol: {volume_ratio:.1f}x | Whale: {whale_score:+.0f}\n\n"
        )
        
        if len(positions_text) + len(entry) > 1024:
            field_name = f"Open Positions ({field_count})"
            fields.append({"name": field_name, "value": positions_text.strip(), "inline": False})
            positions_text = ""
            field_count += 1

        positions_text += entry

    if positions_text:
        field_name = f"Open Positions ({field_count})" if field_count > 1 else "Open Positions"
        fields.append({"name": field_name, "value": positions_text.strip(), "inline": False})
    
    send_discord_embed(
        "PORTFOLIO REPORT",
        fields,
        color='blue',
        webhook_url=CRITICAL_WEBHOOK
    )

    last_report_sent_time = datetime.now(timezone.utc)




def send_critical_alert(error_type, message, details=None):
    """Send critical error alert to Discord"""
    if not CRITICAL_WEBHOOK:
        return
    
    fields = [
        {"name": "Bot", "value": "Trading Bot", "inline": True},
        {"name": "Error Type", "value": error_type, "inline": True},
        {"name": "Timestamp", "value": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), "inline": True},
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
    except Exception as e:
        print(f"⚠️ Failed to send critical alert: {e}")
        import logging
        logging.exception("Critical alert send error")

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
