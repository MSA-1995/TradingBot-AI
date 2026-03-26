"""
📊 Technical Analysis Module
Handles RSI, MACD, Volume, Momentum calculations
"""

import pandas as pd
import ta
from datetime import datetime
from functools import lru_cache
import time

# [تحسين الذاكرة] تم حذف المتغير العام _market_cache

@lru_cache(maxsize=1)
def get_market_data(exchange, ttl_hash=None):
    """[تحسين الذاكرة] جلب بيانات السوق مع تخزين مؤقت آمن باستخدام lru_cache"""
    del ttl_hash # يستخدم فقط لتحديث الكاش
    new_market_data = {}
    for market_coin in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
        try:
            m_ohlcv = exchange.fetch_ohlcv(market_coin, '5m', limit=13)
            if len(m_ohlcv) >= 13:
                m_current = m_ohlcv[-1][4]
                m_1h_ago = m_ohlcv[-13][4]
                change = ((m_current - m_1h_ago) / m_1h_ago) * 100
                new_market_data[market_coin] = change
            else:
                new_market_data[market_coin] = 0
        except:
            new_market_data[market_coin] = 0
    return new_market_data

def get_ttl_hash(seconds=20):
    """[تحسين الذاكرة] إنشاء hash يعتمد على الوقت لتحديث الكاش"""
    return round(time.time() / seconds)

def analyze_reversal(df, current_price):
    """
    تحليل الارتداد من القاع اللحظي
    Returns: dict with reversal analysis
    """
    if df is None or len(df) < 5:
        return {
            'low_1h': 0,
            'bounce_percent': 0,
            'is_reversing': False
        }
    
    try:
        # تحديد القاع في آخر ساعة (12 شمعة * 5 دقائق)
        low_1h = df['low'].tail(12).min() if len(df) >= 12 else df['low'].min()
        
        # حساب نسبة الارتداد من القاع
        if low_1h > 0:
            bounce_percent = ((current_price - low_1h) / low_1h) * 100
        else:
            bounce_percent = 0
            
        # هل بدأ السعر بالارتداد؟ (ارتد 0.1% على الأقل)
        is_reversing = bounce_percent >= 0.1
        
        return {
            'low_1h': low_1h,
            'bounce_percent': bounce_percent,
            'is_reversing': is_reversing
        }
        
    except Exception as e:
        return {
            'low_1h': 0,
            'bounce_percent': 0,
            'is_reversing': False
        }

def get_market_analysis(exchange, symbol, limit=60):
    """Get technical analysis for a symbol with multi-timeframe data"""
    try:
        # 1. جلب بيانات العملة الحالية (لحظي ومباشر)
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)  # Fill NaN with 1.0
        
        # Momentum
        df['price_change'] = df['close'].pct_change(10) * 100
        df['price_change'] = df['price_change'].fillna(0)  # Fill NaN with 0
        
        # ========== الإضافات الجديدة (5 مؤشرات) ==========
        
        # 1. ATR (Average True Range) - للمخاطرة (محسّن باستخدام مكتبة ta)
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        ).average_true_range()
        df['atr'] = df['atr'].fillna(1.0)
        
        # 2. EMA 9/21 Crossover - للأنماط (محسّن باستخدام مكتبة ta)
        df['ema_9'] = ta.trend.EMAIndicator(close=df['close'], window=9, fillna=True).ema_indicator()
        df['ema_21'] = ta.trend.EMAIndicator(close=df['close'], window=21, fillna=True).ema_indicator()
        df['ema_crossover'] = (df['ema_9'] > df['ema_21']).astype(int) * 2 - 1  # 1 or -1
        
        # 3. Bid-Ask Spread - للفخاخ (سيتم حسابه من API)
        # سيتم إضافته لاحقاً من ticker data
        
        # 4. Volume Trend - للبيع
        df['volume_trend'] = df['volume'].pct_change(3) * 100  # تغير الحجم في آخر 3 شموع
        df['volume_trend'] = df['volume_trend'].fillna(0)
        
        # 5. Price Change 1h - للشذوذ
        if len(df) >= 12:  # 12 شموع × 5 دقائق = ساعة
            df['price_change_1h'] = ((df['close'] - df['close'].shift(12)) / df['close'].shift(12)) * 100
        else:
            df['price_change_1h'] = 0
        df['price_change_1h'] = df['price_change_1h'].fillna(0)
        
        # ========== حساب تغير BTC, ETH, BNB (للسوق العام) ==========
        btc_change_1h = 0
        eth_change_1h = 0
        bnb_change_1h = 0
        
        # [تحسين الذاكرة] استخدام الدالة الجديدة مع التخزين المؤقت الآمن
        market_data = get_market_data(exchange, ttl_hash=get_ttl_hash())
        
        if symbol not in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
            btc_change_1h = market_data.get('BTC/USDT', 0)
            eth_change_1h = market_data.get('ETH/USDT', 0)
            bnb_change_1h = market_data.get('BNB/USDT', 0)
        
        # Multi-timeframe analysis من نفس البيانات
        mtf_analysis = calculate_mtf_from_5m_data(df)
        
        latest = df.iloc[-1]
        
        # تحسين: إذا المؤشرات سيئة جداً، لا داعي لجلب Order Book (توفير وقت)
        # إذا RSI > 65 (تشبع شرائي) وما زلنا نبحث عن شراء، غالباً لن نشتري
        # ولكن نحتاج السيولة للموديلات، سنكتفي بتحسين سرعة السوق العام حالياً
        
        # Get Bid-Ask Spread from ticker
        bid_ask_spread = 0
        try:
            ticker = exchange.fetch_ticker(symbol)
            if ticker.get('bid') and ticker.get('ask'):
                bid_ask_spread = ((ticker['ask'] - ticker['bid']) / ticker['bid']) * 100
        except:
            bid_ask_spread = 0
        
        # ========== إضافة بيانات السيولة (Order Book) ==========
        liquidity_metrics = get_liquidity_metrics(exchange, symbol, df)

        # ========== Reversal Analysis (New) ==========
        reversal_analysis = analyze_reversal(df, latest['close'])

        # ========== Price Drop Analysis (New) ==========
        price_drop = {'drop_percent': 0, 'confirmed': False}
        try:
            if len(df) >= 12:
                highest_price_1h = df['high'].tail(12).max()
                current_price_df = df['close'].iloc[-1]
                
                if highest_price_1h is not None and current_price_df is not None and highest_price_1h > 0:
                    drop_percent = ((highest_price_1h - current_price_df) / highest_price_1h) * 100
                    price_drop = {
                        'drop_percent': drop_percent,
                        'highest_1h': highest_price_1h,
                        'current': current_price_df,
                        'confirmed': drop_percent >= 2.0
                    }
        except Exception as e:
            pass # Ignore if calculation fails
        
        # [تحسين الذاكرة] لا تقم بإرجاع الـ DataFrame الكامل.
        # تم استخلاص جميع المعلومات الضرورية في المتغير 'latest'
        # سيتم تحرير ذاكرة الـ df تلقائيًا عند انتهاء الدالة.
        return {
            # 'df': df, # <<< تم الحذف لمنع تسرب الذاكرة
            'rsi': latest['rsi'],
            'macd': latest['macd'],
            'macd_signal': latest['macd_signal'],
            'macd_diff': latest['macd_diff'],
            'volume': latest['volume'],
            'volume_sma': latest['volume_sma'],
            'volume_ratio': latest['volume_ratio'],
            'price_momentum': latest['price_change'],
            'close': latest['close'],
            'mtf': mtf_analysis,  # إضافة تحليل multi-timeframe
            # الإضافات الجديدة
            'atr': latest['atr'],
            'ema_9': latest['ema_9'],
            'ema_21': latest['ema_21'],
            'ema_crossover': latest['ema_crossover'],
            'bid_ask_spread': bid_ask_spread,
            'volume_trend': latest['volume_trend'],
            'price_change_1h': latest['price_change_1h'],
            'reversal': reversal_analysis,  # إضافة تحليل الارتداد
            'price_drop': price_drop, # إضافة تحليل هبوط السعر
            # بيانات السيولة
            'liquidity': liquidity_metrics,
            # بيانات السوق العام (Top 3)
            'btc_change_1h': btc_change_1h,
            'eth_change_1h': eth_change_1h,
            'bnb_change_1h': bnb_change_1h
        }
    except Exception as e:
        print(f"❌ Analysis error {symbol}: {e}")
        return None

def calculate_mtf_from_5m_data(df):
    """حساب multi-timeframe analysis من بيانات 5 دقائق"""
    try:
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}
        
        # تحليل 5 دقائق (آخر 20 نقطة)
        df_5m = df.tail(20).copy()
        df_5m['sma_20'] = df_5m['close'].rolling(window=20).mean()
        df_5m['sma_50'] = df_5m['close'].rolling(window=min(50, len(df_5m))).mean()
        latest_5m = df_5m.iloc[-1]
        
        if latest_5m['close'] > latest_5m['sma_20'] > latest_5m['sma_50']:
            scores['bullish'] += 1
        elif latest_5m['close'] < latest_5m['sma_20'] < latest_5m['sma_50']:
            scores['bearish'] += 1
        else:
            scores['neutral'] += 1
        
        # تحليل 15 دقائق (كل 3 نقاط من بيانات 5 دقائق)
        if len(df) >= 20:
            df_15m = df.iloc[::3].tail(20).copy()  # كل 3 نقاط = 15 دقيقة
            df_15m['sma_20'] = df_15m['close'].rolling(window=20).mean()
            df_15m['sma_50'] = df_15m['close'].rolling(window=min(50, len(df_15m))).mean()
            if len(df_15m) > 0:
                latest_15m = df_15m.iloc[-1]
                
                if latest_15m['close'] > latest_15m['sma_20'] > latest_15m['sma_50']:
                    scores['bullish'] += 1
                elif latest_15m['close'] < latest_15m['sma_20'] < latest_15m['sma_50']:
                    scores['bearish'] += 1
                else:
                    scores['neutral'] += 1
        
        # تحليل ساعة (كل 12 نقطة من بيانات 5 دقائق)
        if len(df) >= 60:
            df_1h = df.iloc[::12].tail(20).copy()  # كل 12 نقطة = ساعة
            df_1h['sma_20'] = df_1h['close'].rolling(window=20).mean()
            df_1h['sma_50'] = df_1h['close'].rolling(window=min(50, len(df_1h))).mean()
            if len(df_1h) > 0:
                latest_1h = df_1h.iloc[-1]
                
                if latest_1h['close'] > latest_1h['sma_20'] > latest_1h['sma_50']:
                    scores['bullish'] += 1
                elif latest_1h['close'] < latest_1h['sma_20'] < latest_1h['sma_50']:
                    scores['bearish'] += 1
                else:
                    scores['neutral'] += 1
        
        trend = max(scores, key=scores.get)
        return {'trend': trend, 'scores': scores, 'total': scores[trend]}
        
    except Exception as e:
        return {'trend': 'neutral', 'scores': {'bullish': 0, 'bearish': 0, 'neutral': 3}, 'total': 3}



def get_liquidity_metrics(exchange, symbol, df_5m=None):
    """
    قياس السيولة من Order Book
    Returns: dict with liquidity metrics
    """
    try:
        # 1. قراءة Order Book
        order_book = exchange.fetch_order_book(symbol, limit=20)
        
        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return {
                'depth_ratio': 1.0,
                'spread_percent': 0.1,
                'bid_depth': 0,
                'ask_depth': 0,
                'liquidity_score': 50,
                'price_impact': 0.5,
                'volume_consistency': 50
            }
        
        # 2. حساب Bid/Ask Depth (أول 10 مستويات)
        bid_depth = sum([bid[1] for bid in order_book['bids'][:10]]) if len(order_book['bids']) >= 10 else 0
        ask_depth = sum([ask[1] for ask in order_book['asks'][:10]]) if len(order_book['asks']) >= 10 else 0
        
        # 3. نسبة التوازن
        depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0
        
        # 4. قياس Spread
        best_bid = order_book['bids'][0][0] if order_book['bids'] else 0
        best_ask = order_book['asks'][0][0] if order_book['asks'] else 0
        spread_percent = ((best_ask - best_bid) / best_bid) * 100 if best_bid > 0 else 0.1
        
        # 5. محاكاة تأثير السعر (شراء بـ $15)
        target_cost = 15
        cumulative_cost = 0
        cumulative_volume = 0
        price_impact = 0
        
        for ask in order_book['asks']:
            price, volume = ask
            cost = price * volume
            if cumulative_cost + cost >= target_cost:
                # وصلنا للهدف
                remaining = target_cost - cumulative_cost
                final_price = price
                price_impact = ((final_price - best_ask) / best_ask) * 100 if best_ask > 0 else 0
                break
            cumulative_cost += cost
            cumulative_volume += volume
        
        # 6. حساب Liquidity Score (0-100)
        liquidity_score = 100
        
        # خصم بناءً على Spread
        if spread_percent > 0.5:
            liquidity_score -= 30
        elif spread_percent > 0.3:
            liquidity_score -= 15
        
        # خصم بناءً على Depth Ratio
        if depth_ratio < 0.7 or depth_ratio > 1.5:
            liquidity_score -= 20
        
        # خصم بناءً على حجم السيولة
        if bid_depth < 10000:
            liquidity_score -= 20
        elif bid_depth < 50000:
            liquidity_score -= 10
        
        # خصم بناءً على تأثير السعر
        if price_impact > 1.0:
            liquidity_score -= 20
        elif price_impact > 0.5:
            liquidity_score -= 10
        
        liquidity_score = max(0, liquidity_score)
        
        # 7. تحليل ثبات الحجم (من البيانات التاريخية)
        volume_consistency = 50  # default
        try:
            # تحسين السرعة: استخدام بيانات 5 دقائق بدلاً من طلب بيانات 1 ساعة جديدة
            if df_5m is not None and not df_5m.empty:
                volumes = df_5m['volume'].tolist()
                import numpy as np
                volume_mean = np.mean(volumes)
                volume_std = np.std(volumes)
                
                # لو الانحراف المعياري منخفض = ثبات عالي
                if volume_mean > 0:
                    cv = (volume_std / volume_mean) * 100  # Coefficient of Variation
                    if cv < 30:
                        volume_consistency = 90  # ثبات ممتاز
                    elif cv < 50:
                        volume_consistency = 70  # ثبات جيد
                    elif cv < 80:
                        volume_consistency = 50  # ثبات متوسط
                    else:
                        volume_consistency = 30  # متذبذب
        except:
            volume_consistency = 50
        
        return {
            'depth_ratio': round(depth_ratio, 2),
            'spread_percent': round(spread_percent, 4),
            'bid_depth': round(bid_depth, 2),
            'ask_depth': round(ask_depth, 2),
            'liquidity_score': int(liquidity_score),
            'price_impact': round(price_impact, 4),
            'volume_consistency': int(volume_consistency)
        }
        
    except Exception as e:
        print(f"⚠️ Liquidity metrics error for {symbol}: {e}")
        return {
            'depth_ratio': 1.0,
            'spread_percent': 0.1,
            'bid_depth': 0,
            'ask_depth': 0,
            'liquidity_score': 50,
            'price_impact': 0.5,
            'volume_consistency': 50
        }
