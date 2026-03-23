"""
🧠 Market Mood Analyzer - محلل مزاج السوق

- يحلل نفسية السوق العامة باستخدام مؤشرات استراتيجية.
- مؤشر الخوف والطمع (Fear & Greed Index).
- هيمنة البيتكوين (BTC Dominance).
- يعطي دفعة ثقة (Confidence Boost) أو تحذير بناءً على مزاج السوق.
- يستخدم نظام كاش (Cache) لتقليل طلبات API.
"""
import requests
import time

class MarketMoodAnalyzer:
    def __init__(self, cache_duration=300): # 5 دقائق كاش
        """
        تهيئة المحلل مع نظام الكاش
        """
        print("🧠 Market Mood Analyzer initialized")
        # روابط API
        self.fear_and_greed_api = "https://api.alternative.me/fng/?limit=1"
        self.btc_dominance_api = "https://api.coingecko.com/api/v3/global"

        # إعدادات الكاش
        self.cache_duration = cache_duration
        self.last_fetch_time = 0
        self.cached_fng = None
        self.cached_btc_dominance = None

    def _is_cache_valid(self):
        """فحص صلاحية الكاش"""
        return (time.time() - self.last_fetch_time) < self.cache_duration

    def get_fear_and_greed_index(self):
        """
        جلب مؤشر الخوف والطمع (مع كاش)
        """
        if self._is_cache_valid() and self.cached_fng is not None:
            return self.cached_fng # إرجاع البيانات من الكاش

        try:
            response = requests.get(self.fear_and_greed_api, timeout=10)
            response.raise_for_status()
            data = response.json()['data'][0]
            value = int(data['value'])
            classification = data['value_classification']
            
            result = {'value': value, 'classification': classification}
            self.cached_fng = result # تخزين النتيجة في الكاش
            self.last_fetch_time = time.time() # تحديث وقت الجلب
            return result
        except Exception as e:
            print(f"⚠️ MarketMood: خطأ في جلب مؤشر الخوف والطمع: {e}")
            # في حالة الخطأ، نرجع آخر بيانات ناجحة إذا كانت موجودة
            return self.cached_fng if self.cached_fng else None

    def get_btc_dominance(self):
        """
        جلب نسبة هيمنة البيتكوين (مع كاش)
        """
        if self._is_cache_valid() and self.cached_btc_dominance is not None:
            return self.cached_btc_dominance

        try:
            response = requests.get(self.btc_dominance_api, timeout=10)
            response.raise_for_status()
            data = response.json()['data']
            btc_dominance = data['market_cap_percentage']['btc']
            
            self.cached_btc_dominance = btc_dominance
            # لا نحدث وقت الجلب هنا لنسمح لدالة الخوف والطمع بتحديثه
            # هذا يضمن أن كلا الطلبين يحدثان في نفس الدورة عند انتهاء صلاحية الكاش
            return btc_dominance
        except Exception as e:
            print(f"⚠️ MarketMood: خطأ في جلب هيمنة البيتكوين: {e}")
            return self.cached_btc_dominance if self.cached_btc_dominance else None

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
