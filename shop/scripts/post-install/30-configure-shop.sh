#!/bin/sh
# Runs once, right after the automatic PrestaShop install (image hook: /tmp/post-install-scripts/).
# Sets currency, country, VAT, payments, carriers, free delivery, e-mail and invoices
# from shop/config/shop-settings.php (issue #47).
set -e
runuser -u www-data -- php /opt/ciocia/scripts/setup/configure-shop.php
