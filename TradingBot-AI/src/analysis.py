"""
📊 Technical Analysis Module
Handles RSI, MACD, Volume, Momentum calculations
"""

import pandas as pd
import ta

def get_market_analysis(exchange, symbol, limit=50):
    """Get technical analysis for a symbol"""
    try:
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
        
        latest = df.iloc[-1]
        
        return {
            'rsi': latest['rsi'],
            'macd': latest['macd'],
            'macd_signal': latest['macd_signal'],
            'macd_diff': latest['macd_diff'],
            'volume': latest['volume'],
            'volume_sma': latest['volume_sma'],
            'volume_ratio': latest['volume_ratio'],
            'price_momentum': latest['price_change'],
            'close': latest['close'],
            'df': df
        }
    except Exception as e:
        print(f"❌ Analysis error {symbol}: {e}")
        return None

def get_multi_timeframe_analysis(exchange, symbol):
    """Multi-timeframe trend analysis"""
    try:
        timeframes = {'5m': 50, '15m': 50, '1h': 50}
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}
        
        for tf, limit in timeframes.items():
            ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=min(50, len(df))).mean()
            
            latest = df.iloc[-1]
            
            if latest['close'] > latest['sma_20'] > latest['sma_50']:
                scores['bullish'] += 1
            elif latest['close'] < latest['sma_20'] < latest['sma_50']:
                scores['bearish'] += 1
            else:
                scores['neutral'] += 1
        
        trend = max(scores, key=scores.get)
        return {'trend': trend, 'scores': scores, 'total': scores[trend]}
        
    except Exception as e:
        return {'trend': 'neutral', 'scores': {'bullish': 0, 'bearish': 0, 'neutral': 3}, 'total': 3}

def calculate_momentum(df):
    """Calculate price momentum"""
    if len(df) < 10:
        return 0
    current_price = df['close'].iloc[-1]
    past_price = df['close'].iloc[-10]
    momentum = ((current_price - past_price) / past_price) * 100
    return momentum

def check_volume_smart(volume_ratio, confidence):
    """Smart volume check based on confidence"""
    if confidence >= 70:
        return volume_ratio >= 0.8
    elif confidence >= 60:
        return volume_ratio >= 1.0
    else:
        return volume_ratio >= 1.2

def adjust_confidence_for_oversold(rsi, macd_diff, confidence):
    """Adjust confidence for oversold conditions"""
    if rsi < 25:
        if macd_diff < 10:
            return confidence * 0.7
        else:
            return confidence * 0.85
    return confidence
