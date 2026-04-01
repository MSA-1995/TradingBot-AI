"""
🧠 Deep Learning Client V3 - للبوت الرئيسي
يقرأ توقعات 8 موديلات (7 LSTM + 1 CNN) من قاعدة البيانات
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

ADVISORS_LEARNING_FILE = 'data/advisors_learning.json'

class DeepLearningClientV2:
    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = None
        self._db_params = None
        self._connect_db()
        self._load_learning_data()
        print("🧠 Deep Learning Client V3 initialized (LightGBM)")
    
    def _load_learning_data(self):
        """تحميل بيانات تعلم المستشارين"""
        os.makedirs('data', exist_ok=True)
        if os.path.exists(ADVISORS_LEARNING_FILE):
            with open(ADVISORS_LEARNING_FILE, 'r') as f:
                self.learning_data = json.load(f)
        else:
            self.learning_data = {
                'exit': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 0.5},
                'mtf': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 0},
                'risk': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.0},
                'pattern': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 0},
                'cnn': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.0},
                'anomaly': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.5},
                'liquidity': {'buy_success': 0, 'buy_fail': 0, 'sell_success': 0, 'sell_fail': 0, 'threshold': 1.1}
            }
    
    def _save_learning_data(self):
        """حفظ بيانات تعلم المستشارين"""
        with open(ADVISORS_LEARNING_FILE, 'w') as f:
            json.dump(self.learning_data, f, indent=2, ensure_ascii=False)
    
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
    
    def get_model_data(self, model_name):
        """يجلب البيانات الثنائية (binary data) لنموذج معين من قاعدة البيانات."""
        try:
            conn = self._get_conn()
            if not conn:
                print(f"⚠️ DL Client: No DB connection to get model data for {model_name}.")
                return None
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT model_data
                FROM dl_models_v2
                WHERE model_name = %s
                ORDER BY trained_at DESC
                LIMIT 1
            """, (model_name,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result and result.get('model_data'):
                # The data is returned as a memoryview, which is what pickle.loads expects
                return result['model_data']
            else:
                print(f"⚠️ DL Client: Model data for '{model_name}' not found in the database.")
                return None
        
        except Exception as e:
            print(f"❌ DL Client: Error getting model data for {model_name}: {e}")
            return None

    
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
            
            # الملك (Meta) يقرر في meta.py، هنا نرجع نتيجة المستشارين فقط
            return {
                'action': 'BUY' if consultants_adjustment > 0 else 'SKIP',
                'reason': 'Consultants approved' if consultants_adjustment > 0 else 'Low confidence',
                'confidence_adjustment': consultants_adjustment,
                'mtf_boost': mtf_boost,
                'risk_level': risk_result['risk_level'],
                'pattern_type': pattern_result['pattern_type'],
                'rank_score': ranking_result['rank_score'],
                'cnn_pattern': cnn_result['pattern_detected']
            }
        
        except Exception as e:
            print(f"⚠️ Buy decision error: {e}")
            return {'action': 'SKIP', 'confidence_adjustment': 0}
    
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

    def vote_sell_now(self, rsi, macd, volume_ratio, price_momentum, liquidity_metrics=None, candle_analysis=None):
        """
        البيع: يصوتون بالقمة مع صبر لحلب العملة - نظام متوازن محسّن
        """
        votes = {}

        # استخراج تحليل الشموع (شمعة قمة)
        is_peak_candle = False
        if candle_analysis:
            is_peak_candle = candle_analysis.get('is_peak', False)

        # 1. Exit Strategy (القناص) - يصوت بالقمة مع صبر:
        # RSI > 72 أو (RSI > 68 و شمعة قمة)
        votes['exit'] = 1 if (rsi > 72 or (rsi > 68 and is_peak_candle)) else 0

        # 2. MTF vote (صائد الانفجار) - يصوت عند ضعف واضح:
        # MACD ضعيف جداً (< -0.3) أو Volume نزل كثير (< 0.6)
        votes['mtf'] = 1 if (macd < -0.3 or volume_ratio < 0.6) else 0

        # 3. Risk vote (محافظ) - يصوت عند RSI عالي جداً:
        # RSI > 70 (تشبع شرائي واضح)
        votes['risk'] = 1 if rsi > 70 else 0

        # 4. Pattern vote (الأنماط) - يصوت عند ضعف واضح:
        # momentum سالب قوي (< -0.5) أو شمعة قمة
        votes['pattern'] = 1 if (price_momentum < -0.5 or is_peak_candle) else 0

        # 5. CNN vote (الزخم) - يصوت عند ضعف واضح:
        # MACD ضعيف جداً (< -0.5) أو Volume نزل كثير
        votes['cnn'] = 1 if (macd < -0.5 or volume_ratio < 0.7) else 0

        # 6. Anomaly vote (كاشف الفخاخ) - يصوت إذا مافي فخ:
        # Volume طبيعي (< 4.0) و RSI مو متطرف
        votes['anomaly'] = 1 if (volume_ratio < 4.0 and 25 < rsi < 85) else 0

        # 7. Liquidity vote (الشيخ - محلل السيولة) - يصوت عند ضعف واضح:
        # score نزل كثير (< 45) أو Volume نزل كثير
        liquidity_score = liquidity_metrics.get('liquidity_score', 50) if liquidity_metrics else 50
        votes['liquidity'] = 1 if (liquidity_score < 45 or volume_ratio < 0.7) else 0

        return votes
    
    def vote_buy_now(self, rsi, macd, volume_ratio, trend, mtf_score):
        """يصوت المستشار على الشراء الفوري بناءً على معايير محددة"""
        score = 0
        reasons = []

        # 1. RSI في منطقة التشبع بالبيع (< 30)
        if rsi < 30:
            score += 25
            reasons.append("RSI Oversold")

        # 2. مؤشر MACD الإيجابي
        if macd > 0.1:
            score += 20
            reasons.append("Positive MACD")

        # 3. نسبة حجم الشراء المرتفعة
        if volume_ratio > 1.2:
            score += 15
            reasons.append("High Buy Volume")

        # 4. اتجاه صاعد
        if trend == 1:  # 1 يمثل الاتجاه الصاعد
            score += 25
            reasons.append("Uptrend")

        # 5. تحليل الإطار الزمني المتعدد (MTF)
        if mtf_score > 70:
            score += 15
            reasons.append("Strong MTF Signal")

        # إذا لم تتحقق أي من الشروط، لا يوجد تصويت للشراء
        if score == 0:
            return None

        return {
            "score": min(score, 100),  # تأكد من أن النتيجة لا تتجاوز 100
            "reasons": ", ".join(reasons)
        }

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
    
    def vote_buy_now(self, rsi, macd, volume_ratio, price_momentum, confidence, liquidity_metrics=None, market_sentiment=None, candle_analysis=None, peak_hunter_signal='neutral'):
        """
        المستشارين يصوتون: هل نشتري؟ (BUY/SKIP) - نظام وسطي محسّن
        market_sentiment: {'btc_change_1h': float, 'eth_change_1h': float, 'bnb_change_1h': float}
        candle_analysis: {'is_rejection': bool, 'is_accumulation': bool}
        Returns: buy_votes (dict with each consultant's vote: 1=BUY, 0=SKIP), market_status (str)
        """
        # فحص السوق العام أولاً
        
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
            market_status, _ = self.get_market_sentiment(btc_change, eth_change, bnb_change)
        
        votes = {}
        
        # 1. Exit Strategy (القناص) - وسطي محسّن:
        # RSI < 50 + تأكيد شمعة أو RSI < 60 بدون تأكيد
        has_confirmed_candle = is_rejection or is_accumulation
        votes['exit'] = 1 if (rsi < 50 or (rsi < 60 and has_confirmed_candle)) else 0
        
        # 2. MTF vote (صائد الانفجار) - وسطي محسّن:
        # MACD > 0 + Volume > 1.0
        votes['mtf'] = 1 if (macd > 0 and volume_ratio > 1.0) else 0
        
        # 3. Risk vote (محافظ) - وسطي:
        # RSI < 72 (ما يكون في تشبع شرائي)
        votes['risk'] = 1 if rsi < 72 else 0
        
        # 4. Pattern vote (الأنماط) - وسطي محسّن:
        # momentum إيجابي (> -0.5) أو تأكيد شمعة
        votes['pattern'] = 1 if (price_momentum > -0.5 or is_rejection) else 0
        
        # 5. CNN vote (الزخم) - وسطي محسّن:
        # MACD > 0.2 + Volume > 0.9
        votes['cnn'] = 1 if (macd > 0.2 and volume_ratio > 0.9) else 0
        
        # 6. Anomaly vote (كاشف الفخاخ) - وسطي محسّن:
        # Volume < 6.0 + RSI بين 10-90
        votes['anomaly'] = 1 if (volume_ratio < 6.0 and 10 < rsi < 90) else 0
        
        # 7. Liquidity vote (الشيخ - محلل السيولة) - وسطي محسّن:
        # liquidity_score ≥ 50 + Volume > 0.8
        if liquidity_metrics:
            liquidity_score = liquidity_metrics.get('liquidity_score', 50)
            votes['liquidity'] = 1 if (liquidity_score >= 50 and volume_ratio > 0.8) else 0
        else:
            votes['liquidity'] = 1 if volume_ratio > 0.8 else 0
        
        return votes, market_status

    # =========================================================
    # 🎓 التعلم المباشر للمستشارين ال7 - يتعلمون من كل صفقة
    # =========================================================
    def learn_from_trade(self, profit, trade_quality, buy_votes, sell_votes, signal_type='sell'):
        """
        التعلم المباشر من كل صفقة
        كل مستشار يتعلم من أخطائه بدون أوزان متفاوتة
        """
        try:
            if signal_type == 'sell' and sell_votes:
                for advisor, voted in sell_votes.items():
                    if advisor in self.learning_data:
                        if trade_quality in ['GREAT', 'GOOD', 'OK']:
                            if voted == 1:
                                self.learning_data[advisor]['sell_success'] += 1
                            else:
                                self.learning_data[advisor]['sell_fail'] += 1
                        elif trade_quality in ['RISKY', 'TRAP']:
                            if voted == 1:
                                self.learning_data[advisor]['sell_fail'] += 1
                            else:
                                self.learning_data[advisor]['sell_success'] += 1
            
            elif signal_type == 'buy' and buy_votes:
                for advisor, voted in buy_votes.items():
                    if advisor in self.learning_data:
                        if profit > 0.5:
                            if voted == 1:
                                self.learning_data[advisor]['buy_success'] += 1
                            else:
                                self.learning_data[advisor]['buy_fail'] += 1
                        elif profit < -0.5:
                            if voted == 1:
                                self.learning_data[advisor]['buy_fail'] += 1
                            else:
                                self.learning_data[advisor]['buy_success'] += 1
            
            self._save_learning_data()
            
            # طباعة التعلم
            print(f"🎓 المستشارون تعلموا: {trade_quality} | profit: {profit:+.2f}%")
            
        except Exception as e:
            print(f"⚠️ خطأ في تعلم المستشارين: {e}")
    
    def get_advisor_accuracy(self, advisor_name):
        """حساب دقة المستشار (0-100)"""
        if advisor_name not in self.learning_data:
            return 50
        
        data = self.learning_data[advisor_name]
        total = data['buy_success'] + data['buy_fail'] + data['sell_success'] + data['sell_fail']
        
        if total < 5:
            return 50
        
        success = data['buy_success'] + data['sell_success']
        return round((success / total) * 100, 1)
    
    def get_all_advisors_accuracy(self):
        """دقة جميع المستشارين"""
        return {name: self.get_advisor_accuracy(name) for name in self.learning_data.keys()}
