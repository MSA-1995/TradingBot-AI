"""
📊 Technical Analysis Module
Handles RSI, MACD, Volume, Momentum calculations
"""

import pandas as pd
import ta
from datetime import datetime, timezone
import time
import numpy as np
from analysis_parts.market_intelligence import get_market_regime, check_flash_crash, get_time_analysis, get_time_multiplier
from integrations.news_analyzer import get_sentiment_data

from analysis_parts.market_data import (
    _fetch_ohlcv_cached, _impact_cache, _order_book_cache,
    get_market_data, get_ttl_hash,
)
from analysis_parts.patterns import analyze_peak, analyze_reversal
from analysis_parts.mtf import calculate_mtf_from_5m_data
from analysis_parts.liquidity import get_liquidity_metrics
from analysis_parts.psychology import detect_panic_greed












# ═══════════════════════════════════════════════════════════════
# الدوال المساعدة الجديدة لتحسين الأداء
# ═══════════════════════════════════════════════════════════════







# ═══════════════════════════════════════════════════════════════
def get_market_analysis(exchange, symbol, limit=120, external_client=None):
    """Get technical analysis for a symbol with multi-timeframe data"""
    analysis_start = time.time()
    try:
        # ─────────────────────────────────────────────
        # 1️⃣ جلب بيانات OHLCV (مع كاش)
        # ─────────────────────────────────────────────
        ohlcv_5m = _fetch_ohlcv_cached(exchange, symbol, '5m', f"{symbol}_5m", limit)
        if not ohlcv_5m or len(ohlcv_5m) < 20:
            print(f"⚠️ Not enough 5m data for {symbol}")
            return None
        
        ohlcv_15m = _fetch_ohlcv_cached(exchange, symbol, '15m', f'{symbol}_15m', 60)
        ohlcv_1h = _fetch_ohlcv_cached(exchange, symbol, '1h', f'{symbol}_1h', 24)
        ohlcv_4h = _fetch_ohlcv_cached(exchange, symbol, '4h', f'{symbol}_4h', 30)
        ohlcv_1d = _fetch_ohlcv_cached(exchange, symbol, '1d', f'{symbol}_1d', 14)

        # ─────────────────────────────────────────────
        # 2️⃣ بناء DataFrame الرئيسي (5m)
        # ─────────────────────────────────────────────
        df = pd.DataFrame(
            ohlcv_5m,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # ── EMA ──────────────────────────────────────
        df['ema_9']  = df['close'].ewm(span=9,  adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()

        ema_cross_series  = (
            (df['ema_9'] > df['ema_21']).astype(int) -
            (df['ema_9'] < df['ema_21']).astype(int)
        )
        df['ema_crossover'] = ema_cross_series

        # ── RSI ──────────────────────────────────────
        delta     = df['close'].diff()
        gain      = delta.clip(lower=0).rolling(14).mean()
        loss      = (-delta.clip(upper=0)).rolling(14).mean()
        rs        = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df.loc[(gain > 0) & (loss == 0), 'rsi'] = 100
        df.loc[(gain == 0) & (loss > 0), 'rsi'] = 0
        df.loc[(gain == 0) & (loss == 0), 'rsi'] = 50

        # ── MACD ─────────────────────────────────────
        ema_12              = df['close'].ewm(span=12, adjust=False).mean()
        ema_26              = df['close'].ewm(span=26, adjust=False).mean()
        df['macd']          = ema_12 - ema_26
        df['macd_signal']   = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_diff']     = df['macd'] - df['macd_signal']
        df['macd_histogram']= df['macd_diff']
        df['macd_diff_pct']  = (df['macd_diff'] / df['close'].replace(0, 1)) * 100

        # ── ATR ──────────────────────────────────────
        tr        = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift()).abs(),
            (df['low']  - df['close'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        # ── Volume ───────────────────────────────────
        df['volume_sma']   = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma'].replace(0, 1)
        vol_trend_val      = df['volume_ratio'].rolling(5).mean().iloc[-1] - 1.0
        df['volume_trend'] = vol_trend_val

        # ── Price Change ─────────────────────────────
        df['price_change']    = df['close'].pct_change() * 100
        df['price_change_1h'] = df['close'].pct_change(12) * 100   # 12 x 5m = 1h

        # ── Noise / Fake Break ───────────────────────
        df['is_noise']   = df['atr'] > df['close'] * 0.005
        df['fake_break'] = (
            (df['high'] > df['high'].shift(1)) &
            (df['close'] < df['high'].shift(1))
        )

        # ─────────────────────────────────────────────
        # 3️⃣ latest (آخر شمعة)
        # ─────────────────────────────────────────────
        def _safe(val, default=0.0):
            try:
                return float(val) if not pd.isna(val) else default
            except Exception:
                return default

        lr     = df.iloc[-1]   # last row
        latest = {
            'close'          : _safe(lr['close']),
            'open'           : _safe(lr['open']),
            'high'           : _safe(lr['high']),
            'low'            : _safe(lr['low']),
            'volume'         : _safe(lr['volume']),
            'rsi'            : _safe(lr['rsi'],            50.0),
            'macd'           : _safe(lr['macd'],           0.0),
            'macd_signal'    : _safe(lr['macd_signal'],    0.0),
            'macd_diff'      : _safe(lr['macd_diff'],      0.0),
            'macd_diff_pct'  : _safe(lr['macd_diff_pct'],  0.0),
            'atr'            : _safe(lr['atr'],            0.0),
            'ema_9'          : _safe(lr['ema_9'],          _safe(lr['close'])),
            'ema_21'         : _safe(lr['ema_21'],         _safe(lr['close'])),
            'ema_crossover'  : int(_safe(lr['ema_crossover'], 0)),
            'volume_sma'     : _safe(lr['volume_sma'],    _safe(lr['volume'])),
            'volume_ratio'   : _safe(lr['volume_ratio'],  1.0),
            'volume_trend'   : _safe(vol_trend_val,       0.0),
            'price_change'   : _safe(lr['price_change'],  0.0),
            'price_change_1h': _safe(lr['price_change_1h'], 0.0),
            'is_noise'       : bool(lr['is_noise']),
            'fake_break'     : bool(lr['fake_break']),
        }

        # ─────────────────────────────────────────────
        # 4️⃣ Candles للـ UI
        # ─────────────────────────────────────────────
        candles    = df[['timestamp','open','high','low','close','volume']].tail(50).to_dict('records')
        candles_5m = candles

        candles_15m = []
        if ohlcv_15m and len(ohlcv_15m) > 0:
            df_15m = pd.DataFrame(ohlcv_15m, columns=['timestamp','open','high','low','close','volume'])
            df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            candles_15m = df_15m[['timestamp','open','high','low','close','volume']].tail(50).to_dict('records')

        candles_1h = []
        df_1h_ohlcv = None
        if ohlcv_1h and len(ohlcv_1h) > 0:
            df_1h_ohlcv = pd.DataFrame(ohlcv_1h, columns=['timestamp','open','high','low','close','volume'])
            df_1h_ohlcv['timestamp'] = pd.to_datetime(df_1h_ohlcv['timestamp'], unit='ms')
            candles_1h = df_1h_ohlcv[['timestamp','open','high','low','close','volume']].tail(24).to_dict('records')

        # ─────────────────────────────────────────────
        # 5️⃣ High / Low 24h
        # ─────────────────────────────────────────────
        df_24h   = df.tail(288)   # 288 x 5m = 24h
        high_24h = float(df_24h['high'].max())
        low_24h  = float(df_24h['low'].min())

        # ─────────────────────────────────────────────
        # 6️⃣ BTC / ETH / BNB تغيرات السوق
        # ─────────────────────────────────────────────
        market_data   = get_market_data(exchange, ttl_hash=get_ttl_hash())
        btc_change_1h = market_data.get('BTC/USDT', 0.0)
        eth_change_1h = market_data.get('ETH/USDT', 0.0)
        bnb_change_1h = market_data.get('BNB/USDT', 0.0)

        # ─────────────────────────────────────────────
        # 7️⃣ Order Book
        # ─────────────────────────────────────────────
        order_book     = {'bids': [], 'asks': []}
        bid_ask_spread = 0.0
        average_spread = 0.001
        try:
            _ob_ts = _order_book_cache.get(symbol, {}).get('timestamp', 0)
            if __import__('time').time() - _ob_ts < 60:
                order_book = _order_book_cache[symbol]['data']
            else:
                order_book = exchange.fetch_order_book(symbol, limit=20)
                _order_book_cache[symbol] = {'data': order_book, 'timestamp': __import__('time').time()}
            best_bid   = order_book['bids'][0][0] if order_book.get('bids') else latest['close']
            best_ask   = order_book['asks'][0][0] if order_book.get('asks') else latest['close']
            bid_ask_spread = (best_ask - best_bid) / best_bid * 100 if best_bid > 0 else 0.0
            average_spread = bid_ask_spread if bid_ask_spread > 0 else 0.001
        except Exception as e:
            print(f"⚠️ Order book error {symbol}: {e}")

        # ─────────────────────────────────────────────
        # 8️⃣ MTF Analysis
        # ─────────────────────────────────────────────
        try:
            mtf_analysis = calculate_mtf_from_5m_data(df)
        except Exception:
            mtf_analysis = {'trend': 'neutral', 'scores': {}, 'total': 0}

        # ─────────────────────────────────────────────
        # 9️⃣ Market Regime
        # ─────────────────────────────────────────────
        try:
            market_regime = get_market_regime(df)
        except Exception:
            atr_pct       = latest['atr'] / latest['close'] * 100 if latest['close'] > 0 else 0
            market_regime = (
                'high_volatility' if atr_pct > 2.0
                else 'low_volatility' if atr_pct < 0.5
                else 'normal'
            )

        # ─────────────────────────────────────────────
        # 🔟 Flash Crash Protection
        # ─────────────────────────────────────────────
        try:
            flash_crash_protection = check_flash_crash(df)
        except Exception:
            flash_crash_protection = {
                'triggered': latest['price_change'] < -3.0,
                'drop_pct' : latest['price_change']
            }

        # ─────────────────────────────────────────────
        # 1️⃣1️⃣ Time Analysis
        # ─────────────────────────────────────────────
        try:
            time_analysis = get_time_analysis()
        except Exception:
            now           = datetime.now(timezone.utc)
            time_analysis = {
                'hour'       : now.hour,
                'is_weekend' : now.weekday() >= 5,
                'session'    : (
                    'asia'    if 0  <= now.hour < 8
                    else 'europe' if 8  <= now.hour < 14
                    else 'us'
                )
            }

        # ─────────────────────────────────────────────
        # 1️⃣2️⃣ Liquidity Metrics
        # ─────────────────────────────────────────────
        try:
            liquidity_metrics = get_liquidity_metrics(
                exchange, symbol, df_5m=df, order_book=order_book
            )
        except Exception:
            liquidity_metrics = {
                'depth_ratio': 1.0, 'spread_percent': 0.1,
                'bid_depth': 0, 'ask_depth': 0,
                'liquidity_score': 50, 'price_impact': 0.5,
                'volume_consistency': 50
            }

        # ─────────────────────────────────────────────
        # 1️⃣3️⃣ Reversal / Peak / Price Drop
        # ─────────────────────────────────────────────
        try:
            reversal_analysis = analyze_reversal(df, latest['rsi'])
        except Exception:
            reversal_analysis = {'confidence': 0, 'candle_signal': False, 'reasons': []}

        try:
            peak_analysis = analyze_peak(df, latest['rsi'])
        except Exception:
            peak_analysis = {'confidence': 0, 'candle_signal': False, 'reasons': []}

        price_drop = max(0.0, (high_24h - latest['close']) / high_24h * 100) if high_24h > 0 else 0.0

        # ─────────────────────────────────────────────
        # 1️⃣4️⃣ Optimism Penalty
        # ─────────────────────────────────────────────
        opt_penalty = 0.0
        try:
            time_mult = get_time_multiplier()
            if latest['rsi'] > 70 and latest['price_change'] > 2:
                opt_penalty = (latest['rsi'] - 70) * 0.5 * time_mult
        except Exception:
            pass

        # ─────────────────────────────────────────────
        # 1️⃣5️⃣ External Impact
        # ─────────────────────────────────────────────
        external_impact = {'score': 50, 'sentiment': 'Neutral', 'fear_greed_value': 50}
        if external_client:
            try:
                external_impact = external_client.analyze_impact(symbol)
            except Exception as e:
                print(f"⚠️ External impact error: {e}")
        else:
            # الجديد ✅
            try:
                from integrations.external_apis import get_global_external_client
                _ic = _impact_cache.get(symbol, {})
                if __import__('time').time() - _ic.get('ts', 0) < 300:
                    external_impact = _ic['data']
                else:
                    _ec = get_global_external_client()
                    external_impact = _ec.analyze_impact(symbol)
                    _impact_cache[symbol] = {'data': external_impact, 'ts': __import__('time').time()}
            except Exception as e:
                print(f'⚠️ External direct error: {e}')
        try:
            sentiment_data = get_sentiment_data(
                symbol,
                {'close': latest['close'], 'rsi': latest['rsi']}
            )
        except Exception:
            sentiment_data = {
                'fear_greed_index'   : 50,
                'positive_news_count': 0,
                'negative_news_count': 0,
            }
        # ═════════════════════════════════════════════
        # 1️⃣7️⃣ بناء analysis_dict
        # ═════════════════════════════════════════════
        analysis_dict = {
            'relative_strength_btc'  : latest['price_change'] - btc_change_1h,
            'liquidity_trap'         : (latest['volume_ratio'] > 3.0 and abs(latest['price_change']) < 0.5),
            'liquidity_sweep'        : (latest['low'] <= low_24h * 1.005 and latest['price_change'] > 1.0 and latest['volume_ratio'] > 2.0),
            'candles'     : candles,
            'candles_5m'  : candles_5m,
            'candles_15m' : candles_15m,
            'candles_1h'  : candles_1h,
            'candles_4h'  : ohlcv_4h,
            'candles_1d'  : ohlcv_1d,
            'rsi'             : latest['rsi'],
            'macd'            : latest['macd'],
            'macd_signal'     : latest['macd_signal'],
            'macd_diff'       : latest['macd_diff'],
            'macd_diff_pct'   : latest['macd_diff_pct'],
            'latest'          : latest,
            'volume'          : latest['volume'],
            'volume_sma'      : latest['volume_sma'],
            'volume_ratio'    : latest['volume_ratio'],
            'price_momentum'  : latest['price_change'],
            'close'           : latest['close'],
            'high'            : latest['high'],
            'low'             : latest['low'],
            'mtf'             : mtf_analysis,
            'market_regime'   : market_regime,
            'flash_crash_protection': flash_crash_protection,
            'time_analysis'   : time_analysis,
            'atr'             : latest['atr'],
            'ema_9'           : latest['ema_9'],
            'ema_21'          : latest['ema_21'],
            'ema_crossover'   : latest['ema_crossover'],
            'bid_ask_spread'  : bid_ask_spread,
            'volume_trend'    : latest['volume_trend'],
            'price_change_1h' : latest['price_change_1h'],
            'reversal'        : reversal_analysis,
            'peak'            : peak_analysis,
            'price_drop'      : price_drop,
            'liquidity_metrics': liquidity_metrics,
            **liquidity_metrics,
            'atr_value'            : latest['atr'],
            'optimism_penalty'     : opt_penalty,
            'psychological_analysis': f"Panic:{detect_panic_greed(latest)['panic_score']:.1f}, RSI:{latest['rsi']:.1f}",
            'btc_change_1h'    : btc_change_1h,
            'panic_greed'      : detect_panic_greed(latest),
            'eth_change_1h'    : eth_change_1h,
            'bnb_change_1h'    : bnb_change_1h,
            'high_24h'         : high_24h,
            'low_24h'          : low_24h,
            'is_noise'         : latest['is_noise'],
            'fake_break'       : latest['fake_break'],
            'external_impact'  : external_impact,
            'external_score'   : external_impact.get('score', 50),
            'order_book'       : order_book,
            'average_spread'   : average_spread,
            **sentiment_data,
        }

        # ─────────────────────────────────────────────
        # Fix 2: sentiment.fear_greed
        # ─────────────────────────────────────────────
        fear_greed_value = (
            sentiment_data.get('fear_greed_index')
            or sentiment_data.get('fear_greed')
            or 50
        )

        if fear_greed_value == 50:
            fng_val = external_impact.get('fear_greed_value')
            if fng_val and fng_val != 50:
                fear_greed_value = fng_val
            # ✅ لا نستدعي API جديد - نأخذ من external_impact مباشرة
            # لأنه يستدعي get_market_sentiment_global بالفعل داخل analyze_impact

        analysis_dict['sentiment'] = {'fear_greed': fear_greed_value}

        # ─────────────────────────────────────────────
        # Fix 3: market_intelligence (UPGRADED - uses MarketRegimeDetector)
        # ─────────────────────────────────────────────
        try:
            _regime = market_regime if isinstance(market_regime, dict) else {}
            _regime_name = _regime.get('regime', 'RANGING')
            _advice = _regime.get('trading_advice', {}) if isinstance(_regime.get('trading_advice'), dict) else {}
            
            # تم تحييد صلاحية هذا الموديول في تقييم إيجابية السوق
            # القرار الآن مركزي في meta_buy بناءً على MacroTrendAdvisor فقط
            analysis_dict['market_intelligence'] = {
                'bullish_score': 0, 
                'bearish_score': 0,
                'regime': _regime_name,
                'trend': _regime.get('trend_strength', 'neutral'),
                'adx': _regime.get('adx', 20),
                'can_trade': _advice.get('can_trade', True),
                'position_size_mult': _advice.get('position_size', 1.0),
            }
        except Exception:
            analysis_dict['market_intelligence'] = {
                'bullish_score': max(0, min(100, 50 + btc_change_1h * 10)),
                'bearish_score': max(0, min(100, 50 - btc_change_1h * 10)),
            }

        # ─────────────────────────────────────────────
        # Fix 4: external_signal
        # ─────────────────────────────────────────────
        ext_score = external_impact.get('score', 50)
        analysis_dict['external_signal'] = {
            'bullish': 1 if ext_score > 65 else 0,
            'bearish': 1 if ext_score < 35 else 0,
        }

        # ─────────────────────────────────────────────
        # Fix 5: news
        # ─────────────────────────────────────────────
        analysis_dict['news'] = {
            'positive': sentiment_data.get('positive_news_count', 0),
            'negative': sentiment_data.get('negative_news_count', 0),
        }

        # ═════════════════════════════════════════════
        # الأعمدة الإضافية
        # ═════════════════════════════════════════════
        bids_volume  = sum(float(l[1]) for l in order_book.get('bids', [])[:10])
        asks_volume  = sum(float(l[1]) for l in order_book.get('asks', [])[:10])
        total_vol_ob = bids_volume + asks_volume

        analysis_dict['order_book_imbalance'] = (
            (bids_volume - asks_volume) / max(total_vol_ob, 1) if total_vol_ob > 0 else 0
        )
        analysis_dict['spread_volatility'] = (
            abs(bid_ask_spread - average_spread) / max(average_spread, 0.0001)
        )
        analysis_dict['depth_at_1pct'] = sum(
            float(l[1])
            for l in order_book.get('bids', []) + order_book.get('asks', [])
            if abs(float(l[0]) - latest['close']) / latest['close'] <= 0.01
        )
        analysis_dict['market_impact_score'] = min(latest['volume_ratio'] / 10, 1.0)
        analysis_dict['liquidity_trends'] = (
            1  if latest['volume_ratio'] > 1.5 and analysis_dict['spread_volatility'] < 0.5
            else -1 if latest['volume_ratio'] < 0.7 or analysis_dict['spread_volatility'] > 1.0
            else 0
        )

        # Risk
        analysis_dict['volatility_risk_score']  = (latest['atr'] / latest['close']) * 100 if latest['close'] > 0 else 0
        analysis_dict['correlation_risk']        = abs(btc_change_1h) / 5.0
        analysis_dict['gap_risk_score']          = abs(latest['high'] - latest['low']) / latest['close'] * 100 if latest['close'] > 0 else 0
        analysis_dict['black_swan_probability']  = 1.0 if abs(latest['price_change_1h']) > 5 else abs(latest['price_change_1h']) / 5.0
        analysis_dict['behavioral_risk']         = max(0, 1.0 - latest['volume_ratio'])
        analysis_dict['systemic_risk']           = abs(eth_change_1h) / 10.0

        # Exit
        analysis_dict['profit_optimization_score'] = max(0, (latest['rsi'] - 50) / 30)
        analysis_dict['time_decay_signals']         = 0.3 + (latest['rsi'] / 200)
        analysis_dict['opportunity_cost_exits']     = abs(min(0, latest['macd_diff'])) * 100
        analysis_dict['market_condition_exits']     = btc_change_1h / 10.0 if btc_change_1h < 0 else 0.0

        # Pattern
        analysis_dict['harmonic_patterns_score'] = abs(latest['price_change_1h']) / 2.0
        analysis_dict['elliott_wave_signals']    = float(latest['ema_crossover'])
        analysis_dict['fractal_patterns']        = latest['volume_ratio'] / 3.0
        analysis_dict['cycle_patterns']          = abs(50 - latest['rsi']) / 50.0
        analysis_dict['momentum_patterns']       = abs(latest['price_change']) / 3.0

        # Smart Money
        analysis_dict['whale_wallet_changes']       = latest['volume_ratio'] / 2.0
        analysis_dict['institutional_accumulation'] = (
            1.0 if bid_ask_spread < 0.05
            else 0.5 if bid_ask_spread < 0.1
            else 0.0
        )
        analysis_dict['smart_money_ratio']    = min(latest['volume_ratio'] / 2.0, 1.0)
        analysis_dict['exchange_whale_flows'] = 1.0 if latest['volume_ratio'] < 0.3 else 0.0

        # Anomaly
        analysis_dict['statistical_outliers'] = abs(latest['close'] - latest['ema_21']) / latest['close'] * 100
        analysis_dict['pattern_anomalies']    = abs(latest['macd_diff'] * latest['price_change'])
        analysis_dict['behavioral_anomalies'] = max(0, latest['volume_ratio'] - 2.0)
        analysis_dict['volume_anomalies']     = abs(1.0 - latest['volume_ratio'])

        # Chart pattern features
        volume_signal = min(max((latest['volume_ratio'] - 1.0) / 2.0, 0.0), 1.0)
        macd_signal   = min(abs(latest['macd_diff_pct']) / 0.5, 1.0)
        temporal_sig  = min(abs(latest['price_change_1h']) / 5.0, 1.0)
        analysis_dict['attention_mechanism_score'] = volume_signal
        analysis_dict['multi_scale_features']      = macd_signal
        analysis_dict['temporal_features']         = temporal_sig

        rsi_buy_signal  = max(0.0, min((45.0 - latest['rsi']) / 25.0, 1.0))
        rsi_sell_signal = max(0.0, min((latest['rsi'] - 55.0) / 25.0, 1.0))
        macd_buy_signal = max(0.0, min(latest['macd_diff_pct'] / 0.5, 1.0))
        macd_sell_signal = max(0.0, min(-latest['macd_diff_pct'] / 0.5, 1.0))
        momentum_buy_signal = max(0.0, min(latest['price_change_1h'] / 5.0, 1.0))
        momentum_sell_signal = max(0.0, min(-latest['price_change_1h'] / 5.0, 1.0))
        ema_buy_signal = 1.0 if latest['ema_crossover'] > 0 else 0.0
        ema_sell_signal = 1.0 if latest['ema_crossover'] < 0 else 0.0

        analysis_dict['chart_cnn_buy_score'] = round(min(100.0, (
            volume_signal * 25
            + rsi_buy_signal * 25
            + macd_buy_signal * 20
            + momentum_buy_signal * 20
            + ema_buy_signal * 10
        )), 1)
        analysis_dict['chart_cnn_sell_score'] = round(min(100.0, (
            volume_signal * 25
            + rsi_sell_signal * 25
            + macd_sell_signal * 20
            + momentum_sell_signal * 20
            + ema_sell_signal * 10
        )), 1)
        analysis_dict['chart_cnn_score'] = max(
            analysis_dict['chart_cnn_buy_score'],
            analysis_dict['chart_cnn_sell_score']
        )

        # Volume
        analysis_dict['volume_trend_strength'] = latest['volume_trend']
        analysis_dict['volume_volatility']     = (
            abs(latest['volume'] - latest['volume_sma'])
            / max(latest['volume_sma'], 1)
        )
        analysis_dict['volume_momentum']    = min(latest['volume_ratio'] / 2.0, 1.0)
        analysis_dict['volume_seasonality'] = 0.5
        analysis_dict['volume_correlation'] = min(
            abs(latest['price_change_1h'])
            / max(latest['volume_ratio'], 0.1)
            / 10.0,
            1.0
        )

        # Meta
        analysis_dict['dynamic_consultant_weights'] = 0.7
        analysis_dict['uncertainty_quantification'] = abs(50 - latest['rsi']) / 50.0
        analysis_dict['context_aware_score']        = 1.0 - abs(btc_change_1h) / 10.0

        # Whale Confidence
        v_ratio      = latest['volume_ratio']
        ob_imbalance = analysis_dict.get('order_book_imbalance', 0)
        price_change = latest['price_change']
        rsi_val      = latest['rsi']

        w_base   = (price_change * 10) if abs(price_change) > 0.1 else 0
        w_volume = (v_ratio - 1.0) * 5
        w_rsi    = (rsi_val - 50) / 2
        w_ob     = (ob_imbalance * 10) if abs(ob_imbalance) > 0.1 else 0

        analysis_dict['whale_confidence'] = round(
            max(-25, min(25, w_base + w_volume + w_rsi + w_ob)), 2
        )

        elapsed = time.time() - analysis_start
        #print(f"✅ Analysis done {symbol} in {elapsed:.2f}s")

        return analysis_dict

    except Exception as e:
        print(f"❌ Analysis error {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════







