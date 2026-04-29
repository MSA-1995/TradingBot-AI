"""
👑 Meta Core
الكلاس الرئيسي - يجمع كل المكونات
"""

import gc
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from config import (
    MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT,
    MIN_SELL_CONFIDENCE, MIN_BUY_CONFIDENCE,
    MACRO_CANDLE_THRESHOLD, PEAK_DROP_THRESHOLD,
    BOTTOM_BOUNCE_THRESHOLD, VOLUME_SPIKE_FACTOR,
    META_BUY_INTELLIGENCE, META_BUY_WHALE,
    META_BUY_TREND, META_BUY_VOLUME, META_BUY_PATTERN,
    META_BUY_CANDLE, META_BUY_SUPPORT, META_BUY_HISTORY,
    META_BUY_CONSENSUS, META_DISPLAY_THRESHOLD,

)
from memory.memory_cache import MemoryCache

from meta.meta_utils    import get_meta_feature_names
from meta.meta_advisors import AdvisorsMixin
from meta.meta_buy      import BuyMixin
from meta.meta_sell     import SellMixin
from meta.meta_learning import LearningMixin

logger = logging.getLogger(__name__)


class Meta(AdvisorsMixin, BuyMixin, SellMixin, LearningMixin):
    """👑 Meta - The Ultimate Decision Maker"""

    # ─── حدود الذاكرة ───
    MAX_PATTERNS         = 500
    MAX_COURAGE_RECORDS  = 200
    MAX_ERROR_HISTORY    = 200
    MAX_CACHE_PATTERNS   = 1000
    MAX_PROFIT_HISTORY   = 5

    # ─── عتبات القفزات ───
    SPIKE_POSITIVE_THRESHOLD = 5.0
    SPIKE_TIME_WINDOW        = 20

    # ─── عتبات البيع ───

    PEAK_CONF_STRONG     = 70
    PEAK_SIGNALS_MIN     = 2
    PEAK_SCORE_HIGH      = 80
    PEAK_SCORE_MAX       = 95
    RSI_OVERBOUGHT       = 70
    MACD_BEARISH         = -0.05  # نسبة % بدل دولار



    # ─── عتبات الشراء ───
    FORECAST_BULL_MIN    = 0.65
    FORECAST_BEAR_MAX    = 0.45
    FLASH_RISK_MAX       = 70
    LIQ_SAFETY_MIN       = 30
    CANDLE_SCORE_STRONG      = 90
    CANDLE_SCORE_BULL        = 70
    CANDLE_SCORE_NEUTRAL     = 50
    CANDLE_SCORE_BEAR        = 30
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
    STOP_TIME_WARN       = 2
    STOP_TIME_NEAR       = 5

    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager    = advisor_manager
        self.storage            = storage
        self.meta_model         = None
        self.meta_feature_names = None
        self._patterns_cache    = None
        self.profit_history: dict = {}
        self._cache             = MemoryCache()

        self._load_model_data_from_db()
        self._load_patterns_to_cache()

        # ── Multi-Timeframe Analyzer ──
        self.mtf_analyzer = self._load_component(
            'multi_timeframe_analyzer', 'MultiTimeframeAnalyzer',
            extra_path=os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'models')
        )

        # ── Real-time Price Action ──
        self.realtime_pa = self._load_component(
            'realtime_price_action', 'RealTimePriceAction'
        )

        # ── News Analyzer ──
        try:
            from news_analyzer import NewsAnalyzer
            self.news_analyzer = NewsAnalyzer(storage=self.storage)
        except Exception as e:
            print(f"⚠️ NewsAnalyzer not loaded: {e}")
            self.news_analyzer = None

        pass  # silent init

    # ─────────────────────────────────────────────
    # تحميل المكونات
    # ─────────────────────────────────────────────

    def _load_component(self, module_name: str, class_name: str,
                         extra_path: str = None):
        """تحميل مكوّن خارجي بأمان"""
        try:
            import sys
            if extra_path and extra_path not in sys.path:
                sys.path.insert(0, extra_path)
            module = __import__(module_name)
            obj    = getattr(module, class_name)()
            pass  # silent
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

            patterns             = self.storage.load_all_patterns()
            self._patterns_cache = patterns

            import sys
            cache_size_kb = sys.getsizeof(self._patterns_cache) / 1024
            pass  # silent


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
                pass  # silent
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

            avg_profit = (sum(r['profit'] for r in similar_wins)
                          / len(similar_wins))

            if len(similar_wins) == 1:
                return round(min(avg_profit * 1.2, 3.0), 1)

            return round(min(avg_profit * 2.5, 5.0), 1)

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

            success = best_times.get(hour_key,  0)
            fails   = worst_times.get(hour_key, 0)
            total   = success + fails

            if success >= 3 and fails == 0:
                label = f"GoodHour({current_hour}h,{success}wins)"
                print(f"⏰ Time Boost [{symbol}]: {label}")
                return +5, label

            if total >= 4 and success / total >= 0.75:
                label = f"GoodHour({current_hour}h,{int(success/total*100)}%)"
                print(f"⏰ Time Boost [{symbol}]: {label}")
                return +3, label

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
                                   macd_diff_pct: float,
                                   volume_ratio: float) -> tuple[float, str]:
        """رفع الثقة بناءً على أنماط ناجحة مشابهة"""
        try:
            data     = self._load_learning_data()
            patterns = data.get('successful_patterns', [])

            symbol_patterns = [p for p in patterns
                               if p.get('symbol') == symbol]
            if not symbol_patterns:
                return 0, ""

            matches = [
                p for p in symbol_patterns
                if abs(p.get('rsi', 50) - rsi) < 15
                and abs(p.get('volume_ratio', 1.0) - volume_ratio) < 0.8
            ]

            if len(matches) >= 3:
                avg_profit = (sum(p.get('profit', 0) for p in matches)
                              / len(matches))
                if avg_profit > 0.8:
                    boost = min(avg_profit * 2.0, 5.0)
                    label = f"Pattern({len(matches)}hits,avg{avg_profit:.1f}%)"
                    return round(boost, 1), label

            if len(matches) >= 2:
                avg_profit = (sum(p.get('profit', 0) for p in matches)
                              / len(matches))
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
                return +5, label
            if win_rate >= 0.65 and total >= 5:
                label = f"WinRate({int(win_rate*100)}%,{total}trades)"
                return +2, label
            if win_rate < 0.35 and total >= 6:
                label = f"LowWin({int(win_rate*100)}%,{total}trades)"
                print(f"⚠️ Win Rate Penalty [{symbol}]: -8 — {label}")
                return -8, label

        except Exception as e:
            print(f"⚠️ Win rate boost error: {e}")
        return 0, ""

    # ─────────────────────────────────────────────
    # الذاكرة
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
                        expiry_seconds=1800
                    )
            return memory
        except Exception as e:
            logger.warning(f"Symbol memory error: {e}")
            return {}

    def _update_symbol_memory(self, symbol: str) -> None:
        """تحديث ذاكرة الملك للعملة"""
        try:
            memory_data = {
                'sentiment_avg':         0,
                'whale_confidence_avg':  0,
                'profit_loss_ratio':     0,
                'volume_trend':          'neutral',
                'panic_score_avg':       0,
                'optimism_penalty_avg':  0,
                'psychological_summary': 'Updated by Meta'
            }
            if hasattr(self.storage, 'save_symbol_memory'):
                self.storage.save_symbol_memory(symbol, memory_data)
        except Exception as e:
            print(f"❌ _update_symbol_memory error for {symbol}: {e}")

    def _get_whale_fingerprint_score(self, symbol: str) -> int:
        """مراجعة ذاكرة الحيتان للعملة"""
        try:
            memory = self.storage.get_symbol_memory(symbol)
            if not memory:
                return 0

            last_whale_conf = memory.get('whale_conf',         0)
            plr             = memory.get('profit_loss_ratio', 1.0)

            result = 0
            if last_whale_conf > 10 and plr > 1.2:
                result = 15     # حيتان تشتري للصعود
            elif last_whale_conf > 10 and plr < 0.8:
                result = -25    # حيتان تصرّف (Fake Wall)

            del memory
            gc.collect()
            return result
        except Exception:
            return 0

    # ─────────────────────────────────────────────
    # نموذج Meta
    # ─────────────────────────────────────────────

    def _run_meta_model(self, features: list, ai: dict,
                         direction: str) -> tuple[float, float, dict, dict]:
        """
        تشغيل نموذج meta_trading
        direction: 'buy' | 'sell'
        Returns: (probability, confidence, coin_forecast, market_forecast)
        """
        probability   = 0.5
        confidence    = 50.0
        coin_fc       = {'direction': 'neutral', 'confidence': 50}
        market_fc     = {'direction': 'neutral', 'confidence': 50}

        if not self.meta_model:
            print("⚠️ Meta: meta_trading model not loaded, using default")
            return probability, confidence, coin_fc, market_fc

        try:
            X        = pd.DataFrame([features],
                                    columns=get_meta_feature_names())
            raw_prob = self.meta_model.predict_proba(X)[0][1]
            probability = (1 - raw_prob) if direction == 'sell' else raw_prob
            confidence  = probability * 100

            # ── توقع العملة ──
            if probability > self.FORECAST_BULL_MIN:
                direction_label = ('bearish' if direction == 'sell'
                                   else 'bullish')
                coin_fc = {'direction': direction_label,
                           'confidence': min(95, confidence)}
            elif probability < self.FORECAST_BEAR_MAX:
                direction_label = ('bullish' if direction == 'sell'
                                   else 'bearish')
                coin_fc = {'direction': direction_label,
                           'confidence': min(95, 100 - confidence)}

            # ── توقع السوق ──
            macro = ai.get('macro_trend' if direction == 'buy'
                           else 'macro_trend_sell', 50)
            sent  = ai.get('sentiment_score', 0)
            whale = ai.get('whale_activity' if direction == 'buy'
                           else 'whale_tracking_score', 0)
            sign  = 1 if direction == 'buy' else -1
            m_score = macro * 0.5 + sent * 5 * sign + whale * 0.3 * sign

            if   m_score > 60:
                market_fc = {'direction': 'bullish',
                             'confidence': min(95, m_score)}
            elif m_score < 40:
                market_fc = {'direction': 'bearish',
                             'confidence': min(95, 100 - m_score)}

            # ── تأثير التوقعات على الثقة ──
            if direction == 'buy':
                if (coin_fc['direction'] == 'bullish'
                        and market_fc['direction'] == 'bullish'):
                    confidence += ((coin_fc['confidence'] + market_fc['confidence']) / 80)
                elif (coin_fc['direction'] == 'bearish'
                      or market_fc['direction'] == 'bearish'):
                    confidence -= ((coin_fc['confidence']
                                    + market_fc['confidence']) / 25)
            else:
                if (coin_fc['direction'] == 'bearish'
                        and market_fc['direction'] == 'bearish'):
                    confidence += ((coin_fc['confidence']
                                    + market_fc['confidence']) / 70)
                elif (coin_fc['direction'] == 'bullish'
                      or market_fc['direction'] == 'bullish'):
                    confidence -= ((coin_fc['confidence']
                                    + market_fc['confidence']) / 25)

            confidence = max(0.0, min(100.0, confidence))

        except Exception as e:
            print(f"⚠️ Meta model error: {e}")

        return probability, confidence, coin_fc, market_fc

    def _calibrate_meta_confidence(self, confidence: float,
                                   core_votes: dict,
                                   support_points: float,
                                   direction: str,
                                   analysis_data: dict,
                                   ai: dict) -> float:
        """معايرة ثقة meta_trading بإجماع المستشارين والذاكرة."""
        try:
            raw_conf = max(0.0, min(100.0, float(confidence or 0)))
            votes = [
                max(0.0, min(100.0, float(v or 0)))
                for v in (core_votes or {}).values()
                if isinstance(v, (int, float))
            ]
            core_avg = sum(votes) / len(votes) if votes else 0.0
            strong_votes = sum(1 for v in votes if v >= 60)
            support_norm = max(0.0, min(100.0, (support_points / 25.0) * 100.0))

            evidence = core_avg * 0.65 + support_norm * 0.35
            calibrated = raw_conf * 0.68 + evidence * 0.32

            rsi = float(analysis_data.get('rsi', 50) or 50)
            macd = float(
                analysis_data.get('latest', {}).get(
                    'macd_diff_pct',
                    analysis_data.get('macd_diff_pct', 0)
                ) or 0
            )
            momentum = float(analysis_data.get('price_momentum', 0) or 0)

            contradictions = 0
            if direction == 'buy':
                contradictions += int(rsi > 65)
                contradictions += int(macd < 0)
                contradictions += int(momentum < -0.3)
            else:
                contradictions += int(rsi < 40)
                contradictions += int(macd > 0)
                contradictions += int(momentum > 0.3)

            if core_avg < 25 and raw_conf > 70:
                calibrated -= min(18.0, (raw_conf - 70) * 0.45 + 8)
            if strong_votes == 0 and raw_conf > 65:
                calibrated -= 8
            if contradictions:
                calibrated -= 6 * contradictions

            if strong_votes >= 3 and support_points >= 8 and contradictions == 0:
                calibrated += min(5.0, strong_votes * 1.2)

            if direction == 'buy' and hasattr(self, '_load_learning_data'):
                data = self._load_learning_data()
                bucket = str(int(raw_conf // 10) * 10)
                stats = data.get('confidence_calibration', {}).get(bucket, {})
                total = stats.get('total', 0)
                if total >= 8:
                    learned = (stats.get('wins', 0) / total) * 100.0
                    calibrated = calibrated * 0.85 + learned * 0.15
                    if learned < 45 and raw_conf > 70:
                        calibrated -= 5

            cap = 94.0
            if strong_votes < 3 or support_points < 8:
                cap = 88.0
            if strong_votes < 2 and support_points < 6:
                cap = 72.0
            if strong_votes == 0:
                cap = 65.0
            if contradictions >= 2:
                cap = min(cap, 68.0)

            calibrated = max(0.0, min(cap, calibrated))

            ai['meta_raw_confidence'] = round(raw_conf, 2)
            ai['meta_calibration'] = {
                'core_avg': round(core_avg, 1),
                'strong_votes': strong_votes,
                'support_norm': round(support_norm, 1),
                'contradictions': contradictions,
                'cap': cap,
            }
            return calibrated

        except Exception as e:
            logger.warning(f"Meta confidence calibration error: {e}")
            return max(0.0, min(100.0, confidence))

    # ─────────────────────────────────────────────
    # بناء الميزات
    # ─────────────────────────────────────────────

    def _build_meta_features(self, rsi: float, macd_diff_pct: float,
                              volume_ratio: float, price_momentum: float,
                              atr: float, analysis_data: dict,
                              advisors_intelligence: dict,
                              symbol_memory: dict) -> list:
        """بناء الميزات لنموذج meta_trading (48 ميزة)"""
        ai   = advisors_intelligence
        news = analysis_data.get('news',              {})
        sent = analysis_data.get('sentiment',          {})
        liq  = analysis_data.get('liquidity_metrics', {})

        fear_greed   = sent.get('fear_greed',     50)
        liq_score    = liq.get('liquidity_score', 50)
        news_neg     = news.get('negative',        0) + 0.001

        whale_act    = ai.get('whale_activity',    0)
        trend_birth  = ai.get('trend_birth',       50)
        pattern_conf = ai.get('pattern_confidence', 50)

        buy_signals = sum([
            whale_act    > 60,
            trend_birth  > 70,
            pattern_conf > 60,
            ai.get('volume_momentum',  0) > 60,
            ai.get('support_strength', 0) > 60,
        ])
        sell_signals = sum([
            ai.get('anomaly_risk',       80) < 30,
            ai.get('liquidation_safety', 50) < 30,
            ai.get('macro_trend',        50) < 30,
        ])
        consensus      = buy_signals / max(buy_signals + sell_signals, 1)
        market_quality = (ai.get('liquidity_score',  50)
                          + ai.get('support_strength', 50)) / 2

        # ── Context: hours_held ──
        hours_held = 0
        buy_time   = analysis_data.get('buy_time')
        if buy_time:
            try:
                bt = (datetime.fromisoformat(buy_time)
                      if isinstance(buy_time, str) else buy_time)
                hours_held = ((datetime.now(timezone.utc) - bt)
                              .total_seconds() / 3600)
            except Exception:
                hours_held = 0

        return [
            # Technical (5)
            rsi, macd_diff_pct, volume_ratio, price_momentum, atr,
            # News (6)
            news.get('news_score', 0),
            news.get('positive',   0),
            news.get('negative',   0),
            news.get('total',      0),
            news.get('positive',   0) / news_neg,
            1 if news.get('total', 0) > 0 else 0,
            # Sentiment (5)
            sent.get('news_sentiment', 0),
            fear_greed,
            (fear_greed - 50) / 50,
            1 if fear_greed < 30 else 0,
            1 if fear_greed > 70 else 0,
            # Liquidity (4)
            liq_score,
            liq.get('depth_ratio',  1.0),
            liq.get('price_impact', 0.5),
            1 if liq_score > 70 else 0,
            # Smart Money (2)
            whale_act,
            analysis_data.get('exchange_inflow', 0),
            # Social (2)
            analysis_data.get('social_volume', 0),
            ai.get('sentiment_score',  0),
            # Consultants (3)
            consensus, buy_signals, sell_signals,
            # Derived (5)
            ai.get('risk_level',      50),
            ai.get('volume_momentum', 50),
            market_quality,
            abs(price_momentum) / 10.0,
            atr * 10,
            # Symbol Memory Basic (5)
            symbol_memory.get('win_rate',     0),
            symbol_memory.get('avg_profit',   0),
            symbol_memory.get('trap_count',   0),
            symbol_memory.get('total_trades', 0),
            1 if symbol_memory.get('win_rate', 0) > 0.6 else 0,
            # Symbol Memory Advanced (7)
            symbol_memory.get('sentiment_avg',    0),
            symbol_memory.get('whale_avg',         0),
            symbol_memory.get('profit_loss_ratio', 1.0),
            0,  # volume_trend placeholder
            symbol_memory.get('panic_avg',         0),
            symbol_memory.get('optimism_avg',      0),
            symbol_memory.get('smart_stop_loss',   0),
            # Symbol Memory Boost (4)
            symbol_memory.get('courage_boost',  0),
            symbol_memory.get('time_memory',    0),
            symbol_memory.get('pattern_score',  0),
            symbol_memory.get('win_rate_boost', 0),
            # Context (1)
            hours_held
        ]
