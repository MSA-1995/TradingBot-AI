"""
🔴 Sell Handler
Processes SELL results and handles AI learning after a successful sell.
"""

import sys
import os

# إضافة مسار src للاستيراد
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from datetime import datetime
from colorama import Fore, Style
import json

from utils import execute_sell, calculate_sell_value
from notifications import send_sell_notification


def process_sell(result, exchange, ctx):
    """
    Process a SELL action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              exit_strategy, pattern_recognizer, sell_cooldown,
              meta, advisor_manager
    Returns: True if sell executed successfully, False otherwise.
    """
    symbol          = result['symbol']
    SYMBOLS_DATA    = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage         = ctx['storage']
    advisor_manager = ctx.get('advisor_manager')
    meta            = ctx.get('meta')
    sell_cooldown   = ctx.get('sell_cooldown', {})
    dl_client       = ctx.get('dl_client')

    print(f"{Fore.RED}🔴 SELL {symbol} | {result['reason']} | Profit: {result['profit']:+.2f}%{Style.RESET_ALL}")

    sell_result = execute_sell(exchange, symbol, result['amount'], result['reason'])
    if not sell_result['success']:
        return False

    sell_cooldown[symbol] = datetime.now()

    sell_value = calculate_sell_value(result['amount'], result['price'])
    send_sell_notification(
        symbol, result['amount'], result['price'],
        sell_value, result['profit'], result['reason']
    )

    position = result['position']

    # AI Learning with instant evaluation
    try:
        hours_held = 24
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str:
                buy_time = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except:
            pass

        profit = result.get('profit', 0)
        
        # تقييم فوري للصفقة
        if profit >= 1.5:
            trade_quality = 'GREAT'
        elif profit >= 0.8:
            trade_quality = 'GOOD'
        elif profit >= 0.3:
            trade_quality = 'OK'
        elif profit >= -0.5:
            trade_quality = 'RISKY'
        else:
            trade_quality = 'TRAP'

        # جلب أصوات المستشارين للبيع (من result) والشراء (من position)
        sell_votes = result.get('sell_votes', {})
        buy_votes = position.get('advisor_votes', {})
        
        # تعريف analysis مبكراً لاستخدامه في جلب sentiment
        analysis = result.get('analysis', {}) or {}

        # جلب بيانات الأخبار والسيولة لحفظها في بيانات الصفقة
        news_data = {}
        sentiment_data = {}
        liquidity_data = {}
        real_sentiment_score = 0.0
        real_panic_score = 0.0
        try:
            news_analyzer = advisor_manager.get('NewsAnalyzer') if advisor_manager else None
            if news_analyzer:
                # محاولة بـ 24 ساعة أولاً، بعدين 48 ساعة، بعدين 72 ساعة
                news_sentiment = None
                for hours in [24, 48, 72]:
                    news_sentiment = news_analyzer.get_news_sentiment(symbol, hours=hours)
                    if news_sentiment:
                        break
                
                if news_sentiment:
                    news_data = {
                        'positive': news_sentiment.get('positive', 0),
                        'negative': news_sentiment.get('negative', 0),
                        'neutral': news_sentiment.get('neutral', 0),
                        'total': news_sentiment.get('total', 0),
                        'news_score': news_sentiment.get('news_score', 0)
                    }
                    sentiment_data = {
                        'news_sentiment': news_sentiment.get('news_score', 0)
                    }

            # جلب Fear & Greed Index + panic_score الحقيقيين من API
            try:
                from news_analyzer import get_sentiment_data
                market_sentiment = get_sentiment_data(symbol, analysis)
                real_sentiment_score = market_sentiment.get('sentiment_score', 0.0)
                real_panic_score = market_sentiment.get('panic_score', 0.0)
            except Exception as e:
                print(f"⚠️ get_sentiment_data error: {e}")
                # fallback: panic_score من التحليل مباشرة إن وُجد
                real_panic_score = float(analysis.get('panic_greed', {}).get('panic_score', 0) or 0)

        except:
            pass

        # جلب بيانات السيولة من الصفقة
        try:
            ai_data = position.get('ai_data', {})
            if ai_data:
                liquidity_data = {
                    'depth_ratio': ai_data.get('depth_ratio', 1.0),
                    'spread_percent': ai_data.get('spread_percent', 0.1),
                    'liquidity_score': ai_data.get('liquidity_score', 50),
                    'price_impact': ai_data.get('price_impact', 0.5),
                    'volume_consistency': ai_data.get('volume_consistency', 50)
                }
        except:
            pass

        # حفظ بيانات الصفقة
        trade_data = {
            'symbol': symbol,
            'action': 'sell',
            'profit_percent': profit,
            'trade_quality': trade_quality,
            'sell_reason': result.get('reason'),
            'hours_held': hours_held,
            'sell_votes': sell_votes,
            'buy_votes': buy_votes,
            'data': {
                'buy_price': position.get('buy_price'),
                'sell_price': result.get('price'),
                'ai_data': position.get('ai_data', {}),
                'news': news_data,
                'sentiment': sentiment_data,
                'liquidity': liquidity_data
            }
        }

        # حساب الميزات المتقدمة للتدريب - GET REAL ANALYSIS FROM CTX!!!
        analysis_data = ctx.get('last_analysis', {}) if 'last_analysis' in ctx else result.get('analysis', {})
        candles = result.get('candles', analysis_data.get('candles', []))
        price = analysis_data.get('close', 1) or 1
        volume_ratio = analysis_data.get('volume_ratio', 1)
        rsi = analysis_data.get('rsi', 50)
        macd_diff = analysis_data.get('macd_diff', 0)
        atr = analysis_data.get('atr', 0)

        # Helper to safely convert to float
        def safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        # Liquidity Features - FROM REAL ANALYSIS DATA NOW!
        order_book = analysis_data.get('order_book', {})
        bids_volume = sum(float(level[1]) for level in order_book.get('bids', [])[:10])
        asks_volume = sum(float(level[1]) for level in order_book.get('asks', [])[:10])
        total_volume = bids_volume + asks_volume
        order_book_imbalance = (bids_volume - asks_volume) / max(total_volume, 1) if total_volume > 0 else 0

        spread = analysis_data.get('bid_ask_spread', 0.001)
        avg_spread = analysis_data.get('average_spread', 0.001)
        spread_volatility = abs(spread - avg_spread) / max(avg_spread, 0.0001)

        depth_at_1pct = 0
        for level in order_book.get('bids', []):
            if abs(float(level[0]) - price) / price <= 0.01:
                depth_at_1pct += float(level[1])
        for level in order_book.get('asks', []):
            if abs(float(level[0]) - price) / price <= 0.01:
                depth_at_1pct += float(level[1])

        market_impact_score = min(volume_ratio / 10, 1.0)
        liquidity_trends = 0
        if volume_ratio > 1.5 and spread_volatility < 0.5:
            liquidity_trends = 1
        elif volume_ratio < 0.7 or spread_volatility > 1.0:
            liquidity_trends = -1

        # Risk Features
        volatility_risk_score = atr / price * 100 if price else 0

        # correlation_risk: كم العملة تتحرك بشكل مستقل عن BTC (بيانات موجودة في analysis)
        try:
            btc_change = safe_float(analysis.get('btc_change', analysis.get('btc_dominance', 0)))
            coin_change = safe_float(analysis.get('price_momentum', analysis.get('price_change_24h', 0)))
            correlation_risk = min(abs(coin_change - btc_change) / 10.0, 1.0)
        except:
            correlation_risk = 0

        # gap_risk_score: متوسط الفجوات السعرية بين الشمعات
        try:
            if candles and len(candles) >= 5:
                gaps = []
                for i in range(1, min(10, len(candles))):
                    prev_close = safe_float(candles[i-1].get('close', 0))
                    curr_open  = safe_float(candles[i].get('open', 0))
                    if prev_close > 0:
                        gaps.append(abs(curr_open - prev_close) / prev_close)
                gap_risk_score = (sum(gaps) / len(gaps)) * 100 if gaps else 0
            else:
                gap_risk_score = 0
        except:
            gap_risk_score = 0

        # black_swan_probability: احتمال حركة متطرفة (اعتماداً على ATR والتذبذب)
        try:
            if candles and len(candles) >= 10:
                closes = [safe_float(c.get('close', 0)) for c in candles[-10:] if c.get('close')]
                if len(closes) >= 2:
                    changes = [abs(closes[i] - closes[i-1]) / max(closes[i-1], 1) for i in range(1, len(closes))]
                    avg_change = sum(changes) / len(changes)
                    max_change = max(changes)
                    black_swan_probability = min(max_change / max(avg_change * 3, 0.001), 1.0)
                else:
                    black_swan_probability = 0
            else:
                black_swan_probability = 0
        except:
            black_swan_probability = 0

        # behavioral_risk: خطر سلوكي بناءً على panic و RSI المتطرف
        try:
            panic_score_val = safe_float(analysis.get('panic_greed', {}).get('panic_score', 0))
            rsi_extreme = max(0, rsi - 70) / 30 if rsi > 70 else max(0, 30 - rsi) / 30
            behavioral_risk = min((panic_score_val / 100 + rsi_extreme) / 2, 1.0)
        except:
            behavioral_risk = 0

        # systemic_risk: خطر السوق العام (volume منخفض + spread عالي)
        try:
            low_volume_risk = max(0, 1 - volume_ratio) if volume_ratio < 1 else 0
            high_spread_risk = min(spread_volatility / 2, 1.0)
            systemic_risk = (low_volume_risk + high_spread_risk) / 2
        except:
            systemic_risk = 0

        # Exit Features
        profit_optimization_score = profit / 10

        # time_decay_signals: كلما طالت المدة كلما زاد الضغط للخروج
        time_decay_signals = min(hours_held / 48, 1.0)

        # opportunity_cost_exits: هل السوق يقدم فرص أفضل؟ (volume مرتفع = فرص أكثر)
        try:
            opportunity_cost_exits = min(safe_float(analysis.get('market_volume_ratio', volume_ratio)) / 3, 1.0)
        except:
            opportunity_cost_exits = 0

        # market_condition_exits: حالة السوق عند البيع
        try:
            greed = safe_float(analysis.get('panic_greed', {}).get('greed_score', 50))
            market_condition_exits = greed / 100
        except:
            market_condition_exits = 0

        # Pattern Features
        # harmonic_patterns_score: بناءً على نسب Fibonacci بين الشمعات
        try:
            if candles and len(candles) >= 5:
                highs  = [safe_float(c.get('high', 0)) for c in candles[-5:]]
                lows   = [safe_float(c.get('low', 0)) for c in candles[-5:]]
                swing  = max(highs) - min(lows)
                fib_50 = min(lows) + swing * 0.5
                fib_61 = min(lows) + swing * 0.618
                curr_price = safe_float(candles[-1].get('close', price))
                dist_50 = abs(curr_price - fib_50) / max(swing, 0.0001)
                dist_61 = abs(curr_price - fib_61) / max(swing, 0.0001)
                harmonic_patterns_score = max(0, 1 - min(dist_50, dist_61))
            else:
                harmonic_patterns_score = 0
        except:
            harmonic_patterns_score = 0

        # elliott_wave_signals: كشف موجات بسيط (ارتفاع ثم انخفاض ثم ارتفاع)
        try:
            if candles and len(candles) >= 6:
                closes_ew = [safe_float(c.get('close', 0)) for c in candles[-6:]]
                up1   = closes_ew[1] > closes_ew[0]
                down1 = closes_ew[2] < closes_ew[1]
                up2   = closes_ew[3] > closes_ew[2]
                down2 = closes_ew[4] < closes_ew[3]
                up3   = closes_ew[5] > closes_ew[4]
                elliott_wave_signals = 1.0 if (up1 and down1 and up2 and down2 and up3) else 0.0
            else:
                elliott_wave_signals = 0
        except:
            elliott_wave_signals = 0

        # fractal_patterns: نمط الشمعة الوسطى أعلى/أقل من جيرانها
        try:
            if candles and len(candles) >= 5:
                fractal_count = 0
                for i in range(2, min(len(candles)-2, 10)):
                    h = [safe_float(candles[j].get('high', 0)) for j in range(i-2, i+3)]
                    l = [safe_float(candles[j].get('low', 0)) for j in range(i-2, i+3)]
                    if h[2] == max(h) or l[2] == min(l):
                        fractal_count += 1
                fractal_patterns = min(fractal_count / 5, 1.0)
            else:
                fractal_patterns = 0
        except:
            fractal_patterns = 0

        # cycle_patterns: هل الحركة تكررت؟ (مقارنة أول وآخر الشمعات)
        try:
            if candles and len(candles) >= 10:
                first_half = [safe_float(c.get('close', 0)) for c in candles[-10:-5]]
                second_half = [safe_float(c.get('close', 0)) for c in candles[-5:]]
                f_trend = (first_half[-1] - first_half[0]) / max(abs(first_half[0]), 0.001)
                s_trend = (second_half[-1] - second_half[0]) / max(abs(second_half[0]), 0.001)
                cycle_patterns = 1.0 if (f_trend > 0 and s_trend > 0) or (f_trend < 0 and s_trend < 0) else 0.0
            else:
                cycle_patterns = 0
        except:
            cycle_patterns = 0

        # momentum_patterns: قوة الزخم من RSI + MACD + Volume
        try:
            rsi_signal  = 1 if rsi > 60 else (-1 if rsi < 40 else 0)
            macd_signal = 1 if macd_diff > 0 else -1
            vol_signal  = 1 if volume_ratio > 1.5 else (0 if volume_ratio > 0.8 else -1)
            momentum_patterns = (rsi_signal + macd_signal + vol_signal) / 3
        except:
            momentum_patterns = 0

        # Smart Money Features

        # smart_money_ratio: نسبة الأموال الذكية (order book imbalance + volume)
        try:
            smart_money_ratio = min(abs(order_book_imbalance) * volume_ratio, 1.0)
        except:
            smart_money_ratio = 0

        # exchange_whale_flows: تدفق الحيتان (volume عالي جداً = تدفق كبير)
        try:
            exchange_whale_flows = min(max(volume_ratio - 1, 0) / 4, 1.0)
        except:
            exchange_whale_flows = 0

        # Anomaly Features
        # statistical_outliers: هل السعر الحالي خارج النطاق الطبيعي؟
        try:
            if candles and len(candles) >= 10:
                closes_an = [safe_float(c.get('close', 0)) for c in candles[-10:]]
                avg_c = sum(closes_an) / len(closes_an)
                std_c = (sum((x - avg_c)**2 for x in closes_an) / len(closes_an)) ** 0.5
                statistical_outliers = min(abs(price - avg_c) / max(std_c * 2, 0.0001), 1.0)
            else:
                statistical_outliers = 0
        except:
            statistical_outliers = 0

        # pattern_anomalies: شمعة كبيرة غير عادية
        try:
            if candles and len(candles) >= 5:
                bodies = [abs(safe_float(c.get('close',0)) - safe_float(c.get('open',0))) for c in candles[-5:]]
                avg_body = sum(bodies[:-1]) / max(len(bodies)-1, 1)
                pattern_anomalies = min(bodies[-1] / max(avg_body * 2, 0.0001), 1.0) - 0.5
                pattern_anomalies = max(0, pattern_anomalies)
            else:
                pattern_anomalies = 0
        except:
            pattern_anomalies = 0

        # behavioral_anomalies: سلوك غير طبيعي (panic + volume spike)
        try:
            panic_val = safe_float(analysis.get('panic_greed', {}).get('panic_score', 0))
            behavioral_anomalies = min((panic_val / 100 + max(volume_ratio - 2, 0) / 3) / 2, 1.0)
        except:
            behavioral_anomalies = 0

        # volume_anomalies: حجم غير طبيعي مقارنة بالمتوسط
        try:
            if candles and len(candles) >= 10:
                vols = [safe_float(c.get('volume', 0)) for c in candles[-10:]]
                avg_vol = sum(vols[:-1]) / max(len(vols)-1, 1)
                last_vol = vols[-1]
                volume_anomalies = min(abs(last_vol - avg_vol) / max(avg_vol, 0.0001), 1.0)
            else:
                volume_anomalies = min(max(volume_ratio - 1.5, 0) / 2, 1.0)
        except:
            volume_anomalies = 0

        # Chart CNN Features
        # attention_mechanism_score: تركيز الاهتمام (RSI extreme + volume spike)
        try:
            rsi_attention = abs(rsi - 50) / 50
            vol_attention = min(max(volume_ratio - 1, 0) / 2, 1.0)
            attention_mechanism_score = (rsi_attention + vol_attention) / 2
        except:
            attention_mechanism_score = 0

        # multi_scale_features: مقارنة حركة قصيرة وطويلة المدى
        try:
            if candles and len(candles) >= 20:
                short_trend = safe_float(candles[-1].get('close',0)) - safe_float(candles[-5].get('close',0))
                long_trend  = safe_float(candles[-1].get('close',0)) - safe_float(candles[-20].get('close',0))
                short_norm  = short_trend / max(abs(long_trend), 0.0001)
                multi_scale_features = max(-1.0, min(1.0, short_norm))
            else:
                multi_scale_features = 0
        except:
            multi_scale_features = 0

        # temporal_features: موضع الصفقة زمنياً (بكير = 0، متأخر = 1)
        try:
            temporal_features = min(hours_held / 72, 1.0)
        except:
            temporal_features = 0

        # Volume Features
        volume_trend_strength = safe_float(analysis.get('volume_trend', 0))

        # volume_volatility: تذبذب الحجم
        try:
            if candles and len(candles) >= 5:
                vols_vv = [safe_float(c.get('volume', 0)) for c in candles[-10:]]
                avg_vv  = sum(vols_vv) / max(len(vols_vv), 1)
                volume_volatility = sum(abs(v - avg_vv) for v in vols_vv) / max(avg_vv, 0.0001) / len(vols_vv)
            else:
                volume_volatility = 0
        except:
            volume_volatility = 0

        # volume_momentum: هل الحجم يزيد أو ينقص؟
        try:
            if candles and len(candles) >= 6:
                recent_v = sum(safe_float(c.get('volume',0)) for c in candles[-3:]) / 3
                older_v  = sum(safe_float(c.get('volume',0)) for c in candles[-6:-3]) / 3
                volume_momentum = (recent_v - older_v) / max(older_v, 0.0001)
                volume_momentum = max(-1.0, min(1.0, volume_momentum))
            else:
                volume_momentum = 0
        except:
            volume_momentum = 0

        # volume_seasonality: نمط دوري للحجم (نسبة الحجم الحالي لمتوسط نفس الوقت)
        try:
            volume_seasonality = min(volume_ratio / 2, 1.0)
        except:
            volume_seasonality = 0

        # volume_correlation: علاقة الحجم بالسعر
        try:
            if candles and len(candles) >= 5:
                price_changes = []
                vol_changes   = []
                for i in range(1, min(6, len(candles))):
                    pc = safe_float(candles[i].get('close',0)) - safe_float(candles[i-1].get('close',0))
                    vc = safe_float(candles[i].get('volume',0)) - safe_float(candles[i-1].get('volume',0))
                    price_changes.append(pc)
                    vol_changes.append(vc)
                same_dir = sum(1 for p, v in zip(price_changes, vol_changes) if (p > 0 and v > 0) or (p < 0 and v < 0))
                volume_correlation = same_dir / max(len(price_changes), 1)
            else:
                volume_correlation = 0.5
        except:
            volume_correlation = 0

        # Meta Features
        # dynamic_consultant_weights: متوسط ثقة المستشارين اللي صوتوا للبيع
        try:
            if sell_votes:
                voted_sell = [v for v in sell_votes.values() if v == 1]
                dynamic_consultant_weights = len(voted_sell) / max(len(sell_votes), 1)
            else:
                dynamic_consultant_weights = 0
        except:
            dynamic_consultant_weights = 0

        # uncertainty_quantification: عدم اليقين (أصوات متضاربة بين المستشارين)
        try:
            if sell_votes:
                votes_list = list(sell_votes.values())
                agree = max(votes_list.count(1), votes_list.count(0))
                uncertainty_quantification = 1 - (agree / max(len(votes_list), 1))
            else:
                uncertainty_quantification = 0.5
        except:
            uncertainty_quantification = 0

        # context_aware_score: مدى ملاءمة السياق (profit + market condition)
        try:
            profit_factor = max(0, min(profit / 10, 1.0))
            greed_factor  = safe_float(analysis.get('panic_greed', {}).get('greed_score', 50)) / 100
            context_aware_score = (profit_factor + greed_factor) / 2
        except:
            context_aware_score = 0

        # Add to trade_data - READ ALL VALUES FROM REAL ANALYSIS DATA!!!
        trade_data.update({
            'order_book_imbalance': safe_float(analysis_data.get('order_book_imbalance')),
            'spread_volatility': safe_float(analysis_data.get('spread_volatility')),
            'depth_at_1pct': safe_float(analysis_data.get('depth_at_1pct')),
            'market_impact_score': safe_float(analysis_data.get('market_impact_score')),
            'liquidity_trends': safe_float(analysis_data.get('liquidity_trends')),
            'volatility_risk_score': safe_float(analysis_data.get('volatility_risk_score')),
            'correlation_risk': safe_float(analysis_data.get('correlation_risk')),
            'gap_risk_score': safe_float(analysis_data.get('gap_risk_score')),
            'black_swan_probability': safe_float(analysis_data.get('black_swan_probability')),
            'behavioral_risk': safe_float(analysis_data.get('behavioral_risk')),
            'systemic_risk': safe_float(analysis_data.get('systemic_risk')),
            'profit_optimization_score': safe_float(analysis_data.get('profit_optimization_score')),
            'time_decay_signals': safe_float(analysis_data.get('time_decay_signals')),
            'opportunity_cost_exits': safe_float(analysis_data.get('opportunity_cost_exits')),
            'market_condition_exits': safe_float(analysis_data.get('market_condition_exits')),
            'harmonic_patterns_score': safe_float(analysis_data.get('harmonic_patterns_score')),
            'elliott_wave_signals': safe_float(analysis_data.get('elliott_wave_signals')),
            'fractal_patterns': safe_float(analysis_data.get('fractal_patterns')),
            'cycle_patterns': safe_float(analysis_data.get('cycle_patterns')),
            'momentum_patterns': safe_float(analysis_data.get('momentum_patterns')),
            'whale_wallet_changes': safe_float(analysis_data.get('whale_wallet_changes')),
            'institutional_accumulation': safe_float(analysis_data.get('institutional_accumulation')),
            'smart_money_ratio': safe_float(analysis_data.get('smart_money_ratio')),
            'exchange_whale_flows': safe_float(analysis_data.get('exchange_whale_flows')),
            'statistical_outliers': safe_float(analysis_data.get('statistical_outliers')),
            'pattern_anomalies': safe_float(analysis_data.get('pattern_anomalies')),
            'behavioral_anomalies': safe_float(analysis_data.get('behavioral_anomalies')),
            'volume_anomalies': safe_float(analysis_data.get('volume_anomalies')),
            'attention_mechanism_score': safe_float(analysis_data.get('attention_mechanism_score')),
            'multi_scale_features': safe_float(analysis_data.get('multi_scale_features')),
            'temporal_features': safe_float(analysis_data.get('temporal_features')),
            'volume_trend_strength': safe_float(analysis_data.get('volume_trend_strength')),
            'volume_volatility': safe_float(analysis_data.get('volume_volatility')),
            'volume_momentum': safe_float(analysis_data.get('volume_momentum')),
            'volume_seasonality': safe_float(analysis_data.get('volume_seasonality')),
            'volume_correlation': safe_float(analysis_data.get('volume_correlation')),
            'dynamic_consultant_weights': safe_float(analysis_data.get('dynamic_consultant_weights')),
            'uncertainty_quantification': safe_float(analysis_data.get('uncertainty_quantification')),
            'context_aware_score': safe_float(analysis_data.get('context_aware_score')),
            'rsi': safe_float(analysis_data.get('rsi'), 50),
            'volume_ratio': safe_float(volume_ratio, 1),
            'sentiment_score': safe_float(analysis_data.get('sentiment_score'), 0),
            'panic_score': safe_float(analysis_data.get('panic_score'), 0)
        })
        # تحديث ذاكرة العملة
        try:
            if hasattr(storage.storage, 'update_symbol_memory'):
                storage.storage.update_symbol_memory(
                    symbol=symbol,
                    profit=float(profit),
                    trade_quality=str(trade_quality),
                    hours_held=float(hours_held),
                    rsi=float(position.get('ai_data', {}).get('rsi', 50)),
                    volume_ratio=float(position.get('ai_data', {}).get('volume_ratio', 1))
                )
        except Exception as e:
            print(f"⚠️ Symbol memory update error: {e}")

        storage.save_trade(trade_data)
        
        # =========================================================
        # 🎓 التعلم المباشر للملك والمستشارين - حفظ في الداتابيز
        # =========================================================
        
        # حفظ بيانات التعلم
        try:
            # تعلم المستشارين (dl_client)
            if dl_client:
                dl_client.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, signal_type='sell')

            # تعلم الملك (مع symbol للقائمة السوداء)
            if meta:
                meta.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, symbol=symbol)
            
            king_learning_data = {
                'king': {
                    'buy_success': 1 if profit > 0.5 else 0,
                    'buy_fail': 1 if profit < -0.5 else 0,
                    'sell_success': 1 if trade_quality in ['GREAT', 'GOOD', 'OK'] else 0,
                    'sell_fail': 1 if trade_quality in ['RISKY', 'TRAP'] else 0,
                    'peak_correct': 1 if trade_quality in ['GREAT', 'GOOD', 'OK'] else 0,
                    'peak_wrong': 1 if trade_quality in ['RISKY', 'TRAP'] else 0,
                    'bottom_correct': 1 if profit > 0.5 else 0,
                    'bottom_wrong': 1 if profit < -0.5 else 0
                }
            }
            storage.save_learning_data('king', king_learning_data)
            
            # تعلم المستشارين (من أصوات البيع)
            advisor_learning_data = {}
            for advisor, voted in sell_votes.items():
                if trade_quality in ['GREAT', 'GOOD', 'OK']:
                    advisor_learning_data[advisor] = {
                        'sell_success': 1 if voted == 1 else 0,
                        'sell_fail': 0 if voted == 1 else 1
                    }
                elif trade_quality in ['RISKY', 'TRAP']:
                    advisor_learning_data[advisor] = {
                        'sell_success': 0 if voted == 1 else 1,
                        'sell_fail': 1 if voted == 1 else 0
                    }
            if advisor_learning_data:
                storage.save_learning_data('advisors', advisor_learning_data)
            
            print(f"🎓 Learning saved to database")
            
        except Exception as e:
            print(f"⚠️ Learning save error: {e}")
        
        quality_emoji = '🟢' if trade_quality in ['GREAT', 'GOOD'] else ('🟡' if trade_quality == 'OK' else '🔴')
        print(f"{quality_emoji} Trade Quality: {trade_quality} | Profit: {profit:+.2f}% | Held: {hours_held:.1f}h")
        
    except Exception as e:
        print(f"⚠️ Error saving trade for {symbol}: {e}")

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = None

    try:
        storage.delete_position(symbol)
        print(f"✅ {symbol} position deleted from database.")
    except Exception as e:
        print(f"⚠️ Error deleting {symbol} from database: {e}")

    return True
