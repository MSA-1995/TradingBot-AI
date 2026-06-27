"""Split-out analysis helpers."""



def calculate_mtf_from_5m_data(df):
    try:
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}

        df_5m           = df.tail(20).copy()
        df_5m['sma_20'] = df_5m['close'].rolling(window=20).mean()
        df_5m['sma_50'] = df_5m['close'].rolling(window=min(50, len(df_5m))).mean()
        latest_5m       = df_5m.iloc[-1]

        if   latest_5m['close'] > latest_5m['sma_20'] > latest_5m['sma_50']: scores['bullish'] += 1
        elif latest_5m['close'] < latest_5m['sma_20'] < latest_5m['sma_50']: scores['bearish'] += 1
        else:                                                                   scores['neutral'] += 1

        if len(df) >= 20:
            df_15m            = df.iloc[::3].tail(20).copy()
            df_15m['sma_20']  = df_15m['close'].rolling(window=20).mean()
            df_15m['sma_50']  = df_15m['close'].rolling(window=min(50, len(df_15m))).mean()
            if len(df_15m) > 0:
                latest_15m = df_15m.iloc[-1]
                if   latest_15m['close'] > latest_15m['sma_20'] > latest_15m['sma_50']: scores['bullish'] += 1
                elif latest_15m['close'] < latest_15m['sma_20'] < latest_15m['sma_50']: scores['bearish'] += 1
                else:                                                                     scores['neutral'] += 1

        if len(df) >= 60:
            df_1h            = df.iloc[::12].tail(20).copy()
            df_1h['sma_20']  = df_1h['close'].rolling(window=20).mean()
            df_1h['sma_50']  = df_1h['close'].rolling(window=min(50, len(df_1h))).mean()
            if len(df_1h) > 0:
                latest_1h = df_1h.iloc[-1]
                if   latest_1h['close'] > latest_1h['sma_20'] > latest_1h['sma_50']: scores['bullish'] += 1
                elif latest_1h['close'] < latest_1h['sma_20'] < latest_1h['sma_50']: scores['bearish'] += 1
                else:                                                                  scores['neutral'] += 1

        trend = max(scores, key=scores.get)
        return {'trend': trend, 'scores': scores, 'total': scores[trend]}

    except Exception as e:
        return {'trend': 'neutral', 'scores': {'bullish': 0, 'bearish': 0, 'neutral': 3}, 'total': 3}
