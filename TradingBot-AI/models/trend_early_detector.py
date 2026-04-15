"""
🎯 Trend Early Detection System - نظام الكشف المبكر عن الاتجاهات
يكتشف بداية الاتجاه قبل الجميع (قبل تأكيد EMA/MACD)
"""
import numpy as np

class TrendEarlyDetector:
    """
    يستخدم:
    - Micro Structure Analysis (تحليل الهيكل الدقيق)
    - Order Flow (تدفق الأوامر)
    - Price Action Footprints (بصمات حركة السعر)
    """
    
    def __init__(self):
        self.trend_memory = {}  # {symbol: last_trend}
    
    def detect_trend_birth(self, df, order_book=None):
        """
        كشف ولادة اتجاه جديد (قبل التأكيد الكلاسيكي)
        Returns: {'trend': 'BULLISH/BEARISH/NONE', 'strength': 0-100, 'stage': 'BIRTH/GROWTH/MATURE'}
        """
        if df is None or len(df) < 30:
            return {'trend': 'NONE', 'strength': 0, 'stage': 'UNKNOWN'}
        
        signals = []
        
        # 1. فحص الشموع الأخيرة (Micro Pattern)
        last_5 = df.tail(5)
        green_candles = sum(1 for _, row in last_5.iterrows() if row['close'] > row['open'])
        
        if green_candles >= 4:
            signals.append(('BULLISH', 20))
        elif green_candles <= 1:
            signals.append(('BEARISH', 20))
        
        # 2. Market Structure (Break of Structure)
        bos_signal = self._detect_break_of_structure(df)
        if bos_signal:
            signals.append(bos_signal)
        
        # 3. فحص القيعان والقمم (Higher Lows / Lower Highs)
        lows = df['low'].tail(10).tolist()
        highs = df['high'].tail(10).tolist()
        
        if len(lows) >= 6:
            recent_lows = lows[-3:]
            older_lows = lows[-6:-3]
            if min(recent_lows) > min(older_lows):
                signals.append(('BULLISH', 25))
        
        if len(highs) >= 6:
            recent_highs = highs[-3:]
            older_highs = highs[-6:-3]
            if max(recent_highs) < max(older_highs):
                signals.append(('BEARISH', 25))
        
        # 4. Liquidity Sweep Detection
        sweep_signal = self._detect_liquidity_sweep(df)
        if sweep_signal:
            signals.append(sweep_signal)
        
        # 5. Fair Value Gap (FVG)
        fvg_signal = self._detect_fair_value_gap(df)
        if fvg_signal:
            signals.append(fvg_signal)
        
        # 6. فحص الحجم (Volume Confirmation)
        volumes = df['volume'].tail(10).tolist()
        if len(volumes) >= 5:
            recent_vol = np.mean(volumes[-3:])
            older_vol = np.mean(volumes[-10:-3])
            
            if recent_vol > older_vol * 1.3:
                signals.append(('VOLUME_CONFIRM', 15))
        
        # 7. فحص Order Book (إذا متوفر)
        if order_book and order_book.get('bids') and order_book.get('asks'):
            bid_depth = sum(b[1] for b in order_book['bids'][:10])
            ask_depth = sum(a[1] for a in order_book['asks'][:10])
            
            ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0
            
            if ratio > 1.5:
                signals.append(('BULLISH', 20))
            elif ratio < 0.67:
                signals.append(('BEARISH', 20))
        
        # 8. تجميع الإشارات
        bullish_score = sum(s[1] for s in signals if s[0] in ['BULLISH', 'VOLUME_CONFIRM', 'BOS_BULLISH', 'SWEEP_BULLISH', 'FVG_BULLISH'])
        bearish_score = sum(s[1] for s in signals if s[0] in ['BEARISH', 'BOS_BEARISH', 'SWEEP_BEARISH', 'FVG_BEARISH'])
        
        if bullish_score > bearish_score and bullish_score >= 40:
            trend = 'BULLISH'
            strength = min(100, bullish_score)
        elif bearish_score > bullish_score and bearish_score >= 40:
            trend = 'BEARISH'
            strength = min(100, bearish_score)
        else:
            trend = 'NONE'
            strength = 0
        
        stage = self._determine_stage(df, trend, strength)
        
        return {
            'trend': trend,
            'strength': strength,
            'stage': stage,
            'signals': signals,
            'confidence': self._calculate_confidence(signals)
        }
    
    def _determine_stage(self, df, trend, strength):
        """تحديد مرحلة الاتجاه"""
        if trend == 'NONE':
            return 'UNKNOWN'
        
        # فحص كم شمعة مضت على بداية الاتجاه
        last_10 = df.tail(10)
        
        if trend == 'BULLISH':
            green_count = sum(1 for _, row in last_10.iterrows() if row['close'] > row['open'])
            if green_count <= 3:
                return 'BIRTH'  # بداية الاتجاه
            elif green_count <= 6:
                return 'GROWTH'  # نمو الاتجاه
            else:
                return 'MATURE'  # اتجاه ناضج (قد ينعكس قريباً)
        else:
            red_count = sum(1 for _, row in last_10.iterrows() if row['close'] < row['open'])
            if red_count <= 3:
                return 'BIRTH'
            elif red_count <= 6:
                return 'GROWTH'
            else:
                return 'MATURE'
    
    def _calculate_confidence(self, signals):
        """حساب الثقة بناءً على عدد الإشارات المتوافقة"""
        if len(signals) >= 4:
            return 90
        elif len(signals) >= 3:
            return 75
        elif len(signals) >= 2:
            return 60
        else:
            return 40
    
    def is_optimal_entry(self, trend_data, current_price, df):
        """
        هل هذه نقطة دخول مثالية؟
        (في بداية الاتجاه، وليس في نهايته)
        """
        if trend_data['trend'] == 'NONE':
            return False
        
        # أفضل دخول = BIRTH أو GROWTH المبكر
        if trend_data['stage'] == 'BIRTH':
            return True
        elif trend_data['stage'] == 'GROWTH' and trend_data['strength'] < 70:
            return True
        elif trend_data['stage'] == 'MATURE':
            # اتجاه ناضج = خطر الانعكاس
            return False
        
        return False
    
    def get_trend_exhaustion_score(self, df, trend):
        """
        درجة إنهاك الاتجاه (0-100)
        100 = الاتجاه منهك ومستعد للانعكاس
        """
        if df is None or len(df) < 20:
            return 0
        
        exhaustion = 0
        
        # 1. فحص RSI
        if 'rsi' in df.columns:
            rsi = df['rsi'].iloc[-1]
            if trend == 'BULLISH' and rsi > 75:
                exhaustion += 30
            elif trend == 'BEARISH' and rsi < 25:
                exhaustion += 30
        
        # 2. فحص الحجم (هل يتناقص؟)
        volumes = df['volume'].tail(10).tolist()
        if len(volumes) >= 5:
            recent_vol = np.mean(volumes[-3:])
            older_vol = np.mean(volumes[-10:-3])
            
            if recent_vol < older_vol * 0.7:
                exhaustion += 25
        
        # 3. فحص الشموع (هل تصغر؟)
        last_5 = df.tail(5)
        candle_sizes = [abs(row['close'] - row['open']) for _, row in last_5.iterrows()]
        
        if len(candle_sizes) >= 3:
            if candle_sizes[-1] < np.mean(candle_sizes) * 0.5:
                exhaustion += 20
        
        # 4. فحص Divergence
        if 'rsi' in df.columns and len(df) >= 10:
            price_trend = df['close'].iloc[-1] - df['close'].iloc[-10]
            rsi_trend = df['rsi'].iloc[-1] - df['rsi'].iloc[-10]
            
            if trend == 'BULLISH' and price_trend > 0 and rsi_trend < 0:
                exhaustion += 25
            elif trend == 'BEARISH' and price_trend < 0 and rsi_trend > 0:
                exhaustion += 25
        
        return min(100, exhaustion)
    
    def _detect_break_of_structure(self, df):
        """كشف Break of Structure (BOS) - كسر الهيكل"""
        try:
            if len(df) < 15:
                return None
            
            highs = df['high'].tail(15).tolist()
            lows = df['low'].tail(15).tolist()
            closes = df['close'].tail(15).tolist()
            
            # Bullish BOS: كسر آخر قمة
            recent_high = max(highs[-5:])
            previous_high = max(highs[-15:-5])
            
            if closes[-1] > previous_high and recent_high > previous_high:
                return ('BOS_BULLISH', 30)
            
            # Bearish BOS: كسر آخر قاع
            recent_low = min(lows[-5:])
            previous_low = min(lows[-15:-5])
            
            if closes[-1] < previous_low and recent_low < previous_low:
                return ('BOS_BEARISH', 30)
            
            return None
        except:
            return None
    
    def _detect_liquidity_sweep(self, df):
        """كشف Liquidity Sweep - كنس السيولة"""
        try:
            if len(df) < 10:
                return None
            
            last_10 = df.tail(10)
            
            # Bullish Sweep: كسر قاع سابق ثم ارتداد سريع
            lows = last_10['low'].tolist()
            closes = last_10['close'].tolist()
            
            for i in range(len(lows) - 3):
                local_low = min(lows[i:i+3])
                if lows[-2] < local_low and closes[-1] > closes[-2]:
                    # كسر القاع ثم ارتد بقوة = Sweep
                    return ('SWEEP_BULLISH', 25)
            
            # Bearish Sweep: كسر قمة سابقة ثم هبوط سريع
            highs = last_10['high'].tolist()
            
            for i in range(len(highs) - 3):
                local_high = max(highs[i:i+3])
                if highs[-2] > local_high and closes[-1] < closes[-2]:
                    return ('SWEEP_BEARISH', 25)
            
            return None
        except:
            return None
    
    def _detect_fair_value_gap(self, df):
        """كشف Fair Value Gap (FVG) - فجوة القيمة العادلة"""
        try:
            if len(df) < 5:
                return None
            
            last_3 = df.tail(3)
            candles = last_3.to_dict('records')
            
            if len(candles) < 3:
                return None
            
            c1, c2, c3 = candles[0], candles[1], candles[2]
            
            # Bullish FVG: فجوة صعودية
            # الشمعة الثالثة low > الشمعة الأولى high
            if c3['low'] > c1['high']:
                gap_size = ((c3['low'] - c1['high']) / c1['high']) * 100
                if gap_size > 0.5:  # فجوة > 0.5%
                    return ('FVG_BULLISH', 20)
            
            # Bearish FVG: فجوة هبوطية
            if c3['high'] < c1['low']:
                gap_size = ((c1['low'] - c3['high']) / c3['high']) * 100
                if gap_size > 0.5:
                    return ('FVG_BEARISH', 20)
            
            return None
        except:
            return None
