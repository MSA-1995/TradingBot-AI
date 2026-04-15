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
        self._cache_duration = 300  # تحديث كل 5 دقائق فقط لتوفير الطلبات

    def get_macro_status(self):
        if not self.exchange: return "NEUTRAL"
        
        current_time = time.time()
        if current_time - self._last_check_time < self._cache_duration:
            return self._last_status

        try:
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1d', limit=50)
            df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            
            available_days = len(df)
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
                
                print(f"\n🌐 [Macro] BTC: ${current_price:,.2f} | SMA20: ${sma_20:,.2f} | EMA20: ${ema_20:,.2f} | RSI: {current_rsi:.1f} | Momentum: {momentum:.1f}%")
                
                # تحديد الحالة بناءً على مؤشرات متعددة
                if current_price > sma_20 * 1.05 and current_price > ema_20 and current_rsi > 60 and momentum > 5:
                    status = "STRONG_BULL_MARKET"
                elif current_price > sma_20 and current_price > ema_20 and current_rsi > 50:
                    status = "BULL_MARKET"
                elif current_price < sma_20 * 0.95 and current_price < ema_20 and current_rsi < 40:
                    status = "STRONG_BEAR_MARKET"
                elif current_price < sma_20 and current_price < ema_20:
                    status = "BEAR_MARKET"
                else:
                    status = "SIDEWAYS"
                
            elif available_days >= 10:
                sma_10 = df['c'].rolling(10).mean().iloc[-1]
                
                if current_price > sma_10 * 1.05:
                    status = "STRONG_BULL_MARKET"
                elif current_price > sma_10:
                    status = "BULL_MARKET"
                else:
                    status = "BEAR_MARKET"
            else:
                print(f"\n⚠️ [Macro] Insufficient data (Need 10+ days, got {available_days})")
                status = "NEUTRAL"
            
            self._last_status = status
            self._last_check_time = current_time
            return status
            
        except Exception as e:
            return "NEUTRAL"

    def can_aim_high(self):
        """هل يمكن استهداف 80% ربح؟ (يعطي الضوء الأخضر فقط في البول ماركت)"""
        status = self.get_macro_status()
        return status in ["STRONG_BULL_MARKET", "BULL_MARKET"]
