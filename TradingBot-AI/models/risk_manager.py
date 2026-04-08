"""
🛡️ Risk Manager
إدارة مخاطر متقدمة مع Kelly Criterion و Sharpe Ratio
"""

import pandas as pd
from datetime import datetime, timedelta
import requests
from src.external_apis import get_external_atr

class RiskManager:
    def __init__(self, storage):
        self.storage = storage
        self.max_drawdown_percent = 10  # أقصى خسارة مسموحة
        self.max_daily_loss = 5  # أقصى خسارة يومية %
        self.min_sharpe_ratio = 0.5  # الحد الأدنى لـ Sharpe Ratio
        print("🛡️ Risk Manager initialized")
    
    def calculate_optimal_amount(self, symbol, confidence, base_amount=12, max_amount=30, whale_confidence=0):
        """حساب المبلغ الأمثل باستخدام Kelly Criterion مع دمج whale_confidence و ATR خارجي"""
        # جلب ATR خارجي لتحسين المخاطر
        external_atr = get_external_atr(symbol)
        try:
            # جلب تاريخ الصفقات للعملة
            trades = self._get_symbol_trades(symbol)
            
            if len(trades) < 5:
                # لو ما فيه بيانات كافية، استخدم النظام البسيط
                return self._simple_amount_calculation(confidence, base_amount, max_amount)
            
            # حساب Win Rate و متوسط الربح/الخسارة
            wins = [t for t in trades if t['profit_percent'] > 0]
            losses = [t for t in trades if t['profit_percent'] < 0]
            
            win_rate = len(wins) / len(trades)
            avg_win = sum(t['profit_percent'] for t in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(t['profit_percent'] for t in losses) / len(losses)) if losses else 1
            
            # Kelly Criterion: f = (p * b - q) / b
            # p = win rate, q = loss rate, b = avg_win / avg_loss
            if avg_loss == 0:
                avg_loss = 1
            
            b = avg_win / avg_loss

            # حماية من القسمة على صفر في حال عدم وجود صفقات رابحة تاريخياً
            if b == 0:
                # إذا كانت نسبة الربح/الخسارة صفراً، فهذا يعني عدم توقع ربح. جزء كيلي يجب أن يكون صفراً.
                kelly_fraction = 0
            else:
                kelly_fraction = (win_rate * b - (1 - win_rate)) / b
            
            # Kelly محافظ (نصف Kelly)
            kelly_fraction = max(0, min(kelly_fraction * 0.5, 1.0))
            
            # حساب المبلغ
            available_capital = max_amount - base_amount
            optimal_amount = base_amount + (available_capital * kelly_fraction)
            
            # تعديل حسب Confidence
            confidence_multiplier = self._get_confidence_multiplier(confidence)
            optimal_amount *= confidence_multiplier

            # تعديل حسب Whale Confidence (إيجابي يزيد، سلبي يقلل)
            whale_multiplier = 1.0 + (whale_confidence / 25.0)  # normalize -25 to 25 to -1 to 1
            whale_multiplier = max(0.5, min(whale_multiplier, 1.5))  # حد 0.5-1.5
            optimal_amount *= whale_multiplier
            
            # التأكد من البقاء ضمن الحدود (لا تنزل تحت base_amount أبداً!)
            optimal_amount = max(base_amount, min(optimal_amount, max_amount))
            
            return round(optimal_amount, 2)
            
        except Exception as e:
            print(f"⚠️ Kelly calculation error: {e}")
            return max(base_amount, self._simple_amount_calculation(confidence, base_amount, max_amount))
    
    def get_risk_score(self, analysis, confidence):
        """
        تقييم درجة المخاطرة للعملة بناءً على التحليل الحالي.
        النتيجة تكون بين 0 (لا يوجد خطر) و 1 (خطر مرتفع).
        """
        try:
            risk_score = 0
            max_risk_score = 10.0  # The maximum possible score

            rsi = analysis.get('rsi', 50)
            volume_ratio = analysis.get('volume_ratio', 1.0)
            atr = analysis.get('atr', 0)
            close_price = analysis.get('df')['close'].iloc[-1] if analysis.get('df') is not None and not analysis.get('df').empty else 1

            # 1. Confidence score (weight: 4)
            if confidence < 55:
                risk_score += 4
            elif confidence < 65:
                risk_score += 2

            # 2. RSI score (weight: 3)
            if rsi < 30:
                risk_score += 3
            elif rsi < 40:
                risk_score += 1

            # 3. Volume Ratio score (weight: 2)
            if volume_ratio < 1.2:
                risk_score += 2
            
            # 4. Volatility (ATR) score (weight: 1)
            if close_price > 0:
                atr_percent = (atr / close_price) * 100
                if atr_percent > 7:  # High volatility
                    risk_score += 1

            # Normalize score to be between 0 and 1
            normalized_score = risk_score / max_risk_score
            
            return min(normalized_score, 1.0)  # Ensure it doesn't exceed 1.0

        except Exception as e:
            print(f"⚠️ Risk score calculation error: {e}")
            return 0.5  # Return a neutral score on error
    
    def _simple_amount_calculation(self, confidence, base_amount, max_amount):
        """حساب بسيط للمبلغ"""
        if confidence >= 90:
            amount = max_amount
        elif confidence >= 80:
            amount = base_amount + (max_amount - base_amount) * 0.8
        elif confidence >= 70:
            amount = base_amount + (max_amount - base_amount) * 0.6
        else:
            amount = base_amount + (max_amount - base_amount) * 0.3
        
        # التأكد من عدم النزول تحت base_amount
        return max(base_amount, amount)
    
    def _get_confidence_multiplier(self, confidence):
        """مضاعف حسب الثقة"""
        if confidence >= 90:
            return 1.2
        elif confidence >= 80:
            return 1.1
        elif confidence >= 70:
            return 1.0
        elif confidence >= 60:
            return 0.9
        else:
            return 0.8
    
    def _get_symbol_trades(self, symbol):
        """جلب تاريخ صفقات العملة"""
        try:
            all_trades = self.storage.get_all_trades()
            symbol_trades = [t for t in all_trades if t.get('symbol') == symbol]
            return symbol_trades[-20:]  # آخر 20 صفقة
        except:
            return []
    
    def calculate_sharpe_ratio(self, symbol=None, days=30):
        """حساب Sharpe Ratio (العائد/المخاطرة)"""
        try:
            trades = self._get_recent_trades(symbol, days)
            
            if len(trades) < 5:
                return 0
            
            # حساب العوائد
            returns = [t['profit_percent'] for t in trades]
            
            # متوسط العائد
            avg_return = sum(returns) / len(returns)
            
            # الانحراف المعياري (المخاطرة)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            
            if std_dev == 0:
                return 0
            
            # Sharpe Ratio (نفترض risk-free rate = 0)
            sharpe = avg_return / std_dev
            
            return round(sharpe, 2)
            
        except Exception as e:
            print(f"⚠️ Sharpe calculation error: {e}")
            return 0
    
    def _get_recent_trades(self, symbol, days):
        """جلب الصفقات الأخيرة"""
        try:
            all_trades = self.storage.get_all_trades()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            recent = [
                t for t in all_trades 
                if datetime.fromisoformat(t.get('sell_time', t.get('timestamp', '2020-01-01'))) > cutoff_date
            ]
            
            if symbol:
                recent = [t for t in recent if t.get('symbol') == symbol]
            
            return recent
            
        except:
            return []
    
    def calculate_max_drawdown(self, days=30):
        """حساب أقصى انخفاض في رأس المال"""
        try:
            trades = self._get_recent_trades(None, days)
            
            if not trades:
                return 0
            
            # حساب رأس المال التراكمي
            capital = 1000  # نقطة بداية افتراضية
            peak = capital
            max_dd = 0
            
            for trade in trades:
                profit = trade.get('profit_percent', 0)
                capital *= (1 + profit / 100)
                
                if capital > peak:
                    peak = capital
                
                drawdown = ((peak - capital) / peak) * 100
                max_dd = max(max_dd, drawdown)
            
            return round(max_dd, 2)
            
        except Exception as e:
            print(f"⚠️ Drawdown calculation error: {e}")
            return 0
    
    def should_stop_trading(self):
        """هل يجب إيقاف التداول؟"""
        try:
            # فحص الخسارة اليومية
            daily_loss = self._calculate_daily_loss()
            if daily_loss >= self.max_daily_loss:
                return {
                    'stop': True,
                    'reason': f'Daily loss {daily_loss}% >= {self.max_daily_loss}%',
                    'severity': 'HIGH'
                }
            
            # فحص Max Drawdown
            max_dd = self.calculate_max_drawdown(days=7)
            if max_dd >= self.max_drawdown_percent:
                return {
                    'stop': True,
                    'reason': f'Max drawdown {max_dd}% >= {self.max_drawdown_percent}%',
                    'severity': 'CRITICAL'
                }
            
            # فحص Sharpe Ratio
            sharpe = self.calculate_sharpe_ratio(days=7)
            if sharpe < self.min_sharpe_ratio and len(self._get_recent_trades(None, 7)) >= 10:
                return {
                    'stop': True,
                    'reason': f'Sharpe Ratio {sharpe} < {self.min_sharpe_ratio}',
                    'severity': 'MEDIUM'
                }
            
            return {'stop': False, 'reason': 'All checks passed'}
            
        except Exception as e:
            print(f"⚠️ Stop check error: {e}")
            return {'stop': False, 'reason': 'Error in check'}
    
    def _calculate_daily_loss(self):
        """حساب الخسارة اليومية"""
        try:
            today_trades = self._get_recent_trades(None, days=1)
            
            if not today_trades:
                return 0
            
            total_profit = sum(t.get('profit_percent', 0) for t in today_trades)
            
            return abs(min(0, total_profit))
            
        except:
            return 0
    
    def get_position_size(self, symbol, confidence, total_balance, max_positions=20):
        """حساب حجم الصفقة المثالي"""
        try:
            # حساب رأس المال المتاح لكل صفقة
            capital_per_position = total_balance / max_positions
            
            # حساب المبلغ الأمثل
            optimal_amount = self.calculate_optimal_amount(
                symbol, 
                confidence, 
                base_amount=12,  # الحد الأدنى 12 (آمن للبيع)
                max_amount=min(30, capital_per_position)  # الحد الأقصى 30
            )
            
            # التأكد من عدم تجاوز 5% من رأس المال
            max_per_trade = total_balance * 0.05
            optimal_amount = min(optimal_amount, max_per_trade)
            
            # التأكد من عدم النزول تحت 12 (لتجنب العلق)
            optimal_amount = max(12, optimal_amount)
            
            return round(optimal_amount, 2)
            
        except Exception as e:
            print(f"⚠️ Position size error: {e}")
            return 12  # الحد الأدنى الآمن
    
    def calculate_risk_reward_ratio(self, entry_price, tp_price, sl_price):
        """حساب نسبة المخاطرة/العائد"""
        try:
            potential_profit = ((tp_price - entry_price) / entry_price) * 100
            potential_loss = ((entry_price - sl_price) / entry_price) * 100
            
            if potential_loss == 0:
                return 0
            
            rr_ratio = potential_profit / potential_loss
            
            return round(rr_ratio, 2)
            
        except:
            return 0
    
    def get_risk_report(self):
        """تقرير شامل عن المخاطر"""
        try:
            sharpe_7d = self.calculate_sharpe_ratio(days=7)
            sharpe_30d = self.calculate_sharpe_ratio(days=30)
            max_dd_7d = self.calculate_max_drawdown(days=7)
            max_dd_30d = self.calculate_max_drawdown(days=30)
            daily_loss = self._calculate_daily_loss()
            
            # تقييم المخاطر
            risk_level = 'LOW'
            if max_dd_7d > 7 or daily_loss > 3:
                risk_level = 'HIGH'
            elif max_dd_7d > 5 or daily_loss > 2:
                risk_level = 'MEDIUM'
            
            return {
                'sharpe_ratio_7d': sharpe_7d,
                'sharpe_ratio_30d': sharpe_30d,
                'max_drawdown_7d': max_dd_7d,
                'max_drawdown_30d': max_dd_30d,
                'daily_loss': daily_loss,
                'risk_level': risk_level,
                'timestamp': datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"⚠️ Risk report error: {e}")
            return None

    def suggest_stop_loss(self, symbol, position, analysis, mtf):
        """اقتراح مسافة ستوبロス ذكية بناءً على إدارة المخاطر"""
        try:
            # حساب مسافة الستوبロス基于 ATR ونسبة المخاطرة/العائد
            atr = analysis.get('atr', 0)
            current_price = analysis.get('close', 0)
            
            if atr > 0 and current_price > 0:
                # مسافة الستوبロス基于 ATR (مضاعف 1.5 إلى 2.5 basado على الثقة)
                atr_multiplier = 2.0  # 기본값
                confidence = analysis.get('confidence', 50)  # اگر در analysis نیست، از تابع利用可能
                
                # تعديل المضاعف baseado على الثقة
                if confidence > 70:
                    atr_multiplier = 2.5  # مسافة أوسع للثقة العالية
                elif confidence < 30:
                    atr_multiplier = 1.5  # مسافة أقرب للثقة المنخفضة
                
                stop_distance_percent = (atr * atr_multiplier / current_price) * 100
                
                # تعديل بناءً على نسبة المخاطرة/العائد من Kelly Criterion
                kelly_data = self._get_kelly_data(symbol)
                if kelly_data:
                    # إذا كانت فرصة Kelly جيدة (فرصة ربح عالية)، podemos aumentar ligeramente el stop
                    if kelly_data['kelly_fraction'] > 0.3:
                        stop_distance_percent *= 1.1
                    elif kelly_data['kelly_fraction'] < 0.1:  # فرصة ضعيفة، נחזק את ההגנה
                        stop_distance_percent *= 0.9
                
                # ضمان أن القيمة ضمن نطاق معقول
                stop_distance_percent = max(0.5, min(stop_distance_percent, 5.0))
                return stop_distance_percent
            
            # phương pháp dự phòng: استخدام Kelly Criterion напрямую
            kelly_data = self._get_kelly_data(symbol)
            if kelly_data:
                # تحويل نسبة Kelly إلى مسافة توقف معقولة
                # Kelly العالي = ثقة أعلى = مسافة توقف أوسع قليلًا
                base_stop = 1.5
                kelly_adjustment = 1.0 + (kelly_data['kelly_fraction'] * 0.5)  # 0 إلى 0.5
                stop_distance = base_stop * kelly_adjustment
                return max(0.5, min(stop_distance, 5.0))
            
            # última fallback: مسافة افتراضية معقولة
            return 1.5
        except Exception as e:
            print(f"⚠️ Risk manager stop loss suggestion error: {e}")
            return 1.5  # مسافة افتراضية معقولة

    def _get_kelly_data(self, symbol):
        """الحصول على بيانات Kelly Criterion لحساب مسافة الستوبロス"""
        try:
            trades = self._get_symbol_trades(symbol)
            
            if len(trades) < 5:
                return None
            
            # حساب Win Rate و متوسط الربح/الخسارة
            wins = [t for t in trades if t['profit_percent'] > 0]
            losses = [t for t in trades if t['profit_percent'] < 0]
            
            if not wins or not losses:
                return None
                
            win_rate = len(wins) / len(trades)
            loss_rate = 1 - win_rate
            avg_win = sum(t['profit_percent'] for t in wins) / len(wins)
            avg_loss = abs(sum(t['profit_percent'] for t in losses) / len(losses))
            
            if avg_loss == 0:
                avg_loss = 1
            
            # Kelly Criterion: f = (p * b - q) / b
            # p = win rate, q = loss rate, b = avg_win / avg_loss
            b = avg_win / avg_loss if avg_loss > 0 else 0
            
            if b == 0:
                kelly_fraction = 0
            else:
                kelly_fraction = (win_rate * b - loss_rate) / b
            
            # Kelly محافظ (نصف Kelly) مع حدود آمنة
            kelly_fraction = max(0.0, min(kelly_fraction * 0.5, 0.5))
            
            return {
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'kelly_fraction': kelly_fraction
            }
        except Exception as e:
            print(f"⚠️ Kelly data error: {e}")
            return None
