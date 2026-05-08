# MSA Smart Trading Bot

بوت تداول ذكي يعتمد على استراتيجية Wave Rider، ونظام Meta Decision، ونماذج LightGBM للتصويت والتعلم من الصفقات.

## التشغيل السريع

1. ثبت التبعيات:
   `pip install -r requirements.txt`
2. جهز البيئة:
   `scripts/setup.bat`
3. شغل البوت:
   `scripts/run_trading_bot.bat`

## وضع التشغيل الحالي

- بيانات السوق والشموع والتحليل الفني: Binance الرسمي `live public market data`.
- تنفيذ أوامر البيع والشراء: Binance sandbox/testnet.
- الهدف: اختبار قرارات حقيقية على سوق حقيقي، مع تنفيذ وهمي آمن.

## بنية المشروع

### نقطة الدخول والتكوين

- `app/trading_bot.py`: نقطة تشغيل البوت والحلقة الرئيسية.
- `app_config/config.py`: إعدادات التداول والعتبات والعملات.
- `app_config/config_encrypted.py`: مفاتيح API و Discord المشفرة.
- `.env`: متغيرات البيئة.

### التحليل الفني وبيانات السوق

- `analysis_parts/core.py`: بناء نتيجة التحليل الكاملة لكل عملة.
- `analysis_parts/market_data.py`: جلب الشموع والكاش وبيانات BTC/ETH/BNB.
- `analysis_parts/patterns.py`: تحليل القاع والقمة والبنية الفنية.
- `analysis_parts/liquidity.py`: مقاييس السيولة ودفتر الأوامر.
- `analysis_parts/mtf.py`: تحليل متعدد الإطارات من بيانات 5m.
- `analysis_parts/market_intelligence.py`: حالة السوق والحماية من الانهيارات.
- `analysis_parts/psychology.py`: مؤشرات الذعر والطمع.

### منطق القرار Meta

- `meta/meta_core.py`: كلاس Meta الرئيسي.
- `meta/meta_buy.py`: قرار شراء القاع.
- `meta/meta_sell.py`: قرار بيع القمة والخروج.
- `meta/meta_advisors.py`: تصويت المستشارين.
- `meta/meta_learning.py`: التعلم من الصفقات السابقة.

### Bot Handlers

- `bot/main_loop.py`: إدارة دورة التداول.
- `bot/buy_handler.py`: تنفيذ ومعالجة الشراء.
- `bot/sell_handler.py`: تنفيذ ومعالجة البيع.
- `bot/advisor_manager.py`: تحميل وإدارة المستشارين.

### نماذج AI والتكاملات

- `ai/dl_client_v2.py`: تحميل نماذج LightGBM من قاعدة البيانات.
- `models/`: مستشارو التحليل الثابت مثل MacroTrend, MTF, Fibonacci, Realtime PA.
- `integrations/external_apis.py`: APIs خارجية.
- `integrations/news_analyzer.py`: تحليل الأخبار.
- `messaging/discord.py`: إشعارات وتقارير Discord.

### التداول والتخزين

- `trading/capital_manager.py`: إدارة رأس المال.
- `trading/utils.py`: تنفيذ الأوامر وحفظ الصفقات وحسابات مساعدة.
- `storage/`: التخزين المحلي/قاعدة البيانات/الهجين.
- `memory/`: الذاكرة والكاش المضغوط.

## نماذج LightGBM

البوت يستخدم 12 نموذجًا من قاعدة البيانات:

- `smart_money`
- `risk`
- `anomaly`
- `exit`
- `pattern`
- `liquidity`
- `chart_cnn`
- `candle_expert`
- `volume_pred`
- `sentiment`
- `crypto_news`
- `meta_trading`

## التخصيص

عدّل:

- `app_config/config.py`
- `app_config/config_encrypted.py`
- `.env`

أهم الإعدادات:

- `MIN_BUY_CONFIDENCE`
- `MIN_SELL_CONFIDENCE`
- `SYMBOLS`
- `MAX_CAPITAL`
- `MAX_POSITIONS`
- `BATCH_SIZE`
- `MAX_WORKERS`
