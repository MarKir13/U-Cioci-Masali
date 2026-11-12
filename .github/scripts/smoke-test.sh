#!/bin/sh
# Smoke test of a running shop, through the HTTPS proxy, the way a browser reaches it.
# CI runs it after `docker compose up --wait` (job `smoke` in .github/workflows/ci.yml).
# Locally, with the shop running: sh .github/scripts/smoke-test.sh
# Ports come from HTTP_PORT and HTTPS_PORT, as in deploy/.env (default 8080 and 8443).
# Reports every check, then exits 1 if any failed.
set -eu

HTTP_PORT=${HTTP_PORT:-8080}
HTTPS_PORT=${HTTPS_PORT:-8443}
BASE="https://localhost:$HTTPS_PORT"

failures=0
pass() { echo "OK    $1"; }
fail() {
  echo "FAIL  $1"
  failures=$((failures + 1))
}

# check_redirect URL CODE TARGET: the status code and where it redirects, without following it.
# -k accepts our self-signed certificate.
check_redirect() {
  got=$(curl -ksS -o /dev/null -w '%{http_code} %{redirect_url}' "$1") || got="curl failed"
  if [ "$got" = "$2 $3" ]; then
    pass "$1 gives $got"
  else
    fail "$1: expected '$2 $3', got '$got'"
  fi
}

# check_page FILE PATTERN DESCRIPTION: the saved page contains PATTERN (extended regex)
check_page() {
  if grep -qE "$2" "$1"; then
    pass "$3"
  else
    fail "$3: '$2' not found in the page"
  fi
}

# W3: HTTP answers 301 to HTTPS and keeps the published port (ADR 0002)
check_redirect "http://localhost:$HTTP_PORT/" 301 "$BASE/"

# The home page: TLS works, the proxy reaches the shop and PrestaShop renders the page.
# With one language installed, PrestaShop puts no language prefix such as /pl/ in its URLs.
page=$(mktemp)
trap 'rm -f "$page"' EXIT
got=$(curl -ksS -o "$page" -w '%{http_code} %{content_type}' "$BASE/") || got="curl failed"
case "$got" in
  "200 text/html; charset=utf-8") pass "$BASE/ gives $got" ;;
  *) fail "$BASE/: expected '200 text/html; charset=utf-8', got '$got'" ;;
esac

check_page "$page" 'lang="pl-PL"' "Storefront is in Polish"
# Files of the child theme are linked: post-install/10-enable-theme.sh made ciocia active
check_page "$page" '/themes/ciocia/' "Theme ciocia is active"
# The header shows the free delivery threshold from the shop configuration, and 0 without it:
# post-install/30-configure-shop.sh ran. The pattern takes any amount, so changing it in
# shop/config/shop-settings.php does not break this check. "ł" also checks the UTF-8 encoding.
check_page "$page" 'Dostawa od [1-9][0-9]* zł gratis' "Shop configuration applied (free delivery threshold)"

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "All checks passed"
