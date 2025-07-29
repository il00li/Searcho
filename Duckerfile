# استخدام صورة PHP مع Apache
FROM php:8.2-apache

# نسخ ملفات المشروع إلى مجلد الاستضافة داخل الحاوية
COPY . /var/www/html/

# فتح المنفذ 80 (افتراضي لـ HTTP)
EXPOSE 80

# تثبيت Composer (اختياري إذا كنت تستخدمه)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer
