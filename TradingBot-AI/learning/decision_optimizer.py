"""
Decision Optimizer - محسّن القرارات
يبحث عن أفضل الإعدادات ضمن الحدود
"""

class DecisionOptimizer:
    def __init__(self, boundaries):
        self.boundaries = boundaries
    
    def optimize_confidence(self, trades_history):
        """
        إيجاد أفضل Confidence بناءً على التاريخ
        """
        if not trades_history or len(trades_history) < 10:
            return self.boundaries['min_confidence']
        
        # تجميع حسب Confidence
        confidence_performance = {}
        
        for trade in trades_history:
            conf = trade.get('confidence', 60)
            profit = trade.get('profit_percent', 0)
            
            if conf not in confidence_performance:
                confidence_performance[conf] = {
                    'wins': 0,
                    'losses': 0,
                    'total_profit': 0,
                    'count': 0
                }
            
            confidence_performance[conf]['count'] += 1
            confidence_performance[conf]['total_profit'] += profit
            
            if profit > 0:
                confidence_performance[conf]['wins'] += 1
            else:
                confidence_performance[conf]['losses'] += 1
        
        # إيجاد الأفضل
        best_confidence = self.boundaries['min_confidence']
        best_score = 0
        
        for conf, perf in confidence_performance.items():
            # ضمن الحدود فقط
            if self.boundaries['min_confidence'] <= conf <= self.boundaries['max_confidence']:
                # حساب النقاط
                win_rate = perf['wins'] / perf['count']
                avg_profit = perf['total_profit'] / perf['count']
                
                # النقاط = نسبة النجاح × متوسط الربح
                score = win_rate * avg_profit
                
                # يحتاج عدد كافي من الصفقات
                if perf['count'] >= 5 and score > best_score:
                    best_score = score
                    best_confidence = conf
        
        return best_confidence
    
    def suggest_improvements(self, recent_trades):
        """
        اقتراح تحسينات بناءً على الأداء الأخير
        """
        if len(recent_trades) < 20:
            return None
        
        suggestions = []
        
        # تحليل نسبة النجاح
        wins = sum(1 for t in recent_trades if t.get('profit_percent', 0) > 0)
        win_rate = wins / len(recent_trades)
        
        if win_rate < 0.70:
            suggestions.append({
                'type': 'INCREASE_MIN_CONFIDENCE',
                'reason': f'Win rate {win_rate:.0%} is low',
                'suggestion': 'Consider increasing min_confidence by 2-3 points'
            })
        elif win_rate > 0.90:
            suggestions.append({
                'type': 'DECREASE_MIN_CONFIDENCE',
                'reason': f'Win rate {win_rate:.0%} is very high',
                'suggestion': 'You might be too conservative, try lowering by 2 points'
            })
        
        # تحليل متوسط الربح
        avg_profit = sum(t.get('profit_percent', 0) for t in recent_trades) / len(recent_trades)
        
        if avg_profit < 0.5:
            suggestions.append({
                'type': 'ADJUST_STRATEGY',
                'reason': f'Average profit {avg_profit:.2f}% is low',
                'suggestion': 'Consider being more selective or adjusting TP levels'
            })
        
        return suggestions if suggestions else None
    
    def find_optimal_volume_threshold(self, trades_history):
        """
        إيجاد أفضل حد للـ Volume
        """
        if not trades_history or len(trades_history) < 20:
            return self.boundaries.get('min_volume', 0.8)
        
        # تجربة عتبات مختلفة
        thresholds = [0.6, 0.8, 1.0, 1.2, 1.5]
        best_threshold = 0.8
        best_performance = 0
        
        for threshold in thresholds:
            # فلترة الصفقات
            filtered = [t for t in trades_history if t.get('volume_ratio', 0) >= threshold]
            
            if len(filtered) < 10:
                continue
            
            # حساب الأداء
            wins = sum(1 for t in filtered if t.get('profit_percent', 0) > 0)
            win_rate = wins / len(filtered)
            avg_profit = sum(t.get('profit_percent', 0) for t in filtered) / len(filtered)
            
            performance = win_rate * avg_profit
            
            if performance > best_performance:
                best_performance = performance
                best_threshold = threshold
        
        return best_threshold
    
    def calculate_optimal_amounts(self, trades_history):
        """
        حساب المبالغ المثلى لكل مستوى Confidence
        """
        optimal_amounts = {}
        
        # تجميع حسب Confidence
        for trade in trades_history:
            conf = trade.get('confidence', 60)
            profit = trade.get('profit_percent', 0)
            amount = trade.get('amount', 10)
            
            if conf not in optimal_amounts:
                optimal_amounts[conf] = {
                    'total_profit': 0,
                    'count': 0,
                    'suggested_amount': 10
                }
            
            optimal_amounts[conf]['total_profit'] += profit
            optimal_amounts[conf]['count'] += 1
        
        # حساب المبالغ المقترحة
        for conf, data in optimal_amounts.items():
            avg_profit = data['total_profit'] / data['count']
            
            # كلما زاد الربح، زاد المبلغ المقترح
            if avg_profit > 1.5:
                data['suggested_amount'] = 20
            elif avg_profit > 1.0:
                data['suggested_amount'] = 15
            elif avg_profit > 0.5:
                data['suggested_amount'] = 12
            else:
                data['suggested_amount'] = 10
        
        return optimal_amounts
