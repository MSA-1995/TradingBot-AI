"""
🎯 Real-time Price Action Analyzer
كشف القمم والقيعان بشكل فوري
"""

from datetime import datetime, timezone

class RealTimePriceAction:
    def __init__(self):
        self.stalling_tracker = {}
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
    def analyze_peak_signals(self, symbol, candles, current_price, highest_price=None, volume_data=None, order_book=None):
        """🔴 كشف القمة السريع"""
        if not candles or len(candles) < 2:
            return {'is_peak': False, 'confidence': 0, 'signals': []}
        
        signals = []
        confidence = 0
        
        # 0. Highest Price Check
        if highest_price:
            distance = ((highest_price - current_price) / highest_price) * 100
            if distance > 2.0:
                return {'is_peak': False, 'confidence': 0, 'signals': ['Not at peak']}
            elif distance < 0.5:
                signals.append(f"At Peak: {distance:.1f}%")
                confidence += 20
        
        # 1. Upper Wick
        upper = self._detect_upper_rejection(candles[-1], current_price)
        if upper['detected']:
            signals.append(f"Upper Rejection: {upper['strength']:.0f}%")
            confidence += upper['strength'] * 0.25
        
        # 2. Volume Drop
        if volume_data:
            vol = self._analyze_volume_drop(volume_data)
            if vol['detected']:
                signals.append(f"Volume Drop: {vol['strength']:.0f}%")
                confidence += vol['strength'] * 0.2
        
        # 3. Order Book Resistance
        if order_book:
            ob = self._analyze_sell_wall(order_book)
            if ob['detected']:
                signals.append(f"Sell Wall: {ob['strength']:.0f}%")
                confidence += ob['strength'] * 0.15
        
        # 4. RSI Overbought
        rsi = self._calculate_rsi(candles)
        if rsi > 70:
            signals.append(f"RSI: {rsi:.0f}")
            confidence += min(20, (rsi - 70) * 0.5)
        
        # 5. MACD Bearish
        macd = self._calculate_macd(candles)
        if macd['signal'] == 'bearish':
            signals.append(f"MACD Bearish")
            confidence += 15
        
        # 6. Stalling
        stalling = self._detect_stalling(symbol, current_price)
        if stalling['detected']:
            signals.append(f"Stalling: {stalling['duration']:.0f}min")
            confidence += min(20, stalling['duration'] * 3)
        
        # 7. Momentum Loss
        momentum = self._detect_momentum_loss(candles)
        if momentum['detected']:
            signals.append(f"Momentum Loss: {momentum['strength']:.0f}%")
            confidence += momentum['strength'] * 0.2
        
        self._cleanup_stalling_tracker()
        confidence = min(100, confidence)
        is_peak = confidence >= 65 and len(signals) >= 3
        
        return {'is_peak': is_peak, 'confidence': confidence, 'signals': signals}
    
    def analyze_bottom_signals(self, symbol, candles, current_price, volume_data=None, order_book=None):
        """🟢 كشف القاع السريع"""
        if not candles or len(candles) < 2:
            return {'is_bottom': False, 'confidence': 0, 'signals': []}
        
        signals = []
        confidence = 0
        
        # 1. Lower Wick
        lower = self._detect_lower_rejection(candles[-1], current_price)
        if lower['detected']:
            signals.append(f"Lower Rejection: {lower['strength']:.0f}%")
            confidence += lower['strength'] * 0.25
        
        # 2. Volume Spike
        if volume_data:
            vol = self._analyze_volume_spike(volume_data)
            if vol['detected']:
                signals.append(f"Volume Spike: +{vol['strength']:.0f}%")
                confidence += vol['strength'] * 0.2
        
        # 3. Order Book Support
        if order_book:
            ob = self._analyze_buy_wall(order_book)
            if ob['detected']:
                signals.append(f"Buy Wall: {ob['strength']:.0f}%")
                confidence += ob['strength'] * 0.15
        
        # 4. RSI Oversold
        rsi = self._calculate_rsi(candles)
        if rsi < 30:
            signals.append(f"RSI: {rsi:.0f}")
            confidence += min(20, (30 - rsi) * 0.5)
        
        # 5. MACD Bullish
        macd = self._calculate_macd(candles)
        if macd['signal'] == 'bullish':
            signals.append(f"MACD Bullish")
            confidence += 15
        
        # 6. Bounce
        bounce = self._detect_bounce(current_price, candles)
        if bounce['detected']:
            signals.append(f"Bounce: +{bounce['strength']:.1f}%")
            confidence += min(20, bounce['strength'] * 10)
        
        # 7. Momentum Gain
        momentum = self._detect_momentum_gain(candles)
        if momentum['detected']:
            signals.append(f"Momentum Gain: {momentum['strength']:.0f}%")
            confidence += momentum['strength'] * 0.2
        
        confidence = min(100, confidence)
        is_bottom = confidence >= 65 and len(signals) >= 3
        
        return {'is_bottom': is_bottom, 'confidence': confidence, 'signals': signals}
    
    def analyze_multi_timeframe_peak(self, symbol, candles_1m, candles_5m, candles_15m, current_price, highest_price=None, volume_data_1m=None, volume_data_5m=None, volume_data_15m=None, order_book=None, macro_status=None):
        """🎯 Multi-Timeframe Peak Detection (1m + 5m + 15m) + Market Context"""
        if not candles_1m or not candles_5m or not candles_15m:
            return {'is_peak': False, 'confidence': 0, 'signals': [], 'timeframes': {}}
        
        # Analyze each timeframe
        tf_1m = self.analyze_peak_signals(symbol, candles_1m, current_price, highest_price, volume_data_1m, order_book)
        tf_5m = self.analyze_peak_signals(symbol, candles_5m, current_price, highest_price, volume_data_5m, order_book)
        tf_15m = self.analyze_peak_signals(symbol, candles_15m, current_price, highest_price, volume_data_15m, order_book)
        
        # Count confirmations
        confirmations = sum([tf_1m['is_peak'], tf_5m['is_peak'], tf_15m['is_peak']])
        
        # Calculate weighted confidence
        confidence = (
            tf_1m['confidence'] * 0.3 +  # 1m: 30% weight (fast signals)
            tf_5m['confidence'] * 0.4 +  # 5m: 40% weight (balanced)
            tf_15m['confidence'] * 0.3   # 15m: 30% weight (trend confirmation)
        )
        
        # 🌍 Market Context Adjustment
        market_modifier = 0
        if macro_status:
            if 'STRONG_BULL' in macro_status:
                market_modifier = -10  # سوق صاعد قوي = القمة أبعد
            elif 'BULL' in macro_status:
                market_modifier = -5   # سوق صاعد = حذر من البيع المبكر
            elif 'BEAR' in macro_status:
                market_modifier = +15  # سوق هابط = بيع أسرع
            elif 'SIDEWAYS' in macro_status:
                market_modifier = 0    # سوق جانبي = عادي
        
        confidence += market_modifier
        
        # Collect all signals
        all_signals = []
        if market_modifier != 0:
            market_label = "Bull Market" if market_modifier < 0 else "Bear Market"
            all_signals.append(f"Market: {market_label} ({market_modifier:+d})")
        
        if tf_1m['signals']:
            all_signals.append(f"1m: {', '.join(tf_1m['signals'][:2])}")
        if tf_5m['signals']:
            all_signals.append(f"5m: {', '.join(tf_5m['signals'][:2])}")
        if tf_15m['signals']:
            all_signals.append(f"15m: {', '.join(tf_15m['signals'][:2])}")
        
        # 🎯 Dynamic Thresholds from Config
        from config import (
            REALTIME_PEAK_BASE_CONFIDENCE, REALTIME_PEAK_BASE_CONFIRMATIONS,
            REALTIME_PEAK_STRONG_BULL_CONFIDENCE, REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS,
            REALTIME_PEAK_BULL_CONFIDENCE, REALTIME_PEAK_SIDEWAYS_CONFIDENCE,
            REALTIME_PEAK_BEAR_CONFIDENCE
        )
        
        min_confidence_required = REALTIME_PEAK_BASE_CONFIDENCE
        min_confirmations_required = REALTIME_PEAK_BASE_CONFIRMATIONS
        
        if macro_status:
            if 'STRONG_BULL' in macro_status:
                min_confidence_required = REALTIME_PEAK_STRONG_BULL_CONFIDENCE
                min_confirmations_required = REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS
            elif 'BULL' in macro_status:
                min_confidence_required = REALTIME_PEAK_BULL_CONFIDENCE
            elif 'BEAR' in macro_status:
                min_confidence_required = REALTIME_PEAK_BEAR_CONFIDENCE
            elif 'SIDEWAYS' in macro_status:
                min_confidence_required = REALTIME_PEAK_SIDEWAYS_CONFIDENCE
        
        # Decision logic with dynamic thresholds
        is_peak = False
        if confirmations >= 3 and confidence >= min_confidence_required:
            # All timeframes agree - STRONG signal
            is_peak = True
            confidence = min(100, confidence + 15)
            all_signals.insert(0, "✅ All TF Confirmed")
        elif confirmations >= min_confirmations_required and confidence >= min_confidence_required:
            # Dynamic threshold met
            is_peak = True
            all_signals.insert(0, f"⚠️ {confirmations}/3 TF Confirmed")
        elif confirmations == 1 and confidence >= 85:
            # 1 timeframe but very high confidence
            is_peak = True
            all_signals.insert(0, "⚡ 1 TF High Confidence")
        
        return {
            'is_peak': is_peak,
            'confidence': round(confidence, 1),
            'signals': all_signals,
            'confirmations': confirmations,
            'market_context': macro_status,
            'threshold_used': min_confidence_required,
            'timeframes': {
                '1m': {'confidence': tf_1m['confidence'], 'is_peak': tf_1m['is_peak']},
                '5m': {'confidence': tf_5m['confidence'], 'is_peak': tf_5m['is_peak']},
                '15m': {'confidence': tf_15m['confidence'], 'is_peak': tf_15m['is_peak']}
            }
        }
    
    def analyze_multi_timeframe_bottom(self, symbol, candles_1m, candles_5m, candles_15m, current_price, volume_data_1m=None, volume_data_5m=None, volume_data_15m=None, order_book=None, macro_status=None):
        """🎯 Multi-Timeframe Bottom Detection (1m + 5m + 15m) + Market Context"""
        if not candles_1m or not candles_5m or not candles_15m:
            return {'is_bottom': False, 'confidence': 0, 'signals': [], 'timeframes': {}}
        
        # Analyze each timeframe
        tf_1m = self.analyze_bottom_signals(symbol, candles_1m, current_price, volume_data_1m, order_book)
        tf_5m = self.analyze_bottom_signals(symbol, candles_5m, current_price, volume_data_5m, order_book)
        tf_15m = self.analyze_bottom_signals(symbol, candles_15m, current_price, volume_data_15m, order_book)
        
        # Count confirmations
        confirmations = sum([tf_1m['is_bottom'], tf_5m['is_bottom'], tf_15m['is_bottom']])
        
        # Calculate weighted confidence
        confidence = (
            tf_1m['confidence'] * 0.3 +  # 1m: 30% weight
            tf_5m['confidence'] * 0.4 +  # 5m: 40% weight
            tf_15m['confidence'] * 0.3   # 15m: 30% weight
        )
        
        # 🌍 Market Context Adjustment
        market_modifier = 0
        if macro_status:
            if 'STRONG_BULL' in macro_status:
                market_modifier = +15  # سوق صاعد قوي = القاع فرصة ذهبية
            elif 'BULL' in macro_status:
                market_modifier = +10  # سوق صاعد = شراء بثقة
            elif 'BEAR' in macro_status:
                market_modifier = -15  # سوق هابط = حذر (ممكن ينزل أكثر)
            elif 'SIDEWAYS' in macro_status:
                market_modifier = 0    # سوق جانبي = عادي
        
        confidence += market_modifier
        
        # Collect all signals
        all_signals = []
        if market_modifier != 0:
            market_label = "Bull Market" if market_modifier > 0 else "Bear Market"
            all_signals.append(f"Market: {market_label} ({market_modifier:+d})")
        
        if tf_1m['signals']:
            all_signals.append(f"1m: {', '.join(tf_1m['signals'][:2])}")
        if tf_5m['signals']:
            all_signals.append(f"5m: {', '.join(tf_5m['signals'][:2])}")
        if tf_15m['signals']:
            all_signals.append(f"15m: {', '.join(tf_15m['signals'][:2])}")
        
        # 🎯 Dynamic Thresholds from Config
        from config import (
            REALTIME_BOTTOM_BASE_CONFIDENCE, REALTIME_BOTTOM_BASE_CONFIRMATIONS,
            REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE, REALTIME_BOTTOM_BULL_CONFIDENCE,
            REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE, REALTIME_BOTTOM_BEAR_CONFIDENCE,
            REALTIME_BOTTOM_BEAR_CONFIRMATIONS
        )
        
        min_confidence_required = REALTIME_BOTTOM_BASE_CONFIDENCE
        min_confirmations_required = REALTIME_BOTTOM_BASE_CONFIRMATIONS
        
        if macro_status:
            if 'STRONG_BULL' in macro_status:
                min_confidence_required = REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE
            elif 'BULL' in macro_status:
                min_confidence_required = REALTIME_BOTTOM_BULL_CONFIDENCE
            elif 'BEAR' in macro_status:
                min_confidence_required = REALTIME_BOTTOM_BEAR_CONFIDENCE
                min_confirmations_required = REALTIME_BOTTOM_BEAR_CONFIRMATIONS
            elif 'SIDEWAYS' in macro_status:
                min_confidence_required = REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE
        
        # Decision logic with dynamic thresholds
        is_bottom = False
        if confirmations >= 3 and confidence >= min_confidence_required:
            # All timeframes agree - STRONG signal
            is_bottom = True
            confidence = min(100, confidence + 15)
            all_signals.insert(0, "✅ All TF Confirmed")
        elif confirmations >= min_confirmations_required and confidence >= min_confidence_required:
            # Dynamic threshold met
            is_bottom = True
            all_signals.insert(0, f"⚠️ {confirmations}/3 TF Confirmed")
        elif confirmations == 1 and confidence >= 85:
            # 1 timeframe but very high confidence
            is_bottom = True
            all_signals.insert(0, "⚡ 1 TF High Confidence")
        
        return {
            'is_bottom': is_bottom,
            'confidence': round(confidence, 1),
            'signals': all_signals,
            'confirmations': confirmations,
            'market_context': macro_status,
            'threshold_used': min_confidence_required,
            'timeframes': {
                '1m': {'confidence': tf_1m['confidence'], 'is_bottom': tf_1m['is_bottom']},
                '5m': {'confidence': tf_5m['confidence'], 'is_bottom': tf_5m['is_bottom']},
                '15m': {'confidence': tf_15m['confidence'], 'is_bottom': tf_15m['is_bottom']}
            }
        }
    
    def analyze_stop_loss_trigger(self, candles, current_price, highest_price, stop_threshold):
        """🛡️ كشف Stop Loss المبكر"""
        if not candles or len(candles) < 2:
            return {'trigger_soon': False, 'confidence': 0}
        
        drop_from_peak = ((highest_price - current_price) / highest_price) * 100
        remaining = stop_threshold - drop_from_peak
        
        momentum = self._calculate_drop_momentum(candles)
        pressure = self._calculate_sell_pressure(candles)
        
        time_to_stop = (remaining / momentum) * 10 if momentum > 0 else 999
        
        trigger = time_to_stop < 5 or (remaining < 1.0 and pressure > 70)
        confidence = min(100, (stop_threshold - remaining) * 20 + pressure * 0.3) if trigger else 0
        
        return {'trigger_soon': trigger, 'confidence': confidence, 'time_estimate': time_to_stop}
    
    def _detect_upper_rejection(self, candle, current_price):
        try:
            high = candle.get('high', current_price)
            close = candle.get('close', current_price)
            open_price = candle.get('open', current_price)
            
            upper_wick = high - max(close, open_price)
            total_range = high - min(close, open_price)
            
            if total_range == 0:
                return {'detected': False, 'strength': 0}
            
            wick_ratio = (upper_wick / total_range) * 100
            detected = wick_ratio > 60
            
            return {'detected': detected, 'strength': min(100, wick_ratio)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _detect_lower_rejection(self, candle, current_price):
        try:
            low = candle.get('low', current_price)
            close = candle.get('close', current_price)
            open_price = candle.get('open', current_price)
            
            lower_wick = min(close, open_price) - low
            total_range = max(close, open_price) - low
            
            if total_range == 0:
                return {'detected': False, 'strength': 0}
            
            wick_ratio = (lower_wick / total_range) * 100
            detected = wick_ratio > 60
            
            return {'detected': detected, 'strength': min(100, wick_ratio)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _detect_stalling(self, symbol, current_price):
        try:
            now = datetime.now(timezone.utc)
            
            if symbol not in self.stalling_tracker:
                self.stalling_tracker[symbol] = {'price': current_price, 'start_time': now}
                return {'detected': False, 'duration': 0}
            
            tracker = self.stalling_tracker[symbol]
            price_change = abs((current_price - tracker['price']) / tracker['price']) * 100
            
            if price_change < 0.3:
                duration = (now - tracker['start_time']).total_seconds() / 60
                return {'detected': duration >= 3, 'duration': duration}
            else:
                self.stalling_tracker[symbol] = {'price': current_price, 'start_time': now}
                return {'detected': False, 'duration': 0}
        except:
            return {'detected': False, 'duration': 0}
    
    def _detect_momentum_loss(self, candles):
        try:
            if len(candles) < 5:
                return {'detected': False, 'strength': 0}
            
            changes = []
            for i in range(-5, -1):
                prev = candles[i-1].get('close', 0)
                curr = candles[i].get('close', 0)
                if prev > 0:
                    changes.append(((curr - prev) / prev) * 100)
            
            if not changes:
                return {'detected': False, 'strength': 0}
            
            avg = sum(changes) / len(changes)
            last = candles[-2].get('close', 0)
            current = candles[-1].get('close', 0)
            current_change = ((current - last) / last) * 100 if last > 0 else 0
            
            drop = avg - current_change
            detected = drop > 0.5 and avg > 0.3
            
            return {'detected': detected, 'strength': min(100, drop * 30)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _detect_momentum_gain(self, candles):
        try:
            if len(candles) < 5:
                return {'detected': False, 'strength': 0}
            
            changes = []
            for i in range(-5, -1):
                prev = candles[i-1].get('close', 0)
                curr = candles[i].get('close', 0)
                if prev > 0:
                    changes.append(((curr - prev) / prev) * 100)
            
            if not changes:
                return {'detected': False, 'strength': 0}
            
            avg = sum(changes) / len(changes)
            last = candles[-2].get('close', 0)
            current = candles[-1].get('close', 0)
            current_change = ((current - last) / last) * 100 if last > 0 else 0
            
            gain = current_change - avg
            detected = gain > 0.5 and current_change > 0.3
            
            return {'detected': detected, 'strength': min(100, gain * 30)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _detect_bounce(self, current_price, candles):
        try:
            if len(candles) < 3:
                return {'detected': False, 'strength': 0}
            
            lows = [c.get('low', current_price) for c in candles[-3:]]
            lowest = min(lows)
            
            bounce = ((current_price - lowest) / lowest) * 100 if lowest > 0 else 0
            
            return {'detected': bounce > 0.5, 'strength': bounce}
        except:
            return {'detected': False, 'strength': 0}
    
    def _calculate_drop_momentum(self, candles):
        try:
            if len(candles) < 3:
                return 0
            
            drops = []
            for i in range(-3, 0):
                prev = candles[i-1].get('close', 0)
                curr = candles[i].get('close', 0)
                if prev > 0:
                    drop = ((prev - curr) / prev) * 100
                    if drop > 0:
                        drops.append(drop)
            
            return sum(drops) / len(drops) if drops else 0
        except:
            return 0
    
    def _calculate_sell_pressure(self, candles):
        try:
            if len(candles) < 5:
                return 0
            
            red = 0
            for candle in candles[-5:]:
                if candle.get('close', 0) < candle.get('open', 0):
                    red += 1
            
            return (red / 5) * 100
        except:
            return 0
    
    def _analyze_volume_drop(self, volume_data):
        try:
            if len(volume_data) < 5:
                return {'detected': False, 'strength': 0}
            
            avg = sum(volume_data[-5:-1]) / 4
            current = volume_data[-1]
            
            if avg == 0:
                return {'detected': False, 'strength': 0}
            
            drop = ((avg - current) / avg) * 100
            return {'detected': drop > 30, 'strength': min(100, drop)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _analyze_volume_spike(self, volume_data):
        try:
            if len(volume_data) < 5:
                return {'detected': False, 'strength': 0}
            
            avg = sum(volume_data[-5:-1]) / 4
            current = volume_data[-1]
            
            if avg == 0:
                return {'detected': False, 'strength': 0}
            
            spike = ((current - avg) / avg) * 100
            return {'detected': spike > 50, 'strength': min(100, spike)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _analyze_sell_wall(self, order_book):
        try:
            asks = order_book.get('asks', [])
            bids = order_book.get('bids', [])
            
            if not asks or not bids:
                return {'detected': False, 'strength': 0}
            
            ask_vol = sum([float(a[1]) for a in asks[:10]])
            bid_vol = sum([float(b[1]) for b in bids[:10]])
            
            if bid_vol == 0:
                return {'detected': False, 'strength': 0}
            
            ratio = (ask_vol / bid_vol) * 100
            return {'detected': ratio > 150, 'strength': min(100, ratio - 100)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _analyze_buy_wall(self, order_book):
        try:
            asks = order_book.get('asks', [])
            bids = order_book.get('bids', [])
            
            if not asks or not bids:
                return {'detected': False, 'strength': 0}
            
            ask_vol = sum([float(a[1]) for a in asks[:10]])
            bid_vol = sum([float(b[1]) for b in bids[:10]])
            
            if ask_vol == 0:
                return {'detected': False, 'strength': 0}
            
            ratio = (bid_vol / ask_vol) * 100
            return {'detected': ratio > 150, 'strength': min(100, ratio - 100)}
        except:
            return {'detected': False, 'strength': 0}
    
    def _calculate_rsi(self, candles):
        try:
            if len(candles) < self.rsi_period + 1:
                return 50
            
            gains, losses = [], []
            for i in range(-self.rsi_period, 0):
                change = candles[i]['close'] - candles[i-1]['close']
                gains.append(max(0, change))
                losses.append(max(0, -change))
            
            avg_gain = sum(gains) / self.rsi_period
            avg_loss = sum(losses) / self.rsi_period
            
            if avg_loss == 0:
                return 100
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except:
            return 50
    
    def _calculate_macd(self, candles):
        try:
            if len(candles) < self.macd_slow + self.macd_signal:
                return {'signal': 'neutral', 'histogram': 0}
            
            closes = [c['close'] for c in candles]
            
            ema_fast = self._ema(closes, self.macd_fast)
            ema_slow = self._ema(closes, self.macd_slow)
            macd_line = ema_fast - ema_slow
            
            macd_values = []
            for i in range(len(closes) - self.macd_slow + 1):
                f = self._ema(closes[:self.macd_slow + i], self.macd_fast)
                s = self._ema(closes[:self.macd_slow + i], self.macd_slow)
                macd_values.append(f - s)
            
            signal_line = self._ema(macd_values, self.macd_signal)
            histogram = macd_line - signal_line
            
            if len(macd_values) > 1:
                prev_hist = macd_values[-2] - self._ema(macd_values[:-1], self.macd_signal)
                if histogram > 0 and prev_hist <= 0:
                    return {'signal': 'bullish', 'histogram': histogram}
                elif histogram < 0 and prev_hist >= 0:
                    return {'signal': 'bearish', 'histogram': histogram}
            
            return {'signal': 'neutral', 'histogram': histogram}
        except:
            return {'signal': 'neutral', 'histogram': 0}
    
    def _ema(self, data, period):
        try:
            if len(data) < period:
                return sum(data) / len(data)
            
            k = 2 / (period + 1)
            ema = sum(data[:period]) / period
            
            for price in data[period:]:
                ema = (price * k) + (ema * (1 - k))
            
            return ema
        except:
            return 0
    
    def _cleanup_stalling_tracker(self):
        try:
            now = datetime.now(timezone.utc)
            to_remove = []
            
            for symbol, tracker in self.stalling_tracker.items():
                age = (now - tracker['start_time']).total_seconds() / 3600
                if age > 24:
                    to_remove.append(symbol)
            
            for symbol in to_remove:
                del self.stalling_tracker[symbol]
        except:
            pass
