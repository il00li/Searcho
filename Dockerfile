FROM php:8.2-cli

WORKDIR /app

# تثبيت curl
RUN apt-get update && apt-get install -y curl

# نسخ ملفات البوت كاملة
COPY . /app

# إخطار Render بالمنفذ
EXPOSE 10000

# تشغيل PHP Built-in Web Server باستخدام متغير PORT
CMD ["sh", "-c", "php -S 0.0.0.0:${PORT:-10000} index.php"] 
