"""
🟢 Meta Buy
منطق قرار الشراء + نظام النقاط
"""

import logging
from datetime import datetime, timezone

import pandas as pd

from config import (
    MIN_BUY_CONFIDENCE, MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT,
    get_prediction_modes
)

logger = logging.getLogger(__name__)


class BuyMixin:
    """Mixin يحتوي على كل منطق الشراء"""

    # ─────────────────────────────────────────────
    # قرار الشراء الرئيسي
    # ─────────────────────────────────────────────

    def should_buy(self, symbol: str, analysis: dict,
                   models_scores=None, candles=None,
                   preloaded_advisors=None) -> dict:
        """👑 Buy Decision + Smart Prediction System"""
        analysis_data = analysis
        reasons       = []

        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action': 'DISPLAY', 'reason': 'Invalid analysis data',
                    'confidence': 0}

        if candles is None:
            candles = analysis_data.get('candles', [])

        # ── جمع ذكاء المستشارين ──
        ai = self._gather_buy_advisors_intelligence(
            symbol, analysis_data, reasons)
        ai.update(self._gather_extra_buy_intelligence(
            symbol, analysis_data))

        # ── توقع السوق ──
        buy_mode     = None
        macro_status = '⚪ NEUTRAL'
        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                macro_status        = macro.get_macro_status()
                ai['macro_status']  = macro_status
                prediction          = macro.predict_market()
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

                buy_mode, _ = get_prediction_modes(
                    macro_status, smart_direction)

        except Exception as e:
            print(f"⚠️ Market prediction error: {e}")

        # ── المؤشرات الأساسية ──
        rsi            = analysis_data.get('rsi',            50)
        macd_diff      = analysis_data.get('macd_diff',       0)
        volume_ratio   = analysis_data.get('volume_ratio',  1.0)
        price_momentum = analysis_data.get('price_momentum',  0)
        atr            = analysis_data.get('atr',            2.5)

        # ── بناء الميزات وتشغيل النموذج ──
        symbol_memory = self._get_symbol_memory(symbol)
        features = self._build_meta_features(
            rsi=rsi, macd_diff=macd_diff, volume_ratio=volume_ratio,
            price_momentum=price_momentum, atr=atr,
            analysis_data=analysis_data,
            advisors_intelligence=ai,
            symbol_memory=symbol_memory
        )

        buy_prob, confidence, coin_fc, market_fc = self._run_meta_model(
            features, ai, direction='buy')
        confidence = max(0.0, min(100.0, confidence))

        # ── فلاتر الأمان ──
        flash_risk = (analysis_data.get('flash_crash_protection', {})
                      .get('risk_score', 0))
        if flash_risk >= self.FLASH_RISK_MAX:
            return {'action': 'DISPLAY',
                    'reason': f'🚨 Flash Crash Risk ({flash_risk}%)',
                    'confidence': 0}

        if ai.get('liquidation_safety', 50) < self.LIQ_SAFETY_MIN:
            return {'action': 'DISPLAY',
                    'reason': '🛡️ High Liquidation Risk',
                    'confidence': 0}

        # ════════════════════════════════════════
        # نظام النقاط للشراء (القاع) - 114 نقطة
        # ════════════════════════════════════════

        # 1. Meta AI (10)
        meta_points = (confidence / 100) * 10

        # 2. Real-time Price Action - Bottom (10)
        rtpa_buy_conf = 0.0
        try:
            if self.realtime_pa and candles and len(candles) >= 3:
                rt_result = self.realtime_pa.analyze_bottom_signals(
                    symbol=symbol,
                    candles=candles,
                    current_price=analysis_data.get('close', 0),
                    volume_data=analysis_data.get('volume_list', None),
                    order_book=analysis_data.get('order_book', None)
                )
                if rt_result:
                    rtpa_buy_conf = rt_result.get('confidence', 0)
        except Exception as e:
            print(f"⚠️ Realtime bottom error: {e}")
        rtpa_points = (rtpa_buy_conf / 100) * 10

        # 3. Candle Expert (9)
        candle_score  = ai.get('candle_expert_score', 50)
        candle_points = (candle_score / 100) * 9

        # 4. Chart CNN (9)
        chart_cnn_score = analysis_data.get('chart_cnn_score', 0)
        chart_points    = (chart_cnn_score / 100) * 9

        # 5. Whale Activity - اتجاه الشراء (8)
        whale_score     = ai.get('whale_activity',  0)
        whale_direction = ai.get('whale_direction', 'sell')
        whale_points    = ((whale_score / 100) * 8
                           if whale_direction == 'buy' else 0)

        # 6. Multi-Timeframe Bottom (8)
        mtf_points = 0
        try:
            if self.mtf_analyzer and candles and len(candles) >= 3:
                from meta.meta_utils import extract_volumes
                candles_5m  = analysis_data.get('candles_5m',  candles)
                candles_15m = analysis_data.get('candles_15m', candles)
                candles_1h  = analysis_data.get('candles_1h',  candles)

                result = self.mtf_analyzer.analyze_bottom(
                    candles_5m=candles_5m,
                    candles_15m=candles_15m,
                    candles_1h=candles_1h,
                    current_price=analysis_data.get('close', 0),
                    volume_data_5m=extract_volumes(candles_5m),
                    volume_data_15m=extract_volumes(candles_15m),
                    volume_data_1h=extract_volumes(candles_1h),
                    order_book=analysis_data.get('order_book'),
                    macro_status=ai.get('macro_status', 'NEUTRAL')
                )
                if result:
                    mtf_conf = result.get('confidence', 0)
                    conf     = result.get('confirmations', 0)
                    if mtf_conf > 20:
                        mtf_points = ((mtf_conf / 100) * 8
                                      * (max(conf, 1) / 3))
        except Exception as e:
            print(f"⚠️ MTF bottom error: {e}")

        # 7. Volume Momentum (7)
        volume_momentum = ai.get('volume_momentum', 40)
        vol_pred_score  = analysis_data.get('volume_pred_score', 0)
        volume_points   = (((volume_momentum / 100) * 4)
                           + ((vol_pred_score / 100) * 3))
        volume_points   = min(volume_points, 7)

        # 8. Pattern Confidence (6)
        pattern_conf   = ai.get('pattern_confidence', 0)
        pattern_points = (pattern_conf / 100) * 6

        # 9. Fibonacci Support (6)
        support_strength = ai.get('support_strength', 30)
        support_points   = (support_strength / 100) * 6

        # 10. Trend Birth (5)
        trend_birth  = ai.get('trend_birth', 30)
        trend_points = (trend_birth / 100) * 5

        # 11. Fear & Greed - القاع عند الخوف (5)
        fear_greed      = analysis_data.get('sentiment', {}).get('fear_greed', 50)
        sentiment_score = ai.get('sentiment_score', 0)
        fear_points     = 0
        if fear_greed < 30:      # خوف شديد = فرصة شراء
            fear_points = ((30 - fear_greed) / 30) * 5
        elif fear_greed < 50:
            fear_points = ((50 - fear_greed) / 50) * 2
        elif sentiment_score > 0:
            fear_points = (sentiment_score / 100) * 2

        # 12. News (4)
        news_points = self._calculate_buy_news_points(
            symbol, analysis_data, ai)

        # 13. Liquidation Safety (4)
        liq_safety = ai.get('liquidation_safety', 50)
        liq_points = (liq_safety / 100) * 4

        # 14. Trap Detection (4)
        trap_detection = ai.get('trap_detection', 60)
        anomaly_points = (trap_detection / 100) * 4

        # 15. Liquidity Score (3)
        liquidity_score  = ai.get('liquidity_score', 50)
        liquidity_points = (liquidity_score / 100) * 3

        # 16. RSI Oversold (3)
        rsi_points = 0
        if rsi < 30:
            rsi_points = ((30 - rsi) / 30) * 3
        elif rsi < 40:
            rsi_points = ((40 - rsi) / 10) * 1

        # 17. MACD Bullish (3)
        macd_points = 0
        if macd_diff > 0:
            if abs(macd_diff) >= 1.0:
                macd_points = (min(abs(macd_diff), 100) / 100) * 3
            else:
                macd_points = (min(abs(macd_diff), 0.01) / 0.01) * 3
            macd_points = min(macd_points, 3.0)

        # 18. Market Intelligence Bullish (3)
        market_intel = analysis_data.get('market_intelligence', {})
        intel_score  = market_intel.get('bullish_score', 0)
        intel_points = (intel_score / 100) * 3

        # 19. Risk Level (2)
        risk_level  = ai.get('risk_level', 50)
        risk_points = ((100 - risk_level) / 100) * 2

        # 20. Historical Success (2)
        hist_success    = ai.get('historical_success', 50)
        adaptive_points = (hist_success / 100) * 2

        # 21. Macro Status (2)
        macro_points = 0
        macro_clean  = macro_status.upper()
        if   'BULL'    in macro_clean: macro_points = 2
        elif 'NEUTRAL' in macro_clean: macro_points = 1
        elif 'BEAR'    in macro_clean: macro_points = 0

        # 22. External Signal (1)
        ext_signal  = analysis_data.get('external_signal', {})
        ext_bullish = ext_signal.get('bullish', 0)
        ext_score   = analysis_data.get('external_score', 50)
        if   ext_bullish == 1: ext_points = 1.0
        elif ext_score   >= 55: ext_points = 0.5
        elif ext_score   >= 50: ext_points = 0.2
        else:                   ext_points = 0.0

        # ── حساب النقاط الكلية ──
        raw_points = (
            meta_points    + rtpa_points   + candle_points  + chart_points
            + whale_points + mtf_points    + volume_points  + pattern_points
            + support_points + trend_points + fear_points   + news_points
            + liq_points   + anomaly_points + liquidity_points + rsi_points
            + macd_points  + intel_points  + risk_points    + adaptive_points
            + macro_points + ext_points
        )
        buy_points = min((raw_points / 114) * 100, 100)

        # ── تحديد الحد المطلوب ──
        required_confidence = MIN_BUY_CONFIDENCE
        max_amount          = MAX_TRADE_AMOUNT

        if buy_mode:
            required_confidence = buy_mode.get(
                'min_confidence', MIN_BUY_CONFIDENCE)
            max_amount = buy_mode.get('max_amount', MAX_TRADE_AMOUNT)

        # ── القرار النهائي ──
        if buy_points >= required_confidence:
            amount = self._calculate_smart_amount_safe(
                symbol, confidence, analysis_data)
            amount = min(amount, max_amount)

            return {
                'action'               : 'BUY',
                'reason'               : (
                    f'🤖 Meta AI: {confidence:.1f}% | '
                    f'Points: {buy_points:.0f}/{required_confidence} | '
                    f'RT:{rtpa_buy_conf:.0f}%'),
                'confidence'           : min(confidence, 99),
                'amount'               : amount,
                'advisors_intelligence': ai,
                'buy_probability'      : buy_prob,
                'coin_forecast'        : coin_fc,
                'market_forecast'      : market_fc
            }

        return {
            'action'               : 'DISPLAY',
            'reason'               : (
                f'🤖 Meta AI: {confidence:.1f}% | '
                f'Points: {buy_points:.0f} '
                f'(need {required_confidence}+)'),
            'confidence'           : min(confidence, 99),
            'advisors_intelligence': ai,
            'buy_probability'      : buy_prob,
            'coin_forecast'        : coin_fc,
            'market_forecast'      : market_fc
        }

    # ─────────────────────────────────────────────
    # دوال مساعدة للشراء
    # ─────────────────────────────────────────────

    def _calculate_buy_news_points(self, symbol: str,
                                    analysis_data: dict,
                                    ai: dict) -> float:
        """حساب نقاط الأخبار للشراء (max 4)"""
        news_points = 0
        try:
            if hasattr(self, 'news_analyzer') and self.news_analyzer:
                news_sentiment = self.news_analyzer.get_news_sentiment(symbol)
                if news_sentiment and news_sentiment.get('total', 0) >= 2:
                    news_score    = news_sentiment.get('news_score',  0)
                    news_positive = news_sentiment.get('positive',    0)
                    total_news    = news_sentiment.get('total',        0)
                    news_ratio    = news_positive / max(total_news, 1)
                    if news_score > 0:
                        news_points = news_ratio * 4
                    elif news_score < -3:
                        news_points = 0
                    else:
                        news_points = news_ratio * 2
            else:
                ext_impact    = analysis_data.get('external_impact', {})
                news_positive = ext_impact.get('positive_news_count', 0)
                news_negative = ext_impact.get('negative_news_count', 0)
                if news_positive > 0 or news_negative > 0:
                    total_news  = news_positive + news_negative
                    news_ratio  = news_positive / max(total_news, 1)
                    news_points = news_ratio * 4
                else:
                    sent_score  = ai.get('sentiment_score', 0)
                    news_points = (max(0, (sent_score / 10) * 2)
                                   if sent_score > 0 else 0)
        except Exception as e:
            print(f"⚠️ News points error: {e}")

        return min(news_points, 4)

    def _apply_mtf_bottom_boost(self, symbol: str,
                                  analysis_data: dict,
                                  candles, ai: dict,
                                  confidence: float) -> float:
        """رفع الثقة بناءً على Multi-Timeframe Bottom Detection"""
        if not self.mtf_analyzer or not candles or len(candles) < 5:
            return confidence
        try:
            from meta.meta_utils import extract_volumes
            candles_5m  = analysis_data.get('candles_5m',  candles)
            candles_15m = analysis_data.get('candles_15m', candles)
            candles_1h  = analysis_data.get('candles_1h',  candles)

            result = self.mtf_analyzer.analyze_bottom(
                candles_5m=candles_5m,
                candles_15m=candles_15m,
                candles_1h=candles_1h,
                current_price=analysis_data.get('close', 0),
                volume_data_5m=extract_volumes(candles_5m),
                volume_data_15m=extract_volumes(candles_15m),
                volume_data_1h=extract_volumes(candles_1h),
                order_book=analysis_data.get('order_book'),
                macro_status=ai.get('macro_status', 'NEUTRAL')
            )
            if result and result.get('is_bottom'):
                conf       = result['confirmations']
                confidence += result['confidence'] * 0.15 * (conf / 3)

        except Exception as e:
            print(f"⚠️ Multi-TF bottom error: {e}")
        return confidence

    def _calculate_smart_amount(self, symbol: str,
                                 confidence: float,
                                 analysis: dict) -> float:
        """حساب المبلغ الذكي بناءً على الثقة والمؤشرات"""
        try:
            conf_ratio  = (
                (max(self.AMOUNT_CONF_MIN,
                     min(self.AMOUNT_CONF_MAX, confidence))
                 - self.AMOUNT_CONF_MIN)
                / (self.AMOUNT_CONF_MAX - self.AMOUNT_CONF_MIN)
            )
            base_amount = (MIN_TRADE_AMOUNT
                           + (MAX_TRADE_AMOUNT - MIN_TRADE_AMOUNT)
                           * conf_ratio)

            rsi          = analysis.get('rsi',          50)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            macd_diff    = analysis.get('macd_diff',     0)
            flash_risk   = (analysis.get('flash_crash_protection', {})
                            .get('risk_score', 0))

            mult = 1.0
            if   rsi < self.RSI_OVERSOLD:   mult *= 1.3
            elif rsi < self.RSI_LOW:         mult *= 1.1
            elif rsi > self.RSI_OVERBOUGHT:  mult *= 0.7

            if   volume_ratio > self.VOLUME_HIGH: mult *= 1.2
            elif volume_ratio > self.VOLUME_MED:  mult *= 1.1

            if macd_diff < self.MACD_BEARISH:          mult *= 1.1
            if flash_risk >= self.FLASH_RISK_AMOUNT:   mult *= 0.8

            return round(
                max(MIN_TRADE_AMOUNT,
                    min(MAX_TRADE_AMOUNT, base_amount * mult)), 2)

        except Exception as e:
            print(f"⚠️ Smart amount error: {e}")
            return MIN_TRADE_AMOUNT

    def _calculate_smart_amount_safe(self, symbol: str,
                                      confidence: float,
                                      analysis: dict) -> float:
        """حساب المبلغ الذكي مع معالجة الأخطاء"""
        try:
            return self._calculate_smart_amount(symbol, confidence, analysis)
        except Exception:
            return MIN_TRADE_AMOUNT