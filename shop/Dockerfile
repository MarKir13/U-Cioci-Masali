# Shop image: official PrestaShop 8.2.8 on PHP 8.1 with Apache.
FROM prestashop/prestashop:8.2.8-8.1-apache

# PHP settings for PrestaShop
COPY config/php.ini /usr/local/etc/php/conf.d/zz-shop.ini

# Behind the HTTPS proxy: treat X-Forwarded-Proto: https as a secure request
COPY config/apache-https-proxy.conf /etc/apache2/conf-available/https-proxy.conf
RUN a2enconf https-proxy

# Our theme and modules are kept in /opt/ciocia and copied into the shop files by sync-code.sh
# (before install and on every start), because /var/www/html lives in a volume.
COPY --chown=www-data:www-data themes/ /opt/ciocia/themes/
COPY --chown=www-data:www-data modules/ /opt/ciocia/modules/
COPY --chmod=755 scripts/sync-code.sh /tmp/pre-install-scripts/10-sync-code.sh
COPY --chmod=755 scripts/sync-code.sh /tmp/init-scripts/10-sync-code.sh

# Run once after the automatic install, in name order: enable our child theme, then put our content
# into the database. The PHP setup scripts and their data stay in /opt/ciocia/setup, outside the web root.
COPY scripts/setup/ /opt/ciocia/setup/
COPY --chmod=755 scripts/post-install/ /tmp/post-install-scripts/
