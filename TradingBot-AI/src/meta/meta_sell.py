"""
🔴 Meta Sell
منطق قرار البيع + Stop Loss الديناميكي + نظام القفزات
"""

import gc
import logging
from datetime import datetime, timezone
from typing import Optional

from config import (
    MIN_SELL_CONFIDENCE, MIN_SELL_PROFIT,
    get_prediction_modes
)
from meta.meta_utils import adjust_threshold_by_forecasts, extract_volumes

logger = logging.getLogger(__name__)


class SellMixin:
    """Mixin يحتوي على كل منطق البيع"""

    # ─────────────────────────────────────────────
    # قرار البيع الرئيسي
    # ─────────────────────────────────────────────

    def should_sell(self, symbol: str, position: dict,
                    current_price: float, analysis: dict,
                    mtf, candles=None,
                    preloaded_advisors=None) -> dict:
        """🔴 Sell Decision + Smart Prediction System"""

        # 1. Spike Detection (instant sell)
        spike = self._calculate_profit_spike_features(
            symbol, position, current_price)

        if spike.get('is_spike') == 1:
            buy_price  = float(position.get('buy_price', 0) or 0)
            profit     = ((current_price - buy_price) / buy_price * 100
                          if buy_price > 0 else 0)
            spike_type = spike.get('spike_type', 'UNKNOWN')

            if spike_type == 'POSITIVE':
                emoji = '🚀'
                label = 'PROFIT SPIKE'
            else:
                emoji = '🛡️'
                label = 'CRASH PROTECTION'

            return {
                'action'              : 'SELL',
                'reason'              : (f"{emoji} {label}: "
                                         f"{spike.get('profit_jump', 0):.1f}% in "
                                         f"{spike.get('time_diff', 0):.0f}s"),
                'profit'              : profit,
                'sell_votes'          : {},
                'sell_vote_percentage': 100.0,
                'sell_vote_count'     : 16,
                'total_advisors'      : 16
            }

        # ── Setup ──
        ai                   = {}
        risk_level           = analysis.get('risk_level',       50)
        whale_tracking_score = analysis.get('whale_score',       0)
        sentiment_score      = analysis.get('sentiment_score',   0)
        ai['risk_level']           = risk_level
        ai['whale_tracking_score'] = whale_tracking_score
        ai['sentiment_score']      = sentiment_score

        buy_price     = float(position.get('buy_price', 0) or 0)
        current_price = float(analysis.get('close', 0) or 0)
        profit_pct    = (((current_price - buy_price) / buy_price * 100)
                         if buy_price > 0 else 0.0)
        rsi           = analysis.get('rsi',          50)
        macd_diff     = analysis.get('macd_diff',     0)
        volume_ratio  = analysis.get('volume_ratio', 1.0)

        # ── توقع السوق ──
        sell_mode               = None
        macro_status            = '⚪ NEUTRAL'
        dynamic_min_sell_profit = MIN_SELL_PROFIT

        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                macro_status            = macro.get_macro_status()
                ai['macro_status']      = macro_status
                prediction              = macro.predict_market()
                ai['market_prediction'] = prediction

                combined            = prediction.get('combined', {})
                predicted_direction = combined.get('direction', 'NEUTRAL')
                predicted_strength  = combined.get('strength',  'NEUTRAL')

                if (predicted_direction == 'MIXED'
                        and predicted_strength == 'RECOVERY'):
                    smart_direction = 'BULLISH'
                elif (predicted_direction == 'MIXED'
                      and predicted_strength == 'CAUTION'):
                    smart_direction = 'BEARISH'
                else:
                    smart_direction = predicted_direction

                _, sell_mode = get_prediction_modes(
                    macro_status, smart_direction)
                dynamic_min_sell_profit = max(
                    sell_mode.get('min_sell_profit', MIN_SELL_PROFIT),
                    MIN_SELL_PROFIT)

        except Exception as e:
            print(f"⚠️ Sell prediction error: {e}")

        # 2. Stop Loss
        sl_info      = self._calculate_stop_loss_features(
            position, current_price, analysis,
            risk_level, whale_tracking_score, sentiment_score)
        drop         = sl_info.get('drop_from_peak', 0)
        sl_threshold = sl_info.get('threshold',      0)

        if sell_mode:
            sl_threshold *= sell_mode.get('stop_loss_mult', 1.0)

        if drop >= sl_threshold:
            gc.collect()
            return {
                'action'  : 'SELL',
                'reason'  : (f'🛡️ Stop Loss: Drop {drop:.1f}% >= '
                             f'Threshold {sl_threshold:.1f}%'),
                'profit'  : profit_pct,
                'sell_votes': {},
                'stop_loss_threshold': sl_threshold
            }

        # 3. Min Profit Check
        if profit_pct < dynamic_min_sell_profit:
            if profit_pct < -1.0:
                reason = (f'🛡️ Stop Loss Zone: {profit_pct:.2f}% | '
                          f'SL Trigger: -{sl_threshold:.2f}%')
            else:
                reason = (f'Min profit: {profit_pct:.2f}% < '
                          f'{dynamic_min_sell_profit}%')
            return {'action': 'HOLD', 'reason': reason, 'profit': profit_pct}

        # 4. Stop Loss Intelligence
        ai.update(self._gather_stop_loss_intelligence(
            symbol, analysis, volume_ratio, sl_info))

        # 5. Build Features + Meta Model
        symbol_memory = self._get_symbol_memory(symbol)
        features = self._build_meta_features(
            rsi=rsi, macd_diff=macd_diff, volume_ratio=volume_ratio,
            price_momentum=analysis.get('price_momentum', 0),
            atr=analysis.get('atr', 2.5),
            analysis_data=analysis,
            advisors_intelligence=ai,
            symbol_memory=symbol_memory
        )

        sell_prob, meta_sell_confidence, coin_fc_sell, market_fc_sell = \
            self._run_meta_model(features, ai, direction='sell')

        # 6. Real-time Price Action Peak
        rtpa_sell_conf = 0.0
        try:
            if self.realtime_pa and candles and len(candles) >= 3:
                rt_result = self.realtime_pa.detect_peak(
                    symbol=symbol,
                    candles=candles,
                    current_price=current_price,
                    analysis=analysis
                )
                if rt_result:
                    rtpa_sell_conf = rt_result.get('confidence', 0)
        except Exception as e:
            print(f"⚠️ Realtime peak error: {e}")

        # 7. Multi-Timeframe Peak
        mtf_sell_conf = self._apply_mtf_peak_boost(
            symbol, analysis, candles, position,
            ai, meta_sell_confidence)

        # 8. Peak Signals
        peak_conf, peak_reasons = self._detect_peak_signals(
            symbol, analysis, ai, profit_pct)

        # 9. Advisor Voting
        sell_vote_count, total_advisors, sell_votes, candle_confirmed = \
            self._run_sell_advisor_voting(
                symbol, analysis, rsi, macd_diff,
                volume_ratio, profit_pct)

        vote_ratio    = (sell_vote_count / total_advisors
                         if total_advisors > 0 else 0)
        peak_analysis = analysis.get('peak', {})
        peak_score    = peak_analysis.get('confidence', 0) + peak_conf

        # ════════════════════════════════════════
        # نظام النقاط للبيع (القمة) - 111 نقطة
        # ════════════════════════════════════════

        # 1. Meta AI (10)
        meta_points  = (meta_sell_confidence / 100) * 10

        # 2. Real-time Price Action - Peak (10)
        rtpa_points  = (rtpa_sell_conf / 100) * 10

        # 3. Candle Expert (9)
        candle_expert_score = sell_votes.get('candle_expert', 0)
        candle_points = (9 if candle_confirmed
                         else min(candle_expert_score * 5, 9))

        # 4. Chart CNN (9)
        chart_cnn_score = sell_votes.get('chart_cnn', 0)
        chart_points    = min(chart_cnn_score * 9, 9)

        # 5. Exit Strategy (8)
        exit_score  = sell_votes.get('exit', 0)
        exit_points = min(exit_score * 8, 8)

        # 6. Peak Confidence (7)
        peak_points = (peak_conf / 100) * 7

        # 7. Vote Ratio (7)
        vote_points = vote_ratio * 7

        # 8. Whale Dumping (6)
        whale_dump   = analysis.get('whale_dumping', False)
        whale_points = (6 if whale_dump
                        else (whale_tracking_score / 100) * 3)

        # 9. Volume Momentum (6)
        vol_momentum  = ai.get('volume_momentum', 40)
        vol_pred      = sell_votes.get('volume_pred', 0)
        volume_points = min(((vol_momentum / 100) * 3) + (vol_pred * 3), 6)

        # 10. Fibonacci Resistance (5)
        support_strength = ai.get('support_strength', 30)
        fib_points       = ((100 - support_strength) / 100) * 5

        # 11. Trend Exhaustion (4)
        trend_birth  = ai.get('trend_birth', 30)
        trend_points = ((100 - trend_birth) / 100) * 4

        # 12. Negative News (4)
        news_score  = analysis.get('news', {}).get('negative', 0)
        news_points = min((news_score / 10) * 4, 4)

        # 13. Fear & Greed - القمة عند الطمع (4)
        fear_greed  = analysis.get('sentiment', {}).get('fear_greed', 50)
        sent_points = 0
        if fear_greed > 70:      # طمع شديد = فرصة بيع
            sent_points = ((fear_greed - 70) / 30) * 4
        elif sentiment_score < -1:
            sent_points = min(abs(sentiment_score) / 5 * 4, 4)

        # 14. Liquidation Risk (3)
        liq_safety = ai.get('liquidation_safety', 50)
        liq_points = ((100 - liq_safety) / 100) * 3

        # 15. RSI Overbought (3)
        rsi_points = 0
        if rsi > 70:
            rsi_points = ((rsi - 70) / 30) * 3
        elif rsi > 60:
            rsi_points = ((rsi - 60) / 10) * 1

        # 16. MACD Bearish (3)
        macd_points = 0
        if macd_diff < 0:
            macd_points = (min(abs(macd_diff), 10) / 10) * 3

        # 17. Market Intelligence Bearish (3)
        market_intel = analysis.get('market_intelligence', {})
        intel_score  = market_intel.get('bearish_score', 0)
        intel_points = (intel_score / 100) * 3

        # 18. Anomaly Score (2)
        anomaly_score  = analysis.get('anomaly_score', 0)
        anomaly_points = (anomaly_score / 100) * 2

        # 19. Historical Success (2)
        hist_success    = ai.get('historical_success', 50)
        adaptive_points = ((100 - hist_success) / 100) * 2

        # 20. Liquidity Score (2)
        liquidity_score  = ai.get('liquidity_score', 50)
        liquidity_points = ((100 - liquidity_score) / 100) * 2

        # 21. Macro Bear (2)
        macro_points = 0
        if   'BEAR'    in macro_status: macro_points = 2
        elif 'NEUTRAL' in macro_status: macro_points = 1

        # 22. External Signal (1)
        ext_signal = analysis.get('external_signal', {}).get('bearish', 0)
        ext_points = min(ext_signal, 1)

        # ── حساب النقاط الكلية ──
        raw_points = (
            meta_points    + rtpa_points   + candle_points  + chart_points
            + exit_points  + peak_points   + vote_points    + whale_points
            + volume_points + fib_points   + trend_points   + news_points
            + sent_points  + liq_points    + rsi_points     + macd_points
            + intel_points + anomaly_points + adaptive_points
            + liquidity_points + macro_points + ext_points
        )
        sell_points = min((raw_points / 111) * 100, 100)

        # ── حد البيع حسب حالة السوق ──
        if   'BULL'    in macro_status: required_sell_points = 75
        elif 'BEAR'    in macro_status: required_sell_points = 55
        else:                           required_sell_points = 65

        sell_vote_pct = vote_ratio * 100

        # ── القرار النهائي ──
        if sell_points >= required_sell_points:
            gc.collect()
            return {
                'action'              : 'SELL',
                'reason'              : (
                    f'👑 Peak: {sell_points:.0f}/{required_sell_points}pts | '
                    f'Meta:{meta_sell_confidence:.0f}% | '
                    f'RT:{rtpa_sell_conf:.0f}% | '
                    f'Votes:{sell_vote_count}/{total_advisors}'),
                'profit'              : profit_pct,
                'sell_votes'          : sell_votes,
                'peak_score'          : peak_score,
                'sell_vote_percentage': sell_vote_pct,
                'coin_forecast'       : coin_fc_sell,
                'market_forecast'     : market_fc_sell
            }

        # ── Smart Sell ──
        if sell_mode and sell_mode.get('mode') != 'NORMAL':
            smart_sell = self._smart_sell_check(
                symbol, position, profit_pct, sell_mode)
            if smart_sell:
                return smart_sell

        # ── Wave Protection ──
        return self._wave_protection(
            symbol, analysis, candles, position,
            ai, rsi, macd_diff, volume_ratio,
            profit_pct, peak_score,
            sell_votes, sell_vote_count, total_advisors
        )

    # ─────────────────────────────────────────────
    # 🎯 البيع الذكي حسب التوقع
    # ─────────────────────────────────────────────

    def _smart_sell_check(self, symbol: str, position: dict,
                           profit_pct: float,
                           sell_mode: dict) -> Optional[dict]:
        """Smart sell check based on prediction mode"""
        mode              = sell_mode.get('mode',              'NORMAL')
        stability_minutes = sell_mode.get('stability_minutes', 5)
        label             = sell_mode.get('label',             '')

        price_key = f"{symbol}_smart_sell"
        now       = __import__('time').time()

        if not hasattr(self, '_smart_sell_tracker'):
            self._smart_sell_tracker = {}

        tracker = self._smart_sell_tracker.get(price_key, {
            'highest_profit': profit_pct,
            'stable_since':   now,
            'last_profit':    profit_pct,
        })

        # ── SNIPER_PROFIT ──
        if mode == 'SNIPER_PROFIT':
            if profit_pct > tracker['highest_profit']:
                tracker.update({'highest_profit': profit_pct,
                                'stable_since': now,
                                'last_profit':  profit_pct})
                self._smart_sell_tracker[price_key] = tracker
                return None

            elif abs(profit_pct - tracker['last_profit']) < 0.1:
                stable_time = (now - tracker['stable_since']) / 60
                if stable_time >= stability_minutes:
                    self._smart_sell_tracker.pop(price_key, None)
                    return {
                        'action': 'SELL',
                        'reason': (f'🎯 Sniper: Stable {stable_time:.0f}m | '
                                   f'Profit {profit_pct:.2f}% | {label}'),
                        'profit': profit_pct, 'sell_votes': {}
                    }
                tracker['last_profit'] = profit_pct
                self._smart_sell_tracker[price_key] = tracker
                return None

            else:
                if profit_pct < 0:
                    tracker['last_profit'] = profit_pct
                    self._smart_sell_tracker[price_key] = tracker
                    return None
                self._smart_sell_tracker.pop(price_key, None)
                return {
                    'action': 'SELL',
                    'reason': (f'🎯 Sniper: Drop After Peak | '
                               f'Profit {profit_pct:.2f}% | {label}'),
                    'profit': profit_pct, 'sell_votes': {}
                }

        # ── SNIPER_EXIT ──
        elif mode == 'SNIPER_EXIT':
            if profit_pct > tracker.get('highest_profit', profit_pct):
                self._smart_sell_tracker.pop(price_key, None)
                return {
                    'action': 'SELL',
                    'reason': (f'🛡️ Rescue: Temp Bounce | '
                               f'Profit {profit_pct:.2f}% | {label}'),
                    'profit': profit_pct, 'sell_votes': {}
                }
            elif abs(profit_pct - tracker.get('last_profit', profit_pct)) < 0.1:
                stable_time = (now - tracker.get('stable_since', now)) / 60
                if stable_time >= stability_minutes:
                    self._smart_sell_tracker.pop(price_key, None)
                    return {
                        'action': 'SELL',
                        'reason': (f'🛡️ Rescue: Stable {stable_time:.0f}m | '
                                   f'Loss {profit_pct:.2f}% | {label}'),
                        'profit': profit_pct, 'sell_votes': {}
                    }
                tracker['last_profit'] = profit_pct
                self._smart_sell_tracker[price_key] = tracker
                return None
            else:
                self._smart_sell_tracker.pop(price_key, None)
                return {
                    'action': 'SELL',
                    'reason': (f'🛡️ Rescue: Continued Drop | '
                               f'Loss {profit_pct:.2f}% | {label}'),
                    'profit': profit_pct, 'sell_votes': {}
                }

        # ── WAIT_RECOVERY ──
        elif mode == 'WAIT_RECOVERY':
            if profit_pct >= 0.3:
                self._smart_sell_tracker.pop(price_key, None)
                return {
                    'action': 'SELL',
                    'reason': (f'⏳ Recovery: Target Reached | '
                               f'{profit_pct:.2f}% | {label}'),
                    'profit': profit_pct, 'sell_votes': {}
                }
            tracker['last_profit'] = profit_pct
            self._smart_sell_tracker[price_key] = tracker
            return None

        # ── CAUTIOUS ──
        elif mode == 'CAUTIOUS':
            if profit_pct > tracker.get('highest_profit', profit_pct):
                tracker.update({'highest_profit': profit_pct,
                                'stable_since': now,
                                'last_profit':  profit_pct})
                self._smart_sell_tracker[price_key] = tracker
                return None

            elif abs(profit_pct - tracker.get('last_profit', profit_pct)) < 0.1:
                stable_time = (now - tracker.get('stable_since', now)) / 60
                if stable_time >= stability_minutes:
                    self._smart_sell_tracker.pop(price_key, None)
                    return {
                        'action': 'SELL',
                        'reason': (f'⚪ Cautious: Stable {stable_time:.0f}m | '
                                   f'Profit {profit_pct:.2f}% | {label}'),
                        'profit': profit_pct, 'sell_votes': {}
                    }
                tracker['last_profit'] = profit_pct
                self._smart_sell_tracker[price_key] = tracker
                return None

            else:
                if profit_pct < 0:   # ✅ لا تبيع بخسارة في وضع Cautious
                    tracker['last_profit'] = profit_pct
                    self._smart_sell_tracker[price_key] = tracker
                    return None
                self._smart_sell_tracker.pop(price_key, None)
                return {
                    'action': 'SELL',
                    'reason': (f'⚪ Cautious: Price Drop | '
                               f'Profit {profit_pct:.2f}% | {label}'),
                    'profit': profit_pct, 'sell_votes': {}
                }

        return None

    # ─────────────────────────────────────────────
    # Wave Protection + Dynamic Stop Loss
    # ─────────────────────────────────────────────

    def _wave_protection(self, symbol: str, analysis: dict,
                          candles, position: dict, ai: dict,
                          rsi: float, macd_diff: float,
                          volume_ratio: float, profit_pct: float,
                          peak_score: int, sell_votes: dict,
                          sell_vote_count: int,
                          total_advisors: int) -> dict:
        """Wave Protection + Dynamic Stop Loss"""
        highest_price = position.get(
            'highest_price',
            float(position.get('buy_price', 0) or 0))
        current       = float(analysis.get('close', 0))
        drop          = ((highest_price - current) / highest_price * 100
                         if highest_price > 0 else 0)

        # ── Stop Loss ديناميكي ──
        atr       = analysis.get('atr', 0) or 0
        threshold = max(ai.get('risk_level', 50) / 25,
                        atr * self.STOP_ATR_MULT)
        threshold += (ai.get('risk_level', 50) - 50) / 100 * 3
        threshold -= (ai.get('whale_tracking_score', 0) / 200) * 2
        threshold += (max(-10, min(10, ai.get('sentiment_score', 0)))
                      / 100) * 2
        threshold  = max(self.STOP_TRAILING_MIN,
                         min(self.STOP_TRAILING_MAX, threshold))

        # ── توقعات Meta ──
        stop_coin_fc, stop_market_fc = self._calc_stop_forecasts(
            ai, rsi, macd_diff, volume_ratio)
        threshold = adjust_threshold_by_forecasts(
            threshold, stop_coin_fc, stop_market_fc, drop)

        # ── Real-time Stop Loss ──
        if self.realtime_pa and candles and len(candles) >= 3:
            threshold = self._apply_realtime_stop(
                symbol, analysis, candles,
                current_price=current,
                highest_price=highest_price,
                threshold=threshold)

        if drop >= threshold:
            gc.collect()
            return {
                'action'             : 'SELL',
                'reason'             : (f'🛡️ Stop Loss: Drop {drop:.1f}% >= '
                                        f'Threshold {threshold:.1f}%'),
                'profit'             : profit_pct,
                'optimism_penalty'   : 0,
                'sell_votes'         : sell_votes,
                'peak_score'         : peak_score,
                'stop_loss_threshold': threshold,
                'coin_forecast'      : stop_coin_fc,
                'market_forecast'    : stop_market_fc
            }

        # ── HOLD ──
        gc.collect()
        return {
            'action'             : 'HOLD',
            'reason'             : (f'Wave Riding | Profit: {profit_pct:+.1f}% | '
                                    f'Peak: {peak_score} | '
                                    f'Votes: {sell_vote_count}/{total_advisors}'),
            'profit'             : profit_pct,
            'sell_votes'         : sell_votes,
            'peak_score'         : peak_score,
            'stop_loss_threshold': threshold
        }

    def _apply_mtf_peak_boost(self, symbol: str, analysis: dict,
                               candles, position: dict,
                               ai: dict,
                               sell_conf: float) -> float:
        """رفع ثقة البيع بناءً على Multi-Timeframe Peak Detection"""
        if not self.mtf_analyzer or not candles or len(candles) < 5:
            return sell_conf
        try:
            candles_5m  = analysis.get('candles_5m',  candles)
            candles_15m = analysis.get('candles_15m', candles)
            candles_1h  = analysis.get('candles_1h',  candles)

            result = self.mtf_analyzer.analyze_peak(
                candles_5m=candles_5m,
                candles_15m=candles_15m,
                candles_1h=candles_1h,
                current_price=float(analysis.get('close', 0)),
                highest_price=position.get(
                    'highest_price',
                    float(position.get('buy_price', 0) or 0)),
                volume_data_5m=extract_volumes(candles_5m),
                volume_data_15m=extract_volumes(candles_15m),
                volume_data_1h=extract_volumes(candles_1h),
                order_book=analysis.get('order_book'),
                macro_status=ai.get('macro_status', 'NEUTRAL')
            )
            if result and result.get('is_peak'):
                conf       = result['confirmations']
                sell_conf += result['confidence'] * 0.2 * (conf / 3)

        except Exception as e:
            print(f"⚠️ Multi-TF peak error: {e}")
        return sell_conf

    def _apply_realtime_stop(self, symbol: str, analysis: dict,
                              candles, current_price: float,
                              highest_price: float,
                              threshold: float) -> float:
        """تطبيق Real-time Stop Loss Trigger"""
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
            print(f"⚠️ Real-time stop loss error: {e}")
        return threshold

    def _calc_stop_forecasts(self, ai: dict, rsi: float,
                              macd_diff: float,
                              volume_ratio: float) -> tuple[dict, dict]:
        """حساب توقعات Stop Loss"""
        coin_fc   = {'direction': 'neutral', 'confidence': 50}
        market_fc = {'direction': 'neutral', 'confidence': 50}
        try:
            if rsi < self.RSI_OVERSOLD and volume_ratio > 2.0:
                coin_fc = {'direction': 'bullish', 'confidence': 70}
            elif rsi > self.RSI_OVERBOUGHT or macd_diff < -2:
                coin_fc = {'direction': 'bearish', 'confidence': 75}

            macro_bear = ai.get('macro_bear_signal', 0)
            macro_sell = ai.get('macro_trend_sell',  50)
            if   macro_bear == 1:    market_fc = {'direction': 'bearish', 'confidence': 80}
            elif macro_sell < 30:    market_fc = {'direction': 'bearish', 'confidence': 70}
            elif macro_sell > 70:    market_fc = {'direction': 'bullish', 'confidence': 70}

        except Exception as e:
            print(f"⚠️ Stop forecast error: {e}")
        return coin_fc, market_fc

    # ─────────────────────────────────────────────
    # Profit Spike + Stop Loss Features
    # ─────────────────────────────────────────────

    def _calculate_profit_spike_features(self, symbol: str,
                                          position: dict,
                                          current_price: float) -> dict:
        """حساب معلومات القفزات - محفوظ كما هو"""
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'profit_jump': 0, 'time_diff': 0,
                        'is_spike': 0, 'spike_type': 'NONE'}

            current_profit = (current_price - buy_price) / buy_price * 100
            now            = datetime.now(timezone.utc)

            self.profit_history.setdefault(symbol, [])
            history = self.profit_history[symbol]

            profit_jump = time_diff = is_spike = 0
            spike_type  = 'NONE'

            if history:
                last_time, last_profit = history[-1]
                last_profit = last_profit or 0
                time_diff   = (now - last_time).total_seconds()

                if time_diff < self.SPIKE_TIME_WINDOW:
                    profit_jump = current_profit - last_profit

                    if profit_jump >= self.SPIKE_POSITIVE_THRESHOLD:
                        is_spike   = 1
                        spike_type = 'POSITIVE'
                    elif profit_jump <= self.SPIKE_NEGATIVE_THRESHOLD:
                        is_spike   = 1
                        spike_type = 'NEGATIVE'

            history.append((now, current_profit))
            if len(history) > self.MAX_PROFIT_HISTORY:
                self.profit_history[symbol] = \
                    history[-self.MAX_PROFIT_HISTORY:]

            return {
                'profit_jump':    profit_jump,
                'time_diff':      time_diff,
                'is_spike':       is_spike,
                'spike_type':     spike_type,
                'current_profit': current_profit
            }
        except Exception as e:
            print(f"⚠️ Profit spike error: {e}")
            return {'profit_jump': 0, 'time_diff': 0,
                    'is_spike': 0, 'spike_type': 'NONE'}

    def _calculate_stop_loss_features(self, position: dict,
                                       current_price: float,
                                       analysis: dict,
                                       risk_level: float,
                                       whale_tracking_score: float,
                                       sentiment_score: float) -> dict:
        """حساب معلومات Stop Loss الديناميكي - محفوظ كما هو"""
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'drop_from_peak': 0, 'threshold': 0,
                        'is_stop_loss': 0}

            highest_price = position.get('highest_price', buy_price)
            drop          = ((highest_price - current_price) / highest_price * 100
                             if highest_price > 0 else 0)

            atr_p        = analysis.get('atr_percent',   2.5)
            volume_ratio = analysis.get('volume_ratio',  1.0)
            rsi          = analysis.get('rsi',            50)

            threshold  = atr_p * (1 + risk_level / 100)
            threshold += (volume_ratio - 1.0) * 0.5
            threshold += (50 - rsi) / 100
            threshold -= whale_tracking_score / 500
            threshold += sentiment_score / 200
            threshold  = max(atr_p * 0.5, min(atr_p * 3.0, threshold))

            profit_pct = (current_price - buy_price) / buy_price * 100
            is_sl      = (1 if drop >= threshold
                          or profit_pct <= -(threshold * 1.5) else 0)

            return {
                'drop_from_peak': drop,
                'threshold':      threshold,
                'is_stop_loss':   is_sl,
                'profit_percent': profit_pct
            }
        except Exception as e:
            print(f"⚠️ Stop loss features error: {e}")
            return {'drop_from_peak': 0, 'threshold': 0, 'is_stop_loss': 0}