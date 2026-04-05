"""
💧 Liquidity Analyzer
يحلل عمق السوق والسيولة لاختيار أفضل العملات
"""

class LiquidityAnalyzer:
    def __init__(self, exchange):
        self.exchange = exchange
        self.cache = {}
        self.cache_duration = 300  # 5 دقائق
        print("💧 Liquidity Analyzer initialized")
    
    def get_order_book_depth(self, symbol):
        """قياس عمق السوق من Order Book"""
        try:
            from datetime import datetime
            
            # Cache check
            if symbol in self.cache:
                cached_data, cached_time = self.cache[symbol]
                if (datetime.now() - cached_time).total_seconds() < self.cache_duration:
                    return cached_data
            
            # جلب Order Book
            order_book = self.exchange.fetch_order_book(symbol, limit=20)
            
            bids = order_book['bids']
            asks = order_book['asks']
            
            if not bids or not asks:
                return None
            
            # حساب إجمالي السيولة في أول 20 مستوى
            bid_liquidity = sum([bid[1] * bid[0] for bid in bids[:20]])  # الكمية × السعر
            ask_liquidity = sum([ask[1] * ask[0] for ask in asks[:20]])
            
            total_liquidity = bid_liquidity + ask_liquidity
            
            # Bid-Ask Spread
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread_percent = ((best_ask - best_bid) / best_bid) * 100
            
            # Order Book Imbalance (اختلال التوازن)
            imbalance = (bid_liquidity - ask_liquidity) / (bid_liquidity + ask_liquidity) if (bid_liquidity + ask_liquidity) > 0 else 0
            
            result = {
                'total_liquidity': total_liquidity,
                'bid_liquidity': bid_liquidity,
                'ask_liquidity': ask_liquidity,
                'spread': spread_percent,
                'imbalance': imbalance,
                'best_bid': best_bid,
                'best_ask': best_ask
            }
            
            # Cache
            self.cache[symbol] = (result, datetime.now())
            
            return result
        
        except Exception as e:
            return None
    
    def calculate_liquidity_score(self, symbol, analysis):
        """حساب نقاط السيولة"""
        try:
            order_book = self.get_order_book_depth(symbol)
            if not order_book:
                return 50  # محايد
            
            score = 50  # البداية من 50
            
            # 1. Spread (كلما أقل كلما أفضل)
            spread = order_book['spread']
            if spread < 0.05:
                score += 20  # ممتاز
            elif spread < 0.1:
                score += 10  # جيد
            elif spread < 0.2:
                score += 5   # مقبول
            elif spread > 0.5:
                score -= 20  # سيء جداً
            
            # 2. Total Liquidity (كلما أكثر كلما أفضل)
            liquidity = order_book['total_liquidity']
            if liquidity > 1000000:
                score += 15  # سيولة عالية جداً
            elif liquidity > 500000:
                score += 10  # سيولة عالية
            elif liquidity > 100000:
                score += 5   # سيولة متوسطة
            elif liquidity < 50000:
                score -= 15  # سيولة ضعيفة
            
            # 3. Order Book Imbalance
            imbalance = order_book['imbalance']
            if imbalance > 0.3:
                score += 10  # ضغط شراء قوي
            elif imbalance > 0.1:
                score += 5   # ضغط شراء متوسط
            elif imbalance < -0.3:
                score -= 15  # ضغط بيع قوي
            
            # الحد الأقصى 0-100
            score = max(0, min(100, score))
            
            return score
        
        except:
            return 50
    
    def should_trade_coin(self, symbol, analysis):
        """هل يجب التداول على هذه العملة؟"""
        try:
            liquidity_score = self.calculate_liquidity_score(symbol, analysis)
            
            # الحد الأدنى للسيولة
            if liquidity_score < 30:
                return {
                    'trade': False,
                    'reason': f'Low liquidity (score: {liquidity_score})',
                    'confidence_adjustment': -20
                }
            
            # سيولة ممتازة
            if liquidity_score >= 80:
                return {
                    'trade': True,
                    'reason': f'Excellent liquidity (score: {liquidity_score})',
                    'confidence_adjustment': 15
                }
            
            # سيولة جيدة
            elif liquidity_score >= 60:
                return {
                    'trade': True,
                    'reason': f'Good liquidity (score: {liquidity_score})',
                    'confidence_adjustment': 8
                }
            
            # سيولة مقبولة
            elif liquidity_score >= 40:
                return {
                    'trade': True,
                    'reason': f'Fair liquidity (score: {liquidity_score})',
                    'confidence_adjustment': 0
                }
            
            # سيولة ضعيفة
            else:
                return {
                    'trade': False,
                    'reason': f'Poor liquidity (score: {liquidity_score})',
                    'confidence_adjustment': -10
                }
        
        except:
            return {
                'trade': True,
                'reason': 'Liquidity check failed',
                'confidence_adjustment': 0
            }
    
    def get_best_coins(self, symbols, analysis_dict):
        """ترتيب العملات حسب السيولة"""
        try:
            scores = {}
            
            for symbol in symbols:
                analysis = analysis_dict.get(symbol)
                if analysis:
                    score = self.calculate_liquidity_score(symbol, analysis)
                    scores[symbol] = score
            
            # ترتيب تنازلي
            sorted_coins = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            
            return sorted_coins
        
        except:
            return []

    def detect_low_market_liquidity(self, symbols_list):
        """كشف سيولة منخفضة في السوق العام (متوسط السيولة للعملات + API خارجي)"""
        try:
            liquidity_scores = []
            for symbol in symbols_list[:10]:  # فحص أول 10 عملات
                score = self.calculate_liquidity_score(symbol, None)
                liquidity_scores.append(score)

            if not liquidity_scores:
                return {'low_liquidity': False, 'avg_score': 0}

            avg_score = sum(liquidity_scores) / len(liquidity_scores)

            # جلب سيولة عالمية من external_apis
            from src.external_apis import get_global_liquidity
            global_liquidity = get_global_liquidity()

            # دمج مع السيولة المحلية
            combined_score = (avg_score + global_liquidity) / 2

            # إذا متوسط السيولة منخفض (<40)، السوق غير سائل
            low_liquidity = combined_score < 40

            return {
                'low_liquidity': low_liquidity,
                'avg_score': combined_score,
                'warning': 'Market liquidity low - avoid large trades' if low_liquidity else 'Market liquidity OK'
            }

        except Exception as e:
            return {'low_liquidity': False, 'avg_score': 0}

  # افتراضي إذا فشل
