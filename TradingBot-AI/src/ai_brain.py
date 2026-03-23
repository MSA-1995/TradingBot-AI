"""
AI Brain - العقل المفكر
يقرر، يتعلم، يتحسن (ضمن الحدود الآمنة)
"""
from datetime import datetime
import sys
import os
import pickle # <<< لاستيراد عقل الملك
import pandas as pd

# إضافة المسار الصحيح
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from storage.storage_manager import StorageManager

class AIBrain:
    def __init__(self, boundaries):
        self.storage = StorageManager()
        self.boundaries = boundaries
        self.learned_patterns = []
        self.trap_memory = []
        self.meta_learner = None # <<< الملك الجديد
        
        # إضافة الخبل (Rescue Scalper)
        try:
            from models.rescue_scalper import RescueScalper
            self.rescue_scalper = RescueScalper()
        except Exception as e:
            print(f"⚠️ Could not load RescueScalper: {e}")
            self.rescue_scalper = None
        
        # تحميل المعرفة السابقة
        self.load_knowledge()
        self.load_meta_learner() # <<< تحميل عقل الملك
        
        # Smart Money Tracker (optional)
        try:
            import sys
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from models.smart_money_tracker import SmartMoneyTracker
            self.smart_money_tracker = None  # Will be set externally
        except:
            self.smart_money_tracker = None
        
        # Deep Learning Client (optional)
        try:
            from dl_client_v2 import DeepLearningClientV2
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                self.dl_client = DeepLearningClientV2(database_url)
                if self.dl_client.is_available():
                    print("🧠 AI Brain: Deep Learning connected!")
                else:
                    self.dl_client = None
            else:
                self.dl_client = None
        except Exception as e:
            print(f"⚠️ AI Brain: Deep Learning not available: {e}")
            self.dl_client = None
        
        print("🧠 AI Brain initialized")
        print(f"📊 Loaded {len(self.learned_patterns)} patterns")
        print(f"🚫 Loaded {len(self.trap_memory)} traps")
    
    def load_knowledge(self):
        """تحميل المعرفة من التخزين"""
        try:
            self.learned_patterns = self.storage.load_patterns()
            self.trap_memory = self.storage.load_traps()
        except Exception as e:
            print(f"⚠️ Error loading knowledge: {e}")
            self.learned_patterns = []
            self.trap_memory = []

    def load_meta_learner(self):
        """تحميل عقل الملك الجديد المدرب من قاعدة البيانات"""
        try:
            # محاولة تحميل النموذج من قاعدة البيانات
            model_data = self.storage.load_model_from_db('meta_learner_model.pkl')
            if model_data:
                # استخدام pickle.loads لتحميل النموذج من البيانات الثنائية
                self.meta_learner = pickle.loads(model_data)
                print("👑🧠 New King's Brain (Meta-Learner) loaded successfully from DB!")
            else:
                print("⚠️ Meta-Learner model not found in DB. The old king will rule.")
                self.meta_learner = None
        except Exception as e:
            print(f"❌ Error loading Meta-Learner model from DB: {e}")
            self.meta_learner = None

    def is_meta_learner_active(self):
        """Check if the new king is ruling"""
        return self.meta_learner is not None
    
    def should_buy(self, symbol, analysis, mtf, price_drop, models_scores=None, risk_manager=None):
        """
        القرار الذكي: هل نشتري؟ (باستخدام الملك الجديد)
        """
        # إذا كان الملك الجديد موجوداً، استخدمه. وإلا، استخدم النظام القديم.
        if self.meta_learner:
            return self.should_buy_with_meta_learner(symbol, analysis, models_scores, risk_manager)
        else:
            return self.should_buy_old_system(symbol, analysis, mtf, price_drop, models_scores, risk_manager)

    def should_buy_with_meta_learner(self, symbol, analysis, models_scores, risk_manager):
        """القرار باستخدام الملك الجديد (Meta-Learner)"""
        
        models_scores = models_scores or {}
        
        # 1. جمع آراء المستشارين (المدخلات للملك)
        # يجب أن يكون ترتيبهم بنفس ترتيب التدريب بالضبط
        feature_names = [
            'ai_brain', 'smart_money', 'risk', 'anomaly', 'exit', 
            'pattern', 'liquidity', 'chart_cnn', 'rescue'
        ]
        consultant_opinions = [models_scores.get(name, 0) for name in feature_names]

        # 2. استشارة الملك الجديد
        try:
            # تحويل الآراء إلى تنسيق مناسب للملك (DataFrame with feature names)
            opinions_df = pd.DataFrame([consultant_opinions], columns=feature_names)
            
            # الحصول على القرار ونسبة الثقة
            prediction = self.meta_learner.predict(opinions_df)[0]
            probability = self.meta_learner.predict_proba(opinions_df)[0]
            
            confidence = int(probability[1] * 100) # الثقة هي احتمالية الشراء

        except Exception as e:
            print(f"❌ Meta-Learner prediction error: {e}")
            return {'action': 'SKIP', 'reason': 'Meta-Learner error', 'confidence': 0}

        # 3. القرار النهائي بناءً على رأي الملك
        if prediction == 1 and confidence >= 55:
            amount = self._calculate_smart_amount(symbol, confidence, analysis, risk_manager=risk_manager)
            decision = {
                'action': 'BUY',
                'confidence': confidence,
                'amount': amount,
                'reason': f'Meta-Learner approved with {confidence}% confidence',
                # ... (يمكن إضافة بيانات أخرى هنا إذا لزم الأمر)
            }
            # لا داعي لحفظ القرار هنا، سيتم حفظه في trading_bot
            return decision
        else:
            reason = f'Meta-Learner rejected with {confidence}% confidence'
            if prediction == 0:
                reason = f'Meta-Learner voted SKIP'
            elif confidence < 55:
                reason = f'Meta-Learner confidence {confidence}% < 55%'

            return {'action': 'SKIP', 'reason': reason, 'confidence': confidence}


    def should_buy_old_system(self, symbol, analysis, mtf, price_drop, models_scores=None, risk_manager=None):
        """
        القرار الذكي: هل نشتري؟
        models_scores: dict with scores from all models (optional)
        """
        from learning.safety_validator import SafetyValidator
        from learning.pattern_detector import PatternDetector
        
        # 1. التحليل الأساسي
        base_confidence = self._calculate_base_confidence(analysis, mtf, price_drop)

        # Add market mood score to confidence
        if models_scores and 'market_mood' in models_scores:
            base_confidence += models_scores.get('market_mood', 0)
        
        # 1.5. شرط تأكيد الانعكاس (جديد)
        reversal_info = analysis.get('reversal', {})
        if not reversal_info.get('is_reversing', False):
            return {
                'action': 'SKIP',
                'reason': f"No reversal confirmation (bounce: {reversal_info.get('bounce_percent', 0):.2f}%)",
                'confidence': 0
            }

        # 2. فحص الفخاخ
        if self._is_trap_pattern(symbol, analysis):
            decision = {
                'action': 'SKIP',
                'reason': 'Matches known trap pattern',
                'confidence': 0
            }
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'SKIP',
                'reason': 'Trap detected',
                'confidence': base_confidence
            })
            return decision
        
        # 3. البحث عن أنماط مشابهة ناجحة
        similar_success = self._find_similar_patterns(analysis, pattern_type='SUCCESS')
        
        # 4. تحسين الـ Confidence بناءً على التعلم
        optimized_confidence = self._optimize_confidence(
            base_confidence, 
            similar_success
        )
        
        # 4.5. Deep Learning Boost (المستشارين + الملك)
        if self.dl_client:
            try:
                # استشارة المستشارين + الملك
                dl_decision = self.dl_client.get_buy_decision(symbol, {
                    'rsi': analysis.get('rsi', 50),
                    'macd_diff': analysis.get('macd_diff', 0),
                    'volume_ratio': analysis.get('volume_ratio', 1),
                    'price_momentum': analysis.get('price_momentum', 0),
                    'confidence': optimized_confidence
                })
                
                if dl_decision['action'] == 'SKIP':
                    # الملك أو المستشارين رفضوا
                    decision = {
                        'action': 'SKIP',
                        'reason': dl_decision['reason'],
                        'confidence': optimized_confidence
                    }
                    self.storage.save_ai_decision({
                        'symbol': symbol,
                        'decision': 'SKIP',
                        'reason': dl_decision['reason'],
                        'confidence': optimized_confidence
                    })
                    return decision
                
                # الملك وافق - نضيف التعديل
                dl_boost = dl_decision.get('confidence_adjustment', 0)
                brain_boost = dl_decision.get('brain_boost', 0)
                
                if dl_boost > 0 or brain_boost > 0:
                    optimized_confidence += dl_boost
                    # رسالة محذوفة - التصويت يطبع تحت
            except Exception as e:
                print(f"⚠️ DL decision error: {e}")
        
        # 5. التحقق من الحدود الآمنة
        validator = SafetyValidator(self.boundaries)
        is_safe = validator.validate_decision({
            'confidence': optimized_confidence,
            'volume': analysis['volume_ratio'],
            'rsi': analysis['rsi'],
            'macd': analysis['macd_diff']
        })
        
        if not is_safe:
            decision = {
                'action': 'SKIP',
                'reason': 'Failed safety validation',
                'confidence': optimized_confidence
            }
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'SKIP',
                'reason': 'Safety check failed',
                'confidence': optimized_confidence
            })
            return decision
        
        # 6. القرار النهائي
        if optimized_confidence >= 55:  # استخدام 55 (أكثر عدوانية للتعلم على Testnet)
            
            # 🗳️ المستشارين يصوتون: هل نشتري؟
            buy_votes = {}
            buy_vote_count = 0
            total_consultants = 0
            min_votes_required = 3  # default
            market_status = 'neutral'

            if self.dl_client:
                try:
                    # 🚨 حماية صارمة: منع الشراء نهائياً إذا لم يكن هناك مستشارين
                    if not self.dl_client.is_available():
                        decision = {
                            'action': 'SKIP',
                            'reason': 'No consultants available (DL Client offline) - Safety Block',
                            'confidence': optimized_confidence
                        }
                        self.storage.save_ai_decision({
                            'symbol': symbol,
                            'decision': 'SKIP',
                            'reason': 'Safety Block: DL Client offline',
                            'confidence': optimized_confidence
                        })
                        # إرسال إشعار
                        from notifications import send_safety_block_notification
                        send_safety_block_notification(symbol, 'DL Client is offline')
                        return decision

                    # تجميع البيانات اللازمة للتصويت
                    rsi = analysis.get('rsi', 50)
                    macd = analysis.get('macd_diff', 0)
                    volume_ratio = analysis.get('volume_ratio', 1.0)
                    price_momentum = analysis.get('price_momentum', 0)
                    liquidity_metrics = analysis.get('liquidity', {})

                    # بيانات السوق
                    market_sentiment_data = {
                        'btc_change_1h': analysis.get('btc_change_1h', 0),
                        'eth_change_1h': analysis.get('eth_change_1h', 0)
                    }

                    # تحليل الشموع
                    candle_analysis = self._analyze_candle(analysis)

                    # استدعاء دالة التصويت الموحدة
                    buy_votes, market_status = self.dl_client.vote_buy_now(
                        rsi, macd, volume_ratio, price_momentum, optimized_confidence,
                        liquidity_metrics, market_sentiment_data, candle_analysis
                    )

                    buy_vote_count = sum(buy_votes.values())
                    total_consultants = len(buy_votes)

                    # تحديد الأصوات المطلوبة ديناميكياً
                    if market_status == 'strong_bearish':
                        min_votes_required = total_consultants + 1  # مستحيل للشراء
                    elif market_status == 'bearish':
                        min_votes_required = int(total_consultants * 0.7)  # 70% موافقة
                    else:  # neutral or bullish
                        min_votes_required = int(total_consultants * 0.4)  # 40% موافقة
                    
                    # الملك يقرر بناءً على min_votes_required (يتغير حسب السوق)
                    buy_percentage = (buy_vote_count / total_consultants * 100) if total_consultants > 0 else 0
                    
                    # فحص السوق العام
                    if market_status == 'strong_bearish':
                        # السوق نازل قوي - توقف تام
                        decision = {
                            'action': 'SKIP',
                            'reason': f'Market strong bearish (BTC/ETH < -2%)',
                            'confidence': optimized_confidence
                        }
                        self.storage.save_ai_decision({
                            'symbol': symbol,
                            'decision': 'SKIP',
                            'reason': 'Market strong bearish',
                            'confidence': optimized_confidence
                        })
                        return decision
                    
                    if buy_vote_count < min_votes_required:
                        # لم يصل للحد المطلوب
                        decision = {
                            'action': 'SKIP',
                            'reason': f'Consultants voted SKIP ({buy_vote_count}/{min_votes_required} required, market: {market_status})',
                            'confidence': optimized_confidence
                        }
                        self.storage.save_ai_decision({
                            'symbol': symbol,
                            'decision': 'SKIP',
                            'reason': f'Voting rejected: {buy_vote_count}/{total_consultants} (need {min_votes_required}, market: {market_status})',
                            'confidence': optimized_confidence
                        })
                        return decision
                    
                    print(f"🗳️ {symbol}: {buy_vote_count}/{total_consultants} voted BUY ({buy_percentage:.0f}%) | Market: {market_status} | Required: {min_votes_required}/7")
                
                except Exception as e:
                    print(f"⚠️ Buy voting error: {e}")
                    # Fallback: continue without voting
            
            # حساب المبلغ الذكي
            amount = self._calculate_smart_amount(symbol, optimized_confidence, analysis, risk_manager=risk_manager)
            
            # تم إلغاء توقعات السعر والأيام (الاعتماد على القناص والستوب المتحرك فقط)
            # smart_targets = self._calculate_smart_targets(...)
            
            decision = {
                'action': 'BUY',
                'confidence': optimized_confidence,
                'amount': amount,
                'tp_target': None,
                'sl_target': None,
                'max_wait_hours': 72,  # شرط الزومبي الثابت (3 أيام)
                'reason': f'AI optimized from {base_confidence} to {optimized_confidence}',
                'success_probability': self._estimate_success_probability(similar_success),
                'buy_vote_percentage': (buy_vote_count / total_consultants * 100) if total_consultants > 0 else 0,
                'buy_vote_count': buy_vote_count,
                'total_consultants': total_consultants,
                'buy_votes': buy_votes,  # حفظ تصويت كل مستشار
                'ai_data': {
                    'rsi': analysis.get('rsi', 50),
                    'macd': analysis.get('macd_diff', 0),
                    'volume_ratio': analysis.get('volume_ratio', 1),
                    'price_momentum': analysis.get('price_momentum', 0),
                    'confidence': optimized_confidence,
                    'mtf_score': models_scores.get('mtf', 0) if models_scores else 0,
                    'risk_score': models_scores.get('risk', 0) if models_scores else 0,
                    'anomaly_score': models_scores.get('anomaly', 0) if models_scores else 0,
                    'exit_score': models_scores.get('exit', 0) if models_scores else 0,
                    'pattern_score': models_scores.get('pattern', 0) if models_scores else 0,
                    'ranking_score': models_scores.get('ranking', 0) if models_scores else 0,
                    'market_mood_score': models_scores.get('market_mood', 0) if models_scores else 0,
                    'predicted_tp': 0,
                    'predicted_sl': 0,
                    'predicted_amount': amount,
                    # المؤشرات الـ 5 الجديدة
                    'atr': analysis.get('atr', 0),
                    'ema_9': analysis.get('ema_9', 0),
                    'ema_21': analysis.get('ema_21', 0),
                    'bid_ask_spread': analysis.get('bid_ask_spread', 0),
                    'volume_trend': analysis.get('volume_trend', 0),
                    'price_change_1h': analysis.get('price_change_1h', 0)
                }
            }
            
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'BUY',
                'confidence': optimized_confidence,
                'amount': amount,
                'tp_target': 0,
                'sl_target': 0,
                'max_wait_hours': 72,
                'base_confidence': base_confidence,
                'reasoning': decision['reason']
            })
            
            return decision
        else:
            decision = {
                'action': 'SKIP',
                'reason': f'Confidence {optimized_confidence} < 55',
                'confidence': optimized_confidence
            }
            return decision
    
    def _calculate_base_confidence(self, analysis, mtf, price_drop):
        """حساب Confidence الأساسي (نفس النظام الحالي)"""
        import pandas as pd
        
        rsi = analysis.get('rsi', 50)
        macd_diff = analysis.get('macd_diff', 0)
        momentum = analysis.get('price_momentum', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        trend = mtf.get('trend', 'neutral')
        drop_percent = price_drop.get('drop_percent', 0)
        
        # Handle NaN values
        if pd.isna(rsi):
            rsi = 50
        if pd.isna(macd_diff):
            macd_diff = 0
        if pd.isna(momentum):
            momentum = 0
        if pd.isna(volume_ratio) or volume_ratio <= 0:
            volume_ratio = 1.0
        if pd.isna(drop_percent):
            drop_percent = 0
        
        confidence = 0
        
        # RSI
        if rsi < 25:
            confidence += 30
        elif rsi < 30:
            confidence += 25
        elif rsi < 35:
            confidence += 20
        elif rsi < 40:
            confidence += 15
        elif rsi < 45:
            confidence += 10
        else:
            confidence += 5
        
        # Volume
        if pd.isna(volume_ratio) or volume_ratio <= 0:
            volume_points = 0
        else:
            volume_points = min(int((volume_ratio - 0.6) * 20), 25)
        confidence += volume_points
        
        # Trend
        if trend == 'bullish':
            confidence += 20
        elif trend == 'neutral':
            confidence += 10
        
        # MACD
        if macd_diff > 5:
            confidence += 15
        elif macd_diff > 0:
            confidence += 10
        else:
            confidence += 5
        
        # Momentum
        if momentum < -5:
            confidence += 15
        elif momentum < -3:
            confidence += 12
        elif momentum < -2:
            confidence += 8
        
        # Price Drop
        if drop_percent >= 3:
            confidence += 15
        elif drop_percent >= 2:
            confidence += 10
        elif drop_percent >= 1:
            confidence += 5
        
        return confidence

    def _analyze_candle(self, analysis):
        """تحليل آخر شمعة للكشف عن إشارات القناص (Rejection & Accumulation)"""
        candle_analysis = {'is_rejection': False, 'is_accumulation': False}
        try:
            df = analysis.get('df')
            if df is not None and not df.empty:
                last = df.iloc[-1]
                open_p = float(last['open'])
                close_p = float(last['close'])
                low_p = float(last['low'])
                volume_ratio = analysis.get('volume_ratio', 1.0)

                body = abs(close_p - open_p)
                lower_wick = min(open_p, close_p) - low_p

                # 1. Rejection (Hammer/Pinbar): الذيل السفلي أكبر من الجسم بـ 1.2 مرة
                if body > 0 and lower_wick > (body * 1.2):
                    candle_analysis['is_rejection'] = True

                # 2. Accumulation: فوليوم عالي (> 1.3) مع تحرك سعري بسيط (< 0.4%)
                change_pct = (body / open_p) * 100 if open_p > 0 else 0
                if volume_ratio > 1.3 and change_pct < 0.4:
                    candle_analysis['is_accumulation'] = True
        except Exception as e:
            # In case of any error in candle analysis, just return the default
            # print(f"⚠️ Candle analysis error: {e}") # Optional: for debugging
            pass
        return candle_analysis

    def _analyze_candle(self, analysis):
        """تحليل آخر شمعة للكشف عن إشارات القناص (Rejection & Accumulation)"""
        candle_analysis = {'is_rejection': False, 'is_accumulation': False}
        try:
            df = analysis.get('df')
            if df is not None and not df.empty:
                last = df.iloc[-1]
                open_p = float(last['open'])
                close_p = float(last['close'])
                low_p = float(last['low'])
                volume_ratio = analysis.get('volume_ratio', 1.0)

                body = abs(close_p - open_p)
                lower_wick = min(open_p, close_p) - low_p

                # 1. Rejection (Hammer/Pinbar): الذيل السفلي أكبر من الجسم بـ 1.2 مرة
                if body > 0 and lower_wick > (body * 1.2):
                    candle_analysis['is_rejection'] = True

                # 2. Accumulation: فوليوم عالي (> 1.3) مع تحرك سعري بسيط (< 0.4%)
                change_pct = (body / open_p) * 100 if open_p > 0 else 0
                if volume_ratio > 1.3 and change_pct < 0.4:
                    candle_analysis['is_accumulation'] = True
        except Exception as e:
            # In case of any error in candle analysis, just return the default
            # print(f"⚠️ Candle analysis error: {e}") # Optional: for debugging
            pass
        return candle_analysis
    
    def _is_trap_pattern(self, symbol, analysis):
        """فحص إذا كان النمط يشبه فخ سابق"""
        try:
            for trap in self.trap_memory:
                pattern = trap.get('pattern', {})
                if not pattern:
                    continue
                similarity = self._calculate_similarity(analysis, pattern)
                if similarity > 0.85:  # 85% مشابه
                    return True
        except Exception as e:
            print(f"⚠️ Trap check error: {e}")
        return False
    
    def _find_similar_patterns(self, analysis, pattern_type='SUCCESS'):
        """البحث عن أنماط مشابهة"""
        similar = []
        try:
            for pattern in self.learned_patterns:
                if pattern.get('type') == pattern_type:
                    conditions = pattern.get('conditions', {})
                    if not conditions:
                        continue
                    similarity = self._calculate_similarity(analysis, conditions)
                    if similarity > 0.7:  # 70% مشابه
                        similar.append({
                            'pattern': pattern,
                            'similarity': similarity
                        })
        except Exception as e:
            print(f"⚠️ Pattern search error: {e}")
        return similar
    
    def _calculate_similarity(self, current, stored):
        """حساب التشابه بين نمطين"""
        if not stored:
            return 0
        
        score = 0
        count = 0
        
        # مقارنة RSI
        if 'rsi' in stored and 'rsi' in current:
            # حماية من None
            current_rsi = current.get('rsi')
            stored_rsi = stored.get('rsi')
            
            if current_rsi is not None and stored_rsi is not None:
                diff = abs(current_rsi - stored_rsi)
                score += max(0, 1 - diff / 100)
                count += 1
        
        # مقارنة Volume
        if 'volume_ratio' in stored and 'volume_ratio' in current:
            current_vol = current.get('volume_ratio')
            stored_vol = stored.get('volume_ratio')
            
            if current_vol is not None and stored_vol is not None:
                diff = abs(current_vol - stored_vol)
                score += max(0, 1 - diff / 2)
                count += 1
        
        # مقارنة MACD
        if 'macd_diff' in stored and 'macd_diff' in current:
            current_macd = current.get('macd_diff')
            stored_macd = stored.get('macd_diff')
            
            if current_macd is not None and stored_macd is not None:
                diff = abs(current_macd - stored_macd)
                score += max(0, 1 - diff / 50)
                count += 1
        
        return score / count if count > 0 else 0
    
    def _optimize_confidence(self, base_confidence, similar_patterns):
        """تحسين Confidence بناءً على الأنماط المشابهة"""
        if not similar_patterns:
            return base_confidence
        
        # حساب متوسط نجاح الأنماط المشابهة
        total_success = sum(p['pattern'].get('success_rate', 0) for p in similar_patterns)
        avg_success = total_success / len(similar_patterns)
        
        # تعديل Confidence
        if avg_success > 0.85:  # نجاح عالي
            adjustment = 3
        elif avg_success > 0.75:
            adjustment = 2
        elif avg_success < 0.60:  # نجاح منخفض
            adjustment = -5
        else:
            adjustment = 0
        
        optimized = base_confidence + adjustment
        
        # التأكد من البقاء ضمن الحدود (60-75)
        optimized = max(60, optimized)
        optimized = min(75, optimized)
        
        return optimized
    
    def _calculate_smart_amount(self, symbol, confidence, analysis, win_rate=None, risk_manager=None):
        """حساب المبلغ الذكي بالتصويت من المستشارين + Risk Manager"""
        import pandas as pd
        from config import MIN_TRADE_AMOUNT, MAX_TRADE_AMOUNT
        
        rsi = analysis.get('rsi', 50)
        macd = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        
        # استشارة المستشارين للتصويت
        if self.dl_client:
            try:
                # Risk Manager vote (Kelly Criterion)
                risk_vote = None
                if risk_manager:
                    try:
                        risk_vote = risk_manager.calculate_optimal_amount(symbol, confidence, 12, 20)
                    except:
                        pass
                
                # Amount Voting (7 مستشارين + Risk Manager)
                amount_votes = self.dl_client.vote_amount(rsi, macd, volume_ratio, confidence, risk_vote)
                avg_amount = sum(amount_votes.values()) / len(amount_votes)
                
                # الملك يعدل (±$3)
                king_adjustment = min(max((confidence - 65) * 0.06, -3.0), 3.0)
                final_amount = max(12.0, min(23.0, avg_amount + king_adjustment))
                
                amount = round(final_amount, 2)
                
                print(f"💰 {symbol}: ${avg_amount:.2f}→${amount}")
                
            except Exception as e:
                print(f"⚠️ Amount voting error: {e}")
                # Fallback
                amount = MIN_TRADE_AMOUNT
        else:
            # Fallback if DL not available
            amount = MIN_TRADE_AMOUNT
        
        return amount
    
    def _estimate_success_probability(self, similar_patterns):
        """تقدير احتمال النجاح"""
        if not similar_patterns:
            return 0.5  # 50% افتراضي
        
        total_success = sum(p['pattern'].get('success_rate', 0.5) for p in similar_patterns)
        return total_success / len(similar_patterns)
    
    def learn_from_trade(self, trade_result):
        """
        التعلم من صفقة (يُستدعى بعد كل بيع)
        """
        from learning.pattern_detector import PatternDetector
        
        # حفظ الصفقة
        self.storage.save_trade(trade_result)
        
        # حفظ نتائج التصويت (إذا كانت موجودة)
        if 'voting_results' in trade_result:
            self._save_voting_results(trade_result)
        
        # استخراج النمط
        detector = PatternDetector()
        pattern = detector.extract_pattern(trade_result)
        
        if pattern:
            # حفظ النمط
            self.storage.save_pattern(pattern)
            
            # تحديث الذاكرة
            if pattern['type'] == 'SUCCESS':
                self.learned_patterns.append(pattern)
                print(f"✅ Learned success pattern: {pattern.get('summary', '')}")
            elif pattern['type'] == 'TRAP':
                self.trap_memory.append(pattern)
                self.storage.save_trap(pattern)
                print(f"🚫 Learned trap pattern: {pattern.get('summary', '')}")
        
        return pattern
    
    def _save_voting_results(self, trade_result):
        """حفظ نتائج تصويت المستشارين"""
        try:
            symbol = trade_result.get('symbol')
            profit_percent = trade_result.get('profit_percent', 0)
            voting_results = trade_result.get('voting_results', {})
            
            # حفظ نتيجة كل مستشار
            for consultant_name, vote_data in voting_results.items():
                vote_record = {
                    'symbol': symbol,
                    'consultant_name': consultant_name,
                    'vote_type': vote_data.get('vote_type'),
                    'vote_value': vote_data.get('vote_value'),
                    'actual_result': vote_data.get('actual_result'),
                    'is_correct': vote_data.get('is_correct'),
                    'profit_percent': profit_percent
                }
                self.storage.save_consultant_vote(vote_record)
        except Exception as e:
            print(f"⚠️ Error saving voting results: {e}")
    
    def save_buy_voting_results(self, symbol, buy_votes):
        """حفظ نتائج تصويت الشراء (يُستدعى عند الشراء)"""
        try:
            # حفظ تصويت كل مستشار على الشراء
            for consultant_name, vote in buy_votes.items():
                vote_record = {
                    'symbol': symbol,
                    'consultant_name': consultant_name,
                    'vote_type': 'buy',
                    'vote_value': float(vote),  # 1=BUY, 0=SKIP
                    'actual_result': 1.0,  # تم الشراء فعلاً
                    'is_correct': (vote == 1),  # صح لو صوت BUY
                    'profit_percent': 0.0  # ما نعرف الربح بعد
                }
                self.storage.save_consultant_vote(vote_record)
        except Exception as e:
            print(f"⚠️ Error saving buy voting results: {e}")

    
    def _calculate_smart_targets(self, symbol, confidence, analysis, similar_patterns, risk_manager=None):
        """دالة فارغة - تم إلغاء التوقعات"""
        return {
            'tp': 0,
            'sl': 0,
            'wait_hours': 72
        }
    
    def should_sell(self, symbol, position, current_price, analysis, mtf):
        """القرار الذكي: هل نبيع؟ (الملك يقرر مع استشارة المستشارين)"""
        buy_price = position['buy_price']
        highest_price = position.get('highest_price', buy_price)
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        
        # الأهداف الذكية من وقت الشراء (الحد الأدنى)
        tp_target = position.get('tp_target', 1.0)
        max_wait_hours = position.get('max_wait_hours', 48)
        
        # حساب المدة - حماية من None
        hours_held = 24  # default
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str and isinstance(buy_time_str, str):
                buy_time = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except Exception as e:
            hours_held = 24  # fallback
        
        # حساب أعلى ربح محقق والنزول منه (للمستشارين)
        highest_profit_percent = ((highest_price - buy_price) / buy_price) * 100
        drop_from_high_percent = ((highest_price - current_price) / buy_price) * 100

        # 0. Zombie Trade Check (3 Days Limit)
        # إذا مرت 72 ساعة (3 أيام) يتم تسليم العملة للخبل (Rescue Scalper)
        if hours_held >= 72:
            if self.rescue_scalper:
                print(f"🤪 {symbol}: Handing over to Crazy Rescue Scalper (> 72h)...")
                rescue_decision = self.rescue_scalper.get_exit_decision(symbol, analysis, profit_percent)
                
                if rescue_decision['action'] == 'SELL':
                    # حفظ محاولة الإنقاذ للتدريب
                    self.storage.save_rescue_event({
                        'symbol': symbol,
                        'hours_held': hours_held,
                        'final_profit': profit_percent,
                        'exit_reason': rescue_decision['reason'],
                        'market_conditions': {
                            'rsi': analysis.get('rsi'),
                            'volume': analysis.get('volume_ratio')
                        }
                    })
                    return {
                        'action': 'SELL',
                        'reason': rescue_decision['reason'],
                        'profit': profit_percent
                    }
                else:
                    return {
                        'action': 'HOLD',
                        'reason': rescue_decision['reason']
                    }
            else:
                # Fallback للمكنسة القديمة لو الخبل مو موجود
                return {
                    'action': 'SELL',
                    'reason': 'ZOMBIE TRADE (72h timeout)',
                    'profit': profit_percent
                }

        # 1. Trailing Stop Loss (من أعلى سعر - الحد الأقصى -2%)
        drop_from_high = ((highest_price - current_price) / highest_price) * 100
        
        if drop_from_high >= 2.0:
            # نزل 2% من أعلى سعر - بيع
            print(f"🛑 {symbol}: Trailing Stop triggered (dropped {drop_from_high:.2f}% from peak)")
            return {
                'action': 'SELL',
                'reason': 'TRAILING STOP -2%',
                'profit': profit_percent
            }
        
        # 2. فحص الخسارة: تم إلغاء البيع اليدوي بخسارة
        # نعتمد فقط على Trailing Stop في الأعلى (-2% من القمة)
        
        # 3. استشارة المستشارين للبيع (تصويت - النظام الوحيد للبيع)
        # المستشارين يراقبون العملة + السوق العام ويصوتون
        if self.dl_client:
            try:
                rsi = analysis.get('rsi', 50) if analysis else 50
                macd_diff = analysis.get('macd_diff', 0) if analysis else 0
                volume_ratio = analysis.get('volume_ratio', 1.0) if analysis else 1.0
                trend = mtf.get('trend', 'neutral') if mtf else 'neutral'
                
                # حساب تغير BTC, ETH, BNB في آخر ساعة
                market_sentiment = None
                try:
                    btc_change_1h = analysis.get('btc_change_1h', 0) if analysis else 0
                    eth_change_1h = analysis.get('eth_change_1h', 0) if analysis else 0
                    bnb_change_1h = analysis.get('bnb_change_1h', 0) if analysis else 0
                    market_sentiment = {
                        'btc_change_1h': btc_change_1h,
                        'eth_change_1h': eth_change_1h,
                        'bnb_change_1h': bnb_change_1h
                    }
                except:
                    pass
                
                # المستشارين يصوتون: SELL (1) أو HOLD (0)
                # بالربح: يراقبون العملة + السوق - لو السوق بينقلب → بيع (كفاية طمع)
                # بالخسارة: يراقبون العملة + السوق - لو السوق نازل → بيع (قبل تنزل أكثر)
                sell_votes = self.dl_client.vote_sell_now(
                    symbol, profit_percent, rsi, macd_diff, volume_ratio, trend, hours_held,
                    market_sentiment, highest_profit_percent, drop_from_high_percent
                )
                
                # حساب نسبة التصويت
                total_votes = len(sell_votes)
                sell_count = sum(sell_votes.values())
                sell_percentage = (sell_count / total_votes) * 100
                
                # الملك يقرر بناءً على التصويت
                # 3/7 أو أكثر → بيع فوراً (سواء ربح أو خسارة)
                if sell_count >= 3:
                    reason_type = "profit" if profit_percent > 0 else "loss"
                    market_info = ""
                    if market_sentiment:
                        btc = market_sentiment['btc_change_1h']
                        eth = market_sentiment['eth_change_1h']
                        bnb = market_sentiment['bnb_change_1h']
                        market_info = f" | Market: BTC {btc:+.1f}% ETH {eth:+.1f}% BNB {bnb:+.1f}%"
                    print(f"🗳️ {symbol}: {sell_count}/{total_votes} voted SELL ({sell_percentage:.0f}%) - {reason_type}{market_info}")
                    return {
                        'action': 'SELL',
                        'reason': f'Consultants voted SELL ({sell_percentage:.0f}%)',
                        'profit': profit_percent
                    }
                    
            except Exception as e:
                print(f"⚠️ Sell voting error: {e}")
        
        # 4. TP الذكي - تم إلغاؤه
        # البيع يتم فقط عبر تصويت المستشارين (3/7)
        # TP المحفوظ للمعلومات فقط
        
        # 5. Bearish Exit - تم إلغاؤه
        # البيع يتم فقط عبر تصويت المستشارين
        
        # 6. Timeout - تم إلغاؤه
        # البيع يتم فقط عبر تصويت المستشارين أو Trailing Stop
        
        # 7. Hold
        return {'action': 'HOLD', 'reason': 'Waiting for target'}
