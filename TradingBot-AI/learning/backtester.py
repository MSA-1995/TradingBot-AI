"""
Backtester - اختبار الاستراتيجيات على بيانات تاريخية
"""
from datetime import datetime, timedelta

class Backtester:
    def __init__(self):
        pass
    
    def test_confidence_levels(self, trades_history, confidence_levels):
        """
        اختبار مستويات Confidence مختلفة
        """
        results = {}
        
        for confidence in confidence_levels:
            # فلترة الصفقات
            filtered_trades = [
                t for t in trades_history 
                if t.get('confidence', 0) >= confidence
            ]
            
            if not filtered_trades:
                continue
            
            # حساب الأداء
            wins = sum(1 for t in filtered_trades if t.get('profit_percent', 0) > 0)
            total_profit = sum(t.get('profit_percent', 0) for t in filtered_trades)
            
            results[confidence] = {
                'trades_count': len(filtered_trades),
                'wins': wins,
                'losses': len(filtered_trades) - wins,
                'win_rate': wins / len(filtered_trades) if filtered_trades else 0,
                'total_profit': total_profit,
                'avg_profit': total_profit / len(filtered_trades) if filtered_trades else 0
            }
        
        return results
    
    def test_volume_thresholds(self, trades_history, volume_thresholds):
        """
        اختبار عتبات Volume مختلفة
        """
        results = {}
        
        for threshold in volume_thresholds:
            filtered_trades = [
                t for t in trades_history 
                if t.get('volume_ratio', 0) >= threshold
            ]
            
            if not filtered_trades:
                continue
            
            wins = sum(1 for t in filtered_trades if t.get('profit_percent', 0) > 0)
            total_profit = sum(t.get('profit_percent', 0) for t in filtered_trades)
            
            results[threshold] = {
                'trades_count': len(filtered_trades),
                'win_rate': wins / len(filtered_trades) if filtered_trades else 0,
                'total_profit': total_profit,
                'avg_profit': total_profit / len(filtered_trades) if filtered_trades else 0
            }
        
        return results
    
    def simulate_strategy(self, trades_history, strategy_params):
        """
        محاكاة استراتيجية كاملة
        """
        min_confidence = strategy_params.get('min_confidence', 60)
        min_volume = strategy_params.get('min_volume', 0.8)
        
        # فلترة حسب الاستراتيجية
        filtered_trades = [
            t for t in trades_history 
            if t.get('confidence', 0) >= min_confidence 
            and t.get('volume_ratio', 0) >= min_volume
        ]
        
        if not filtered_trades:
            return None
        
        # حساب النتائج
        wins = sum(1 for t in filtered_trades if t.get('profit_percent', 0) > 0)
        losses = len(filtered_trades) - wins
        total_profit = sum(t.get('profit_percent', 0) for t in filtered_trades)
        
        # حساب أفضل وأسوأ صفقة
        profits = [t.get('profit_percent', 0) for t in filtered_trades]
        best_trade = max(profits) if profits else 0
        worst_trade = min(profits) if profits else 0
        
        return {
            'strategy': strategy_params,
            'total_trades': len(filtered_trades),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(filtered_trades),
            'total_profit': total_profit,
            'avg_profit': total_profit / len(filtered_trades),
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'profit_factor': self._calculate_profit_factor(filtered_trades)
        }
    
    def _calculate_profit_factor(self, trades):
        """
        حساب Profit Factor (إجمالي الأرباح / إجمالي الخسائر)
        """
        total_wins = sum(t.get('profit_percent', 0) for t in trades if t.get('profit_percent', 0) > 0)
        total_losses = abs(sum(t.get('profit_percent', 0) for t in trades if t.get('profit_percent', 0) < 0))
        
        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0
        
        return total_wins / total_losses
    
    def compare_strategies(self, trades_history, strategies):
        """
        مقارنة استراتيجيات متعددة
        """
        results = []
        
        for strategy in strategies:
            result = self.simulate_strategy(trades_history, strategy)
            if result:
                results.append(result)
        
        # ترتيب حسب الأداء
        results.sort(key=lambda x: x['total_profit'], reverse=True)
        
        return results
    
    def generate_report(self, backtest_results):
        """
        توليد تقرير مفصل
        """
        if not backtest_results:
            return "No results to report"
        
        report = "📊 Backtest Report\n"
        report += "=" * 50 + "\n\n"
        
        for i, result in enumerate(backtest_results[:3], 1):
            report += f"#{i} Strategy:\n"
            report += f"  Min Confidence: {result['strategy']['min_confidence']}\n"
            report += f"  Min Volume: {result['strategy']['min_volume']}\n"
            report += f"  Trades: {result['total_trades']}\n"
            report += f"  Win Rate: {result['win_rate']:.1%}\n"
            report += f"  Total Profit: {result['total_profit']:.2f}%\n"
            report += f"  Avg Profit: {result['avg_profit']:.2f}%\n"
            report += f"  Profit Factor: {result['profit_factor']:.2f}\n"
            report += "\n"
        
        return report
