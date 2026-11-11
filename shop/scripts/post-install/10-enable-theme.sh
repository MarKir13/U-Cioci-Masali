#!/bin/sh
# Runs once, right after the automatic PrestaShop install (image hook: /tmp/post-install-scripts/).
# Switches the shop from Classic to our child theme.
set -e
cd /var/www/html
runuser -u www-data -- php bin/console prestashop:theme:enable ciocia
