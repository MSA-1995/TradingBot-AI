"""
🤝 Meta Advisors
جمع ذكاء المستشارين للشراء والبيع
"""

import logging
import pandas as pd
from datetime import datetime

from meta.meta_utils import _EnhancedPatternRecognitionFallback

logger = logging.getLogger(__name__)


class AdvisorsMixin:
    """Mixin يحتوي على كل منطق المستشارين"""

    # ─────────────────────────────────────────────
    # مستشارو الشراء
    # ─────────────────────────────────────────────

    def _gather_buy_advisors_intelligence(self, symbol: str,
                                           analysis_data: dict,
                                           reasons: list) -> dict:
        """جمع ذكاء المستشارين للشراء"""
        ai = {}

        # 1. Smart Money Tracker
        try:
            smart_money = (self.advisor_manager.get('SmartMoneyTracker')
                           if self.advisor_manager else None)
            if smart_money:
                whale_score           = analysis_data.get('whale_confidence', 0)
                ai['whale_activity']  = abs(whale_score) * 4
                ai['whale_direction'] = 'buy' if whale_score > 0 else 'sell'
                ai['order_flow_imbalance'] = self._calc_order_flow_imbalance(
                    analysis_data, ai, reasons)
        except Exception as e:
            logger.warning(f"SmartMoneyTracker error: {e}")

        # 2. Trend Early Detector
        try:
            trend_detector = (self.advisor_manager.get('TrendEarlyDetector')
                              if self.advisor_manager else None)
            if trend_detector:
                candles_data = analysis_data.get('candles', [])
                if len(candles_data) >= 30:
                    df         = pd.DataFrame(candles_data)
                    order_book = analysis_data.get('order_book')
                    trend_data = trend_detector.detect_trend_birth(df, order_book)

                    if trend_data['trend'] == 'BULLISH':
                        if trend_data['stage'] == 'BIRTH':
                            ai['trend_birth'] = 95
                            reasons.append(f"🎯 Trend Birth: {trend_data['strength']}")
                        elif trend_data['stage'] == 'GROWTH':
                            ai['trend_birth'] = 75
                        else:
                            ai['trend_birth'] = 30
                    else:
                        ai['trend_birth'] = 30
        except Exception as e:
            logger.warning(f"TrendEarlyDetector error: {e}")

        # 3. Volume Forecast Engine
        try:
            volume_engine = (self.advisor_manager.get('VolumeForecastEngine')
                             if self.advisor_manager else None)
            if volume_engine:
                candles_data = analysis_data.get('candles', [])
                if len(candles_data) >= 20:
                    volumes      = [c.get('volume', 0) for c in candles_data[-20:]]
                    current_hour = datetime.now().hour
                    prediction   = volume_engine.predict_next_volume(
                        symbol, volumes, current_hour)
                    breakout = volume_engine.detect_volume_breakout(
                        symbol, volumes, prediction)

                    if breakout['breakout_imminent']:
                        ai['volume_momentum'] = breakout['probability']
                        reasons.append(
                            f"💥 Volume Breakout: {breakout['probability']}%")
                    else:
                        ai['volume_momentum'] = 40
        except Exception as e:
            logger.warning(f"VolumeForecastEngine error: {e}")

        # 4. Liquidation Shield
        try:
            liq_shield = (self.advisor_manager.get('LiquidationShield')
                          if self.advisor_manager else None)
            if liq_shield:
                current_price = analysis_data.get('close', 0)
                order_book    = analysis_data.get('order_book')
                if order_book:
                    liq = liq_shield.analyze_liquidation_risk(
                        symbol, current_price, order_book)
                    ai['liquidation_safety'] = 100 - liq.get('risk_score', 50)
        except Exception as e:
            logger.warning(f"LiquidationShield error: {e}")

        # 5. Pattern Recognition
        try:
            ai.update(self._gather_pattern_intelligence(
                symbol, analysis_data, reasons))
        except Exception as e:
            logger.warning(f"Pattern recognition error: {e}")
            ai.setdefault('pattern_confidence',  0)
            ai.setdefault('candle_expert_score', 50)

        # 6. Fibonacci Analyzer
        try:
            fib = (self.advisor_manager.get('FibonacciAnalyzer')
                   if self.advisor_manager else None)
            if fib:
                rsi          = analysis_data.get('rsi', 50)
                volume_ratio = analysis_data.get('volume_ratio', 1.0)
                if rsi <= self.RSI_OVERBOUGHT:
                    is_at_support, boost = fib.is_at_support(
                        current_price=analysis_data.get('close', 0),
                        analysis=analysis_data,
                        volume_ratio=volume_ratio,
                        symbol=symbol
                    )
                    ai['support_strength'] = boost * 2 if is_at_support else 30
        except Exception as e:
            logger.warning(f"FibonacciAnalyzer error: {e}")

        # 7. Sentiment
        try:
            ai['sentiment_score'] = analysis_data.get('sentiment_score', 0)
        except Exception as e:
            logger.warning(f"Sentiment error: {e}")

        # 8. News Analyzer
        try:
            ai.update(self._gather_news_intelligence(
                symbol, analysis_data, reasons))
        except Exception as e:
            logger.warning(f"NewsAnalyzer error: {e}")

        # 9. Anomaly Detector
        try:
            anomaly_score      = analysis_data.get('anomaly_score', 0)
            ai['anomaly_risk'] = 10 if anomaly_score > 70 else 80
        except Exception as e:
            logger.warning(f"AnomalyDetector error: {e}")

        # 10. Liquidity
        try:
            ai['liquidity_score'] = analysis_data.get('liquidity_score', 50)
        except Exception as e:
            logger.warning(f"LiquidityAnalyzer error: {e}")

        # 11. Whale Tracking
        try:
            if 'whale_tracking_score' not in ai:
                ai['whale_tracking_score'] = (
                    analysis_data.get('whale_activity', 0) * 5)
        except Exception as e:
            logger.warning(f"Whale tracking error: {e}")

        return ai

    def _calc_order_flow_imbalance(self, analysis_data: dict,
                                    ai: dict,
                                    reasons: list) -> float:
        """حساب Order Flow Imbalance من Order Book"""
        try:
            order_book = analysis_data.get('order_book')
            if not order_book:
                return 0.0

            bids = order_book.get('bids', [])[:20]
            asks = order_book.get('asks', [])[:20]
            if not bids or not asks:
                return 0.0

            avg_bid = sum(b[1] for b in bids) / 20
            avg_ask = sum(a[1] for a in asks) / 20

            large_bids = [b for b in bids if b[1] > avg_bid * 3]
            large_asks = [a for a in asks if a[1] > avg_ask * 3]

            lb_vol = sum(b[1] for b in large_bids)
            la_vol = sum(a[1] for a in large_asks)
            total  = lb_vol + la_vol

            if total == 0:
                return 0.0

            imbalance = (lb_vol - la_vol) / total
            if imbalance > 0.4:
                ai['whale_activity'] = min(
                    100, ai.get('whale_activity', 0) + 20)
                reasons.append(
                    f"🐋 Whale Buying: Flow Imbalance {imbalance:.2f}")
            return imbalance

        except Exception as e:
            logger.warning(f"Order Flow Imbalance error: {e}")
            return 0.0

    def _gather_pattern_intelligence(self, symbol: str,
                                      analysis_data: dict,
                                      reasons: list) -> dict:
        """جمع ذكاء الأنماط - عكسي للقاع والقمة"""
        result = {}

        base_pattern = analysis_data.get('reversal', {}).get('confidence', 0)
        candle_score = self._get_candle_expert_score(analysis_data)

        peak_valley_score = 50
        try:
            pattern_rec = (self.advisor_manager.get('EnhancedPatternRecognition')
                           if self.advisor_manager else None)

            if (pattern_rec is None
                    or not hasattr(pattern_rec, 'analyze_peak_hunter_pattern')):
                pattern_rec = _EnhancedPatternRecognitionFallback()

            candles = analysis_data.get('candles', [])
            if len(candles) >= 10:
                pr = pattern_rec.analyze_peak_hunter_pattern(candles)

                # ✅ عكسي: buy signal = قاع، sell signal = قمة
                if pr['signal'] == 'buy':
                    peak_valley_score = 85   # قاع → إشارة شراء
                    reasons.append(f"🎯 Peak Hunter (Bottom): {pr['reason']}")
                elif pr['signal'] == 'sell':
                    peak_valley_score = 15   # قمة → ضعف إشارة الشراء
                    reasons.append(f"🎯 Peak Hunter (Top): {pr['reason']}")
                else:
                    peak_valley_score = 50

        except Exception as e:
            print(f"⚠️ Peak hunter error: {e}")
            peak_valley_score = 50

        combined = min(100, base_pattern * 0.2
                       + candle_score   * 0.3
                       + peak_valley_score * 0.5)

        result['pattern_confidence']  = combined
        result['candle_expert_score'] = candle_score
        result['peak_valley_score']   = peak_valley_score
        return result

    def _get_candle_expert_score(self, analysis_data: dict) -> int:
        """جلب نقاط candle_expert من DL Client"""
        try:
            dl_client = (self.advisor_manager.get('dl_client')
                         if self.advisor_manager else None)
            if not dl_client:
                return self.CANDLE_SCORE_NEUTRAL

            advice = dl_client.get_advice(
                rsi=analysis_data.get('rsi', 50),
                macd=analysis_data.get('macd_diff', 0),
                volume_ratio=analysis_data.get('volume_ratio', 1.0),
                price_momentum=analysis_data.get('price_momentum', 0),
                confidence=50,
                analysis_data=analysis_data,
                action='BUY'
            )
            text = str(advice.get('candle_expert', ''))

            if 'Strong-Bullish' in text: return self.CANDLE_SCORE_STRONG
            if 'Bullish'        in text: return self.CANDLE_SCORE_BULL
            if 'Strong-Bearish' in text: return self.CANDLE_SCORE_STRONG_BEAR
            if 'Bearish'        in text: return self.CANDLE_SCORE_BEAR
            return self.CANDLE_SCORE_NEUTRAL

        except Exception as e:
            print(f"⚠️ candle_expert score error: {e}")
            return self.CANDLE_SCORE_NEUTRAL

    def _gather_news_intelligence(self, symbol: str,
                                   analysis_data: dict,
                                   reasons: list) -> dict:
        """جمع ذكاء الأخبار"""
        result = {'news_impact': 0, 'historical_success': 50}
        try:
            news_analyzer = (self.advisor_manager.get('NewsAnalyzer')
                             if self.advisor_manager else None)
            if not news_analyzer:
                return result

            result['news_impact'] = news_analyzer.get_news_confidence_boost(symbol)

            summary = news_analyzer.get_news_summary(symbol)
            if summary and 'sentiment_history' in summary:
                history = summary['sentiment_history'][-5:]
                if len(history) >= 3:
                    recent = sum(h.get('score', 0) for h in history[-2:]) / 2
                    older  = sum(h.get('score', 0) for h in history[-5:-2]) / 3
                    change = recent - older
                    if change > 2:
                        result['news_impact'] += 10
                        reasons.append(f"📰 News Sentiment Improved: +{change:.1f}")
                    elif change < -2:
                        result['news_impact'] -= 10
                        reasons.append(f"📰 News Sentiment Worsened: {change:.1f}")

        except Exception as e:
            logger.warning(f"NewsAnalyzer error: {e}")
        return result

    def _gather_extra_buy_intelligence(self, symbol: str,
                                        analysis_data: dict) -> dict:
        """مستشارون إضافيون للشراء"""
        ai = {}

        # Adaptive Intelligence
        try:
            adaptive = (self.advisor_manager.get('AdaptiveIntelligence')
                        if self.advisor_manager else None)
            if adaptive:
                profile = adaptive.get_symbol_profile(symbol)
                if profile:
                    ai['historical_success'] = profile.get('success_rate', 50)
        except Exception as e:
            logger.warning(f"AdaptiveIntelligence error: {e}")

        # Liquidity
        try:
            liquidity = analysis_data.get('liquidity_metrics', {})
            ai['liquidity_score'] = liquidity.get('liquidity_score', 50)
        except Exception as e:
            logger.warning(f"Liquidity error: {e}")

        # Anomaly → Trap Detection
        try:
            anomaly = analysis_data.get('anomaly_score', 0)
            ai['trap_detection'] = 100 - min(anomaly * 10, 100)
        except Exception as e:
            logger.warning(f"Anomaly error: {e}")

        # Risk Level
        try:
            risk = analysis_data.get('volatility_risk_score', 2.0)
            ai['risk_level'] = max(0, 100 - risk * 10)
        except Exception as e:
            logger.warning(f"Risk error: {e}")

        # Macro Trend Advisor
        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                status = macro.get_macro_status()
                if status in ("STRONG_BULL_MARKET", "BULL_MARKET"):
                    ai['macro_trend'] = 85
                elif status == "BEAR_MARKET":
                    ai['macro_trend'] = 20
                else:
                    ai['macro_trend'] = 50
                ai['macro_status'] = status
        except Exception as e:
            logger.warning(f"MacroTrendAdvisor error: {e}")

        ai.setdefault('entry_timing', 60)
        return ai

    # ─────────────────────────────────────────────
    # مستشارو البيع
    # ─────────────────────────────────────────────

    def _gather_stop_loss_intelligence(self, symbol: str,
                                        analysis: dict,
                                        volume_ratio: float,
                                        sl_info: dict) -> dict:
        """جمع ذكاء مستشاري Stop Loss"""
        ai = {
            'drop_from_peak': sl_info.get('drop_from_peak', 0),
            'stop_threshold': sl_info.get('threshold',      0),
            'is_stop_loss':   sl_info.get('is_stop_loss',   0),
        }

        # Fibonacci
        try:
            fib = (self.advisor_manager.get('FibonacciAnalyzer')
                   if self.advisor_manager else None)
            if fib:
                is_res, boost = fib.is_at_resistance(
                    current_price=analysis.get('close', 0),
                    analysis=analysis, tolerance=1.0,
                    volume_ratio=volume_ratio, symbol=symbol)
                ai['fib_resistance_stop'] = boost if is_res else 0
        except Exception as e:
            logger.warning(f"Fibonacci stop error: {e}")
            ai['fib_resistance_stop'] = 0

        # Volume Forecast
        try:
            ve = (self.advisor_manager.get('VolumeForecastEngine')
                  if self.advisor_manager else None)
            if ve:
                candles = analysis.get('candles', [])
                if len(candles) >= 20:
                    vols = [c.get('volume', 0) for c in candles[-20:]]
                    pred = ve.predict_next_volume(
                        symbol, vols, datetime.now().hour)
                    if pred['trend'] == 'DECREASING' and pred['momentum'] < -20:
                        ai['volume_collapse_stop'] = 1
                    elif pred['trend'] == 'DECREASING':
                        ai['volume_collapse_stop'] = 0.5
                    else:
                        ai['volume_collapse_stop'] = 0
        except Exception as e:
            logger.warning(f"Volume collapse stop error: {e}")
            ai['volume_collapse_stop'] = 0

        # Adaptive Intelligence
        try:
            adp = (self.advisor_manager.get('AdaptiveIntelligence')
                   if self.advisor_manager else None)
            if adp:
                profile    = adp.get_symbol_profile(symbol)
                avg_profit = ((profile.get('avg_profit', 0) or 0)
                              if profile else 0)
                if avg_profit > 5:
                    ai['adaptive_stop_multiplier'] = 1.3
                elif avg_profit < 2:
                    ai['adaptive_stop_multiplier'] = 0.7
                else:
                    ai['adaptive_stop_multiplier'] = 1.0
        except Exception as e:
            logger.warning(f"Adaptive stop error: {e}")
            ai['adaptive_stop_multiplier'] = 1.0

        # Macro Trend
        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                status = macro.get_macro_status()
                if 'BEAR' in status:
                    ai['macro_bear_signal'] = 1
                    ai['macro_trend_sell']  = 85
                elif 'BULL' in status:
                    ai['macro_bear_signal'] = 0
                    ai['macro_trend_sell']  = 20
                else:
                    ai['macro_bear_signal'] = 0
                    ai['macro_trend_sell']  = 50
        except Exception as e:
            logger.warning(f"Macro trend sell error: {e}")
            ai.setdefault('macro_bear_signal', 0)
            ai.setdefault('macro_trend_sell',  50)

        return ai

    def _detect_peak_signals(self, symbol: str, analysis: dict,
                              ai: dict,
                              profit_pct: float) -> tuple[int, list]:
        """كشف إشارات القمة - عكسي للبيع"""
        peak_conf    = 0
        peak_reasons = []

        # Sentiment + Momentum
        sent     = analysis.get('sentiment_score', 0)
        momentum = analysis.get('price_momentum', 0)

        if sent < -5:
            peak_conf += 20
            peak_reasons.append("Sentiment Very Bearish (+20)")
        elif sent < -3:
            peak_conf += 10
            peak_reasons.append("Sentiment Bearish (+10)")

        if momentum < -1.0:
            peak_conf += 20
            peak_reasons.append("Strong Negative Momentum (+20)")
        elif momentum < -0.5:
            peak_conf += 12
            peak_reasons.append("Negative Momentum (+12)")

        # Trend Exhaustion
        try:
            td = (self.advisor_manager.get('TrendEarlyDetector')
                  if self.advisor_manager else None)
            if td:
                candles = analysis.get('candles', [])
                if len(candles) >= 30:
                    exh = td.get_trend_exhaustion_score(
                        pd.DataFrame(candles), 'BULLISH')
                    if exh >= 75:
                        peak_conf += 30
                        peak_reasons.append(f"Trend Exhaustion: {exh}% (+30)")
                        print(f"🎯 Trend Exhaustion: {exh}%")
                    elif exh >= 50:
                        peak_conf += 15
                        peak_reasons.append(f"Trend Weakening: {exh}% (+15)")
        except Exception as e:
            print(f"⚠️ Trend exhaustion error: {e}")

        # Volume Collapse + Delta
        try:
            ve = (self.advisor_manager.get('VolumeForecastEngine')
                  if self.advisor_manager else None)
            if ve:
                candles = analysis.get('candles', [])
                if len(candles) >= 20:
                    vols = [c.get('volume', 0) for c in candles[-20:]]
                    pred = ve.predict_next_volume(
                        symbol, vols, datetime.now().hour)
                    if pred['trend'] == 'DECREASING' and pred['momentum'] < -20:
                        peak_conf += 20
                        peak_reasons.append(
                            f"Volume Collapse: {pred['momentum']:.1f}% (+20)")
                    elif pred['trend'] == 'DECREASING':
                        peak_conf += 10
                        peak_reasons.append("Volume Declining (+10)")

                    # Delta Volume من Order Book
                    ob = analysis.get('order_book')
                    if ob and ob.get('bids') and ob.get('asks'):
                        bv    = sum(b[1] for b in ob['bids'][:20])
                        av    = sum(a[1] for a in ob['asks'][:20])
                        delta = (bv - av) / (bv + av) if (bv + av) > 0 else 0
                        if delta < -0.3:
                            peak_conf += 25
                            peak_reasons.append(
                                f"Delta Volume: Strong Sell ({delta:.2f}) (+25)")
                        elif delta < -0.15:
                            peak_conf += 15
                            peak_reasons.append(
                                f"Delta Volume: Sell Pressure ({delta:.2f}) (+15)")
        except Exception as e:
            print(f"⚠️ Volume forecast peak error: {e}")

        # Adaptive + Profit Velocity
        try:
            adp = (self.advisor_manager.get('AdaptiveIntelligence')
                   if self.advisor_manager else None)
            if adp:
                profile = adp.get_symbol_profile(symbol)
                if (profile
                        and (profile.get('avg_profit') or 0) < 2.0
                        and profit_pct > 5.0):
                    peak_conf += 15
                    peak_reasons.append("Adaptive: Quick Exit (+15)")
        except Exception as e:
            print(f"⚠️ Adaptive peak error: {e}")

        return peak_conf, peak_reasons

    def _run_sell_advisor_voting(self, symbol: str, analysis: dict,
                                  rsi: float, macd_diff: float,
                                  volume_ratio: float,
                                  profit_pct: float) -> tuple[int, int, dict, bool]:
        """تصويت مستشاري البيع - 16 مستشار"""
        sell_vote_count  = 0
        total_advisors   = 16
        sell_votes       = {}
        candle_confirmed = False

        try:
            dl_client = (self.advisor_manager.get('dl_client')
                         if self.advisor_manager else None)
            if not dl_client:
                return sell_vote_count, total_advisors, sell_votes, candle_confirmed

            peak     = analysis.get('peak',     {})
            reversal = analysis.get('reversal', {})
            candle_analysis = {
                'is_reversal':         peak.get('candle_signal',    False),
                'is_bottom':           reversal.get('candle_signal', False),
                'is_peak':             peak.get('candle_signal',    False),
                'is_rejection':        peak.get('candle_signal',    False),
                'reversal_confidence': reversal.get('confidence',   0),
                'peak_confidence':     peak.get('confidence',       0),
            }

            advice = dl_client.get_advice(
                rsi=rsi, macd=macd_diff, volume_ratio=volume_ratio,
                price_momentum=analysis.get('price_momentum', 0),
                confidence=profit_pct,
                liquidity_metrics=analysis.get('liquidity_metrics'),
                market_sentiment=analysis.get('market_sentiment'),
                candle_analysis=candle_analysis,
                analysis_data=analysis,
                action='SELL'
            )

            bearish_kw = ['Bearish', 'Sell', 'Overbought', 'Peak', 'Reversal']
            for name, text in advice.items():
                voted = any(k in str(text) for k in bearish_kw)
                sell_votes[name] = 1 if voted else 0
                if voted:
                    sell_vote_count += 1

            if any(k in str(advice.get('candle_expert', ''))
                   for k in bearish_kw):
                candle_confirmed = True

            # ✅ أصوات إضافية من المستشارين المتخصصين
            for advisor_key, condition in [
                ('AnomalyDetector',
                 analysis.get('anomaly_score', 0) > 70),
                ('LiquidityAnalyzer',
                 analysis.get('liquidity_score', 50) < 30),
                ('SmartMoneyTracker',
                 analysis.get('whale_dumping', False)),
                ('CrossExchange',
                 abs(analysis.get('price_diff_pct', 0)) > 1.0),
            ]:
                try:
                    voted = bool(condition)
                    sell_votes[advisor_key] = 1 if voted else 0
                    if voted:
                        sell_vote_count += 1
                except Exception as e:
                    logger.warning(f"{advisor_key} vote error: {e}")
                    sell_votes[advisor_key] = 0

        except Exception as e:
            print(f"⚠️ Sell voting error [{symbol}]: {e}")

        return sell_vote_count, total_advisors, sell_votes, candle_confirmed