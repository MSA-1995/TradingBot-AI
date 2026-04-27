"""
🔴 Meta Sell - Smart Peak System
👑 meta_trading (40) + 7 Voters (40) + Support (20) = 100
"""

import gc
import logging
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

from config import (
    MIN_SELL_CONFIDENCE, MIN_SELL_PROFIT,
    get_prediction_modes, MACRO_SELL_POINTS
)
from meta.meta_utils import adjust_threshold_by_forecasts, extract_volumes

logger = logging.getLogger(__name__)


class SellMixin:

    def should_sell(self, symbol: str, position: dict,
                    current_price: float, analysis: dict,
                    mtf, candles=None,
                    preloaded_advisors=None) -> dict:

        # ══════════════════════════════════════
        # 1. Spike Detection - Instant (No Voting)
        # ══════════════════════════════════════
        spike = self._calculate_profit_spike_features(
            symbol, position, current_price)

        if spike.get('is_spike') == 1 and spike.get('spike_type') == 'POSITIVE':
            buy_price  = float(position.get('buy_price', 0) or 0)
            profit     = ((current_price - buy_price) / buy_price * 100
                          if buy_price > 0 else 0)
            emoji = '🚀'
            label = 'PROFIT SPIKE'


            return {
                'action'    : 'SELL',
                'reason'    : (f"{emoji} {label}: "
                               f"{spike.get('profit_jump',0):.1f}% in "
                               f"{spike.get('time_diff',0):.0f}s"),
                'profit'    : profit,
                'sell_votes': {}
            }

        # ══════════════════════════════════════
        # Setup
        # ══════════════════════════════════════
        ai  = {}
        rl  = analysis.get('risk_level',     50)
        wts = analysis.get('whale_score',     0)
        ss  = analysis.get('sentiment_score', 0)
        ai['risk_level']           = rl
        ai['whale_tracking_score'] = wts
        ai['sentiment_score']      = ss

        buy_price     = float(position.get('buy_price', 0) or 0)
        current_price = float(analysis.get('close', 0) or 0)
        profit_pct    = (((current_price - buy_price) / buy_price * 100)
                         if buy_price > 0 else 0.0)
        rsi          = analysis.get('rsi',          50)
        macd_diff    = analysis.get('macd_diff',     0)
        volume_ratio = analysis.get('volume_ratio', 1.0)

        # ══════════════════════════════════════
        # MacroTrend
        # ══════════════════════════════════════
        sell_mode    = None
        macro_status = '⚪ NEUTRAL'
        dyn_min      = MIN_SELL_PROFIT

        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                macro_status       = macro.get_macro_status()
                ai['macro_status'] = macro_status
                prediction         = macro.predict_market()
                combined           = prediction.get('combined', {})
                pd_dir = combined.get('direction', 'NEUTRAL')
                pd_str = combined.get('strength',  'NEUTRAL')

                if   pd_dir == 'MIXED' and pd_str == 'RECOVERY':
                    smart = 'BULLISH'
                elif pd_dir == 'MIXED' and pd_str == 'CAUTION':
                    smart = 'BEARISH'
                else:
                    smart = pd_dir

                _, sell_mode = get_prediction_modes(macro_status, smart)

                # Save predictions for Meta (1h + 4h + current)
                ai['macro_prediction'] = {
                    'current': macro_status,
                    '1h': prediction.get('short', {}).get('prediction', 'NEUTRAL'),
                    '4h': prediction.get('medium', {}).get('prediction', 'NEUTRAL'),
                    '1h_confidence': prediction.get('short', {}).get('confidence', 50),
                    '4h_confidence': prediction.get('medium', {}).get('confidence', 50),
                    'direction': pd_dir,
                    'strength': pd_str,
                }
                ai['1h_bullish'] = 'BULL' in str(prediction.get('short', {}).get('prediction', ''))
                ai['4h_bullish'] = 'BULL' in str(prediction.get('medium', {}).get('prediction', ''))
                ai['1h_bearish'] = 'BEAR' in str(prediction.get('short', {}).get('prediction', ''))
                ai['4h_bearish'] = 'BEAR' in str(prediction.get('medium', {}).get('prediction', ''))
                dyn_min = max(
                    sell_mode.get('min_sell_profit', MIN_SELL_PROFIT),
                    MIN_SELL_PROFIT)
        except Exception as e:
            logger.warning(f"Sell macro error: {e}")


        # ══════════════════════════════════════
        # ENSURE sell_mode is ALWAYS set
        # ══════════════════════════════════════
        if sell_mode is None:
            from config import SELL_MODE_CAUTIOUS
            sell_mode = SELL_MODE_CAUTIOUS



        # ══════════════════════════════════════
        # ══════════════════════════════════════
        # MARKET INTELLIGENCE for Sell (SMART)
        # ══════════════════════════════════════
        _intel = analysis.get('market_intelligence', {})
        _bullish = _intel.get('bullish_score', 50)
        _adx = _intel.get('adx', 20)
        _reversal = analysis.get('reversal', {})
        _reversal_conf = _reversal.get('confidence', 0)
        _reversal_signals = _reversal.get('reversal_signals', 0)
        _flash = analysis.get('flash_crash_protection', {})
        _flash_risk = _flash.get('risk_score', 0) if isinstance(_flash.get('risk_score'), (int, float)) else 0
        _1h_bull = ai.get('1h_bullish', False)
        _4h_bull = ai.get('4h_bullish', False)
        _1h_bear = ai.get('1h_bearish', False)
        _4h_bear = ai.get('4h_bearish', False)

        # Smart multiplier from ALL indicators
        _factors = []

        # 1. Market regime (bullish_score 0-100)
        _factors.append(_bullish / 100.0)  # 0.0 to 1.0

        # 2. Reversal signals (if coin shows bounce signs -> widen)
        if _reversal_conf > 0:
            _factors.append(_reversal_conf / 100.0)  # 0.0 to 1.0

        # 3. Future prediction (1h + 4h)
        if _1h_bull and _4h_bull:
            _factors.append(1.0)  # future good -> widen
        elif _1h_bull:
            _factors.append(0.7)
        elif _1h_bear and _4h_bear:
            _factors.append(0.0)  # future bad -> tighten
        elif _1h_bear:
            _factors.append(0.3)
        else:
            _factors.append(0.5)  # neutral

        # 4. Flash crash risk
        if _flash_risk > 0:
            _factors.append(max(0, (100 - _flash_risk) / 100.0))

        # 5. RSI (oversold = might bounce -> widen)
        _rsi = analysis.get('rsi', 50)
        _factors.append(_rsi / 100.0)

        # Average all factors -> multiplier
        _avg = sum(_factors) / len(_factors) if _factors else 0.5
        # Scale: avg=0 -> mult=0.4, avg=0.5 -> mult=1.0, avg=1.0 -> mult=1.6
        _market_mult = _avg * 1.6 + 0.4 * (1.0 - _avg)

        # 2. Stop Loss - Instant
        # ══════════════════════════════════════
        sl   = self._calculate_stop_loss_features(
            position, current_price, analysis, rl, wts, ss)
        drop = sl.get('drop_from_peak', 0)
        slt  = sl.get('threshold',      0)
        if sell_mode:
            slt *= sell_mode.get('stop_loss_mult', 1.0)
            slt *= _market_mult  # Market regime adjustment
        if drop >= slt:
            gc.collect()
            return {
                'action'             : 'SELL',
                'reason'             : (f'🛡️ Stop Loss: {drop:.1f}%>='
                                        f'{slt:.1f}%'),
                'profit'             : profit_pct,
                'sell_votes'         : {},
                'stop_loss_threshold': slt
            }

        # ══════════════════════════════════════
        # 3. Minimum Profit Threshold
        # ══════════════════════════════════════
        if profit_pct < dyn_min:
            if sl.get('is_stop_loss') == 1:
                pass
            else:
                reason = (f'🛡️ Stop Loss Zone: {profit_pct:.2f}% | SL Trigger: -{slt:.2f}%'
                          if profit_pct < -1.0
                          else f'⏳ Waiting: {profit_pct:.2f}% < {dyn_min:.1f}%')
                return {'action':'HOLD','reason':reason,'profit':profit_pct,'stop_loss_threshold':slt}

        # ══════════════════════════════════════
        # Support Inputs
        # ══════════════════════════════════════
        ai.update(self._gather_stop_loss_intelligence(
            symbol, analysis, volume_ratio, sl))

        symbol_memory = self._get_symbol_memory(symbol)
        features = self._build_meta_features(
            rsi=rsi, macd_diff=macd_diff,
            volume_ratio=volume_ratio,
            price_momentum=analysis.get('price_momentum', 0),
            atr=analysis.get('atr', 2.5),
            analysis_data=analysis,
            advisors_intelligence=ai,
            symbol_memory=symbol_memory
        )

        # ══════════════════════════════════════
        # 👑 meta_trading = 40 Points
        # ══════════════════════════════════════
        _, meta_conf, coin_fc, market_fc = self._run_meta_model(
            features, ai, direction='sell')
        meta_conf   = max(0.0, min(100.0, meta_conf))
        meta_points = (meta_conf / 100) * 40

        # ══════════════════════════════════════
        # 7 Peak Advisors = 60 Points (detect peak)
        # ══════════════════════════════════════
        core_votes = self._run_sell_core_voting(
            symbol, analysis,
            candles if candles else [],
            current_price)

        candle_p = (core_votes.get('candle_expert',   0) / 100) * 8
        chart_p  = (core_votes.get('chart_cnn',       0) / 100) * 8
        rtpa_p   = (core_votes.get('realtime_pa',     0) / 100) * 8
        mtf_p    = (core_votes.get('multitimeframe',  0) / 100) * 4
        trend_p  = (core_votes.get('trend_detector',  0) / 100) * 5
        whale_p  = (core_votes.get('smart_money',     0) / 100) * 5
        vol_p    = (core_votes.get('volume_forecast', 0) / 100) * 2

        core_points = (candle_p + chart_p + rtpa_p
                       + mtf_p  + trend_p + whale_p + vol_p)

        # ══════════════════════════════════════
        # Support Inputs = 20 Points
        # ══════════════════════════════════════

        # RSI Overbought (4)
        rsi_p = 0
        if   rsi > 70: rsi_p = ((rsi - 70) / 30) * 4
        elif rsi > 60: rsi_p = ((rsi - 60) / 10) * 1

        # Fear & Greed (4)
        fg   = analysis.get('sentiment', {}).get('fear_greed', 50)
        fg_p = 0
        if   fg > 70: fg_p = ((fg - 70) / 30) * 4
        elif ss < -1: fg_p = min(abs(ss) / 5 * 2, 2)

        # MACD Bearish (3)
        macd_diff_pct = analysis.get('latest', {}).get('macd_diff_pct', 0.0)
        macd_p = 0
        if macd_diff_pct < 0:
            macd_p = min((min(abs(macd_diff_pct), 0.5) / 0.5) * 3, 3.0)

        # MacroTrend (3) - replaced by MACRO_SELL_POINTS below
        macro_p = 0

        # News Negative (3)
        news_neg = analysis.get('news', {}).get('negative', 0)
        news_p   = min((news_neg / 10) * 3, 3)

        # Anomaly (2)
        anom_p = (analysis.get('anomaly_score', 0) / 100) * 2


        # Prediction Points (1h + 4h forecast)
        _pred = ai.get('macro_prediction', {})
        _1h_bull = ai.get('1h_bullish', False)
        _4h_bull = ai.get('4h_bullish', False)
        _1h_bear = ai.get('1h_bearish', False)
        _4h_bear = ai.get('4h_bearish', False)
        _1h_conf = _pred.get('1h_confidence', 50) / 100.0
        _4h_conf = _pred.get('4h_confidence', 50) / 100.0

        # Sell boost: future looks bad = sell faster
        # Sell penalty: future looks good = hold more
        pred_p = 0
        if _1h_bear and _4h_bear:
            pred_p = (_1h_conf + _4h_conf) * 2.5  # max ~5 (sell faster)
        elif _1h_bear:
            pred_p = _1h_conf * 2.0
        elif _1h_bull and _4h_bull:
            pred_p = -(_1h_conf + _4h_conf) * 2.5  # max ~-5 (hold more)
        elif _1h_bull:
            pred_p = -_1h_conf * 2.0

        support_total = min(
            rsi_p + fg_p + macd_p + macro_p + news_p + anom_p + pred_p, 25)

        # ══════════════════════════════════════
        # Total Score
        # ══════════════════════════════════════
        sell_points = min(meta_points + core_points + support_total, 100)

        # ══════════════════════════════════════
        # 🌐 Macro Trend Voting = ±10 Points
        # ══════════════════════════════════════
        try:
            _macro_pred   = ai.get('macro_prediction', {})
            _now          = _macro_pred.get('current', '')
            _1h           = _macro_pred.get('1h', 'NEUTRAL')
            _4h           = _macro_pred.get('4h', 'NEUTRAL')

            def _macro_state(s):
                if 'BULL' in str(s): return 'BULL'
                if 'BEAR' in str(s): return 'BEAR'
                return 'NEUT'

            _key              = (_macro_state(_now), _macro_state(_1h), _macro_state(_4h))
            macro_sell_points = MACRO_SELL_POINTS.get(_key, 0)
            sell_points       = sell_points + macro_sell_points
            ai['macro_sell_points'] = macro_sell_points
            ai['macro_sell_key']    = str(_key)
        except Exception as e:
            logger.warning('Macro sell points error: ' + str(e))
            macro_sell_points = 0

        # Smart Sell - only for emergency modes (EXIT/RECOVERY)
        if sell_mode and sell_mode.get('mode') in ('SNIPER_EXIT', 'WAIT_RECOVERY', 'CAUTIOUS'):
            smart = self._smart_sell_check(
                symbol, position, profit_pct, sell_mode)
            if smart:
                return smart
        

        # Wave Protection
        return self._wave_protection(
            symbol, analysis, candles, position,
            ai, rsi, macd_diff, volume_ratio,
            profit_pct,
            analysis.get('peak', {}).get('confidence', 0),
            core_votes,
            sum(1 for v in core_votes.values() if v >= 50),
            len(core_votes)
        )

    # ─────────────────────────────────────────────
    # Smart Sell
    # ─────────────────────────────────────────────

    def _smart_sell_check(self, symbol, position,
                           profit_pct, sell_mode):
        mode  = sell_mode.get('mode',              'NORMAL')
        stab  = sell_mode.get('stability_minutes', 5)
        minp  = sell_mode.get('min_sell_profit',   MIN_SELL_PROFIT)
        label = sell_mode.get('label',             '')
        key   = f"{symbol}_smart_sell"
        now   = __import__('time').time()

        if not hasattr(self, '_smart_sell_tracker'):
            self._smart_sell_tracker = {}

        tr = self._smart_sell_tracker.get(key, {
            'highest_profit': profit_pct,
            'stable_since'  : now,
            'last_profit'   : profit_pct,
        })

        if mode == 'SNIPER_EXIT':
            if profit_pct > tr.get('highest_profit', profit_pct):
                self._smart_sell_tracker.pop(key, None)
                return {'action': 'SELL',
                        'reason': (f'🛡️ Rescue: Bounce |'
                                   f' {profit_pct:.2f}% | {label}'),
                        'profit': profit_pct, 'sell_votes': {}}
            elif abs(profit_pct - tr.get('last_profit', profit_pct)) < 0.1:
                stable = (now - tr.get('stable_since', now)) / 60
                if stable >= stab:
                    self._smart_sell_tracker.pop(key, None)
                    return {'action': 'SELL',
                            'reason': (f'🛡️ Rescue: Stable {stable:.0f}m |'
                                       f' {profit_pct:.2f}% | {label}'),
                            'profit': profit_pct, 'sell_votes': {}}
                tr['last_profit'] = profit_pct
                self._smart_sell_tracker[key] = tr
                return None
            else:
                self._smart_sell_tracker.pop(key, None)
                return {'action': 'SELL',
                        'reason': (f'🛡️ Rescue: Drop |'
                                   f' {profit_pct:.2f}% | {label}'),
                        'profit': profit_pct, 'sell_votes': {}}

        elif mode == 'WAIT_RECOVERY':
            if profit_pct >= minp:
                self._smart_sell_tracker.pop(key, None)
                return {'action': 'SELL',
                        'reason': (f'⏳ Recovery: {profit_pct:.2f}%'
                                   f' | {label}'),
                        'profit': profit_pct, 'sell_votes': {}}
            tr['last_profit'] = profit_pct
            self._smart_sell_tracker[key] = tr
            return None

        elif mode == 'CAUTIOUS':
            if profit_pct > tr.get('highest_profit', profit_pct):
                tr.update({'highest_profit': profit_pct,
                           'stable_since'  : now,
                           'last_profit'   : profit_pct})
                self._smart_sell_tracker[key] = tr
                return None
            elif abs(profit_pct - tr.get('last_profit', profit_pct)) < 0.1:
                stable = (now - tr.get('stable_since', now)) / 60
                if stable >= stab and profit_pct >= minp:
                    self._smart_sell_tracker.pop(key, None)
                    return {'action': 'SELL',
                            'reason': (f'⚪ Cautious: Stable {stable:.0f}m'
                                       f' | {profit_pct:.2f}% | {label}'),
                            'profit': profit_pct, 'sell_votes': {}}
                tr['last_profit'] = profit_pct
                self._smart_sell_tracker[key] = tr
                return None
            else:
                if profit_pct < minp:
                    tr['last_profit'] = profit_pct
                    self._smart_sell_tracker[key] = tr
                    return None
                self._smart_sell_tracker.pop(key, None)
                return {'action': 'SELL',
                        'reason': (f'⚪ Cautious: Drop |'
                                   f' {profit_pct:.2f}% | {label}'),
                        'profit': profit_pct, 'sell_votes': {}}

        return None

    # ─────────────────────────────────────────────
    # Wave Protection
    # ─────────────────────────────────────────────

    def _wave_protection(self, symbol, analysis, candles,
                          position, ai, rsi, macd_diff,
                          volume_ratio, profit_pct, peak_score,
                          sell_votes, sell_vote_count,
                          total_advisors):
        highest = position.get(
            'highest_price',
            float(position.get('buy_price', 0) or 0))
        current = float(analysis.get('close', 0))
        drop    = ((highest - current) / highest * 100
                   if highest > 0 else 0)

        atr       = analysis.get('atr', 0) or 0
        threshold = max(ai.get('risk_level', 50) / 25,
                        atr * self.STOP_ATR_MULT)
        threshold += (ai.get('risk_level', 50) - 50) / 100 * 3
        threshold -= (ai.get('whale_tracking_score', 0) / 200) * 2
        threshold += (max(-10, min(10, ai.get('sentiment_score', 0)))
                      / 100) * 2
        threshold  = max(self.STOP_TRAILING_MIN,
                         min(self.STOP_TRAILING_MAX, threshold))

        c_fc, m_fc = self._calc_stop_forecasts(
            ai, rsi, macd_diff, volume_ratio)
        threshold  = adjust_threshold_by_forecasts(
            threshold, c_fc, m_fc, drop)

        if self.realtime_pa and candles and len(candles) >= 3:
            threshold = self._apply_realtime_stop(
                symbol, analysis, candles,
                current_price=current,
                highest_price=highest,
                threshold=threshold)

        # 🛡️ Stop Loss - drop from peak
        if drop >= threshold:
            gc.collect()
            return {
                'action'             : 'SELL',
                'reason'             : (f'🛡️ Wave Stop: {drop:.1f}%>='
                                        f'{threshold:.1f}%'),
                'profit'             : profit_pct,
                'sell_votes'         : sell_votes,
                'peak_score'         : peak_score,
                'stop_loss_threshold': threshold,
                'coin_forecast'      : c_fc,
                'market_forecast'    : m_fc
            }

        # 🎯 Smart Peak Sell - points system (like buy but reversed)
        if profit_pct >= dyn_min:
            # Meta: 20 points max (less trust for selling)
            meta_sell_conf = sell_votes.get('meta_trading', 0)
            meta_points = (meta_sell_conf / 100) * 20

            # Advisors: 60 points max (they detect the peak)
            candle_p  = (sell_votes.get('candle_expert',   0) / 100) * 12
            chart_p   = (sell_votes.get('chart_cnn',       0) / 100) * 12
            rtpa_p    = (sell_votes.get('realtime_pa',     0) / 100) * 12
            mtf_p     = (sell_votes.get('multitimeframe',  0) / 100) * 8
            trend_p   = (sell_votes.get('trend_detector',  0) / 100) * 8
            whale_p   = (sell_votes.get('smart_money',     0) / 100) * 5
            vol_p     = (sell_votes.get('volume_forecast', 0) / 100) * 3
            core_points = candle_p + chart_p + rtpa_p + mtf_p + trend_p + whale_p + vol_p

            # Support: 20 points max
            support_points = min(peak_score / 100 * 20, 20)

            # Total
            sell_points = min(meta_points + core_points + support_points, 100)
            required = 60

            if sell_points >= required:
                gc.collect()
                return {
                    'action'             : 'SELL',
                    'reason'             : (f'🎯 Peak Points: {sell_points:.0f}/{required}pts | '
                                            f'Core:{core_points:.0f}/60 | '
                                            f'Peak:{peak_score}'),
                    'profit'             : profit_pct,
                    'sell_votes'         : sell_votes,
                    'peak_score'         : peak_score,
                    'stop_loss_threshold': threshold,
                    'coin_forecast'      : c_fc,
                    'market_forecast'    : m_fc
                }

        gc.collect()
        return {
            'action'             : 'HOLD',
            'reason'             : (f'Wave Riding | '
                                    f'Profit:{profit_pct:+.1f}% | '
                                    f'Peak:{peak_score} | '
                                    f'Votes:{sell_vote_count}/'
                                    f'{total_advisors}'),
            'profit'             : profit_pct,
            'sell_votes'         : sell_votes,
            'peak_score'         : peak_score,
            'stop_loss_threshold': threshold
        }

    # ─────────────────────────────────────────────
    # Helper Functions
    # ─────────────────────────────────────────────

    def _apply_mtf_peak_boost(self, symbol, analysis,
                               candles, position, ai, sell_conf):
        return sell_conf

    def _apply_realtime_stop(self, symbol, analysis, candles,
                              current_price, highest_price, threshold):
        try:
            trigger = self.realtime_pa.analyze_stop_loss_trigger(
                candles=candles,
                current_price=current_price,
                highest_price=highest_price,
                stop_threshold=threshold
            )
            if trigger['trigger_soon']:
                eta = trigger.get('time_estimate', 999)
                if   eta < self.STOP_TIME_WARN: threshold *= 0.6
                elif eta < self.STOP_TIME_NEAR: threshold *= 0.8
                else:                           threshold *= 0.9
        except Exception as e:
            logger.warning(f"Realtime stop error: {e}")
        return threshold

    def _calc_stop_forecasts(self, ai, rsi, macd_diff, volume_ratio):
        c_fc = {'direction': 'neutral', 'confidence': 50}
        m_fc = {'direction': 'neutral', 'confidence': 50}
        try:
            if rsi < self.RSI_OVERSOLD and volume_ratio > 2.0:
                c_fc = {'direction': 'bullish', 'confidence': 70}
            elif rsi > self.RSI_OVERBOUGHT or macd_diff < -2:
                c_fc = {'direction': 'bearish', 'confidence': 75}
            mb = ai.get('macro_bear_signal', 0)
            ms = ai.get('macro_trend_sell',  50)
            if   mb == 1: m_fc = {'direction': 'bearish', 'confidence': 80}
            elif ms < 30: m_fc = {'direction': 'bearish', 'confidence': 70}
            elif ms > 70: m_fc = {'direction': 'bullish', 'confidence': 70}
        except Exception as e:
            logger.warning(f"Stop forecast error: {e}")
        return c_fc, m_fc

    def _calculate_profit_spike_features(self, symbol,
                                          position, current_price):
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'profit_jump':0,'time_diff':0,
                        'is_spike':0,'spike_type':'NONE'}
            current_profit = ((current_price - buy_price)
                              / buy_price * 100)
            now = datetime.now(timezone.utc)
            self.profit_history.setdefault(symbol, [])
            history     = self.profit_history[symbol]
            profit_jump = time_diff = is_spike = 0
            spike_type  = 'NONE'
            if history:
                last_time, last_profit = history[-1]
                last_profit = last_profit or 0
                time_diff   = (now - last_time).total_seconds()
                if time_diff < self.SPIKE_TIME_WINDOW:
                    profit_jump = current_profit - last_profit
                    if profit_jump >= self.SPIKE_POSITIVE_THRESHOLD:
                        is_spike = 1; spike_type = 'POSITIVE'
                    elif profit_jump <= self.SPIKE_NEGATIVE_THRESHOLD:
                        is_spike = 1; spike_type = 'NEGATIVE'
            history.append((now, current_profit))
            if len(history) > self.MAX_PROFIT_HISTORY:
                self.profit_history[symbol] = \
                    history[-self.MAX_PROFIT_HISTORY:]
            return {'profit_jump':    profit_jump,
                    'time_diff':      time_diff,
                    'is_spike':       is_spike,
                    'spike_type':     spike_type,
                    'current_profit': current_profit}
        except Exception as e:
            logger.warning(f"Spike error: {e}")
            return {'profit_jump':0,'time_diff':0,
                    'is_spike':0,'spike_type':'NONE'}

    def _calculate_stop_loss_features(self, position, current_price,
                                       analysis, risk_level,
                                       whale_tracking_score,
                                       sentiment_score):
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'drop_from_peak':0,'threshold':0,'is_stop_loss':0}
            highest   = position.get('highest_price', buy_price)
            drop      = ((highest - current_price) / highest * 100
                         if highest > 0 else 0)
            atr_p     = analysis.get('atr_percent',  2.5)
            vr        = analysis.get('volume_ratio', 1.0)
            rsi       = analysis.get('rsi',           50)
            threshold = atr_p * (1 + risk_level / 100)
            threshold += (vr - 1.0) * 0.5
            threshold += (50 - rsi) / 100
            threshold -= whale_tracking_score / 500
            threshold += sentiment_score / 200
            threshold  = max(atr_p * 0.5, min(atr_p * 3.0, threshold))
            profit_pct = ((current_price - buy_price) / buy_price * 100)
            is_sl      = (1 if drop >= threshold
                          or profit_pct <= -(threshold * 1.5) else 0)
            return {'drop_from_peak': drop,
                    'threshold':      threshold,
                    'is_stop_loss':   is_sl,
                    'profit_percent': profit_pct}
        except Exception as e:
            logger.warning(f"SL features error: {e}")
            return {'drop_from_peak':0,'threshold':0,'is_stop_loss':0}
