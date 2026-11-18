#!/bin/sh
# Copies our theme and modules from the image (/opt/ciocia) into the shop files.
# The shop files live in a volume that is filled from the image only once, so without this
# a rebuilt image would never update them. Runs before the first install and on every start.
#
# It then deletes PrestaShop's cache. The cache keeps resolved template paths and lives in the same
# volume, so without this a new module template override (themes/ciocia/modules/...) is ignored
# until the cache is cleared by hand. Nothing serves requests yet, and PrestaShop rebuilds the cache
# on the first request. Only delete: folders created here would belong to root, not www-data.
set -e
for dir in /opt/ciocia/themes/* /opt/ciocia/modules/*; do
  [ -d "$dir" ] || continue
  target="/var/www/html/${dir#/opt/ciocia/}"
  rm -rf "$target"
  cp -a "$dir" "$target"
done
rm -rf /var/www/html/var/cache/prod /var/www/html/var/cache/dev
# PrestaShop's HTML cleaner (HTMLPurifier) keeps its cache in var/cache/prod/purifier and never creates that
# folder itself. Without it every product saved through the Webservice API fails with HTTP 500 (a PHP warning),
# although the product is saved. Created as www-data, so the folders do not belong to root.
runuser -u www-data -- mkdir -p /var/www/html/var/cache/prod/purifier
