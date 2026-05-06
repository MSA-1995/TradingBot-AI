"""
🤝 Meta Advisors
7 مصوتين للقاع + 7 مصوتين للقمة
+ مدخلات دعم
"""

import logging
import pandas as pd
from datetime import datetime

from meta.meta_utils import _EnhancedPatternRecognitionFallback

logger = logging.getLogger(__name__)


class AdvisorsMixin:

    # ─────────────────────────────────────────────
    # 🟢 تصويت القاع - 7 مستشارين
    # ─────────────────────────────────────────────

    def _run_buy_core_voting(self, symbol: str,
                              analysis_data: dict,
                              candles: list) -> dict:
        """
        7 مستشارين يصوتون للقاع
        كل واحد يرجع score 0-100
        """
        votes = {}

        # 1️⃣ candle_expert
        try:
            votes['candle_expert'] = self._get_candle_score(
                analysis_data, action='BUY')
        except Exception as e:
            print(f"⚠️ candle_expert buy error: {e}")
            votes['candle_expert'] = 0

        # 2️⃣ chart_cnn
        try:
            votes['chart_cnn'] = analysis_data.get(
                'chart_cnn_buy_score',
                analysis_data.get('chart_cnn_score', 0))
        except Exception as e:
            print(f"⚠️ chart_cnn buy error: {e}")
            votes['chart_cnn'] = 0

        # 3️⃣ RealTimePriceAction
        try:
            votes['realtime_pa'] = 0
            if self.realtime_pa and candles and len(candles) >= 3:
                rt = self.realtime_pa.detect_bottom(
                    symbol=symbol,
                    candles=candles,
                    current_price=analysis_data.get('close', 0),
                    analysis=analysis_data
                )
                if rt:
                    votes['realtime_pa'] = rt.get('confidence', 0)
        except Exception as e:
            print(f"⚠️ realtime_pa buy error: {e}")
            votes['realtime_pa'] = 0

        # 4️⃣ MultiTimeframeAnalyzer
        try:
            votes['multitimeframe'] = 0
            if self.mtf_analyzer and candles and len(candles) >= 3:
                from meta.meta_utils import extract_volumes
                c5  = analysis_data.get('candles_5m',  candles)
                c15 = analysis_data.get('candles_15m', candles)
                c1h = analysis_data.get('candles_1h',  candles)
                r = self.mtf_analyzer.analyze_bottom(
                    candles_5m=c5, candles_15m=c15, candles_1h=c1h,
                    current_price=analysis_data.get('close', 0),
                    volume_data_5m=extract_volumes(c5),
                    volume_data_15m=extract_volumes(c15),
                    volume_data_1h=extract_volumes(c1h),
                    order_book=analysis_data.get('order_book'),
                    macro_status=analysis_data.get('macro_status','NEUTRAL')
                )
                if r and r.get('confidence', 0) > 20:
                    conf = r.get('confirmations', 1)
                    votes['multitimeframe'] = (
                        r['confidence'] * (max(conf,1) / 3))
        except Exception as e:
            print(f"⚠️ multitimeframe buy error: {e}")
            votes['multitimeframe'] = 0

        # 5️⃣ FibonacciAnalyzer
        try:
            votes['fibonacci'] = 0
            fib = (self.advisor_manager.get('FibonacciAnalyzer')
                   if self.advisor_manager else None)
            if fib:
                is_support, boost = fib.is_at_support(
                    current_price=analysis_data.get('close', 0),
                    analysis=analysis_data,
                    volume_ratio=analysis_data.get('volume_ratio', 1.0),
                    symbol=symbol
                )
                votes['fibonacci'] = boost * 2 if is_support else 0
        except Exception as e:
            print(f"⚠️ fibonacci buy error: {e}")
            votes['fibonacci'] = 0

        # 6️⃣ SmartMoneyTracker
        try:
            whale_score = analysis_data.get('whale_confidence', 0)
            direction   = 'buy' if whale_score > 0 else 'sell'
            votes['smart_money'] = (
                abs(whale_score) * 4 if direction == 'buy' else 0)
        except Exception as e:
            print(f"⚠️ smart_money buy error: {e}")
            votes['smart_money'] = 0

        # 7️⃣ VolumeForecastEngine
        try:
            votes['volume_forecast'] = 0
            ve = (self.advisor_manager.get('VolumeForecastEngine')
                  if self.advisor_manager else None)
            if ve and candles and len(candles) >= 20:
                vols = [c.get('volume', 0) for c in candles[-20:]]
                pred = ve.predict_next_volume(
                    symbol, vols, datetime.now().hour)
                brk  = ve.detect_volume_breakout(symbol, vols, pred)
                votes['volume_forecast'] = (
                    brk['probability'] if brk.get('breakout_imminent')
                    else 0)
        except Exception as e:
            print(f"⚠️ volume_forecast buy error: {e}")
            votes['volume_forecast'] = 0

        return votes

    # ─────────────────────────────────────────────
    # 🔴 تصويت القمة - 7 مستشارين
    # ─────────────────────────────────────────────

    def _run_sell_core_voting(self, symbol: str,
                               analysis: dict,
                               candles: list,
                               current_price: float) -> dict:
        """
        7 مستشارين يصوتون للقمة
        كل واحد يرجع score 0-100
        """
        votes = {}

        # 1️⃣ candle_expert
        try:
            votes['candle_expert'] = self._get_candle_score(
                analysis, action='SELL')
        except Exception as e:
            print(f"⚠️ candle_expert sell error: {e}")
            votes['candle_expert'] = 0

        # 2️⃣ chart_cnn
        try:
            votes['chart_cnn'] = analysis.get(
                'chart_cnn_sell_score',
                analysis.get('chart_cnn_score', 0))
        except Exception as e:
            print(f"⚠️ chart_cnn sell error: {e}")
            votes['chart_cnn'] = 0

        # 3️⃣ RealTimePriceAction
        try:
            votes['realtime_pa'] = 0
            if self.realtime_pa and candles and len(candles) >= 3:
                rt = self.realtime_pa.detect_peak(
                    symbol=symbol,
                    candles=candles,
                    current_price=current_price,
                    analysis=analysis
                )
                if rt:
                    votes['realtime_pa'] = rt.get('confidence', 0)
        except Exception as e:
            print(f"⚠️ realtime_pa sell error: {e}")
            votes['realtime_pa'] = 0

        # 4️⃣ MultiTimeframeAnalyzer
        try:
            votes['multitimeframe'] = 0
            if self.mtf_analyzer and candles and len(candles) >= 5:
                from meta.meta_utils import extract_volumes
                c5  = analysis.get('candles_5m',  candles)
                c15 = analysis.get('candles_15m', candles)
                c1h = analysis.get('candles_1h',  candles)
                r = self.mtf_analyzer.analyze_peak(
                    candles_5m=c5, candles_15m=c15, candles_1h=c1h,
                    current_price=float(analysis.get('close', 0)),
                    highest_price=analysis.get('highest_price',
                        float(analysis.get('close', 0))),
                    volume_data_5m=extract_volumes(c5),
                    volume_data_15m=extract_volumes(c15),
                    volume_data_1h=extract_volumes(c1h),
                    order_book=analysis.get('order_book'),
                    macro_status=analysis.get('macro_status', 'NEUTRAL')
                )
                if r and r.get('is_peak'):
                    votes['multitimeframe'] = r.get('confidence', 0)
        except Exception as e:
            print(f"⚠️ multitimeframe sell error: {e}")
            votes['multitimeframe'] = 0

        # 5️⃣ TrendEarlyDetector
        try:
            votes['trend_detector'] = 0
            td = (self.advisor_manager.get('TrendEarlyDetector')
                  if self.advisor_manager else None)
            if td:
                td_candles = analysis.get('candles', [])
                if len(td_candles) >= 30:
                    exh = td.get_trend_exhaustion_score(
                        pd.DataFrame(td_candles), 'BULLISH')
                    votes['trend_detector'] = exh
        except Exception as e:
            print(f"⚠️ trend_detector sell error: {e}")
            votes['trend_detector'] = 0

        # 6️⃣ SmartMoneyTracker
        try:
            whale_dump  = analysis.get('whale_dumping', False)
            whale_score = analysis.get(
                'whale_score',
                analysis.get('whale_confidence', 0)
            )
            votes['smart_money'] = (
                100 if whale_dump
                else min(abs(whale_score) * 4, 100) if whale_score < 0
                else 0)
        except Exception as e:
            print(f"⚠️ smart_money sell error: {e}")
            votes['smart_money'] = 0

        # 7️⃣ Fibonacci Resistance
        try:
            votes['fibonacci'] = 0
            fib = (self.advisor_manager.get('FibonacciAnalyzer')
                   if self.advisor_manager else None)
            if fib:
                is_res, boost = fib.is_at_resistance(
                    current_price=current_price,
                    analysis=analysis,
                    volume_ratio=analysis.get('volume_ratio', 1.0),
                    symbol=symbol)
                votes['fibonacci'] = boost if is_res else 0
        except Exception as e:
            print(f"⚠️ fibonacci sell error: {e}")
            votes['fibonacci'] = 0

        # 8️⃣ VolumeForecastEngine
        try:
            votes['volume_forecast'] = 0
            ve = (self.advisor_manager.get('VolumeForecastEngine')
                  if self.advisor_manager else None)
            if ve and candles and len(candles) >= 20:
                vols = [c.get('volume', 0) for c in candles[-20:]]
                pred = ve.predict_next_volume(
                    symbol, vols, datetime.now().hour)
                if pred.get('trend') == 'DECREASING':
                    votes['volume_forecast'] = min(
                        abs(pred.get('momentum', 0)) + 50, 100)
                else:
                    votes['volume_forecast'] = 0
        except Exception as e:
            print(f"⚠️ volume_forecast sell error: {e}")
            votes['volume_forecast'] = 0

        return votes

    # للتوافق مع الكود القديم
    def _run_sell_advisor_voting(self, symbol, analysis,
                                  rsi, macd_diff,
                                  volume_ratio, profit_pct):
        candles = analysis.get('candles', [])
        current = float(analysis.get('close', 0))
        votes   = self._run_sell_core_voting(
            symbol, analysis, candles, current)
        count   = sum(1 for v in votes.values() if v >= 50)
        candle  = votes.get('candle_expert', 0) >= 50
        return count, len(votes), votes, candle

    # ─────────────────────────────────────────────
    # دالة مشتركة: candle_expert score
    # ─────────────────────────────────────────────

    def _get_candle_score(self, analysis_data: dict,
                           action: str = 'BUY') -> float:
        """جلب نقاط candle_expert من DL Client"""
        try:
            dl = (self.advisor_manager.get('dl_client')
                  if self.advisor_manager else None)
            if not dl:
                return 0

            advice = dl.get_advice(
                rsi=analysis_data.get('rsi', 50),
                macd=analysis_data.get('macd_diff', 0),
                volume_ratio=analysis_data.get('volume_ratio', 1.0),
                price_momentum=analysis_data.get('price_momentum', 0),
                confidence=50,
                analysis_data=analysis_data,
                action=action
            )
            text = str(advice.get('candle_expert', ''))

            if action == 'BUY':
                if 'Strong-Bullish' in text: return self.CANDLE_SCORE_STRONG
                if 'Bullish'        in text: return self.CANDLE_SCORE_BULL
                if 'Strong-Bearish' in text: return 0
                if 'Bearish'        in text: return 0
            else:  # SELL
                if 'Strong-Bearish' in text: return self.CANDLE_SCORE_STRONG
                if 'Bearish'        in text: return self.CANDLE_SCORE_BULL
                if 'Strong-Bullish' in text: return 0
                if 'Bullish'        in text: return 0

            return 0

        except Exception as e:
            print(f"⚠️ candle_expert score error: {e}")
            return 0

    # ─────────────────────────────────────────────
    # مستشارو الشراء - دعم فقط
    # ─────────────────────────────────────────────

    def _gather_buy_advisors_intelligence(self, symbol: str,
                                           analysis_data: dict,
                                           reasons: list) -> dict:
        """جمع مدخلات الدعم للشراء"""
        ai = {}

        # Smart Money - اتجاه فقط
        try:
            whale_score           = analysis_data.get('whale_confidence', 0)
            ai['whale_activity']  = abs(whale_score) * 4
            ai['whale_direction'] = 'buy' if whale_score > 0 else 'sell'
            ai['order_flow_imbalance'] = self._calc_order_flow_imbalance(
                analysis_data, ai, reasons)
        except Exception as e:
            logger.warning(f"SmartMoney error: {e}")

        # Volume Momentum
        try:
            ve = (self.advisor_manager.get('VolumeForecastEngine')
                  if self.advisor_manager else None)
            if ve:
                candles = analysis_data.get('candles', [])
                if len(candles) >= 20:
                    vols = [c.get('volume', 0) for c in candles[-20:]]
                    pred = ve.predict_next_volume(
                        symbol, vols, datetime.now().hour)
                    brk  = ve.detect_volume_breakout(symbol, vols, pred)
                    ai['volume_momentum'] = (
                        brk['probability']
                        if brk.get('breakout_imminent') else 0)
        except Exception as e:
            logger.warning(f"VolumeForecast error: {e}")

        # Liquidation Shield
        try:
            ls = (self.advisor_manager.get('LiquidationShield')
                  if self.advisor_manager else None)
            if ls:
                ob = analysis_data.get('order_book')
                if ob:
                    liq = ls.analyze_liquidation_risk(
                        symbol,
                        analysis_data.get('close', 0), ob)
                    ai['liquidation_safety'] = (
                        100 - liq.get('risk_score', 50))
        except Exception as e:
            logger.warning(f"LiquidationShield error: {e}")

        # Pattern + Candle
        try:
            ai.update(self._gather_pattern_intelligence(
                symbol, analysis_data, reasons))
        except Exception as e:
            logger.warning(f"Pattern error: {e}")
            ai.setdefault('pattern_confidence',  0)
            ai.setdefault('candle_expert_score', 50)

        # Fibonacci - دعم فقط
        try:
            fib = (self.advisor_manager.get('FibonacciAnalyzer')
                   if self.advisor_manager else None)
            if fib:
                is_sup, boost = fib.is_at_support(
                    current_price=analysis_data.get('close', 0),
                    analysis=analysis_data,
                    volume_ratio=analysis_data.get('volume_ratio', 1.0),
                    symbol=symbol
                )
                ai['support_strength'] = boost * 2 if is_sup else 0
        except Exception as e:
            logger.warning(f"Fibonacci error: {e}")

        # Sentiment
        ai['sentiment_score'] = analysis_data.get('sentiment_score', 0)

        # News
        try:
            ai.update(self._gather_news_intelligence(
                symbol, analysis_data, reasons))
        except Exception as e:
            logger.warning(f"News error: {e}")

        # Anomaly
        anomaly = analysis_data.get('anomaly_score', 0)
        ai['anomaly_risk'] = 10 if anomaly > 70 else 80

        # Liquidity
        ai['liquidity_score'] = analysis_data.get('liquidity_score', 50)

        return ai

    def _gather_extra_buy_intelligence(self, symbol: str,
                                        analysis_data: dict) -> dict:
        """مدخلات دعم إضافية للشراء"""
        ai = {}

        # Adaptive
        try:
            adp = (self.advisor_manager.get('AdaptiveIntelligence')
                   if self.advisor_manager else None)
            if adp:
                profile = adp.get_symbol_profile(symbol)
                if profile:
                    ai['historical_success'] = profile.get(
                        'success_rate', 50)
        except Exception as e:
            logger.warning(f"Adaptive error: {e}")

        # Risk
        risk = analysis_data.get('volatility_risk_score', 2.0)
        ai['risk_level'] = max(0, 100 - risk * 10)

        # Trap Detection
        anomaly = analysis_data.get('anomaly_score', 0)
        ai['trap_detection'] = 100 - min(anomaly * 10, 100)

        # Macro
        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                status = macro.get_macro_status()
                ai['macro_trend'] = (
                    85 if status in ('STRONG_BULL_MARKET','BULL_MARKET')
                    else 20 if status == 'BEAR_MARKET'
                    else 50)
                ai['macro_status'] = status
        except Exception as e:
            logger.warning(f"Macro error: {e}")

        ai.setdefault('entry_timing', 60)
        return ai

    # ─────────────────────────────────────────────
    # مستشارو البيع - دعم فقط
    # ─────────────────────────────────────────────

    def _gather_stop_loss_intelligence(self, symbol: str,
                                        analysis: dict,
                                        volume_ratio: float,
                                        sl_info: dict) -> dict:
        """جمع مدخلات الدعم للبيع"""
        ai = {
            'drop_from_peak': sl_info.get('drop_from_peak', 0),
            'stop_threshold': sl_info.get('threshold',      0),
            'is_stop_loss':   sl_info.get('is_stop_loss',   0),
        }

        # Fibonacci مقاومة
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

        # Volume Collapse
        try:
            ve = (self.advisor_manager.get('VolumeForecastEngine')
                  if self.advisor_manager else None)
            if ve:
                candles = analysis.get('candles', [])
                if len(candles) >= 20:
                    vols = [c.get('volume', 0) for c in candles[-20:]]
                    pred = ve.predict_next_volume(
                        symbol, vols, datetime.now().hour)
                    ai['volume_collapse_stop'] = (
                        1   if pred['trend'] == 'DECREASING'
                               and pred['momentum'] < -20
                        else 0.5 if pred['trend'] == 'DECREASING'
                        else 0)
        except Exception as e:
            logger.warning(f"Volume collapse error: {e}")
            ai['volume_collapse_stop'] = 0

        # Adaptive
        try:
            adp = (self.advisor_manager.get('AdaptiveIntelligence')
                   if self.advisor_manager else None)
            if adp:
                profile    = adp.get_symbol_profile(symbol)
                avg_profit = (profile.get('avg_profit', 0) or 0) if profile else 0
                ai['adaptive_stop_multiplier'] = (
                    1.3 if avg_profit > 5
                    else 0.7 if avg_profit < 2
                    else 1.0)
        except Exception as e:
            logger.warning(f"Adaptive stop error: {e}")
            ai['adaptive_stop_multiplier'] = 1.0

        # Macro
        try:
            macro = (self.advisor_manager.get('MacroTrendAdvisor')
                     if self.advisor_manager else None)
            if macro:
                status = macro.get_macro_status()
                ai['macro_bear_signal'] = 1 if 'BEAR' in status else 0
                ai['macro_trend_sell']  = (
                    85 if 'BEAR' in status
                    else 20 if 'BULL' in status
                    else 50)
        except Exception as e:
            logger.warning(f"Macro stop error: {e}")
            ai.setdefault('macro_bear_signal', 0)
            ai.setdefault('macro_trend_sell',  50)

        return ai

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    def _calc_order_flow_imbalance(self, analysis_data, ai, reasons):
        try:
            ob = analysis_data.get('order_book')
            if not ob: return 0.0
            bids = ob.get('bids', [])[:20]
            asks = ob.get('asks', [])[:20]
            if not bids or not asks: return 0.0
            avg_bid = sum(b[1] for b in bids) / 20
            avg_ask = sum(a[1] for a in asks) / 20
            lb = [b for b in bids if b[1] > avg_bid * 3]
            la = [a for a in asks if a[1] > avg_ask * 3]
            lbv = sum(b[1] for b in lb)
            lav = sum(a[1] for a in la)
            total = lbv + lav
            if total == 0: return 0.0
            imb = (lbv - lav) / total
            if imb > 0.4:
                ai['whale_activity'] = min(
                    100, ai.get('whale_activity', 0) + 20)
                reasons.append(f"🐋 Whale Buying: {imb:.2f}")
            return imb
        except Exception as e:
            logger.warning(f"Order flow error: {e}")
            return 0.0

    def _gather_pattern_intelligence(self, symbol, analysis_data, reasons):
        result = {}
        base   = analysis_data.get('reversal', {}).get('confidence', 0)
        candle = self._get_candle_score(analysis_data, 'BUY')
        pv     = 50
        try:
            pr = (self.advisor_manager.get('EnhancedPatternRecognition')
                  if self.advisor_manager else None)
            if not pr or not hasattr(pr, 'analyze_peak_hunter_pattern'):
                pr = _EnhancedPatternRecognitionFallback()
            c = analysis_data.get('candles', [])
            if len(c) >= 10:
                r = pr.analyze_peak_hunter_pattern(c)
                if   r['signal'] == 'buy':  pv = 85
                elif r['signal'] == 'sell': pv = 15
                else:                       pv = 50
        except Exception as e:
            print(f"⚠️ Pattern error: {e}")
        combined = min(100, base*0.2 + candle*0.3 + pv*0.5)
        result['pattern_confidence']  = combined
        result['candle_expert_score'] = candle
        result['peak_valley_score']   = pv
        return result

    def _gather_news_intelligence(self, symbol, analysis_data, reasons):
        result = {'news_impact': 0, 'historical_success': 50}
        try:
            na = (self.advisor_manager.get('NewsAnalyzer')
                  if self.advisor_manager else None)
            if not na: return result
            result['news_impact'] = na.get_news_confidence_boost(symbol)
            summary = na.get_news_summary(symbol)
            if summary and 'sentiment_history' in summary:
                h  = summary['sentiment_history'][-5:]
                if len(h) >= 3:
                    rc = sum(x.get('score',0) for x in h[-2:]) / 2
                    ol = sum(x.get('score',0) for x in h[-5:-2]) / 3
                    ch = rc - ol
                    if   ch >  2: result['news_impact'] += 10
                    elif ch < -2: result['news_impact'] -= 10
        except Exception as e:
            logger.warning(f"News error: {e}")
        return result

    # للتوافق القديم
    def _get_candle_expert_score(self, analysis_data):
        return self._get_candle_score(analysis_data, 'BUY')

    def _detect_peak_signals(self, symbol, analysis, ai, profit_pct):
        return 0, []
