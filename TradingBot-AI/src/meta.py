"""
Meta (The King) - The Ultimate Decision Maker
"""

import gc
import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from config import (
    MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT, MIN_SELL_CONFIDENCE, MIN_BUY_CONFIDENCE,
    MACRO_CANDLE_THRESHOLD, PEAK_DROP_THRESHOLD, BOTTOM_BOUNCE_THRESHOLD,
    VOLUME_SPIKE_FACTOR, META_BUY_INTELLIGENCE, META_BUY_WHALE, META_BUY_TREND,
    META_BUY_VOLUME, META_BUY_PATTERN, META_BUY_CANDLE, META_BUY_SUPPORT,
    META_BUY_HISTORY, META_BUY_CONSENSUS, META_DISPLAY_THRESHOLD
)
from memory.memory_cache import MemoryCache

logger = logging.getLogger(__name__)

DB_LEARNING_KEY = 'king_learning_data'


class Meta:

    # ─── حدود الذاكرة ───
    MAX_PATTERNS         = 500
    MAX_COURAGE_RECORDS  = 200
    MAX_ERROR_HISTORY    = 200
    MAX_CACHE_PATTERNS   = 1000
    MAX_PROFIT_HISTORY   = 5

    # ─── عتبات الثقة ───
    SPIKE_MIN_JUMP_1     = 5.0
    SPIKE_MIN_PROFIT_1   = 8.0
    SPIKE_MIN_JUMP_2     = 8.0
    SPIKE_MIN_PROFIT_2   = 10.0
    SPIKE_REVERSAL_HOLD  = 10.0
    SPIKE_REVERSAL_DROP  = -3.0

    # ─── عتبات البيع ───
    PEAK_VOTE_STRONG     = 8
    PEAK_CONF_STRONG     = 70
    PEAK_SIGNALS_MIN     = 2
    PEAK_SCORE_HIGH      = 80
    PEAK_SCORE_MAX       = 95
    RSI_OVERBOUGHT       = 70
    MACD_BEARISH         = -1.0
    SELL_VOTES_TECH      = 4
    SELL_VOTES_CANDLE    = 6

    # ─── عتبات الشراء ───
    FORECAST_BULL_MIN    = 0.65
    FORECAST_BEAR_MAX    = 0.45
    FLASH_RISK_MAX       = 70
    LIQ_SAFETY_MIN       = 30
    CANDLE_SCORE_STRONG  = 90
    CANDLE_SCORE_BULL    = 70
    CANDLE_SCORE_NEUTRAL = 50
    CANDLE_SCORE_BEAR    = 30
    CANDLE_SCORE_STRONG_BEAR = 10

    # ─── عتبات الكميات ───
    AMOUNT_CONF_MIN      = 50
    AMOUNT_CONF_MAX      = 100
    RSI_OVERSOLD         = 30
    RSI_LOW              = 40
    VOLUME_HIGH          = 3.0
    VOLUME_MED           = 2.0
    FLASH_RISK_AMOUNT    = 30

    # ─── عتبات Stop Loss ───
    STOP_TRAILING_MIN    = 1.0
    STOP_TRAILING_MAX    = 15.0
    STOP_ATR_MULT        = 2.5
    STOP_TIME_WARN       = 2     # دقيقتان
    STOP_TIME_NEAR       = 5     # 5 دقائق

    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager    = advisor_manager
        self.storage            = storage
        self.meta_model         = None
        self.meta_feature_names = None
        self._patterns_cache    = None
        self.profit_history: dict = {}
        self._cache = MemoryCache()

        self._load_model_data_from_db()
        self._load_patterns_to_cache()

        # Multi-Timeframe Analyzer
        self.mtf_analyzer = self._load_component(
            'multi_timeframe_analyzer', 'MultiTimeframeAnalyzer',
            extra_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        )

        # Real-time Price Action
        self.realtime_pa = self._load_component(
            'realtime_price_action', 'RealTimePriceAction'
        )

        print("👑 Meta (The King) is initialized and ready to rule.")

    # ─────────────────────────────────────────────
    # التهيئة
    # ─────────────────────────────────────────────

    def _load_component(self, module_name: str, class_name: str,
                         extra_path: str = None):
        """تحميل مكوّن خارجي بأمان"""
        try:
            import sys
            if extra_path and extra_path not in sys.path:
                sys.path.insert(0, extra_path)
            module = __import__(module_name)
            obj = getattr(module, class_name)()
            print(f"✅ Meta: {class_name} initialized")
            return obj
        except Exception as e:
            print(f"⚠️ Meta: Failed to load {class_name}: {e}")
            return None

    def _load_patterns_to_cache(self) -> None:
        """تحميل كل الأنماط من الداتابيز للرام مرة واحدة"""
        try:
            if not self.storage:
                print("⚠️ Meta: Storage not available, patterns cache disabled")
                self._patterns_cache = []
                return

            patterns = self.storage.load_all_patterns()
            self._patterns_cache = patterns

            import sys
            cache_size_kb = sys.getsizeof(self._patterns_cache) / 1024
            print(f"✅ Meta: Loaded {len(patterns)} patterns to RAM "
                  f"cache ({cache_size_kb:.1f} KB)")

        except Exception as e:
            print(f"❌ Meta: Failed to load patterns cache: {e}")
            self._patterns_cache = []

    def _load_model_data_from_db(self) -> None:
        """تحميل نموذج meta_trading من DL Client"""
        if not self.advisor_manager:
            print("⚠️ Meta: Advisor Manager not provided.")
            return
        try:
            dl_client = self.advisor_manager.get('dl_client')
            if not dl_client:
                print("⚠️ Meta: Deep Learning Client not available.")
                return
            cached_models = getattr(dl_client, '_models', None)
            if cached_models:
                self.meta_model = cached_models.get('meta_trading')
                print("✅ Meta: King's Intelligence (AI Model) loaded.")
            else:
                print("⚠️ Meta: Meta-Learner model not found in DL Client cache.")
                self.meta_model = None
        except Exception as e:
            print(f"❌ Meta: Error loading Meta-Learner: {e}")
            self.meta_model = None

    # ─────────────────────────────────────────────
    # مُعدِّلات الثقة
    # ─────────────────────────────────────────────

    def _get_news_confidence_modifier(self, symbol: str) -> tuple[int, str]:
        """تعديل الثقة من مستشار الأخبار (-15 إلى +15)"""
        try:
            news_analyzer = (self.advisor_manager.get('NewsAnalyzer')
                             if self.advisor_manager else None)
            if not news_analyzer:
                return 0, "No news"
            boost   = news_analyzer.get_news_confidence_boost(symbol)
            summary = news_analyzer.get_news_summary(symbol)
            return boost, summary
        except Exception:
            return 0, "No news"

    def _get_courage_boost(self, symbol: str, rsi: float,
                            volume_ratio: float) -> float:
        """رفع الثقة إذا نجح البوت سابقاً بنفس الظروف"""
        try:
            data           = self._load_learning_data()
            courage_record = data.get('courage_record', [])

            similar_wins = [
                r for r in courage_record
                if r.get('symbol') == symbol
                and abs(r.get('rsi', 50) - rsi) < 12
                and abs(r.get('volume_ratio', 1.0) - volume_ratio) < 0.5
                and r.get('profit', 0) > 0.5
            ]

            if not similar_wins:
                return 0

            avg_profit = sum(r['profit'] for r in similar_wins) / len(similar_wins)

            if len(similar_wins) == 1:
                boost = min(avg_profit * 1.2, 8.0)
                #print(f"💪 Soft Courage [{symbol}]: +{boost:.1f} "
                      f"(1 similar win, avg {avg_profit:.1f}%)")
                return round(boost, 1)

            boost = min(avg_profit * 2.5, 18.0)
            #print(f"💪 Courage Boost [{symbol}]: +{boost:.1f} "
                  f"(based on {len(similar_wins)} similar wins, avg {avg_profit:.1f}%)")
            return round(boost, 1)

        except Exception as e:
            print(f"⚠️ Courage boost error: {e}")
        return 0

    def _get_time_memory_modifier(self, symbol: str) -> tuple[int, str]:
        """تذكر الأوقات الناجحة/الخاسرة وتعديل الثقة"""
        try:
            data         = self._load_learning_data()
            current_hour = datetime.now(timezone.utc).hour
            hour_key     = str(current_hour)

            best_times  = data.get('best_buy_times',  {}).get(symbol, {})
            worst_times = data.get('worst_buy_times', {}).get(symbol, {})

            success = best_times.get(hour_key, 0)
            fails   = worst_times.get(hour_key, 0)
            total   = success + fails

            if success >= 3 and fails == 0:
                label = f"GoodHour({current_hour}h,{success}wins)"
                print(f"⏰ Time Boost [{symbol}]: {label}")
                return +10, label

            if total >= 4 and success / total >= 0.75:
                label = f"GoodHour({current_hour}h,{int(success/total*100)}%)"
                print(f"⏰ Time Boost [{symbol}]: {label}")
                return +6, label

            if fails >= 2:
                label = f"BadHour({current_hour}h,{fails}fails)"
                print(f"⏰ Time Penalty [{symbol}]: {label}")
                return -12, label

            if total >= 3 and fails / total >= 0.6:
                label = f"BadHour({current_hour}h,{int(fails/total*100)}%)"
                print(f"⏰ Time Penalty [{symbol}]: {label}")
                return -7, label

        except Exception as e:
            print(f"⚠️ Time memory error: {e}")
        return 0, ""

    def _get_symbol_pattern_score(self, symbol: str, rsi: float,
                                   macd_diff: float,
                                   volume_ratio: float) -> tuple[float, str]:
        """رفع الثقة بناءً على أنماط ناجحة مشابهة"""
        try:
            data     = self._load_learning_data()
            patterns = data.get('successful_patterns', [])

            symbol_patterns = [p for p in patterns if p.get('symbol') == symbol]
            if not symbol_patterns:
                return 0, ""

            matches = [
                p for p in symbol_patterns
                if abs(p.get('rsi', 50) - rsi) < 15
                and abs(p.get('volume_ratio', 1.0) - volume_ratio) < 0.8
            ]

            if len(matches) >= 3:
                avg_profit = sum(p.get('profit', 0) for p in matches) / len(matches)
                if avg_profit > 0.8:
                    boost = min(avg_profit * 2.0, 14.0)
                    label = f"Pattern({len(matches)}hits,avg{avg_profit:.1f}%)"
                    print(f"🔁 Pattern Boost [{symbol}]: +{boost:.1f} — {label}")
                    return round(boost, 1), label

            if len(matches) >= 2:
                avg_profit = sum(p.get('profit', 0) for p in matches) / len(matches)
                if avg_profit > 1.2:
                    boost = min(avg_profit * 1.2, 8.0)
                    label = f"Pattern(2hits,avg{avg_profit:.1f}%)"
                    return round(boost, 1), label

        except Exception as e:
            print(f"⚠️ Pattern score error: {e}")
        return 0, ""

    def _get_symbol_win_rate_boost(self, symbol: str) -> tuple[int, str]:
        """إضافة ثقة للعملات ذات سجل نجاح تاريخي"""
        try:
            data     = self._load_learning_data()
            win_data = data.get('symbol_win_rate', {}).get(symbol, {})
            wins     = win_data.get('wins',  0)
            total    = win_data.get('total', 0)

            if total < 5:
                return 0, ""

            win_rate = wins / total
            if win_rate >= 0.80 and total >= 8:
                label = f"WinRate({int(win_rate*100)}%,{total}trades)"
                print(f"🏆 Win Rate Boost [{symbol}]: +10 — {label}")
                return +10, label
            if win_rate >= 0.65 and total >= 5:
                label = f"WinRate({int(win_rate*100)}%,{total}trades)"
                return +5, label
            if win_rate < 0.35 and total >= 6:
                label = f"LowWin({int(win_rate*100)}%,{total}trades)"
                print(f"⚠️ Win Rate Penalty [{symbol}]: -8 — {label}")
                return -8, label

        except Exception as e:
            print(f"⚠️ Win rate boost error: {e}")
        return 0, ""

    # ─────────────────────────────────────────────
    # جمع ذكاء المستشارين للشراء
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
                whale_score = analysis_data.get('whale_confidence', 0)
                ai['whale_activity']  = abs(whale_score) * 4
                ai['whale_direction'] = 'buy' if whale_score > 0 else 'sell'
                ai['order_flow_imbalance'] = self._calc_order_flow_imbalance(
                    analysis_data, ai, reasons
                )
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
                        reasons.append(f"💥 Volume Breakout: {breakout['probability']}%")
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
            ai.update(self._gather_news_intelligence(symbol, analysis_data, reasons))
        except Exception as e:
            logger.warning(f"NewsAnalyzer error: {e}")

        # 9. Anomaly Detector
        try:
            anomaly_score    = analysis_data.get('anomaly_score', 0)
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
                ai['whale_tracking_score'] = analysis_data.get('whale_activity', 0) * 5
        except Exception as e:
            logger.warning(f"Whale tracking error: {e}")

        return ai

    def _calc_order_flow_imbalance(self, analysis_data: dict,
                                    ai: dict, reasons: list) -> float:
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
        """جمع ذكاء الأنماط من candle_expert + EnhancedPatternRecognition"""
        result = {}

        base_pattern = analysis_data.get('reversal', {}).get('confidence', 0)
        candle_score = self._get_candle_expert_score(analysis_data)

        # Peak Valley Hunter
        peak_valley_score = 50
        try:
            pattern_rec = (self.advisor_manager.get('EnhancedPatternRecognition')
                           if self.advisor_manager else None)
            if pattern_rec:
                candles = analysis_data.get('candles', [])
                if len(candles) >= 10:
                    pr = pattern_rec.analyze_peak_hunter_pattern(candles)
                    if pr['signal'] == 'buy':
                        peak_valley_score = 85
                        reasons.append(f"🎯 Peak Hunter: {pr['reason']}")
                    elif pr['signal'] == 'sell':
                        peak_valley_score = 15
                        reasons.append(f"🎯 Peak Hunter: {pr['reason']}")
                    else:
                        peak_valley_score = 50
        except Exception as e:
            print(f"⚠️ Peak hunter error: {e}")

        combined = min(100, base_pattern * 0.2
                       + candle_score * 0.3
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

    # ─────────────────────────────────────────────
    # قرار الشراء
    # ─────────────────────────────────────────────

    def should_buy(self, symbol: str, analysis: dict,
                   models_scores=None, candles=None,
                   preloaded_advisors=None) -> dict:
        """👑 قرار الشراء بناءً على meta_trading المتعلم"""
        analysis_data = analysis
        reasons       = []

        if not analysis_data or not isinstance(analysis_data, dict):
            return {'action': 'DISPLAY', 'reason': 'Invalid analysis data',
                    'confidence': 0}

        ai = self._gather_buy_advisors_intelligence(symbol, analysis_data, reasons)

        # مستشارون إضافيون
        ai.update(self._gather_extra_buy_intelligence(symbol, analysis_data))

        rsi           = analysis_data.get('rsi', 50)
        macd_diff     = analysis_data.get('macd_diff', 0)
        volume_ratio  = analysis_data.get('volume_ratio', 1.0)
        price_momentum = analysis_data.get('price_momentum', 0)
        atr            = analysis_data.get('atr', 2.5)

        symbol_memory = self._get_symbol_memory(symbol)
        features = self._build_meta_features(
            rsi=rsi, macd_diff=macd_diff, volume_ratio=volume_ratio,
            price_momentum=price_momentum, atr=atr,
            analysis_data=analysis_data,
            advisors_intelligence=ai,
            symbol_memory=symbol_memory
        )

        buy_prob, confidence, coin_fc, market_fc = self._run_meta_model(
            features, ai, direction='buy'
        )

        # تعديلات الذاكرة
        confidence += (
            self._get_courage_boost(symbol, rsi, volume_ratio)
            + self._get_time_memory_modifier(symbol)[0]
            + self._get_symbol_pattern_score(symbol, rsi, macd_diff, volume_ratio)[0]
            + self._get_symbol_win_rate_boost(symbol)[0]
        )
        confidence = max(0.0, min(100.0, confidence))

        # حماية من المخاطر الحرجة
        flash_risk = analysis_data.get('flash_crash_protection', {}).get('risk_score', 0)
        if flash_risk >= self.FLASH_RISK_MAX:
            return {'action': 'DISPLAY',
                    'reason': f'🚨 Flash Crash Risk ({flash_risk}%)',
                    'confidence': 0}

        if ai.get('liquidation_safety', 50) < self.LIQ_SAFETY_MIN:
            return {'action': 'DISPLAY',
                    'reason': '🛡️ High Liquidation Risk',
                    'confidence': 0}

        # Multi-Timeframe Bottom Detection
        confidence = self._apply_mtf_bottom_boost(
            symbol, analysis_data, candles, ai, confidence)

        if confidence >= MIN_BUY_CONFIDENCE:
            amount = self._calculate_smart_amount_safe(symbol, confidence, analysis_data)
            return {
                'action':                 'BUY',
                'reason':                 f"🤖 Meta AI: {confidence:.1f}% confidence",
                'confidence':             min(confidence, 99),
                'amount':                 amount,
                'advisors_intelligence':  ai,
                'buy_probability':        buy_prob,
                'coin_forecast':          coin_fc,
                'market_forecast':        market_fc
            }

        return {
            'action':                'DISPLAY',
            'reason':                f"🤖 Meta AI: {confidence:.1f}% - Low confidence (need {MIN_BUY_CONFIDENCE}%+)",
            'confidence':            min(confidence, 99),
            'advisors_intelligence': ai,
            'buy_probability':       buy_prob,
            'coin_forecast':         coin_fc,
            'market_forecast':       market_fc
        }

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

        # Anomaly
        try:
            anomaly = analysis_data.get('anomaly_score', 0)
            ai['trap_detection'] = 100 - min(anomaly * 10, 100)
        except Exception as e:
            logger.warning(f"Anomaly error: {e}")

        # Risk
        try:
            risk = analysis_data.get('volatility_risk_score', 2.0)
            ai['risk_level'] = max(0, 100 - risk * 10)
        except Exception as e:
            logger.warning(f"Risk error: {e}")

        # Macro Trend
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

    def _apply_mtf_bottom_boost(self, symbol: str, analysis_data: dict,
                                  candles, ai: dict,
                                  confidence: float) -> float:
        """رفع الثقة بناءً على Multi-Timeframe Bottom Detection"""
        if not self.mtf_analyzer or not candles or len(candles) < 5:
            return confidence
        try:
            candles_5m  = analysis_data.get('candles_5m',  candles)
            candles_15m = analysis_data.get('candles_15m', candles)
            candles_1h  = analysis_data.get('candles_1h',  candles)

            vol_5m  = self._extract_volumes(candles_5m)
            vol_15m = self._extract_volumes(candles_15m)
            vol_1h  = self._extract_volumes(candles_1h)

            result = self.mtf_analyzer.analyze_bottom(
                candles_5m=candles_5m, candles_15m=candles_15m,
                candles_1h=candles_1h,
                current_price=analysis_data.get('close', 0),
                volume_data_5m=vol_5m, volume_data_15m=vol_15m,
                volume_data_1h=vol_1h,
                order_book=analysis_data.get('order_book'),
                macro_status=ai.get('macro_status', 'NEUTRAL')
            )

            if result['is_bottom']:
                conf  = result['confirmations']
                ctx   = result.get('market_context', 'N/A')
                thr   = result.get('threshold_used', 60)
                print(f"⚡ Multi-TF Bottom [{symbol}]: "
                      f"{result['confidence']:.0f}% ({conf}/3 TF) | "
                      f"Market: {ctx} | Threshold: {thr}%")
                print(f"   Signals: {', '.join(result['signals'][:3])}")
                confidence += result['confidence'] * 0.15 * (conf / 3)

        except Exception as e:
            print(f"⚠️ Multi-TF bottom error: {e}")
        return confidence

    # ─────────────────────────────────────────────
    # قرار البيع
    # ─────────────────────────────────────────────

    def should_sell(self, symbol: str, position: dict,
                    current_price: float, analysis: dict,
                    mtf, candles=None,
                    preloaded_advisors=None) -> dict:
        """🔴 قرار البيع"""

        # 1. فحص القفزات المفاجئة (بيع فوري)
        spike = self._calculate_profit_spike_features(
            symbol, position, current_price)
        if spike.get('is_spike') == 1:
            buy_price = float(position.get('buy_price', 0) or 0)
            profit    = ((current_price - buy_price) / buy_price * 100
                         if buy_price > 0 else 0)
            return {
                'action':             'SELL',
                'reason':             (f"🚀 PROFIT SPIKE: "
                                       f"{spike.get('profit_jump', 0):.1f}% in "
                                       f"{spike.get('time_diff', 0):.0f}s"),
                'profit':             profit,
                'sell_votes':         {},
                'sell_vote_percentage': 100.0,
                'sell_vote_count':    16,
                'total_advisors':     16
            }

        # إعداد المتغيرات الأساسية
        ai                    = {}
        risk_level            = analysis.get('risk_level', 50)
        whale_tracking_score  = analysis.get('whale_score', 0)
        sentiment_score       = analysis.get('sentiment_score', 0)
        ai['risk_level']             = risk_level
        ai['whale_tracking_score']   = whale_tracking_score
        ai['sentiment_score']        = sentiment_score

        from config import MIN_SELL_CONFIDENCE, MIN_SELL_PROFIT

        buy_price     = float(position.get('buy_price', 0) or 0)
        current_price = float(analysis.get('close', 0) or 0)
        profit_pct    = (((current_price - buy_price) / buy_price * 100)
                         if buy_price > 0 else 0.0)
        rsi           = analysis.get('rsi', 50)
        macd_diff     = analysis.get('macd_diff', 0)
        volume_ratio  = analysis.get('volume_ratio', 1.0)

        # 2. Stop Loss فوري
        sl_info      = self._calculate_stop_loss_features(
            position, current_price, analysis,
            risk_level, whale_tracking_score, sentiment_score)
        drop         = sl_info.get('drop_from_peak', 0)
        sl_threshold = sl_info.get('threshold', 0)

        if drop >= sl_threshold:
            gc.collect()
            return {
                'action':  'SELL',
                'reason':  (f'🛡️ Stop Loss: Drop {drop:.1f}% >= '
                            f'Threshold {sl_threshold:.1f}%'),
                'profit':  profit_pct,
                'sell_votes': {},
                'stop_loss_threshold': sl_threshold
            }

        if profit_pct < MIN_SELL_PROFIT:
            reason = (f'🛡️ Stop Loss Zone: {profit_pct:.2f}%'
                      if profit_pct < -1.0
                      else f'Minimum profit not reached: {profit_pct:.2f}% < {MIN_SELL_PROFIT}%')
            return {'action': 'HOLD', 'reason': reason, 'profit': profit_pct}

        # 3. إضافة مستشاري Stop Loss
        ai.update(self._gather_stop_loss_intelligence(
            symbol, analysis, volume_ratio, sl_info))

        # 4. بناء الميزات
        symbol_memory = self._get_symbol_memory(symbol)
        features = self._build_meta_features(
            rsi=rsi, macd_diff=macd_diff, volume_ratio=volume_ratio,
            price_momentum=analysis.get('price_momentum', 0),
            atr=analysis.get('atr', 2.5),
            analysis_data=analysis,
            advisors_intelligence=ai,
            symbol_memory=symbol_memory
        )

        # 5. نموذج Meta للبيع
        sell_prob, sell_conf, coin_fc_sell, market_fc_sell = self._run_meta_model(
            features, ai, direction='sell'
        )
        meta_sell_confidence = sell_conf

        # 6. Multi-Timeframe Peak Detection
        sell_conf = self._apply_mtf_peak_boost(
            symbol, analysis, candles, position, ai, sell_conf)

        # 7. كشف القمة من المستشارين
        peak_conf, peak_reasons = self._detect_peak_signals(
            symbol, analysis, ai, profit_pct)

        # 8. تصويت المستشارين
        sell_vote_count, total_advisors, sell_votes, candle_confirmed = \
            self._run_sell_advisor_voting(
                symbol, analysis, rsi, macd_diff, volume_ratio, profit_pct)

        # 9. قرار الملك
        sell_vote_pct = (sell_vote_count / total_advisors * 100
                         if total_advisors > 0 else 0)
        peak_analysis  = analysis.get('peak', {})
        peak_score     = peak_analysis.get('confidence', 0) + peak_conf
        peak_rev_sigs  = peak_analysis.get('reversal_signals', 0)

        sentiment_confirmed = analysis.get('sentiment', {}).get('score', 0) < -1

        sell_result = self._king_sell_decision(
            symbol, profit_pct, rsi, macd_diff,
            peak_conf, peak_score, peak_reasons, peak_rev_sigs,
            sell_vote_count, total_advisors, sell_votes,
            sell_vote_pct, candle_confirmed, sentiment_confirmed,
            coin_fc_sell, market_fc_sell
        )
        if sell_result:
            return sell_result

        # 10. meta_trading له الكلمة الأخيرة
        if meta_sell_confidence >= MIN_SELL_CONFIDENCE:
            gc.collect()
            return {
                'action':       'SELL',
                'reason':       f'🤖 Meta AI: {meta_sell_confidence:.1f}% sell confidence',
                'profit':       profit_pct,
                'sell_votes':   sell_votes,
                'sell_confidence': meta_sell_confidence,
                'coin_forecast':   coin_fc_sell,
                'market_forecast': market_fc_sell
            }

        # 11. Wave Protection + Dynamic Stop Loss
        return self._wave_protection(
            symbol, analysis, candles, position,
            ai, rsi, macd_diff, volume_ratio,
            profit_pct, peak_score,
            sell_votes, sell_vote_count, total_advisors
        )

    def _gather_stop_loss_intelligence(self, symbol: str, analysis: dict,
                                        volume_ratio: float,
                                        sl_info: dict) -> dict:
        """جمع ذكاء مستشاري Stop Loss"""
        ai = {
            'drop_from_peak':  sl_info.get('drop_from_peak', 0),
            'stop_threshold':  sl_info.get('threshold', 0),
            'is_stop_loss':    sl_info.get('is_stop_loss', 0)
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
                avg_profit = (profile.get('avg_profit', 0) or 0) if profile else 0
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

    def _apply_mtf_peak_boost(self, symbol: str, analysis: dict,
                               candles, position: dict,
                               ai: dict, sell_conf: float) -> float:
        """رفع ثقة البيع بناءً على Multi-Timeframe Peak Detection"""
        if not self.mtf_analyzer or not candles or len(candles) < 5:
            return sell_conf
        try:
            candles_5m  = analysis.get('candles_5m',  candles)
            candles_15m = analysis.get('candles_15m', candles)
            candles_1h  = analysis.get('candles_1h',  candles)

            result = self.mtf_analyzer.analyze_peak(
                candles_5m=candles_5m, candles_15m=candles_15m,
                candles_1h=candles_1h,
                current_price=float(analysis.get('close', 0)),
                highest_price=position.get(
                    'highest_price',
                    float(position.get('buy_price', 0) or 0)),
                volume_data_5m=self._extract_volumes(candles_5m),
                volume_data_15m=self._extract_volumes(candles_15m),
                volume_data_1h=self._extract_volumes(candles_1h),
                order_book=analysis.get('order_book'),
                macro_status=ai.get('macro_status', 'NEUTRAL')
            )

            if result['is_peak']:
                conf = result['confirmations']
                print(f"⚡ Multi-TF Peak [{symbol}]: "
                      f"{result['confidence']:.0f}% ({conf}/3 TF)")
                print(f"   Signals: {', '.join(result['signals'][:3])}")
                sell_conf += result['confidence'] * 0.2 * (conf / 3)

        except Exception as e:
            print(f"⚠️ Multi-TF peak error: {e}")
        return sell_conf

    def _detect_peak_signals(self, symbol: str, analysis: dict,
                              ai: dict, profit_pct: float) -> tuple[int, list]:
        """كشف إشارات القمة من المستشارين الجدد"""
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

                    # Delta Volume
                    ob = analysis.get('order_book')
                    if ob and ob.get('bids') and ob.get('asks'):
                        bv = sum(b[1] for b in ob['bids'][:20])
                        av = sum(a[1] for a in ob['asks'][:20])
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
                if profile and (profile.get('avg_profit') or 0) < 2.0 and profit_pct > 5.0:
                    peak_conf += 15
                    peak_reasons.append(f"Adaptive: Quick Exit (+15)")
        except Exception as e:
            print(f"⚠️ Adaptive peak error: {e}")

        return peak_conf, peak_reasons

    def _run_sell_advisor_voting(self, symbol: str, analysis: dict,
                                  rsi: float, macd_diff: float,
                                  volume_ratio: float,
                                  profit_pct: float) -> tuple[int, int, dict, bool]:
        """تصويت مستشاري البيع"""
        sell_vote_count  = 0
        total_advisors   = 16
        sell_votes       = {}
        candle_confirmed = False

        try:
            dl_client = (self.advisor_manager.get('dl_client')
                         if self.advisor_manager else None)
            if not dl_client:
                return sell_vote_count, total_advisors, sell_votes, candle_confirmed

            peak    = analysis.get('peak', {})
            reversal = analysis.get('reversal', {})
            candle_analysis = {
                'is_reversal':         peak.get('candle_signal', False),
                'is_bottom':           reversal.get('candle_signal', False),
                'is_peak':             peak.get('candle_signal', False),
                'is_rejection':        peak.get('candle_signal', False),
                'reversal_confidence': reversal.get('confidence', 0),
                'peak_confidence':     peak.get('confidence', 0),
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

            # أصوات إضافية
            for advisor_key, condition in [
                ('AnomalyDetector',   analysis.get('anomaly_score', 0) > 70),
                ('LiquidityAnalyzer', analysis.get('liquidity_score', 50) < 30),
                ('SmartMoneyTracker', analysis.get('whale_dumping', False)),
                ('CrossExchange',     abs(analysis.get('price_diff_pct', 0)) > 1.0),
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

    def _king_sell_decision(self, symbol: str, profit_pct: float,
                             rsi: float, macd_diff: float,
                             peak_conf: int, peak_score: int,
                             peak_reasons: list, peak_rev_sigs: int,
                             sell_vote_count: int, total_advisors: int,
                             sell_votes: dict, sell_vote_pct: float,
                             candle_confirmed: bool,
                             sentiment_confirmed: bool,
                             coin_fc, market_fc) -> dict | None:
        """قرار الملك النهائي للبيع"""

        base = {
            'profit':             profit_pct,
            'optimism_penalty':   0,
            'sell_votes':         sell_votes,
            'peak_score':         peak_score,
            'sell_vote_percentage': sell_vote_pct,
            'sell_vote_count':    sell_vote_count,
            'total_advisors':     total_advisors
        }

        # قمة قوية جداً
        if (sell_vote_count >= self.PEAK_VOTE_STRONG
                and peak_conf >= self.PEAK_CONF_STRONG
                and sentiment_confirmed
                and peak_rev_sigs >= self.PEAK_SIGNALS_MIN):
            return {**base, 'action': 'SELL',
                    'reason': (f"Ultimate Peak: {sell_vote_count}/{total_advisors} "
                               f"votes + {peak_rev_sigs} signals")}

        if peak_score >= self.PEAK_SCORE_HIGH and peak_rev_sigs >= self.PEAK_SIGNALS_MIN:
            return {**base, 'action': 'SELL',
                    'reason': f"Strong Peak: {peak_score} pts + {peak_rev_sigs} signals"}

        if (rsi > self.RSI_OVERBOUGHT
                and macd_diff < self.MACD_BEARISH
                and sell_vote_count >= self.SELL_VOTES_TECH
                and peak_rev_sigs >= self.PEAK_SIGNALS_MIN):
            return {**base, 'action': 'SELL',
                    'reason': (f"Technical Peak: RSI {rsi:.0f} + "
                               f"MACD {macd_diff:.1f} + {sell_vote_count} votes")}

        if peak_score >= self.PEAK_SCORE_MAX and peak_rev_sigs >= self.PEAK_SIGNALS_MIN:
            return {**base, 'action': 'SELL',
                    'reason': f"Strong Reversal (Peak: {peak_score})"}

        if peak_conf >= 50 and peak_rev_sigs >= 3:
            return {**base, 'action': 'SELL',
                    'reason': f"Advisors Alert + {peak_rev_sigs} Signals"}

        if (peak_conf >= 60 and len(peak_reasons) >= 2
                and sentiment_confirmed
                and peak_rev_sigs >= self.PEAK_SIGNALS_MIN):
            return {**base, 'action': 'SELL',
                    'reason': (f"REAL PEAK: {', '.join(peak_reasons)} "
                               f"(Conf:{peak_conf}, Sigs:{peak_rev_sigs})")}

        return None

    def _wave_protection(self, symbol: str, analysis: dict,
                          candles, position: dict, ai: dict,
                          rsi: float, macd_diff: float,
                          volume_ratio: float, profit_pct: float,
                          peak_score: int, sell_votes: dict,
                          sell_vote_count: int,
                          total_advisors: int) -> dict:
        """Wave Protection + Dynamic Stop Loss"""
        highest_price = position.get('highest_price',
                                     float(position.get('buy_price', 0) or 0))
        drop = ((highest_price - float(analysis.get('close', 0)))
                / highest_price * 100 if highest_price > 0 else 0)

        # Stop Loss ديناميكي
        atr       = analysis.get('atr', 0) or 0
        threshold = max(
            ai.get('risk_level', 50) / 25,
            atr * self.STOP_ATR_MULT
        )
        risk_mod  = (ai.get('risk_level', 50) - 50) / 100
        threshold += risk_mod * 3
        threshold -= (ai.get('whale_tracking_score', 0) / 200) * 2
        sent_mod   = max(-10, min(10, ai.get('sentiment_score', 0))) / 100
        threshold += sent_mod * 2
        threshold  = max(self.STOP_TRAILING_MIN,
                         min(self.STOP_TRAILING_MAX, threshold))

        # توقعات Meta عند Stop Loss
        stop_coin_fc, stop_market_fc = self._calc_stop_forecasts(
            ai, rsi, macd_diff, volume_ratio)

        threshold = self._adjust_threshold_by_forecasts(
            threshold, stop_coin_fc, stop_market_fc, drop)

        # Real-time Stop Loss Trigger
        if self.realtime_pa and candles and len(candles) >= 3:
            threshold = self._apply_realtime_stop(
                symbol, analysis, candles,
                current_price=float(analysis.get('close', 0)),
                highest_price=highest_price,
                threshold=threshold)

        if drop >= threshold:
            gc.collect()
            return {
                'action':             'SELL',
                'reason':             (f'🛡️ Stop Loss: Drop {drop:.1f}% >= '
                                       f'Threshold {threshold:.1f}%'),
                'profit':             profit_pct,
                'optimism_penalty':   0,
                'sell_votes':         sell_votes,
                'peak_score':         peak_score,
                'stop_loss_threshold': threshold,
                'coin_forecast':      stop_coin_fc,
                'market_forecast':    stop_market_fc
            }

        # HOLD
        gc.collect()
        return {
            'action':             'HOLD',
            'reason':             (f'Wave Riding | Profit: {profit_pct:+.1f}% | '
                                   f'Peak: {peak_score} | '
                                   f'Votes: {sell_vote_count}/{total_advisors}'),
            'profit':             profit_pct,
            'sell_votes':         sell_votes,
            'peak_score':         peak_score,
            'stop_loss_threshold': threshold
        }

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
                print(f"⚡ Stop Loss Trigger Soon [{symbol}]: "
                      f"{trigger['confidence']:.0f}% - ETA: {eta:.1f}min")
                if eta < self.STOP_TIME_WARN:
                    threshold *= 0.6
                elif eta < self.STOP_TIME_NEAR:
                    threshold *= 0.8
                else:
                    threshold *= 0.9
        except Exception as e:
            print(f"⚠️ Real-time stop loss error: {e}")
        return threshold

    def _calc_stop_forecasts(self, ai: dict, rsi: float,
                              macd_diff: float,
                              volume_ratio: float) -> tuple[dict, dict]:
        """حساب توقعات Stop Loss للعملة والسوق"""
        coin_fc   = {'direction': 'neutral', 'confidence': 50}
        market_fc = {'direction': 'neutral', 'confidence': 50}

        try:
            if rsi < self.RSI_OVERSOLD and volume_ratio > 2.0:
                coin_fc = {'direction': 'bullish', 'confidence': 70}
            elif rsi > self.RSI_OVERBOUGHT or macd_diff < -2:
                coin_fc = {'direction': 'bearish', 'confidence': 75}

            macro_bear = ai.get('macro_bear_signal', 0)
            macro_sell = ai.get('macro_trend_sell', 50)
            if macro_bear == 1:
                market_fc = {'direction': 'bearish', 'confidence': 80}
            elif macro_sell < 30:
                market_fc = {'direction': 'bearish', 'confidence': 70}
            elif macro_sell > 70:
                market_fc = {'direction': 'bullish', 'confidence': 70}

        except Exception as e:
            print(f"⚠️ Stop forecast error: {e}")

        return coin_fc, market_fc

    @staticmethod
    def _adjust_threshold_by_forecasts(threshold: float,
                                        coin_fc: dict,
                                        market_fc: dict,
                                        drop: float) -> float:
        """تعديل عتبة Stop Loss بناءً على توقعات Meta"""
        try:
            if (coin_fc['direction'] == 'bullish'
                    and market_fc['direction'] == 'bullish'):
                mult = 1 + (coin_fc['confidence']
                            + market_fc['confidence']) / 200
                threshold *= mult
            elif (coin_fc['direction'] == 'bearish'
                  and market_fc['direction'] == 'bearish'):
                mult = 1 - (coin_fc['confidence']
                            + market_fc['confidence']) / 200
                threshold *= max(0.5, mult)
        except Exception as e:
            print(f"⚠️ Threshold adjustment error: {e}")
        return threshold

    # ─────────────────────────────────────────────
    # نموذج Meta
    # ─────────────────────────────────────────────

    def _run_meta_model(self, features: list, ai: dict,
                         direction: str) -> tuple[float, float, dict, dict]:
        """
        تشغيل نموذج meta_trading.
        direction: 'buy' | 'sell'
        Returns: (probability, confidence, coin_forecast, market_forecast)
        """
        probability   = 0.5
        confidence    = 50.0
        coin_fc       = {'direction': 'neutral', 'confidence': 50}
        market_fc     = {'direction': 'neutral', 'confidence': 50}

        if not self.meta_model:
            print("⚠️ Meta: meta_trading model not loaded, using default confidence")
            return probability, confidence, coin_fc, market_fc

        try:
            X           = pd.DataFrame([features],
                                       columns=self._get_meta_feature_names())
            raw_prob    = self.meta_model.predict_proba(X)[0][1]
            probability = (1 - raw_prob) if direction == 'sell' else raw_prob
            confidence  = probability * 100

            # توقع العملة
            if probability > self.FORECAST_BULL_MIN:
                direction_label = 'bearish' if direction == 'sell' else 'bullish'
                coin_fc = {'direction': direction_label,
                           'confidence': min(95, confidence)}
            elif probability < self.FORECAST_BEAR_MAX:
                direction_label = 'bullish' if direction == 'sell' else 'bearish'
                coin_fc = {'direction': direction_label,
                           'confidence': min(95, 100 - confidence)}

            # توقع السوق
            macro   = ai.get('macro_trend' if direction == 'buy'
                             else 'macro_trend_sell', 50)
            sent    = ai.get('sentiment_score', 0)
            whale   = ai.get('whale_activity' if direction == 'buy'
                             else 'whale_tracking_score', 0)
            sign    = 1 if direction == 'buy' else -1
            m_score = macro * 0.5 + sent * 5 * sign + whale * 0.3 * sign

            if m_score > 60:
                market_fc = {'direction': 'bullish',
                             'confidence': min(95, m_score)}
            elif m_score < 40:
                market_fc = {'direction': 'bearish',
                             'confidence': min(95, 100 - m_score)}

            # تأثير التوقعات
            if direction == 'buy':
                if (coin_fc['direction'] == 'bullish'
                        and market_fc['direction'] == 'bullish'):
                    confidence += (coin_fc['confidence']
                                   + market_fc['confidence']) / 20
                elif (coin_fc['direction'] == 'bearish'
                      or market_fc['direction'] == 'bearish'):
                    confidence -= (coin_fc['confidence']
                                   + market_fc['confidence']) / 20
            else:
                if (coin_fc['direction'] == 'bearish'
                        and market_fc['direction'] == 'bearish'):
                    confidence += (coin_fc['confidence']
                                   + market_fc['confidence']) / 20
                elif (coin_fc['direction'] == 'bullish'
                      or market_fc['direction'] == 'bullish'):
                    confidence -= (coin_fc['confidence']
                                   + market_fc['confidence']) / 20

            confidence = max(0.0, min(100.0, confidence))

        except Exception as e:
            print(f"⚠️ Meta model error: {e}")

        return probability, confidence, coin_fc, market_fc

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    def _get_symbol_memory(self, symbol: str) -> dict:
        """جلب ذاكرة العملة من الكاش أو الداتابيز"""
        try:
            memory = self._cache.get(f'symbol_mem_{symbol}') or {}
            if not memory and self.storage:
                memory = self.storage.get_symbol_memory(symbol) or {}
                if memory:
                    self._cache.set(
                        f'symbol_mem_{symbol}',
                        memory,
                        expiry_seconds=1800  # 30 دقيقة
                    )
            return memory
        except Exception as e:
            logger.warning(f"Symbol memory error: {e}")
            return {}

    def _calculate_smart_amount_safe(self, symbol: str,
                                      confidence: float,
                                      analysis: dict) -> float:
        """حساب المبلغ الذكي مع معالجة الأخطاء"""
        try:
            return self._calculate_smart_amount(symbol, confidence, analysis)
        except Exception:
            return MIN_TRADE_AMOUNT

    @staticmethod
    def _extract_volumes(candles: list, lookback: int = 10) -> list | None:
        """استخراج بيانات الحجم من الشموع"""
        if len(candles) >= lookback:
            return [c.get('volume', 0) for c in candles[-lookback:]]
        return None

    # ─────────────────────────────────────────────
    # Whale Fingerprint
    # ─────────────────────────────────────────────

    def _get_whale_fingerprint_score(self, symbol: str) -> int:
        """مراجعة ذاكرة الحيتان للعملة"""
        try:
            memory = self.storage.get_symbol_memory(symbol)
            if not memory:
                return 0

            last_whale_conf = memory.get('whale_conf', 0)
            plr             = memory.get('profit_loss_ratio', 1.0)

            result = 0
            if last_whale_conf > 10 and plr > 1.2:
                result = 15    # حيتان تشتري للصعود
            elif last_whale_conf > 10 and plr < 0.8:
                result = -25   # حيتان تصرّف (Fake Wall)

            del memory
            gc.collect()
            return result
        except Exception:
            return 0

    # ─────────────────────────────────────────────
    # بناء الميزات
    # ─────────────────────────────────────────────

    def _build_meta_features(self, rsi: float, macd_diff: float,
                              volume_ratio: float, price_momentum: float,
                              atr: float, analysis_data: dict,
                              advisors_intelligence: dict,
                              symbol_memory: dict) -> list:
        """بناء الميزات لنموذج meta_trading (48 ميزة)"""
        ai   = advisors_intelligence
        news = analysis_data.get('news', {})
        sent = analysis_data.get('sentiment', {})
        liq  = analysis_data.get('liquidity_metrics', {})

        fear_greed  = sent.get('fear_greed', 50)
        liq_score   = liq.get('liquidity_score', 50)
        news_neg    = news.get('negative', 0) + 0.001

        whale_act    = ai.get('whale_activity', 0)
        trend_birth  = ai.get('trend_birth', 50)
        pattern_conf = ai.get('pattern_confidence', 50)

        buy_signals = sum([
            whale_act    > 60,
            trend_birth  > 70,
            pattern_conf > 60,
            ai.get('volume_momentum',   0)  > 60,
            ai.get('support_strength',  0)  > 60,
        ])
        sell_signals = sum([
            ai.get('anomaly_risk',        80) < 30,
            ai.get('liquidation_safety',  50) < 30,
            ai.get('macro_trend',         50) < 30,
        ])
        consensus     = buy_signals / max(buy_signals + sell_signals, 1)
        market_quality = (ai.get('liquidity_score', 50)
                          + ai.get('support_strength', 50)) / 2

        # Context: hours_held
        hours_held = 0
        buy_time   = analysis_data.get('buy_time')
        if buy_time:
            try:
                bt = (datetime.fromisoformat(buy_time)
                      if isinstance(buy_time, str) else buy_time)
                hours_held = (datetime.now(timezone.utc) - bt
                              ).total_seconds() / 3600
            except Exception:
                hours_held = 0

        return [
            # Technical (5)
            rsi, macd_diff, volume_ratio, price_momentum, atr,
            # News (6)
            news.get('news_score', 0),
            news.get('positive', 0),
            news.get('negative', 0),
            news.get('total', 0),
            news.get('positive', 0) / news_neg,
            1 if news.get('total', 0) > 0 else 0,
            # Sentiment (5)
            sent.get('news_sentiment', 0),
            fear_greed,
            (fear_greed - 50) / 50,
            1 if fear_greed < 30 else 0,
            1 if fear_greed > 70 else 0,
            # Liquidity (4)
            liq_score,
            liq.get('depth_ratio', 1.0),
            liq.get('price_impact', 0.5),
            1 if liq_score > 70 else 0,
            # Smart Money (2)
            whale_act,
            analysis_data.get('exchange_inflow', 0),
            # Social (2)
            analysis_data.get('social_volume', 0),
            ai.get('sentiment_score', 0),
            # Consultants (3)
            consensus, buy_signals, sell_signals,
            # Derived (5)
            ai.get('risk_level', 50),
            ai.get('volume_momentum', 50),
            market_quality,
            abs(price_momentum) / 10.0,
            atr * 10,
            # Symbol Memory Basic (5)
            symbol_memory.get('win_rate',      0),
            symbol_memory.get('avg_profit',    0),
            symbol_memory.get('trap_count',    0),
            symbol_memory.get('total_trades',  0),
            1 if symbol_memory.get('win_rate', 0) > 0.6 else 0,
            # Symbol Memory New 7
            symbol_memory.get('sentiment_avg',      0),
            symbol_memory.get('whale_avg',           0),
            symbol_memory.get('profit_loss_ratio',   1.0),
            0,   # volume_trend placeholder
            symbol_memory.get('panic_avg',           0),
            symbol_memory.get('optimism_avg',        0),
            symbol_memory.get('smart_stop_loss',     0),
            # Symbol Memory New 4
            symbol_memory.get('courage_boost',   0),
            symbol_memory.get('time_memory',     0),
            symbol_memory.get('pattern_score',   0),
            symbol_memory.get('win_rate_boost',  0),
            # Context (1)
            hours_held
        ]

    def _get_meta_feature_names(self) -> list[str]:
        """أسماء الميزات (48 ميزة)"""
        return [
            'rsi', 'macd_diff', 'volume_ratio', 'price_momentum', 'atr',
            'news_score', 'news_pos', 'news_neg', 'news_total',
            'news_ratio', 'has_news',
            'sent_score', 'fear_greed', 'fear_greed_norm',
            'is_fearful', 'is_greedy',
            'liq_score', 'depth_ratio', 'price_impact', 'good_liq',
            'whale_activity', 'exchange_inflow',
            'social_volume', 'market_sentiment',
            'consensus', 'buy_count', 'sell_count',
            'risk_score', 'opportunity', 'market_quality',
            'momentum_strength', 'volatility_level',
            'sym_win_rate', 'sym_avg_profit', 'sym_trap_count',
            'sym_total', 'sym_is_reliable',
            'sym_sentiment_avg', 'sym_whale_avg',
            'sym_profit_loss_ratio', 'sym_volume_trend',
            'sym_panic_avg', 'sym_optimism_avg', 'sym_smart_stop_loss',
            'sym_courage_boost', 'sym_time_memory',
            'sym_pattern_score', 'sym_win_rate_boost',
            'hours_held'
        ]

    # ─────────────────────────────────────────────
    # حساب المبلغ الذكي
    # ─────────────────────────────────────────────

    def _calculate_smart_amount(self, symbol: str, confidence: float,
                                 analysis: dict) -> float:
        """حساب المبلغ الذكي بناءً على الثقة والمؤشرات"""
        try:
            conf_ratio   = ((max(self.AMOUNT_CONF_MIN,
                                 min(self.AMOUNT_CONF_MAX, confidence))
                             - self.AMOUNT_CONF_MIN)
                            / (self.AMOUNT_CONF_MAX - self.AMOUNT_CONF_MIN))
            base_amount  = (MIN_TRADE_AMOUNT
                            + (MAX_TRADE_AMOUNT - MIN_TRADE_AMOUNT)
                            * conf_ratio)

            rsi          = analysis.get('rsi', 50)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            macd_diff    = analysis.get('macd_diff', 0)
            flash_risk   = (analysis.get('flash_crash_protection', {})
                            .get('risk_score', 0))

            mult = 1.0
            if   rsi < self.RSI_OVERSOLD: mult *= 1.3
            elif rsi < self.RSI_LOW:      mult *= 1.1
            elif rsi > self.RSI_OVERBOUGHT: mult *= 0.7

            if   volume_ratio > self.VOLUME_HIGH: mult *= 1.2
            elif volume_ratio > self.VOLUME_MED:  mult *= 1.1

            if macd_diff < self.MACD_BEARISH:     mult *= 1.1
            if flash_risk >= self.FLASH_RISK_AMOUNT: mult *= 0.8

            return round(max(MIN_TRADE_AMOUNT,
                             min(MAX_TRADE_AMOUNT,
                                 base_amount * mult)), 2)
        except Exception as e:
            print(f"⚠️ Smart amount error: {e}")
            return MIN_TRADE_AMOUNT

    # ─────────────────────────────────────────────
    # التعلم من الصفقات
    # ─────────────────────────────────────────────

    def learn_from_trade(self, profit: float, trade_quality: str,
                          buy_votes: dict, sell_votes: dict,
                          symbol: str = None, position: dict = None,
                          extra_data: dict = None) -> None:
        """التعلم المباشر من كل صفقة"""
        try:
            data       = self._load_learning_data()
            ai_data    = (position.get('ai_data', {})
                          if position else {})
            rsi        = ai_data.get('rsi', 50)
            vol_ratio  = ai_data.get('volume_ratio',
                                     ai_data.get('volume', 1.0))
            macd_diff  = ai_data.get('macd_diff', 0)
            buy_conf   = (position.get('buy_confidence', 50)
                          if position else 50)
            hour       = datetime.now().hour
            hour_key   = str(hour)

            cur_rsi  = (extra_data.get('rsi', 50)
                        if extra_data else rsi)
            optimism = (extra_data.get('optimism', 0)
                        if extra_data else 0)
            if optimism == 0 and cur_rsi > 75:
                optimism = (cur_rsi - 75) * 0.8

            success_qualities = {'GREAT', 'GOOD', 'OK'}
            fail_qualities    = {'RISKY', 'TRAP'}

            # تعلم من البيع
            sv_count = (len([v for v in sell_votes.values() if v == 1])
                        if sell_votes else 0)
            if trade_quality in success_qualities:
                data['sell_success'] += 1
                if sv_count >= 4:
                    data['peak_correct'] += 1
            elif trade_quality in fail_qualities:
                data['sell_fail'] += 1
                if sv_count >= 4:
                    data['peak_wrong'] += 1

            # تعلم من الشراء
            if profit > 5.0:
                data['buy_success'] += 1
                pos_votes = sum(
                    1 for v in buy_votes.values()
                    if 'Bullish' in str(v)
                ) if buy_votes else 0
                if pos_votes >= 3:
                    data['bottom_correct'] += 1
            elif profit < -0.5:
                data['buy_fail'] += 1
                bv_count = (len([v for v in buy_votes.values() if v == 1])
                            if buy_votes else 0)
                if bv_count >= 3:
                    data['bottom_wrong'] += 1

            # ذاكرة ذكية عند النجاح
            if trade_quality in success_qualities:
                self._record_success(data, symbol, hour, hour_key,
                                     rsi, vol_ratio, macd_diff,
                                     buy_conf, profit)

            # ذاكرة ذكية عند الفشل
            if profit < -0.5 or trade_quality in fail_qualities:
                self._record_failure(data, symbol, hour_key,
                                     rsi, vol_ratio, buy_conf,
                                     trade_quality, profit)

            self._save_learning_data(data)
            self._update_memory_columns(
                symbol, position, data, rsi, vol_ratio,
                macd_diff, buy_conf, profit, trade_quality,
                sell_votes, buy_votes, extra_data, ai_data, optimism
            )

            total   = (data['buy_success'] + data['buy_fail']
                       + data['sell_success'] + data['sell_fail'])
            if total > 0:
                success  = data['buy_success'] + data['sell_success']
                accuracy = success / total * 100
                print(f"👑 King learned: {trade_quality} | "
                      f"Accuracy: {accuracy:.0f}% ({success}/{total})")

        except Exception as e:
            print(f"⚠️ King learning error: {e}")

    def _record_success(self, data: dict, symbol: str, hour: int,
                         hour_key: str, rsi: float, vol_ratio: float,
                         macd_diff: float, buy_conf: float,
                         profit: float) -> None:
        """تسجيل بيانات الصفقة الناجحة"""
        data['best_buy_times'].setdefault(symbol, {})
        data['best_buy_times'][symbol][hour_key] = (
            data['best_buy_times'][symbol].get(hour_key, 0) + 1)

        data['successful_patterns'].append({
            'symbol': symbol, 'rsi': rsi,
            'volume_ratio': vol_ratio, 'macd_diff': macd_diff,
            'confidence': buy_conf, 'profit': profit,
            'hour': hour,
            'date': datetime.now(timezone.utc).isoformat()
        })
        if len(data['successful_patterns']) > self.MAX_PATTERNS:
            data['successful_patterns'] = \
                data['successful_patterns'][-self.MAX_PATTERNS:]

        if rsi < 40 or vol_ratio > 2.0:
            data['courage_record'].append({
                'symbol': symbol, 'rsi': rsi,
                'volume_ratio': vol_ratio, 'confidence': buy_conf,
                'profit': profit, 'hour': hour,
                'date': datetime.now().isoformat()
            })
            if len(data['courage_record']) > self.MAX_COURAGE_RECORDS:
                data['courage_record'] = \
                    data['courage_record'][-self.MAX_COURAGE_RECORDS:]

        data['symbol_win_rate'].setdefault(
            symbol, {'wins': 0, 'total': 0})
        data['symbol_win_rate'][symbol]['wins']  += 1
        data['symbol_win_rate'][symbol]['total'] += 1

        bucket = str(int(buy_conf // 10) * 10)
        data['confidence_calibration'].setdefault(
            bucket, {'wins': 0, 'total': 0})
        data['confidence_calibration'][bucket]['wins']  += 1
        data['confidence_calibration'][bucket]['total'] += 1

    def _record_failure(self, data: dict, symbol: str, hour_key: str,
                         rsi: float, vol_ratio: float, buy_conf: float,
                         trade_quality: str, profit: float) -> None:
        """تسجيل بيانات الصفقة الفاشلة"""
        data['worst_buy_times'].setdefault(symbol, {})
        data['worst_buy_times'][symbol][hour_key] = (
            data['worst_buy_times'][symbol].get(hour_key, 0) + 1)

        data['symbol_win_rate'].setdefault(
            symbol, {'wins': 0, 'total': 0})
        data['symbol_win_rate'][symbol]['total'] += 1

        bucket = str(int(buy_conf // 10) * 10)
        data['confidence_calibration'].setdefault(
            bucket, {'wins': 0, 'total': 0})
        data['confidence_calibration'][bucket]['total'] += 1

        reason = ('trap'       if trade_quality == 'TRAP'
                  else 'low_profit' if profit < -0.5
                  else 'other')
        data['error_history'].append({
            'symbol': symbol, 'rsi': rsi,
            'volume_ratio': vol_ratio,
            'reason': reason,
            'date': datetime.now().isoformat()
        })
        if len(data['error_history']) > self.MAX_ERROR_HISTORY:
            data['error_history'] = \
                data['error_history'][-self.MAX_ERROR_HISTORY:]

    def _update_memory_columns(self, symbol: str, position,
                                data: dict, rsi: float,
                                vol_ratio: float, macd_diff: float,
                                buy_conf: float, profit: float,
                                trade_quality: str, sell_votes: dict,
                                buy_votes: dict, extra_data,
                                ai_data: dict, optimism: float) -> None:
        """تحديث أعمدة الذاكرة في الداتابيز"""
        try:
            c_boost = self._get_courage_boost(symbol, rsi, vol_ratio)
            t_mod, _ = self._get_time_memory_modifier(symbol)
            p_score, _ = self._get_symbol_pattern_score(
                symbol, rsi, macd_diff, vol_ratio)
            w_boost, _ = self._get_symbol_win_rate_boost(symbol)

            swr = data.get('symbol_win_rate', {}).get(
                symbol, {'wins': 0, 'total': 1})
            plr = swr['wins'] / max(swr['total'] - swr['wins'], 1)

            sent = (extra_data.get('sentiment', 0)
                    if extra_data else 0)
            panc = (extra_data.get('panic', 0)
                    if extra_data else 0)
            psy  = ("Greed" if sent > 2
                    else "Panic" if panc > 5
                    else "Neutral")

            if hasattr(self.storage, 'update_symbol_memory'):
                hours_held = 24.0
                if position:
                    try:
                        hours_held = float(
                            (datetime.now()
                             - datetime.fromisoformat(position['buy_time'])
                             ).total_seconds() / 3600)
                    except Exception:
                        hours_held = 24.0

                self.storage.update_symbol_memory(
                    symbol=symbol, profit=profit,
                    trade_quality=trade_quality,
                    hours_held=hours_held, rsi=rsi,
                    volume_ratio=vol_ratio, sentiment=sent,
                    whale_conf=(extra_data.get('whale_confidence', 0)
                                if extra_data
                                else ai_data.get('whale_confidence', 0)),
                    panic=panc, optimism=float(optimism),
                    profit_loss_ratio=plr,
                    volume_trend=(extra_data.get('volume_trend', 0)
                                  if extra_data else 0),
                    psychological_summary=psy,
                    courage_boost=c_boost,
                    time_memory_modifier=t_mod,
                    pattern_score=p_score,
                    win_rate_boost=w_boost
                )

            # حفظ النمط
            pattern_type = ('SUCCESS'
                            if trade_quality in {'GREAT', 'GOOD', 'OK'}
                            else 'TRAP')
            pattern_data = {
                'type':         pattern_type,
                'success_rate': 1.0 if trade_quality in {'GREAT', 'GOOD'} else 0.0,
                'features': {
                    'profit':        profit,
                    'trade_quality': trade_quality,
                    'sell_votes':    sell_votes,
                    'buy_votes':     buy_votes or {},
                    'symbol':        symbol
                }
            }
            self.storage.save_pattern(pattern_data)
            self._patterns_cache.append({
                'id':           None,
                'pattern_type': pattern_type,
                'data':         {'features': pattern_data['features']},
                'success_rate': pattern_data['success_rate']
            })
            if len(self._patterns_cache) > self.MAX_CACHE_PATTERNS:
                self._patterns_cache = \
                    self._patterns_cache[-self.MAX_CACHE_PATTERNS:]
            print(f"✅ Saved {pattern_type} pattern for {symbol}")

        except Exception as e:
            print(f"⚠️ Memory update error: {e}")

    # ─────────────────────────────────────────────
    # بيانات التعلم
    # ─────────────────────────────────────────────

    def _load_learning_data(self) -> dict:
        """تحميل بيانات التعلم من الداتابيز"""
        default = {
            'buy_success': 0, 'buy_fail': 0,
            'sell_success': 0, 'sell_fail': 0,
            'peak_correct': 0, 'peak_wrong': 0,
            'bottom_correct': 0, 'bottom_wrong': 0,
            'best_buy_times': {}, 'worst_buy_times': {},
            'best_trade_sizes': {},
            'successful_patterns': [],
            'error_history': [],
            'courage_record': [],
            'symbol_win_rate': {},
            'confidence_calibration': {}
        }
        try:
            if self.storage:
                raw = self.storage.load_setting(DB_LEARNING_KEY)
                if raw:
                    loaded = json.loads(raw) if isinstance(raw, str) else raw
                    for key, val in default.items():
                        loaded.setdefault(key, val)
                    gc.collect()
                    return loaded
        except Exception:
            pass

        # Fallback: ملف محلي
        try:
            local_file = 'data/king_learning.json'
            if os.path.exists(local_file):
                with open(local_file, 'r') as f:
                    file_data = json.load(f)
                self._save_learning_data(file_data)
                print("✅ Migrated king_learning.json to database")
                return file_data
        except Exception:
            pass

        return default

    def _save_learning_data(self, data: dict) -> None:
        """حفظ بيانات التعلم في الداتابيز"""
        try:
            if self.storage:
                self.storage.save_setting(
                    DB_LEARNING_KEY, json.dumps(data))
        except Exception as e:
            print(f"⚠️ Error saving learning data: {e}")

    def get_patterns_from_cache(self) -> list:
        """قراءة الأنماط من الرام"""
        return self._patterns_cache or []

    def get_learning_stats(self) -> dict:
        """إحصائيات تعلم الملك"""
        try:
            data    = self._load_learning_data()
            total   = (data['buy_success'] + data['buy_fail']
                       + data['sell_success'] + data['sell_fail'])
            success = data['buy_success'] + data['sell_success']

            symbol_stats = {
                sym: {'win_rate': round(w['wins'] / w['total'] * 100, 1),
                      'total':    w['total']}
                for sym, w in data.get('symbol_win_rate', {}).items()
                if w.get('total', 0) > 0
            }

            calib = {
                f"conf_{b}": {'win_rate': round(cc['wins'] / cc['total'] * 100, 1),
                               'total':    cc['total']}
                for b, cc in data.get('confidence_calibration', {}).items()
                if cc.get('total', 0) >= 3
            }

            pk  = data['peak_correct']   + data['peak_wrong']
            btm = data['bottom_correct'] + data['bottom_wrong']

            return {
                'total':                total,
                'success':              success,
                'accuracy':             success / total * 100 if total > 0 else 0,
                'peak_accuracy':        data['peak_correct']   / pk  * 100 if pk  > 0 else 0,
                'bottom_accuracy':      data['bottom_correct'] / btm * 100 if btm > 0 else 0,
                'patterns_stored':      len(data.get('successful_patterns', [])),
                'courage_records':      len(data.get('courage_record', [])),
                'symbol_win_rates':     symbol_stats,
                'confidence_calibration': calib
            }
        except Exception:
            return {'total': 0, 'success': 0, 'accuracy': 0,
                    'peak_accuracy': 0, 'bottom_accuracy': 0}

    # ─────────────────────────────────────────────
    # Profit Spike & Stop Loss Features
    # ─────────────────────────────────────────────

    def _calculate_profit_spike_features(self, symbol: str,
                                          position: dict,
                                          current_price: float) -> dict:
        """حساب معلومات القفزات"""
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'profit_jump': 0, 'time_diff': 0, 'is_spike': 0}

            current_profit = (current_price - buy_price) / buy_price * 100
            now            = datetime.now(timezone.utc)

            self.profit_history.setdefault(symbol, [])
            history = self.profit_history[symbol]

            profit_jump = time_diff = is_spike = 0

            if history:
                last_time, last_profit = history[-1]
                last_profit = last_profit or 0
                time_diff   = (now - last_time).total_seconds()

                if time_diff < 20:
                    profit_jump = current_profit - last_profit
                    if ((profit_jump >= self.SPIKE_MIN_JUMP_1
                         and current_profit >= self.SPIKE_MIN_PROFIT_1)
                        or (profit_jump >= self.SPIKE_MIN_JUMP_2
                            and current_profit >= self.SPIKE_MIN_PROFIT_2)
                        or (last_profit >= self.SPIKE_REVERSAL_HOLD
                            and profit_jump <= self.SPIKE_REVERSAL_DROP)):
                        is_spike = 1

            history.append((now, current_profit))
            if len(history) > self.MAX_PROFIT_HISTORY:
                self.profit_history[symbol] = history[-self.MAX_PROFIT_HISTORY:]

            return {
                'profit_jump':    profit_jump,
                'time_diff':      time_diff,
                'is_spike':       is_spike,
                'current_profit': current_profit
            }
        except Exception as e:
            print(f"⚠️ Profit spike error: {e}")
            return {'profit_jump': 0, 'time_diff': 0, 'is_spike': 0}

    def _calculate_stop_loss_features(self, position: dict,
                                       current_price: float,
                                       analysis: dict,
                                       risk_level: float,
                                       whale_tracking_score: float,
                                       sentiment_score: float) -> dict:
        """حساب معلومات Stop Loss"""
        try:
            buy_price = float(position.get('buy_price', 0) or 0)
            if buy_price == 0:
                return {'drop_from_peak': 0, 'threshold': 0, 'is_stop_loss': 0}

            profit_pct    = (current_price - buy_price) / buy_price * 100
            highest_price = position.get('highest_price', buy_price)
            drop          = ((highest_price - current_price) / highest_price * 100
                             if highest_price > 0 else 0)

            atr_p        = analysis.get('atr_percent', 2.5)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            rsi          = analysis.get('rsi', 50)

            threshold  = atr_p * (1 + risk_level / 100)
            threshold += (volume_ratio - 1.0) * 0.5
            threshold += (50 - rsi) / 100
            threshold -= whale_tracking_score / 500
            threshold += sentiment_score / 200
            threshold  = max(atr_p * 0.5, min(atr_p * 3.0, threshold))

            is_sl = (1 if drop >= threshold
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

    # ─────────────────────────────────────────────
    # تحديث الذاكرة
    # ─────────────────────────────────────────────

    def _update_symbol_memory(self, symbol: str) -> None:
        """تحديث ذاكرة الملك للعملة"""
        try:
            memory_data = {
                'sentiment_avg':          0,
                'whale_confidence_avg':   0,
                'profit_loss_ratio':      0,
                'volume_trend':           'neutral',
                'panic_score_avg':        0,
                'optimism_penalty_avg':   0,
                'psychological_summary':  'Updated by Meta'
            }
            if hasattr(self.storage, 'save_symbol_memory'):
                self.storage.save_symbol_memory(symbol, memory_data)
        except Exception as e:
            print(f"❌ _update_symbol_memory error for {symbol}: {e}")
