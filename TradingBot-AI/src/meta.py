"""
👑 Meta (The King) - القرار النهائي
تم تقليص الكود عبر نقل العمليات الحسابية اليدوية للموديلات الـ 6 المتعلمة
"""
import pandas as pd
from datetime import datetime
from config import MIN_TRADE_AMOUNT, META_BUY_INTELLIGENCE

class Meta:
    def __init__(self, advisor_manager=None, storage=None):
        self.advisor_manager = advisor_manager
        self.storage = storage
        print("👑 Meta (The King) is initialized and ruling via AI Models.")

    def _map_ml_advice_to_score(self, advice):
        """تحويل مخرجات الذكاء الاصطناعي إلى نقاط رقمية"""
        if not advice or advice == 'N/A': return 50
        mapping = {'Strong-Bullish': 95, 'Bullish': 75, 'Neutral': 50, 'Bearish': 25, 'Strong-Bearish': 5}
        return mapping.get(str(advice), 50)

    def _gather_buy_advisors_intelligence(self, symbol, analysis_data, reasons):
        """جمع الذكاء من الـ 6 موديلات المتعلمة + المستشارين المنطقيين"""
        advisors_intelligence = {}
        ml_advice = {}
        
        try:
            dl_client = self.advisor_manager.get('dl_client')
            if dl_client:
                ml_advice = dl_client.get_advice(
                    rsi=analysis_data.get('rsi', 50), macd=analysis_data.get('macd_diff', 0),
                    volume_ratio=analysis_data.get('volume_ratio', 1.0),
                    price_momentum=analysis_data.get('price_momentum', 0),
                    analysis_data=analysis_data
                )
        except: pass

        # 🚀 1. سحب مخرجات الموديلات الـ 6 المتعلمة حصرياً
        advisors_intelligence['whale_activity'] = self._map_ml_advice_to_score(ml_advice.get('smart_money'))
        advisors_intelligence['risk_level'] = self._map_ml_advice_to_score(ml_advice.get('risk'))
        advisors_intelligence['anomaly_risk'] = self._map_ml_advice_to_score(ml_advice.get('anomaly'))
        advisors_intelligence['entry_timing'] = self._map_ml_advice_to_score(ml_advice.get('exit'))
        advisors_intelligence['liquidity_score'] = self._map_ml_advice_to_score(ml_advice.get('liquidity'))
        
        ml_pattern_score = self._map_ml_advice_to_score(ml_advice.get('pattern'))
        candle_expert_score = self._map_ml_advice_to_score(ml_advice.get('candle_expert'))

        # 🛠️ 2. المستشارون المنطقيون (Logic Based) - دعم فني
        try:
            # 🌐 Macro Trend Filter (حارس الاتجاه الكلي)
            macro_score = 50
            macro_adv = self.advisor_manager.get('MacroTrendAdvisor')
            if macro_adv:
                status = macro_adv.get_macro_status()
                if "BULL" in status:
                    macro_score = 90 if "STRONG" in status else 75
                elif "BEAR" in status:
                    macro_score = 10 if "STRONG" in status else 25
            advisors_intelligence['macro_trend'] = macro_score

            # صائد القمم والقيعان اليدوي (Ground Truth)
            peak_valley_score = 50
            pattern_rec = self.advisor_manager.get('EnhancedPatternRecognition')
            if pattern_rec:
                p_res = pattern_rec.analyze_peak_hunter_pattern(analysis_data.get('candles', []))
                if p_res['signal'] == 'buy': peak_valley_score = 85
                elif p_res['signal'] == 'sell': peak_valley_score = 15
            
            # دمج مخرجات ML مع صائد القيعان اليدوي
            combined_p = (ml_pattern_score * 0.4 + candle_expert_score * 0.3 + peak_valley_score * 0.3)
            advisors_intelligence['pattern_confidence'] = min(100, combined_p)
            advisors_intelligence['peak_valley_score'] = peak_valley_score

            # درع التصفية وبداية الاتجاه
            trend_det = self.advisor_manager.get('TrendEarlyDetector')
            if trend_det:
                df = pd.DataFrame(analysis_data.get('candles', []))
                if len(df) >= 20:
                    t_res = trend_det.detect_trend_birth(df, analysis_data.get('order_book'))
                    advisors_intelligence['trend_birth'] = 90 if t_res['trend'] == 'BULLISH' else 30
        except: pass

        return advisors_intelligence

    def should_buy(self, symbol, analysis, preloaded_advisors=None):
        """اتخاذ قرار الشراء بناءً على إجماع النماذج"""
        advisors_intelligence = self._gather_buy_advisors_intelligence(symbol, analysis, [])
        
        # حساب الثقة النهائية (الملك يزن مخرجات الموديلات)
        # الأوزان الجديدة تعطي أولوية للمايكرو والأنماط
        total_intel = (
            advisors_intelligence.get('macro_trend', 50) * 0.20 +      # الاتجاه الكلي (الفلتر الأساسي)
            advisors_intelligence.get('pattern_confidence', 50) * 0.25 + # صائد القاع والأنماط
            advisors_intelligence.get('whale_activity', 50) * 0.15 +    # نشاط الحيتان
            advisors_intelligence.get('trend_birth', 50) * 0.15 +       # بداية الزخم
            advisors_intelligence.get('liquidity_score', 50) * 0.15 +   # قوة السيولة
            advisors_intelligence.get('risk_level', 50) * 0.10          # أمان الصفقة
        )

        if total_intel >= META_BUY_INTELLIGENCE or advisors_intelligence.get('peak_valley_score', 50) >= 80:
            return {'action': 'BUY', 'confidence': total_intel, 'reason': f"AI Consensus: {total_intel:.0f}/100", 'amount': MIN_TRADE_AMOUNT}
        return {'action': 'DISPLAY', 'confidence': total_intel, 'reason': "Watching"}

    def should_sell(self, symbol, position, current_price, analysis, mtf, preloaded_advisors=None):
        """قرار البيع والستوب لوس الديناميكي بناءً على مخرجات ML"""
        # جلب ذكاء الموديلات (نفس المجمع للشراء)
        advisors_intelligence = self._gather_buy_advisors_intelligence(symbol, analysis, [])
        
        # حساب ثقة البيع (Sell Confidence) - عكس الشراء
        # نستخدم (100 - القيمة) لأن انخفاض ثقة الشراء يعني ارتفاع ثقة البيع
        sell_confidence = (
            (100 - advisors_intelligence.get('entry_timing', 50)) * 0.25 + # توقيت الخروج (Exit ML)
            (100 - advisors_intelligence.get('macro_trend', 50)) * 0.20 +  # الاتجاه الكلي هابط
            (100 - advisors_intelligence.get('risk_level', 50)) * 0.15 +   # ارتفاع المخاطر
            (100 - advisors_intelligence.get('pattern_confidence', 50)) * 0.15 + # كسر الأنماط
            (100 - advisors_intelligence.get('whale_activity', 50)) * 0.15 + # خروج الحيتان
            (100 - advisors_intelligence.get('anomaly_risk', 50)) * 0.10     # رصد شذوذ (فخ)
        )

        risk_level = advisors_intelligence.get('risk_level', 50)
        exit_timing = advisors_intelligence.get('entry_timing', 50)
        
        buy_price = float(position.get('buy_price', 0))
        profit_pct = ((current_price - buy_price) / buy_price) * 100
        
        # ستوب لوس ذكي يتأثر بموديل المخاطر (ML Risk)
        base_sl = analysis.get('atr_percent', 2.5) * (1 + risk_level / 100)
        
        highest = position.get('highest_price', buy_price)
        drop_from_peak = ((highest - current_price) / highest) * 100
        
        if drop_from_peak >= base_sl or profit_pct <= -12:
            return {'action': 'SELL', 'reason': f"ML Risk SL Triggered ({risk_level})", 'profit': profit_pct}

        # قرار البيع عند رصد قمة عبر ثقة البيع (بدل عدد الأصوات)
        if (sell_confidence >= 70 and profit_pct >= 0.5) or exit_timing <= 15:
            return {'action': 'SELL', 'reason': f"AI Peak Confidence: {sell_confidence:.1f}%", 'profit': profit_pct}

        return {'action': 'HOLD', 'reason': "AI Bullish trend", 'profit': profit_pct}
