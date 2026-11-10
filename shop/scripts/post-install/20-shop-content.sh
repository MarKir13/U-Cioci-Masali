#!/bin/sh
# Runs once, right after the automatic PrestaShop install (image hook: /tmp/post-install-scripts/),
# after 10-enable-theme.sh. Puts our content into the database: see shop/scripts/setup/shop-content.php.
# Safe to run again on a running shop, for example after changing the content and rebuilding:
#   docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/20-shop-content.sh
set -e
runuser -u www-data -- php /opt/ciocia/setup/shop-content.php
