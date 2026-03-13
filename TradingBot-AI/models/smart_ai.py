"""
🧠 Smart AI - الذكاء الحقيقي
يجمع Neural Network + Pattern Recognition + News Analysis
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime

class SmartAI:
    def __init__(self):
        self.nn_model = None
        self.scaler = None
        self.feature_names = []
        self.enabled = False
        
        # محاولة تحميل النموذج
        self._load_model()
        
        # إحصائيات
        self.predictions_count = 0
        self.correct_predictions = 0
        
    def _load_model(self):
        """تحميل Neural Network إذا موجود"""
        try:
            import tensorflow as tf
            from tensorflow import keras
            import pickle
            
            model_path = 'simple_ai_model.h5'
            scaler_path = 'scaler.pkl'
            
            if os.path.exists(model_path) and os.path.exists(scaler_path):
                self.nn_model = keras.models.load_model(model_path)
                
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                
                with open('feature_names.pkl', 'rb') as f:
                    self.feature_names = pickle.load(f)
                
                self.enabled = True
                print("🧠 Smart AI: ACTIVE (Neural Network loaded)")
            else:
                print("⚠️ Smart AI: Model not found - will train on first run")
                self.enabled = False
                
        except Exception as e:
            print(f"⚠️ Smart AI: Could not load model - {e}")
            self.enabled = False
    
    def should_buy(self, symbol, analysis, mtf, price_drop, news_sentiment=None):
        """
        القرار الذكي: هل نشتري؟
        """
        # لو النموذج مو جاهز - استخدم القواعد البسيطة
        if not self.enabled:
            return self._fallback_decision(analysis, mtf, price_drop)
        
        try:
            # 1. تحضير Features للـ Neural Network
            features = self._prepare_features(analysis, mtf, price_drop, news_sentiment)
            
            # 2. التنبؤ بالـ Neural Network
            nn_probability = self._predict_with_nn(features)
            
            # 3. تحليل إضافي (Pattern + News)
            pattern_score = self._analyze_patterns(analysis, mtf)
            news_score = self._analyze_news(news_sentiment) if news_sentiment else 0
            
            # 4. دمج القرارات
            final_confidence = self._combine_decisions(
                nn_probability, 
                pattern_score, 
                news_score
            )
            
            # 5. القرار النهائي
            if final_confidence >= 0.75:  # 75% ثقة
                return {
                    'action': 'BUY',
                    'confidence': int(final_confidence * 100),
                    'amount': self._calculate_smart_amount(final_confidence, analysis),
                    'reason': f'Smart AI: NN={nn_probability:.2f} Pattern={pattern_score:.2f} News={news_score:.2f}',
                    'tp_target': self._calculate_tp(final_confidence),
                    'sl_target': self._calculate_sl(final_confidence),
                    'max_wait_hours': self._calculate_wait_time(final_confidence)
                }
            else:
                return {
                    'action': 'SKIP',
                    'confidence': int(final_confidence * 100),
                    'reason': f'Low confidence ({final_confidence:.2f})'
                }
                
        except Exception as e:
            print(f"⚠️ Smart AI error: {e}")
            return self._fallback_decision(analysis, mtf, price_drop)
    
    def _prepare_features(self, analysis, mtf, price_drop, news_sentiment):
        """تحضير Features للـ Neural Network"""
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume = analysis.get('volume_ratio', 1.0)
        
        # حساب confidence أساسي
        confidence = 50
        if rsi < 30:
            confidence += 20
        if macd_diff > 0:
            confidence += 10
        if volume > 1.5:
            confidence += 10
        
        # Handle NaN
        if pd.isna(rsi):
            rsi = 50
        if pd.isna(macd_diff):
            macd_diff = 0
        if pd.isna(volume):
            volume = 1.0
        
        return [rsi, macd_diff, volume, confidence]
    
    def _predict_with_nn(self, features):
        """التنبؤ باستخدام Neural Network"""
        try:
            # Normalize
            features_scaled = self.scaler.transform([features])
            
            # Predict
            probability = self.nn_model.predict(features_scaled, verbose=0)[0][0]
            
            return float(probability)
        except Exception as e:
            print(f"⚠️ NN prediction error: {e}")
            return 0.5  # محايد
    
    def _analyze_patterns(self, analysis, mtf):
        """تحليل الأنماط"""
        score = 0.5  # محايد
        
        # RSI Pattern
        rsi = analysis.get('rsi', 50)
        if not pd.isna(rsi):
            if rsi < 25:
                score += 0.15
            elif rsi < 30:
                score += 0.10
        
        # Trend Pattern
        if mtf.get('trend') == 'bullish':
            score += 0.10
        elif mtf.get('trend') == 'bearish':
            score -= 0.10
        
        # Volume Pattern
        volume = analysis.get('volume_ratio', 1.0)
        if not pd.isna(volume) and volume > 2.0:
            score += 0.10
        
        return max(0, min(1, score))
    
    def _analyze_news(self, news_sentiment):
        """تحليل الأخبار"""
        if not news_sentiment:
            return 0
        
        # تحويل news sentiment (-10 to +10) إلى (0 to 1)
        score = (news_sentiment + 10) / 20
        return max(0, min(1, score))
    
    def _combine_decisions(self, nn_prob, pattern_score, news_score):
        """دمج القرارات بأوزان ذكية"""
        # الأوزان
        nn_weight = 0.5      # 50% للـ Neural Network
        pattern_weight = 0.3  # 30% للأنماط
        news_weight = 0.2     # 20% للأخبار
        
        final = (
            nn_prob * nn_weight +
            pattern_score * pattern_weight +
            news_score * news_weight
        )
        
        return final
    
    def _calculate_smart_amount(self, confidence, analysis):
        """حساب المبلغ الذكي"""
        from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT
        
        # كلما زادت الثقة، زاد المبلغ
        if confidence >= 0.85:
            return MAX_TRADE_AMOUNT
        elif confidence >= 0.75:
            return (MIN_TRADE_AMOUNT + MAX_TRADE_AMOUNT) / 2
        else:
            return MIN_TRADE_AMOUNT
    
    def _calculate_tp(self, confidence):
        """حساب Take Profit الذكي"""
        if confidence >= 0.85:
            return 1.5  # هدف أعلى
        elif confidence >= 0.75:
            return 1.2
        else:
            return 1.0
    
    def _calculate_sl(self, confidence):
        """حساب Stop Loss الذكي"""
        if confidence >= 0.85:
            return 2.5  # صبر أكثر
        elif confidence >= 0.75:
            return 2.0
        else:
            return 1.5  # حماية سريعة
    
    def _calculate_wait_time(self, confidence):
        """حساب وقت الانتظار"""
        if confidence >= 0.85:
            return 72  # انتظار أطول
        elif confidence >= 0.75:
            return 48
        else:
            return 36
    
    def _fallback_decision(self, analysis, mtf, price_drop):
        """قرار احتياطي (قواعد بسيطة)"""
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        volume = analysis.get('volume_ratio', 1.0)
        
        confidence = 50
        
        if not pd.isna(rsi) and rsi < 30:
            confidence += 20
        if not pd.isna(macd_diff) and macd_diff > 0:
            confidence += 15
        if not pd.isna(volume) and volume > 1.5:
            confidence += 15
        
        if confidence >= 70:
            return {
                'action': 'BUY',
                'confidence': confidence,
                'amount': 12,
                'reason': 'Fallback rules',
                'tp_target': 1.0,
                'sl_target': 2.0,
                'max_wait_hours': 48
            }
        else:
            return {
                'action': 'SKIP',
                'confidence': confidence,
                'reason': f'Low confidence ({confidence})'
            }
    
    def should_sell(self, symbol, position, current_price, analysis, mtf):
        """القرار الذكي: هل نبيع؟"""
        buy_price = position['buy_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        
        # الأهداف الذكية
        tp_target = position.get('tp_target', 1.0)
        sl_target = position.get('sl_target', 2.0)
        max_wait_hours = position.get('max_wait_hours', 48)
        
        # حساب المدة
        try:
            buy_time = datetime.fromisoformat(position['buy_time'])
            hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except:
            hours_held = 24
        
        # 1. TP الذكي
        if profit_percent >= tp_target:
            return {
                'action': 'SELL',
                'reason': f'SMART TP {tp_target}%',
                'profit': profit_percent
            }
        
        # 2. Bearish Exit
        if mtf.get('trend') == 'bearish' and profit_percent > 0:
            return {
                'action': 'SELL',
                'reason': 'BEARISH TREND',
                'profit': profit_percent
            }
        
        # 3. Stop Loss الذكي
        highest_price = position.get('highest_price', buy_price)
        trailing_stop = highest_price * (1 - sl_target / 100)
        
        if current_price <= trailing_stop:
            return {
                'action': 'SELL',
                'reason': f'SMART SL {sl_target}%',
                'profit': profit_percent
            }
        
        # 4. Timeout
        if hours_held >= max_wait_hours and profit_percent < 0:
            return {
                'action': 'SELL',
                'reason': f'TIMEOUT {max_wait_hours}h',
                'profit': profit_percent
            }
        
        # 5. Hold
        return {
            'action': 'HOLD',
            'reason': 'Waiting for target'
        }
    
    def learn_from_trade(self, trade_result):
        """
        التعلم من الصفقة
        """
        try:
            from storage import StorageManager
            storage = StorageManager()
            
            # حفظ الصفقة
            storage.save_trade(trade_result)
            
            # تحديث الإحصائيات
            self.predictions_count += 1
            if trade_result.get('profit_percent', 0) > 0:
                self.correct_predictions += 1
            
            # إعادة التدريب كل 50 صفقة
            if self.predictions_count % 50 == 0:
                print(f"\n🎓 Auto-retraining after {self.predictions_count} trades...")
                self._auto_retrain()
            
        except Exception as e:
            print(f"⚠️ Learning error: {e}")
    
    def _auto_retrain(self):
        """إعادة التدريب التلقائي"""
        try:
            print("🔄 Starting auto-retrain...")
            
            # تشغيل التدريب
            import subprocess
            import sys
            result = subprocess.run(
                [sys.executable, 'simple_ai_trainer.py'],
                capture_output=True,
                text=True,
                timeout=300  # 5 دقائق max
            )
            
            if result.returncode == 0:
                print("✅ Auto-retrain completed!")
                # إعادة تحميل النموذج
                self._load_model()
            else:
                print(f"⚠️ Auto-retrain failed: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️ Auto-retrain error: {e}")
    
    def get_statistics(self):
        """إحصائيات الأداء"""
        if self.predictions_count == 0:
            return None
        
        accuracy = self.correct_predictions / self.predictions_count * 100
        
        return {
            'total_predictions': self.predictions_count,
            'correct': self.correct_predictions,
            'accuracy': accuracy,
            'enabled': self.enabled
        }
