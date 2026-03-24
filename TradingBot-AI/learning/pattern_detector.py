"""
Pattern Detector - كاشف الأنماط
يستخرج الأنماط من الصفقات ويصنفها
"""

class PatternDetector:
    def __init__(self):
        self.min_trades_for_pattern = 3  # الحد الأدنى لتكوين نمط
    
    def extract_pattern(self, trade_result):
        """
        استخراج نمط من صفقة
        """
        if not trade_result:
            return None
        
        # حماية من None
        profit = trade_result.get('profit_percent', 0)
        if profit is None:
            profit = 0
        try:
            profit = float(profit)
        except:
            profit = 0
        
        # تحديد نوع النمط
        if profit >= 0.5:
            pattern_type = 'SUCCESS'
        elif profit <= -1.5:
            pattern_type = 'TRAP'
        else:
            pattern_type = 'NEUTRAL'
        
        pattern = {
            'type': pattern_type,
            'conditions': {
                'confidence': trade_result.get('confidence'),
                'rsi': trade_result.get('rsi'),
                'volume_ratio': trade_result.get('volume_ratio'),
                'macd_diff': trade_result.get('macd_diff'),
                'momentum': trade_result.get('momentum'),
                'trend': trade_result.get('trend')
            },
            'result': {
                'profit_percent': profit,
                'symbol': trade_result.get('symbol')
            },
            'success_rate': 1.0 if profit > 0 else 0.0,
            'trades_count': 1,
            'summary': self._generate_summary(trade_result, pattern_type)
        }
        
        return pattern
    
    def _generate_summary(self, trade, pattern_type):
        """توليد ملخص للنمط"""
        symbol = trade.get('symbol', 'Unknown')
        confidence = trade.get('confidence', 0)
        profit = trade.get('profit_percent', 0)
        
        # حماية من None
        if confidence is None:
            confidence = 0
        if profit is None:
            profit = 0
        try:
            confidence = float(confidence)
            profit = float(profit)
        except:
            confidence = 0
            profit = 0
        
        if pattern_type == 'SUCCESS':
            return f"{symbol}: Confidence {confidence} → +{profit:.2f}%"
        elif pattern_type == 'TRAP':
            return f"{symbol}: Confidence {confidence} → {profit:.2f}% (TRAP)"
        else:
            return f"{symbol}: Confidence {confidence} → {profit:.2f}%"
    
    def analyze_patterns(self, trades):
        """
        تحليل مجموعة صفقات لاكتشاف أنماط متكررة
        """
        if len(trades) < self.min_trades_for_pattern:
            return []
        
        patterns = []
        
        # تجميع الصفقات حسب الخصائص المتشابهة
        grouped = self._group_similar_trades(trades)
        
        for group in grouped:
            if len(group) >= self.min_trades_for_pattern:
                pattern = self._create_pattern_from_group(group)
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    def _group_similar_trades(self, trades):
        """تجميع الصفقات المتشابهة"""
        groups = []
        
        for trade in trades:
            added = False
            for group in groups:
                if self._is_similar(trade, group[0]):
                    group.append(trade)
                    added = True
                    break
            
            if not added:
                groups.append([trade])
        
        return groups
    
    def _is_similar(self, trade1, trade2):
        """فحص إذا كانت صفقتين متشابهتين"""
        # حماية من None
        rsi1 = trade1.get('rsi', 0) or 0
        rsi2 = trade2.get('rsi', 0) or 0
        conf1 = trade1.get('confidence', 0) or 0
        conf2 = trade2.get('confidence', 0) or 0
        
        try:
            # مقارنة RSI
            rsi_diff = abs(float(rsi1) - float(rsi2))
            if rsi_diff > 10:
                return False
            
            # مقارنة Confidence
            conf_diff = abs(float(conf1) - float(conf2))
            if conf_diff > 5:
                return False
        except:
            return False
        
        return True
    
    def _create_pattern_from_group(self, group):
        """إنشاء نمط من مجموعة صفقات"""
        if not group:
            return None
        
        # حساب المتوسطات مع حماية من None
        try:
            confidences = [float(t.get('confidence', 0) or 0) for t in group]
            rsis = [float(t.get('rsi', 0) or 0) for t in group]
            volumes = [float(t.get('volume_ratio', 0) or 0) for t in group]
            
            avg_confidence = sum(confidences) / len(group) if group else 0
            avg_rsi = sum(rsis) / len(group) if group else 0
            avg_volume = sum(volumes) / len(group) if group else 0
        except:
            avg_confidence = 0
            avg_rsi = 0
            avg_volume = 0
        
        # حساب نسبة النجاح مع حماية من None
        try:
            success_count = sum(1 for t in group if (t.get('profit_percent', 0) or 0) > 0)
            success_rate = success_count / len(group) if group else 0
        except:
            success_rate = 0
        
        # تحديد النوع
        try:
            if success_rate >= 0.8:
                pattern_type = 'SUCCESS'
            elif success_rate <= 0.3:
                pattern_type = 'TRAP'
            else:
                pattern_type = 'NEUTRAL'
            
            return {
                'type': pattern_type,
                'conditions': {
                    'confidence': avg_confidence,
                    'rsi': avg_rsi,
                    'volume_ratio': avg_volume
                },
                'success_rate': success_rate,
                'trades_count': len(group),
                'summary': f"Pattern: Confidence ~{avg_confidence:.0f}, Success: {success_rate:.0%}"
            }
        except:
            return None
