# إعداد PostgreSQL (Supabase) - دليل سريع

## الخطوة 1: إنشاء قاعدة البيانات

1. روح: https://supabase.com
2. سجل حساب مجاني
3. اضغط "New Project"
4. املأ:
   - Name: `trading-bot`
   - Password: (احفظه!)
   - Region: `Asia-Pacific`
5. انتظر 2 دقيقة حتى يخلص

## الخطوة 2: الحصول على Connection String

Connection String حقك:
```
postgresql://postgres.etzdipnphgbihfyqglyu:%23%23SnYb%25Din7%21H%2C%2F@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

## الخطوة 3: الاستخدام

### على جهازك المحلي (JSON):
```bash
# لا تحتاج شي! يشتغل مباشرة
python src/trading_bot.py
```

### على Koyeb (PostgreSQL):
```bash
# في Koyeb Environment Variables:
DATABASE_URL=postgresql://postgres.etzdipnphgbihfyqglyu:%23%23SnYb%25Din7%21H%2C%2F@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# البوت يكتشف تلقائياً ويستخدم PostgreSQL!
```

## الخطوة 4: التحقق

البوت يطبع عند التشغيل:
- `✅ Using PostgreSQL (Supabase)` ← على Koyeb
- `✅ Using JSON (Local)` ← على جهازك

## ملاحظات مهمة:

1. **الباسورد مشفر في Connection String:**
   - `##SnYb%Din7!H,/` → `%23%23SnYb%25Din7%21H%2C%2F`
   - لا تغير التشفير!

2. **الجدول ينشأ تلقائياً:**
   - البوت ينشئ جدول `positions` أول مرة
   - لا تحتاج تسوي شي يدوياً

3. **التبديل بين JSON و PostgreSQL:**
   - على جهازك: احذف `DATABASE_URL` → JSON
   - على Koyeb: ضيف `DATABASE_URL` → PostgreSQL

## استكشاف الأخطاء:

### خطأ: "connection refused"
- تأكد من Connection String صحيح
- تأكد من الباسورد مشفر صح

### خطأ: "table does not exist"
- عادي! البوت ينشئه تلقائياً
- لو استمر، شيك Supabase Dashboard

### البوت يستخدم JSON بدل PostgreSQL:
- تأكد من `DATABASE_URL` موجود في Environment Variables
- تأكد من التهجئة صحيحة (حساس لحالة الأحرف)

## الدعم:

لو واجهت مشكلة، تأكد من:
1. ✅ Supabase Project شغال (Status: Healthy)
2. ✅ Connection String كامل وصحيح
3. ✅ الباسورد مشفر (URL encoded)
4. ✅ `psycopg2-binary` مثبت: `pip install psycopg2-binary`
