"""
🛡️ Smart Liquidation Shield - درع التصفية الذكي
يكتشف مناطق التصفية المحتملة ويتجنبها
"""
import numpy as np

class LiquidationShield:
    """
    يحلل Order Book لكشف:
    - مناطق التصفية الكبيرة (Liquidation Clusters)
    - جدران البيع/الشراء الوهمية (Fake Walls)
    - مناطق السيولة الضعيفة (Thin Liquidity Zones)
    """
    
    def __init__(self):
        self.liquidation_zones = {}  # {symbol: [zones]}
    
    def analyze_liquidation_risk(self, symbol, current_price, order_book, leverage_data=None):
        """
        تحليل خطر التصفية
        Returns: {'risk_level': 'LOW/MEDIUM/HIGH', 'safe_entry': price, 'danger_zones': []}
        """
        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return {'risk_level': 'UNKNOWN', 'safe_entry': current_price, 'danger_zones': []}
        
        # 1. كشف الجدران الكبيرة (Large Walls)
        bids = order_book['bids'][:50]
        asks = order_book['asks'][:50]
        
        # حساب متوسط حجم الطلبات
        avg_bid_size = np.mean([b[1] for b in bids]) if bids else 0
        avg_ask_size = np.mean([a[1] for a in asks]) if asks else 0
        
        # كشف الجدران (أكبر من 5x المتوسط)
        large_bid_walls = [b for b in bids if b[1] > avg_bid_size * 5]
        large_ask_walls = [a for a in asks if a[1] > avg_ask_size * 5]
        
        # 2. حساب مناطق التصفية المحتملة
        # (في الرافعة المالية، التصفية تحدث عند انخفاض 10-20% من سعر الدخول)
        liquidation_zones = []
        
        # منطقة تصفية Long positions (تحت السعر الحالي)
        long_liq_zone = current_price * 0.90  # -10%
        liquidation_zones.append({
            'type': 'LONG_LIQUIDATION',
            'price': long_liq_zone,
            'risk': 'HIGH' if any(b[0] <= long_liq_zone * 1.02 for b in large_bid_walls) else 'MEDIUM'
        })
        
        # منطقة تصفية Short positions (فوق السعر الحالي)
        short_liq_zone = current_price * 1.10  # +10%
        liquidation_zones.append({
            'type': 'SHORT_LIQUIDATION',
            'price': short_liq_zone,
            'risk': 'HIGH' if any(a[0] >= short_liq_zone * 0.98 for a in large_ask_walls) else 'MEDIUM'
        })
        
        # 3. تقييم الخطر الإجمالي
        risk_level = 'LOW'
        
        # إذا كان هناك جدار كبير قريب جداً (أقل من 2%)
        close_walls = [w for w in large_ask_walls if abs(w[0] - current_price) / current_price < 0.02]
        if len(close_walls) >= 2:
            risk_level = 'HIGH'
        elif len(close_walls) == 1:
            risk_level = 'MEDIUM'
        
        # 4. اقتراح نقطة دخول آمنة
        # (بعيداً عن مناطق التصفية بـ 3%)
        safe_entry = current_price
        if risk_level == 'HIGH':
            # انتظر حتى يكسر الجدار أو ابتعد عنه
            safe_entry = current_price * 0.97  # ادخل أقل بـ 3%
        
        return {
            'risk_level': risk_level,
            'safe_entry': safe_entry,
            'danger_zones': liquidation_zones,
            'large_walls': {
                'bids': len(large_bid_walls),
                'asks': len(large_ask_walls)
            },
            'recommendation': self._get_recommendation(risk_level)
        }
    
    def _get_recommendation(self, risk_level):
        """توصية بناءً على مستوى الخطر"""
        if risk_level == 'HIGH':
            return "⚠️ High liquidation risk - Wait for breakout or avoid"
        elif risk_level == 'MEDIUM':
            return "⚡ Medium risk - Reduce position size by 50%"
        else:
            return "✅ Low risk - Safe to enter"
    
    def is_fake_wall(self, wall_price, wall_size, recent_trades):
        """
        كشف الجدران الوهمية
        الجدار الوهمي = جدار كبير لكن لا يتم تنفيذ صفقات عنده
        """
        # فحص إذا كان هناك صفقات قريبة من سعر الجدار
        trades_near_wall = [t for t in recent_trades if abs(t['price'] - wall_price) / wall_price < 0.005]
        
        # إذا الجدار كبير لكن ما في صفقات = وهمي
        if wall_size > 100000 and len(trades_near_wall) < 3:
            return True
        
        return False
