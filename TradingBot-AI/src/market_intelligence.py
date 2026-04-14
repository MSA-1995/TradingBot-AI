"""
🧠 Market Intelligence Module
يجمع 3 أنظمة في ملف واحد:
1. Market Regime Detection
2. Flash Crash Protection
3. Time Analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
import math


# ================================================================
# 📊 1. MARKET REGIME DETECTION
# ================================================================

class MarketRegimeDetector:
    """
    يكشف 5 حالات للسوق:
    1. STRONG_UPTREND - ترند صاعد قوي
    2. STRONG_DOWNTREND - ترند هابط قوي
    3. HIGH_VOLATILITY - تقلبات عالية
    4. LOW_VOLATILITY - تقلبات منخفضة
    5. RANGING - سوق ثابت
    """
    
    def __init__(self):
        self.adx_period = 14
        self.atr_period = 14
        self.atr_lookback = 50
    
    def detect(self, df):
        """ يحلل البيانات ويرجع حالة السوق """
        if df is None or len(df) < 20:
            return self._default_regime()
        
        try:
            adx = self._calculate_adx(df)
            atr = self._calculate_atr(df)
            atr_avg = df['atr_avg'].iloc[-1] if 'atr_avg' in df.columns else atr
            trend_strength = self._get_trend_strength(df)
            
            regime = self._classify_regime(adx, atr, atr_avg, trend_strength)
            
            return {
                'regime': regime['name'],
                'description': regime['description'],
                'trading_advice': regime['advice'],
                'adx': round(adx, 2),
                'atr': round(atr, 4),
                'atr_avg': round(atr_avg, 4),
                'trend_strength': trend_strength,
                'volatility_ratio': round(atr / atr_avg if atr_avg > 0 else 1, 2),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Market Regime Error: {e}")
            return self._default_regime()
    
    def _calculate_adx(self, df):
        """حساب ADX"""
        try:
            high, low, close = df['high'], df['low'], df['close']
            
            up_move = high.diff()
            down_move = -low.diff()
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.rolling(self.atr_period).mean()
            plus_di = 100 * (pd.Series(plus_dm).rolling(self.adx_period).mean() / atr)
            minus_di = 100 * (pd.Series(minus_dm).rolling(self.adx_period).mean() / atr)
            
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            adx = dx.rolling(self.adx_period).mean()
            
            return adx.iloc[-1] if not adx.empty else 20
        except Exception as e:
            print(f"⚠️ ADX calculation error: {e}")
            return 20
    
    def _calculate_atr(self, df):
        """حساب ATR"""
        try:
            high, low, close = df['high'], df['low'], df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.rolling(self.atr_period).mean()
            df['atr_avg'] = atr.rolling(self.atr_lookback).mean()
            
            return atr.iloc[-1] if not atr.empty else 0
        except:
            return 0
    
    def _get_trend_strength(self, df):
        """تحديد قوة الاتجاه"""
        try:
            sma_20 = df['close'].rolling(20).mean()
            sma_50 = df['close'].rolling(min(50, len(df))).mean()
            current_price = df['close'].iloc[-1]
            
            if sma_20.iloc[-1] > sma_50.iloc[-1] and current_price > sma_20.iloc[-1]:
                return 'strong_uptrend'
            elif sma_20.iloc[-1] < sma_50.iloc[-1] and current_price < sma_20.iloc[-1]:
                return 'strong_downtrend'
            elif current_price > sma_20.iloc[-1]:
                return 'weak_uptrend'
            elif current_price < sma_20.iloc[-1]:
                return 'weak_downtrend'
            return 'neutral'
        except:
            return 'neutral'
    
    def _classify_regime(self, adx, atr, atr_avg, trend_strength):
        """تصنيف حالة السوق"""
        volatility_ratio = atr / atr_avg if atr_avg > 0 else 1
        
        if volatility_ratio > 1.5:
            return {
                'name': 'HIGH_VOLATILITY',
                'description': 'تقلبات عالية - السوق متقلب',
                'advice': {'position_size': 0.5, 'stop_multiplier': 2.5, 'can_trade': True, 'caution': 'عالي'}
            }
        
        if volatility_ratio < 0.7:
            return {
                'name': 'LOW_VOLATILITY',
                'description': 'تقلبات منخفضة - سوق هادئ',
                'advice': {'position_size': 1.0, 'stop_multiplier': 1.5, 'can_trade': True, 'caution': 'منخفض'}
            }
        
        if adx > 30:
            if 'up' in trend_strength:
                return {
                    'name': 'STRONG_UPTREND',
                    'description': 'ترند صاعد قوي',
                    'advice': {'position_size': 1.2, 'stop_multiplier': 2.0, 'can_trade': True, 'preferred_action': 'BUY', 'caution': 'منخفض'}
                }
            else:
                return {
                    'name': 'STRONG_DOWNTREND',
                    'description': 'ترند هابط قوي',
                    'advice': {'position_size': 0.3, 'stop_multiplier': 2.0, 'can_trade': False, 'preferred_action': 'HOLD', 'caution': 'عالي'}
                }
        
        if adx > 20:
            return {
                'name': 'WEAK_TREND',
                'description': 'ترند ضعيف',
                'advice': {'position_size': 0.8, 'stop_multiplier': 1.8, 'can_trade': True, 'caution': 'متوسط'}
            }
        
        return {
            'name': 'RANGING',
            'description': 'سوق ثابت (سائد واي)',
            'advice': {'position_size': 0.7, 'stop_multiplier': 1.5, 'can_trade': True, 'preferred_action': 'BUY_LOW_SELL_HIGH', 'caution': 'متوسط'}
        }
    
    def _default_regime(self):
        """قيمة افتراضية"""
        return {
            'regime': 'UNKNOWN',
            'description': 'غير محدد',
            'trading_advice': {'position_size': 0.5, 'stop_multiplier': 2.0, 'can_trade': True, 'caution': 'متوسط'},
            'adx': 20, 'atr': 0, 'atr_avg': 0, 'trend_strength': 'neutral', 'volatility_ratio': 1.0,
            'timestamp': datetime.now().isoformat()
        }


# ================================================================
# 🚨 2. FLASH CRASH PROTECTION
# ================================================================

class FlashCrashDetector:
    """
    يكشف 3 أنواع من السقوط المفاجئ:
    1. Flash Crash - سقوط 10%+ في 5 دقائق
    2. Whale Dump - بيع حيتان
    3. Cascade Risk - سلسلة تصفية
    """
    
    def __init__(self):
        self.flash_crash_threshold = 10.0
        self.whale_dump_threshold = 5.0
        self.volume_spike_threshold = 5.0
    
    def detect(self, df, symbol=None):
        """ يحلل البيانات ويرجع تنبيهات """
        if df is None or len(df) < 10:
            return self._safe_result()
        
        try:
            flash_crash = self._detect_flash_crash(df)
            whale_dump = self._detect_whale_dump(df)
            cascade_risk = self._detect_cascade_risk(df)
            risk_score = self._calculate_risk_score(flash_crash, whale_dump, cascade_risk)
            
            return {
                'flash_crash_detected': flash_crash['detected'],
                'flash_crash_details': flash_crash,
                'whale_dump_detected': whale_dump['detected'],
                'whale_dump_details': whale_dump,
                'cascade_risk': cascade_risk,
                'risk_score': risk_score,
                'risk_level': self._get_risk_level(risk_score),
                'recommendation': self._get_recommendation(risk_score),
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol
            }
        except Exception as e:
            print(f"❌ Flash Crash Error: {e}")
            return self._safe_result()
    
    def _detect_flash_crash(self, df):
        """كشف سقوط مفاجئ"""
        try:
            last_5 = df.tail(5)
            high = last_5['high'].max()
            current = df['close'].iloc[-1]
            open_5min_ago = df['open'].iloc[-5]
            
            drop_from_high = ((high - current) / high) * 100 if high > 0 else 0
            change_5m = ((current - open_5min_ago) / open_5min_ago) * 100 if open_5min_ago > 0 else 0
            
            detected = drop_from_high >= self.flash_crash_threshold
            
            return {
                'detected': detected,
                'drop_percent': round(drop_from_high, 2),
                'change_5m': round(change_5m, 2),
                'high': high, 'low': last_5['low'].min(), 'current': current,
                'severity': 'CRITICAL' if drop_from_high >= 15 else 'HIGH' if detected else 'NORMAL'
            }
        except:
            return {'detected': False, 'drop_percent': 0, 'change_5m': 0, 'severity': 'NORMAL'}
    
    def _detect_whale_dump(self, df):
        """كشف بيع حيتان"""
        try:
            if len(df) < 20:
                return {'detected': False, 'volume_spike': 0, 'price_drop': 0}
            
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            price_change = ((df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]) * 100
            volume_spike = current_volume / avg_volume if avg_volume > 0 else 1
            
            detected = volume_spike >= self.volume_spike_threshold and price_change < -3
            
            return {
                'detected': detected, 'volume_spike': round(volume_spike, 2),
                'price_drop': round(price_change, 2), 'avg_volume': round(avg_volume, 2),
                'current_volume': round(current_volume, 2)
            }
        except:
            return {'detected': False, 'volume_spike': 0, 'price_drop': 0}
    
    def _detect_cascade_risk(self, df):
        """كشف خطر التصفية السلسلة"""
        try:
            if len(df) < 12:
                return {'risk': 'LOW', 'score': 0}
            
            price_changes = []
            for i in range(1, min(6, len(df))):
                change = (df['close'].iloc[-i] - df['open'].iloc[-i]) / df['open'].iloc[-i] * 100
                price_changes.append(change)
            
            red_candles = 0
            for change in price_changes:
                if change < -0.5:
                    red_candles += 1
                else:
                    break
            
            acceleration = 0
            if len(price_changes) >= 3:
                if abs(price_changes[0]) > abs(price_changes[1]) > abs(price_changes[2]):
                    acceleration = 1
            
            risk_score = (red_candles * 20) + (acceleration * 30)
            risk = 'HIGH' if risk_score >= 60 else 'MEDIUM' if risk_score >= 30 else 'LOW'
            
            return {'risk': risk, 'score': risk_score, 'red_candles': red_candles, 'acceleration': bool(acceleration)}
        except:
            return {'risk': 'LOW', 'score': 0}
    
    def _calculate_risk_score(self, flash_crash, whale_dump, cascade_risk):
        """حساب درجة المخاطرة"""
        score = 0
        if flash_crash['detected']:
            score += 50 if flash_crash['severity'] == 'CRITICAL' else 30
        if whale_dump['detected']:
            score += 30
        cascade_scores = {'HIGH': 30, 'MEDIUM': 15, 'LOW': 0}
        score += cascade_scores.get(cascade_risk['risk'], 0)
        return min(score, 100)
    
    def _get_risk_level(self, score):
        """تحويل درجة المخاطرة لمستوى"""
        if score >= 70: return 'CRITICAL'
        elif score >= 50: return 'HIGH'
        elif score >= 30: return 'MEDIUM'
        return 'LOW'
    
    def _get_recommendation(self, score):
        """توصية بناءً على درجة المخاطرة"""
        if score >= 70:
            return {'action': 'STOP_ALL', 'message': '🚨 مخاطرة حرجة', 'can_buy': False, 'can_sell': True, 'position_action': 'REDUCE_75'}
        elif score >= 50:
            return {'action': 'REDUCE_ONLY', 'message': '⚠️ مخاطرة عالية', 'can_buy': False, 'can_sell': True, 'position_action': 'REDUCE_50'}
        elif score >= 30:
            return {'action': 'CAUTION', 'message': '⚡ مخاطرة متوسطة', 'can_buy': True, 'can_sell': True, 'position_action': 'NORMAL', 'size_multiplier': 0.5}
        return {'action': 'NORMAL', 'message': '✅ طبيعي', 'can_buy': True, 'can_sell': True, 'position_action': 'NORMAL'}
    
    def _safe_result(self):
        """نتيجة آمنة"""
        return {
            'flash_crash_detected': False, 'flash_crash_details': {'detected': False, 'severity': 'NORMAL'},
            'whale_dump_detected': False, 'whale_dump_details': {'detected': False},
            'cascade_risk': {'risk': 'LOW', 'score': 0}, 'risk_score': 0, 'risk_level': 'LOW',
            'recommendation': {'action': 'NORMAL', 'message': '✅ طبيعي', 'can_buy': True, 'can_sell': True, 'position_action': 'NORMAL'},
            'timestamp': datetime.now().isoformat()
        }


# ================================================================
# ⏰ 3. TIME ANALYZER
# ================================================================

class TimeAnalyzer:
    """
    يحلل الوقت ويحدد:
    1. الجلسة النشطة
    2. وقت مناسب للتاجر
    3. مؤشرات زمنية
    """
    
    def __init__(self):
        self.peak_hours = {
            'asian': (0, 8),
            'european': (8, 16),
            'american': (13, 21),
        }
    
    def analyze(self):
        """تحليل الوقت الحالي"""
        now = datetime.now(timezone.utc)
        
        return {
            'hour_utc': now.hour,
            'day_of_week': now.weekday(),
            'day_name': now.strftime('%A'),
            'is_weekend': now.weekday() >= 5,
            'is_asian_session': self._is_in_session('asian'),
            'is_european_session': self._is_in_session('european'),
            'is_american_session': self._is_in_session('american'),
            'current_session': self._get_current_session(),
            'volatility_expectation': self._get_volatility_expectation(),
            'trading_recommendation': self._get_recommendation(),
        }
    
    def _is_in_session(self, session):
        """هل الوقت الحالي ضمن الجلسة؟"""
        hour = datetime.now(timezone.utc).hour
        start, end = self.peak_hours.get(session, (0, 24))
        return start <= hour < end
    
    def _get_current_session(self):
        """أي جلسة نشطة الآن؟"""
        if self._is_in_session('american'):
            return 'AMERICAN'
        elif self._is_in_session('european'):
            return 'EUROPEAN'
        elif self._is_in_session('asian'):
            return 'ASIAN'
        return 'QUIET'
    
    def _get_volatility_expectation(self):
        """توقعات التقلبات"""
        session = self._get_current_session()
        if session == 'AMERICAN': return 'HIGH'
        elif session == 'EUROPEAN': return 'MEDIUM'
        elif session == 'ASIAN': return 'LOW_TO_MEDIUM'
        return 'LOW'
    
    def _get_recommendation(self):
        """توصية بناءً على الوقت - الكريبتو يتداول 24/7"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # ذروة أمريكية
        if 14 <= hour <= 20:
            return {'action': 'OPTIMAL', 'message': '⭐ Peak Hours', 'can_trade': True, 'size_multiplier': 1.0, 'reason': 'وقت الذروة'}
        
        # فترة هادئة (بس نتداول بحجم أقل)
        if 21 <= hour < 24 or 0 <= hour < 6:
            return {'action': 'REDUCED', 'message': 'Quiet Hours', 'can_trade': True, 'size_multiplier': 0.8, 'reason': 'فترة هادئة'}
        
        return {'action': 'NORMAL', 'message': '✅ Normal', 'can_trade': True, 'size_multiplier': 1.0, 'reason': 'وقت عادي'}
    
    def get_time_features(self):
        """ميزات زمنية للـ ML"""
        now = datetime.now(timezone.utc)
        return {
            'hour': now.hour,
            'hour_sin': math.sin(2 * math.pi * now.hour / 24),
            'hour_cos': math.cos(2 * math.pi * now.hour / 24),
            'day_of_week': now.weekday(),
            'day_sin': math.sin(2 * math.pi * now.weekday() / 7),
            'day_cos': math.cos(2 * math.pi * now.weekday() / 7),
            'is_weekend': int(now.weekday() >= 5),
            'is_us_hours': int(13 <= now.hour <= 21),
            'is_asia_hours': int(0 <= now.hour <= 8),
        }


# ================================================================
# 🎯 QUICK FUNCTIONS
# ================================================================

def get_market_regime(df):
    """كشف حالة السوق"""
    detector = MarketRegimeDetector()
    return detector.detect(df)


def check_flash_crash(df, symbol=None):
    """كشف Flash Crash"""
    detector = FlashCrashDetector()
    return detector.detect(df, symbol)


def get_time_analysis():
    """تحليل الوقت"""
    analyzer = TimeAnalyzer()
    return analyzer.analyze()


def get_time_multiplier():
    """المضاعف الزمني"""
    analyzer = TimeAnalyzer()
    rec = analyzer._get_recommendation()
    return rec.get('size_multiplier', 1.0)
