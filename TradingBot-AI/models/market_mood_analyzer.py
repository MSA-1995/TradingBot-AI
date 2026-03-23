"""
🧠 Market Mood Analyzer - محلل مزاج السوق

- يحلل نفسية السوق العامة باستخدام مؤشرات استراتيجية.
- مؤشر الخوف والطمع (Fear & Greed Index).
- هيمنة البيتكوين (BTC Dominance).
- يعطي دفعة ثقة (Confidence Boost) أو تحذير بناءً على مزاج السوق.
"""
import requests # سنحتاج هذه المكتبة لجلب البيانات من الإنترنت

class MarketMoodAnalyzer:
    def __init__(self):
        """
        تهيئة المحلل
        """
        print("🧠 Market Mood Analyzer initialized")
        # روابط API لجلب البيانات الحية
        self.fear_and_greed_api = "https://api.alternative.me/fng/?limit=1"
        # لهيمنة البيتكوين، سنستخدم API مثل CoinGecko (هذا مثال)
        self.btc_dominance_api = "https://api.coingecko.com/api/v3/global"

    def get_fear_and_greed_index(self):
        """
        جلب مؤشر الخوف والطمع
        - أقل من 25 (خوف شديد) -> فرصة شراء عكسية
        - أعلى من 75 (طمع شديد) -> خطر وتصحيح محتمل
        """
        try:
            # استخدام timeout لتجنب الانتظار الطويل
            response = requests.get(self.fear_and_greed_api, timeout=10)
            response.raise_for_status() # التأكد من نجاح الطلب
            data = response.json()['data'][0]
            value = int(data['value'])
            classification = data['value_classification']
            return {'value': value, 'classification': classification}
        except Exception as e:
            print(f"⚠️ MarketMood: خطأ في جلب مؤشر الخوف والطمع: {e}")
            return None # في حالة الفشل، لا نؤثر على القرار

    def get_btc_dominance(self):
        """
        جلب نسبة هيمنة البيتكوين
        - إذا كانت الهيمنة ترتفع، تسحب السيولة من العملات البديلة (سلبي).
        - إذا كانت الهيمنة تنخفض، تذهب السيولة للعملات البديلة (إيجابي).
        """
        try:
            response = requests.get(self.btc_dominance_api, timeout=10)
            response.raise_for_status()
            data = response.json()['data']
            btc_dominance = data['market_cap_percentage']['btc']
            return btc_dominance
        except Exception as e:
            print(f"⚠️ MarketMood: خطأ في جلب هيمنة البيتكوين: {e}")
            return None

    def get_mood_adjustment(self, symbol):
        """
        حساب دفعة الثقة بناءً على مزاج السوق العام
        """
        total_adjustment = 0
        mood_reasons = []

        # 1. تحليل الخوف والطمع
        fng_data = self.get_fear_and_greed_index()
        if fng_data:
            fng_value = fng_data['value']
            if fng_value <= 25: # خوف شديد (فرصة)
                total_adjustment += 10
                mood_reasons.append(f"F&G={fng_value} (Extreme Fear)")
            elif fng_value >= 75: # طمع شديد (خطر)
                total_adjustment -= 15
                mood_reasons.append(f"F&G={fng_value} (Extreme Greed)")

        # 2. تحليل هيمنة البيتكوين (يؤثر فقط على العملات البديلة)
        if 'BTC' not in symbol.upper():
            btc_dominance = self.get_btc_dominance()
            if btc_dominance:
                # هذا منطق مبسط، يمكن تطويره لاحقًا لتحليل "اتجاه" الهيمنة
                if btc_dominance > 50: # هيمنة عالية قد تكون سلبية للـ Alts
                    total_adjustment -= 5
                    mood_reasons.append(f"BTC.D={btc_dominance:.1f}% (High)")

        reason_str = ", ".join(mood_reasons) if mood_reasons else "Neutral"
        return {'adjustment': total_adjustment, 'reason': reason_str}