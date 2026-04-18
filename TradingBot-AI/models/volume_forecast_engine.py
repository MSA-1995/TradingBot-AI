"""
📊 Volume Forecasting Engine - محرك التنبؤ بالحجم
يتنبأ بالحجم في الشموع القادمة لاكتشاف الانفجارات مبكراً
"""
import numpy as np
from datetime import datetime, timedelta

class VolumeForecastEngine:
    """
    يستخدم:
    - Moving Average للحجم
    - Volume Momentum (تسارع الحجم)
    - Time-based patterns (أوقات الذروة)
    """
    
    def __init__(self):
        self.volume_history = {}  # {symbol: [volumes]}
        self.time_patterns = {}   # {symbol: {hour: avg_volume}}
    
    def predict_next_volume(self, symbol, current_volumes, current_hour):
        """
        التنبؤ بحجم الشمعة القادمة + Volume Profile Analysis
        Returns: {'predicted_volume': float, 'confidence': 0-100, 'trend': 'INCREASING/DECREASING'}
        """
        if len(current_volumes) < 20:
            return {'predicted_volume': current_volumes[-1] if current_volumes else 0, 'confidence': 0, 'trend': 'UNKNOWN'}
        
        # 1. حساب المتوسط المتحرك
        ma_20 = np.mean(current_volumes[-20:])
        ma_5 = np.mean(current_volumes[-5:])
        
        # 2. Volume Momentum (زخم الحجم)
        recent_trend = ma_5 / ma_20 if ma_20 > 0 else 1.0
        
        # 3. Volume Acceleration (تسارع الحجم)
        ma_3 = np.mean(current_volumes[-3:])
        acceleration = (ma_3 / ma_5) if ma_5 > 0 else 1.0
        
        # 4. التنبؤ باستخدام EMA
        alpha = 0.3
        predicted = alpha * current_volumes[-1] + (1 - alpha) * ma_5
        
        # 5. تعديل بناءً على التسارع
        if acceleration > 1.2:
            predicted *= 1.15  # حجم يتسارع
        elif acceleration < 0.8:
            predicted *= 0.85  # حجم يتباطأ
        
        # 6. تعديل بناءً على الوقت
        time_multiplier = self._get_time_multiplier(symbol, current_hour)
        predicted *= time_multiplier
        
        # 7. Volume Profile Analysis
        volume_profile = self._analyze_volume_profile(current_volumes)
        
        # 8. حساب الثقة
        volume_std = np.std(current_volumes[-20:])
        volume_cv = (volume_std / ma_20) if ma_20 > 0 else 1.0
        
        confidence = max(0, min(100, 100 - (volume_cv * 50)))
        
        # 9. تحديد الاتجاه
        if recent_trend > 1.2:
            trend = 'INCREASING'
        elif recent_trend < 0.8:
            trend = 'DECREASING'
        else:
            trend = 'STABLE'
        
        return {
            'predicted_volume': predicted,
            'current_volume': current_volumes[-1],
            'ma_20': ma_20,
            'confidence': round(confidence, 1),
            'trend': trend,
            'momentum': round((recent_trend - 1) * 100, 1),
            'acceleration': round((acceleration - 1) * 100, 1),
            'time_multiplier': time_multiplier,
            'volume_profile': volume_profile
        }
    
    def _get_time_multiplier(self, symbol, current_hour):
        """
        مضاعف الوقت - بعض الساعات تشهد حجم أعلى
        """
        # أوقات الذروة (الجلسة الأمريكية)
        if 14 <= current_hour <= 20:
            return 1.3
        # أوقات هادئة (الجلسة الآسيوية)
        elif 0 <= current_hour <= 6:
            return 0.7
        else:
            return 1.0
    
    def detect_volume_breakout(self, symbol, current_volumes, prediction):
        """
        كشف انفجار الحجم قبل حدوثه
        Returns: {'breakout_imminent': bool, 'probability': 0-100}
        """
        if len(current_volumes) < 10:
            return {'breakout_imminent': False, 'probability': 0}
        
        # شروط انفجار الحجم:
        # 1. الحجم الحالي أعلى من المتوسط بـ 50%+
        # 2. الزخم إيجابي (INCREASING)
        # 3. التنبؤ يشير لحجم أعلى
        
        current = current_volumes[-1]
        avg = np.mean(current_volumes[-20:])
        
        current_ratio = current / avg if avg > 0 else 1.0
        predicted_ratio = prediction['predicted_volume'] / avg if avg > 0 else 1.0
        
        # احتمالية الانفجار
        probability = 0
        
        if current_ratio > 1.5 and prediction['trend'] == 'INCREASING':
            probability = 70
        elif current_ratio > 1.3 and predicted_ratio > 1.5:
            probability = 50
        elif prediction['trend'] == 'INCREASING' and prediction['momentum'] > 20:
            probability = 40
        
        return {
            'breakout_imminent': probability >= 50,
            'probability': probability,
            'current_ratio': round(current_ratio, 2),
            'predicted_ratio': round(predicted_ratio, 2)
        }
    
    def get_volume_quality_score(self, symbol, current_volumes):
        """
        تقييم جودة الحجم (0-100)
        حجم عالي + مستقر = جودة عالية
        """
        if len(current_volumes) < 20:
            return 50
        
        avg = np.mean(current_volumes[-20:])
        std = np.std(current_volumes[-20:])
        current = current_volumes[-1]
        
        # 1. الحجم الحالي مقارنة بالمتوسط (0-50 نقطة)
        volume_score = min(50, (current / avg) * 25) if avg > 0 else 0
        
        # 2. الاستقرار (0-50 نقطة)
        cv = (std / avg) if avg > 0 else 1.0
        stability_score = max(0, 50 - (cv * 25))
        
        return round(volume_score + stability_score, 1)
    
    def _analyze_volume_profile(self, volumes):
        """تحليل Volume Profile - توزيع الحجم"""
        try:
            if len(volumes) < 20:
                return {'type': 'UNKNOWN', 'strength': 0}
            
            # تقسيم الحجم إلى 3 مستويات
            sorted_volumes = sorted(volumes[-20:])
            low_threshold = sorted_volumes[6]   # 30%
            high_threshold = sorted_volumes[13]  # 70%
            
            recent_5 = volumes[-5:]
            
            # حساب نسبة الحجم العالي
            high_volume_count = sum(1 for v in recent_5 if v > high_threshold)
            low_volume_count = sum(1 for v in recent_5 if v < low_threshold)
            
            # Accumulation: حجم عالي مستمر
            if high_volume_count >= 4:
                return {'type': 'ACCUMULATION', 'strength': 85}
            
            # Distribution: حجم عالي متقطع
            elif high_volume_count >= 2 and low_volume_count >= 2:
                return {'type': 'DISTRIBUTION', 'strength': 70}
            
            # Climax: حجم مفاجئ جداً
            elif recent_5[-1] > np.mean(volumes[-20:]) * 3:
                return {'type': 'CLIMAX', 'strength': 90}
            
            # Low Activity: حجم ضعيف
            elif low_volume_count >= 4:
                return {'type': 'LOW_ACTIVITY', 'strength': 30}
            
            return {'type': 'NEUTRAL', 'strength': 50}
            
        except:
            return {'type': 'UNKNOWN', 'strength': 0}
