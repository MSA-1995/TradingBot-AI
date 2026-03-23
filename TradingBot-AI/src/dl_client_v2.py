"""
🧠 Deep Learning Client V3 - للبوت الرئيسي
يقرأ توقعات 8 موديلات (7 LSTM + 1 CNN) من قاعدة البيانات
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

class DeepLearningClientV2:
    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = None
        self._db_params = None
        self._connect_db()
        print("🧠 Deep Learning Client V3 initialized (8 Models: LightGBM)")
    
    def _connect_db(self):
        """Connect to PostgreSQL"""
        try:
            parsed = urlparse(self.database_url)
            self._db_params = {
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path[1:],
                'user': parsed.username,
                'password': unquote(parsed.password)
            }
            self.conn = psycopg2.connect(**self._db_params)
        except Exception as e:
            print(f"⚠️ DL Client V2 DB error: {e}")
            self.conn = None
    
    def _get_conn(self):
        """Get valid connection - reconnect if closed"""
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(**self._db_params)
        except Exception as e:
            print(f"⚠️ DL Client V2 reconnect error: {e}")
        return self.conn
    
    def get_model_accuracy(self, model_name):
        """الحصول على دقة موديل معين"""
        try:
            conn = self._get_conn()
            if not conn:
                return 0
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT accuracy
                FROM dl_models_v2
                WHERE model_name = %s
                AND status = 'active'
                ORDER BY trained_at DESC
                LIMIT 1
            """, (model_name,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result.get('accuracy', 0)
            return 0
        
        except Exception as e:
            return 0
    
    def get_mtf_prediction(self, rsi, macd, volume_ratio, price_momentum):
        """
        Multi-Timeframe: توقع الترند
        Returns: confidence_boost (-10 to +10)
        """
        accuracy = self.get_model_accuracy('mtf')
        
        if accuracy < 0.55:
            return 0
        
        # حساب Boost بناءً على الدقة
        if accuracy >= 0.70:
            boost = 8
        elif accuracy >= 0.65:
            boost = 5
        elif accuracy >= 0.60:
            boost = 3
        else:
            boost = 2
        
        # تعديل حسب المؤشرات
        if rsi < 30 and macd > 0:
            return boost
        elif rsi > 70 and macd < 0:
            return -boost
        else:
            return boost // 2
    
    def get_risk_prediction(self, rsi, volume_ratio, confidence, price_momentum):
        """
        Risk Manager: تقييم المخاطر
        Returns: risk_level ('low', 'medium', 'high'), confidence_adjustment
        """
        accuracy = self.get_model_accuracy('risk')
        
        if accuracy < 0.55:
            return {'risk_level': 'medium', 'confidence_adjustment': 0}
        
        # تقييم المخاطر
        risk_score = 0
        
        if rsi > 70:
            risk_score += 2
        if volume_ratio > 2.5:
            risk_score += 2
        if confidence < 65:
            risk_score += 1
        
        if risk_score >= 4:
            return {'risk_level': 'high', 'confidence_adjustment': -5}
        elif risk_score >= 2:
            return {'risk_level': 'medium', 'confidence_adjustment': 0}
        else:
            return {'risk_level': 'low', 'confidence_adjustment': 3}
    
    def get_anomaly_prediction(self, rsi, macd, volume_ratio, price_momentum):
        """
        Anomaly Detector: كشف الحالات الشاذة - نظام نقاط متوازن
        Returns: is_anomaly (bool), severity ('low', 'medium', 'high'), confidence_adjustment
        """
        accuracy = self.get_model_accuracy('anomaly')
        
        if accuracy < 0.55:
            return {'is_anomaly': False, 'severity': 'low', 'confidence_adjustment': 0}
        
        # كشف الشذوذ - نظام نقاط متوازن
        anomaly_score = 0
        
        # شذوذ خفيف
        if rsi < 25 or rsi > 75:
            anomaly_score += 1
        
        # شذوذ متوسط
        if volume_ratio > 2.5:
            anomaly_score += 2
        
        # شذوذ قوي
        if rsi < 15 or rsi > 85:
            anomaly_score += 3
        if volume_ratio > 4.0:
            anomaly_score += 3
        if abs(macd) > 20:
            anomaly_score += 2
        
        # حساب التعديل بناءً على الدقة
        boost_multiplier = 1.0
        if accuracy >= 0.75:
            boost_multiplier = 1.5
        elif accuracy >= 0.65:
            boost_multiplier = 1.2
        
        # القرار النهائي
        if anomaly_score >= 5:
            # شذوذ قوي جداً - تحذير قوي
            adjustment = int(-10 * boost_multiplier)
            return {'is_anomaly': True, 'severity': 'high', 'confidence_adjustment': adjustment}
        elif anomaly_score >= 3:
            # شذوذ متوسط - تحذير متوسط
            adjustment = int(-5 * boost_multiplier)
            return {'is_anomaly': True, 'severity': 'medium', 'confidence_adjustment': adjustment}
        elif anomaly_score >= 1:
            # شذوذ خفيف - تحذير خفيف
            adjustment = int(-2 * boost_multiplier)
            return {'is_anomaly': True, 'severity': 'low', 'confidence_adjustment': adjustment}
        else:
            # طبيعي
            return {'is_anomaly': False, 'severity': 'normal', 'confidence_adjustment': 0}
    
    def get_exit_prediction(self, rsi, macd, confidence, price_momentum, profit_percent):
        """
        Exit Strategy: متى نبيع؟ (غير مستخدم - البيع عبر التصويت فقط)
        Returns: should_exit (bool), reason, confidence_boost
        """
        # هذه الدالة غير مستخدمة - البيع يتم عبر vote_sell_now فقط
        return {'should_exit': False, 'reason': 'Hold', 'confidence_boost': 0}
    
    def get_pattern_prediction(self, rsi, macd, volume_ratio, price_momentum, confidence):
        """
        Pattern Recognition: التعرف على الأنماط
        Returns: pattern_type ('success', 'trap', 'neutral'), confidence_adjustment
        """
        accuracy = self.get_model_accuracy('pattern')
        
        if accuracy < 0.55:
            return {'pattern_type': 'neutral', 'confidence_adjustment': 0}
        
        # تحليل النمط
        pattern_score = 0
        
        if rsi < 30 and macd > 0 and volume_ratio > 1.5:
            pattern_score += 3  # نمط ناجح
        elif rsi > 70 and macd < 0:
            pattern_score -= 3  # فخ
        
        if pattern_score >= 2:
            return {'pattern_type': 'success', 'confidence_adjustment': 5}
        elif pattern_score <= -2:
            return {'pattern_type': 'trap', 'confidence_adjustment': -10}
        else:
            return {'pattern_type': 'neutral', 'confidence_adjustment': 0}
    
    def get_ranking_prediction(self, symbol):
        """
        Coin Ranking: تقييم العملة (قديم - سيتم استبداله بـ Liquidity)
        Returns: rank_score (0-100), should_trade (bool)
        """
        accuracy = self.get_model_accuracy('ranking')
        
        if accuracy < 0.55:
            return {'rank_score': 50, 'should_trade': True, 'confidence_adjustment': 0}
        
        # هنا يمكن إضافة منطق أكثر تعقيداً
        # حالياً نعتمد على الدقة فقط
        
        if accuracy >= 0.70:
            return {'rank_score': 80, 'should_trade': True, 'confidence_adjustment': 5}
        elif accuracy >= 0.60:
            return {'rank_score': 65, 'should_trade': True, 'confidence_adjustment': 2}
        else:
            return {'rank_score': 50, 'should_trade': True, 'confidence_adjustment': 0}
    
    def get_liquidity_prediction(self, liquidity_metrics):
        """
        Liquidity Analyzer: تحليل السيولة من Order Book
        Returns: liquidity_quality, should_trade, confidence_adjustment
        """
        accuracy = self.get_model_accuracy('liquidity')
        
        if accuracy < 0.55 or not liquidity_metrics:
            return {'liquidity_quality': 'medium', 'should_trade': True, 'confidence_adjustment': 0}
        
        # استخراج المقاييس
        liquidity_score = liquidity_metrics.get('liquidity_score', 50)
        spread_percent = liquidity_metrics.get('spread_percent', 0.1)
        depth_ratio = liquidity_metrics.get('depth_ratio', 1.0)
        price_impact = liquidity_metrics.get('price_impact', 0.5)
        volume_consistency = liquidity_metrics.get('volume_consistency', 50)
        
        # تقييم السيولة
        quality_score = 0
        
        # 1. Liquidity Score (0-100)
        if liquidity_score >= 80:
            quality_score += 3
        elif liquidity_score >= 60:
            quality_score += 1
        elif liquidity_score < 40:
            quality_score -= 2
        
        # 2. Spread
        if spread_percent < 0.1:
            quality_score += 2
        elif spread_percent > 0.5:
            quality_score -= 3
        
        # 3. Depth Ratio (التوازن)
        if 0.8 <= depth_ratio <= 1.3:
            quality_score += 2
        elif depth_ratio < 0.6 or depth_ratio > 1.6:
            quality_score -= 2
        
        # 4. Price Impact
        if price_impact < 0.2:
            quality_score += 2
        elif price_impact > 1.0:
            quality_score -= 3
        
        # 5. Volume Consistency
        if volume_consistency >= 70:
            quality_score += 1
        elif volume_consistency < 40:
            quality_score -= 1
        
        # حساب التعديل بناءً على الدقة
        boost_multiplier = 1.0
        if accuracy >= 0.75:
            boost_multiplier = 1.5
        elif accuracy >= 0.65:
            boost_multiplier = 1.2
        
        # القرار النهائي
        if quality_score >= 6:
            adjustment = int(8 * boost_multiplier)
            return {'liquidity_quality': 'excellent', 'should_trade': True, 'confidence_adjustment': adjustment}
        elif quality_score >= 3:
            adjustment = int(4 * boost_multiplier)
            return {'liquidity_quality': 'good', 'should_trade': True, 'confidence_adjustment': adjustment}
        elif quality_score >= 0:
            return {'liquidity_quality': 'medium', 'should_trade': True, 'confidence_adjustment': 0}
        elif quality_score >= -3:
            adjustment = int(-5 * boost_multiplier)
            return {'liquidity_quality': 'poor', 'should_trade': True, 'confidence_adjustment': adjustment}
        else:
            adjustment = int(-10 * boost_multiplier)
            return {'liquidity_quality': 'very_poor', 'should_trade': False, 'confidence_adjustment': adjustment}
    
    def get_chart_cnn_prediction(self, rsi, macd, volume_ratio, price_momentum):
        """
        Chart Pattern Analyzer (CNN): تحليل أنماط الشارت
        Returns: pattern_detected, confidence_adjustment
        """
        accuracy = self.get_model_accuracy('chart_cnn')
        
        if accuracy < 0.55:
            return {'pattern_detected': 'neutral', 'confidence_adjustment': 0}
        
        # تحليل النمط البصري
        pattern_score = 0
        
        # نمط صاعد
        if rsi < 35 and macd > 0 and volume_ratio > 1.3:
            pattern_score += 3
        
        # نمط هابط
        if rsi > 65 and macd < 0:
            pattern_score -= 2
        
        # حساب التعديل بناءً على الدقة
        if accuracy >= 0.80:
            boost_multiplier = 1.5
        elif accuracy >= 0.70:
            boost_multiplier = 1.2
        else:
            boost_multiplier = 1.0
        
        if pattern_score >= 2:
            adjustment = int(5 * boost_multiplier)
            return {'pattern_detected': 'bullish', 'confidence_adjustment': adjustment}
        elif pattern_score <= -2:
            adjustment = int(-8 * boost_multiplier)
            return {'pattern_detected': 'bearish', 'confidence_adjustment': adjustment}
        else:
            return {'pattern_detected': 'neutral', 'confidence_adjustment': 0}
    
    def vote_tp_target(self, rsi, macd, volume_ratio, price_momentum, confidence):
        """
        المستشارين يصوتون على TP (Take Profit)
        Returns: tp_votes (dict with each consultant's vote)
        """
        votes = {}
        
        # Exit Strategy vote (0.5% - 10%)
        votes['exit'] = min(max(2.0 + (confidence - 60) * 0.1, 0.5), 10.0)
        
        # MTF vote
        if macd > 0:
            votes['mtf'] = min(max(3.0 + (volume_ratio - 1) * 2, 0.5), 10.0)
        else:
            votes['mtf'] = 2.0
        
        # Risk vote (conservative)
        votes['risk'] = min(max(1.5 if rsi > 70 else 2.5, 0.5), 10.0)
        
        # Pattern vote
        votes['pattern'] = min(max(2.5 + (confidence - 65) * 0.08, 0.5), 10.0)
        
        # CNN vote
        votes['cnn'] = min(max(2.0 + abs(macd) * 0.2, 0.5), 10.0)
        
        # Anomaly vote (conservative if anomaly detected)
        votes['anomaly'] = min(max(1.8 if rsi > 75 else 2.3, 0.5), 10.0)
        
        # Ranking vote
        votes['ranking'] = min(max(2.8, 0.5), 10.0)
        
        return votes
    
    def vote_amount(self, rsi, macd, volume_ratio, confidence, risk_vote=None):
        """
        المستشارين + Risk Manager يصوتون على المبلغ ($12 - $20)
        Returns: amount_votes (dict with each consultant's vote)
        """
        votes = {}
        
        # Exit Strategy vote
        votes['exit'] = 15.0
        
        # MTF vote (aggressive if strong trend)
        if macd > 5:
            votes['mtf'] = min(18.0, 20.0)
        else:
            votes['mtf'] = 14.0
        
        # Risk vote (conservative)
        votes['risk'] = 13.0 if rsi > 70 else 16.0
        
        # Pattern vote
        votes['pattern'] = 16.0
        
        # CNN vote
        votes['cnn'] = 15.0
        
        # Anomaly vote
        votes['anomaly'] = 13.5
        
        # Ranking vote
        votes['ranking'] = 17.0
        
        # Risk Manager vote (مستشار ثامن - Kelly Criterion)
        if risk_vote is not None:
            votes['risk_manager'] = max(12.0, min(20.0, risk_vote))
        
        # Ensure all votes are within bounds ($12 - $20)
        for key in votes:
            votes[key] = max(12.0, min(20.0, votes[key]))
        
        return votes
    
    def vote_stop_loss(self, rsi, macd, volume_ratio, confidence, risk_vote=None):
        """
        المستشارين + Risk Manager يصوتون على SL (Stop Loss: -0.1% to -2%)
        Returns: sl_votes (dict with each consultant's vote)
        """
        votes = {}
        
        # Exit Strategy vote
        votes['exit'] = -1.5
        
        # MTF vote (patient if strong trend)
        if macd > 0:
            votes['mtf'] = -2.0  # patient
        else:
            votes['mtf'] = -1.3
        
        # Risk vote (strict)
        votes['risk'] = -0.8 if rsi > 70 else -1.5
        
        # Pattern vote
        votes['pattern'] = -1.8
        
        # CNN vote
        votes['cnn'] = -1.6
        
        # Anomaly vote (strict if anomaly)
        votes['anomaly'] = -1.0
        
        # Ranking vote
        votes['ranking'] = -1.7
        
        # Risk Manager vote (مستشار ثامن)
        if risk_vote is not None:
            votes['risk_manager'] = max(-2.0, min(-0.1, risk_vote))
        
        # Ensure all votes are within bounds (-0.1% to -2%)
        for key in votes:
            votes[key] = max(-2.0, min(-0.1, votes[key]))
        
        return votes
    
    def get_ai_brain_prediction(self, rsi, macd, volume_ratio, price_momentum, confidence, 
                                mtf_score=0, risk_score=0, anomaly_score=0, 
                                exit_score=0, pattern_score=0, ranking_score=0, cnn_score=0):
        """
        👑 AI Brain: القرار النهائي (يستشير 7 مستشارين)
        Returns: should_buy (bool), confidence_boost
        """
        accuracy = self.get_model_accuracy('ai_brain')
        
        if accuracy < 0.55:
            return {'should_buy': True, 'confidence_boost': 0}  # neutral
        
        # الملك يحلل كل شي
        brain_score = 0
        
        # تحليل المؤشرات الأساسية
        if rsi < 30 and macd > 0:
            brain_score += 3
        if volume_ratio > 1.5:
            brain_score += 2
        if confidence >= 70:
            brain_score += 2
        
        # تحليل المستشارين
        if mtf_score > 5:
            brain_score += 2
        if risk_score < 0:  # مخاطر عالية
            brain_score -= 3
        if anomaly_score > 0:  # شذوذ
            brain_score -= 2
        if pattern_score > 0:
            brain_score += 2
        
        # القرار النهائي
        if brain_score >= 5:
            boost = int(10 * (accuracy - 0.5))  # كلما زادت الدقة، زاد التأثير
            return {'should_buy': True, 'confidence_boost': boost}
        elif brain_score <= -3:
            return {'should_buy': False, 'confidence_boost': -10}
        else:
            return {'should_buy': True, 'confidence_boost': 0}
    
    def get_buy_decision(self, symbol, analysis):
        """
        قرار الشراء الشامل من كل الموديلات (المستشارين + الملك)
        """
        try:
            rsi = analysis.get('rsi', 50)
            macd = analysis.get('macd_diff', 0)
            volume_ratio = analysis.get('volume_ratio', 1)
            price_momentum = analysis.get('price_momentum', 0)
            confidence = analysis.get('confidence', 60)
            
            # جمع توقعات المستشارين (7 مستشارين)
            mtf_boost = self.get_mtf_prediction(rsi, macd, volume_ratio, price_momentum)
            risk_result = self.get_risk_prediction(rsi, volume_ratio, confidence, price_momentum)
            anomaly_result = self.get_anomaly_prediction(rsi, macd, volume_ratio, price_momentum)
            pattern_result = self.get_pattern_prediction(rsi, macd, volume_ratio, price_momentum, confidence)
            ranking_result = self.get_ranking_prediction(symbol)
            cnn_result = self.get_chart_cnn_prediction(rsi, macd, volume_ratio, price_momentum)
            
            # حساب التعديل من المستشارين (بما فيهم Anomaly)
            consultants_adjustment = (
                mtf_boost +
                risk_result['confidence_adjustment'] +
                anomaly_result['confidence_adjustment'] +  # يعطي -10 أو -5 أو -2 أو 0
                pattern_result['confidence_adjustment'] +
                ranking_result['confidence_adjustment'] +
                cnn_result['confidence_adjustment']
            )
            
            # فحص الشذوذ القوي جداً فقط (CRITICAL)
            # ملاحظة: anomaly_result من DL client مختلف عن anomaly_detector من models
            # هنا نعتمد على confidence_adjustment بدل الرفض المباشر
            
            # فحص النمط
            if pattern_result['pattern_type'] == 'trap':
                return {
                    'action': 'SKIP',
                    'reason': 'Trap pattern detected',
                    'confidence_adjustment': 0
                }
            
            # فحص المخاطر
            if risk_result['risk_level'] == 'high':
                consultants_adjustment -= 5
            
            # 👑 استشارة الملك (القرار النهائي)
            brain_result = self.get_ai_brain_prediction(
                rsi, macd, volume_ratio, price_momentum, confidence,
                mtf_score=mtf_boost,
                risk_score=risk_result['confidence_adjustment'],
                anomaly_score=1 if anomaly_result['is_anomaly'] else 0,
                exit_score=0,
                pattern_score=pattern_result['confidence_adjustment'],
                ranking_score=ranking_result['confidence_adjustment'],
                cnn_score=cnn_result['confidence_adjustment']
            )
            
            # الملك يقرر
            if not brain_result['should_buy']:
                return {
                    'action': 'SKIP',
                    'reason': 'AI Brain rejected',
                    'confidence_adjustment': brain_result['confidence_boost']
                }
            
            # حساب التعديل النهائي (المستشارين + الملك)
            total_adjustment = consultants_adjustment + brain_result['confidence_boost']
            
            return {
                'action': 'BUY' if total_adjustment > 0 else 'SKIP',
                'reason': 'Consultants approved' if total_adjustment > 0 else 'Low confidence',
                'confidence_adjustment': total_adjustment,
                'mtf_boost': mtf_boost,
                'risk_level': risk_result['risk_level'],
                'pattern_type': pattern_result['pattern_type'],
                'rank_score': ranking_result['rank_score'],
                'cnn_pattern': cnn_result['pattern_detected'],
                'brain_boost': brain_result['confidence_boost']
            }
        
        except Exception as e:
            print(f"⚠️ Buy decision error: {e}")
            return {'action': 'SKIP', 'confidence_adjustment': 0}
    
    def get_sell_decision(self, symbol, position, current_price, analysis):
        """
        قرار البيع الشامل (غير مستخدم - البيع عبر ai_brain.should_sell فقط)
        """
        # هذه الدالة غير مستخدمة - البيع يتم عبر ai_brain.should_sell + التصويت
        return {'action': 'HOLD', 'reason': 'Use ai_brain.should_sell instead'}
    
    def is_available(self):
        """فحص إذا الموديلات متوفرة"""
        try:
            conn = self._get_conn()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'dl_models_v2'
                )
            """)
            exists = cursor.fetchone()[0]
            cursor.close()
            
            return exists
        except:
            return False
    
    def get_models_status(self):
        """الحصول على حالة كل الموديلات"""
        try:
            conn = self._get_conn()
            if not conn:
                return {}
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT model_name, accuracy, trained_at
                FROM dl_models_v2
                WHERE status = 'active'
                ORDER BY model_name
            """)
            
            results = cursor.fetchall()
            cursor.close()
            
            status = {}
            for row in results:
                status[row['model_name']] = {
                    'accuracy': row['accuracy'],
                    'trained_at': str(row['trained_at'])
                }
            
            return status
        
        except Exception as e:
            return {}

    def vote_sell_now(self, symbol, profit_percent, rsi, macd, volume_ratio, trend, hours_held,
                      market_sentiment=None, highest_profit_percent=0, drop_from_high_percent=0):
        """
        المستشارين يراقبون ويصوتون: هل نبيع الحين؟
        
        بالربح: يراقبون العملة + السوق (BTC+ETH+BNB) - لو السوق بينقلب → بيع (كفاية طمع)
        بالخسارة: يراقبون العملة + السوق - لو السوق نازل → بيع (قبل تنزل أكثر)
        
        market_sentiment: {'btc_change_1h': float, 'eth_change_1h': float, 'bnb_change_1h': float}
        highest_profit_percent: أعلى ربح وصله السعر منذ الشراء
        drop_from_high_percent: كم نزل السعر من الذروة كنسبة من سعر الشراء
        شروط متوسطة - لا صارمة ولا متساهلة
        Returns: sell_votes (dict: 1=SELL, 0=HOLD)
        """
        votes = {}
        
        # استخراج بيانات السوق
        btc_change = 0
        eth_change = 0
        bnb_change = 0
        market_falling = False
        market_rising = False
        
        if market_sentiment:
            btc_change = market_sentiment.get('btc_change_1h', 0)
            eth_change = market_sentiment.get('eth_change_1h', 0)
            bnb_change = market_sentiment.get('bnb_change_1h', 0)
            
            # حساب متوسط التغير
            avg_change = (btc_change + eth_change + bnb_change) / 3
            
            # السوق نازل: أغلبية < -1% أو متوسط < -1%
            falling_count = sum(1 for c in [btc_change, eth_change, bnb_change] if c < -1.0)
            market_falling = (falling_count >= 2 or avg_change < -1.0)
            
            # السوق طالع: أغلبية > +1% أو متوسط > +1%
            rising_count = sum(1 for c in [btc_change, eth_change, bnb_change] if c > 1.0)
            market_rising = (rising_count >= 2 or avg_change > 1.0)
        
        # --- نظام اكتشاف القمة (Reversal Consensus) ---
        # نراقب 4 عوامل، إذا تحققت 3 منها نبيع فوراً عند القمة
        reversal_score = 0
        
        # 1. شكل الشمعة/التشبع (RSI): تشبع شرائي متوسط (65) بدلاً من الصارم (70)
        if rsi > 65: reversal_score += 1
            
        # 2. حجم التداول (Volume): فوليوم نشط (1.5) بدلاً من الانفجاري (2.5)
        if volume_ratio > 1.5: reversal_score += 1
            
        # 3. الزخم والتقارب (MACD): ضعف العزم (سلبي) رغم وجود السعر في القمة
        if macd < 0: reversal_score += 1
            
        # 4. ضغط السوق (Market): السوق العام بدأ ينزف
        if market_falling: reversal_score += 1
            
        # شرط "الشمعة الحمراء/بداية الانعكاس": السعر نزل قليلاً عن أعلى نقطة (ليس في قمة الاندفاع)
        is_reversing = (drop_from_high_percent > 0.0)
        
        # إشارة القمة: اتفاق 3 من 4 مؤشرات + ربح يغطي الرسوم (> 0.8%) + بداية انعكاس فعلي
        peak_signal = (profit_percent > 0.8 and reversal_score >= 3 and is_reversing)
        
        # Exit Strategy - يراقب الربح والخسارة + السوق
        if profit_percent > 0:
            # ربح: (> 1% + السوق نازل) أو اكتشاف القمة (تم حذف هدف 2.5% الثابت)
            votes['exit'] = 1 if ((profit_percent > 1.0 and market_falling) or peak_signal) else 0
        else:
            # خسارة: لا نبيع، نعتمد على Trailing Stop (-2%) في AI Brain فقط
            votes['exit'] = 0 
        
        # MTF - يراقب الترند + السوق
        if profit_percent > 0:
            # ربح: bearish + ربح > 1% أو (ربح > 0.5% + السوق نازل قوي) أو اكتشاف القمة
            votes['mtf'] = 1 if (trend == 'bearish' and profit_percent > 1.0) or (profit_percent > 0.5 and btc_change < -1.5) or peak_signal else 0
        else:
            # خسارة: bearish + خسارة < -0.5% أو (خسارة < -0.3% + السوق نازل)
            votes['mtf'] = 0
        
        # Risk - محافظ + يشوف السوق
        if profit_percent > 0:
            # ربح: RSI > 78 أو (ربح > 1.5% + السوق نازل) أو اكتشاف القمة
            votes['risk'] = 1 if (rsi > 78 or (profit_percent > 1.5 and market_falling) or peak_signal) else 0
        else:
            # خسارة: لا نبيع
            votes['risk'] = 0 
        
        # Pattern - يراقب الأنماط + السوق
        if profit_percent > 0:
            # ربح: > 2% + MACD سالب قوي أو (> 1% + السوق نازل + MACD < -5) أو اكتشاف القمة
            votes['pattern'] = 1 if (profit_percent > 2.0 and macd < -7) or (profit_percent > 1.0 and market_falling and macd < -5) or peak_signal else 0
        else:
            # خسارة: لا نبيع
            votes['pattern'] = 0
        
        # CNN - يراقب الشارت + السوق
        if profit_percent > 0:
            # ربح: (> 1.2% + السوق نازل) أو اكتشاف القمة (تم حذف هدف 2.5% الثابت)
            votes['cnn'] = 1 if ((profit_percent > 1.2 and market_falling) or peak_signal) else 0
        else:
            # خسارة: لا نبيع
            votes['cnn'] = 0
        
        # Anomaly - يكشف الشذوذ + السوق
        if profit_percent > 0:
            # ربح: RSI شاذ جداً (> 85) أو (RSI > 75 + السوق نازل) أو اكتشاف القمة
            votes['anomaly'] = 1 if (rsi > 85 or (rsi > 75 and market_falling) or peak_signal) else 0
        else:
            # خسارة: لا نبيع
            votes['anomaly'] = 0
        
        # Liquidity - الشيخ + السوق
        if profit_percent > 0:
            # ربح: (> 1% + السوق نازل) أو اكتشاف القمة (تم حذف هدف 2.5% الثابت)
            votes['liquidity'] = 1 if ((profit_percent > 1.0 and market_falling) or peak_signal) else 0
        else:
            # خسارة: لا نبيع
            votes['liquidity'] = 0
        
        return votes
    
    def get_market_sentiment(self, btc_change_1h, eth_change_1h, bnb_change_1h):
        """
        تحليل السوق العام (BTC + ETH + BNB)
        Returns: market_status, min_votes_required
        """
        # حساب متوسط التغير
        changes = [btc_change_1h, eth_change_1h, bnb_change_1h]
        avg_change = sum(changes) / len(changes)
        
        # عد العملات النازلة/الطالعة
        falling_count = sum(1 for c in changes if c < -1.0)
        rising_count = sum(1 for c in changes if c > 1.0)
        
        # Strong Bearish: توقف تام
        # أغلبية نازلة (2/3 أو أكثر) أو متوسط < -2%
        if falling_count >= 2 or avg_change < -2.0:
            return 'strong_bearish', 8  # مستحيل (8/7) = توقف
        
        # Bearish: حذر (نحتاج 5/7)
        # واحدة نازلة قوي أو متوسط < -1%
        if falling_count >= 1 or avg_change < -1.0:
            return 'bearish', 5
        
        # Neutral/Bullish: عادي (3/7)
        return 'neutral', 3
    
    def vote_buy_now(self, rsi, macd, volume_ratio, price_momentum, confidence, liquidity_metrics=None, market_sentiment=None, candle_analysis=None):
        """
        المستشارين يصوتون: هل نشتري؟ (BUY/SKIP)
        market_sentiment: {'btc_change_1h': float, 'eth_change_1h': float, 'bnb_change_1h': float}
        candle_analysis: {'is_rejection': bool, 'is_accumulation': bool}
        Returns: buy_votes (dict with each consultant's vote: 1=BUY, 0=SKIP), min_votes_required
        """
        # فحص السوق العام أولاً
        min_votes_required = 3  # default
        market_status = 'neutral'
        
        # استخراج تحليل الشموع (القناص)
        is_rejection = False
        is_accumulation = False
        if candle_analysis:
            is_rejection = candle_analysis.get('is_rejection', False)
            is_accumulation = candle_analysis.get('is_accumulation', False)
        
        if market_sentiment:
            btc_change = market_sentiment.get('btc_change_1h', 0)
            eth_change = market_sentiment.get('eth_change_1h', 0)
            bnb_change = market_sentiment.get('bnb_change_1h', 0)
            market_status, min_votes_required = self.get_market_sentiment(btc_change, eth_change, bnb_change)
        
        votes = {}
        
        # 1. Exit Strategy (القناص):
        # يشتري في حالتين:
        # أ. فرصة رخيصة جداً (RSI < 42) - كلاسيكي
        # ب. فرصة ذكية (RSI < 55 + وجود ذيل رفض أو تجميع) -> هذا هو الدهاء!
        votes['exit'] = 1 if (rsi < 42 or (rsi < 55 and (is_rejection or is_accumulation))) else 0
        
        # 2. MTF vote (صائد الانفجار):
        # شراء لو MACD موجب + volume عالي (كلاسيكي)
        # أو لو فيه تجميع واضح (فوليوم عالي وسعر ثابت) حتى لو MACD لسه ما قلب
        votes['mtf'] = 1 if ((macd > 0 and volume_ratio > 1.2) or is_accumulation) else 0
        
        # 3. Risk vote (محافظ - متوسط الصرامة):
        votes['risk'] = 1 if (rsi < 65 and confidence >= 65) else 0
        
        # 4. Pattern vote (الأنماط):
        votes['pattern'] = 1 if (confidence >= 60 and (price_momentum > 0 or is_rejection)) else 0
        
        # 5. CNN vote (الزخم):
        votes['cnn'] = 1 if ((macd > 2 and volume_ratio > 1.0) or (is_rejection and volume_ratio > 1.5)) else 0
        
        # 6. Anomaly vote (كاشف الفخاخ):
        # يرفض الشراء إذا الفوليوم جنوني (> 4.0) لأنه غالباً تصريف (Panic Dump)
        # يسمح بالشراء في القاع (RSI < 30) فقط إذا كان هناك "ذيل رفض" (ارتداد)
        votes['anomaly'] = 1 if (volume_ratio < 4.0 and (rsi > 30 or is_rejection)) else 0
        
        # Liquidity vote (الشيخ - محلل السيولة)
        if liquidity_metrics:
            liquidity_pred = self.get_liquidity_prediction(liquidity_metrics)
            liquidity_score = liquidity_metrics.get('liquidity_score', 50)
            spread = liquidity_metrics.get('spread_percent', 0.1)
            
            # شراء لو السيولة جيدة
            votes['liquidity'] = 1 if (
                liquidity_pred['should_trade'] and 
                liquidity_score >= 60 and 
                spread < 0.3
            ) else 0
        else:
            # fallback للطريقة القديمة
            votes['liquidity'] = 1 if confidence >= 60 else 0
        
        return votes, min_votes_required, market_status