#!/bin/sh
# Runs once, right after the automatic PrestaShop install (image hook: /tmp/post-install-scripts/),
# after 30-configure-shop.sh. Turns on the Webservice API and sets up the importer's key from
# PS_WEBSERVICE_KEY: see shop/scripts/setup/webservice.php.
# Safe to run again on a running shop, for example after changing the key in deploy/.env and `up -d`:
#   docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/40-webservice.sh
set -e
runuser -u www-data -- php /opt/ciocia/scripts/setup/webservice.php
