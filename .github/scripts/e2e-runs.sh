#!/bin/sh
# Runs the E2E suite (`npm test` in tests/) several times in a row against a running shop with its data, the way
# W4 counts stability: 3 passes of 3 runs. Each run gets its own seed, so each one picks other products.
# CI runs it in .github/workflows/e2e.yml. Locally, from the repository root, after `npm ci` and
# `npx playwright install chromium` in tests/ (Git Bash, Linux, macOS):
#   sh .github/scripts/e2e-runs.sh 3
# BASE_URL, MAILPIT_URL and the other E2E_* variables reach the tests unchanged (see README, E2E tests). With
# E2E_SEED set, every run uses that seed.
# Every run starts with an empty tests/test-results/ and a new tests/playwright-report/, so after each run both are
# moved to tests/e2e-runs/run-<n>/ (gitignored), which keeps the reports of all runs. Open one from tests/ with
#   npx playwright show-report e2e-runs/run-2/playwright-report
# Prints a table (run, seed, result, time), also to the job summary in GitHub Actions. Exits 1 if any run failed
# or took longer than MAX_SECONDS.
set -eu

# W4: the whole run within 5 minutes. Playwright already stops a run after 4 (globalTimeout in
# tests/playwright.config.js); this also catches a run that was slow before the tests started.
MAX_SECONDS=300
OUT=tests/e2e-runs

usage() {
  echo "Usage: sh .github/scripts/e2e-runs.sh [number of runs, default 3]" >&2
  exit 2
}

# An empty argument counts as none (`:-`), so it gives 3 too
runs=${1:-3}
# Only digits, and at least 1. Without the second check, "00" or a number too large for `[` would end the
# loop below before the first run and exit 0, with nothing tested. `[` fails on such a number
# ("Illegal number"), so 2>/dev/null hides its message and `||` gives the usage.
case "$runs" in
  *[!0-9]*) usage ;;
esac
[ "$runs" -ge 1 ] 2>/dev/null || usage

if [ ! -f tests/playwright.config.js ]; then
  echo "Run this from the repository root" >&2
  exit 2
fi

# Reports of an earlier call would mix with this one's
rm -rf "$OUT"
mkdir -p "$OUT"

table="| Run | Seed | Result | Time |
|---|---|---|---|"
bad=0
i=1
while [ "$i" -le "$runs" ]; do
  # A whole number below 2^31, like the seeds playwright.config.js draws itself. POSIX sh has no $RANDOM.
  seed=${E2E_SEED:-$(($(od -An -N4 -tu4 /dev/urandom) % 2147483648))}
  echo "=== E2E run $i of $runs, seed $seed"

  started=$(date +%s)
  # `if` keeps `set -e` from stopping the script at a failed run: the next runs still go, so the table shows
  # how many of them pass
  if (cd tests && E2E_SEED="$seed" npm test); then
    result=passed
  else
    result=failed
  fi
  seconds=$(($(date +%s) - started))

  if [ "$result" = passed ] && [ "$seconds" -gt "$MAX_SECONDS" ]; then
    result="passed, over $MAX_SECONDS s"
  fi
  if [ "$result" != passed ]; then
    bad=$((bad + 1))
  fi

  # Missing only if Playwright stopped before it wrote anything, for example on a wrong setting. A failed move
  # (on Windows, a file still held open, for example by a virus scanner) loses only that run's report, so it is
  # a warning: under `set -e` it would end the script before the table.
  mkdir -p "$OUT/run-$i"
  for dir in tests/playwright-report tests/test-results; do
    if [ -d "$dir" ]; then
      mv "$dir" "$OUT/run-$i/" || echo "Warning: could not move $dir to $OUT/run-$i/" >&2
    fi
  done

  table="$table
| $i | $seed | $result | $seconds s |"
  i=$((i + 1))
done

passed=$((runs - bad))
# `e2e-reports` is the artifact name in .github/workflows/e2e.yml: change both together
summary="## E2E: $passed of $runs runs passed

$table

Reports of every run: \`tests/e2e-runs/run-<n>/\` (in CI, the \`e2e-reports\` artifact of this run). To repeat a
run with the same products: \`E2E_SEED=<seed> npm test\` in \`tests/\`."

echo
echo "$summary"
# Set by GitHub Actions: Markdown appended to this file is shown on the run's summary page
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "$summary" >> "$GITHUB_STEP_SUMMARY"
fi

[ "$bad" -eq 0 ]
