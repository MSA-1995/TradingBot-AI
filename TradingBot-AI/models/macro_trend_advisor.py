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
        
        # استخدام الكاش إذا لم تنتهِ الـ 5 دقائق
        current_time = time.time()
        if current_time - self._last_check_time < self._cache_duration:
            return self._last_status

        try:
            # تحليل البتكوين على فريم يومي كمرجع للسوق العالمي
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1d', limit=50)
            df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            
            available_days = len(df)
            current_price = df['c'].iloc[-1]
            
            # ✅ نظام البديل الديناميكي (SMA20 أو SMA10 كبديل للـ Testnet)
            if available_days >= 20:
                sma_value = df['c'].rolling(20).mean().iloc[-1]
                sma_label = "SMA20"
            elif available_days >= 10:
                sma_value = df['c'].rolling(10).mean().iloc[-1]
                sma_label = "SMA10 (Fallback)"
            else:
                print(f"\n⚠️ [Macro Check] Insufficient data even for fallback (Need 10+ days, got {available_days})")
                self._last_status = "NEUTRAL"
                self._last_check_time = current_time
                return "NEUTRAL"

            # طباعة التأكيد مع توضيح نوع المتوسط المستخدم حالياً
            print(f"\n🌐 [Macro Check] BTC: ${current_price:,.2f} | {sma_label}: ${sma_value:,.2f}")

            # اتخاذ القرار بناءً على المتوسط المتاح
            if current_price > sma_value * 1.05:
                status = "STRONG_BULL_MARKET"
            elif current_price > sma_value:
                status = "BULL_MARKET"
            else:
                status = "BEAR_MARKET"
            
            self._last_status = status
            self._last_check_time = current_time
            return status
            
        except Exception as e:
            # print(f"⚠️ Macro Advisor Error: {e}")
            return "NEUTRAL"

    def can_aim_high(self):
        """هل يمكن استهداف 80% ربح؟ (يعطي الضوء الأخضر فقط في البول ماركت)"""
        status = self.get_macro_status()
        return status in ["STRONG_BULL_MARKET", "BULL_MARKET"]