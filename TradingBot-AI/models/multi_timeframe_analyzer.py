"""
🕐 Multi-Timeframe Analyzer
تحليل متعدد الأطر الزمنية (1m, 5m, 15m) لكشف القمم والقيعان
"""

class MultiTimeframeAnalyzer:
    def __init__(self):
        print("✅ Multi-Timeframe Analyzer initialized")
    
    def analyze_peak(self, candles_5m, candles_15m, candles_1h, current_price, highest_price, 
                     volume_data_5m=None, volume_data_15m=None, volume_data_1h=None, 
                     order_book=None, macro_status='NEUTRAL'):
        """
        تحليل القمة عبر 3 أطر زمنية
        
        Args:
            candles_5m: شموع 5 دقائق (سريعة)
            candles_15m: شموع 15 دقيقة (متوسطة)
            candles_1h: شموع 1 ساعة (الاتجاه الكلي)
            current_price: السعر الحالي
            highest_price: أعلى سعر
            volume_data_*: بيانات الحجم
            order_book: دفتر الأوامر
            macro_status: حالة السوق الكلي
        
        Returns:
            dict: {
                'is_peak': bool,
                'confidence': float (0-100),
                'confirmations': int (0-3),
                'signals': list,
                'market_context': str,
                'threshold_used': float
            }
        """
        try:
            from config import (
                REALTIME_PEAK_BASE_CONFIDENCE, REALTIME_PEAK_BASE_CONFIRMATIONS,
                REALTIME_PEAK_STRONG_BULL_CONFIDENCE, REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS,
                REALTIME_PEAK_BULL_CONFIDENCE, REALTIME_PEAK_SIDEWAYS_CONFIDENCE,
                REALTIME_PEAK_BEAR_CONFIDENCE
            )
            
            # تحديد العتبة حسب السوق
            if 'STRONG_BULL' in macro_status:
                threshold = REALTIME_PEAK_STRONG_BULL_CONFIDENCE
                required_confirmations = REALTIME_PEAK_STRONG_BULL_CONFIRMATIONS
            elif 'BULL' in macro_status:
                threshold = REALTIME_PEAK_BULL_CONFIDENCE
                required_confirmations = REALTIME_PEAK_BASE_CONFIRMATIONS
            elif 'BEAR' in macro_status:
                threshold = REALTIME_PEAK_BEAR_CONFIDENCE
                required_confirmations = REALTIME_PEAK_BASE_CONFIRMATIONS
            else:
                threshold = REALTIME_PEAK_SIDEWAYS_CONFIDENCE
                required_confirmations = REALTIME_PEAK_BASE_CONFIRMATIONS
            
            # تحليل كل إطار زمني
            tf_5m = self._analyze_single_timeframe_peak(candles_5m, current_price, highest_price, volume_data_5m, order_book, '5m')
            tf_15m = self._analyze_single_timeframe_peak(candles_15m, current_price, highest_price, volume_data_15m, order_book, '15m')
            tf_1h = self._analyze_single_timeframe_peak(candles_1h, current_price, highest_price, volume_data_1h, order_book, '1h')
            
            # حساب الثقة الموزونة
            weighted_confidence = (
                tf_5m['confidence'] * 0.4 +   # 5m: 40% (سريع ومتوازن)
                tf_15m['confidence'] * 0.35 +  # 15m: 35% (تأكيد متوسط)
                tf_1h['confidence'] * 0.25     # 1h: 25% (الاتجاه الكلي)
            )
            
            # عدد التأكيدات
            confirmations = sum([
                1 if tf_5m['is_peak'] else 0,
                1 if tf_15m['is_peak'] else 0,
                1 if tf_1h['is_peak'] else 0
            ])
            
            # تعديل الثقة حسب السوق
            if 'BULL' in macro_status:
                weighted_confidence *= 0.9  # تقليل الثقة في السوق الصاعد
            elif 'BEAR' in macro_status:
                weighted_confidence *= 1.1  # زيادة الثقة في السوق الهابط
            
            weighted_confidence = min(100, weighted_confidence)
            
            # جمع الإشارات
            signals = []
            if tf_5m['is_peak']: signals.append(f"5m: {tf_5m['reason']}")
            if tf_15m['is_peak']: signals.append(f"15m: {tf_15m['reason']}")
            if tf_1h['is_peak']: signals.append(f"1h: {tf_1h['reason']}")
            
            # القرار النهائي
            is_peak = weighted_confidence >= threshold and confirmations >= required_confirmations
            
            return {
                'is_peak': is_peak,
                'confidence': weighted_confidence,
                'confirmations': confirmations,
                'signals': signals,
                'market_context': macro_status,
                'threshold_used': threshold,
                'timeframes': {
                    '5m': tf_5m,
                    '15m': tf_15m,
                    '1h': tf_1h
                }
            }
            
        except Exception as e:
            print(f"⚠️ Multi-TF Peak error: {e}")
            return {
                'is_peak': False,
                'confidence': 0,
                'confirmations': 0,
                'signals': [],
                'market_context': macro_status,
                'threshold_used': 60
            }
    
    def analyze_bottom(self, candles_5m, candles_15m, candles_1h, current_price,
                       volume_data_5m=None, volume_data_15m=None, volume_data_1h=None,
                       order_book=None, macro_status='NEUTRAL'):
        """
        تحليل القاع عبر 3 أطر زمنية
        
        Args:
            candles_5m: شموع 5 دقائق (سريعة)
            candles_15m: شموع 15 دقيقة (متوسطة)
            candles_1h: شموع 1 ساعة (الاتجاه الكلي)
            current_price: السعر الحالي
            volume_data_*: بيانات الحجم
            order_book: دفتر الأوامر
            macro_status: حالة السوق الكلي
        
        Returns:
            dict: {
                'is_bottom': bool,
                'confidence': float (0-100),
                'confirmations': int (0-3),
                'signals': list,
                'market_context': str,
                'threshold_used': float
            }
        """
        try:
            from config import (
                REALTIME_BOTTOM_BASE_CONFIDENCE, REALTIME_BOTTOM_BASE_CONFIRMATIONS,
                REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE, REALTIME_BOTTOM_BULL_CONFIDENCE,
                REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE, REALTIME_BOTTOM_BEAR_CONFIDENCE,
                REALTIME_BOTTOM_BEAR_CONFIRMATIONS
            )
            
            # تحديد العتبة حسب السوق
            if 'STRONG_BULL' in macro_status:
                threshold = REALTIME_BOTTOM_STRONG_BULL_CONFIDENCE
                required_confirmations = REALTIME_BOTTOM_BASE_CONFIRMATIONS
            elif 'BULL' in macro_status:
                threshold = REALTIME_BOTTOM_BULL_CONFIDENCE
                required_confirmations = REALTIME_BOTTOM_BASE_CONFIRMATIONS
            elif 'BEAR' in macro_status:
                threshold = REALTIME_BOTTOM_BEAR_CONFIDENCE
                required_confirmations = REALTIME_BOTTOM_BEAR_CONFIRMATIONS
            else:
                threshold = REALTIME_BOTTOM_SIDEWAYS_CONFIDENCE
                required_confirmations = REALTIME_BOTTOM_BASE_CONFIRMATIONS
            
            # تحليل كل إطار زمني
            tf_5m = self._analyze_single_timeframe_bottom(candles_5m, current_price, volume_data_5m, order_book, '5m')
            tf_15m = self._analyze_single_timeframe_bottom(candles_15m, current_price, volume_data_15m, order_book, '15m')
            tf_1h = self._analyze_single_timeframe_bottom(candles_1h, current_price, volume_data_1h, order_book, '1h')
            
            # حساب الثقة الموزونة
            weighted_confidence = (
                tf_5m['confidence'] * 0.4 +   # 5m: 40%
                tf_15m['confidence'] * 0.35 +  # 15m: 35%
                tf_1h['confidence'] * 0.25     # 1h: 25%
            )
            
            # عدد التأكيدات
            confirmations = sum([
                1 if tf_5m['is_bottom'] else 0,
                1 if tf_15m['is_bottom'] else 0,
                1 if tf_1h['is_bottom'] else 0
            ])
            
            # تعديل الثقة حسب السوق
            if 'BULL' in macro_status:
                weighted_confidence *= 1.1  # زيادة الثقة في السوق الصاعد
            elif 'BEAR' in macro_status:
                weighted_confidence *= 0.9  # تقليل الثقة في السوق الهابط
            
            weighted_confidence = min(100, weighted_confidence)
            
            # جمع الإشارات
            signals = []
            if tf_5m['is_bottom']: signals.append(f"5m: {tf_5m['reason']}")
            if tf_15m['is_bottom']: signals.append(f"15m: {tf_15m['reason']}")
            if tf_1h['is_bottom']: signals.append(f"1h: {tf_1h['reason']}")
            
            # القرار النهائي
            is_bottom = weighted_confidence >= threshold and confirmations >= required_confirmations
            
            return {
                'is_bottom': is_bottom,
                'confidence': weighted_confidence,
                'confirmations': confirmations,
                'signals': signals,
                'market_context': macro_status,
                'threshold_used': threshold,
                'timeframes': {
                    '5m': tf_5m,
                    '15m': tf_15m,
                    '1h': tf_1h
                }
            }
            
        except Exception as e:
            print(f"⚠️ Multi-TF Bottom error: {e}")
            return {
                'is_bottom': False,
                'confidence': 0,
                'confirmations': 0,
                'signals': [],
                'market_context': macro_status,
                'threshold_used': 60
            }
    
    def _analyze_single_timeframe_peak(self, candles, current_price, highest_price, volume_data, order_book, timeframe):
        """تحليل قمة في إطار زمني واحد"""
        try:
            if not candles or len(candles) < 3:
                return {'is_peak': False, 'confidence': 0, 'reason': 'Not enough data'}
            
            confidence = 0
            reasons = []
            
            # 1. فحص الانخفاض من القمة
            drop_from_peak = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
            if drop_from_peak > 1.0:
                confidence += 30
                reasons.append(f"Drop {drop_from_peak:.1f}%")
            
            # 2. فحص الشموع الأخيرة
            last_3 = candles[-3:]
            bearish_candles = sum(1 for c in last_3 if c.get('close', 0) < c.get('open', 0))
            if bearish_candles >= 2:
                confidence += 25
                reasons.append(f"{bearish_candles} bearish candles")
            
            # 3. فحص الحجم
            if volume_data and len(volume_data) >= 3:
                avg_volume = sum(volume_data[-5:]) / 5 if len(volume_data) >= 5 else sum(volume_data) / len(volume_data)
                current_volume = volume_data[-1]
                if current_volume < avg_volume * 0.7:
                    confidence += 20
                    reasons.append("Volume drop")
            
            # 4. فحص Order Book
            if order_book and order_book.get('asks') and order_book.get('bids'):
                sell_pressure = sum(a[1] for a in order_book['asks'][:10])
                buy_pressure = sum(b[1] for b in order_book['bids'][:10])
                if sell_pressure > buy_pressure * 1.3:
                    confidence += 25
                    reasons.append("Sell wall")
            
            is_peak = confidence >= 50
            
            return {
                'is_peak': is_peak,
                'confidence': confidence,
                'reason': ', '.join(reasons) if reasons else 'No signals'
            }
            
        except Exception as e:
            return {'is_peak': False, 'confidence': 0, 'reason': f'Error: {e}'}
    
    def _analyze_single_timeframe_bottom(self, candles, current_price, volume_data, order_book, timeframe):
        """تحليل قاع في إطار زمني واحد"""
        try:
            if not candles or len(candles) < 3:
                return {'is_bottom': False, 'confidence': 0, 'reason': 'Not enough data'}
            
            confidence = 0
            reasons = []
            
            # 1. فحص الارتداد من القاع
            last_5 = candles[-5:]
            lowest = min(c.get('low', float('inf')) for c in last_5)
            bounce = ((current_price - lowest) / lowest) * 100 if lowest > 0 else 0
            if bounce > 0.5:
                confidence += 30
                reasons.append(f"Bounce {bounce:.1f}%")
            
            # 2. فحص الشموع الأخيرة
            last_3 = candles[-3:]
            bullish_candles = sum(1 for c in last_3 if c.get('close', 0) > c.get('open', 0))
            if bullish_candles >= 2:
                confidence += 25
                reasons.append(f"{bullish_candles} bullish candles")
            
            # 3. فحص الحجم
            if volume_data and len(volume_data) >= 3:
                avg_volume = sum(volume_data[-5:]) / 5 if len(volume_data) >= 5 else sum(volume_data) / len(volume_data)
                current_volume = volume_data[-1]
                if current_volume > avg_volume * 1.5:
                    confidence += 20
                    reasons.append("Volume spike")
            
            # 4. فحص Order Book
            if order_book and order_book.get('bids') and order_book.get('asks'):
                buy_pressure = sum(b[1] for b in order_book['bids'][:10])
                sell_pressure = sum(a[1] for a in order_book['asks'][:10])
                if buy_pressure > sell_pressure * 1.3:
                    confidence += 25
                    reasons.append("Buy wall")
            
            is_bottom = confidence >= 50
            
            return {
                'is_bottom': is_bottom,
                'confidence': confidence,
                'reason': ', '.join(reasons) if reasons else 'No signals'
            }
            
        except Exception as e:
            return {'is_bottom': False, 'confidence': 0, 'reason': f'Error: {e}'}
