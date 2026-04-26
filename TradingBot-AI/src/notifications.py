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

def _fmt_price(price):
    """Format price smartly based on value"""
    if price >= 100:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"

def send_discord_embed(title, fields, color='blue', thumbnail_url=None, message_id=None, webhook_url=None):
    """Send or edit an embed message on Discord."""
    target_webhook = webhook_url if webhook_url else DISCORD_WEBHOOK
    if not target_webhook:
        return None

    colors = {
        'green':  0x00ff00,
        'red':    0xff0000,
        'blue':   0x0000ff,
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
        url    = f"{target_webhook}/messages/{message_id}"
        method = 'patch'
    else:
        url    = f"{target_webhook}?wait=true"
        method = 'post'

    try:
        response = requests.request(method, url, json=data, timeout=10)
        response.raise_for_status()

        if not response.text:
            return None
            
        return response.json()
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 404:
            print(f"ℹ️ Discord message {message_id} not found. It might have been deleted.")
        else:
            print(f"❌ Discord API Error: {e}")
        return None
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
        value: القيمة الإجمالية بالدولار (مثل$20.58)
        confidence: نسبة الثقة (0-100)
        realtime_data: Real-time Multi-Timeframe data
    """
    if amount >= 1:
        amount_format = f"{amount:.2f}"
    elif amount >= 0.01:
        amount_format = f"{amount:.4f}"
    elif amount >= 0.0001:
        amount_format = f"{amount:.6f}"
    else:
        amount_format = f"{amount:.8f}"
    
    fields = [
        {"name": "Pair",        "value": symbol,                  "inline": True},
        {"name": "Quantity",    "value": amount_format,            "inline": True},
        {"name": "Price",       "value": _fmt_price(price),         "inline": True},
        {"name": "Total Value", "value": f"${value:.2f}",          "inline": True},
        {"name": "Confidence",  "value": f"{confidence:.0f}/100",  "inline": True}
    ]
    
    if buy_vote_percentage is not None and buy_vote_count is not None and total_consultants is not None:
        fields.append({"name": "Buy Voting", "value": f"{buy_vote_percentage:.0f}% ({buy_vote_count}/{total_consultants} voted BUY)", "inline": False})
    
    if realtime_data and realtime_data.get('is_bottom'):
        rt_conf       = realtime_data.get('confidence', 0)
        confirmations = realtime_data.get('confirmations', 0)
        market_ctx    = realtime_data.get('market_context', 'N/A')
        threshold     = realtime_data.get('threshold_used', 60)
        
        rt_text  = f"⚡ **Multi-TF Bottom**: {rt_conf:.0f}% ({confirmations}/3 TF)\n"
        rt_text += f"Market: {market_ctx} | Threshold: {threshold}%"
        
        fields.append({"name": "Real-time Analysis", "value": rt_text, "inline": False})
    
    send_discord_embed("BUY SIGNAL", fields, 'green')
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
    if "TP" in reason or "FAST" in reason:
        signal_type = "TAKE PROFIT"
        color = 'green'
    elif "BEARISH" in reason:
        signal_type = "BEARISH EXIT"
        color = 'yellow'
    elif "STOP" in reason or "LOSS" in reason:
        signal_type = "STOP LOSS"
        color = 'yellow'
    else:
        signal_type = "SELL SIGNAL"
        color = 'yellow'
    
    profit_sign = "+" if profit_percent > 0 else ""
    
    if amount >= 1:
        amount_format = f"{amount:.2f}"
    elif amount >= 0.01:
        amount_format = f"{amount:.4f}"
    elif amount >= 0.0001:
        amount_format = f"{amount:.6f}"
    else:
        amount_format = f"{amount:.8f}"
    
    fields = [
        {"name": "Pair",        "value": symbol,                                "inline": True},
        {"name": "Quantity",    "value": amount_format,                          "inline": True},
        {"name": "Price",       "value": _fmt_price(price),                      "inline": True},
        {"name": "Total Value", "value": f"${value:.2f}",                       "inline": True},
        {"name": "Profit",      "value": f"{profit_sign}{profit_percent:.1f}%", "inline": True},
        {"name": "Reason",      "value": reason,                                "inline": False}
    ]
    
    if realtime_data and realtime_data.get('is_peak'):
        rt_conf       = realtime_data.get('confidence', 0)
        confirmations = realtime_data.get('confirmations', 0)
        market_ctx    = realtime_data.get('market_context', 'N/A')
        threshold     = realtime_data.get('threshold_used', 60)
        
        rt_text  = f"⚡ **Multi-TF Peak**: {rt_conf:.0f}% ({confirmations}/3 TF)\n"
        rt_text += f"Market: {market_ctx} | Threshold: {threshold}%"
        
        fields.append({"name": "Real-time Analysis", "value": rt_text, "inline": False})
    
    send_discord_embed(signal_type, fields, color)
    log_trade('SELL', symbol, amount, price, value, profit_percent, reason)

# Cooldown for the report to avoid rate limiting
last_report_sent_time = None
REPORT_COOLDOWN = timedelta(minutes=30)

def send_positions_report(balance, invested, active_count, max_positions, open_positions=None, exchange=None):
    """Send positions report with open positions details, respecting a cooldown."""
    global last_report_sent_time

    if not open_positions or len(open_positions) == 0:
        return

    if last_report_sent_time and (datetime.now(timezone.utc) - last_report_sent_time) < REPORT_COOLDOWN:
        return

    fields = [
        {"name": "Balance",          "value": f"${balance:.2f}",               "inline": True},
        {"name": "Invested",         "value": f"${invested:.2f}",              "inline": True},
        {"name": "Active Positions", "value": f"{active_count}/{max_positions}", "inline": True},
        {"name": "Available Slots",  "value": f"{max_positions - active_count}", "inline": True}
    ]
    
    positions_text = ""
    field_count    = 1
    sorted_positions = sorted(open_positions.items(), key=lambda item: item[0])

    for i, (symbol, pos_data) in enumerate(sorted_positions):
        buy_price      = pos_data.get('buy_price', 0)
        current_price  = pos_data.get('current_price', buy_price)
        profit_percent = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
        profit_sign    = "+" if profit_percent >= 0 else ""
        
        current_analysis = None
        if exchange:
            try:
                from analysis import get_market_analysis
                current_analysis = get_market_analysis(exchange, symbol, limit=120)
            except Exception as e:
                print(f"⚠️ Failed to get current analysis for {symbol}: {e}")
        
        if current_analysis:
            atr          = current_analysis.get('atr_percent', 2.5)
            rsi          = current_analysis.get('rsi', 50)
            volume_ratio = current_analysis.get('volume_ratio', 1.0)
            whale_score  = current_analysis.get('whale_confidence', 0)
            sentiment    = current_analysis.get('sentiment_score', 0)
            
            risk = 50
            if rsi > 70:            risk += 20
            elif rsi < 30:          risk -= 20
            if volume_ratio < 0.5:  risk += 15
            elif volume_ratio > 3:  risk += 10
        else:
            ai_data      = pos_data.get('ai_data', {})
            atr          = ai_data.get('atr_percent', 2.5)
            risk         = ai_data.get('risk_level', 50)
            whale_score  = ai_data.get('whale_confidence', 0)
            sentiment    = ai_data.get('sentiment_score', 0)
            volume_ratio = ai_data.get('volume_ratio', 1.0)
            rsi          = ai_data.get('rsi') or 50

        buy_confidence = pos_data.get('buy_confidence', 0)
        buy_amount     = pos_data.get('buy_amount', 0)

        sl_threshold = pos_data.get('stop_loss_threshold')

        if sl_threshold is None or sl_threshold == 6.0:
            # ✅ احسبه من atr مباشرة مثل Meta
            sl_threshold = atr * (1 + risk / 100)
            sl_threshold = max(1.0, min(15.0, sl_threshold))

        highest_price = pos_data.get('highest_price', buy_price)
        stop_price    = highest_price * (1 - sl_threshold / 100)

        advisor_votes   = pos_data.get('advisor_votes', {})
        buy_vote_count  = sum(1 for v in advisor_votes.values() if v == 1) if advisor_votes else 0
        total_advisors  = len(advisor_votes) if advisor_votes else 0
        vote_percentage = (buy_vote_count / total_advisors * 100) if total_advisors > 0 else 0

        sl_warning = ""
        sl_display = ""
        if profit_percent < -1.0:
            drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
            remaining      = sl_threshold - drop_from_peak
            sl_display     = f" | Stop: {sl_threshold:.1f}% (${stop_price:.4f})"
            
            if remaining < 0.5:
                sl_warning = f" 🚨 CRITICAL ({remaining:.1f}% left)"
            elif remaining < 1.5:
                sl_warning = f" ⚡ NEAR STOP ({remaining:.1f}% left)"
        
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
            field_count   += 1

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
        {"name": "Bot",        "value": "Trading Bot",                                           "inline": True},
        {"name": "Error Type", "value": error_type,                                              "inline": True},
        {"name": "Timestamp",  "value": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), "inline": True},
        {"name": "Message",    "value": message,                                                 "inline": False}
    ]
    
    if details:
        fields.append({"name": "Details", "value": str(details)[:1000], "inline": False})
    
    embed = {
        "title": "🚨 CRITICAL ALERT",
        "color": 0xff0000,
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

# ═══════════════════════════════════════════════════
# 📊 Advisor Report
# ═══════════════════════════════════════════════════

def send_advisor_report(signal_type, symbol, core_votes, meta_confidence,
                        support_data=None, total_points=None, required=None,
                        profit_percent=None, reason=None):
    """Send advisor voting report to critical channel - same style as BUY/SELL signals"""
    if not CRITICAL_WEBHOOK:
        return

    try:
        is_buy = signal_type.upper() == 'BUY'
        color = 'green' if is_buy else 'red'

        # Meta points
        meta_pts = (min(meta_confidence, 100) / 100) * 40

        # Advisor weights
        if is_buy:
            advisor_config = [
                ('candle_expert',   'Candle Expert',    8),
                ('chart_cnn',       'Chart CNN',        8),
                ('realtime_pa',     'RealTime PA',      8),
                ('multitimeframe',  'Multi-Timeframe',  4),
                ('fibonacci',       'Fibonacci',        5),
                ('smart_money',     'Smart Money',      5),
                ('volume_forecast', 'Volume Forecast',  2),
            ]
        else:
            advisor_config = [
                ('candle_expert',   'Candle Expert',    8),
                ('chart_cnn',       'Chart CNN',        8),
                ('realtime_pa',     'RealTime PA',      8),
                ('multitimeframe',  'Multi-Timeframe',  4),
                ('trend_detector',  'Trend Detector',   5),
                ('smart_money',     'Smart Money',      5),
                ('volume_forecast', 'Volume Forecast',  2),
            ]

        votes = core_votes or {}
        core_total = 0

        # Build fields - same style as BUY/SELL
        fields = [
            {"name": "Pair",           "value": symbol,                        "inline": True},
            {"name": "Signal",         "value": signal_type.upper(),           "inline": True},
            {"name": "Meta Trading",   "value": f"{meta_pts:.1f}/40 pts ({meta_confidence:.0f}%)", "inline": True},
        ]

        # Each advisor as inline field
        for key, label, max_pts in advisor_config:
            raw = votes.get(key, 0)
            pts = (raw / 100) * max_pts
            core_total += pts
            fields.append({
                "name": label,
                "value": f"{pts:.1f}/{max_pts} pts ({raw:.0f}%)",
                "inline": True
            })

        # Core total
        fields.append({"name": "Core Total", "value": f"{core_total:.1f}/40 pts", "inline": True})

        # Support data
        if support_data:
            sup = support_data
            sup_parts = []
            if 'rsi' in sup:
                sup_parts.append(f"RSI: {sup['rsi']:.0f}")
            if 'macd_diff' in sup:
                sup_parts.append(f"MACD: {sup['macd_diff']:+.2f}")
            if 'fear_greed' in sup:
                sup_parts.append(f"F&G: {sup['fear_greed']:.0f}")
            if 'volume_ratio' in sup:
                sup_parts.append(f"Vol: {sup['volume_ratio']:.1f}x")
            if 'prediction_1h' in sup:
                p1 = "Bullish" if sup.get('1h_bullish') else "Bearish" if sup.get('1h_bearish') else "Neutral"
                p4 = "Bullish" if sup.get('4h_bullish') else "Bearish" if sup.get('4h_bearish') else "Neutral"
                sup_parts.append(f"1h: {p1}")
                sup_parts.append(f"4h: {p4}")

            if sup_parts:
                sup_pts = 0
                if total_points is not None:
                    sup_pts = max(0, total_points - meta_pts - core_total)
                fields.append({
                    "name": "Support Inputs",
                    "value": f"{sup_pts:.1f} pts | " + " | ".join(sup_parts),
                    "inline": False
                })

        # Total Score
        total = total_points if total_points is not None else (meta_pts + core_total)
        total_text = f"{total:.0f}/100 pts"
        if required is not None:
            total_text += f" (Required: {required})"

        fields.append({"name": "Total Score", "value": total_text, "inline": True})

        # Profit (for SELL)
        if profit_percent is not None:
            profit_sign = "+" if profit_percent > 0 else ""
            fields.append({"name": "Profit", "value": f"{profit_sign}{profit_percent:.1f}%", "inline": True})

        # Reason
        if reason:
            fields.append({"name": "Reason", "value": reason, "inline": False})

        title = f"ADVISOR REPORT - {signal_type.upper()}"

        send_discord_embed(title, fields, color, webhook_url=CRITICAL_WEBHOOK)

    except Exception as e:
        print(f"⚠️ Advisor report error: {e}")
