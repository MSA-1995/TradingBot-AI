"""Split-out analysis helpers."""

import pandas as pd
import numpy as np


def _build_technical_indicators(df):
    """Build all technical indicators (RSI, MACD, ATR, etc.)"""
    if df is None or len(df) < 20:
        return df
    
    # EMA
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_crossover'] = (df['ema_9'] > df['ema_21']).astype(int) - (df['ema_9'] < df['ema_21']).astype(int)
    
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df.loc[(gain > 0) & (loss == 0), 'rsi'] = 100
    df.loc[(gain == 0) & (loss > 0), 'rsi'] = 0
    df.loc[(gain == 0) & (loss == 0), 'rsi'] = 50
    
    # MACD
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_diff'] = df['macd'] - df['macd_signal']
    df['macd_histogram'] = df['macd_diff']
    df['macd_diff_pct'] = (df['macd_diff'] / df['close'].replace(0, 1)) * 100
    
    # ATR
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # Volume
    df['volume_sma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma'].replace(0, 1)
    df['volume_trend'] = df['volume_ratio'].rolling(5).mean().iloc[-1] - 1.0 if len(df) >= 5 else 0
    
    # Price change
    df['price_change'] = df['close'].pct_change() * 100
    df['price_change_1h'] = df['close'].pct_change(12) * 100
    
    # Noise detection
    df['is_noise'] = df['atr'] > df['close'] * 0.005
    df['fake_break'] = (df['high'] > df['high'].shift(1)) & (df['close'] < df['high'].shift(1))
    
    return df


def _build_latest_dict(df):
    """Build latest candle dictionary efficiently"""
    _safe = lambda val, default=0.0: float(val) if not pd.isna(val) else default
    
    if df is None or len(df) == 0:
        return {}
    
    lr = df.iloc[-1]
    return {
        'close': _safe(lr['close']), 'open': _safe(lr['open']),
        'high': _safe(lr['high']), 'low': _safe(lr['low']),
        'volume': _safe(lr['volume']), 'rsi': _safe(lr['rsi'], 50.0),
        'macd': _safe(lr['macd'], 0.0), 'macd_signal': _safe(lr['macd_signal'], 0.0),
        'macd_diff': _safe(lr['macd_diff'], 0.0), 'macd_diff_pct': _safe(lr['macd_diff_pct'], 0.0),
        'atr': _safe(lr['atr'], 0.0), 'ema_9': _safe(lr['ema_9'], _safe(lr['close'])),
        'ema_21': _safe(lr['ema_21'], _safe(lr['close'])),
        'ema_crossover': int(_safe(lr['ema_crossover'], 0)),
        'volume_sma': _safe(lr['volume_sma'], _safe(lr['volume'])),
        'volume_ratio': _safe(lr['volume_ratio'], 1.0),
        'volume_trend': _safe(lr.get('volume_trend', 0), 0.0),
        'price_change': _safe(lr.get('price_change', 0), 0.0),
        'price_change_1h': _safe(lr.get('price_change_1h', 0), 0.0),
        'is_noise': bool(lr.get('is_noise', False)),
        'fake_break': bool(lr.get('fake_break', False)),
    }
