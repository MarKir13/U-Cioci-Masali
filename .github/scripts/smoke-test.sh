#!/bin/sh
# Smoke test of a running shop, through the HTTPS proxy, the way a browser reaches it, and of the
# Webservice API from inside the Compose network, the way the importer reaches it.
# CI runs it after `docker compose up --wait` (job `smoke` in .github/workflows/ci.yml).
# Locally, with the shop running, from the repository root: sh .github/scripts/smoke-test.sh
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

# check_status DESCRIPTION EXPECTED GOT
check_status() {
  if [ "$3" = "$2" ]; then
    pass "$1 gives $3"
  else
    fail "$1: expected $2, got '$3'"
  fi
}

# The Webservice API is blocked at the proxy (deploy/proxy/default.conf.template), under both of its paths
for path in '/api/products' '/webservice/dispatcher.php?url=products' '/API/products'; do
  got=$(curl -ksS -o /dev/null -w '%{http_code}' "$BASE$path") || got="curl failed"
  check_status "$BASE$path (API blocked at the proxy)" 404 "$got"
done

# api_status PATH KEY: status code of an API request made the way the importer makes it, from inside
# the Compose network: plain HTTP to the shop, with the Host and X-Forwarded-Proto headers the proxy
# sends (shop/scripts/setup/webservice.php). Runs in the shop container, so KEY=env uses the container's
# own PS_WEBSERVICE_KEY and the key is never printed or read from deploy/.env.
# KEY: env, none, or a literal key. MSYS_NO_PATHCONV=1 stops Git Bash on Windows from rewriting
# /api/... into a Windows path; elsewhere it does nothing.
api_status() {
  MSYS_NO_PATHCONV=1 docker compose -f deploy/compose.yaml exec -T \
    -e API_PATH="$1" -e API_KEY="$2" -e API_HOST="localhost:$HTTPS_PORT" shop sh -c '
      case "$API_KEY" in
        env) auth="$PS_WEBSERVICE_KEY:" ;;
        none) auth="" ;;
        *) auth="$API_KEY:" ;;
      esac
      curl -sS -o /dev/null -w "%{http_code}" -H "Host: $API_HOST" -H "X-Forwarded-Proto: https" \
        ${auth:+-u "$auth"} "http://localhost$API_PATH"' || echo "request failed"
}

# Post-install/40-webservice.sh set up the key: the importer's resources are allowed, others are not
check_status "API products with the key" 200 "$(api_status /api/products env)"
check_status "API categories with the key" 200 "$(api_status /api/categories env)"
check_status "API customers with the key (not allowed)" 401 "$(api_status /api/customers env)"
check_status "API orders with the key (not allowed)" 401 "$(api_status /api/orders env)"
check_status "API products without a key" 401 "$(api_status /api/products none)"
check_status "API products with a wrong key" 401 "$(api_status /api/products WRONGKEYWRONGKEYWRONGKEYWRONGKEY)"

# The key is the Basic auth user, which standard access logs write down (shop/config/apache-access-log.conf,
# log_format noauth in the proxy). After the requests above, and one with the key through the proxy, neither
# log may contain it. The key stays in a variable and is never printed.
key=$(MSYS_NO_PATHCONV=1 docker compose -f deploy/compose.yaml exec -T shop printenv PS_WEBSERVICE_KEY) || key=""
if [ -z "$key" ]; then
  fail "Could not read PS_WEBSERVICE_KEY from the shop container"
else
  # Through a variable: gitleaks (rule curl-auth-user) reports `curl -u "...:"` written out, even with a variable
  auth="$key:"
  curl -ksS -o /dev/null -u "$auth" "$BASE/api/products" || true
  if docker compose -f deploy/compose.yaml logs --no-color shop proxy 2>&1 | grep -qF "$key"; then
    fail "The API key appears in the shop or proxy log"
  else
    pass "The API key appears in no shop or proxy log"
  fi
fi

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "All checks passed"
