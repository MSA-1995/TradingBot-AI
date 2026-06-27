"""
📊 Macro Trend Advisor v3 - Elite Edition (3 Leaders + Real vs Fake Detection)

Features:
- 3 elite coins only: BTC, ETH, BNB (70% of market)
- 2-of-3 voting system for clear decisions
- Advanced REAL vs FAKE signal detection (الأولوية #1)
- OBV (On-Balance Volume) for accumulation/distribution
- RSI Divergence for early reversals
- Multi-timeframe: 1d (50%), 4h (30%), 1h (20%)
- Fast execution (3 coins vs 10)
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
    Elite macro market analyzer - 3 leaders, 2-of-3 voting.
    
    Public API:
    - get_macro_status() -> str
    - analyze_market_state() -> dict
    - can_aim_high() -> bool
    - get_display_info() -> dict
    - invalidate_cache() -> None
    """

    # ═══════════════════════════════════════════════════════════════
    # 🏆 ELITE 3 LEADERS ONLY (BTC + ETH + BNB = 70% of market)
    # ═══════════════════════════════════════════════════════════════
    LEADERS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
    
    TIMEFRAMES = ['1h', '4h', '1d']
    TIMEFRAME_WEIGHTS = {'1d': 0.50, '4h': 0.30, '1h': 0.20}
    CACHE_DURATION = 120  # 2 minutes (faster with only 3 coins)

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_macro_status(self) -> str:
        if not self.exchange:
            return '⚪ SIDEWAYS'
        if time.time() - self._last_check_time < self.CACHE_DURATION:
            return self._last_status
        if not hasattr(self, '_fetch_thread_running') or not self._fetch_thread_running:
            self._fetch_thread_running = True
            threading.Thread(target=self._bg_fetch, daemon=True).start()
        return self._last_status

    def _bg_fetch(self):
        try:
            result = self._analyze_all()
            status = self._resolve_status_2of3(result)
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
    # Core Analysis
    # ------------------------------------------------------------------
    def _analyze_all(self) -> dict:
        """Analyze 3 elite leaders in parallel."""
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_symbol = {
                executor.submit(self._analyze_symbol_full, symbol): symbol
                for symbol in self.LEADERS
            }
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    results[symbol] = future.result()
                except Exception as e:
                    print(f"⚠️ Error analyzing {symbol}: {e}")
                    results[symbol] = self._empty_symbol_result()

        # Count votes
        bull_count = sum(1 for r in results.values() if r['vote'] == 'BULL')
        bear_count = sum(1 for r in results.values() if r['vote'] == 'BEAR')
        neutral_count = 3 - bull_count - bear_count

        return {
            'symbols': results,
            'bull_count': bull_count,
            'bear_count': bear_count,
            'neutral_count': neutral_count,
            'total': 3,
        }

    def _analyze_symbol_full(self, symbol: str) -> dict:
        """
        Full analysis for one symbol across all timeframes.
        Returns vote (BULL/BEAR/NEUTRAL) with confidence.
        """
        tf_results = {}
        
        for tf in self.TIMEFRAMES:
            df = self._fetch_df(symbol, tf, limit=100)
            if df is not None and len(df) >= 50:
                tf_results[tf] = self._analyze_single_timeframe(df, tf)
            else:
                tf_results[tf] = None

        # Weighted aggregation
        total_bull = 0.0
        total_bear = 0.0
        real_signals = 0
        fake_signals = 0
        obv_trend = 'neutral'
        divergence = 'none'
        
        for tf, weight in self.TIMEFRAME_WEIGHTS.items():
            if tf_results.get(tf) is None:
                continue
            data = tf_results[tf]
            total_bull += data['bull_points'] * weight
            total_bear += data['bear_points'] * weight
            
            if data['is_real_signal']:
                real_signals += 1
            if data['is_fake_signal']:
                fake_signals += 1
            
            # Use 1d for OBV trend (most reliable)
            if tf == '1d' and data.get('obv_trend'):
                obv_trend = data['obv_trend']
            
            # Divergence from any timeframe
            if data.get('divergence') != 'none':
                divergence = data['divergence']

        # ═══════════════════════════════════════════════════════════
        # 🎯 FINAL VOTE DECISION (Real vs Fake is #1 priority)
        # ═══════════════════════════════════════════════════════════
        
        # Rule 1: If mostly fake signals, vote NEUTRAL
        if fake_signals >= 2:
            vote = 'NEUTRAL'
            reason = f'⚠️ Fake signals detected ({fake_signals}/3 TFs)'
        
        # Rule 2: Divergence overrides everything (early reversal)
        elif divergence == 'bearish_div':
            vote = 'BEAR'
            reason = '📉 Bearish divergence (price up, RSI down)'
        elif divergence == 'bullish_div':
            vote = 'BULL'
            reason = '📈 Bullish divergence (price down, RSI up)'
        
        # Rule 3: OBV confirms or denies
        elif obv_trend == 'distribution' and total_bull > total_bear:
            vote = 'NEUTRAL'  # Rising price but selling volume = fake pump
            reason = '⚠️ OBV distribution (fake pump)'
        elif obv_trend == 'accumulation' and total_bear > total_bull:
            vote = 'NEUTRAL'  # Falling price but buying volume = fake dump
            reason = '⚠️ OBV accumulation (fake dump)'
        
        # Rule 4: Clear winner with real signals
        elif total_bull >= total_bear + 2 and real_signals >= 1:
            vote = 'BULL'
            reason = f'🟢 Real bullish ({total_bull:.1f} vs {total_bear:.1f})'
        elif total_bear >= total_bull + 2 and real_signals >= 1:
            vote = 'BEAR'
            reason = f'🔴 Real bearish ({total_bear:.1f} vs {total_bull:.1f})'
        
        # Rule 5: Slight edge
        elif total_bull > total_bear + 0.5:
            vote = 'BULL'
            reason = f'🟢 Mild bullish ({total_bull:.1f} vs {total_bear:.1f})'
        elif total_bear > total_bull + 0.5:
            vote = 'BEAR'
            reason = f'🔴 Mild bearish ({total_bear:.1f} vs {total_bull:.1f})'
        
        else:
            vote = 'NEUTRAL'
            reason = f'⚪ No clear direction ({total_bull:.1f} vs {total_bear:.1f})'

        return {
            'vote': vote,
            'bull_points': round(total_bull, 1),
            'bear_points': round(total_bear, 1),
            'real_signals': real_signals,
            'fake_signals': fake_signals,
            'obv_trend': obv_trend,
            'divergence': divergence,
            'reason': reason,
            'timeframes': {tf: tf_results[tf] for tf in tf_results if tf_results[tf]},
        }

    def _analyze_single_timeframe(self, df: pd.DataFrame, tf: str) -> dict:
        """
        Analyze single timeframe with REAL vs FAKE detection.
        """
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        open_price = df['open']

        price = float(close.iloc[-1])
        
        # ═══ EMAs ═══
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        
        price_above_ema21 = price > float(ema21.iloc[-1])
        price_above_ema50 = price > float(ema50.iloc[-1])
        ema21_above_ema50 = float(ema21.iloc[-1]) > float(ema50.iloc[-1])

        # ═══ RSI(14) ═══
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_value = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        rsi_prev = float(rsi.iloc[-10]) if len(rsi) > 10 and not pd.isna(rsi.iloc[-10]) else rsi_value

        # ═══ OBV (On-Balance Volume) ═══
        obv = self._calculate_obv(close, volume)
        obv_trend = self._detect_obv_trend(obv, close)

        # ═══ Multi-period Momentum ═══
        change_5 = self._safe_pct_change(close, 5)
        change_10 = self._safe_pct_change(close, 10)
        change_20 = self._safe_pct_change(close, 20)

        # ═══ Volume Analysis ═══
        avg_vol_20 = float(volume.tail(20).mean())
        recent_vol = float(volume.tail(3).mean())
        volume_ratio = recent_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # ═══ Candle Analysis ═══
        last = df.iloc[-1]
        candle_range = max(float(last["high"]) - float(last["low"]), 1e-12)
        body = abs(float(last["close"]) - float(last["open"]))
        upper_wick = float(last["high"]) - max(float(last["open"]), float(last["close"]))
        lower_wick = min(float(last["open"]), float(last["close"])) - float(last["low"])
        close_strength = (float(last["close"]) - float(last["low"])) / candle_range

        # ═══ Structure (Higher Lows / Lower Highs) ═══
        structure = self._analyze_structure(high, low, close)

        # ═══════════════════════════════════════════════════════════
        # 🎯 REAL vs FAKE SIGNAL DETECTION (الأهم!)
        # ═══════════════════════════════════════════════════════════
        
        # --- FAKE BULL (صعود وهمي) ---
        # 1. Wick علوي طويل (> 50% من الشمعة) = رفض السعر
        # 2. السعر رجع (close_strength < 40%)
        # 3. Volume ما أكد (< 1.2x)
        # 4. OBV يوزع (distribution) مع صعود = بيع مخفي
        # 5. RSI divergence سلبي
        fake_bull_wick = upper_wick / candle_range > 0.50 and close_strength < 0.40
        fake_bull_volume = change_5 > 0.5 and volume_ratio < 0.9  # صعود بدون volume
        fake_bull_obv = obv_trend == 'distribution' and change_10 > 0.5
        fake_bull = fake_bull_wick or fake_bull_volume or fake_bull_obv
        
        # --- FAKE BEAR (هبوط وهمي) ---
        # 1. Wick سفلي طويل = دعم قوي
        # 2. السعر ارتد (close_strength > 60%)
        # 3. Volume ضعيف
        # 4. OBV يجمع (accumulation) مع هبوط = شراء مخفي
        fake_bear_wick = lower_wick / candle_range > 0.50 and close_strength > 0.60
        fake_bear_volume = change_5 < -0.5 and volume_ratio < 0.9
        fake_bear_obv = obv_trend == 'accumulation' and change_10 < -0.5
        fake_bear = fake_bear_wick or fake_bear_volume or fake_bear_obv
        
        # --- REAL BULL (صعود حقيقي) ---
        # 1. Body قوي (> 50%)
        # 2. إغلاق قوي (> 60%)
        # 3. Momentum مستمر (5 + 10 + 20 كلهم صاعدين)
        # 4. Volume يؤكد (> 1.1x)
        # 5. OBV يجمع
        # 6. فوق EMAs
        real_bull = (
            body / candle_range >= 0.40
            and close_strength >= 0.55
            and change_5 > 0.2 and change_10 > 0.2
            and volume_ratio >= 1.0
            and obv_trend != 'distribution'
            and not fake_bull
        )
        
        # --- REAL BEAR (هبوط حقيقي) ---
        real_bear = (
            body / candle_range >= 0.40
            and close_strength <= 0.45
            and change_5 < -0.2 and change_10 < -0.2
            and volume_ratio >= 1.0
            and obv_trend != 'accumulation'
            and not fake_bear
        )

        # ═══ RSI DIVERGENCE ═══
        divergence = 'none'
        price_change_10 = change_10
        rsi_change_10 = rsi_value - rsi_prev
        
        # Bearish divergence: price up, RSI down
        if price_change_10 > 1.0 and rsi_change_10 < -5:
            divergence = 'bearish_div'
        # Bullish divergence: price down, RSI up
        elif price_change_10 < -1.0 and rsi_change_10 > 5:
            divergence = 'bullish_div'

        # ═══════════════════════════════════════════════════════════
        # 🏆 SCORING
        # ═══════════════════════════════════════════════════════════
        bull_points = 0.0
        bear_points = 0.0

        # --- EMA Position ---
        if price_above_ema21 and price_above_ema50:
            bull_points += 2.5
            if ema21_above_ema50:
                bull_points += 1.5  # Golden alignment
        elif not price_above_ema21 and not price_above_ema50:
            bear_points += 2.5
            if not ema21_above_ema50:
                bear_points += 1.5  # Death alignment

        # --- Momentum (متعدد الفترات) ---
        if change_5 > 0.3 and change_10 > 0.3 and change_20 > 0.5:
            bull_points += 3  # Confirmed uptrend
        elif change_5 < -0.3 and change_10 < -0.3 and change_20 < -0.5:
            bear_points += 3  # Confirmed downtrend

        # --- Structure ---
        if structure == 'bullish':
            bull_points += 2
        elif structure == 'bearish':
            bear_points += 2

        # --- Volume + Real Signal ---
        if real_bull and volume_ratio >= 1.1:
            bull_points += 2.5
        elif real_bear and volume_ratio >= 1.1:
            bear_points += 2.5

        # --- OBV Trend ---
        if obv_trend == 'accumulation':
            bull_points += 1.5
        elif obv_trend == 'distribution':
            bear_points += 1.5

        # --- Fake Signal Penalties ---
        if fake_bull:
            bull_points = max(0, bull_points - 3)
            bear_points += 1
        if fake_bear and obv_trend not in ('confirmed_bear', 'distribution'):
            bear_points = max(0, bear_points - 3)
            bull_points += 1

        # --- RSI (requires OBV confirmation for symmetry) ---
        if rsi_value > 75 and obv_trend in ('distribution', 'confirmed_bear'):
            bear_points += 1.5  # Overbought confirmed by volume
        elif rsi_value < 25 and obv_trend in ('accumulation', 'confirmed_bull'):
            bull_points += 1.5  # Oversold confirmed by volume

        # --- Divergence ---
        if divergence == 'bearish_div':
            bear_points += 2
            bull_points = max(0, bull_points - 1)
        elif divergence == 'bullish_div':
            bull_points += 2
            bear_points = max(0, bear_points - 1)

        return {
            'bull_points': round(bull_points, 1),
            'bear_points': round(bear_points, 1),
            'price': price,
            'change_5': round(change_5, 2),
            'change_10': round(change_10, 2),
            'change_20': round(change_20, 2),
            'volume_ratio': round(volume_ratio, 2),
            'rsi': round(rsi_value, 1),
            'obv_trend': obv_trend,
            'structure': structure,
            'divergence': divergence,
            'is_real_signal': real_bull or real_bear,
            'is_fake_signal': fake_bull or fake_bear,
            'fake_bull': fake_bull,
            'fake_bear': fake_bear,
            'close_strength': round(close_strength, 2),
        }

    # ------------------------------------------------------------------
    # OBV Calculation
    # ------------------------------------------------------------------
    def _calculate_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On-Balance Volume."""
        obv = [0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i-1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=close.index)

    def _detect_obv_trend(self, obv: pd.Series, close: pd.Series) -> str:
        """
        Detect OBV trend vs Price trend.
        - accumulation: OBV rising while price flat/down (smart money buying)
        - distribution: OBV falling while price flat/up (smart money selling)
        - confirmed: OBV and price moving together
        """
        if len(obv) < 20:
            return 'neutral'
        
        obv_change = (obv.iloc[-1] - obv.iloc[-20]) / (abs(obv.iloc[-20]) + 1e-10) * 100
        price_change = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100
        
        # Distribution: price up/flat but OBV down
        if price_change > -0.5 and obv_change < -5:
            return 'distribution'
        # Accumulation: price down/flat but OBV up
        elif price_change < 0.5 and obv_change > 5:
            return 'accumulation'
        # Confirmed trends
        elif price_change > 1 and obv_change > 3:
            return 'confirmed_bull'
        elif price_change < -1 and obv_change < -3:
            return 'confirmed_bear'
        
        return 'neutral'

    # ------------------------------------------------------------------
    # Structure Analysis
    # ------------------------------------------------------------------
    def _analyze_structure(self, high: pd.Series, low: pd.Series, close: pd.Series) -> str:
        """Higher Lows = bullish, Lower Highs = bearish."""
        if len(close) < 15:
            return 'neutral'

        zone1_high = float(high.iloc[-15:-10].max())
        zone1_low = float(low.iloc[-15:-10].min())
        zone2_high = float(high.iloc[-10:-5].max())
        zone2_low = float(low.iloc[-10:-5].min())
        zone3_high = float(high.iloc[-5:].max())
        zone3_low = float(low.iloc[-5:].min())

        higher_lows = (zone3_low > zone2_low > zone1_low)
        higher_highs = (zone3_high > zone2_high > zone1_high)
        lower_highs = (zone3_high < zone2_high < zone1_high)
        lower_lows = (zone3_low < zone2_low < zone1_low)

        if higher_lows and higher_highs:
            return 'bullish'
        elif higher_lows:
            return 'bullish'
        elif lower_highs and lower_lows:
            return 'bearish'
        elif lower_highs:
            return 'bearish'
        return 'neutral'

    # ------------------------------------------------------------------
    # 2-of-3 Voting System
    # ------------------------------------------------------------------
    def _resolve_status_2of3(self, result: dict) -> str:
        """
        Simple 2-of-3 voting:
        - 3 BULL = BULL_MARKET
        - 2 BULL = MILD_BULL
        - 2 BEAR = MILD_BEAR
        - 3 BEAR = BEAR_MARKET
        - else = SIDEWAYS
        """
        bull = result['bull_count']
        bear = result['bear_count']
        
        # Get detailed info for smart decision
        symbols = result.get('symbols', {})
        total_fake = sum(s.get('fake_signals', 0) for s in symbols.values())
        
        # If too many fake signals across all 3, be cautious
        if total_fake >= 4:  # 4+ fake signals across 3 coins
            new_status = '⚪ SIDEWAYS'
        elif bull == 3:
            new_status = '🟢 BULL_MARKET'
        elif bull == 2:
            new_status = '🟢 MILD_BULL'
        elif bear == 3:
            new_status = '🔴 BEAR_MARKET'
        elif bear == 2:
            new_status = '🔴 MILD_BEAR'
        else:
            new_status = '⚪ SIDEWAYS'

        # Sticky logic: no confirmation needed on first run, 1 for strong, 2 for weak
        is_first_run = (self._last_check_time == 0.0)
        if self._last_status and new_status != self._last_status:
            bull = result['bull_count']
            bear = result['bear_count']
            is_strong_signal = (bull == 3 or bear == 3)
            required = 0 if is_first_run else (1 if is_strong_signal else 2)
            if new_status == self._pending_status:
                self._pending_count += 1
                if self._pending_count >= required:
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

    # ------------------------------------------------------------------
    # Finalize & Save
    # ------------------------------------------------------------------
    def _finalize(self, status: str, result: dict) -> None:
        self._last_status = status
        self._last_check_time = time.time()
        self._last_analysis = result
        self._last_analysis_time = time.time()

        bull = result["bull_count"]
        bear = result["bear_count"]
        symbols = result.get("symbols", {})
        
        # Build summary
        votes_summary = {s: r.get("vote", "?") for s, r in symbols.items()}
        reasons = [r.get("reason", "") for r in symbols.values()]

        self._display_info = {
            "status": status,
            "total_bull": bull,
            "total_bear": bear,
            "votes": votes_summary,
            "detail": f"BTC:{votes_summary.get('BTC/USDT','?')} ETH:{votes_summary.get('ETH/USDT','?')} BNB:{votes_summary.get('BNB/USDT','?')}",
            "reasons": reasons,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self._save_to_db(status, result)

    def _save_to_db(self, status: str, result: dict) -> None:
        if not self.db:
            return
        try:
            symbols = result.get("symbols", {})
            votes = {s: r.get("vote", "?") for s, r in symbols.items()}
            data = {
                "macro_status": status,
                "time": datetime.now().strftime("%H:%M:%S"),
                "bull_count": result.get("bull_count", 0),
                "bear_count": result.get("bear_count", 0),
                "votes": votes,
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
    def _safe_pct_change(series: pd.Series, periods: int) -> float:
        if len(series) <= periods:
            return 0.0
        prev = float(series.iloc[-periods - 1])
        curr = float(series.iloc[-1])
        return ((curr - prev) / prev * 100) if prev > 0 else 0.0

    @staticmethod
    def _empty_state() -> dict:
        return {
            "symbols": {},
            "bull_count": 0,
            "bear_count": 0,
            "neutral_count": 0,
            "total": 3,
        }

    @staticmethod
    def _empty_symbol_result() -> dict:
        return {
            'vote': 'NEUTRAL',
            'bull_points': 0,
            'bear_points': 0,
            'real_signals': 0,
            'fake_signals': 0,
            'obv_trend': 'neutral',
            'divergence': 'none',
            'reason': 'No data',
        }
