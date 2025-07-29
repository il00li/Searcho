# Use official PHP with Apache
FROM php:8.2-apache

# تحديد مجلد العمل
WORKDIR /var/www/html

# نسخ كامل ملفات البوت (index.php، JSON، إلخ)
COPY . /var/www/html

# تثبيت curl (ولأي امتدادات أخرى تحتاجها)
RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

# تأكد من فتح المنفذ 80
EXPOSE 80

# يدير Apache تلقائيًا؛ لا حاجة لأمر CMD إضافي لأن ENTRYPOINT مضمّن
