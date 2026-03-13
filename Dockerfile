# استخدام Python 3.11
FROM python:3.11-slim

# تعيين مجلد العمل
WORKDIR /app

# نسخ requirements.txt أولاً
COPY TradingBot-AI/requirements.txt .

# تثبيت المكتبات (قبل نسخ الكود)
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY TradingBot-AI/ .

# تعيين مجلد العمل للـ src
WORKDIR /app/src

# تشغيل البوت
CMD ["python", "trading_bot.py"]
