"""
🧠 Smart AI - الذكاء الحقيقي (بدون TensorFlow)
يستخدم القواعد الذكية + التعلم من Database
"""

import os
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
        
        # تحميل الأفخاخ من Database
        self.trap_memory = []
        self._load_traps()
        
        # إحصائيات
        self.predictions_count = 0
        self.correct_predictions = 0
        
    def _load_model(self):
        """استخدام القواعد الذكية + التعلم من Database"""
        self.nn_model = None
        self.scaler = None
        self.enabled = True  # تفعيل الذكاء بدون TensorFlow
    
    def _load_traps(self):
        """تحميل الأفخاخ من Database"""
        try:
            from storage import StorageManager
            storage = StorageManager()
            self.trap_memory = storage.load_traps()
            if self.trap_memory:
                print(f"🚨 Loaded {len(self.trap_memory)} traps from database")
        except Exception as e:
            print(f"⚠️ Could not load traps: {e}")
            self.trap_memory = []
    
    def should_buy(self, symbol, analysis, mtf, price_drop, news_sentiment=None):
        """
        القرار الذكي: هل نشتري؟ (بدون TensorFlow)
        """
        try:
            # 1. فحص الأفخاخ
            if self._is_trap(symbol, analysis):
                return {
                    'action': 'SKIP',
                    'confidence': 0,
                    'reason': '🚨 Matches known trap pattern'
                }
            
            # 2. تحليل الأنماط (بدون NN)
            pattern_score = self._analyze_patterns(analysis, mtf)
            news_score = self._analyze_news(news_sentiment) if news_sentiment else 0.5
            
            # 3. تحليل من Database
            db_score = self._analyze_from_database(symbol, analysis)
            
            # 4. دمج القرارات
            final_confidence = (
                pattern_score * 0.4 +  # 40% للأنماط
                news_score * 0.2 +      # 20% للأخبار
                db_score * 0.4          # 40% للتعلم من Database
            )
            
            # 5. القرار النهائي
            if final_confidence >= 0.70:  # 70% ثقة
                return {
                    'action': 'BUY',
                    'confidence': int(final_confidence * 100),
                    'amount': self._calculate_smart_amount(final_confidence, analysis),
                    'reason': f'Smart AI: Pattern={pattern_score:.2f} News={news_score:.2f} DB={db_score:.2f}',
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
    
    def _analyze_from_database(self, symbol, analysis):
        """تحليل من الصفقات السابقة في Database"""
        try:
            from storage import StorageManager
            storage = StorageManager()
            
            # جلب آخر 20 صفقة للعملة
            trades = storage.get_symbol_trades(symbol, limit=20)
            
            if not trades or len(trades) < 5:
                return 0.5  # محايد - ما فيه بيانات كافية
            
            # حساب Win Rate
            wins = sum(1 for t in trades if t.get('profit_percent', 0) > 0)
            win_rate = wins / len(trades)
            
            # حساب متوسط الربح
            avg_profit = sum(t.get('profit_percent', 0) for t in trades) / len(trades)
            
            # حساب Score
            score = 0.5
            
            # Win Rate Boost
            if win_rate > 0.7:  # 70% نجاح
                score += 0.2
            elif win_rate > 0.6:
                score += 0.1
            elif win_rate < 0.4:  # 40% فشل
                score -= 0.2
            
            # Average Profit Boost
            if avg_profit > 2.0:  # ربح عالي
                score += 0.1
            elif avg_profit < -1.0:  # خسارة
                score -= 0.1
            
            return max(0, min(1, score))
            
        except Exception as e:
            return 0.5  # محايد
    
    def _analyze_news(self, news_sentiment):
        """تحليل الأخبار"""
        if not news_sentiment:
            return 0
        
        # تحويل news sentiment (-10 to +10) إلى (0 to 1)
        score = (news_sentiment + 10) / 20
        return max(0, min(1, score))
    
    def _is_trap(self, symbol, analysis):
        """فحص إذا كان النمط يشبه فخ سابق"""
        if not self.trap_memory:
            return False
        
        try:
            current_pattern = {
                'rsi': analysis.get('rsi'),
                'macd_diff': analysis.get('macd_diff'),
                'volume': analysis.get('volume_ratio')
            }
            
            for trap in self.trap_memory:
                trap_pattern = trap.get('pattern', {})
                if not trap_pattern:
                    continue
                
                # حساب التشابه
                similarity = self._calculate_pattern_similarity(current_pattern, trap_pattern)
                
                if similarity > 0.85:  # 85% مشابه
                    return True
            
            return False
        except Exception as e:
            return False
    
    def _calculate_pattern_similarity(self, pattern1, pattern2):
        """حساب التشابه بين نمطين"""
        try:
            score = 0
            count = 0
            
            # RSI
            if pattern1.get('rsi') and pattern2.get('rsi'):
                diff = abs(pattern1['rsi'] - pattern2['rsi'])
                score += max(0, 1 - diff / 100)
                count += 1
            
            # Volume
            if pattern1.get('volume') and pattern2.get('volume'):
                diff = abs(pattern1['volume'] - pattern2['volume'])
                score += max(0, 1 - diff / 2)
                count += 1
            
            # MACD
            if pattern1.get('macd_diff') and pattern2.get('macd_diff'):
                diff = abs(pattern1['macd_diff'] - pattern2['macd_diff'])
                score += max(0, 1 - diff / 50)
                count += 1
            
            return score / count if count > 0 else 0
        except:
            return 0
    

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
        التعلم من الصفقة (حفظ في Database فقط)
        """
        try:
            from storage import StorageManager
            storage = StorageManager()
            
            # حفظ الصفقة
            storage.save_trade(trade_result)
            
            # حفظ الفخ إذا خسرانة
            if trade_result.get('profit_percent', 0) < -1.5:  # خسارة > 1.5%
                trap_data = {
                    'symbol': trade_result.get('symbol'),
                    'pattern': {
                        'rsi': trade_result.get('rsi'),
                        'macd_diff': trade_result.get('macd_diff'),
                        'volume': trade_result.get('volume'),
                        'confidence': trade_result.get('confidence')
                    },
                    'loss': trade_result.get('profit_percent'),
                    'reason': trade_result.get('sell_reason')
                }
                storage.save_trap(trap_data)
                print(f"🚨 Trap detected and saved: {trade_result.get('symbol')} ({trade_result.get('profit_percent'):.2f}%)")
            
            # تحديث الإحصائيات
            self.predictions_count += 1
            if trade_result.get('profit_percent', 0) > 0:
                self.correct_predictions += 1
            
            # إعادة تحميل الأفخاخ كل 10 صفقات
            if self.predictions_count % 10 == 0:
                self._load_traps()
                print(f"🔄 Traps reloaded after {self.predictions_count} trades")
            
        except Exception as e:
            print(f"⚠️ Learning error: {e}")
    

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
