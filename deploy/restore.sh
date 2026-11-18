#!/bin/sh
# Restores a backup made by deploy/backup.sh into the running shop. It REPLACES the shop's
# database and images, so it asks for confirmation first (AGENTS.md, rule 10).
#
# Usage, with the shop running and healthy (a fresh install after `down -v` is fine):
#   sh deploy/restore.sh deploy/backups/<archive>          asks before it changes anything
#   sh deploy/restore.sh --yes deploy/backups/<archive>    no question: for scripts and timed runs
# In Git Bash give the archive as a relative path or as D:/..., not as /d/... (MSYS_NO_PATHCONV).
#
# The shop keeps this environment's own app/config/parameters.php (database password, cookie
# keys) and .htaccess; neither is in the backup (ADR 0009). Everything in the database comes from
# the backup, including the admin account: log in to the back office with the e-mail and password
# of the backed-up shop, not with ADMIN_MAIL and ADMIN_PASSWORD of this environment.
set -eu

# Git Bash on Windows rewrites arguments that look like Unix paths (/var/www/html becomes
# C:/Program Files/Git/var/www/html). The paths below are container paths, so switch that off.
export MSYS_NO_PATHCONV=1

deploy_dir=$(dirname "$0")
compose="$deploy_dir/compose.yaml"
work=/tmp/ciocia-restore # working folder inside the shop container

usage() {
  echo "Usage: sh deploy/restore.sh [--yes] deploy/backups/<archive>.tar.gz" >&2
  exit 2
}

# sql QUERY: runs one statement in the db container and prints the bare result. The user, password
# and database name come from that container's own environment, so they are never written or
# printed here.
sql() {
  docker compose -f "$compose" exec -T db sh -c \
    'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -N -B -u"$MARIADB_USER" "$MARIADB_DATABASE" -e "$1"' sh "$1" |
    tr -d '\r'
}

# Prints the shop container's health: "healthy" once Apache answers, which is after the install
# and our setup scripts have finished.
shop_health() {
  id=$(docker compose -f "$compose" ps -q shop)
  if [ -n "$id" ]; then
    docker inspect --format '{{.State.Health.Status}}' "$id"
  fi
}

# value KEY: one value from the backup's manifest.txt (lines of key=value)
value() {
  printf '%s\n' "$manifest" | sed -n "s/^$1=//p"
}

confirmed=no
archive=
for arg in "$@"; do
  case "$arg" in
    --yes) confirmed=yes ;;
    -*) usage ;;
    *)
      [ -z "$archive" ] || usage
      archive=$arg
      ;;
  esac
done
[ -n "$archive" ] || usage

if [ ! -f "$archive" ]; then
  echo "No such file: $archive" >&2
  exit 1
fi

if [ "$(shop_health)" != healthy ]; then
  echo "The shop is not running or is still installing. Start it and wait until it is healthy:" >&2
  echo "  docker compose -f deploy/compose.yaml up -d --wait" >&2
  exit 1
fi

if [ "$confirmed" != yes ]; then
  if [ ! -t 0 ]; then
    echo "Not restoring without confirmation. Run it in a terminal or pass --yes." >&2
    exit 1
  fi
  echo "This REPLACES the database and images of the running shop with the contents of:"
  echo "  $archive"
  printf 'Type "yes" to continue: '
  read -r answer
  if [ "$answer" != yes ]; then
    echo "Cancelled, nothing was changed."
    exit 1
  fi
fi

started=$(date +%s)

# The working folder holds a full database dump, so remove it however the script ends.
cleanup() {
  docker compose -f "$compose" exec -T shop rm -rf "$work" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 1' INT TERM

echo "1/5 Copying the archive into the shop container..."
docker compose -f "$compose" exec -T shop sh -c 'rm -rf "$1" && mkdir -p "$1"' sh "$work"
docker compose -f "$compose" cp "$archive" "shop:$work/backup.tar.gz"
if ! docker compose -f "$compose" exec -T shop tar -xzf "$work/backup.tar.gz" -C "$work" manifest.txt db.sql; then
  echo "$archive is not a backup made by deploy/backup.sh." >&2
  exit 1
fi
manifest=$(docker compose -f "$compose" exec -T shop cat "$work/manifest.txt" | tr -d '\r')
echo "    Backup of $(value date): $(value products) products, PrestaShop $(value prestashop), from $(value domain)"
commit=$(git -C "$deploy_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)
if [ "$(value commit)" != "$commit" ]; then
  echo "    Note: the backup was made at commit $(value commit), this checkout is at $commit."
fi

echo "2/5 Loading the database..."
# Start from an empty database, so no table of the current install is left next to the backup's.
docker compose -f "$compose" exec -T db sh -c \
  'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -u"$MARIADB_USER" -e "DROP DATABASE IF EXISTS \`$MARIADB_DATABASE\`; CREATE DATABASE \`$MARIADB_DATABASE\`"'
docker compose -f "$compose" exec -T shop cat "$work/db.sql" |
  docker compose -f "$compose" exec -T db sh -c \
    'MYSQL_PWD="$MARIADB_PASSWORD" mariadb --default-character-set=utf8mb4 -u"$MARIADB_USER" "$MARIADB_DATABASE"'
# A pipeline reports only the status of its last command, so check that the whole dump arrived.
loaded=$(sql "SELECT COUNT(*) FROM ps_product")
if [ "$loaded" != "$(value products)" ]; then
  echo "The database has '$loaded' products, the backup has $(value products): the load failed." >&2
  exit 1
fi

echo "3/5 Restoring the images..."
docker compose -f "$compose" exec -T shop sh -c '
  rm -rf /var/www/html/img /var/www/html/modules/ps_imageslider/images &&
  tar -xzf "$1/backup.tar.gz" -C /var/www/html img modules/ps_imageslider/images' sh "$work"

echo "4/5 Setting the shop domain..."
# The backup may come from a shop on another port or host. PS_DOMAIN of the running shop
# container is "localhost:<HTTPS_PORT>" (compose.yaml); PrestaShop redirects any other host to it.
domain=$(docker compose -f "$compose" exec -T shop printenv PS_DOMAIN | tr -d '\r')
if [ -z "$domain" ]; then
  echo "Could not read PS_DOMAIN from the shop container." >&2
  exit 1
fi
sql "UPDATE ps_shop_url SET domain = '$domain', domain_ssl = '$domain'"
sql "UPDATE ps_configuration SET value = '$domain' WHERE name IN ('PS_SHOP_DOMAIN', 'PS_SHOP_DOMAIN_SSL')"

echo "5/5 Restarting the shop and the proxy..."
# Every start of the shop container deletes PrestaShop's cache (shop/scripts/sync-code.sh), so the
# restart also clears whatever was cached from the old database.
cleanup
docker compose -f "$compose" restart shop
docker compose -f "$compose" restart proxy
tries=0
until [ "$(shop_health)" = healthy ]; do
  tries=$((tries + 1))
  if [ "$tries" -gt 150 ]; then
    echo "The shop is not healthy after 5 minutes: docker compose -f deploy/compose.yaml logs shop" >&2
    exit 1
  fi
  sleep 2
done

echo "Restore finished in $(($(date +%s) - started)) s: $loaded products, https://$domain"
