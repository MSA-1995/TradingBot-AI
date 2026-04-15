"""
🐋 Smart Money Tracker
يكشف حركة الحيتان والأموال الذكية
"""
import os
import requests

class SmartMoneyTracker:
    def __init__(self, exchange):
        self.exchange = exchange
        print("🐋 Smart Money Tracker initialized")
    
    def detect_whale_activity(self, symbol, analysis):
        """كشف نشاط الحيتان من حجم التداول و Order Book"""
        try:
            avg_volume = analysis.get('volume_sma', 0)
            current_volume = analysis.get('volume', 0)

            if avg_volume == 0:
                return {'detected': False, 'confidence_boost': 0}

            # Volume Spike (زيادة مفاجئة في الحجم)
            volume_ratio = current_volume / avg_volume

            # Order Book Analysis (تحليل جدران الطلبات)
            order_book_boost = self._analyze_order_book(symbol)

            # دمج Volume + Order Book
            total_boost = order_book_boost

            # Large Volume Spike = نشاط حيتان
            if volume_ratio >= 3.0:
                # تحقق من الاتجاه
                price_change = analysis.get('price_momentum', 0)

                if price_change > 0:
                    # حيتان تشتري = إشارة إيجابية
                    total_boost += 15
                    return {
                        'detected': True,
                        'type': 'BUY',
                        'volume_ratio': volume_ratio,
                        'confidence_boost': min(total_boost, 25),  # حد أقصى 25
                        'reason': f'Whale buying detected ({volume_ratio:.1f}x volume + Order Book)'
                    }
                else:
                    # حيتان تبيع = إشارة سلبية
                    total_boost -= 20
                    return {
                        'detected': True,
                        'type': 'SELL',
                        'volume_ratio': volume_ratio,
                        'confidence_boost': max(total_boost, -25),  # حد أدنى -25
                        'reason': f'Whale selling detected ({volume_ratio:.1f}x volume + Order Book)'
                    }

            # Medium Volume Spike
            elif volume_ratio >= 2.0:  # احتفظ بـ 2.0 للمتوسط
                price_change = analysis.get('price_momentum', 0)

                if price_change > 0:
                    total_boost += 8
                    return {
                        'detected': True,
                        'type': 'BUY',
                        'volume_ratio': volume_ratio,
                        'confidence_boost': min(total_boost, 15),
                        'reason': f'Smart money accumulation ({volume_ratio:.1f}x volume + Order Book)'
                    }

            # إذا كان Order Book قوي حتى لو Volume متوسط
            if order_book_boost >= 10:
                return {
                    'detected': True,
                    'type': 'BUY',
                    'volume_ratio': volume_ratio,
                    'confidence_boost': order_book_boost,
                    'reason': f'Order Book strong signal (+{order_book_boost})'
                }

            return {'detected': False, 'confidence_boost': 0}

        except Exception as e:
            return {'detected': False, 'confidence_boost': 0}

    def _analyze_order_book(self, symbol):
        """تحليل Order Book المتقدم - كشف جدران + Imbalance + Iceberg"""
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit=50)
            bids = order_book['bids']
            asks = order_book['asks']
            
            if not bids or not asks:
                return 0
            
            # 1. Order Book Imbalance (عدم التوازن)
            total_bid_volume = sum(qty for price, qty in bids[:20])
            total_ask_volume = sum(qty for price, qty in asks[:20])
            
            if total_bid_volume + total_ask_volume == 0:
                return 0
            
            imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)
            imbalance_score = imbalance * 15  # -15 to +15
            
            # 2. كشف الجدران الكبيرة (Walls)
            avg_bid = total_bid_volume / len(bids[:20]) if bids else 0
            avg_ask = total_ask_volume / len(asks[:20]) if asks else 0
            
            big_bid_walls = sum(1 for price, qty in bids[:10] if qty > avg_bid * 3)
            big_ask_walls = sum(1 for price, qty in asks[:10] if qty > avg_ask * 3)
            
            wall_score = (big_bid_walls - big_ask_walls) * 3
            
            # 3. كشف Iceberg Orders (أوامر مخفية)
            # الحيتان يخفون أوامرهم بتقسيمها لأوامر صغيرة متعددة بنفس السعر
            iceberg_score = self._detect_iceberg_orders(bids, asks)
            
            # 4. Bid-Ask Spread Analysis
            spread = ((asks[0][0] - bids[0][0]) / bids[0][0]) * 100 if bids and asks else 0
            spread_score = -5 if spread > 0.1 else 5  # Spread واسع = ضعف
            
            total_score = imbalance_score + wall_score + iceberg_score + spread_score
            return max(-20, min(20, total_score))
            
        except Exception as e:
            return 0
    
    def _detect_iceberg_orders(self, bids, asks):
        """كشف أوامر Iceberg المخفية"""
        try:
            # فحص أوامر متعددة بنفس الحجم تقريباً (علامة Iceberg)
            bid_sizes = [qty for price, qty in bids[:15]]
            ask_sizes = [qty for price, qty in asks[:15]]
            
            # حساب التكرار (كم أمر بنفس الحجم تقريباً)
            bid_clusters = self._count_size_clusters(bid_sizes)
            ask_clusters = self._count_size_clusters(ask_sizes)
            
            if bid_clusters > ask_clusters:
                return 8  # Iceberg شراء = حيتان تشتري بهدوء
            elif ask_clusters > bid_clusters:
                return -8  # Iceberg بيع = حيتان تبيع بهدوء
            
            return 0
        except:
            return 0
    
    def _count_size_clusters(self, sizes):
        """عد الأوامر المتشابهة في الحجم"""
        if not sizes or len(sizes) < 3:
            return 0
        
        clusters = 0
        for i in range(len(sizes) - 2):
            # إذا 3 أوامر متتالية بنفس الحجم تقريباً (±10%)
            if abs(sizes[i] - sizes[i+1]) / sizes[i] < 0.1 and abs(sizes[i+1] - sizes[i+2]) / sizes[i+1] < 0.1:
                clusters += 1
        
        return clusters

    def _get_whale_alerts(self, symbol):
        """جلب تنبيهات الحيتان من API خارجي (Whale Alert)"""
        try:
            api_key = os.getenv("WHALE_ALERT_API_KEY")
            if not api_key or "YOUR_" in api_key:
                return 0

            url = f"https://api.whale-alert.io/v1/transactions?api_key={api_key}&min_value=1000000&limit=10"  # معاملات >1M دولار

            response = requests.get(url, timeout=10)
            data = response.json()

            whale_signals = []
            for tx in data.get('transactions', []):
                if tx['symbol'] == symbol.replace('/USDT', ''):
                    amount_usd = tx['amount_usd']
                    if tx['transaction_type'] == 'transfer' and amount_usd > 5000000:  # نقل كبير
                        if tx['from'].get('owner_type') == 'exchange':  # من بورصة (بيع)
                            whale_signals.append({'type': 'SELL', 'amount': amount_usd})
                        elif tx['to'].get('owner_type') == 'exchange':  # إلى بورصة (شراء)
                            whale_signals.append({'type': 'BUY', 'amount': amount_usd})

            # تحليل الإشارات
            buy_signals = [s for s in whale_signals if s['type'] == 'BUY']
            sell_signals = [s for s in whale_signals if s['type'] == 'SELL']

            if len(buy_signals) > len(sell_signals):
                return 15  # إشارة شراء قوية
            elif len(sell_signals) > len(buy_signals):
                return -15  # إشارة بيع قوية

            return 0

        except Exception as e:
            return 0
    
    def analyze_order_flow(self, symbol, analysis):
        """تحليل تدفق الأوامر - تم تبسيطه ليعتمد على البيانات المتاحة"""
        try:
            price_trend = analysis.get('price_momentum', 0)
            volume_trend = analysis.get('volume_trend', 0)

            if price_trend > 0 and volume_trend > 0:
                # تراكم قوي
                if price_trend > 2 and volume_trend > 50:
                    return 10
                # تراكم متوسط
                elif price_trend > 1 and volume_trend > 30:
                    return 5
            
            # إذا السعر نازل والحجم يزيد = توزيع (Distribution)
            elif price_trend < 0 and volume_trend > 0:
                return -10
            
            return 0
        
        except:
            return 0
    
    def get_confidence_adjustment(self, symbol, analysis):
        """حساب تعديل الثقة بناءً على Smart Money"""
        try:
            if not analysis:
                return 0

            # كشف نشاط الحيتان
            whale_activity = self.detect_whale_activity(symbol, analysis)

            # تحليل تدفق الأوامر
            order_flow = self.analyze_order_flow(symbol, analysis)

            # Whale Alerts خارجي (إذا كان API key متوفر)
            whale_alert_boost = self._get_whale_alerts(symbol)

            # الجمع
            total_adjustment = whale_activity['confidence_boost'] + order_flow + whale_alert_boost

            # الحد الأقصى ±25 (بعد إضافة Whale Alerts)
            total_adjustment = max(-25, min(25, total_adjustment))

            return total_adjustment

        except:
            return 0
    
    def should_avoid(self, symbol, analysis):
        """هل يجب تجنب العملة؟"""
        try:
            if not analysis:
                return False, ""
            
            whale_activity = self.detect_whale_activity(symbol, analysis)
            
            # إذا الحيتان تبيع بقوة
            if whale_activity['detected'] and whale_activity['type'] == 'SELL':
                if whale_activity['volume_ratio'] >= 4.0:
                    return True, whale_activity['reason']
            
            return False, ""
        
        except:
            return False, ""
