"""
📈 Macro Trend Advisor - Market Trend + Next Hour Prediction
Determines current market state and predicts next direction
"""

import time
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd


class MacroTrendAdvisor:
    """
    Determines overall market state and predicts next direction
    """

    MACRO_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']

    CACHE_DURATION = 300
    PREDICTION_CACHE_DURATION = 300

    OHLCV_LIMIT        = 50
    TIMEFRAME          = '4h'
    RSI_PERIOD         = 14
    MOMENTUM_LOOKBACK  = 10

    STRONG_BULL_THRESHOLD  = 1.05
    STRONG_BEAR_THRESHOLD  = 0.95
    BULL_RSI_MIN           = 50
    STRONG_BULL_RSI_MIN    = 60
    BEAR_RSI_MAX           = 40
    STRONG_BULL_MOMENTUM   = 5.0
    SIDEWAYS_MOMENTUM_MAX  = 0.1
    SIDEWAYS_RSI_RANGE     = 5

    STATUS_EMOJI = {
        'BULL': '🟢',
        'BEAR': '🔴',
        'OTHER': '⚪'
    }

    def __init__(self, exchange=None):
        self.exchange = exchange
        self._last_status: str       = '⚪ NEUTRAL'
        self._last_check_time: float = 0.0
        self._last_prediction: dict  = {}
        self._last_prediction_time: float = 0.0

    # ─────────────────────────────────────────────
    # Main Interface - يعتمد على الإشارات الحقيقية
    # ─────────────────────────────────────────────

    def get_macro_status(self) -> str:
        """الحالة الحقيقية من إشارات 1h + 4h الفعلية"""
        if not self.exchange:
            return '⚪ NEUTRAL'

        if time.time() - self._last_check_time < self.CACHE_DURATION:
            return self._last_status

        try:
            # نستخدم predict_market بدال SMA/EMA القديمة
            pred = self.predict_market()
            
            short_bull = pred.get('short', {}).get('bull_score', 0)
            short_bear = pred.get('short', {}).get('bear_score', 0)
            medium_bull = pred.get('medium', {}).get('bull_score', 0)
            medium_bear = pred.get('medium', {}).get('bear_score', 0)

            total_bull = short_bull + medium_bull
            total_bear = short_bear + medium_bear

            # نحدد الحالة الحقيقية
            if total_bull > total_bear * 1.5:
                final_status = '🟢 BULL_MARKET'
            elif total_bear > total_bull * 1.5:
                final_status = '🔴 BEAR_MARKET'
            elif total_bull > total_bear * 1.2:
                final_status = '🟢 MILD_BULL'
            elif total_bear > total_bull * 1.2:
                final_status = '🔴 MILD_BEAR'
            else:
                final_status = '⚪ SIDEWAYS'

            # نضيف التفاصيل للطباعة
            short_d = pred.get('short', {}).get('details', '')
            medium_d = pred.get('medium', {}).get('details', '')

            short_p = pred.get('short', {}).get('prediction', '?')
            medium_p = pred.get('medium', {}).get('prediction', '?')
            s1 = '🟢' if 'BULL' in str(short_p) else ('🔴' if 'BEAR' in str(short_p) else '⚪')
            s4 = '🟢' if 'BULL' in str(medium_p) else ('🔴' if 'BEAR' in str(medium_p) else '⚪')

            # نخزن التفاصيل عشان bot.py يقدر يطبعها
            self._display_info = {
                'status': final_status,
                '1h_icon': s1,
                '4h_icon': s4,
                '1h_details': short_d,
                '4h_details': medium_d,
                'total_bull': total_bull,
                'total_bear': total_bear,
            }

            self._last_status = final_status
            self._last_check_time = time.time()
            return final_status

        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor get_macro_status error: {e}")
            return '⚪ NEUTRAL'

    def get_display_info(self) -> dict:
        """معلومات العرض للهيدر"""
        if hasattr(self, '_display_info'):
            return self._display_info
        return {
            'status': self._last_status,
            '1h_icon': '⚪',
            '4h_icon': '⚪',
            '1h_details': '',
            '4h_details': '',
            'total_bull': 0,
            'total_bear': 0,
        }

    def can_aim_high(self) -> bool:
        status = self.get_macro_status()
        return 'BULL' in status

    def invalidate_cache(self) -> None:
        self._last_check_time = 0.0
        self._last_prediction_time = 0.0

    # ─────────────────────────────────────────────
    # Indicators
    # ─────────────────────────────────────────────

    def _calculate_rsi(self, prices: pd.Series) -> float:
        delta = prices.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(self.RSI_PERIOD).mean()

        rs  = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    def _calculate_momentum(self, prices: pd.Series, current_price: float) -> float:
        past_price = float(prices.iloc[-self.MOMENTUM_LOOKBACK])
        if past_price == 0:
            return 0.0
        return ((current_price - past_price) / past_price) * 100

    # ═════════════════════════════════════════════
    # 🔮 Prediction System - Next 1h + 4h
    # ═════════════════════════════════════════════

    def predict_market(self) -> dict:
        if not self.exchange:
            return self._empty_prediction()

        if time.time() - self._last_prediction_time < self.PREDICTION_CACHE_DURATION:
            return self._last_prediction

        try:
            short  = self._predict_timeframe('1h', 24)
            medium = self._predict_timeframe('4h', 24)
            combined = self._combine_timeframes(short, medium)

            result = {
                'short': short,
                'medium': medium,
                'combined': combined,
                'sell_mode': self._determine_sell_mode(combined),
                'buy_mode': self._determine_buy_mode(combined),
            }

            self._last_prediction = result
            self._last_prediction_time = time.time()
            return result

        except Exception as e:
            print(f"⚠️ predict_market error: {e}")
            return self._empty_prediction()

    def _predict_timeframe(self, timeframe: str, limit: int) -> dict:
        predictions = []

        for symbol in self.MACRO_SYMBOLS:
            try:
                result = self._predict_symbol_direction(symbol, timeframe, limit)
                if result:
                    predictions.append(result)
            except Exception as e:
                print(f"⚠️ Prediction error {symbol} {timeframe}: {e}")

        if not predictions:
            return {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No signals'}

        return self._combine_predictions(predictions, timeframe)

    def _predict_symbol_direction(self, symbol: str, timeframe: str, limit: int) -> Optional[dict]:
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

        if len(df) < 10:
            return None

        bull_signals = 0
        bear_signals = 0

        # 1. Last 3 candles direction (weight 3)
        last_3_change = (float(df['c'].iloc[-1]) - float(df['c'].iloc[-4])) / float(df['c'].iloc[-4]) * 100
        if last_3_change > 0.5:
            bull_signals += 3
        elif last_3_change < -0.5:
            bear_signals += 3
        elif last_3_change > 0:
            bull_signals += 1
        elif last_3_change < 0:
            bear_signals += 1

        # 2. RSI (weight 2)
        rsi = self._calculate_rsi(df['c'])
        if rsi > 75:
            bear_signals += 2
        elif rsi > 60:
            bull_signals += 1
        elif rsi < 25:
            bull_signals += 2
        elif rsi < 40:
            bear_signals += 1

        # 3. Volume (weight 2)
        avg_vol  = float(df['v'].iloc[-6:].mean())
        last_vol = float(df['v'].iloc[-1])
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        if vol_ratio > 1.5 and last_3_change > 0:
            bull_signals += 2
        elif vol_ratio > 1.5 and last_3_change < 0:
            bear_signals += 2
        elif vol_ratio < 0.5:
            bear_signals += 1

        # 4. MACD Direction (weight 2)
        ema_12 = df['c'].ewm(span=12).mean()
        ema_26 = df['c'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        macd_current = float(macd.iloc[-1])
        macd_prev    = float(macd.iloc[-2])

        if macd_current > macd_prev and macd_current > 0:
            bull_signals += 2
        elif macd_current > macd_prev:
            bull_signals += 1
        elif macd_current < macd_prev and macd_current < 0:
            bear_signals += 2
        elif macd_current < macd_prev:
            bear_signals += 1

        # 5. EMA Cross (weight 1)
        ema_9  = float(df['c'].ewm(span=9).mean().iloc[-1])
        ema_21 = float(df['c'].ewm(span=21).mean().iloc[-1])

        if ema_9 > ema_21:
            bull_signals += 1
        else:
            bear_signals += 1

        # 6. Reversal candle (weight 2)
        last_candle_body = abs(float(df['c'].iloc[-1]) - float(df['o'].iloc[-1]))
        last_candle_range = float(df['h'].iloc[-1]) - float(df['l'].iloc[-1])

        if last_candle_range > 0:
            body_ratio = last_candle_body / last_candle_range
            upper_shadow = float(df['h'].iloc[-1]) - max(float(df['c'].iloc[-1]), float(df['o'].iloc[-1]))
            lower_shadow = min(float(df['c'].iloc[-1]), float(df['o'].iloc[-1])) - float(df['l'].iloc[-1])

            if upper_shadow > last_candle_body * 2 and body_ratio < 0.3:
                bear_signals += 2
            elif lower_shadow > last_candle_body * 2 and body_ratio < 0.3:
                bull_signals += 2

        return {
            'symbol': symbol,
            'bull': bull_signals,
            'bear': bear_signals,
        }

    # ─────────────────────────────────────────────
    # 🔮 Combine Predictions
    # ─────────────────────────────────────────────

    def _combine_predictions(self, predictions: list, timeframe: str) -> dict:
        total_bull = sum(p['bull'] for p in predictions)
        total_bear = sum(p['bear'] for p in predictions)
        total = total_bull + total_bear

        if total == 0:
            return {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No signals'}

        bull_pct = total_bull / total * 100
        bear_pct = total_bear / total * 100

        tf_label = 'Next 1h' if timeframe == '1h' else 'Next 4h'

        if bull_pct >= 75:
            prediction = 'STRONG_BULLISH'
            confidence = bull_pct
            reason = f'🟢🟢 Strong Bullish - {tf_label}'
        elif bull_pct >= 60:
            prediction = 'BULLISH'
            confidence = bull_pct
            reason = f'🟢 Bullish - {tf_label}'
        elif bear_pct >= 75:
            prediction = 'STRONG_BEARISH'
            confidence = bear_pct
            reason = f'🔴🔴 Strong Bearish - {tf_label}'
        elif bear_pct >= 60:
            prediction = 'BEARISH'
            confidence = bear_pct
            reason = f'🔴 Bearish - {tf_label}'
        else:
            prediction = 'NEUTRAL'
            confidence = 50
            reason = f'⚪ Neutral - {tf_label}'

        details = ', '.join(
            f"{p['symbol'].split('/')[0]}(🟢{p['bull']}/🔴{p['bear']})"
            for p in predictions
        )

        return {
            'prediction': prediction,
            'confidence': round(confidence, 1),
            'bull_score': total_bull,
            'bear_score': total_bear,
            'reason': reason,
            'details': details,
        }

    def _combine_timeframes(self, short: dict, medium: dict) -> dict:
        short_pred  = short.get('prediction', 'NEUTRAL')
        medium_pred = medium.get('prediction', 'NEUTRAL')

        is_short_bull  = 'BULL' in short_pred
        is_short_bear  = 'BEAR' in short_pred
        is_medium_bull = 'BULL' in medium_pred
        is_medium_bear = 'BEAR' in medium_pred

        if is_short_bull and is_medium_bull:
            return {
                'direction': 'BULLISH',
                'strength': 'STRONG',
                'confidence': max(short['confidence'], medium['confidence']),
                'reason': '🟢🟢 Confirmed Bullish (1h + 4h)',
            }
        elif is_short_bear and is_medium_bear:
            return {
                'direction': 'BEARISH',
                'strength': 'STRONG',
                'confidence': max(short['confidence'], medium['confidence']),
                'reason': '🔴🔴 Confirmed Bearish (1h + 4h)',
            }
        elif is_short_bull and is_medium_bear:
            return {
                'direction': 'MIXED',
                'strength': 'CAUTION',
                'confidence': 50,
                'reason': '⚠️ Short Bullish but Medium Bearish (Caution)',
            }
        elif is_short_bear and is_medium_bull:
            return {
                'direction': 'MIXED',
                'strength': 'RECOVERY',
                'confidence': 55,
                'reason': '⏳ Temp Dip then Recovery (Wait)',
            }
        else:
            return {
                'direction': 'NEUTRAL',
                'strength': 'NEUTRAL',
                'confidence': 50,
                'reason': '⚪ Market Unclear',
            }

    # ─────────────────────────────────────────────
    # 🎯 Sell/Buy Mode Determination
    # ─────────────────────────────────────────────

    def _determine_sell_mode(self, combined: dict) -> dict:
        direction = combined.get('direction', 'NEUTRAL')
        strength  = combined.get('strength', 'NEUTRAL')

        if direction == 'BULLISH' and strength == 'STRONG':
            return {
                'mode': 'NORMAL',
                'wait_minutes': 0,
                'stability_check': 0,
                'label': '👑 Normal - Peak/Bottom System',
                'description': 'Market bullish, wait for real peak',
            }
        elif direction == 'BEARISH' and strength == 'STRONG':
            return {
                'mode': 'SNIPER_EXIT',
                'wait_minutes': 3,
                'stability_check': 3,
                'label': '🎯 Sniper - Minimize Loss & Exit',
                'description': 'Market bearish, sell on any bounce or 3min stability',
            }
        elif direction == 'MIXED' and strength == 'CAUTION':
            return {
                'mode': 'SNIPER_PROFIT',
                'wait_minutes': 5,
                'stability_check': 5,
                'label': '🎯 Sniper - Lock Max Profit & Exit',
                'description': 'Market shifting, take max profit within 5min',
            }
        elif direction == 'MIXED' and strength == 'RECOVERY':
            return {
                'mode': 'WAIT_RECOVERY',
                'wait_minutes': 10,
                'stability_check': 5,
                'label': '⏳ Wait Recovery',
                'description': 'Temp dip, wait for upcoming rally',
            }
        else:
            return {
                'mode': 'CAUTIOUS',
                'wait_minutes': 5,
                'stability_check': 5,
                'label': '⚪ Cautious - Watch 5min',
                'description': 'Market unclear, sell on 5min stability',
            }

    def _determine_buy_mode(self, combined: dict) -> dict:
        direction = combined.get('direction', 'NEUTRAL')
        strength  = combined.get('strength', 'NEUTRAL')

        if direction == 'BULLISH' and strength == 'STRONG':
            return {
                'mode': 'AGGRESSIVE',
                'min_confidence': 55,
                'max_amount': 30,
                'max_positions': 20,
                'label': '🟢🟢 Aggressive - Buy Strong',
            }
        elif direction == 'MIXED' and strength == 'RECOVERY':
            return {
                'mode': 'CAUTIOUS_BUY',
                'min_confidence': 65,
                'max_amount': 22,
                'max_positions': 12,
                'label': '⏳ Cautious - Wait Then Buy',
            }
        elif direction == 'NEUTRAL':
            return {
                'mode': 'BALANCED',
                'min_confidence': 65,
                'max_amount': 22,
                'max_positions': 12,
                'label': '⚪ Balanced',
            }
        elif direction == 'MIXED' and strength == 'CAUTION':
            return {
                'mode': 'MINIMAL',
                'min_confidence': 75,
                'max_amount': 15,
                'max_positions': 5,
                'label': '⚠️ Minimal - Strong Signals Only',
            }
        elif direction == 'BEARISH' and strength == 'STRONG':
            return {
                'mode': 'NO_BUY',
                'min_confidence': 90,
                'max_amount': 12,
                'max_positions': 3,
                'label': '🔴🔴 No Buy - Rare Only',
            }
        else:
            return {
                'mode': 'BALANCED',
                'min_confidence': 65,
                'max_amount': 22,
                'max_positions': 12,
                'label': '⚪ Balanced',
            }

    def _empty_prediction(self) -> dict:
        return {
            'short': {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            'medium': {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            'combined': {
                'direction': 'NEUTRAL',
                'strength': 'NEUTRAL',
                'confidence': 50,
                'reason': '⚪ No data',
            },
            'sell_mode': {
                'mode': 'NORMAL',
                'wait_minutes': 0,
                'stability_check': 0,
                'label': '👑 Normal System',
                'description': 'No prediction available',
            },
            'buy_mode': {
                'mode': 'BALANCED',
                'min_confidence': 65,
                'max_amount': 22,
                'max_positions': 12,
                'label': '⚪ Balanced',
            },
        }