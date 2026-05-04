"""
🛡️ Smart Liquidation Shield - درع التصفية الذكي
يكتشف مناطق التصفية المحتملة ويتجنبها
"""

import numpy as np
from typing import Optional


class LiquidationShield:
    """
    يحلل Order Book لكشف:
    - مناطق التصفية الكبيرة (Liquidation Clusters)
    - جدران البيع/الشراء الوهمية (Fake Walls)
    - مناطق السيولة الضعيفة (Thin Liquidity Zones)
    """

    # رافعات التحليل
    LEVERAGES = [5, 10, 20, 50, 100]

    # حدود الجدران الكبيرة
    WALL_MULTIPLIER      = 5
    FAKE_WALL_MIN_SIZE   = 100_000
    FAKE_WALL_MAX_TRADES = 3

    # نسب المسافات
    CLOSE_WALL_THRESHOLD    = 0.02   # 2%  من السعر الحالي
    NEARBY_WALL_THRESHOLD   = 0.03   # 3%  من منطقة التصفية
    MEDIUM_ZONE_THRESHOLD   = 0.05   # 5%  من السعر الحالي
    FAKE_WALL_PRICE_RANGE   = 0.005  # 0.5% حول الجدار

    # تعديل السعر عند الخطر العالي
    HIGH_RISK_PRICE_ADJUST  = 0.97

    def __init__(self):
        self.liquidation_zones: dict = {}  # {symbol: [zones]}

    # ─────────────────────────────────────────────
    # التحليل الرئيسي
    # ─────────────────────────────────────────────

    def analyze_liquidation_risk(self, symbol: str, current_price: float,
                                  order_book: dict,
                                  leverage_data=None) -> dict:
        """
        تحليل خطر التصفية المتقدم
        Returns: {'risk_level': 'LOW/MEDIUM/HIGH', 'safe_entry': price, 'danger_zones': []}
        """
        empty_result = {
            'risk_level':   'UNKNOWN',
            'safe_entry':   current_price,
            'danger_zones': []
        }

        if not order_book or not order_book.get('bids') or not order_book.get('asks'):
            return empty_result

        try:
            bids = order_book['bids'][:50]
            asks = order_book['asks'][:50]

            # 1. كشف الجدران الكبيرة
            large_bid_walls, large_ask_walls = self._detect_large_walls(bids, asks)

            # 2. Liquidation Heatmap
            heatmap = self._generate_liquidation_heatmap(current_price, leverage_data)

            # 3. حساب مناطق التصفية
            liquidation_zones = self._calculate_liquidation_zones(
                current_price, large_bid_walls, large_ask_walls
            )

            # 4. Cascade Liquidation Detection
            cascade_risk = self._detect_cascade_risk(liquidation_zones)

            # 5. تقييم الخطر الإجمالي
            close_walls = [
                w for w in large_ask_walls
                if abs(w[0] - current_price) / current_price < self.CLOSE_WALL_THRESHOLD
            ]

            if len(close_walls) >= 2 or cascade_risk == 'HIGH':
                risk_level = 'HIGH'
            elif len(close_walls) == 1 or cascade_risk == 'MEDIUM':
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'

            # 6. نقطة دخول آمنة
            safe_entry = (current_price * self.HIGH_RISK_PRICE_ADJUST
                          if risk_level == 'HIGH' else current_price)

            return {
                'risk_level':    risk_level,
                'safe_entry':    safe_entry,
                'danger_zones':  liquidation_zones,
                'large_walls':   {'bids': len(large_bid_walls), 'asks': len(large_ask_walls)},
                'cascade_risk':  cascade_risk,
                'heatmap':       heatmap,
                'recommendation': self._get_recommendation(risk_level)
            }

        except Exception as e:
            print(f"⚠️ LiquidationShield analyze error: {e}")
            return empty_result

    # ─────────────────────────────────────────────
    # الجدران الكبيرة
    # ─────────────────────────────────────────────

    def _detect_large_walls(self, bids: list, asks: list) -> tuple[list, list]:
        """كشف الجدران الكبيرة في Bids و Asks"""
        avg_bid_size = float(np.mean([b[1] for b in bids])) if bids else 0.0
        avg_ask_size = float(np.mean([a[1] for a in asks])) if asks else 0.0

        large_bids = [b for b in bids if b[1] > avg_bid_size * self.WALL_MULTIPLIER]
        large_asks = [a for a in asks if a[1] > avg_ask_size * self.WALL_MULTIPLIER]

        return large_bids, large_asks

    def is_fake_wall(self, wall_price: float, wall_size: float,
                     recent_trades: list) -> bool:
        """
        كشف الجدران الوهمية
        الجدار الوهمي = جدار كبير لكن لا يتم تنفيذ صفقات عنده
        """
        try:
            trades_near_wall = [
                t for t in recent_trades
                if abs(t['price'] - wall_price) / wall_price < self.FAKE_WALL_PRICE_RANGE
            ]
            return (wall_size > self.FAKE_WALL_MIN_SIZE
                    and len(trades_near_wall) < self.FAKE_WALL_MAX_TRADES)

        except Exception as e:
            print(f"⚠️ LiquidationShield is_fake_wall error: {e}")
            return False

    # ─────────────────────────────────────────────
    # مناطق التصفية
    # ─────────────────────────────────────────────

    def _calculate_liquidation_zones(self, current_price: float,
                                      large_bid_walls: list,
                                      large_ask_walls: list) -> list:
        """حساب مناطق التصفية لكل رافعة"""
        zones = []

        for leverage in [10, 20, 50]:
            # Long liquidation
            long_price = current_price * (1 - 1 / leverage)
            zones.append({
                'type':  f'LONG_LIQ_{leverage}x',
                'price': long_price,
                'risk':  self._assess_zone_risk(long_price, large_bid_walls, current_price)
            })

            # Short liquidation
            short_price = current_price * (1 + 1 / leverage)
            zones.append({
                'type':  f'SHORT_LIQ_{leverage}x',
                'price': short_price,
                'risk':  self._assess_zone_risk(short_price, large_ask_walls, current_price)
            })

        return zones

    def _assess_zone_risk(self, zone_price: float, walls: list,
                           current_price: float) -> str:
        """تقييم خطر منطقة تصفية"""
        try:
            if zone_price <= 0:
                return 'LOW'

            nearby_walls = [
                w for w in walls
                if abs(w[0] - zone_price) / zone_price < self.NEARBY_WALL_THRESHOLD
            ]

            if len(nearby_walls) >= 2:
                return 'CRITICAL'
            elif len(nearby_walls) == 1:
                return 'HIGH'
            elif abs(zone_price - current_price) / current_price < self.MEDIUM_ZONE_THRESHOLD:
                return 'MEDIUM'
            else:
                return 'LOW'

        except Exception as e:
            print(f"⚠️ LiquidationShield assess_zone_risk error: {e}")
            return 'LOW'

    def _detect_cascade_risk(self, liquidation_zones: list) -> str:
        """كشف خطر التصفيات المتتالية"""
        try:
            high_risk_zones = [
                z for z in liquidation_zones
                if z['risk'] in {'HIGH', 'CRITICAL'}
            ]

            if len(high_risk_zones) >= 3:
                return 'HIGH'
            elif len(high_risk_zones) >= 2:
                return 'MEDIUM'
            else:
                return 'LOW'

        except Exception as e:
            print(f"⚠️ LiquidationShield cascade_risk error: {e}")
            return 'LOW'

    # ─────────────────────────────────────────────
    # Heatmap
    # ─────────────────────────────────────────────

    def _generate_liquidation_heatmap(self, current_price: float,
                                       leverage_data=None) -> dict:
        """إنشاء Liquidation Heatmap"""
        try:
            zones = []
            for leverage in self.LEVERAGES:
                zones.append({
                    'price':     current_price * (1 - 1 / leverage),
                    'type':      'LONG',
                    'leverage':  leverage,
                    'intensity': self._calculate_intensity(leverage)
                })
                zones.append({
                    'price':     current_price * (1 + 1 / leverage),
                    'type':      'SHORT',
                    'leverage':  leverage,
                    'intensity': self._calculate_intensity(leverage)
                })

            return {'zones': zones}

        except Exception as e:
            print(f"⚠️ LiquidationShield heatmap error: {e}")
            return {'zones': []}

    @staticmethod
    def _calculate_intensity(leverage: int) -> str:
        """حساب كثافة التصفية بناءً على الرافعة"""
        if leverage >= 50:
            return 'EXTREME'
        elif leverage >= 20:
            return 'HIGH'
        elif leverage >= 10:
            return 'MEDIUM'
        else:
            return 'LOW'

    # ─────────────────────────────────────────────
    # التوصيات
    # ─────────────────────────────────────────────

    @staticmethod
    def _get_recommendation(risk_level: str) -> str:
        """توصية بناءً على مستوى الخطر"""
        recommendations = {
            'HIGH':   '⚠️ High liquidation risk - Wait for breakout or avoid',
            'MEDIUM': '⚡ Medium risk - Reduce position size by 50%',
            'LOW':    '✅ Low risk - Safe to enter'
        }
        return recommendations.get(risk_level, '❓ Unknown risk level')