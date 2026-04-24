"""
🔧 Meta Utils
دوال مساعدة مستقلة - بدون dependencies خارجية
"""


# ═══════════════════════════════════════════════════
# ✅ Fallback محلي لـ EnhancedPatternRecognition
# ═══════════════════════════════════════════════════
class _EnhancedPatternRecognitionFallback:
    """Fallback محلي عندما لا يكون EnhancedPatternRecognition متاحاً"""

    def analyze_peak_hunter_pattern(self, candles: list) -> dict:
        try:
            if not candles or len(candles) < 10:
                return {'signal': 'neutral', 'reason': 'Not enough candles', 'score': 0}

            closes  = [float(c['close'])  for c in candles]
            highs   = [float(c['high'])   for c in candles]
            lows    = [float(c['low'])    for c in candles]
            volumes = [float(c['volume']) for c in candles]

            last_close  = closes[-1]
            last_volume = volumes[-1]
            avg_volume  = sum(volumes[-10:]) / 10
            vol_ratio   = last_volume / avg_volume if avg_volume > 0 else 1.0

            recent_high = max(highs[-10:])
            recent_low  = min(lows[-10:])
            price_range = recent_high - recent_low
            position    = ((last_close - recent_low) / price_range
                           if price_range > 0 else 0.5)

            momentum_3 = ((closes[-1] - closes[-4]) / closes[-4] * 100
                          if closes[-4] > 0 else 0)
            momentum_5 = ((closes[-1] - closes[-6]) / closes[-6] * 100
                          if closes[-6] > 0 else 0)

            higher_lows = (lows[-1]  > lows[-3]  > lows[-5]
                           if len(lows)  >= 5 else False)
            lower_highs = (highs[-1] < highs[-3] < highs[-5]
                           if len(highs) >= 5 else False)

            buy_signals  = 0
            sell_signals = 0
            reasons      = []

            # ── إشارات الشراء ──
            if position < 0.25:
                buy_signals += 2
                reasons.append("Price near bottom")
            if momentum_3 > 0.5 and momentum_5 < 0:
                buy_signals += 1
                reasons.append("Momentum reversing up")
            if higher_lows:
                buy_signals += 1
                reasons.append("Higher lows forming")
            if vol_ratio > 1.5 and last_close > closes[-2]:
                buy_signals += 1
                reasons.append(f"Volume surge {vol_ratio:.1f}x")

            # ── إشارات البيع ──
            if position > 0.75:
                sell_signals += 2
                reasons.append("Price near top")
            if momentum_3 < -0.5 and momentum_5 > 0:
                sell_signals += 1
                reasons.append("Momentum reversing down")
            if lower_highs:
                sell_signals += 1
                reasons.append("Lower highs forming")
            if vol_ratio > 1.5 and last_close < closes[-2]:
                sell_signals += 1
                reasons.append(f"Volume surge down {vol_ratio:.1f}x")

            reason_str = " | ".join(reasons) if reasons else "No clear pattern"

            if buy_signals >= 3 and buy_signals > sell_signals:
                return {'signal': 'buy',     'reason': reason_str, 'score': buy_signals}
            elif sell_signals >= 3 and sell_signals > buy_signals:
                return {'signal': 'sell',    'reason': reason_str, 'score': sell_signals}
            else:
                return {'signal': 'neutral', 'reason': reason_str, 'score': 0}

        except Exception as e:
            return {'signal': 'neutral', 'reason': f'Error: {e}', 'score': 0}


# ═══════════════════════════════════════════════════
# ✅ دوال مساعدة ثابتة
# ═══════════════════════════════════════════════════

def extract_volumes(candles: list, lookback: int = 10) -> list | None:
    """استخراج بيانات الحجم من الشموع"""
    if len(candles) >= lookback:
        return [c.get('volume', 0) for c in candles[-lookback:]]
    return None


def adjust_threshold_by_forecasts(threshold: float,
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


def get_meta_feature_names() -> list[str]:
    """أسماء الميزات (48 ميزة) لنموذج meta_trading"""
    return [
        # Technical (5)
        'rsi', 'macd_diff', 'volume_ratio', 'price_momentum', 'atr',
        # News (6)
        'news_score', 'news_pos', 'news_neg', 'news_total',
        'news_ratio', 'has_news',
        # Sentiment (5)
        'sent_score', 'fear_greed', 'fear_greed_norm',
        'is_fearful', 'is_greedy',
        # Liquidity (4)
        'liq_score', 'depth_ratio', 'price_impact', 'good_liq',
        # Smart Money (2)
        'whale_activity', 'exchange_inflow',
        # Social (2)
        'social_volume', 'market_sentiment',
        # Consultants (3)
        'consensus', 'buy_count', 'sell_count',
        # Derived (5)
        'risk_score', 'opportunity', 'market_quality',
        'momentum_strength', 'volatility_level',
        # Symbol Memory Basic (5)
        'sym_win_rate', 'sym_avg_profit', 'sym_trap_count',
        'sym_total', 'sym_is_reliable',
        # Symbol Memory Advanced (7)
        'sym_sentiment_avg', 'sym_whale_avg',
        'sym_profit_loss_ratio', 'sym_volume_trend',
        'sym_panic_avg', 'sym_optimism_avg', 'sym_smart_stop_loss',
        # Symbol Memory Boost (4)
        'sym_courage_boost', 'sym_time_memory',
        'sym_pattern_score', 'sym_win_rate_boost',
        # Context (1)
        'hours_held'
    ]


def safe_float(value, default: float = 0.0) -> float:
    """تحويل آمن لـ float"""
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default