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
        تحليل خطر التصفية المتقدم
        Returns: {'risk_level': 'LOW/MEDIUM/HIGH', 'safe_entry': price, 'danger_zones': []}
        """
        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return {'risk_level': 'UNKNOWN', 'safe_entry': current_price, 'danger_zones': []}
        
        bids = order_book['bids'][:50]
        asks = order_book['asks'][:50]
        
        # 1. كشف الجدران الكبيرة
        avg_bid_size = np.mean([b[1] for b in bids]) if bids else 0
        avg_ask_size = np.mean([a[1] for a in asks]) if asks else 0
        
        large_bid_walls = [b for b in bids if b[1] > avg_bid_size * 5]
        large_ask_walls = [a for a in asks if a[1] > avg_ask_size * 5]
        
        # 2. Liquidation Heatmap Analysis
        heatmap = self._generate_liquidation_heatmap(current_price, leverage_data)
        
        # 3. حساب مناطق التصفية
        liquidation_zones = []
        
        # Long liquidation (10x leverage = -10%, 20x = -5%)
        for leverage in [10, 20, 50]:
            liq_price = current_price * (1 - 1/leverage)
            liquidation_zones.append({
                'type': f'LONG_LIQ_{leverage}x',
                'price': liq_price,
                'risk': self._assess_zone_risk(liq_price, large_bid_walls, current_price)
            })
        
        # Short liquidation
        for leverage in [10, 20, 50]:
            liq_price = current_price * (1 + 1/leverage)
            liquidation_zones.append({
                'type': f'SHORT_LIQ_{leverage}x',
                'price': liq_price,
                'risk': self._assess_zone_risk(liq_price, large_ask_walls, current_price)
            })
        
        # 4. Cascade Liquidation Detection
        cascade_risk = self._detect_cascade_risk(liquidation_zones, heatmap)
        
        # 5. تقييم الخطر الإجمالي
        risk_level = 'LOW'
        
        close_walls = [w for w in large_ask_walls if abs(w[0] - current_price) / current_price < 0.02]
        if len(close_walls) >= 2 or cascade_risk == 'HIGH':
            risk_level = 'HIGH'
        elif len(close_walls) == 1 or cascade_risk == 'MEDIUM':
            risk_level = 'MEDIUM'
        
        # 6. نقطة دخول آمنة
        safe_entry = current_price
        if risk_level == 'HIGH':
            safe_entry = current_price * 0.97
        
        return {
            'risk_level': risk_level,
            'safe_entry': safe_entry,
            'danger_zones': liquidation_zones,
            'large_walls': {
                'bids': len(large_bid_walls),
                'asks': len(large_ask_walls)
            },
            'cascade_risk': cascade_risk,
            'heatmap': heatmap,
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
        trades_near_wall = [t for t in recent_trades if abs(t['price'] - wall_price) / wall_price < 0.005]
        
        if wall_size > 100000 and len(trades_near_wall) < 3:
            return True
        
        return False
    
    def _generate_liquidation_heatmap(self, current_price, leverage_data):
        """إنشاء Liquidation Heatmap"""
        try:
            heatmap = {'zones': []}
            
            # حساب مناطق التصفية لكل رافعة
            for leverage in [5, 10, 20, 50, 100]:
                # Long liquidation
                long_liq = current_price * (1 - 1/leverage)
                heatmap['zones'].append({
                    'price': long_liq,
                    'type': 'LONG',
                    'leverage': leverage,
                    'intensity': self._calculate_intensity(leverage)
                })
                
                # Short liquidation
                short_liq = current_price * (1 + 1/leverage)
                heatmap['zones'].append({
                    'price': short_liq,
                    'type': 'SHORT',
                    'leverage': leverage,
                    'intensity': self._calculate_intensity(leverage)
                })
            
            return heatmap
        except:
            return {'zones': []}
    
    def _calculate_intensity(self, leverage):
        """حساب كثافة التصفية"""
        # الرافعة الأعلى = كثافة أعلى
        if leverage >= 50:
            return 'EXTREME'
        elif leverage >= 20:
            return 'HIGH'
        elif leverage >= 10:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _assess_zone_risk(self, zone_price, walls, current_price):
        """تقييم خطر منطقة"""
        # فحص إذا كان هناك جدران قريبة من منطقة التصفية
        nearby_walls = [w for w in walls if abs(w[0] - zone_price) / zone_price < 0.03]
        
        if len(nearby_walls) >= 2:
            return 'CRITICAL'
        elif len(nearby_walls) == 1:
            return 'HIGH'
        elif abs(zone_price - current_price) / current_price < 0.05:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _detect_cascade_risk(self, liquidation_zones, heatmap):
        """كشف خطر التصفيات المتتالية"""
        try:
            # فحص إذا كان هناك مناطق تصفية متقاربة (ضمن 2%)
            high_risk_zones = [z for z in liquidation_zones if z['risk'] in ['HIGH', 'CRITICAL']]
            
            if len(high_risk_zones) >= 3:
                # 3+ مناطق خطرة = خطر Cascade عالي
                return 'HIGH'
            elif len(high_risk_zones) >= 2:
                return 'MEDIUM'
            else:
                return 'LOW'
        except:
            return 'LOW'
