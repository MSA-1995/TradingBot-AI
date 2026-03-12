"""
🧠 Enhanced Pattern Recognition Model
يتعلم من الأنماط بشكل أعمق ويتوقع النجاح
"""

from datetime import datetime, timedelta
import statistics

class EnhancedPatternRecognition:
    def __init__(self, storage):
        self.storage = storage
        self.patterns = {
            'SUCCESS': [],
            'NEUTRAL': [],
            'TRAP': []
        }
        self.pattern_weights = {}
        self.load_patterns()
        print("🧠 Enhanced Pattern Recognition initialized")
    
    def load_patterns(self):
        """تحميل الأنماط المحفوظة"""
        try:
            stored_patterns = self.storage.load_patterns()
            
            for pattern in stored_patterns:
                pattern_type = pattern.get('pattern_type') or pattern.get('type', 'NEUTRAL')
                if pattern_type in self.patterns:
                    self.patterns[pattern_type].append(pattern)
            
            print(f"📚 Loaded {len(stored_patterns)} patterns")
            
        except Exception as e:
            print(f"⚠️ Pattern loading error: {e}")
    
    def analyze_entry_pattern(self, symbol, analysis, mtf, price_drop):
        """تحليل نمط الدخول"""
        try:
            # استخراج الخصائص
            features = self._extract_features(analysis, mtf, price_drop)
            
            # البحث عن أنماط مشابهة
            similar_success = self._find_similar_patterns(features, 'SUCCESS')
            similar_traps = self._find_similar_patterns(features, 'TRAP')
            
            # حساب احتمال النجاح
            success_probability = self._calculate_success_probability(
                similar_success, similar_traps
            )
            
            # تحديد قوة النمط
            pattern_strength = self._calculate_pattern_strength(
                features, similar_success, similar_traps
            )
            
            # التوصية
            recommendation = self._get_pattern_recommendation(
                success_probability, pattern_strength
            )
            
            return {
                'success_probability': round(success_probability, 2),
                'pattern_strength': pattern_strength,
                'recommendation': recommendation,
                'similar_success_count': len(similar_success),
                'similar_trap_count': len(similar_traps),
                'confidence_adjustment': self._calculate_confidence_adjustment(
                    success_probability, pattern_strength
                ),
                'features': features
            }
            
        except Exception as e:
            print(f"⚠️ Pattern analysis error: {e}")
            return None
    
    def _extract_features(self, analysis, mtf, price_drop):
        """استخراج الخصائص من البيانات"""
        import pandas as pd
        
        features = {}
        
        # RSI features
        rsi = analysis.get('rsi', 50)
        if not pd.isna(rsi):
            features['rsi'] = rsi
            features['rsi_zone'] = self._get_rsi_zone(rsi)
        
        # MACD features
        macd_diff = analysis.get('macd_diff', 0)
        if not pd.isna(macd_diff):
            features['macd_diff'] = macd_diff
            features['macd_signal'] = 'bullish' if macd_diff > 0 else 'bearish'
        
        # Volume features
        volume_ratio = analysis.get('volume_ratio', 1.0)
        if not pd.isna(volume_ratio):
            features['volume_ratio'] = volume_ratio
            features['volume_level'] = self._get_volume_level(volume_ratio)
        
        # Momentum features
        momentum = analysis.get('price_momentum', 0)
        if not pd.isna(momentum):
            features['momentum'] = momentum
            features['momentum_direction'] = 'up' if momentum > 0 else 'down'
        
        # Trend features
        features['trend'] = mtf.get('trend', 'neutral')
        features['trend_strength'] = mtf.get('total', 0)
        
        # Price drop features
        features['price_drop'] = price_drop.get('drop_percent', 0)
        features['drop_confirmed'] = price_drop.get('confirmed', False)
        
        return features
    
    def _get_rsi_zone(self, rsi):
        """تحديد منطقة RSI"""
        if rsi < 25:
            return 'extreme_oversold'
        elif rsi < 30:
            return 'oversold'
        elif rsi < 40:
            return 'low'
        elif rsi < 60:
            return 'neutral'
        elif rsi < 70:
            return 'high'
        elif rsi < 75:
            return 'overbought'
        else:
            return 'extreme_overbought'
    
    def _get_volume_level(self, volume_ratio):
        """تحديد مستوى Volume"""
        if volume_ratio < 0.5:
            return 'very_low'
        elif volume_ratio < 0.8:
            return 'low'
        elif volume_ratio < 1.2:
            return 'normal'
        elif volume_ratio < 2.0:
            return 'high'
        elif volume_ratio < 3.0:
            return 'very_high'
        else:
            return 'extreme'
    
    def _find_similar_patterns(self, features, pattern_type):
        """البحث عن أنماط مشابهة"""
        similar = []
        
        for pattern in self.patterns.get(pattern_type, []):
            pattern_features = pattern.get('conditions') or pattern.get('data', {}).get('features', {})
            
            if not pattern_features:
                continue
            
            similarity = self._calculate_similarity(features, pattern_features)
            
            if similarity > 0.65:  # 65% مشابه
                similar.append({
                    'pattern': pattern,
                    'similarity': similarity
                })
        
        # ترتيب حسب التشابه
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar[:10]  # أفضل 10 أنماط
    
    def _calculate_similarity(self, features1, features2):
        """حساب التشابه بين نمطين"""
        import pandas as pd
        
        score = 0
        count = 0
        
        # RSI zone
        if 'rsi_zone' in features1 and 'rsi_zone' in features2:
            if features1['rsi_zone'] == features2['rsi_zone']:
                score += 1
            count += 1
        
        # MACD signal
        if 'macd_signal' in features1 and 'macd_signal' in features2:
            if features1['macd_signal'] == features2['macd_signal']:
                score += 1
            count += 1
        
        # Volume level
        if 'volume_level' in features1 and 'volume_level' in features2:
            if features1['volume_level'] == features2['volume_level']:
                score += 1
            count += 1
        
        # Trend
        if 'trend' in features1 and 'trend' in features2:
            if features1['trend'] == features2['trend']:
                score += 1
            count += 1
        
        # Momentum direction
        if 'momentum_direction' in features1 and 'momentum_direction' in features2:
            if features1['momentum_direction'] == features2['momentum_direction']:
                score += 1
            count += 1
        
        # RSI numerical
        if 'rsi' in features1 and 'rsi' in features2:
            rsi1 = features1['rsi']
            rsi2 = features2['rsi']
            if not pd.isna(rsi1) and not pd.isna(rsi2):
                diff = abs(rsi1 - rsi2)
                score += max(0, 1 - diff / 100)
                count += 1
        
        # Volume ratio
        if 'volume_ratio' in features1 and 'volume_ratio' in features2:
            vol1 = features1['volume_ratio']
            vol2 = features2['volume_ratio']
            if not pd.isna(vol1) and not pd.isna(vol2):
                diff = abs(vol1 - vol2)
                score += max(0, 1 - diff / 3)
                count += 1
        
        return score / count if count > 0 else 0
    
    def _calculate_success_probability(self, similar_success, similar_traps):
        """حساب احتمال النجاح"""
        if not similar_success and not similar_traps:
            return 0.5  # 50% افتراضي
        
        success_weight = sum(s['similarity'] for s in similar_success)
        trap_weight = sum(t['similarity'] for t in similar_traps)
        
        total_weight = success_weight + trap_weight
        
        if total_weight == 0:
            return 0.5
        
        probability = success_weight / total_weight
        
        return probability
    
    def _calculate_pattern_strength(self, features, similar_success, similar_traps):
        """حساب قوة النمط"""
        strength = 'WEAK'
        
        total_similar = len(similar_success) + len(similar_traps)
        
        if total_similar >= 10:
            strength = 'STRONG'
        elif total_similar >= 5:
            strength = 'MEDIUM'
        
        # تعديل حسب التشابه
        if similar_success:
            avg_similarity = statistics.mean([s['similarity'] for s in similar_success])
            if avg_similarity > 0.85:
                if strength == 'MEDIUM':
                    strength = 'STRONG'
                elif strength == 'WEAK':
                    strength = 'MEDIUM'
        
        return strength
    
    def _get_pattern_recommendation(self, success_probability, pattern_strength):
        """الحصول على التوصية"""
        if success_probability >= 0.75 and pattern_strength == 'STRONG':
            return 'STRONG_BUY'
        elif success_probability >= 0.65 and pattern_strength in ['STRONG', 'MEDIUM']:
            return 'BUY'
        elif success_probability >= 0.50:  # Changed from 0.55
            return 'CONSIDER'
        elif success_probability >= 0.40:  # Changed from 0.45
            return 'NEUTRAL'
        elif success_probability >= 0.30:  # Changed from 0.35 - more aggressive
            return 'CAUTION'
        else:
            return 'AVOID'
    
    def _calculate_confidence_adjustment(self, success_probability, pattern_strength):
        """حساب تعديل الثقة"""
        adjustment = 0
        
        # حسب الاحتمال
        if success_probability >= 0.80:
            adjustment += 10
        elif success_probability >= 0.70:
            adjustment += 7
        elif success_probability >= 0.60:
            adjustment += 5
        elif success_probability >= 0.50:
            adjustment += 2
        elif success_probability < 0.40:
            adjustment -= 5
        elif success_probability < 0.30:
            adjustment -= 10
        
        # حسب القوة
        if pattern_strength == 'STRONG':
            adjustment += 3
        elif pattern_strength == 'MEDIUM':
            adjustment += 1
        
        return adjustment
    
    def learn_pattern(self, trade_data):
        """التعلم من صفقة"""
        try:
            profit = trade_data.get('profit_percent', 0)
            
            # تصنيف النمط
            if profit >= 0.5:
                pattern_type = 'SUCCESS'
            elif profit <= -1.5:
                pattern_type = 'TRAP'
            else:
                pattern_type = 'NEUTRAL'
            
            # استخراج الخصائص
            features = trade_data.get('features', {})
            
            if not features:
                # محاولة استخراج من البيانات الموجودة
                features = {
                    'rsi': trade_data.get('rsi'),
                    'volume': trade_data.get('volume'),
                    'macd_diff': trade_data.get('macd_diff')
                }
            
            pattern = {
                'type': pattern_type,
                'pattern_type': pattern_type,
                'features': features,
                'profit': profit,
                'symbol': trade_data.get('symbol'),
                'timestamp': datetime.now().isoformat(),
                'success_rate': 1.0 if pattern_type == 'SUCCESS' else 0.0
            }
            
            # حفظ النمط
            self.patterns[pattern_type].append(pattern)
            
            # حفظ في قاعدة البيانات
            self.storage.save_pattern(pattern)
            
            # تحديث الأوزان
            self._update_pattern_weights(pattern_type)
            
            print(f"✅ Learned {pattern_type} pattern for {trade_data.get('symbol')}")
            
        except Exception as e:
            print(f"⚠️ Pattern learning error: {e}")
    
    def _update_pattern_weights(self, pattern_type):
        """تحديث أوزان الأنماط"""
        try:
            total_patterns = sum(len(patterns) for patterns in self.patterns.values())
            
            if total_patterns == 0:
                return
            
            for ptype, patterns in self.patterns.items():
                self.pattern_weights[ptype] = len(patterns) / total_patterns
            
        except:
            pass
    
    def get_pattern_statistics(self):
        """إحصائيات الأنماط"""
        try:
            total = sum(len(patterns) for patterns in self.patterns.values())
            
            if total == 0:
                return None
            
            return {
                'total_patterns': total,
                'success_patterns': len(self.patterns['SUCCESS']),
                'neutral_patterns': len(self.patterns['NEUTRAL']),
                'trap_patterns': len(self.patterns['TRAP']),
                'success_rate': (len(self.patterns['SUCCESS']) / total) * 100 if total > 0 else 0,
                'pattern_weights': self.pattern_weights,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ Pattern stats error: {e}")
            return None
    
    def get_coin_pattern_history(self, symbol):
        """تاريخ أنماط العملة"""
        try:
            coin_patterns = {
                'SUCCESS': [],
                'NEUTRAL': [],
                'TRAP': []
            }
            
            for pattern_type, patterns in self.patterns.items():
                for pattern in patterns:
                    if pattern.get('symbol') == symbol:
                        coin_patterns[pattern_type].append(pattern)
            
            total = sum(len(p) for p in coin_patterns.values())
            
            if total == 0:
                return None
            
            success_rate = (len(coin_patterns['SUCCESS']) / total) * 100
            
            return {
                'symbol': symbol,
                'total_patterns': total,
                'success_patterns': len(coin_patterns['SUCCESS']),
                'trap_patterns': len(coin_patterns['TRAP']),
                'success_rate': round(success_rate, 2),
                'recommendation': 'BUY' if success_rate >= 65 else 'AVOID' if success_rate < 40 else 'NEUTRAL'
            }
            
        except:
            return None
