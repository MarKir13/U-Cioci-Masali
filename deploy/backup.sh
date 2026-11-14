#!/bin/sh
# Backs up the running shop into one archive in deploy/backups/ (gitignored):
#   manifest.txt                    date, git commit, PrestaShop version, number of products, shop domain
#   db.sql                          the whole database (mariadb-dump, run in the db container)
#   img/                            product, category and other shop images, with their thumbnails
#   modules/ps_imageslider/images/  home banner slides, which the module keeps outside img/
#
# Not included: app/config/parameters.php. It holds the database password and cookie keys of one
# install, and the environment a backup is restored into has its own (ADR 0009).
# The archive holds customer data and password hashes: never commit or publish it.
#
# Usage, with the shop running:  sh deploy/backup.sh
# Restore it with:               sh deploy/restore.sh deploy/backups/<archive>
set -eu

# Git Bash on Windows rewrites arguments that look like Unix paths (/var/www/html becomes
# C:/Program Files/Git/var/www/html). The paths below are container paths, so switch that off.
export MSYS_NO_PATHCONV=1

deploy_dir=$(dirname "$0")
compose="$deploy_dir/compose.yaml"
name="ciocia-backup-$(date +%Y%m%d-%H%M%S)"
archive="$deploy_dir/backups/$name.tar.gz"
work="/tmp/$name" # working folder inside the shop container
started=$(date +%s)

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

if [ "$(shop_health)" != healthy ]; then
  echo "The shop is not running or is still installing. Start it and wait until it is healthy:" >&2
  echo "  docker compose -f deploy/compose.yaml up -d --wait" >&2
  exit 1
fi

# The working folder holds a full database dump, so remove it however the script ends.
cleanup() {
  docker compose -f "$compose" exec -T shop rm -rf "$work" "$work.tar.gz" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 1' INT TERM

echo "1/4 Dumping the database..."
docker compose -f "$compose" exec -T shop mkdir -p "$work"
docker compose -f "$compose" exec -T db sh -c \
  'MYSQL_PWD="$MARIADB_PASSWORD" mariadb-dump --single-transaction --quick --default-character-set=utf8mb4 -u"$MARIADB_USER" "$MARIADB_DATABASE"' |
  docker compose -f "$compose" exec -T shop sh -c 'cat > "$1/db.sql"' sh "$work"
# A pipeline reports only the status of its last command, so check that the dump reached its end.
if ! docker compose -f "$compose" exec -T shop sh -c 'tail -n 1 "$1/db.sql" | grep -q "Dump completed"' sh "$work"; then
  echo "The database dump is incomplete, see the error above." >&2
  exit 1
fi

echo "2/4 Writing the manifest..."
products=$(sql "SELECT COUNT(*) FROM ps_product")
version=$(sql "SELECT value FROM ps_configuration WHERE name = 'PS_VERSION_DB'")
domain=$(docker compose -f "$compose" exec -T shop printenv PS_DOMAIN | tr -d '\r')
commit=$(git -C "$deploy_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)
if [ -z "$products" ] || [ -z "$version" ]; then
  echo "Could not read the product count or the PrestaShop version from the database." >&2
  exit 1
fi
printf 'date=%s\ncommit=%s\nprestashop=%s\nproducts=%s\ndomain=%s\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')" "$commit" "$version" "$products" "$domain" |
  docker compose -f "$compose" exec -T shop sh -c 'cat > "$1/manifest.txt"' sh "$work"

echo "3/4 Packing the manifest, database and images..."
docker compose -f "$compose" exec -T shop tar -czf "$work.tar.gz" \
  -C "$work" manifest.txt db.sql \
  -C /var/www/html img modules/ps_imageslider/images

echo "4/4 Copying the archive out of the container..."
mkdir -p "$deploy_dir/backups"
docker compose -f "$compose" cp "shop:$work.tar.gz" "$archive"

size=$(du -h "$archive" | cut -f1)
echo "Backup written: $archive ($size, $products products, $(($(date +%s) - started)) s)"
