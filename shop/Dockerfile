# Shop image: official PrestaShop 8.2.8 on PHP 8.1 with Apache.
FROM prestashop/prestashop:8.2.8-8.1-apache

# PHP settings for PrestaShop
COPY config/php.ini /usr/local/etc/php/conf.d/zz-shop.ini

# Child theme and our own modules, owned by the web server user
COPY --chown=www-data:www-data themes/ /var/www/html/themes/
COPY --chown=www-data:www-data modules/ /var/www/html/modules/

# Runs once after the automatic install: enables our child theme
COPY --chmod=755 scripts/post-install/ /tmp/post-install-scripts/
