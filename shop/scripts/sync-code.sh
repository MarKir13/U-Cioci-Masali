#!/bin/sh
# Copies our theme and modules from the image (/opt/ciocia) into the shop files.
# The shop files live in a volume that is filled from the image only once, so without this
# a rebuilt image would never update them. Runs before the first install and on every start.
set -e
for dir in /opt/ciocia/themes/* /opt/ciocia/modules/*; do
  [ -d "$dir" ] || continue
  target="/var/www/html/${dir#/opt/ciocia/}"
  rm -rf "$target"
  cp -a "$dir" "$target"
done
