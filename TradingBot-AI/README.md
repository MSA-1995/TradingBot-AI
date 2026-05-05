# 🤖 MSA Smart Trading Bot V2.0

بوت تداول ذكي يعتمد على استراتيجية **Wave Rider** والتعلم العميق (LightGBM). يستهدف أرباحاً تتراوح بين 50% إلى 80% على العملات القيادية.

## 🚀 التشغيل السريع
1. قم بتثبيت التبعيات: `pip install -r requirements.txt`
2. أعد إعداد البيئة باستخدام `scripts/setup.bat`
3. شغل البوت: `scripts/run_trading_bot.bat`

## 📁 بنية المشروع

### 1. نقطة الدخول والتكوين
- `src/trading_bot.py`: الحلقة الرئيسية للبوت
- `src/config.py`: إعدادات التداول والعتبات والعملات
- `src/config_encrypted.py`: إعدادات مشفرة للـ API
- `.env`: متغيرات البيئة

### 2. المنطق الأساسي (Meta)
- `src/meta/meta_core.py`: الكلاس الرئيسي Meta
- `src/meta/meta_buy.py`: منطق قرار الشراء
- `src/meta/meta_sell.py`: منطق قرار البيع
- `src/meta/meta_advisors.py`: إدارة مستشاري الذكاء الاصطناعي
- `src/meta/meta_learning.py`: التعلم من الصفقات السابقة

### 3. الميكروسيرفيس (Bot Handlers)
- `src/bot/main_loop.py`: الحلقة الرئيسية
- `src/bot/buy_handler.py`: معالجة أوامر الشراء
- `src/bot/sell_handler.py`: معالجة أوامر البيع
- `src/bot/advisor_manager.py`: إدارة المستشارين

### 4. النماذج (AI Models)
- **LightGBM Models (12) من قاعدة البيانات:**
  - `smart_money` - تحليل حركة الحيتان
  - `risk` - تقييم مخاطر السوق
  - `anomaly` - كشف الشذوذ
  - `exit` - نقاط الخروج المثالية
  - `pattern` - الأنماط الفنية
  - `liquidity` - تحليل السيولة
  - `chart_cnn` - التحليل البصري
  - `candle_expert` - خبير الشمعات
  - `volume_pred` - توقع الحجم
  - `sentiment` - تحليل المشاعر
  - `crypto_news` - تحليل الأخبار
  - `meta_trading` - الثقة الخارجية

- **Models Directory:**
  - `models/macro_trend_advisor.py`: مستشار الاتجاه الكلي
  - `models/multi_timeframe_analyzer.py`: تحليل متعدد الإطارات الزمنية
  - `models/realtime_price_action.py`: تحليل السعر الفعلي
  - `models/fibonacci_analyzer.py`: تحليل فيبوناتشي
  - `models/volume_forecast_engine.py`: محرك توقع الحجم
  - `models/liquidation_shield.py`: حماية التصفية

### 5. الدعم والتخزين
- `src/storage/`: نظام التخزين (محلي/قاعدة بيانات/مختلط)
- `memory/`: إدارة الذاكرة والتخزين المؤقت
- `src/analysis.py`: مؤشرات فنية
- `src/notifications.py`: إشعارات Discord
- `src/news_analyzer.py`: تحليل الأخبار

## ⚙️ التخصيص
عدل ملفات `config.py` و `config_encrypted.py` لتحديد:
- الحد الأدنى للبيع/الشراء (MIN_SELL_CONFIDENCE, MIN_BUY_CONFIDENCE)
- قائمة العملات للتداول
- حدود رأس المال