"""
AI Brain - العقل المفكر
يقرر، يتعلم، يتحسن (ضمن الحدود الآمنة)
"""
from datetime import datetime
import sys
import os

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
        
        # تحميل المعرفة السابقة
        self.load_knowledge()
        
        # MTF Analyzer (optional)
        try:
            import sys
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from models.multi_timeframe_analyzer import MultiTimeframeAnalyzer
            self.mtf_analyzer = None  # Will be set externally
        except:
            self.mtf_analyzer = None
        
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
    
    def should_buy(self, symbol, analysis, mtf, price_drop, models_scores=None, risk_manager=None):
        """
        القرار الذكي: هل نشتري؟
        models_scores: dict with scores from all models (optional)
        """
        from learning.safety_validator import SafetyValidator
        from learning.pattern_detector import PatternDetector
        
        # 1. التحليل الأساسي
        base_confidence = self._calculate_base_confidence(analysis, mtf, price_drop)
        
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
            # حساب المبلغ الذكي
            amount = self._calculate_smart_amount(symbol, optimized_confidence, analysis, risk_manager=risk_manager)
            
            # حساب TP و SL الذكي
            smart_targets = self._calculate_smart_targets(symbol, optimized_confidence, analysis, similar_success, risk_manager=risk_manager)
            
            decision = {
                'action': 'BUY',
                'confidence': optimized_confidence,
                'amount': amount,
                'tp_target': smart_targets['tp'],
                'sl_target': smart_targets['sl'],
                'max_wait_hours': smart_targets['wait_hours'],
                'reason': f'AI optimized from {base_confidence} to {optimized_confidence}',
                'success_probability': self._estimate_success_probability(similar_success),
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
                    'predicted_tp': smart_targets['tp'],
                    'predicted_sl': smart_targets['sl'],
                    'predicted_amount': amount
                }
            }
            
            self.storage.save_ai_decision({
                'symbol': symbol,
                'decision': 'BUY',
                'confidence': optimized_confidence,
                'amount': amount,
                'tp_target': smart_targets['tp'],
                'sl_target': smart_targets['sl'],
                'max_wait_hours': smart_targets['wait_hours'],
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

    
    def _calculate_smart_targets(self, symbol, confidence, analysis, similar_patterns, risk_manager=None):
        """حساب TP و SL والانتظار بالتصويت من المستشارين + Risk Manager"""
        import pandas as pd
        
        rsi = analysis.get('rsi', 50)
        macd = analysis.get('macd_diff', 0)
        volume_ratio = analysis.get('volume_ratio', 1.0)
        price_momentum = analysis.get('price_momentum', 0)
        
        # استشارة المستشارين للتصويت
        if self.dl_client:
            try:
                # TP Voting
                tp_votes = self.dl_client.vote_tp_target(rsi, macd, volume_ratio, price_momentum, confidence)
                avg_tp = sum(tp_votes.values()) / len(tp_votes)
                
                # الملك يعدل (±1%)
                king_adjustment_tp = min(max((confidence - 65) * 0.02, -1.0), 1.0)
                final_tp = max(0.5, min(11.0, avg_tp + king_adjustment_tp))
                
                # Risk Manager vote for SL
                risk_sl_vote = None
                if risk_manager:
                    try:
                        # Risk Manager يصوت بناءً على المخاطر
                        sharpe = risk_manager.calculate_sharpe_ratio(symbol, days=7)
                        if sharpe > 1.0:
                            risk_sl_vote = -1.8  # patient
                        elif sharpe > 0.5:
                            risk_sl_vote = -1.2
                        else:
                            risk_sl_vote = -0.8  # strict
                    except:
                        pass
                
                # SL Voting (7 مستشارين + Risk Manager)
                sl_votes = self.dl_client.vote_stop_loss(rsi, macd, volume_ratio, confidence, risk_sl_vote)
                avg_sl = sum(sl_votes.values()) / len(sl_votes)
                
                # الملك يعدل (±0.3%)
                king_adjustment_sl = min(max((confidence - 65) * 0.006, -0.3), 0.3)
                final_sl = max(-2.3, min(-0.1, avg_sl + king_adjustment_sl))
                
                tp = round(final_tp, 1)
                sl = round(abs(final_sl), 1)
                
                print(f"📊 {symbol}: TP={avg_tp:.1f}%→{tp}% | SL={avg_sl:.1f}%→{-sl}%")
                
            except Exception as e:
                print(f"⚠️ Voting error: {e}")
                # Fallback
                tp = 2.0
                sl = 1.5
        else:
            # Fallback if DL not available
            tp = 2.0
            sl = 1.5
        
        # Wait hours (based on TP)
        if tp >= 5:
            wait_hours = 72
        elif tp >= 3:
            wait_hours = 60
        else:
            wait_hours = 48
        
        return {
            'tp': tp,
            'sl': sl,
            'wait_hours': int(wait_hours)
        }
    
    def should_sell(self, symbol, position, current_price, analysis, mtf, exit_strategy=None):
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
        
        # 1. Trailing Stop Loss (من أعلى سعر - الحد الأقصى -2%)
        drop_from_high = ((highest_price - current_price) / highest_price) * 100
        
        if drop_from_high >= 2.0:
            # نزل 2% من أعلى سعر - بيع
            return {
                'action': 'SELL',
                'reason': 'TRAILING STOP -2%',
                'profit': profit_percent
            }
        
        # 2. فحص الخسارة مع تحليل السوق (AI حر يقرر)
        if profit_percent < 0:
            rsi = analysis.get('rsi', 50) if analysis else 50
            macd_diff = analysis.get('macd_diff', 0) if analysis else 0
            trend = mtf.get('trend', 'neutral') if mtf else 'neutral'
            
            # السوق نازل قوي جداً - بيع مبكر (حماية)
            market_falling_hard = (
                trend in ['bearish', 'strong_bearish'] and
                macd_diff < -10 and  # أقوى من -5
                rsi > 65 and  # overbought في نزول
                profit_percent <= -1.0  # خسارة -1% على الأقل
            )
            
            if market_falling_hard:
                return {
                    'action': 'SELL',
                    'reason': f'EARLY STOP (Market crash)',
                    'profit': profit_percent
                }
            
            # السوق عادي - AI يقرر بحرية (يكمل للشروط التالية)
        
        # 3. استشارة المستشارين للبيع (تصويت)
        if self.dl_client:
            try:
                rsi = analysis.get('rsi', 50) if analysis else 50
                macd_diff = analysis.get('macd_diff', 0) if analysis else 0
                volume_ratio = analysis.get('volume_ratio', 1.0) if analysis else 1.0
                trend = mtf.get('trend', 'neutral') if mtf else 'neutral'
                
                # المستشارين يصوتون: SELL (1) أو HOLD (0)
                sell_votes = self.dl_client.vote_sell_now(
                    symbol, profit_percent, rsi, macd_diff, volume_ratio, trend, hours_held
                )
                
                # حساب نسبة التصويت
                total_votes = len(sell_votes)
                sell_count = sum(sell_votes.values())
                sell_percentage = (sell_count / total_votes) * 100
                
                # الملك يقرر بناءً على التصويت
                # لو 50% أو أكثر صوتوا بيع → الملك يبيع
                if sell_percentage >= 50:
                    print(f"🗳️ {symbol}: {sell_count}/{total_votes} voted SELL ({sell_percentage:.0f}%)")
                    return {
                        'action': 'SELL',
                        'reason': f'Consultants voted SELL ({sell_percentage:.0f}%)',
                        'profit': profit_percent
                    }
                else:
                    # الأغلبية قالوا HOLD - نكمل للشروط التالية
                    pass
                    
            except Exception as e:
                print(f"⚠️ Sell voting error: {e}")
        
        # 4. TP الذكي - الحد الأدنى للبيع بالربح
        if profit_percent >= tp_target:
            # استشارة Smart TP (Exit Strategy) للتحسين
            if exit_strategy:
                try:
                    smart_tp_decision = exit_strategy._check_smart_tp(
                        symbol, profit_percent, position, analysis, mtf,
                        exit_strategy._get_coin_exit_history(symbol)
                    )
                    
                    # لو Smart TP قال بيع أو hold، نسمع له
                    if smart_tp_decision.get('action') in ['SELL', 'HOLD']:
                        return smart_tp_decision
                except:
                    pass  # لو فيه خطأ، نكمل بالمنطق العادي
            
            # المنطق العادي (بدون Smart TP)
            rsi = analysis.get('rsi', 50) if analysis else 50
            macd_diff = analysis.get('macd_diff', 0) if analysis else 0
            trend = mtf.get('trend', 'neutral') if mtf else 'neutral'
            
            market_rising = (
                trend == 'bullish' and
                macd_diff > 0 and
                rsi < 70  # مو overbought
            )
            
            if market_rising:
                return {'action': 'HOLD', 'reason': f'TP {tp_target}% reached but market rising'}
            
            # السوق ميت أو نازل - بيع
            return {
                'action': 'SELL',
                'reason': f'AI TP {tp_target}%',
                'profit': profit_percent
            }
        
        # 5. Bearish Exit
        if mtf.get('trend') == 'bearish' and mtf.get('total', 0) >= 2:
            # لو فيه ربح موجب - بيع
            if profit_percent > 0.1:
                return {
                    'action': 'SELL',
                    'reason': 'BEARISH TREND',
                    'profit': profit_percent
                }
        
        # 6. انتهى وقت الانتظار
        if hours_held >= max_wait_hours and profit_percent < 0:
            return {
                'action': 'SELL',
                'reason': f'TIMEOUT {max_wait_hours}h',
                'profit': profit_percent
            }
        
        # 7. Hold
        return {'action': 'HOLD', 'reason': 'Waiting for target'}
