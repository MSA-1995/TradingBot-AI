import pandas as pd
from datetime import datetime
import time
import numpy as np

class MacroTrendAdvisor:
    """
    يحدد ما إذا كان السوق في دورة صعود كبرى (Bull Market Cycle)
    لاستهداف أرباح 50% - 80% بناءً على الفريم اليومي.
    """
    def __init__(self, exchange=None):
        self.exchange = exchange
        self._last_status = "NEUTRAL"
        self._last_check_time = 0
        self._cache_duration = 300  # تحديث كل 5 دقائق

    def get_macro_status(self):
        if not self.exchange: return "⚪ NEUTRAL"

        current_time = time.time()
        if current_time - self._last_check_time < self._cache_duration:
            return self._last_status

        try:
            # فحص عدة عملات لتحديد الاتجاه الماكرو
            symbols = ['BTC/USDT', 'BNB/USDT', 'ETH/USDT']
            statuses = []

            for symbol in symbols:
                try:
                    ohlcv = self.exchange.fetch_ohlcv(symbol, '4h', limit=50)
                    df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

                    available_days = len(df)
                    if available_days < 10:
                        continue

                    current_price = df['c'].iloc[-1]

                    # تحليل متقدم: SMA + EMA + RSI
                    if available_days >= 20:
                        sma_20 = df['c'].rolling(20).mean().iloc[-1]
                        ema_20 = df['c'].ewm(span=20).mean().iloc[-1]

                        # حساب RSI للفريم اليومي
                        delta = df['c'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rs = gain / loss
                        rsi = 100 - (100 / (1 + rs))
                        current_rsi = rsi.iloc[-1]

                        # حساب Momentum
                        momentum = ((current_price - df['c'].iloc[-10]) / df['c'].iloc[-10]) * 100

                        # تحديد الحالة للعملة الحالية
                        if abs(momentum) < 0.1 and abs(current_rsi - 50) < 5:  # سوق ميت أو جانبي
                            coin_status = "SIDEWAYS"
                        elif current_price > sma_20 * 1.05 and current_price > ema_20 and current_rsi > 60 and momentum > 5:
                            coin_status = "STRONG_BULL_MARKET"
                        elif current_price > sma_20 and current_price > ema_20 and current_rsi > 50:
                            coin_status = "BULL_MARKET"
                        elif current_price < sma_20 * 0.95 and current_price < ema_20 and current_rsi < 40:
                            coin_status = "STRONG_BEAR_MARKET"
                        elif current_price < sma_20 and current_price < ema_20:
                            coin_status = "BEAR_MARKET"
                        else:
                            coin_status = "SIDEWAYS"

                    elif available_days >= 10:
                        sma_10 = df['c'].rolling(10).mean().iloc[-1]

                        if current_price > sma_10 * 1.05:
                            coin_status = "STRONG_BULL_MARKET"
                        elif current_price > sma_10:
                            coin_status = "BULL_MARKET"
                        else:
                            coin_status = "BEAR_MARKET"
                    else:
                        coin_status = "NEUTRAL"

                    statuses.append(coin_status)

                except Exception as e:
                    print(f"⚠️ Error fetching {symbol}: {e}")
                    continue

            # تحديد الاتجاه الماكرو بناءً على أغلبية العملات
            if not statuses:
                final_status = "⚪ NEUTRAL"
            else:
                from collections import Counter
                status_counts = Counter(statuses)
                most_common = status_counts.most_common(1)[0][0]

                # إضافة الإيموجي حسب النوع
                if "BULL" in most_common:
                    final_status = f"🟢 {most_common}"
                elif "BEAR" in most_common:
                    final_status = f"🔴 {most_common}"
                else:
                    final_status = f"⚪ {most_common}"

            self._last_status = final_status
            self._last_check_time = current_time
            return final_status
            
        except Exception as e:
            return "NEUTRAL"

    def can_aim_high(self):
        """هل يمكن استهداف 80% ربح؟ (يعطي الضوء الأخضر فقط في البول ماركت)"""
        status = self.get_macro_status()
        return status in ["STRONG_BULL_MARKET", "BULL_MARKET"]