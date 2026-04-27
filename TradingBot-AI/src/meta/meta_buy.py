"""
🟢 Meta Buy - Smart Bottom System
👑 meta_trading (40) + 7 Voters (40) + Support (20) = 100
"""

import logging
from datetime import datetime, timezone
import pandas as pd

from config import (
    MIN_BUY_CONFIDENCE, MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT,
    get_prediction_modes, MACRO_BUY_POINTS
)

logger = logging.getLogger(__name__)


class BuyMixin:

    def should_buy(self, symbol: str, analysis: dict,
                   models_scores=None, candles=None,
                   preloaded_advisors=None) -> dict:
        """👑 Buy Decision"""

        analysis_data = analysis
        reasons       = []

        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action':'DISPLAY','reason':'Invalid data','confidence':0}

        if candles is None:
            candles = analysis_data.get('candles', [])

        # Gather support inputs
        ai = self._gather_buy_advisors_intelligence(
            symbol, analysis_data, reasons)
        ai.update(self._gather_extra_buy_intelligence(
            symbol, analysis_data))

        # ══════════════════════════════════════
        # Mandatory Filter: MacroTrend
        # ══════════════════════════════════════
        buy_mode     = None
        macro_status = '⚪ NEUTRAL'

        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                macro_status       = macro.get_macro_status()
                ai['macro_status'] = macro_status

                prediction  = macro.predict_market()
                combined    = prediction.get('combined', {})
                p_direction = combined.get('direction', 'NEUTRAL')
                p_strength  = combined.get('strength',  'NEUTRAL')

                if p_direction == 'MIXED' and p_strength == 'RECOVERY':
                    smart = 'BULLISH'
                elif p_direction == 'MIXED' and p_strength == 'CAUTION':
                    smart = 'BEARISH'
                else:
                    smart = p_direction

                buy_mode, _ = get_prediction_modes(macro_status, smart)

                # Save predictions for Meta (1h + 4h + current)
                ai['macro_prediction'] = {
                    'current': macro_status,
                    '1h': prediction.get('short', {}).get('prediction', 'NEUTRAL'),
                    '4h': prediction.get('medium', {}).get('prediction', 'NEUTRAL'),
                    '1h_confidence': prediction.get('short', {}).get('confidence', 50),
                    '4h_confidence': prediction.get('medium', {}).get('confidence', 50),
                    'direction': p_direction,
                    'strength': p_strength,
                }
                ai['1h_bullish'] = 'BULL' in str(prediction.get('short', {}).get('prediction', ''))
                ai['4h_bullish'] = 'BULL' in str(prediction.get('medium', {}).get('prediction', ''))
                ai['1h_bearish'] = 'BEAR' in str(prediction.get('short', {}).get('prediction', ''))
                ai['4h_bearish'] = 'BEAR' in str(prediction.get('medium', {}).get('prediction', ''))

        except Exception as e:
            logger.warning(f"MacroTrend error: {e}")

        # Indicators
        rsi            = analysis_data.get('rsi',           50)
        macd_diff_pct  = analysis_data.get('latest', {}).get('macd_diff_pct', 0.0)
        volume_ratio   = analysis_data.get('volume_ratio', 1.0)
        price_momentum = analysis_data.get('price_momentum', 0)
        atr            = analysis_data.get('atr',           2.5)

        # Safety Filters
        flash_risk = (analysis_data.get('flash_crash_protection', {})
                      .get('risk_score', 0))
        if flash_risk >= self.FLASH_RISK_MAX:
            return {'action':'DISPLAY',
                    'reason':f'🚨 Flash Crash ({flash_risk}%)',
                    'confidence':0}

        if ai.get('liquidation_safety', 50) < self.LIQ_SAFETY_MIN:
            return {'action':'DISPLAY',
                    'reason':'🛡️ High Liquidation Risk',
                    'confidence':0}


        # ══════════════════════════════════════
        # ENSURE buy_mode is ALWAYS set
        # ══════════════════════════════════════
        if buy_mode is None:
            from config import BUY_MODE_CAUTIOUS
            buy_mode = BUY_MODE_CAUTIOUS
            reasons.append('MacroTrend unavailable - Cautious mode')

        # ══════════════════════════════════════
        # 👑 meta_trading = 40 Points
        # ══════════════════════════════════════
        symbol_memory = self._get_symbol_memory(symbol)
        features = self._build_meta_features(
            rsi=rsi, macd_diff_pct=macd_diff_pct,
            volume_ratio=volume_ratio,
            price_momentum=price_momentum, atr=atr,
            analysis_data=analysis_data,
            advisors_intelligence=ai,
            symbol_memory=symbol_memory
        )
        buy_prob, confidence, coin_fc, market_fc = self._run_meta_model(
            features, ai, direction='buy')
        confidence  = max(0.0, min(100.0, confidence))
        meta_points = (confidence / 100) * 40

        # ══════════════════════════════════════
        # 7 Bottom Voters = 40 Points
        # ══════════════════════════════════════
        core_votes = self._run_buy_core_voting(
            symbol, analysis_data, candles)

        candle_points  = (core_votes.get('candle_expert',  0) / 100) * 8
        chart_points   = (core_votes.get('chart_cnn',      0) / 100) * 8
        rtpa_points    = (core_votes.get('realtime_pa',    0) / 100) * 8
        mtf_points     = (core_votes.get('multitimeframe', 0) / 100) * 4
        fib_points     = (core_votes.get('fibonacci',      0) / 100) * 5
        whale_points   = (core_votes.get('smart_money',    0) / 100) * 5
        volume_points  = (core_votes.get('volume_forecast',0) / 100) * 2

        core_points = (
            candle_points + chart_points  + rtpa_points
            + mtf_points  + fib_points    + whale_points
            + volume_points
        )

        # ══════════════════════════════════════
        # Support Inputs = 20 Points
        # ══════════════════════════════════════

        # RSI + MACD (5)
        rsi_p = 0
        if   rsi < 30: rsi_p = ((30 - rsi) / 30) * 3
        elif rsi < 40: rsi_p = ((40 - rsi) / 10) * 1
        macd_diff_pct = analysis_data.get('latest', {}).get('macd_diff_pct', 0.0)
        macd_p = 0
        if macd_diff_pct > 0:
            macd_p = min((min(abs(macd_diff_pct), 0.5) / 0.5) * 2, 2.0)
        rsi_macd_p = min(rsi_p + macd_p, 5)

        # Fear & Greed (4)
        fg   = analysis_data.get('sentiment',{}).get('fear_greed', 50)
        sent = ai.get('sentiment_score', 0)
        fg_p = 0
        if   fg < 30: fg_p = ((30 - fg) / 30) * 4
        elif fg < 50: fg_p = ((50 - fg) / 50) * 2
        elif sent > 0: fg_p = (sent / 100) * 1

        # News (3)
        news_p = self._calculate_buy_news_points(
            symbol, analysis_data, ai, max_points=3)

        # Volume Ratio (3)
        vr_p = (3.0 if volume_ratio > 2.0
                else 2.0 if volume_ratio > 1.5
                else 1.0 if volume_ratio > 1.2
                else 0)

        # Market Intel (2)
        intel = analysis_data.get('market_intelligence',{})
        intel_p = (intel.get('bullish_score', 0) / 100) * 2

        # Safety (2)
        liq_p  = ai.get('liquidation_safety', 50) / 100
        risk_p = (100 - ai.get('risk_level', 50)) / 100
        safe_p = liq_p + risk_p

        # External (1)
        ext     = analysis_data.get('external_signal', {})
        ext_s   = analysis_data.get('external_score', 50)
        ext_p   = (1.0 if ext.get('bullish') == 1
                   else 0.5 if ext_s >= 55
                   else 0.2 if ext_s >= 50
                   else 0.0)


        # Prediction Points (1h + 4h forecast)
        _pred = ai.get('macro_prediction', {})
        _1h_bull = ai.get('1h_bullish', False)
        _4h_bull = ai.get('4h_bullish', False)
        _1h_bear = ai.get('1h_bearish', False)
        _4h_bear = ai.get('4h_bearish', False)
        _1h_conf = _pred.get('1h_confidence', 50) / 100.0
        _4h_conf = _pred.get('4h_confidence', 50) / 100.0

        # Buy boost: future looks good = more points
        # Buy penalty: future looks bad = less points

        # Reversal Analysis (bottom detection)
        _rev = analysis_data.get('reversal', {})
        _rev_conf = _rev.get('confidence', 0)
        _rev_signals = _rev.get('reversal_signals', 0)
        rev_p = 0
        if _rev_conf > 0 and _rev_signals > 0:
            rev_p = (_rev_conf / 100.0) * 3  # max 3 points

        pred_p = 0
        if _1h_bull and _4h_bull:
            pred_p = (_1h_conf + _4h_conf) * 2.5  # max ~5
        elif _1h_bull:
            pred_p = _1h_conf * 2.0  # max ~2
        elif _1h_bear and _4h_bear:
            pred_p = -(_1h_conf + _4h_conf) * 2.5  # max ~-5
        elif _1h_bear:
            pred_p = -_1h_conf * 2.0  # max ~-2

        support_total = min(
            rsi_macd_p + fg_p + news_p + vr_p
            + intel_p + safe_p + ext_p + pred_p + rev_p, 28)

        # ══════════════════════════════════════
        # Total Score
        # ══════════════════════════════════════
        buy_points = min(meta_points + core_points + support_total, 100)

        # ══════════════════════════════════════
        # 🌐 Macro Trend Voting = ±20 Points
        # ══════════════════════════════════════
        try:
            _macro_pred  = ai.get('macro_prediction', {})
            _now         = _macro_pred.get('current', '')
            _1h          = _macro_pred.get('1h', 'NEUTRAL')
            _4h          = _macro_pred.get('4h', 'NEUTRAL')

            def _macro_state(s):
                if 'BULL' in str(s): return 'BULL'
                if 'BEAR' in str(s): return 'BEAR'
                return 'NEUT'

            _key         = (_macro_state(_now), _macro_state(_1h), _macro_state(_4h))
            macro_points = MACRO_BUY_POINTS.get(_key, 0)
            buy_points   = buy_points + macro_points
            ai['macro_buy_points'] = macro_points
            ai['macro_key']        = str(_key)
        except Exception as e:
            logger.warning('Macro buy points error: ' + str(e))
            macro_points = 0
            ai['macro_buy_points'] = 0
            ai['macro_key'] = 'ERROR'

        required = MIN_BUY_CONFIDENCE
        max_amt  = MAX_TRADE_AMOUNT
        if buy_mode:
            required = buy_mode.get('min_confidence', MIN_BUY_CONFIDENCE)
            max_amt  = buy_mode.get('max_amount',     MAX_TRADE_AMOUNT)

        # Decision
        if buy_points >= required:
            amount = self._calculate_smart_amount_safe(
                symbol, confidence, analysis_data)
            amount = min(amount, max_amt)
            return {
                'action'               : 'BUY',
                'reason'               : (
                    f'👑 Meta:{confidence:.1f}% | '
                    f'Points:{buy_points:.0f}/{required} | '
                    f'Core:{core_points:.0f}/40'),
                'confidence'           : min(confidence, 99),
                'amount'               : amount,
                'advisors_intelligence': ai,
                'buy_probability'      : buy_prob,
                'coin_forecast'        : coin_fc,
                'market_forecast'      : market_fc,
                'core_votes'           : core_votes
            }

        return {
            'action'               : 'DISPLAY',
            'reason'               : (
                f'👑 Meta:{confidence:.1f}% | '
                f'Points:{buy_points:.0f} '
                f'(need {required}+) | '
                f'Core:{core_points:.0f}/40'),
            'confidence'           : min(confidence, 99),
            'advisors_intelligence': ai,
            'buy_probability'      : buy_prob,
            'coin_forecast'        : coin_fc,
            'market_forecast'      : market_fc,
            'core_votes'           : core_votes
        }

    def _calculate_buy_news_points(self, symbol, analysis_data,
                                    ai, max_points=3):
        news_p = 0
        try:
            if hasattr(self,'news_analyzer') and self.news_analyzer:
                ns = self.news_analyzer.get_news_sentiment(symbol)
                if ns and ns.get('total', 0) >= 2:
                    score = ns.get('news_score', 0)
                    pos   = ns.get('positive',   0)
                    tot   = ns.get('total',       0)
                    ratio = pos / max(tot, 1)
                    news_p = (ratio * max_points if score > 0
                              else 0 if score < -3
                              else ratio * (max_points/2))
            else:
                ei  = analysis_data.get('external_impact', {})
                pos = ei.get('positive_news_count', 0)
                neg = ei.get('negative_news_count', 0)
                if pos > 0 or neg > 0:
                    news_p = (pos / max(pos+neg,1)) * max_points
                else:
                    ss = ai.get('sentiment_score', 0)
                    news_p = max(0,(ss/10)*(max_points/2)) if ss > 0 else 0
        except Exception as e:
            logger.warning(f"News points error: {e}")
        return min(news_p, max_points)

    def _calculate_smart_amount(self, symbol, confidence, analysis):
        try:
            ratio  = ((max(self.AMOUNT_CONF_MIN,
                           min(self.AMOUNT_CONF_MAX, confidence))
                       - self.AMOUNT_CONF_MIN)
                      / (self.AMOUNT_CONF_MAX - self.AMOUNT_CONF_MIN))
            base   = (MIN_TRADE_AMOUNT
                      + (MAX_TRADE_AMOUNT - MIN_TRADE_AMOUNT) * ratio)
            rsi    = analysis.get('rsi',           50)
            vr     = analysis.get('volume_ratio', 1.0)
            md     = analysis.get('latest', {}).get('macd_diff_pct', 0.0)
            fr     = (analysis.get('flash_crash_protection',{})
                      .get('risk_score', 0))
            mult   = 1.0
            if   rsi < self.RSI_OVERSOLD:  mult *= 1.3
            elif rsi < self.RSI_LOW:        mult *= 1.1
            elif rsi > self.RSI_OVERBOUGHT: mult *= 0.7
            if   vr > self.VOLUME_HIGH:    mult *= 1.2
            elif vr > self.VOLUME_MED:     mult *= 1.1
            if md < self.MACD_BEARISH:     mult *= 1.1
            if fr >= self.FLASH_RISK_AMOUNT: mult *= 0.8
            return round(max(MIN_TRADE_AMOUNT,
                             min(MAX_TRADE_AMOUNT, base*mult)), 2)
        except Exception as e:
            logger.warning(f"Smart amount error: {e}")
            return MIN_TRADE_AMOUNT

    def _calculate_smart_amount_safe(self, symbol, confidence, analysis):
        try:
            return self._calculate_smart_amount(symbol, confidence, analysis)
        except Exception:
            return MIN_TRADE_AMOUNT
