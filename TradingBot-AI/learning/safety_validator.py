"""
Safety Validator - نظام الحماية
يفحص القرارات قبل التنفيذ
"""

class SafetyValidator:
    def __init__(self, boundaries):
        self.boundaries = boundaries
    
    def validate_decision(self, decision):
        """
        فحص شامل للقرار
        """
        checks = [
            self._check_hard_limits(decision),
            self._check_smart_rules(decision),
            self._check_risk_level(decision)
        ]
        
        return all(checks)
    
    def _check_hard_limits(self, decision):
        """فحص الحدود الصلبة (ممنوع تجاوزها)"""
        confidence = decision.get('confidence', 0)
        volume = decision.get('volume', 0)
        
        # Confidence
        if confidence < self.boundaries.get('min_confidence', 50):
            return False
        if confidence > self.boundaries.get('max_confidence', 70):
            return False
        
        # Volume
        if volume < self.boundaries.get('min_volume', 0.8):
            return False
        
        return True
    
    def _check_smart_rules(self, decision):
        """فحص القواعد الذكية"""
        rsi = decision.get('rsi', 50)
        macd = decision.get('macd', 0)
        volume = decision.get('volume', 0)
        
        # RSI Overbought
        if rsi > 70:
            return False
        
        # Volume ضعيف جداً
        if volume < 0.6:
            return False
        
        # MACD ضعيف جداً
        if macd < -30:
            return False
        
        return True
    
    def _check_risk_level(self, decision):
        """تقييم مستوى المخاطرة"""
        confidence = decision.get('confidence', 0)
        rsi = decision.get('rsi', 50)
        volume = decision.get('volume', 1)
        
        risk_score = 0
        
        # Confidence منخفض = خطر
        if confidence < 55:
            risk_score += 2
        
        # RSI منخفض جداً = خطر oversold
        if rsi < 25:
            risk_score += 2
        
        # Volume ضعيف = خطر
        if volume < 1.0:
            risk_score += 1
        
        # إذا المخاطرة عالية جداً
        if risk_score >= 4:
            return False
        
        return True
    
    def get_risk_assessment(self, decision):
        """تقييم تفصيلي للمخاطر"""
        confidence = decision.get('confidence', 0)
        rsi = decision.get('rsi', 50)
        volume = decision.get('volume', 1)
        
        risk_factors = []
        
        if confidence < 55:
            risk_factors.append("Low confidence")
        if rsi < 25:
            risk_factors.append("Extreme oversold")
        if volume < 0.8:
            risk_factors.append("Weak volume")
        
        if len(risk_factors) == 0:
            risk_level = "LOW"
        elif len(risk_factors) == 1:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        return {
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'is_safe': len(risk_factors) < 2
        }
