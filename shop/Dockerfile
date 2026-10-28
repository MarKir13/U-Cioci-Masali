# Shop image: official PrestaShop 8.2.8 on PHP 8.1 with Apache.
FROM prestashop/prestashop:8.2.8-8.1-apache

# PHP settings for PrestaShop
COPY config/php.ini /usr/local/etc/php/conf.d/zz-shop.ini

# Our theme and modules are kept in /opt/ciocia and copied into the shop files by sync-code.sh
# (before install and on every start), because /var/www/html lives in a volume.
COPY --chown=www-data:www-data themes/ /opt/ciocia/themes/
COPY --chown=www-data:www-data modules/ /opt/ciocia/modules/
COPY --chmod=755 scripts/sync-code.sh /tmp/pre-install-scripts/10-sync-code.sh
COPY --chmod=755 scripts/sync-code.sh /tmp/init-scripts/10-sync-code.sh

# Runs once after the automatic install: enables our child theme
COPY --chmod=755 scripts/post-install/ /tmp/post-install-scripts/
