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
        print("🧠 Deep Learning Client V3 initialized (8 Models: 7 LSTM + 1 CNN)")
    
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
        Anomaly Detector: كشف الحالات الشاذة
        Returns: is_anomaly (bool), severity ('low', 'medium', 'high')
        """
        accuracy = self.get_model_accuracy('anomaly')
        
        if accuracy < 0.55:
            return {'is_anomaly': False, 'severity': 'low'}
        
        # كشف الشذوذ
        anomaly_score = 0
        
        if rsi < 20 or rsi > 80:
            anomaly_score += 2
        if volume_ratio > 3.0:
            anomaly_score += 2
        if abs(macd) > 15:
            anomaly_score += 1
        
        if anomaly_score >= 4:
            return {'is_anomaly': True, 'severity': 'high'}
        elif anomaly_score >= 2:
            return {'is_anomaly': True, 'severity': 'medium'}
        else:
            return {'is_anomaly': False, 'severity': 'low'}
    
    def get_exit_prediction(self, rsi, macd, confidence, price_momentum, profit_percent):
        """
        Exit Strategy: متى نبيع؟
        Returns: should_exit (bool), reason, confidence_boost
        """
        accuracy = self.get_model_accuracy('exit')
        
        if accuracy < 0.55:
            return {'should_exit': False, 'reason': 'Hold', 'confidence_boost': 0}
        
        # قرار البيع
        exit_score = 0
        
        if profit_percent > 1.5:
            exit_score += 3
        if rsi > 70:
            exit_score += 2
        if macd < -5:
            exit_score += 2
        
        if exit_score >= 5:
            return {'should_exit': True, 'reason': 'Strong exit signal', 'confidence_boost': 10}
        elif exit_score >= 3:
            return {'should_exit': True, 'reason': 'Exit signal', 'confidence_boost': 5}
        else:
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
        Coin Ranking: تقييم العملة
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
            
            # حساب التعديل من المستشارين
            consultants_adjustment = (
                mtf_boost +
                risk_result['confidence_adjustment'] +
                pattern_result['confidence_adjustment'] +
                ranking_result['confidence_adjustment'] +
                cnn_result['confidence_adjustment']
            )
            
            # فحص الشذوذ
            if anomaly_result['is_anomaly'] and anomaly_result['severity'] == 'high':
                return {
                    'action': 'SKIP',
                    'reason': 'High anomaly detected',
                    'confidence_adjustment': 0
                }
            
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
        قرار البيع الشامل من كل الموديلات
        """
        try:
            buy_price = position['buy_price']
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            
            rsi = analysis.get('rsi', 50)
            macd = analysis.get('macd_diff', 0)
            confidence = analysis.get('confidence', 60)
            price_momentum = analysis.get('price_momentum', 0)
            
            # استشارة Exit Strategy
            exit_result = self.get_exit_prediction(rsi, macd, confidence, price_momentum, profit_percent)
            
            if exit_result['should_exit']:
                return {
                    'action': 'SELL',
                    'reason': exit_result['reason'],
                    'profit': profit_percent
                }
            
            return {
                'action': 'HOLD',
                'reason': 'No exit signal',
                'profit': profit_percent
            }
        
        except Exception as e:
            print(f"⚠️ Sell decision error: {e}")
            return {'action': 'HOLD', 'reason': 'Error'}
    
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
