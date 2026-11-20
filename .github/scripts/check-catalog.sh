#!/bin/sh
# The catalogue numbers the lecturer checks (W3) and the extras D3 asks for, read with SQL from the database of the
# running shop. Prints one line per check, "name<TAB>value", so two runs can be compared (acceptance.yml does that
# before the backup and after the restore). With --record each line also becomes a row of the acceptance table
# (.github/scripts/acceptance-results.sh), with its limit.
# From the repository root, with the shop running (Git Bash, Linux, macOS):
#   sh .github/scripts/check-catalog.sh [--record]
#
# What counts: only active products and categories, since inactive ones are not in the shop's pages. A category is
# non-empty when an active product is in it or in any category below it. PrestaShop stores the tree as nested sets:
# category D is below category C (or is C) when C.nleft <= D.nleft <= C.nright.
set -eu

compose=deploy/compose.yaml
record=no
case "${1:-}" in
  --record) record=yes ;;
  "") ;;
  *)
    echo "Usage: sh .github/scripts/check-catalog.sh [--record]" >&2
    exit 2
    ;;
esac

if [ ! -f "$compose" ]; then
  echo "Run this from the repository root" >&2
  exit 2
fi

# sql QUERY: one statement in the db container, its bare result. User, password and database come from that
# container's own environment, so they are never written or printed here (as in deploy/backup.sh).
sql() {
  docker compose -f "$compose" exec -T db sh -c \
    'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -N -B -u"$MARIADB_USER" "$MARIADB_DATABASE" -e "$1"' sh "$1" |
    tr -d '\r'
}

# check NAME MIN MAX QUERY: prints the value, and with --record adds the row (MIN, MAX as in acceptance-results.sh).
# A failed row is remembered, so with --record the script exits 1 and its CI step shows red. Anything but "pass:"
# counts as failed: a row that add rejected (exit 2, for example a value of two lines) prints nothing here.
failed=0
check() {
  value=$(sql "$4")
  printf '%s\t%s\n' "$1" "$value"
  if [ "$record" = yes ]; then
    case "$(sh .github/scripts/acceptance-results.sh add "$1" "$value" "$2" "$3")" in
      pass:*) ;;
      *) failed=1 ;;
    esac
  fi
}

# Categories that hold at least one active product, themselves or below them
NON_EMPTY="EXISTS (
  SELECT 1 FROM ps_category d
  JOIN ps_category_product cp ON cp.id_category = d.id_category
  JOIN ps_product p ON p.id_product = cp.id_product AND p.active = 1
  WHERE d.active = 1 AND d.nleft BETWEEN c.nleft AND c.nright)"
# The shop's home category ("Strona główna"), the parent of the top-level categories
HOME="(SELECT id_category FROM ps_category WHERE is_root_category = 1)"
# The stock of a product itself; its combinations have their own rows with id_product_attribute > 0
PRODUCT_STOCK="ps_stock_available sa ON sa.id_product = p.id_product AND sa.id_product_attribute = 0"

# W3: at least 1000 products
check "Active products" 1000 - \
  "SELECT COUNT(*) FROM ps_product WHERE active = 1"

# W3: at least 4 categories, each with at least 2 non-empty subcategories
check "Top-level categories with 2 or more non-empty subcategories" 4 - \
  "SELECT COUNT(*) FROM (
     SELECT t.id_category FROM ps_category t
     JOIN ps_category c ON c.id_parent = t.id_category AND c.active = 1
     WHERE t.active = 1 AND t.id_parent IN $HOME AND $NON_EMPTY
     GROUP BY t.id_category HAVING COUNT(*) >= 2) AS top_categories"

# W3: 0 empty categories. Every active category below the home category, at any depth.
check "Empty categories" 0 0 \
  "SELECT COUNT(*) FROM ps_category c WHERE c.active = 1 AND c.level_depth >= 2 AND NOT $NON_EMPTY"

# W3: 5-20% of the products have stock 0. Not rounded, so 4.96% does not become a pass as 5.0; MariaDB prints
# 4 decimal places.
check "Out-of-stock products (%)" 5 20 \
  "SELECT 100 * SUM(sa.quantity <= 0) / COUNT(*)
   FROM ps_product p JOIN $PRODUCT_STOCK WHERE p.active = 1"

# W3: stock from 0 to 10 for every product and every variant (combination)
check "Highest stock of a product or variant" - 10 \
  "SELECT MAX(quantity) FROM ps_stock_available"
check "Lowest stock of a product or variant" 0 - \
  "SELECT MIN(quantity) FROM ps_stock_available"

# W2/W3: at least 1 image per product, and at least 2 for 50 products
check "Active products without an image" 0 0 \
  "SELECT COUNT(*) FROM ps_product p
   WHERE p.active = 1 AND NOT EXISTS (SELECT 1 FROM ps_image i WHERE i.id_product = p.id_product)"
check "Active products with 2 or more images" 50 - \
  "SELECT COUNT(*) FROM ps_product p
   WHERE p.active = 1 AND (SELECT COUNT(*) FROM ps_image i WHERE i.id_product = p.id_product) >= 2"

# W3: 0 responses 4xx over the shop's pages. A video player from a source description asks for a file in the
# source shop's /img/cms/ that our shop does not have (404); the importer leaves them out (mapping.without_videos).
# Checked here over the whole catalogue, since the acceptance crawl may never open one of those products.
check "Product descriptions with a video" 0 0 \
  "SELECT COUNT(DISTINCT id_product) FROM ps_product_lang WHERE description LIKE '%<video%'"

# D3: at least 20 products with a price promotion that applies now: a reduction for every customer, with no end
# date or one still to come. 0000-00-00 is PrestaShop's "no date".
check "Active products with a current promotion" 20 - \
  "SELECT COUNT(DISTINCT p.id_product) FROM ps_product p
   JOIN ps_specific_price sp ON sp.id_product = p.id_product
   WHERE p.active = 1 AND sp.reduction > 0 AND sp.id_customer = 0 AND sp.id_group = 0
     AND (sp.\`from\` = '0000-00-00 00:00:00' OR sp.\`from\` <= NOW())
     AND (sp.\`to\` = '0000-00-00 00:00:00' OR sp.\`to\` >= NOW())"

# D3: at least 5 products with at least 2 variants; each variant has its own stock row
check "Active products with 2 or more variants" 5 - \
  "SELECT COUNT(*) FROM (
     SELECT pa.id_product FROM ps_product_attribute pa
     JOIN ps_product p ON p.id_product = pa.id_product AND p.active = 1
     JOIN ps_stock_available sa ON sa.id_product_attribute = pa.id_product_attribute
     GROUP BY pa.id_product HAVING COUNT(*) >= 2) AS with_variants"

# Without --record nothing is judged, so the comparison after a restore never stops here
exit "$failed"
