#!/bin/sh
# Lighthouse on desktop against the running shop, as the lecturer measures it: Performance of the home page
# (W3, at least 60) and Accessibility (D1, at least 85). Performance varies from run to run, so the home page is
# measured 3 times and the middle score counts. Accessibility barely varies; it is taken from the first home run
# and from one run on a category page and one on a product page.
# Each score becomes a row of the acceptance table (.github/scripts/acceptance-results.sh). The HTML reports are in
# tests/acceptance-report/lighthouse/ (gitignored); open one in a browser to see what lowered a score.
# From the repository root, with the shop running, after the E2E setup in tests/ (Git Bash, Linux, macOS):
#   sh .github/scripts/lighthouse.sh
# BASE_URL: the shop, as for the E2E tests (default https://localhost:8443).
set -eu

# Exact version, so every run measures the same way. npx downloads it on first use.
VERSION=13.6.0
BASE_URL=${BASE_URL:-https://localhost:8443}
OUT=tests/acceptance-report/lighthouse
RUNS=3

if [ ! -f deploy/compose.yaml ]; then
  echo "Run this from the repository root" >&2
  exit 2
fi
rm -rf "$OUT"
mkdir -p "$OUT"

# The browser: the Chromium of the E2E tests (npx playwright install chromium in tests/), the version pinned by
# tests/package-lock.json, so a run measures with the same browser on every machine. CHROME_PATH chooses another.
if [ -z "${CHROME_PATH:-}" ]; then
  # executablePath() gives the path where Playwright puts its Chromium, also when it was never installed, so the
  # file itself is checked too
  CHROME_PATH=$(cd tests && node -e 'import("@playwright/test").then((m) => console.log(m.chromium.executablePath()))') || CHROME_PATH=
  if [ -z "$CHROME_PATH" ] || [ ! -x "$CHROME_PATH" ]; then
    echo "No Playwright Chromium: run npm ci and npx playwright install chromium in tests/ first" >&2
    exit 2
  fi
  export CHROME_PATH
fi

# lighthouse NAME URL: one run, written to $OUT/NAME.report.html and $OUT/NAME.report.json.
# --ignore-certificate-errors: the shop's certificate is self-signed (ADR 0002).
# --blocked-url-patterns: imported descriptions can embed images from the source shop, which tests never touch
# (AGENTS.md rule 7).
lighthouse() {
  npx --yes "lighthouse@$VERSION" "$2" \
    --preset=desktop \
    --only-categories=performance,accessibility \
    --output=html --output=json --output-path="$OUT/$1" \
    --chrome-flags="--headless=new --ignore-certificate-errors" \
    --blocked-url-patterns="*magiczne-indie.pl*" \
    --quiet
}

# score NAME CATEGORY: the score from 0 to 100, or "no report" when the run failed (which fails its row).
# Lighthouse gives 0 to 1, or null when it could not measure the page.
score() {
  if [ -f "$OUT/$1.report.json" ]; then
    node -e '
      const report = JSON.parse(require("node:fs").readFileSync(process.argv[1], "utf8"));
      const score = report.categories[process.argv[2]].score;
      console.log(score === null ? "no score" : Math.round(score * 100));
    ' "$OUT/$1.report.json" "$2"
  else
    echo "no report"
  fi
}

# The first category and the first product the home page links to, in page order: a top-menu category, and a
# product of the home page's list. Categories are /<id>-<name>, products /<category>/<id>-<name>.html.
# A shop that does not answer gives no links: those pages are then skipped and their rows fail, instead of set -e
# ending the script here with no rows at all.
home=$(curl -fsSk "$BASE_URL/") || home=
links=$(printf '%s\n' "$home" | grep -o "href=\"$BASE_URL/[^\"]*\"" | sed 's/^href="//; s/"$//')
category=$(printf '%s\n' "$links" | grep -E "^$BASE_URL/[0-9]+-[^/]+$" | head -1 || true)
product=$(printf '%s\n' "$links" | grep -E "^$BASE_URL/[^/]+/[0-9]+-[^/]+\.html$" | head -1 || true)

# run NAME URL: one run; a failed one leaves no report, which its row shows, and the next runs still go
run() {
  if [ -z "$2" ]; then
    echo "No link for the $1 page on the home page" >&2
    return
  fi
  echo "=== Lighthouse: $1, $2"
  lighthouse "$1" "$2" || echo "Lighthouse failed: $1, $2" >&2
}

i=1
while [ "$i" -le "$RUNS" ]; do
  run "home-$i" "$BASE_URL/"
  i=$((i + 1))
done
run category "$category"
run product "$product"

# The middle of the 3 home page scores. Only when all 3 runs gave a score: a failed run would sort as 0 and
# pass the lower of the other two as the middle one.
scores=$(i=1; while [ "$i" -le "$RUNS" ]; do score "home-$i" performance; i=$((i + 1)); done)
if [ "$(printf '%s\n' "$scores" | grep -cE '^[0-9]+$')" -eq "$RUNS" ]; then
  performance=$(printf '%s\n' "$scores" | sort -n | sed -n "$(((RUNS + 1) / 2))p")
else
  performance="not every run gave a score"
fi
echo "Performance scores of the home page: $(echo "$scores" | tr '\n' ' ')"

# record NAME VALUE MIN: adds the row; remembers a failed one, so the script exits 1 and its CI step shows red.
# Anything but "pass:" counts as failed: a row that add rejected (exit 2) prints nothing here. `|| true` keeps
# set -e from ending the script there, so the other rows are still written.
failed=0
record() {
  line=$(sh .github/scripts/acceptance-results.sh add "$1" "$2" "$3" -) || true
  echo "$line"
  case "$line" in
    pass:*) ;;
    *) failed=1 ;;
  esac
}
record "Lighthouse Performance, home page, desktop (middle of $RUNS)" "$performance" 60
record "Lighthouse Accessibility, home page" "$(score home-1 accessibility)" 85
record "Lighthouse Accessibility, category page" "$(score category accessibility)" 85
record "Lighthouse Accessibility, product page" "$(score product accessibility)" 85
exit "$failed"
