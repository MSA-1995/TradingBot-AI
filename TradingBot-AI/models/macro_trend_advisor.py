"""
📈 Macro Trend Advisor - Market Trend + Next Hour Prediction
Determines current market state and predicts next direction
"""

import time
from typing import Optional

import numpy as np
import pandas as pd


class MacroTrendAdvisor:
    """
    Determines overall market state and predicts next direction
    """

    MACRO_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']

    CACHE_DURATION      = 300  # 5 دقائق - حالة السوق
    PREDICTION_CACHE_1H = 300  # 5 دقائق - بيانات 1h
    PREDICTION_CACHE_4H = 300  # 5 دقائق - بيانات 4h

    RSI_PERIOD        = 14
    MOMENTUM_LOOKBACK = 10

    def __init__(self, exchange=None):
        self.exchange = exchange

        # حالة السوق
        self._last_status     : str   = '⚪ NEUTRAL'
        self._last_check_time : float = 0.0

        # كاش predict_market المجمّع
        self._last_prediction      : dict  = {}
        self._last_prediction_time : float = 0.0

        # كاش منفصل لكل timeframe
        self._last_1h_prediction      : dict  = {}
        self._last_1h_prediction_time : float = 0.0
        self._last_4h_prediction      : dict  = {}
        self._last_4h_prediction_time : float = 0.0

    # ─────────────────────────────────────────────
    # Main Interface
    # ─────────────────────────────────────────────

    def get_macro_status(self) -> str:
        """الحالة الحقيقية من إشارات 1h + 4h الفعلية - تتحدث كل 5 دقائق"""
        if not self.exchange:
            return '⚪ NEUTRAL'

        if time.time() - self._last_check_time < self.CACHE_DURATION:
            return self._last_status

        try:
            pred = self.predict_market()

            # استخدام combined المحسوب بدل جمع short + medium منفصلين
            combined_dir = pred.get('combined', {}).get('direction', 'NEUTRAL')
            combined_str = pred.get('combined', {}).get('strength',  'NEUTRAL')

            if   combined_dir == 'BULLISH' and combined_str == 'STRONG': final_status = '🟢 BULL_MARKET'
            elif combined_dir == 'BEARISH' and combined_str == 'STRONG': final_status = '🔴 BEAR_MARKET'
            elif combined_dir == 'BULLISH':                               final_status = '🟢 MILD_BULL'
            elif combined_dir == 'BEARISH':                               final_status = '🔴 MILD_BEAR'
            elif combined_dir == 'MIXED'  and combined_str == 'CAUTION': final_status = '⚪ SIDEWAYS'
            else:                                                          final_status = '⚪ SIDEWAYS'

            # للعرض فقط
            short_bull  = pred.get('short',  {}).get('bull_score', 0)
            short_bear  = pred.get('short',  {}).get('bear_score', 0)
            medium_bull = pred.get('medium', {}).get('bull_score', 0)
            medium_bear = pred.get('medium', {}).get('bear_score', 0)
            total_bull  = short_bull  + medium_bull
            total_bear  = short_bear  + medium_bear

            # تحقق الداتابيز: لو BULL، قارن بالحالة المحفوظة قبل ساعتين
            if 'BULL' in final_status:
                historical = self._get_historical_status(hours_ago=2)
                if historical and 'BEAR' in historical:
                    final_status = '⚪ SIDEWAYS'  # تعارض مع الحالة السابقة

            short_p  = pred.get('short',  {}).get('prediction', '?')
            medium_p = pred.get('medium', {}).get('prediction', '?')
            s1 = '🟢' if 'BULL' in str(short_p)  else ('🔴' if 'BEAR' in str(short_p)  else '⚪')
            s4 = '🟢' if 'BULL' in str(medium_p) else ('🔴' if 'BEAR' in str(medium_p) else '⚪')

            self._display_info = {
                'status'    : final_status,
                '1h_icon'   : s1,
                '4h_icon'   : s4,
                '1h_details': pred.get('short',  {}).get('details', ''),
                '4h_details': pred.get('medium', {}).get('details', ''),
                'total_bull': total_bull,
                'total_bear': total_bear,
            }

            self._last_status     = final_status
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
            'status'    : self._last_status,
            '1h_icon'   : '⚪',
            '4h_icon'   : '⚪',
            '1h_details': '',
            '4h_details': '',
            'total_bull': 0,
            'total_bear': 0,
        }

    def can_aim_high(self) -> bool:
        return 'BULL' in self.get_macro_status()

    def invalidate_cache(self) -> None:
        """إعادة ضبط كل الكاش"""
        self._last_check_time         = 0.0
        self._last_prediction_time    = 0.0
        self._last_1h_prediction_time = 0.0
        self._last_4h_prediction_time = 0.0

    # ─────────────────────────────────────────────
    # Indicators
    # ─────────────────────────────────────────────

    def _calculate_rsi(self, prices: pd.Series) -> float:
        delta = prices.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(self.RSI_PERIOD).mean()
        rs    = gain / loss.replace(0, np.nan)
        return float((100 - (100 / (1 + rs))).iloc[-1])

    def _calculate_momentum(self, prices: pd.Series, current_price: float) -> float:
        past_price = float(prices.iloc[-self.MOMENTUM_LOOKBACK])
        if past_price == 0:
            return 0.0
        return ((current_price - past_price) / past_price) * 100

    # ═════════════════════════════════════════════
    # 🔮 Prediction System
    # ═════════════════════════════════════════════

    def predict_market(self) -> dict:
        """تتحدث كل 5 دقائق"""
        if not self.exchange:
            return self._empty_prediction()

        if time.time() - self._last_prediction_time < self.CACHE_DURATION:
            return self._last_prediction

        try:
            short    = self._predict_timeframe('1h', 24)
            medium   = self._predict_timeframe('4h', 24)
            combined = self._combine_timeframes(short, medium)

            result = {
                'short'   : short,
                'medium'  : medium,
                'combined': combined,
            }

            self._last_prediction      = result
            self._last_prediction_time = time.time()
            return result

        except Exception as e:
            print(f"⚠️ predict_market error: {e}")
            return self._empty_prediction()

    def _predict_timeframe(self, timeframe: str, limit: int) -> dict:
        """كل timeframe له كاش مستقل - كلهم 5 دقائق"""
        if timeframe == '1h':
            cache_dur = self.PREDICTION_CACHE_1H
            last_time = self._last_1h_prediction_time
            last_pred = self._last_1h_prediction
        else:
            cache_dur = self.PREDICTION_CACHE_4H
            last_time = self._last_4h_prediction_time
            last_pred = self._last_4h_prediction

        # رجع الكاش لو ما انتهى
        if time.time() - last_time < cache_dur and last_pred:
            return last_pred

        # جلب بيانات جديدة من API
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

        result = self._combine_predictions(predictions, timeframe)

        # حفظ في الكاش الصحيح
        if timeframe == '1h':
            self._last_1h_prediction      = result
            self._last_1h_prediction_time = time.time()
        else:
            self._last_4h_prediction      = result
            self._last_4h_prediction_time = time.time()

        return result

    def _predict_symbol_direction(self, symbol: str, timeframe: str, limit: int) -> Optional[dict]:
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df    = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

        if len(df) < 10:
            return None

        bull_signals = 0
        bear_signals = 0

        # 1. Last 3 candles direction (weight 3)
        last_3_change = (
            (float(df['c'].iloc[-1]) - float(df['c'].iloc[-4]))
            / float(df['c'].iloc[-4]) * 100
        )
        if   last_3_change >  0.5: bull_signals += 3
        elif last_3_change < -0.5: bear_signals += 3
        elif last_3_change >  0:   bull_signals += 1
        elif last_3_change <  0:   bear_signals += 1

        # 2. RSI (weight 2)
        rsi = self._calculate_rsi(df['c'])
        if   rsi > 80: bear_signals += 1
        elif rsi > 65: bull_signals += 2
        elif rsi > 55: bull_signals += 1
        elif rsi < 25: bull_signals += 2
        elif rsi < 40: bear_signals += 1

        # 3. Volume (weight 2)
        avg_vol   = float(df['v'].iloc[-20:].mean())
        last_vol  = float(df['v'].iloc[-1])
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        if   vol_ratio > 1.5 and last_3_change > 0: bull_signals += 2
        elif vol_ratio > 1.5 and last_3_change < 0: bear_signals += 2
        elif vol_ratio < 0.5:                        bear_signals += 1
        elif vol_ratio < 1.2 and last_3_change > 0: bear_signals += 3  # صعود وهمي بحجم خفيف

        # 4. MACD Direction (weight 2)
        macd         = df['c'].ewm(span=12).mean() - df['c'].ewm(span=26).mean()
        macd_current = float(macd.iloc[-1])
        macd_prev    = float(macd.iloc[-2])

        if   macd_current > macd_prev and macd_current > 0: bull_signals += 2
        elif macd_current > macd_prev:                       bull_signals += 1
        elif macd_current < macd_prev and macd_current < 0: bear_signals += 2
        elif macd_current < macd_prev:                       bear_signals += 1

        # 5. EMA Cross (weight 1)
        ema_9  = float(df['c'].ewm(span=9).mean().iloc[-1])
        ema_21 = float(df['c'].ewm(span=21).mean().iloc[-1])
        if ema_9 > ema_21: bull_signals += 1
        else:              bear_signals += 1

        # 6. Reversal candle (weight 2)
        c_last       = float(df['c'].iloc[-1])
        o_last       = float(df['o'].iloc[-1])
        h_last       = float(df['h'].iloc[-1])
        l_last       = float(df['l'].iloc[-1])
        candle_body  = abs(c_last - o_last)
        candle_range = h_last - l_last

        if candle_range > 0:
            body_ratio   = candle_body / candle_range
            upper_shadow = h_last - max(c_last, o_last)
            lower_shadow = min(c_last, o_last) - l_last

            if   upper_shadow > candle_body * 2 and body_ratio < 0.3: bear_signals += 2
            elif lower_shadow > candle_body * 2 and body_ratio < 0.3: bull_signals += 2

        return {'symbol': symbol, 'bull': bull_signals, 'bear': bear_signals}

    # ─────────────────────────────────────────────
    # 🔮 Combine Predictions
    # ─────────────────────────────────────────────

    def _combine_predictions(self, predictions: list, timeframe: str) -> dict:
        total_bull = sum(p['bull'] for p in predictions)
        total_bear = sum(p['bear'] for p in predictions)
        total      = total_bull + total_bear

        if total == 0:
            return {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No signals'}

        # شرط ثنين من ثلاثة: لازم عملتين على الأقل يتفقان على نفس الاتجاه
        bull_count = sum(1 for p in predictions if p['bull'] > p['bear'])
        bear_count = sum(1 for p in predictions if p['bear'] > p['bull'])
        if bull_count < 2 and bear_count < 2:
            details = ', '.join(
                f"{p['symbol'].split('/')[0]}(🟢{p['bull']}/🔴{p['bear']})"
                for p in predictions
            )
            return {
                'prediction': 'NEUTRAL',
                'confidence': 50,
                'bull_score': total_bull,
                'bear_score': total_bear,
                'reason'    : f'⚪ No consensus (2/3 required) - {"Next 1h" if timeframe == "1h" else "Next 4h"}',
                'details'   : details,
            }

        bull_pct = total_bull / total * 100
        bear_pct = total_bear / total * 100
        tf_label = 'Next 1h' if timeframe == '1h' else 'Next 4h'

        if   bull_pct >= 75: prediction, confidence, reason = 'STRONG_BULLISH', bull_pct, f'🟢🟢 Strong Bullish - {tf_label}'
        elif bull_pct >= 60: prediction, confidence, reason = 'BULLISH',        bull_pct, f'🟢 Bullish - {tf_label}'
        elif bear_pct >= 75: prediction, confidence, reason = 'STRONG_BEARISH', bear_pct, f'🔴🔴 Strong Bearish - {tf_label}'
        elif bear_pct >= 60: prediction, confidence, reason = 'BEARISH',        bear_pct, f'🔴 Bearish - {tf_label}'
        else:                prediction, confidence, reason = 'NEUTRAL',        50,       f'⚪ Neutral - {tf_label}'

        details = ', '.join(
            f"{p['symbol'].split('/')[0]}(🟢{p['bull']}/🔴{p['bear']})"
            for p in predictions
        )

        return {
            'prediction': prediction,
            'confidence': round(confidence, 1),
            'bull_score': total_bull,
            'bear_score': total_bear,
            'reason'    : reason,
            'details'   : details,
        }

    def _combine_timeframes(self, short: dict, medium: dict) -> dict:
        short_pred  = short.get('prediction',  'NEUTRAL')
        medium_pred = medium.get('prediction', 'NEUTRAL')

        is_short_bull  = 'BULL' in short_pred
        is_short_bear  = 'BEAR' in short_pred
        is_medium_bull = 'BULL' in medium_pred
        is_medium_bear = 'BEAR' in medium_pred

        if   is_short_bull and is_medium_bull:
            return {'direction': 'BULLISH', 'strength': 'STRONG',   'confidence': max(short['confidence'], medium['confidence']), 'reason': '🟢🟢 Confirmed Bullish (1h + 4h)'}
        elif is_short_bear and is_medium_bear:
            return {'direction': 'BEARISH', 'strength': 'STRONG',   'confidence': max(short['confidence'], medium['confidence']), 'reason': '🔴🔴 Confirmed Bearish (1h + 4h)'}
        elif is_short_bull and is_medium_bear:
            return {'direction': 'MIXED',   'strength': 'CAUTION',  'confidence': 50,                                             'reason': '⚠️ Short Bullish but Medium Bearish (Caution)'}
        elif is_short_bear and is_medium_bull:
            return {'direction': 'MIXED',   'strength': 'RECOVERY', 'confidence': 55,                                             'reason': '⏳ Temp Dip then Recovery (Wait)'}
        else:
            return {'direction': 'NEUTRAL', 'strength': 'NEUTRAL',  'confidence': 50,                                             'reason': '⚪ Market Unclear'}

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _get_historical_status(self, hours_ago: float = 2) -> Optional[str]:
        """
        يقرأ macro_status المحفوظة في bot_settings (key=bot_status)
        ويرجع القيمة المحفوظة — تُستخدم للمقارنة قبل إرجاع BULL.
        الربط: advisor.db = your_database_storage_instance
        """
        try:
            if not hasattr(self, 'db') or self.db is None:
                return None

            raw = self.db.load_setting('bot_status')
            if not raw:
                return None

            import json
            data = json.loads(raw)

            # تحقق الوقت — لو السجل أقدم من hours_ago + 30 دقيقة تجاهله
            saved_time = data.get('time', '')          # مثال: "07:53:26"
            macro      = data.get('macro_status', '')  # مثال: "🔴 BEAR_MARKET"

            if not macro:
                return None

            # المقارنة بالوقت: bot_status يتحدث كل 5 دقائق
            # لو الفرق بين الوقت الحالي والمحفوظ أكبر من (hours_ago * 60 + 30) دقيقة → تجاهل
            if saved_time:
                try:
                    from datetime import datetime
                    now       = datetime.now()
                    saved_dt  = datetime.strptime(saved_time, "%H:%M:%S").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                    diff_mins = (now - saved_dt).total_seconds() / 60
                    max_age   = hours_ago * 60 + 30
                    if diff_mins < 0 or diff_mins > max_age:
                        return None
                except Exception:
                    pass  # لو فشل تحليل الوقت نكمل بالقيمة

            return macro

        except Exception:
            return None

    def _empty_prediction(self) -> dict:
        return {
            'short'   : {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            'medium'  : {'prediction': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            'combined': {'direction': 'NEUTRAL', 'strength': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
        }
