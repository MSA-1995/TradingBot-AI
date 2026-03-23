"""
🧠 Market Mood Analyzer v3 - محلل مزاج السوق

- يحلل نفسية السوق العامة باستخدام مؤشرات استراتيجية.
- يستخدم نظام كاش مشترك مع قفل (Shared File Cache with Locking) لمنع تلف الملفات.
"""
import requests
import time
import json
import os

class MarketMoodAnalyzer:
    def __init__(self, cache_duration=300): # 5 دقائق كاش
        """
        تهيئة المحلل مع نظام الكاش المشترك والقفل
        """
        print("🧠 Market Mood Analyzer v3 (Locking) initialized")
        self.fear_and_greed_api = "https://api.alternative.me/fng/?limit=1"
        self.btc_dominance_api = "https://api.coingecko.com/api/v3/global"
        self.cache_duration = cache_duration
        
        # تحديد مسارات الكاش والقفل
        base_path = os.path.dirname(__file__)
        self.cache_file_path = os.path.join(base_path, '..', 'src', 'market_mood_cache.json')
        self.lock_file_path = self.cache_file_path + '.lock'

    def _acquire_lock(self, timeout=10):
        """محاولة الحصول على القفل"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 'x' للإنشاء الحصري، يفشل إذا كان الملف موجودًا
                lock_file = open(self.lock_file_path, 'x')
                lock_file.close()
                return True
            except FileExistsError:
                time.sleep(0.2) # انتظار تحرير القفل
        return False

    def _release_lock(self):
        """تحرير القفل"""
        try:
            if os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
        except OSError as e:
            print(f"⚠️ MarketMood: خطأ في تحرير القفل: {e}")

    def _read_cache(self):
        """قراءة البيانات من ملف الكاش"""
        try:
            if not os.path.exists(self.cache_file_path):
                return None
            with open(self.cache_file_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            # إذا كان الملف تالفًا، نعتبره غير موجود
            return None

    def _write_cache(self, data):
        """كتابة البيانات إلى ملف الكاش"""
        try:
            with open(self.cache_file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"⚠️ MarketMood: خطأ في كتابة ملف الكاش: {e}")

    def _fetch_all_data(self):
        """جلب جميع بيانات السوق وتحديث الكاش بأمان"""
        if not self._acquire_lock():
            print("⚠️ MarketMood: فشل في الحصول على القفل، سيتم إعادة محاولة القراءة.")
            time.sleep(1)
            return self._read_cache()
        
        try:
            # إعادة فحص الكاش بعد الحصول على القفل (قد يكون خيط آخر قد قام بالتحديث)
            cache = self._read_cache()
            if cache and (time.time() - cache.get('last_fetch_time', 0)) <= self.cache_duration:
                print("ℹ️ MarketMood: الكاش تم تحديثه بواسطة عملية أخرى أثناء الانتظار.")
                return cache

            print("🔄 MarketMood: تحديث بيانات مزاج السوق من API...")
            fng_data = None
            btc_dominance = None

            # جلب البيانات من APIs
            try:
                response = requests.get(self.fear_and_greed_api, timeout=10)
                response.raise_for_status()
                data = response.json()['data'][0]
                fng_data = {'value': int(data['value']), 'classification': data['value_classification']}
            except Exception as e:
                print(f"⚠️ MarketMood: فشل جلب مؤشر الخوف والطمع: {e}")

            try:
                response = requests.get(self.btc_dominance_api, timeout=10)
                response.raise_for_status()
                btc_dominance = response.json()['data']['market_cap_percentage']['btc']
            except Exception as e:
                print(f"⚠️ MarketMood: فشل جلب هيمنة البيتكوين: {e}")

            # تحديث الكاش بالبيانات الجديدة
            new_cache_data = self._read_cache() or {}
            if fng_data: new_cache_data['fng_data'] = fng_data
            if btc_dominance: new_cache_data['btc_dominance'] = btc_dominance
            new_cache_data['last_fetch_time'] = time.time()
            
            self._write_cache(new_cache_data)
            return new_cache_data

        finally:
            self._release_lock() # الأهم: تحرير القفل دائمًا

    def get_mood_adjustment(self, symbol):
        """
        حساب دفعة الثقة بناءً على مزاج السوق العام
        """
        cache = self._read_cache()

        if not cache or (time.time() - cache.get('last_fetch_time', 0)) > self.cache_duration:
            cache = self._fetch_all_data()

        if not cache:
            return {'adjustment': 0, 'reason': "No Cache Data"}

        total_adjustment = 0
        mood_reasons = []

        # التحليل من الكاش
        fng_data = cache.get('fng_data')
        if fng_data:
            fng_value = fng_data['value']
            if fng_value <= 25:
                total_adjustment += 10
                mood_reasons.append(f"F&G={fng_value} (Extreme Fear)")
            elif fng_value >= 75:
                total_adjustment -= 15
                mood_reasons.append(f"F&G={fng_value} (Extreme Greed)")

        if 'BTC' not in symbol.upper():
            btc_dominance = cache.get('btc_dominance')
            if btc_dominance:
                if btc_dominance > 50:
                    total_adjustment -= 5
                    mood_reasons.append(f"BTC.D={btc_dominance:.1f}% (High)")

        reason_str = ", ".join(mood_reasons) if mood_reasons else "Neutral"
        return {'adjustment': total_adjustment, 'reason': reason_str}
