FROM php:8.2-cli

WORKDIR /app

# تنصيب curl
RUN apt-get update && apt-get install -y curl

# نسخ الملفات
COPY . /app

# تثبيت Composer (اختياري لو تحتاج تحديثات)
# RUN php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" \
#     && php composer-setup.php --install-dir=/usr/local/bin --filename=composer \
#     && rm composer-setup.php

CMD ["php", "bot.php"]
