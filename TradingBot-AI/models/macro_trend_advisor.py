"""
📈 Macro Trend Advisor - Real-time Market Regime Analysis

منطق القرار النهائي يعتمد على 3 بوابات يجب اجتيازها جميعاً للحكم بـ BULL:
    بوابة 1 — الإشارات الفنية      : 15m + 1h + 4h
    بوابة 2 — نماذج الذكاء (5)    : 3 من 5 على الأقل تقول BULL
    بوابة 3 — المستشارين الثابتين  : واحد على الأقل يوافق (MTF أو TED)

أي بوابة مغلقة = لا BULL. لا استثناء.
BEAR و NEUTRAL لا يحتاجان موافقة النماذج — الإشارات الفنية تكفي للهبوط.
"""

import time
import json
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

try:
    from dl_client_v2 import DeepLearningClientV2
    DL_CLIENT_AVAILABLE = True
except ImportError:
    DeepLearningClientV2 = None
    DL_CLIENT_AVAILABLE = False


class MacroTrendAdvisor:
    """
    حالة السوق الحقيقية.
    صاعد = صاعد فعلاً. هابط = هابط فعلاً. محايد = محايد فعلاً.
    """

    MACRO_SYMBOLS  = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
    CACHE_DURATION = 900    # 15 دقيقة بين كل تحليل
    RSI_PERIOD     = 14
    STABILITY_MINS = 30     # دقائق الاستقرار قبل تأكيد BULL

    def __init__(self, exchange=None, dl_client=None, storage=None):
        self.exchange  = exchange
        self.db        = storage
        self.dl_client = dl_client

        # ── نماذج الذكاء الاصطناعي ────────────────────────────────────────
        models_cache = getattr(self.dl_client, '_models', {}) if self.dl_client else {}
        self.volume_predictor     = models_cache.get('volume_pred')
        self.sentiment_analyzer   = models_cache.get('sentiment')
        self.liquidity_analyzer   = models_cache.get('liquidity')
        self.smart_money_tracker  = models_cache.get('smart_money')
        self.crypto_news_analyzer = models_cache.get('crypto_news')

        # ── المستشارين الثابتين ───────────────────────────────────────────
        try:
            from .multi_timeframe_analyzer import MultiTimeframeAnalyzer
            self._mtf_cls = MultiTimeframeAnalyzer
        except ImportError:
            self._mtf_cls = None

        try:
            from .trend_early_detector import TrendEarlyDetector
            self._ted_cls = TrendEarlyDetector
        except ImportError:
            self._ted_cls = None

        # ── الحالة الداخلية ───────────────────────────────────────────────
        self._last_status        : str   = '⚪ NEUTRAL'
        self._last_check_time    : float = 0.0
        self._last_analysis      : dict  = {}
        self._last_analysis_time : float = 0.0
        self._tf_cache           : dict  = {}
        self._display_info       : dict  = {}

        # فلتر الصبر
        self._is_currently_bull : bool           = False
        self._macro_start_time  : Optional[float] = None

    # ══════════════════════════════════════════════════════════════════════
    #  الواجهة الرئيسية
    # ══════════════════════════════════════════════════════════════════════

    def get_macro_status(self) -> str:
        """
        القرار النهائي لحالة السوق بعد اجتياز 3 بوابات.

        القيم الممكنة:
            🟢 BULL_MARKET   — صاعد قوي مؤكد (الثلاث بوابات مفتوحة + مستقر)
            🟢 MILD_BULL     — صاعد خفيف مؤكد (الثلاث بوابات مفتوحة + مستقر)
            🔴 BEAR_MARKET   — هابط قوي
            🔴 MILD_BEAR     — هابط خفيف أو تحذير
            ⚪ SIDEWAYS      — محايد أو إشارات متضاربة
            ⚪ STABILIZING   — إشارة صعود حقيقية لكن لم تستقر STABILITY_MINS دقيقة بعد
        """
        if not self.exchange:
            return '⚪ NEUTRAL'

        if time.time() - self._last_check_time < self.CACHE_DURATION:
            return self._last_status

        try:
            # ══ بوابة 1: الإشارات الفنية ══════════════════════════════════
            tech     = self._gate1_technical()
            tech_dir = tech['direction']  # BULLISH / BEARISH / NEUTRAL / MIXED
            tech_str = tech['strength']   # STRONG / NORMAL / CAUTION / WEAK / NEUTRAL

            # هابط؟ → ارجع فوراً، لا حاجة للنماذج
            if tech_dir == 'BEARISH':
                status = '🔴 BEAR_MARKET' if tech_str == 'STRONG' else '🔴 MILD_BEAR'
                self._reset_stability()
                return self._finalize(status, tech, None, None)

            # محايد أو مختلط؟ → ارجع فوراً
            if tech_dir not in ('BULLISH',):
                self._reset_stability()
                return self._finalize('⚪ SIDEWAYS', tech, None, None)

            # ══ بوابة 2: نماذج الذكاء الاصطناعي ══════════════════════════
            q_df  = self._get_features_df()
            gate2 = self._gate2_dl_models(q_df)

            if not gate2['approved']:
                # النماذج قالت لا — هذه الإشارة وهمية
                self._reset_stability()
                return self._finalize('⚪ SIDEWAYS', tech, gate2, None,
                                      note=f'🚫 DL رفض: {gate2["reason"]}')

            # ══ بوابة 3: المستشارين الثابتين ══════════════════════════════
            gate3 = self._gate3_advisors(q_df)

            if not gate3['approved']:
                # المستشارون قالوا لا — إشارة وهمية
                self._reset_stability()
                return self._finalize('⚪ SIDEWAYS', tech, gate2, gate3,
                                      note=f'🚫 Advisors رفضوا: {gate3["reason"]}')

            # ══ الثلاث بوابات مفتوحة → إشارة BULL حقيقية ════════════════
            raw_bull = '🟢 BULL_MARKET' if tech_str == 'STRONG' else '🟢 MILD_BULL'

            # تحفظ تاريخي: لو السوق كان هابطاً قبل ساعتين → نخفض إلى MILD_BULL
            historical = self._get_historical_status(hours_ago=2)
            if historical and 'BEAR' in historical:
                raw_bull = '🟢 MILD_BULL'

            # فلتر الصبر: الصعود لازم يستقر 30 دقيقة متواصلة
            final_status = self._apply_stability_filter(raw_bull)

            return self._finalize(final_status, tech, gate2, gate3)

        except Exception as e:
            print(f"⚠️ MacroTrendAdvisor error: {e}")
            return '⚪ NEUTRAL'

    def can_aim_high(self) -> bool:
        return 'BULL' in self.get_macro_status()

    def get_display_info(self) -> dict:
        return self._display_info or {
            'status': self._last_status, 'total_bull': 0, 'total_bear': 0, 'detail': ''
        }

    def invalidate_cache(self) -> None:
        self._last_check_time    = 0.0
        self._last_analysis_time = 0.0
        self._tf_cache.clear()

    def analyze_market_state(self) -> dict:
        """واجهة متوافقة — ترجع تحليل الأطر الزمنية"""
        if not self.exchange:
            return self._empty_state()
        if time.time() - self._last_analysis_time < 300:
            return self._last_analysis
        try:
            m15 = self._analyze_timeframe('15m', 48)
            h1  = self._analyze_timeframe('1h',  24)
            h4  = self._analyze_timeframe('4h',  24)
            combined = self._combine_timeframes(m15, h1, h4)
            result = {'15m': m15, '1h': h1, '4h': h4, 'combined': combined}
            self._last_analysis      = result
            self._last_analysis_time = time.time()
            return result
        except Exception as e:
            print(f"⚠️ analyze_market_state error: {e}")
            return self._empty_state()

    # ══════════════════════════════════════════════════════════════════════
    #  بوابة 1 — الإشارات الفنية
    # ══════════════════════════════════════════════════════════════════════

    def _gate1_technical(self) -> dict:
        """يحلل 15m + 1h + 4h ويرجع اتجاه السوق الفني"""
        m15 = self._analyze_timeframe('15m', 48)
        h1  = self._analyze_timeframe('1h',  24)
        h4  = self._analyze_timeframe('4h',  24)
        return self._combine_timeframes(m15, h1, h4)

    def _analyze_timeframe(self, timeframe: str, limit: int) -> dict:
        """تحليل إطار زمني واحد عبر العملات الثلاث مع كاش 5 دقائق"""
        cache = self._tf_cache.get(timeframe)
        if cache and (time.time() - cache['time'] < 300):
            return cache['data']

        results = []
        for symbol in self.MACRO_SYMBOLS:
            try:
                r = self._analyze_symbol(symbol, timeframe, limit)
                if r:
                    results.append(r)
            except Exception as e:
                print(f"⚠️ {symbol} {timeframe}: {e}")

        if not results:
            return {'status': 'NEUTRAL', 'confidence': 50,
                    'bull_score': 0, 'bear_score': 0, 'reason': '⚪ No data'}

        result = self._aggregate_results(results, timeframe)
        self._tf_cache[timeframe] = {'data': result, 'time': time.time()}
        return result

    def _analyze_symbol(self, symbol: str, timeframe: str, limit: int) -> Optional[dict]:
        """التحليل الفني الكامل لعملة واحدة — 7 مؤشرات"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df    = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])

        if len(df) < 11:
            return None

        bull = 0
        bear = 0

        # ── 1. اتجاه آخر 10 شموع (weight 4) ─────────────────────────────
        chg10 = (float(df['c'].iloc[-1]) - float(df['c'].iloc[-11])) / float(df['c'].iloc[-11]) * 100
        if   chg10 >  1.5: bull += 4
        elif chg10 >  0.5: bull += 2
        elif chg10 < -1.5: bear += 4
        elif chg10 < -0.5: bear += 2

        # ── 2. RSI (weight 3) ─────────────────────────────────────────────
        rsi = self._calc_rsi(df['c'])
        if   rsi > 75: bear += 3   # تشبع شرائي قوي
        elif rsi > 65: bear += 1   # تشبع شرائي خفيف
        elif rsi > 55: bull += 1   # زخم صاعد
        elif rsi < 30: bull += 3   # تشبع بيعي قوي
        elif rsi < 40: bull += 1   # تشبع بيعي خفيف

        # ── 3. Volume — فلتر الصعود الوهمي (weight 3 أو 8) ───────────────
        avg_vol   = float(df['v'].iloc[-20:].mean())
        last_vol  = float(df['v'].iloc[-1])
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        if   vol_ratio < 0.8 and chg10 > 0.5: bear += 8  # صعود بدون حجم = فخ مؤكد
        elif vol_ratio > 2.0 and chg10 > 0:   bull += 3  # صعود بحجم قوي = حقيقي
        elif vol_ratio > 2.0 and chg10 < 0:   bear += 3  # هبوط بحجم قوي = حقيقي
        elif vol_ratio < 0.5:                  bear += 1  # حجم ضعيف عموماً

        # ── 4. MACD هستوجرام (weight 2) ──────────────────────────────────
        macd  = df['c'].ewm(span=12).mean() - df['c'].ewm(span=26).mean()
        sig   = macd.ewm(span=9).mean()
        hist  = macd - sig
        h_cur = float(hist.iloc[-1])
        h_prv = float(hist.iloc[-2])

        if   h_cur > 0 and h_cur > h_prv: bull += 2
        elif h_cur > 0:                    bull += 1
        elif h_cur < 0 and h_cur < h_prv: bear += 2
        elif h_cur < 0:                    bear += 1

        # ── 5. EMA 9/21 — الزخم القصير (weight 1) ────────────────────────
        ema9  = float(df['c'].ewm(span=9).mean().iloc[-1])
        ema21 = float(df['c'].ewm(span=21).mean().iloc[-1])
        if ema9 > ema21: bull += 1
        else:            bear += 1

        # ── 6. EMA 50/200 — الاتجاه الكبير (weight 3) ────────────────────
        # الأهم: لو السعر تحت EMA200 = سوق هابط بغض النظر عن باقي الإشارات
        if len(df) >= 50:
            ema50 = float(df['c'].ewm(span=50, adjust=False).mean().iloc[-1])
            price = float(df['c'].iloc[-1])
            if len(df) >= 200:
                ema200 = float(df['c'].ewm(span=200, adjust=False).mean().iloc[-1])
                if   price > ema200 and ema50 > ema200: bull += 3
                elif price < ema200 and ema50 < ema200: bear += 3
                elif price < ema200:                    bear += 2
                elif ema50  < ema200:                   bear += 1
            else:
                if price > ema50: bull += 2
                else:             bear += 2

        # ── 7. شمعة الانعكاس (weight 1-3) ───────────────────────────────
        c  = float(df['c'].iloc[-1])
        o  = float(df['o'].iloc[-1])
        h  = float(df['h'].iloc[-1])
        l  = float(df['l'].iloc[-1])
        bd = abs(c - o)
        rg = h - l
        if rg > 0:
            upper = h - max(c, o)
            lower = min(c, o) - l
            ratio = bd / rg
            if   upper > bd * 2.5 and ratio < 0.3: bear += 3  # شمعة رفض قمة
            elif lower > bd * 2.5 and ratio < 0.3: bull += 3  # مطرقة
            elif upper > bd * 1.5:                  bear += 1
            elif lower > bd * 1.5:                  bull += 1

        return {'symbol': symbol, 'bull': bull, 'bear': bear}

    def _aggregate_results(self, results: list, timeframe: str) -> dict:
        """تجميع نتائج العملات الثلاث — يشترط إجماع عملتين على الأقل"""
        total_bull = sum(p['bull'] for p in results)
        total_bear = sum(p['bear'] for p in results)
        total      = total_bull + total_bear

        if total == 0:
            return {'status': 'NEUTRAL', 'confidence': 50,
                    'bull_score': 0, 'bear_score': 0, 'reason': '⚪ No signals'}

        bull_count = sum(1 for p in results if p['bull'] > p['bear'] + 2)
        bear_count = sum(1 for p in results if p['bear'] > p['bull'] + 2)

        if bull_count < 2 and bear_count < 2:
            return {'status': 'NEUTRAL', 'confidence': 50,
                    'bull_score': total_bull, 'bear_score': total_bear,
                    'reason': f'⚪ No consensus ({timeframe})'}

        bull_pct = total_bull / total * 100
        bear_pct = total_bear / total * 100

        if   bull_pct >= 75: status, conf, rsn = 'STRONG_BULLISH', bull_pct, f'🟢🟢 Strong Bullish ({timeframe})'
        elif bull_pct >= 60: status, conf, rsn = 'BULLISH',        bull_pct, f'🟢 Bullish ({timeframe})'
        elif bear_pct >= 75: status, conf, rsn = 'STRONG_BEARISH', bear_pct, f'🔴🔴 Strong Bearish ({timeframe})'
        elif bear_pct >= 60: status, conf, rsn = 'BEARISH',        bear_pct, f'🔴 Bearish ({timeframe})'
        else:                status, conf, rsn = 'NEUTRAL',        50,       f'⚪ Neutral ({timeframe})'

        return {'status': status, 'confidence': round(conf, 1),
                'bull_score': total_bull, 'bear_score': total_bear, 'reason': rsn}

    def _combine_timeframes(self, m15: dict, h1: dict, h4: dict) -> dict:
        """
        دمج الأطر الزمنية — قواعد الأولوية:
          4h يتفوق دائماً على الأطر الأصغر
          15m هابط + 4h هابط = لا شراء مهما كان 1h
          1h صاعد + 4h هابط = ارتداد وهمي، لا تشتري
        """
        m15s = m15.get('status', 'NEUTRAL')
        h1s  = h1.get('status',  'NEUTRAL')
        h4s  = h4.get('status',  'NEUTRAL')

        is_15m_bear  = 'BEAR' in m15s
        is_15m_bull  = 'BULL' in m15s
        is_1h_bull   = 'BULL' in h1s
        is_1h_bear   = 'BEAR' in h1s
        is_4h_bull   = 'BULL' in h4s
        is_4h_bear   = 'BEAR' in h4s
        is_4h_strong = 'STRONG' in h4s

        bs = m15.get('bull_score', 0) + h1.get('bull_score', 0) + h4.get('bull_score', 0)
        be = m15.get('bear_score', 0) + h1.get('bear_score', 0) + h4.get('bear_score', 0)

        # 🔴 الفلتر الأقوى: 15m هابط + 4h هابط = محظور الشراء
        if is_15m_bear and is_4h_bear:
            return {'direction': 'BEARISH', 'strength': 'STRONG',
                    'confidence': max(m15['confidence'], h4['confidence']),
                    'bull_score': bs, 'bear_score': be,
                    'reason': '🔴🔴 Bear Filter (15m+4h هابطان — لا شراء)'}

        # 🟢 الثلاثة صاعدة = تأكيد قوي
        if is_1h_bull and is_4h_bull and is_15m_bull:
            strength = 'STRONG' if is_4h_strong else 'NORMAL'
            return {'direction': 'BULLISH', 'strength': strength,
                    'confidence': max(h1['confidence'], h4['confidence']),
                    'bull_score': bs, 'bear_score': be,
                    'reason': '🟢🟢🟢 Confirmed Bullish (15m+1h+4h)'}

        # 🟢 1h + 4h صاعدان = تأكيد جيد
        if is_1h_bull and is_4h_bull:
            strength = 'STRONG' if is_4h_strong else 'NORMAL'
            return {'direction': 'BULLISH', 'strength': strength,
                    'confidence': max(h1['confidence'], h4['confidence']),
                    'bull_score': bs, 'bear_score': be,
                    'reason': '🟢🟢 Confirmed Bullish (1h+4h)'}

        # 🔴 1h + 4h هابطان
        if is_1h_bear and is_4h_bear:
            return {'direction': 'BEARISH', 'strength': 'STRONG',
                    'confidence': max(h1['confidence'], h4['confidence']),
                    'bull_score': bs, 'bear_score': be,
                    'reason': '🔴🔴 Confirmed Bearish (1h+4h)'}

        # ⚠️ 1h صاعد لكن 4h هابط = ارتداد مؤقت وهمي
        if is_1h_bull and is_4h_bear:
            return {'direction': 'BEARISH', 'strength': 'CAUTION', 'confidence': 58,
                    'bull_score': bs, 'bear_score': be,
                    'reason': '⚠️ 1h صاعد لكن 4h هابط — 4h يكسب (ارتداد وهمي محتمل)'}

        # ⏳ 1h هابط لكن 4h صاعد = تراجع مؤقت في سوق صاعد، انتظر
        if is_1h_bear and is_4h_bull:
            return {'direction': 'MIXED', 'strength': 'RECOVERY', 'confidence': 55,
                    'bull_score': bs, 'bear_score': be,
                    'reason': '⏳ تراجع مؤقت في سوق صاعد — انتظر الدعم'}

        # 4h هابط وحده = الاتجاه الكبير لا يزال سلبياً
        if is_4h_bear:
            return {'direction': 'BEARISH', 'strength': 'NORMAL', 'confidence': 60,
                    'bull_score': bs, 'bear_score': be,
                    'reason': '🔴 4h لا يزال هابطاً'}

        return {'direction': 'NEUTRAL', 'strength': 'NEUTRAL', 'confidence': 50,
                'bull_score': bs, 'bear_score': be, 'reason': '⚪ السوق غير واضح'}

    # ══════════════════════════════════════════════════════════════════════
    #  بوابة 2 — نماذج الذكاء الاصطناعي (5 نماذج)
    # ══════════════════════════════════════════════════════════════════════

    def _gate2_dl_models(self, q_df: Optional[pd.DataFrame]) -> dict:
        """
        يسأل الـ5 نماذج: هل السوق فعلاً صاعد؟
        الموافقة: 3 من 5 على الأقل (60%)
        نموذج غير متوفر أو أخطأ → يُتجاهل ولا يُحسب ضد أو مع
        إذا أقل من 3 نماذج متوفرة → مرفوض (السلامة أولاً)
        """
        if q_df is None:
            return {'approved': False, 'votes': 0, 'total': 0,
                    'reason': 'لا بيانات للتحقق من النماذج'}

        features = q_df.tail(1).drop(columns=['ts'], errors='ignore').values
        votes    = 0
        total    = 0
        details  = []

        # نموذج 1: حجم التداول — هل في ضغط شراء حقيقي؟
        if self.volume_predictor:
            try:
                score = float(self.volume_predictor.predict(features)[0])
                total += 1
                if score > 0.6:
                    votes += 1
                    details.append(f'Vol✅{score:.2f}')
                else:
                    details.append(f'Vol❌{score:.2f}')
            except Exception as e:
                print(f"⚠️ volume_predictor: {e}")

        # نموذج 2: المشاعر — هل مشاعر السوق إيجابية؟
        if self.sentiment_analyzer:
            try:
                score = float(self.sentiment_analyzer.predict(features)[0])
                total += 1
                if score > 0.5:
                    votes += 1
                    details.append(f'Sent✅{score:.2f}')
                else:
                    details.append(f'Sent❌{score:.2f}')
            except Exception as e:
                print(f"⚠️ sentiment_analyzer: {e}")

        # نموذج 3: السيولة — هل في سيولة كافية للصعود؟
        if self.liquidity_analyzer:
            try:
                score = float(self.liquidity_analyzer.predict(features)[0])
                total += 1
                if score > 0.5:
                    votes += 1
                    details.append(f'Liq✅{score:.2f}')
                else:
                    details.append(f'Liq❌{score:.2f}')
            except Exception as e:
                print(f"⚠️ liquidity_analyzer: {e}")

        # نموذج 4: الأموال الذكية — هل الكبار يشترون؟
        if self.smart_money_tracker:
            try:
                score = float(self.smart_money_tracker.predict(features)[0])
                total += 1
                if score > 0.5:
                    votes += 1
                    details.append(f'SM✅{score:.2f}')
                else:
                    details.append(f'SM❌{score:.2f}')
            except Exception as e:
                print(f"⚠️ smart_money_tracker: {e}")

        # نموذج 5: الأخبار — هل الأخبار مساعدة للصعود؟
        if self.crypto_news_analyzer:
            try:
                score = float(self.crypto_news_analyzer.predict(features)[0])
                total += 1
                if score > 0.5:
                    votes += 1
                    details.append(f'News✅{score:.2f}')
                else:
                    details.append(f'News❌{score:.2f}')
            except Exception as e:
                print(f"⚠️ crypto_news_analyzer: {e}")

        # الحكم: لازم 3 نماذج متوفرة كحد أدنى + 60% منها توافق
        if total < 3:
            return {'approved': False, 'votes': votes, 'total': total,
                    'reason': f'نماذج غير كافية ({total}/5 متوفرة)'}

        needed   = max(3, round(total * 0.6))
        approved = votes >= needed
        detail   = ' | '.join(details)
        reason   = f'{votes}/{total} وافقوا (يحتاج {needed}) [{detail}]'

        return {'approved': approved, 'votes': votes, 'total': total, 'reason': reason}

    # ══════════════════════════════════════════════════════════════════════
    #  بوابة 3 — المستشارين الثابتين (MTF + TED)
    # ══════════════════════════════════════════════════════════════════════

    def _gate3_advisors(self, q_df: Optional[pd.DataFrame]) -> dict:
        """
        يسأل المستشارين الثابتين: هل هذا صعود حقيقي؟
        الموافقة: واحد على الأقل يوافق
        كلاهما غير متوفر → مرفوض (السلامة أولاً)
        """
        if q_df is None:
            return {'approved': False, 'votes': 0, 'total': 0,
                    'reason': 'لا بيانات للمستشارين'}

        votes   = 0
        total   = 0
        details = []

        # المستشار 1: MultiTimeframeAnalyzer — تحليل القاع متعدد الأطر
        if self._mtf_cls:
            try:
                mtf     = self._mtf_cls()
                candles = q_df.to_dict('records')
                price   = float(q_df['c'].iloc[-1])
                res     = mtf.analyze_bottom(
                    candles_5m=None, candles_15m=None,
                    candles_1h=candles, current_price=price
                )
                total += 1
                conf   = res.get('confidence', 0)
                if conf > 60:
                    votes += 1
                    details.append(f'MTF✅(conf={conf}%)')
                else:
                    details.append(f'MTF❌(conf={conf}%)')
            except Exception as e:
                print(f"⚠️ MTF advisor: {e}")

        # المستشار 2: TrendEarlyDetector — كشف بداية الترند مبكراً
        if self._ted_cls:
            try:
                ted     = self._ted_cls()
                res     = ted.detect_trend_birth(q_df)
                total  += 1
                is_bull = (res.get('trend') == 'BULLISH' and res.get('confidence', 0) > 50)
                if is_bull:
                    votes += 1
                    details.append(f'TED✅(conf={res.get("confidence")}%)')
                else:
                    details.append(f'TED❌({res.get("trend")},{res.get("confidence")}%)')
            except Exception as e:
                print(f"⚠️ TED advisor: {e}")

        # الحكم: لازم مستشار واحد على الأقل يوافق
        if total == 0:
            return {'approved': False, 'votes': 0, 'total': 0,
                    'reason': 'لا مستشارين متوفرين'}

        approved = votes >= 1
        reason   = f'{votes}/{total} وافقوا [' + ' | '.join(details) + ']'

        return {'approved': approved, 'votes': votes, 'total': total, 'reason': reason}

    # ══════════════════════════════════════════════════════════════════════
    #  فلتر الصبر
    # ══════════════════════════════════════════════════════════════════════

    def _apply_stability_filter(self, raw_status: str) -> str:
        """
        الصعود لازم يستقر STABILITY_MINS دقيقة متواصلة بعد اجتياز الثلاث بوابات.
        أي انقطاع (تراجع أو رفض بوابة) يصفر العداد من الصفر.
        """
        if not self._is_currently_bull or self._macro_start_time is None:
            # بداية رصد استقرار جديد
            self._is_currently_bull = True
            self._macro_start_time  = time.time()

        elapsed = (time.time() - self._macro_start_time) / 60

        if elapsed < self.STABILITY_MINS:
            return f'⚪ STABILIZING ({int(elapsed)}/{self.STABILITY_MINS}m)'

        return raw_status

    def _reset_stability(self) -> None:
        """يصفر عداد الصبر عند أي إشارة سلبية أو رفض بوابة"""
        self._is_currently_bull = False
        self._macro_start_time  = None

    # ══════════════════════════════════════════════════════════════════════
    #  الإنهاء والحفظ
    # ══════════════════════════════════════════════════════════════════════

    def _finalize(self, status: str, tech: dict,
                  gate2: Optional[dict], gate3: Optional[dict],
                  note: str = '') -> str:
        """يحفظ الحالة النهائية ويطبع سجل واضح ويرجع القيمة"""

        g2 = f" | DL:{gate2['votes']}/{gate2['total']}"   if gate2 else ' | DL:—'
        g3 = f" | Adv:{gate3['votes']}/{gate3['total']}" if gate3 else ' | Adv:—'
        note_str = f' | {note}' if note else ''

        self._display_info = {
            'status'    : status,
            'total_bull': tech.get('bull_score', 0),
            'total_bear': tech.get('bear_score', 0),
            'detail'    : f"{tech.get('reason', '')}{g2}{g3}{note_str}".strip(),
        }

        self._last_status     = status
        self._last_check_time = time.time()

        #print(f"📊 Macro: {status} | Tech:{tech.get('reason','')}{g2}{g3}{note_str}")
        return status

    # ══════════════════════════════════════════════════════════════════════
    #  الأدوات المساعدة
    # ══════════════════════════════════════════════════════════════════════

    def _get_features_df(self) -> Optional[pd.DataFrame]:
        """يجلب BTC/USDT 1h ويضيف المؤشرات الأساسية اللازمة للنماذج"""
        try:
            if not self.exchange:
                return None
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1h', limit=50)
            df    = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            if len(df) < 20:
                return None
            df['rsi']          = self._calc_rsi(df['c'])
            df['volume_ratio'] = df['v'] / df['v'].rolling(20).mean()
            df['price_change'] = df['c'].pct_change() * 100
            return df
        except Exception as e:
            print(f"⚠️ _get_features_df: {e}")
            return None

    def _calc_rsi(self, prices: pd.Series) -> float:
        delta = prices.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(self.RSI_PERIOD).mean()
        rs    = gain / loss.replace(0, np.nan)
        val   = (100 - (100 / (1 + rs))).iloc[-1]
        return float(val) if not pd.isna(val) else 50.0

    def _get_historical_status(self, hours_ago: float = 2) -> Optional[str]:
        """يقرأ حالة السوق المحفوظة من الداتابيز للمقارنة التاريخية"""
        try:
            if not self.db:
                return None
            raw = self.db.load_setting('bot_status')
            if not raw:
                return None
            data  = json.loads(raw)
            macro = data.get('macro_status', '')
            if not macro:
                return None

            max_age = hours_ago * 3600 + 1800  # + 30 دقيقة هامش

            # الطريقة الأولى: timestamp unix (الأدق)
            saved_ts = data.get('timestamp')
            if saved_ts:
                diff = time.time() - float(saved_ts)
                return macro if 0 <= diff <= max_age else None

            # الطريقة الثانية: وقت نصي "%H:%M:%S" (fallback)
            saved_time = data.get('time', '')
            if saved_time:
                now      = datetime.now()
                saved_dt = datetime.strptime(saved_time, "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day)
                diff = (now - saved_dt).total_seconds()
                if diff < 0:  # تجاوز منتصف الليل
                    saved_dt += timedelta(days=1)
                    diff      = (now - saved_dt).total_seconds()
                return macro if 0 <= diff <= max_age else None

            return None
        except Exception:
            return None

    def _empty_state(self) -> dict:
        empty = {'status': 'NEUTRAL', 'confidence': 50,
                 'bull_score': 0, 'bear_score': 0, 'reason': '⚪ No data'}
        return {
            '15m'     : empty.copy(),
            '1h'      : empty.copy(),
            '4h'      : empty.copy(),
            'combined': {'direction': 'NEUTRAL', 'strength': 'NEUTRAL',
                         'confidence': 50, 'bull_score': 0, 'bear_score': 0,
                         'reason': '⚪ No data'},
        }
