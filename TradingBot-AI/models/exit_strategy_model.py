"""
🎯 Exit Strategy Model
يحسن توقيت البيع ويزيد الأرباح
"""

from datetime import datetime, timedelta
import statistics

class ExitStrategyModel:
    def __init__(self, storage):
        self.storage = storage
        self.exit_patterns = {}
        print("🎯 Exit Strategy Model initialized")
    
    def should_exit(self, symbol, position, current_price, analysis, mtf):
        """قرار البيع الذكي"""
        try:
            buy_price = position['buy_price']
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            
            # جلب تاريخ العملة
            coin_history = self._get_coin_exit_history(symbol)
            
            # 1. فحص TP الذكي
            tp_decision = self._check_smart_tp(
                symbol, profit_percent, position, 
                analysis, mtf, coin_history
            )
            if tp_decision['action'] == 'SELL':
                return tp_decision
            
            # 2. فحص Trailing Stop الذكي
            trailing_decision = self._check_smart_trailing(
                symbol, current_price, position, 
                analysis, coin_history
            )
            if trailing_decision['action'] == 'SELL':
                return trailing_decision
            
            # 3. فحص Bearish Exit الذكي
            bearish_decision = self._check_smart_bearish(
                symbol, profit_percent, mtf, 
                analysis, coin_history
            )
            if bearish_decision['action'] == 'SELL':
                return bearish_decision
            
            # 4. فحص Time-based Exit
            time_decision = self._check_time_exit(
                symbol, position, profit_percent, coin_history
            )
            if time_decision['action'] == 'SELL':
                return time_decision
            
            # 5. Hold
            return {
                'action': 'HOLD',
                'reason': 'Waiting for better exit',
                'confidence': self._calculate_hold_confidence(
                    profit_percent, analysis, mtf
                )
            }
            
        except Exception as e:
            print(f"⚠️ Exit strategy error {symbol}: {e}")
            return {'action': 'HOLD', 'reason': 'Error in analysis'}
    
    def _check_smart_tp(self, symbol, profit_percent, position, analysis, mtf, history):
        """فحص TP الذكي"""
        try:
            # TP الافتراضي
            tp_target = position.get('tp_target', 1.0)
            
            # تعديل TP حسب تاريخ العملة
            if history and history['avg_profit'] > 0:
                # لو العملة عادة تربح أكثر، نرفع TP
                if history['avg_profit'] > 2.0:
                    tp_target = max(tp_target, 1.5)
                elif history['avg_profit'] > 1.5:
                    tp_target = max(tp_target, 1.2)
            
            # فحص الوصول للهدف
            if profit_percent >= tp_target:
                # فحص إذا السوق لسه قوي
                rsi = analysis.get('rsi', 50)
                macd_diff = analysis.get('macd_diff', 0)
                trend = mtf.get('trend', 'neutral')
                
                # لو السوق قوي جداً، ننتظر شوي
                if rsi < 65 and macd_diff > 5 and trend == 'bullish' and profit_percent < tp_target + 0.5:
                    return {
                        'action': 'HOLD',
                        'reason': f'TP reached but market still strong'
                    }
                
                return {
                    'action': 'SELL',
                    'reason': f'SMART TP {tp_target}%',
                    'profit': profit_percent,
                    'confidence': 95
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _check_smart_trailing(self, symbol, current_price, position, analysis, history):
        """فحص Trailing Stop الذكي"""
        try:
            buy_price = position['buy_price']
            highest_price = position.get('highest_price', buy_price)
            
            # حساب الربح من أعلى سعر
            drop_from_high = ((highest_price - current_price) / highest_price) * 100
            
            # Trailing Stop الافتراضي
            trailing_percent = position.get('sl_target', 2.0)
            
            # تعديل Trailing حسب الربح الحالي
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            
            if profit_percent > 2:
                # لو الربح عالي، نشدد الـ Trailing
                trailing_percent = 1.5
            elif profit_percent > 1:
                trailing_percent = 1.8
            
            # فحص الانخفاض
            if drop_from_high >= trailing_percent:
                # فحص إذا فيه ارتداد قوي
                rsi = analysis.get('rsi', 50)
                macd_diff = analysis.get('macd_diff', 0)
                
                # لو فيه إشارات ارتداد قوية
                if rsi < 35 and macd_diff > 0 and profit_percent > 0:
                    return {
                        'action': 'HOLD',
                        'reason': 'Trailing triggered but bounce signals detected'
                    }
                
                return {
                    'action': 'SELL',
                    'reason': f'SMART TRAILING {trailing_percent}%',
                    'profit': profit_percent,
                    'confidence': 90
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _check_smart_bearish(self, symbol, profit_percent, mtf, analysis, history):
        """فحص Bearish Exit الذكي"""
        try:
            trend = mtf.get('trend', 'neutral')
            
            # Bearish قوي
            if trend in ['bearish', 'strong_bearish']:
                # لو الربح إيجابي، نبيع
                if profit_percent > 0.1:
                    return {
                        'action': 'SELL',
                        'reason': 'BEARISH TREND',
                        'profit': profit_percent,
                        'confidence': 85
                    }
                
                # لو الخسارة صغيرة والسوق bearish جداً
                if profit_percent > -1 and trend == 'strong_bearish':
                    return {
                        'action': 'SELL',
                        'reason': 'STRONG BEARISH',
                        'profit': profit_percent,
                        'confidence': 80
                    }
            
            # فحص RSI + MACD معاً
            rsi = analysis.get('rsi', 50)
            macd_diff = analysis.get('macd_diff', 0)
            
            # إشارات bearish قوية
            if rsi > 70 and macd_diff < -5 and profit_percent > 0:
                return {
                    'action': 'SELL',
                    'reason': 'OVERBOUGHT + BEARISH MACD',
                    'profit': profit_percent,
                    'confidence': 85
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _check_time_exit(self, symbol, position, profit_percent, history):
        """فحص Time-based Exit"""
        try:
            buy_time = datetime.fromisoformat(position['buy_time'])
            hours_held = (datetime.now() - buy_time).total_seconds() / 3600
            
            max_wait = position.get('max_wait_hours', 48)
            
            # لو انتهى الوقت والربح سلبي
            if hours_held >= max_wait and profit_percent < 0:
                return {
                    'action': 'SELL',
                    'reason': f'TIMEOUT {int(hours_held)}h',
                    'profit': profit_percent,
                    'confidence': 70
                }
            
            # لو مضى وقت طويل جداً (72 ساعة) حتى لو ربح صغير
            if hours_held >= 72 and profit_percent < 0.5:
                return {
                    'action': 'SELL',
                    'reason': f'LONG HOLD {int(hours_held)}h',
                    'profit': profit_percent,
                    'confidence': 75
                }
            
            return {'action': 'HOLD'}
            
        except:
            return {'action': 'HOLD'}
    
    def _calculate_hold_confidence(self, profit_percent, analysis, mtf):
        """حساب ثقة الـ Hold"""
        confidence = 50
        
        # الربح الحالي
        if profit_percent > 0.5:
            confidence += 20
        elif profit_percent > 0:
            confidence += 10
        elif profit_percent < -1:
            confidence -= 20
        
        # RSI
        rsi = analysis.get('rsi', 50)
        if 40 < rsi < 60:
            confidence += 10
        elif rsi < 30:
            confidence += 15
        
        # Trend
        trend = mtf.get('trend', 'neutral')
        if trend in ['bullish', 'strong_bullish']:
            confidence += 15
        elif trend in ['bearish', 'strong_bearish']:
            confidence -= 15
        
        return max(0, min(100, confidence))
    
    def _get_coin_exit_history(self, symbol):
        """جلب تاريخ البيع للعملة"""
        try:
            all_trades = self.storage.get_all_trades()
            coin_trades = [t for t in all_trades if t.get('symbol') == symbol]
            
            if len(coin_trades) < 3:
                return None
            
            profits = [t.get('profit_percent', 0) for t in coin_trades]
            avg_profit = statistics.mean(profits)
            
            durations = [t.get('hours_held', 24) for t in coin_trades]
            avg_duration = statistics.mean(durations)
            
            return {
                'avg_profit': avg_profit,
                'avg_duration': avg_duration,
                'trades_count': len(coin_trades)
            }
            
        except:
            return None
    
    def learn_from_exit(self, symbol, exit_data):
        """التعلم من البيع"""
        try:
            if symbol not in self.exit_patterns:
                self.exit_patterns[symbol] = []
            
            self.exit_patterns[symbol].append({
                'profit': exit_data.get('profit_percent', 0),
                'reason': exit_data.get('sell_reason', ''),
                'duration': exit_data.get('hours_held', 0),
                'timestamp': datetime.now().isoformat()
            })
            
            # الاحتفاظ بآخر 20 بيع فقط
            if len(self.exit_patterns[symbol]) > 20:
                self.exit_patterns[symbol] = self.exit_patterns[symbol][-20:]
            
        except Exception as e:
            print(f"⚠️ Exit learning error: {e}")
    
    def get_optimal_exit_point(self, symbol, current_profit):
        """الحصول على نقطة البيع المثالية"""
        try:
            history = self._get_coin_exit_history(symbol)
            
            if not history:
                return {
                    'optimal_tp': 1.0,
                    'optimal_sl': 2.0,
                    'confidence': 50
                }
            
            avg_profit = history['avg_profit']
            
            # حساب TP المثالي
            if avg_profit > 2:
                optimal_tp = 1.8
            elif avg_profit > 1.5:
                optimal_tp = 1.3
            elif avg_profit > 1:
                optimal_tp = 1.0
            else:
                optimal_tp = 0.8
            
            # حساب SL المثالي
            if avg_profit > 1:
                optimal_sl = 2.5  # نعطي مساحة أكبر
            else:
                optimal_sl = 1.5  # نشدد الحماية
            
            return {
                'optimal_tp': optimal_tp,
                'optimal_sl': optimal_sl,
                'confidence': min(history['trades_count'] * 10, 90)
            }
            
        except:
            return {
                'optimal_tp': 1.0,
                'optimal_sl': 2.0,
                'confidence': 50
            }
