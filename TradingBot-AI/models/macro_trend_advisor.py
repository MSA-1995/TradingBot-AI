"""
📈 Macro Trend Advisor - Real-time Market Regime Analysis
Determines the current market state by analyzing multiple timeframes and leader symbols.
"""

import sys
import time
import os
from typing import Optional

import numpy as np
import pandas as pd

# استيراد dl_client إذا كان متوفراً
try:
    from dl_client_v2 import DeepLearningClientV2
    DL_CLIENT_AVAILABLE = True
except ImportError:
    DeepLearningClientV2 = None
    DL_CLIENT_AVAILABLE = False


class MacroTrendAdvisor:
    """
    Determines overall market state and predicts next direction
    """

    MACRO_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']

    CACHE_DURATION      = 900  # 15 دقيقة - حالة السوق (إشارات 1h/4h بطيئة، تحديث أسرع يعطي ضجيج)
    PREDICTION_CACHE_1H = 900  # 15 دقيقة - بيانات 1h
    PREDICTION_CACHE_4H = 900  # 15 دقيقة - بيانات 4h

    RSI_PERIOD        = 14
    MOMENTUM_LOOKBACK = 10

    def __init__(self, exchange=None, dl_client=None, storage=None):
        self.exchange = exchange
        self.db = storage  # ربط كائن التخزين للوصول لقاعدة البيانات

        # حالة السوق
        self._last_status     : str   = '⚪ NEUTRAL'
        self._last_check_time : float = 0.0

        # ⏳ فلتر الصبر (Stability Timer)
        self._is_currently_bull : bool = False
        self._macro_start_time  : Optional[float] = None

        # المايكرو يستخدم dl_client المشترك المحمل مسبقاً
        self.dl_client = dl_client

        # استخدام النماذج المحملة من cache RAM مباشرة ككائنات جاهزة
        # تأكيد الأسماء الصحيحة بناءً على ما يتم حقنه في الداتابيز
        models_cache = getattr(self.dl_client, '_models', {}) if self.dl_client else {}
        
        self.volume_predictor     = models_cache.get('volume_pred')
        self.sentiment_analyzer   = models_cache.get('sentiment')
        self.liquidity_analyzer   = models_cache.get('liquidity')
        self.smart_money_tracker  = models_cache.get('smart_money')
        self.crypto_news_analyzer = models_cache.get('crypto_news')

        # كاش تحليل الحالة الراهنة
        self._last_analysis      : dict  = {}
        self._last_analysis_time : float = 0.0
        self._tf_cache           : dict  = {} # {tf: {'data': dict, 'time': float}}

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
            state = self.analyze_market_state()

            # استخدام الحالة الراهنة المجمعة
            combined_dir = state.get('combined', {}).get('direction', 'NEUTRAL')
            combined_str = state.get('combined', {}).get('strength',  'NEUTRAL')

            if   combined_dir == 'BULLISH' and combined_str == 'STRONG':  final_status = '🟢 BULL_MARKET'
            elif combined_dir == 'BEARISH' and combined_str == 'STRONG':  final_status = '🔴 BEAR_MARKET'
            elif combined_dir == 'BULLISH':                                final_status = '🟢 MILD_BULL'
            elif combined_dir == 'BEARISH' and combined_str == 'CAUTION': final_status = '🔴 MILD_BEAR'   # ✅ FIX 2: كان SIDEWAYS
            elif combined_dir == 'BEARISH':                                final_status = '🔴 MILD_BEAR'
            elif combined_dir == 'MIXED'   and combined_str == 'CAUTION': final_status = '⚪ SIDEWAYS'
            else:                                                           final_status = '⚪ SIDEWAYS'

            # حساب النقاط الكلية للعملات الثلاثة
            total_bull = state.get('1h', {}).get('bull_score', 0) + state.get('4h', {}).get('bull_score', 0)
            total_bear = state.get('1h', {}).get('bear_score', 0) + state.get('4h', {}).get('bear_score', 0)

            # تحقق الداتابيز: لو BULL، قارن بالحالة المحفوظة قبل ساعتين
            if 'BULL' in final_status:
                historical = self._get_historical_status(hours_ago=2)
                if historical and 'BEAR' in historical:
                    # 🛡️ منع تخفيض الحراسة: إذا كان التاريخ هابطاً، نبقى في وضع الحذر (80 نقطة شراء)
                    final_status = '🔴 MILD_BEAR' 

            # 🛡️ تطبيق فلتر الصبر: التأكد من استقرار الصعود لمدة 30 دقيقة (أو 5 مع التحقق السريع)
            is_bull_signal = 'BULL' in final_status
            required_mins = 30
            stability_info = ""

            # ⚡ التحقق السريع باستخدام نماذج DL المحملة من DB: إذا كان أكثر من 3 نماذج تشير إلى BULL، قلل الانتظار
            quick_verified = False
            if is_bull_signal:
                # جلب البيانات اللازمة للتحقق
                q_df = self._get_quick_verification_df()
                if q_df is not None:
                    try:
                        bull_votes = 0
                        total_models = 0

                        # تحويل الصف الأخير لمصفوفة للنماذج
                        features_array = q_df.tail(1).drop(columns=['ts'], errors='ignore').values

                        # 1. نماذج الذكاء الاصطناعي من الكاش
                        if self.volume_predictor:
                            # predict ترجع مصفوفة احتمالات
                            spike_proba = self.volume_predictor.predict(features_array)[0]
                            if spike_proba > 0.6: bull_votes += 1 
                            total_models += 1

                        if self.sentiment_analyzer:
                            sent_score = self.sentiment_analyzer.predict(features_array)[0]
                            if sent_score > 0.5: bull_votes += 1
                            total_models += 1

                        if self.liquidity_analyzer:
                            liq_score = self.liquidity_analyzer.predict(features_array)[0]
                            if liq_score > 0.5: bull_votes += 1
                            total_models += 1

                        if self.smart_money_tracker:
                            sm_score = self.smart_money_tracker.predict(features_array)[0]
                            if sm_score > 0.5: bull_votes += 1
                            total_models += 1

                        if self.crypto_news_analyzer:
                            news_score = self.crypto_news_analyzer.predict(features_array)[0]
                            if news_score > 0.5: bull_votes += 1
                            total_models += 1

                        # 2. الأكواد الثابتة (Fixed Logic)
                        try:
                            from .multi_timeframe_analyzer import MultiTimeframeAnalyzer
                            mtf_analyzer = MultiTimeframeAnalyzer()
                            # تصحيح: تحليل القاع يحتاج بيانات شمعية
                            # سنمرر نفس البيانات كإطار زمني افتراضي للتحقق
                            mtf_res = mtf_analyzer.analyze_bottom(
                                candles_5m=None, candles_15m=None, candles_1h=q_df.to_dict('records'),
                                current_price=float(q_df['c'].iloc[-1])
                            )
                            if mtf_res.get('confidence', 0) > 60:
                                bull_votes += 1
                            total_models += 1
                        except Exception:
                            pass

                        try:
                            from .trend_early_detector import TrendEarlyDetector
                            ted = TrendEarlyDetector()
                            # تصحيح: اسم الدالة detect_trend_birth
                            ted_res = ted.detect_trend_birth(q_df)
                            if ted_res.get('trend') == 'BULLISH' and ted_res.get('confidence', 0) > 50:
                                bull_votes += 1
                            total_models += 1
                        except Exception:
                            pass

                        if total_models >= 5 and bull_votes >= 5:  # أكثر من 70% من 7 متفقة على BULL
                            # ⚡ حتى مع موافقة الكل، دقيقة واحدة غير كافية للتأكد. 10 دقائق هي الحد الأدنى للأمان.
                            required_mins = 10 
                            quick_verified = True
                    except Exception as e:
                        print(f"⚠️ Error in DL model verification: {e}")

            if is_bull_signal:
                if not self._is_currently_bull or self._macro_start_time is None:
                    # بداية رصد محاولة صعود جديدة
                    self._is_currently_bull = True
                    self._macro_start_time = time.time()
                
                elapsed_mins = (time.time() - self._macro_start_time) / 60
                if elapsed_mins < required_mins:
                    # لم يستقر بعد -> نحجب إشارة الشراء
                    verify_type = "Quick" if quick_verified else "Standard"
                    stability_info = f" (⏳ {int(elapsed_mins)}/{required_mins}m {verify_type})"
                    final_status = f"⚪ STABILIZING ({int(elapsed_mins)}/{required_mins}m {verify_type})"
                else:
                    stability_info = " (✅ Stable)"
            else:
                # أي تراجع أو تذبذب يصفر العداد فوراً
                self._is_currently_bull = False
                self._macro_start_time = None

            self._display_info = {
                'status'    : final_status + stability_info if "STABILIZING" not in final_status else final_status,
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
            'total_bull': 0,
            'total_bear': 0,
        }

    def can_aim_high(self) -> bool:
        return 'BULL' in self.get_macro_status()

    def invalidate_cache(self) -> None:
        """إعادة ضبط كل الكاش"""
        self._last_check_time          = 0.0
        self._last_analysis_time       = 0.0
        self._tf_cache.clear()

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
    #  State Analysis System
    # ═════════════════════════════════════════════

    def analyze_market_state(self) -> dict:
        """تحليل حالة السوق الراهنة عبر أطر زمنية متعددة"""
        if not self.exchange:
            return self._empty_state()

        if time.time() - self._last_analysis_time < 300: # تحديث كل 5 دقائق كافٍ للماكرو
            return self._last_analysis

        try:
            # تحليل الحالة الراهنة (Current State) لكل إطار زمني
            m15 = self._analyze_timeframe_state('15m', 48)
            h1  = self._analyze_timeframe_state('1h',  24)
            h4  = self._analyze_timeframe_state('4h',  24)
            
            combined = self._combine_timeframes(m15, h1, h4)

            result = {
                '15m'     : m15,
                '1h'      : h1,
                '4h'      : h4,
                'combined': combined,
            }

            self._last_analysis      = result
            self._last_analysis_time = time.time()
            return result

        except Exception as e:
            print(f"⚠️ analyze_market_state error: {e}")
            return self._empty_state()

    def _analyze_timeframe_state(self, timeframe: str, limit: int) -> dict:
        """تحليل الحالة الفنية لإطار زمني محدد عبر العملات القائدة"""
        cache = self._tf_cache.get(timeframe)
        if cache and (time.time() - cache['time'] < 300):
            return cache['data']

        results = []
        for symbol in self.MACRO_SYMBOLS:
            try:
                # تحليل الحالة اللحظية للعملة
                analysis = self._analyze_symbol_state(symbol, timeframe, limit)
                if analysis:
                    results.append(analysis)
            except Exception as e:
                print(f"⚠️ Analysis error {symbol} {timeframe}: {e}")

        if not results:
            return {'status': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'}

        result = self._aggregate_symbol_results(results, timeframe)
        self._tf_cache[timeframe] = {'data': result, 'time': time.time()}
        return result

    def _analyze_symbol_state(self, symbol: str, timeframe: str, limit: int) -> Optional[dict]:
        """تحليل فني عميق لحالة العملة الراهنة (Current State)"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df    = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

        if len(df) < 10:
            return None

        bull_signals = 0
        bear_signals = 0

        # 1. الاتجاه الحقيقي - آخر 10 شموع بدلاً من 3 (weight 4)
        last_10_change = (
            (float(df['c'].iloc[-1]) - float(df['c'].iloc[-11]))
            / float(df['c'].iloc[-11]) * 100
        )
        # شرط أقوى: لازم يكون الصعود/الهبوط واضح
        if   last_10_change >  1.5: bull_signals += 4  # صعود قوي
        elif last_10_change >  0.5: bull_signals += 2  # صعود خفيف
        elif last_10_change < -1.5: bear_signals += 4  # هبوط قوي
        elif last_10_change < -0.5: bear_signals += 2  # هبوط خفيف
        # لو التغيير بين -0.5% و +0.5% = سوق عرضي (لا نضيف نقاط)

        # 2. RSI - تعديل الحدود (weight 3)
        rsi = self._calculate_rsi(df['c'])
        if   rsi > 75: bear_signals += 3  # تشبع شرائي قوي
        elif rsi > 65: bear_signals += 1  # تشبع شرائي خفيف
        elif rsi > 55: bull_signals += 1  # زخم صاعد
        elif rsi < 30: bull_signals += 3  # تشبع بيعي قوي
        elif rsi < 40: bull_signals += 1  # تشبع بيعي خفيف
        elif rsi > 45 and rsi < 55: pass  # منطقة محايدة

        # 3. Volume - فلتر الصعود الوهمي (weight 3)
        avg_vol   = float(df['v'].iloc[-20:].mean())
        last_vol  = float(df['v'].iloc[-1])
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        # ✅ الفلتر الأهم: صعود بحجم ضعيف = فخ!
        if vol_ratio < 0.8 and last_10_change > 0.5:
            bear_signals += 8  # مضاعفة العقوبة لمنع اعتبار هذه الحالة "عرضية" أو "صاعدة"
        elif vol_ratio > 2.0 and last_10_change > 0:
            bull_signals += 3  # صعود بحجم قوي = اتجاه حقيقي
        elif vol_ratio > 2.0 and last_10_change < 0:
            bear_signals += 3  # هبوط بحجم قوي = اتجاه حقيقي
        elif vol_ratio < 0.5:
            bear_signals += 1  # حجم ضعيف = ضعف السوق

        # 4. MACD - اتجاه الزخم (weight 2)
        macd         = df['c'].ewm(span=12).mean() - df['c'].ewm(span=26).mean()
        macd_signal  = macd.ewm(span=9).mean()
        macd_hist    = macd - macd_signal
        hist_current = float(macd_hist.iloc[-1])
        hist_prev    = float(macd_hist.iloc[-2])

        # استخدام الهستوجرام بدلاً من MACD المباشر (أدق)
        if   hist_current > 0 and hist_current > hist_prev: bull_signals += 2
        elif hist_current > 0:                               bull_signals += 1
        elif hist_current < 0 and hist_current < hist_prev: bear_signals += 2
        elif hist_current < 0:                               bear_signals += 1

        # 5. EMA Cross قصير المدى (weight 1)
        ema_9  = float(df['c'].ewm(span=9).mean().iloc[-1])
        ema_21 = float(df['c'].ewm(span=21).mean().iloc[-1])
        if ema_9 > ema_21: bull_signals += 1
        else:              bear_signals += 1

        # 5b. فلتر الاتجاه الحقيقي EMA50/200 (weight 3) — يمنع الشراء في سوق هابط
        # هذا الفلتر هو الأهم: لو السعر تحت EMA200 = سوق هابط بغض النظر عن الإشارات القصيرة
        if len(df) >= 200:
            ema_50  = float(df['c'].ewm(span=50,  adjust=False).mean().iloc[-1])
            ema_200 = float(df['c'].ewm(span=200, adjust=False).mean().iloc[-1])
            price   = float(df['c'].iloc[-1])

            if   price > ema_200 and ema_50 > ema_200: bull_signals += 3  # اتجاه صاعد حقيقي
            elif price < ema_200 and ema_50 < ema_200: bear_signals += 3  # اتجاه هابط حقيقي
            elif price < ema_200:                       bear_signals += 2  # تحت EMA200 = خطر
            elif ema_50 < ema_200:                      bear_signals += 1  # death cross وشيك

        # 6. Reversal candle - شموع الانعكاس (weight 3)
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

            # شمعة دوجي أو شمعة ذيل طويل = انعكاس محتمل
            if   upper_shadow > candle_body * 2.5 and body_ratio < 0.3: bear_signals += 3
            elif lower_shadow > candle_body * 2.5 and body_ratio < 0.3: bull_signals += 3
            elif upper_shadow > candle_body * 1.5: bear_signals += 1
            elif lower_shadow > candle_body * 1.5: bull_signals += 1

        return {'symbol': symbol, 'bull': bull_signals, 'bear': bear_signals}

    def _aggregate_symbol_results(self, results: list, timeframe: str) -> dict:
        """تجميع نتائج العملات الثلاث لتحديد حالة الإطار الزمني"""
        total_bull = sum(p['bull'] for p in results)
        total_bear = sum(p['bear'] for p in results)
        total      = total_bull + total_bear

        if total == 0:
            return {'status': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No signals'}

        # الإجماع: يجب أن تتفق عملتان على الأقل
        bull_count = sum(1 for p in results if p['bull'] > p['bear'] + 2)
        bear_count = sum(1 for p in results if p['bear'] > p['bull'] + 2)
        
        if bull_count < 2 and bear_count < 2:
            details = ', '.join(
                f"{p['symbol'].split('/')[0]}(🟢{p['bull']}/🔴{p['bear']})"
                for p in results
            )
            return {
                'status': 'NEUTRAL',
                'confidence': 50,
                'bull_score': total_bull,
                'bear_score': total_bear,
                'reason'    : f'⚪ No consensus ({timeframe})',
                'details'   : details,
            }

        bull_pct = total_bull / total * 100
        bear_pct = total_bear / total * 100

        if   bull_pct >= 75: status, confidence, reason = 'STRONG_BULLISH', bull_pct, f'🟢🟢 Strong Bullish ({timeframe})'
        elif bull_pct >= 60: status, confidence, reason = 'BULLISH',        bull_pct, f'🟢 Bullish ({timeframe})'
        elif bear_pct >= 75: status, confidence, reason = 'STRONG_BEARISH', bear_pct, f'🔴🔴 Strong Bearish ({timeframe})'
        elif bear_pct >= 60: status, confidence, reason = 'BEARISH',        bear_pct, f'🔴 Bearish ({timeframe})'
        else:                status, confidence, reason = 'NEUTRAL',        50,       f'⚪ Neutral ({timeframe})'

        details = ', '.join(
            f"{p['symbol'].split('/')[0]}(🟢{p['bull']}/🔴{p['bear']})"
            for p in results
        )

        return {
            'status': status,
            'confidence': round(confidence, 1),
            'bull_score': total_bull,
            'bear_score': total_bear,
            'reason'    : reason,
            'details'   : details,
        }

    def _combine_timeframes(self, m15: dict, h1: dict, h4: dict) -> dict:
        """دمج نتائج الأطر الزمنية لتحديد وضع السوق الكلي"""
        m15_status = m15.get('status', 'NEUTRAL')
        h1_status  = h1.get('status',  'NEUTRAL')
        h4_status  = h4.get('status',  'NEUTRAL')

        is_fast_bear   = 'BEAR' in m15_status
        is_fast_bull   = 'BULL' in m15_status
        is_short_bull  = 'BULL' in h1_status
        is_short_bear  = 'BEAR' in h1_status
        is_medium_bull = 'BULL' in h4_status
        is_medium_bear = 'BEAR' in h4_status

        # ❌ فلتر الاتجاه: لو 15m هابط + 4h هابط = لا تشتري مهما كان 1h
        if is_fast_bear and is_medium_bear:
            return {'direction': 'BEARISH', 'strength': 'STRONG',
                    'confidence': max(fast['confidence'], medium['confidence']),
                    'reason': '🔴🔴 Bear Filter Active (15m + 4h Bearish — NO BUY)'}

        if   is_short_bull and is_medium_bull and is_fast_bull:
            return {'direction': 'BULLISH', 'strength': 'STRONG',
                    'confidence': max(h1['confidence'], h4['confidence']),
                    'reason': '🟢🟢🟢 Confirmed Bullish (15m + 1h + 4h)'}
        elif is_short_bull and is_medium_bull:
            return {'direction': 'BULLISH', 'strength': 'STRONG',
                    'confidence': max(h1['confidence'], h4['confidence']),
                    'reason': '🟢🟢 Confirmed Bullish (1h + 4h)'}
        elif is_short_bear and is_medium_bear:
            return {'direction': 'BEARISH', 'strength': 'STRONG',
                    'confidence': max(h1['confidence'], h4['confidence']),
                    'reason': '🔴🔴 Confirmed Bearish (1h + 4h)'}
        elif is_short_bull and is_medium_bear:
            # ✅ FIX 1: 4h الهابط يتفوق على 1h الصاعد — الارتداد مؤقت فقط
            return {'direction': 'BEARISH', 'strength': 'CAUTION',  'confidence': 55,
                    'reason': '⚠️ 1h Bullish but 4h Bearish → 4h wins (Dead-cat bounce risk)'}
        elif is_short_bear and is_medium_bull:
            return {'direction': 'MIXED',   'strength': 'RECOVERY', 'confidence': 55,
                    'reason': '⏳ Temp Dip in Bull Market (Wait for support)'}
        elif is_medium_bear:
            # 🔴 طالما أن فريم الـ 4 ساعات هابط، لا يمكن اعتبار السوق "عرضياً"؛ الاتجاه العام لا يزال سلبياً.
            return {'direction': 'BEARISH', 'strength': 'NORMAL', 'confidence': 60,
                    'reason': '🔴 4h Macro is still Bearish (Macro wins over noise)'}
        else:
            return {'direction': 'NEUTRAL', 'strength': 'NEUTRAL',  'confidence': 50,
                    'reason': '⚪ Market Unclear'}

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _get_quick_verification_df(self) -> Optional[pd.DataFrame]:
        """جلب DataFrame للتحقق السريع"""
        try:
            if not self.exchange:
                return None
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1h', limit=50)
            df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            if len(df) < 20:
                return None
            
            # إضافة المؤشرات الأساسية التي قد تحتاجها النماذج
            df['rsi'] = self._calculate_rsi(df['c'])
            df['volume_ratio'] = df['v'] / df['v'].rolling(20).mean()
            df['price_change'] = df['c'].pct_change() * 100
            
            return df
        except Exception as e:
            print(f"⚠️ Quick verification DF error: {e}")
            return None

    def _get_historical_status(self, hours_ago: float = 2) -> Optional[str]:
        """
        يقرأ macro_status المحفوظة في bot_settings (key=bot_status)
        ويرجع القيمة المحفوظة — تُستخدم للمقارنة قبل إرجاع BULL.
        الربط: advisor.db = your_database_storage_instance

        ✅ FIX 3: يستخدم 'timestamp' (unix) بدل 'time' (string) لتفادي
                  خطأ عبور منتصف الليل حين يصبح الفرق سالباً.
                  لو الداتابيز تحفظ 'time' فقط، نحسب التوافق بطريقة آمنة.
        """
        try:
            if not hasattr(self, 'db') or self.db is None:
                return None

            raw = self.db.load_setting('bot_status')
            if not raw:
                return None

            import json
            data = json.loads(raw)

            macro = data.get('macro_status', '')
            if not macro:
                return None

            max_age_secs = hours_ago * 3600 + 1800  # hours_ago + 30 دقيقة هامش

            # ── الطريقة الأولى: timestamp unix (الأفضل والأدق) ──────────────
            saved_ts = data.get('timestamp')
            if saved_ts:
                try:
                    diff_secs = time.time() - float(saved_ts)
                    if diff_secs < 0 or diff_secs > max_age_secs:
                        return None
                    return macro
                except Exception:
                    pass  # نكمل للطريقة الثانية

            # ── الطريقة الثانية: وقت النص "%H:%M:%S" (fallback آمن) ─────────
            # ✅ نعالج حالة عبور منتصف الليل بأخذ القيمة المطلقة أو إضافة يوم
            saved_time = data.get('time', '')
            if saved_time:
                try:
                    from datetime import datetime, timedelta
                    now      = datetime.now()
                    saved_dt = datetime.strptime(saved_time, "%H:%M:%S").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                    diff_secs = (now - saved_dt).total_seconds()

                    # لو الفرق سالب = تجاوزنا منتصف الليل → نضيف يوم للسجل
                    if diff_secs < 0:
                        saved_dt  += timedelta(days=1)
                        diff_secs  = (now - saved_dt).total_seconds()

                    if diff_secs < 0 or diff_secs > max_age_secs:
                        return None
                except Exception:
                    pass  # لو فشل تحليل الوقت نكمل بالقيمة كما هي

            return macro

        except Exception:
            return None

    def _empty_state(self) -> dict:
        return {
            '15m'     : {'status': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            '1h'      : {'status': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            '4h'      : {'status': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
            'combined': {'direction': 'NEUTRAL', 'strength': 'NEUTRAL', 'confidence': 50, 'reason': '⚪ No data'},
        }