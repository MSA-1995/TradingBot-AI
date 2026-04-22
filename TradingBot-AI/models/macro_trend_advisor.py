"""
📈 Macro Trend Advisor - مستشار الاتجاه الكلي
يحدد ما إذا كان السوق في دورة صعود كبرى (Bull Market Cycle)
لاستهداف أرباح 50% - 80% بناءً على الفريم اليومي.
"""

import time
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd


class MacroTrendAdvisor:
    """
    يحدد ما إذا كان السوق في دورة صعود كبرى (Bull Market Cycle)
    لاستهداف أرباح 50% - 80% بناءً على الفريم اليومي.
    """

    # العملات المستخدمة لتحليل الاتجاه الكلي
    MACRO_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']

    # إعدادات الكاش
    CACHE_DURATION = 300  # 5 دقائق

    # إعدادات التحليل
    OHLCV_LIMIT        = 50
    TIMEFRAME          = '4h'
    RSI_PERIOD         = 14
    MOMENTUM_LOOKBACK  = 10

    # حدود الحالات
    STRONG_BULL_THRESHOLD  = 1.05   # 5%  فوق SMA
    STRONG_BEAR_THRESHOLD  = 0.95   # 5%  تحت SMA
    BULL_RSI_MIN           = 50
    STRONG_BULL_RSI_MIN    = 60
    BEAR_RSI_MAX           = 40
    STRONG_BULL_MOMENTUM   = 5.0    # 5%  momentum
    SIDEWAYS_MOMENTUM_MAX  = 0.1
    SIDEWAYS_RSI_RANGE     = 5      # ±5 من 50

    # إيموجي الحالات
    STATUS_EMOJI = {
        'BULL': '🟢',
        'BEAR': '🔴',
        'OTHER': '⚪'
    }

    def __init__(self, exchange=None):
        self.exchange = exchange
        self._last_status: str      = '⚪ NEUTRAL'
        self._last_check_time: float = 0.0

    # ─────────────────────────────────────────────
    # الواجهة الرئيسية
    # ─────────────────────────────────────────────

    def get_macro_status(self) -> str:
        """جلب حالة السوق الكلية مع الكاش"""
        if not self.exchange:
            return '⚪ NEUTRAL'

        # إرجاع الكاش إذا لم ينته
        if time.time() - self._last_check_time < self.CACHE_DURATION:
            return self._last_status

        try:
            statuses = self._collect_symbol_statuses()
            final_status = self._determine_final_status(statuses)

            self._last_status      = final_status
            self._last_check_time  = time.time()
            return final_status

        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor get_macro_status error: {e}")
            return '⚪ NEUTRAL'

    def can_aim_high(self) -> bool:
        """هل يمكن استهداف 80% ربح؟ (الضوء الأخضر في Bull Market فقط)"""
        status = self.get_macro_status()
        return 'BULL' in status

    def invalidate_cache(self) -> None:
        """مسح الكاش لإجبار التحديث"""
        self._last_check_time = 0.0

    # ─────────────────────────────────────────────
    # جمع البيانات
    # ─────────────────────────────────────────────

    def _collect_symbol_statuses(self) -> list[str]:
        """جلب وتحليل كل العملات"""
        statuses = []

        for symbol in self.MACRO_SYMBOLS:
            try:
                status = self._analyze_symbol(symbol)
                if status:
                    statuses.append(status)
            except Exception as e:
                print(f"⚠️ MacroTrendAdvisor error fetching {symbol}: {e}")

        return statuses

    def _analyze_symbol(self, symbol: str) -> Optional[str]:
        """تحليل عملة واحدة وإرجاع حالتها"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, self.TIMEFRAME, limit=self.OHLCV_LIMIT)
        df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

        available = len(df)
        if available < 10:
            return None

        current_price = float(df['c'].iloc[-1])

        if available >= 20:
            return self._analyze_full(df, current_price)
        else:
            return self._analyze_simple(df, current_price)

    # ─────────────────────────────────────────────
    # التحليل
    # ─────────────────────────────────────────────

    def _analyze_full(self, df: pd.DataFrame, current_price: float) -> str:
        """تحليل متكامل: SMA + EMA + RSI + Momentum"""
        sma_20 = float(df['c'].rolling(20).mean().iloc[-1])
        ema_20 = float(df['c'].ewm(span=20).mean().iloc[-1])
        rsi    = self._calculate_rsi(df['c'])
        momentum = self._calculate_momentum(df['c'], current_price)

        # سوق جانبي
        if (abs(momentum) < self.SIDEWAYS_MOMENTUM_MAX
                and abs(rsi - 50) < self.SIDEWAYS_RSI_RANGE):
            return 'SIDEWAYS'

        # Bull قوي
        if (current_price > sma_20 * self.STRONG_BULL_THRESHOLD
                and current_price > ema_20
                and rsi > self.STRONG_BULL_RSI_MIN
                and momentum > self.STRONG_BULL_MOMENTUM):
            return 'STRONG_BULL_MARKET'

        # Bull عادي
        if (current_price > sma_20
                and current_price > ema_20
                and rsi > self.BULL_RSI_MIN):
            return 'BULL_MARKET'

        # Bear قوي
        if (current_price < sma_20 * self.STRONG_BEAR_THRESHOLD
                and current_price < ema_20
                and rsi < self.BEAR_RSI_MAX):
            return 'STRONG_BEAR_MARKET'

        # Bear عادي
        if current_price < sma_20 and current_price < ema_20:
            return 'BEAR_MARKET'

        return 'SIDEWAYS'

    def _analyze_simple(self, df: pd.DataFrame, current_price: float) -> str:
        """تحليل مبسط عند عدم كفاية البيانات"""
        sma_10 = float(df['c'].rolling(10).mean().iloc[-1])

        if current_price > sma_10 * self.STRONG_BULL_THRESHOLD:
            return 'STRONG_BULL_MARKET'
        elif current_price > sma_10:
            return 'BULL_MARKET'
        else:
            return 'BEAR_MARKET'

    # ─────────────────────────────────────────────
    # المؤشرات
    # ─────────────────────────────────────────────

    def _calculate_rsi(self, prices: pd.Series) -> float:
        """حساب RSI"""
        delta = prices.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(self.RSI_PERIOD).mean()

        rs  = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    def _calculate_momentum(self, prices: pd.Series, current_price: float) -> float:
        """حساب Momentum كنسبة مئوية"""
        past_price = float(prices.iloc[-self.MOMENTUM_LOOKBACK])
        if past_price == 0:
            return 0.0
        return ((current_price - past_price) / past_price) * 100

    # ─────────────────────────────────────────────
    # تحديد الحالة النهائية
    # ─────────────────────────────────────────────

    def _determine_final_status(self, statuses: list[str]) -> str:
        """تحديد الحالة الكلية بناءً على أغلبية العملات"""
        if not statuses:
            return '⚪ NEUTRAL'

        most_common = Counter(statuses).most_common(1)[0][0]
        emoji = self._get_status_emoji(most_common)
        return f"{emoji} {most_common}"

    @staticmethod
    def _get_status_emoji(status: str) -> str:
        """إرجاع الإيموجي المناسب للحالة"""
        if 'BULL' in status:
            return '🟢'
        elif 'BEAR' in status:
            return '🔴'
        else:
            return '⚪'