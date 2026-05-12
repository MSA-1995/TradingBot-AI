"""
📊 Macro Trend Advisor - Advanced (Multi-Timeframe + RSI + 10 Coins + Dynamic Threshold + Funding Rate)

Features:
- 10 coins from different sectors (BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, MATIC, LINK)
- 3 timeframes (1h, 4h, 1d) with weighting: 1d (50%), 4h (30%), 1h (20%)
- RSI(14) to filter fake pumps
- Dynamic threshold based on market volatility (ATR)
- Funding Rate check (if exchange supports perpetual futures)
- Parallel data fetching for speed
- Sticky status with 3 confirmations
"""

import time
import json
import threading
import concurrent.futures
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import pandas as pd
import numpy as np


class MacroTrendAdvisor:
    """
    Advanced macro market analyzer.
    Public API same as before:
    - get_macro_status() -> str
    - analyze_market_state() -> dict
    - can_aim_high() -> bool
    - get_display_info() -> dict
    - invalidate_cache() -> None
    """

    # Expanded coin list (sectors: large cap, DeFi, L1, Meme)
    LEADERS = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
        'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'TRX/USDT', 'LINK/USDT'
    ]
    TIMEFRAMES = ['1h', '4h', '1d']
    TIMEFRAME_WEIGHTS = {'1d': 0.50, '4h': 0.30, '1h': 0.20}
    CACHE_DURATION = 180  # seconds

    def __init__(self, exchange=None, dl_client=None, storage=None):
        self.exchange = exchange
        self.dl_client = dl_client
        self.db = storage

        self._last_status = '⚪ SIDEWAYS'
        self._last_check_time = 0.0
        self._last_analysis = {}
        self._last_analysis_time = 0.0
        self._display_info = {
            'status': self._last_status,
            'total_bull': 0,
            'total_bear': 0,
            'detail': 'Not analyzed yet',
        }
        self._pending_status = None
        self._pending_count = 0
        self._funding_rates_cache = {}
        self._funding_cache_time = 0.0

    # ------------------------------------------------------------------
    # Public API (unchanged signatures)
    # ------------------------------------------------------------------
    def get_macro_status(self) -> str:
        if not self.exchange:
            return '⚪ SIDEWAYS'
        if time.time() - self._last_check_time < self.CACHE_DURATION:
            return self._last_status
        # Trigger async refresh
        if not hasattr(self, '_fetch_thread_running') or not self._fetch_thread_running:
            self._fetch_thread_running = True
            threading.Thread(target=self._bg_fetch, daemon=True).start()
        return self._last_status

    def _bg_fetch(self):
        try:
            result = self._analyze_all()
            status = self._resolve_status(result)
            self._finalize(status, result)
        except Exception as e:
            print(f'⚠️ MacroTrendAdvisor error: {e}')
        finally:
            self._fetch_thread_running = False

    def can_aim_high(self) -> bool:
        return 'BULL' in (self._last_status or '')

    def analyze_market_state(self) -> dict:
        if not self.exchange:
            return self._empty_state()
        return self._last_analysis or self._empty_state()

    def get_display_info(self) -> dict:
        return self._display_info

    def invalidate_cache(self) -> None:
        self._last_check_time = 0.0
        self._last_analysis_time = 0.0
        self._last_analysis = {}

    # ------------------------------------------------------------------
    # Core logic with multi-timeframe, RSI, dynamic threshold, funding
    # ------------------------------------------------------------------
    def _analyze_all(self) -> dict:
        """Analyze all coins across timeframes in parallel."""
        results = {}
        bull_count = 0
        bear_count = 0

        # 1. Fetch funding rates if available
        funding_rates = self._fetch_all_funding_rates()

        # 2. Parallel fetch for each symbol (all timeframes)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_symbol = {
                executor.submit(self._fetch_symbol_analysis, symbol, funding_rates.get(symbol, 0.0)): symbol
                for symbol in self.LEADERS
            }
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    analysis = future.result()
                    results[symbol] = analysis
                    if analysis['status'] == 'BULLISH':
                        bull_count += 1
                    elif analysis['status'] == 'BEARISH':
                        bear_count += 1
                except Exception as e:
                    print(f"⚠️ Error analyzing {symbol}: {e}")
                    results[symbol] = {'status': 'NEUTRAL', 'reason': 'error'}

        neutral_count = len(self.LEADERS) - bull_count - bear_count
        return {
            'symbols': results,
            'bull_count': bull_count,
            'bear_count': bear_count,
            'neutral_count': neutral_count,
            'total': len(self.LEADERS),
        }

    def _fetch_symbol_analysis(self, symbol: str, funding_rate: float) -> dict:
        """Analyze a single symbol across timeframes and compute final score."""
        tf_data = {}
        valid_tfs = 0
        for tf in self.TIMEFRAMES:
            df = self._fetch_df(symbol, tf, limit=100)  # enough for RSI and EMAs
            if df is not None and len(df) >= 50:
                tf_data[tf] = self._analyze_timeframe(df, tf, funding_rate)
                valid_tfs += 1
            else:
                tf_data[tf] = None

        if valid_tfs == 0:
            return {
                'status': 'NEUTRAL',
                'reason': 'no data',
                'bull_points': 0,
                'bear_points': 0,
                'change_10': 0,
                'volume_ratio': 1.0,
                'real_candle': False,
                'fake_signal': False,
                'close_strength': 0.5,
                'rsi': 50,
            }

        # Weighted aggregation
        total_bull = 0.0
        total_bear = 0.0
        details = {}
        for tf, weight in self.TIMEFRAME_WEIGHTS.items():
            if tf_data.get(tf) is None:
                continue
            data = tf_data[tf]
            details[tf] = data
            total_bull += data['bull_points'] * weight
            total_bear += data['bear_points'] * weight

        # Dynamic threshold based on recent volatility (using 4h ATR across all symbols)
        volatility_factor = self._get_volatility_factor()
        required_lead = max(2, int(3 / volatility_factor))  # more volatile -> need bigger lead
        min_bull_points = max(3, int(5 * volatility_factor))  # low vol: lower threshold

        # Final decision
        fake_detected = any(details[tf].get('fake_signal', False) for tf in details if details[tf])
        pump_dump = any(details[tf].get('pump_then_dump', False) for tf in details if details[tf])
        rsi_avg = np.mean([details[tf].get('rsi', 50) for tf in details if details[tf]])

        # Funding rate adjustment: negative funding = bearish pressure
        funding_adjust = 0
        if funding_rate != 0:
            if funding_rate < -0.01:
                funding_adjust = -1  # bearish
            elif funding_rate > 0.05:
                funding_adjust = -2  # overheated long, fake pump risk
            elif funding_rate > 0.01:
                funding_adjust = 0.5  # healthy bull

        total_bull += funding_adjust if funding_adjust > 0 else 0
        total_bear += abs(funding_adjust) if funding_adjust < 0 else 0

        if pump_dump or fake_detected:
            status = 'BEARISH'
        elif rsi_avg > 80:
            status = 'BEARISH'  # overbought without confirmation
        elif total_bull >= total_bear + required_lead and total_bull >= min_bull_points:
            status = 'BULLISH'
        elif total_bear >= total_bull + required_lead and total_bear >= min_bull_points:
            status = 'BEARISH'
        else:
            status = 'NEUTRAL'

        # Use 1h data for detailed fields (for compatibility)
        base = details.get('1h', {}) or details.get('4h', {}) or details.get('1d', {})
        return {
            'status': status,
            'bull_points': round(total_bull, 1),
            'bear_points': round(total_bear, 1),
            'price': base.get('price', 0),
            'change_10': base.get('change_10', 0),
            'volume_ratio': base.get('volume_ratio', 1.0),
            'real_candle': base.get('real_candle', False),
            'fake_signal': fake_detected,
            'close_strength': base.get('close_strength', 0.5),
            'rsi': round(rsi_avg, 1),
            'funding_rate': funding_rate,
            'reason': f"{status} bull={total_bull:.1f} bear={total_bear:.1f} rsi={rsi_avg:.0f} vol={base.get('volume_ratio',1):.1f}x",
        }

    def _analyze_timeframe(self, df: pd.DataFrame, tf: str, funding_rate: float) -> dict:
        """Analyze a single timeframe's OHLCV."""
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']

        price = float(close.iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])

        price_above_ema21 = price > ema21
        price_above_ema50 = price > ema50
        ema21_above_ema50 = ema21 > ema50

        # RSI(14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

        # Price change over 10 candles
        prev_price = float(close.iloc[-11]) if len(close) > 11 else price
        change_10 = ((price - prev_price) / prev_price * 100) if prev_price > 0 else 0

        # Volume ratio
        avg_vol_20 = float(volume.tail(20).mean())
        recent_vol = float(volume.tail(3).mean())
        volume_ratio = recent_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Candle quality
        last = df.iloc[-1]
        candle_range = float(last["high"]) - float(last["low"])
        candle_range = max(candle_range, 1e-12)
        body = abs(float(last["close"]) - float(last["open"]))
        upper_wick = float(last["high"]) - max(float(last["open"]), float(last["close"]))
        close_strength = (float(last["close"]) - float(last["low"])) / candle_range

        real_candle = (
            body / candle_range >= 0.4
            and close_strength >= 0.55
            and upper_wick / candle_range < 0.45
        )
        fake_signal = (
            upper_wick / candle_range > 0.55
            and close_strength < 0.35
            and volume_ratio < 1.3
        )

        # Pump then dump detection
        recent_change30 = float(close.iloc[-1] - close.iloc[-30]) / float(close.iloc[-30]) * 100 if len(close) > 30 else 0
        prev_high40 = float(high.iloc[-40:-5].max()) if len(high) > 40 else float(high.max())
        pump_then_dump = (
            prev_high40 > float(close.iloc[-1]) * 1.05
            and recent_change30 < -3.0
        )

        # Scoring
        bull_points = 0
        bear_points = 0

        # Price vs EMAs
        if price_above_ema21 and price_above_ema50:
            bull_points += 3
            if ema21_above_ema50: bull_points += 1
        elif price_above_ema21:
            bull_points += 1

        if not price_above_ema21 and not price_above_ema50:
            bear_points += 2
            if not ema21_above_ema50: bear_points += 1
        elif not price_above_ema21:
            bear_points += 1

        # Momentum
        if change_10 > 2.0:
            bull_points += 2
        elif change_10 > 0.8:
            bull_points += 1
        elif change_10 < -2.0:
            bear_points += 2
        elif change_10 < -0.8:
            bear_points += 1

        # Volume + candle
        volume_confirms = volume_ratio >= 1.15
        if volume_confirms and real_candle:
            bull_points += 2
        elif fake_signal:
            bear_points += 2
        elif volume_confirms and change_10 > 0:
            bull_points += 1
        elif volume_ratio < 0.7 and change_10 > 0.5:
            bear_points += 2
        elif change_10 > 3.0 and volume_ratio < 0.95:
            bear_points += 2

        if fake_signal:
            bear_points += 1

        # RSI influence
        if rsi_value > 70:
            bear_points += 0.5  # overbought caution
        elif rsi_value < 30:
            bull_points += 1  # oversold bounce potential

        return {
            'bull_points': bull_points,
            'bear_points': bear_points,
            'price': price,
            'change_10': round(change_10, 2),
            'volume_ratio': round(volume_ratio, 2),
            'real_candle': real_candle,
            'fake_signal': fake_signal,
            'pump_then_dump': pump_then_dump,
            'close_strength': round(close_strength, 2),
            'rsi': round(rsi_value, 1),
        }

    def _get_volatility_factor(self) -> float:
        """Compute dynamic threshold factor based on ATR of BTC/USDT 4h."""
        try:
            df = self._fetch_df('BTC/USDT', '4h', limit=50)
            if df is None or len(df) < 20:
                return 1.0
            high, low = df['high'], df['low']
            atr = (high.rolling(14).max() - low.rolling(14).min()).iloc[-1]
            price = df['close'].iloc[-1]
            volatility_pct = (atr / price) * 100
            # Normalize: low vol < 2% -> factor 0.7, high vol > 5% -> factor 1.3
            factor = np.clip(volatility_pct / 3.0, 0.7, 1.3)
            return factor
        except Exception:
            return 1.0

    def _fetch_all_funding_rates(self) -> Dict[str, float]:
        """Fetch funding rates for perpetual futures (if available)."""
        if not self.exchange:
            return {}
        # Cache for 5 minutes
        if time.time() - self._funding_cache_time < 300:
            return self._funding_rates_cache
        rates = {}
        try:
            # Check if exchange has fetch_funding_rate method
            if hasattr(self.exchange, 'fetch_funding_rate'):
                for symbol in self.LEADERS:
                    try:
                        fr = self.exchange.fetch_funding_rate(symbol)
                        rates[symbol] = fr.get('fundingRate', 0.0)
                        time.sleep(0.1)  # avoid rate limit
                    except Exception:
                        rates[symbol] = 0.0
            else:
                # Fallback: try to get from ticker or ignore
                pass
        except Exception as e:
            print(f"⚠️ Funding rate fetch error: {e}")
        self._funding_rates_cache = rates
        self._funding_cache_time = time.time()
        return rates

    def _resolve_status(self, result: dict) -> str:
        """Aggregate across all coins with sticky logic."""
        bull = result['bull_count']
        bear = result['bear_count']
        symbols = result.get('symbols', {})
        momentums = [d.get("change_10", 0.0) for d in symbols.values() if isinstance(d, dict)]
        volumes = [d.get("volume_ratio", 0.0) for d in symbols.values() if isinstance(d, dict)]
        avg_momentum = sum(momentums) / len(momentums) if momentums else 0.0
        avg_volume = sum(volumes) / len(volumes) if volumes else 1.0

        bull_threshold = int(len(self.LEADERS) * 0.3)

        mild_threshold = int(len(self.LEADERS) * 0.2)
        if avg_volume < 0.6 and avg_momentum < -15 and bear >= bull_threshold:
            new_status = "🔴 BEAR_MARKET"
        elif bull >= bull_threshold and avg_momentum > 0.2 and avg_volume >= 1.1:
            new_status = "🟢 BULL_MARKET"
        elif bull >= bull_threshold and avg_momentum > 0.5 and avg_volume >= 0.7:
            new_status = "🟢 BULL_MARKET"
        elif bull >= mild_threshold and avg_momentum > 0.1 and avg_volume >= 0.65:
            new_status = "🟢 MILD_BULL"
        elif bear >= bull_threshold and avg_momentum < -0.2 and bear > 0:
            new_status = "🔴 BEAR_MARKET"
        elif bear >= mild_threshold and avg_momentum < -0.1:
            new_status = "🔴 MILD_BEAR"
        else:
            new_status = "⚪ SIDEWAYS"
        # Sticky logic
        if new_status != self._last_status:
            if new_status == self._pending_status:
                self._pending_count += 1
                if self._pending_count >= 2:
                    self._pending_status = None
                    self._pending_count = 0
                    return new_status
                return self._last_status
            else:
                self._pending_status = new_status
                self._pending_count = 1
                return self._last_status
        self._pending_status = None
        self._pending_count = 0
        return new_status

    def _finalize(self, status: str, result: dict) -> None:
        """Update cache and save to DB."""
        self._last_status = status
        self._last_check_time = time.time()
        self._last_analysis = result
        self._last_analysis_time = time.time()

        bull = result["bull_count"]
        bear = result["bear_count"]
        symbols_summary = {
            s: r.get("status", "NEUTRAL")
            for s, r in result.get("symbols", {}).items()
        }

        if bull >= len(self.LEADERS) * 0.5:
            direction = "BULLISH"
            strength = "STRONG" if bull >= len(self.LEADERS) * 0.7 else "NORMAL"
        elif bear >= len(self.LEADERS) * 0.5:
            direction = "BEARISH"
            strength = "STRONG" if bear >= len(self.LEADERS) * 0.7 else "NORMAL"
        else:
            direction = "NEUTRAL"
            strength = "NEUTRAL"

        self._combined = {"direction": direction, "strength": strength}

        self._display_info = {
            "status": status,
            "total_bull": bull,
            "total_bear": bear,
            "combined": self._combined,
            "detail": f"Bull:{bull}/{len(self.LEADERS)} Bear:{bear}/{len(self.LEADERS)} | {symbols_summary}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self._save_to_db(status, result)

    def _save_to_db(self, status: str, result: dict) -> None:
        if not self.db:
            return
        try:
            symbols_summary = {
                s: r.get("status", "NEUTRAL")
                for s, r in result.get("symbols", {}).items()
            }
            data = {
                "macro_status": status,
                "time": datetime.now().strftime("%H:%M:%S"),
                "bull_count": result.get("bull_count", 0),
                "bear_count": result.get("bear_count", 0),
                "symbols": symbols_summary,
            }
            self.db.save_setting("bot_status", json.dumps(data))
        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor DB save error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fetch_df(self, symbol: str, timeframe: str, limit: int):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                return None
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna().reset_index(drop=True)
            return df if len(df) >= 20 else None
        except Exception as e:
            print(f"⚠️ {symbol} {timeframe}: {e}")
            return None

    @staticmethod
    def _empty_state() -> dict:
        return {
            "symbols": {},
            "bull_count": 0,
            "bear_count": 0,
            "neutral_count": 0,
            "total": 0,
        }
