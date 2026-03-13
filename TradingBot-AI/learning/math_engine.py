"""
Math Engine - محرك الرياضيات
حسابات احتمالية وتحسين القرارات
"""
import statistics

class MathEngine:
    def __init__(self):
        pass
    
    def calculate_success_probability(self, similar_trades):
        """
        حساب احتمال النجاح بناءً على صفقات مشابهة
        """
        if not similar_trades:
            return 0.5  # 50% افتراضي
        
        success_count = sum(1 for t in similar_trades if t.get('profit_percent', 0) > 0)
        total = len(similar_trades)
        
        # Bayesian adjustment
        prior = 0.5  # احتمال مسبق
        likelihood = success_count / total
        
        # وزن أكبر للبيانات الأكثر
        weight = min(total / 10, 1.0)  # أقصى وزن عند 10 صفقات
        
        probability = (weight * likelihood) + ((1 - weight) * prior)
        
        return probability
    
    def calculate_optimal_confidence(self, trades_history, confidence_range):
        """
        إيجاد أفضل Confidence ضمن النطاق
        """
        if not trades_history:
            return confidence_range[0]  # الحد الأدنى
        
        # تجميع الصفقات حسب Confidence
        confidence_groups = {}
        for trade in trades_history:
            conf = int(trade.get('confidence', 60))
            if conf not in confidence_groups:
                confidence_groups[conf] = []
            confidence_groups[conf].append(trade)
        
        # حساب نسبة النجاح لكل Confidence
        best_confidence = confidence_range[0]
        best_success_rate = 0
        
        for conf, trades in confidence_groups.items():
            if confidence_range[0] <= conf <= confidence_range[1]:
                success_count = sum(1 for t in trades if t.get('profit_percent', 0) > 0)
                success_rate = success_count / len(trades)
                
                if success_rate > best_success_rate and len(trades) >= 3:
                    best_success_rate = success_rate
                    best_confidence = conf
        
        return best_confidence
    
    def calculate_risk_score(self, decision):
        """
        حساب درجة المخاطرة (0-100)
        """
        confidence = decision.get('confidence', 60)
        rsi = decision.get('rsi', 50)
        volume = decision.get('volume', 1.0)
        
        risk = 0
        
        # Confidence منخفض = خطر أعلى
        if confidence < 55:
            risk += 30
        elif confidence < 60:
            risk += 20
        elif confidence < 65:
            risk += 10
        
        # RSI extreme = خطر
        if rsi < 25 or rsi > 75:
            risk += 25
        elif rsi < 30 or rsi > 70:
            risk += 15
        
        # Volume ضعيف = خطر
        if volume < 0.8:
            risk += 20
        elif volume < 1.0:
            risk += 10
        
        return min(risk, 100)
    
    def calculate_expected_profit(self, similar_trades):
        """
        حساب الربح المتوقع
        """
        if not similar_trades:
            return 0
        
        profits = [t.get('profit_percent', 0) for t in similar_trades]
        
        if not profits:
            return 0
        
        # المتوسط المرجح (الصفقات الأحدث لها وزن أكبر)
        weights = [i + 1 for i in range(len(profits))]
        weighted_avg = sum(p * w for p, w in zip(profits, weights)) / sum(weights)
        
        return weighted_avg
    
    def calculate_confidence_interval(self, trades, confidence_level=0.95):
        """
        حساب فترة الثقة للأرباح
        """
        if len(trades) < 2:
            return (0, 0)
        
        profits = [t.get('profit_percent', 0) for t in trades]
        
        mean = statistics.mean(profits)
        stdev = statistics.stdev(profits)
        
        # فترة الثقة البسيطة
        margin = 1.96 * stdev / (len(profits) ** 0.5)  # 95% confidence
        
        return (mean - margin, mean + margin)
    
    def optimize_amount(self, confidence, success_probability):
        """
        تحسين المبلغ المستثمر بناءً على الثقة والاحتمال
        """
        base_amount = 10
        
        # Confidence أعلى = مبلغ أكبر
        if confidence >= 110:
            amount = 20
        elif confidence >= 100:
            amount = 18
        elif confidence >= 90:
            amount = 16
        elif confidence >= 80:
            amount = 14
        elif confidence >= 70:
            amount = 12
        else:
            amount = 10
        
        # تعديل بناءً على احتمال النجاح
        if success_probability < 0.6:
            amount = base_amount  # حذر
        elif success_probability > 0.85:
            amount = min(amount + 2, 20)  # جريء
        
        return amount
