"""
🤪 Rescue Scalper (The Crazy Jester) - منقذ الصفقات الزومبي
يستلم العملات الميتة (> 72 ساعة) ويحاول الخروج منها بذكاء (Micro-Scalping)
الاستراتيجية: انتظر أي شمعة خضراء أو ارتداد لحظي واهرب!
"""

class RescueScalper:
    def __init__(self):
        print("🤪 Rescue Scalper (The Crazy Jester) initialized - Ready to rescue zombies!")

    def get_exit_decision(self, symbol, analysis, current_profit):
        """
        قرار الخروج السريع: هل نبيع الآن أم ننتظر شمعة خضراء؟
        """
        try:
            # استخراج البيانات اللحظية
            rsi = analysis.get('rsi', 50)
            macd_diff = analysis.get('macd_diff', 0)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            
            # تحليل الشموع الأخيرة (نحتاج شمعة خضراء)
            df = analysis.get('df')
            is_green_candle = False
            is_recovering = False
            
            if df is not None and not df.empty:
                last_candle = df.iloc[-1]
                close_p = last_candle['close']
                open_p = last_candle['open']
                
                # هل الشمعة الحالية خضراء؟
                if close_p > open_p:
                    is_green_candle = True
                
                # هل هناك ذيل سفلي طويل (رفض للهبوط)؟
                low_p = last_candle['low']
                body = abs(close_p - open_p)
                lower_wick = min(close_p, open_p) - low_p
                if lower_wick > body:
                    is_recovering = True

            # ---------------------------------------------------------
            # منطق الخبل (Scenario A: Smart Exit)
            # ---------------------------------------------------------
            
            # 1. إذا كان فيه ربح ولو بسيط (+0.2%) -> بيع فوراً (لا تطمع)
            if current_profit > 0.2:
                return {
                    'action': 'SELL',
                    'reason': 'Crazy Rescue: Secured small profit (+0.2%)'
                }

            # 2. إذا الشمعة خضراء والزخم يتحسن -> بيع (استغلال الارتداد)
            if is_green_candle and rsi > 40:
                return {
                    'action': 'SELL',
                    'reason': 'Crazy Rescue: Sold on Green Candle'
                }

            # 3. إذا كان RSI مرتفع نسبياً (> 50) -> فرصة خروج ممتازة
            if rsi > 50:
                return {
                    'action': 'SELL',
                    'reason': 'Crazy Rescue: RSI Recovery (>50)'
                }

            # 4. إذا كان MACD بدأ يقلب إيجابي -> بيع
            if macd_diff > 0:
                return {
                    'action': 'SELL',
                    'reason': 'Crazy Rescue: MACD Flip'
                }
            
            # الحالة الافتراضية: انتظر (HOLD)
            return {'action': 'HOLD', 'reason': 'Crazy Rescue: Waiting for ANY green candle'}

        except Exception as e:
            print(f"⚠️ Rescue error: {e}")
            return {'action': 'SELL', 'reason': 'Rescue Error (Emergency Exit)'}