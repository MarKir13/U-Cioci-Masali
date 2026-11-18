#!/bin/sh
# The pass/fail table of the acceptance run (.github/workflows/acceptance.yml): every check adds one row with its
# measured value and its allowed range, and the last step prints the table and fails if any row failed.
#
#   sh .github/scripts/acceptance-results.sh add NAME VALUE MIN MAX
#     MIN and MAX: the allowed range, both included; "-" for no limit on that side. For example
#       add "Active products" 2159 1000 -
#       add "Clean start to a shop with data (s)" 1312 - 900
#       add "Out-of-stock products (%)" 9.6 5 20
#       add "Duplicates after a second init" 0 0 0
#     A VALUE that is not a number (for example "did not finish") fails the row.
#   sh .github/scripts/acceptance-results.sh report
#     Prints the table, also to the job summary in GitHub Actions. Exits 1 if any row failed or there is none.
#
# The rows are kept in $ACCEPTANCE_RESULTS, by default acceptance-results.tsv in $RUNNER_TEMP (GitHub Actions) or
# /tmp. Delete that file to start a new table.
set -eu

FILE=${ACCEPTANCE_RESULTS:-${RUNNER_TEMP:-/tmp}/acceptance-results.tsv}
TAB=$(printf '\t')
# A newline; $(...) would strip it, so it is written out inside the quotes
NL='
'

usage() {
  echo "Usage: sh .github/scripts/acceptance-results.sh add NAME VALUE MIN MAX" >&2
  echo "       sh .github/scripts/acceptance-results.sh report" >&2
  exit 2
}

# is_limit X: a number (whole or with a decimal point, may be negative) or "-"
is_limit() {
  [ "$1" = "-" ] || echo "$1" | grep -Eq '^-?[0-9]+(\.[0-9]+)?$'
}

add() {
  [ "$#" -eq 4 ] || usage
  name=$1 value=$2 min=$3 max=$4
  if ! is_limit "$min" || ! is_limit "$max"; then
    usage
  fi
  # One row per line, fields separated by tabs: a tab inside a field would shift the columns, and a newline would
  # start a broken row that report would not see as failed (for example a query that returned two lines)
  case "$name$value" in
    *"$TAB"* | *"$NL"*) usage ;;
  esac

  # awk compares as numbers (sh `[` knows only whole numbers). +0 turns the text into a number.
  result=$(awk -v v="$value" -v min="$min" -v max="$max" 'BEGIN {
    if (v !~ /^-?[0-9]+(\.[0-9]+)?$/) result = "fail"
    else if (min != "-" && v + 0 < min + 0) result = "fail"
    else if (max != "-" && v + 0 > max + 0) result = "fail"
    else result = "pass"
    print result
  }')

  # The limit as a reader expects it: "= 0", ">= 1000", "<= 900", "5 to 20", or "none" for a number shown only
  # for information (it still fails when it is not a number, for example when its step did not finish)
  if [ "$min" = "-" ] && [ "$max" = "-" ]; then
    limit=none
  elif [ "$min" = "$max" ]; then
    limit="= $min"
  elif [ "$max" = "-" ]; then
    limit=">= $min"
  elif [ "$min" = "-" ]; then
    limit="<= $max"
  else
    limit="$min to $max"
  fi

  printf '%s\t%s\t%s\t%s\n' "$name" "$value" "$limit" "$result" >>"$FILE"
  echo "$result: $name = $value (limit: $limit)"
}

report() {
  [ "$#" -eq 0 ] || usage
  if [ ! -s "$FILE" ]; then
    echo "No results in $FILE: no check recorded anything" >&2
    exit 1
  fi
  total=$(wc -l <"$FILE" | tr -d ' ')
  failed=$(awk -F '\t' '$4 == "fail"' "$FILE" | wc -l | tr -d ' ')

  table="## Acceptance: $((total - failed)) of $total checks passed

| Check | Value | Limit | Result |
|---|---|---|---|
$(awk -F '\t' '{ printf "| %s | %s | %s | %s |\n", $1, $2, $3, ($4 == "fail" ? "**fail**" : "pass") }' "$FILE")"

  echo "$table"
  # Set by GitHub Actions: Markdown appended to this file is shown on the run's summary page
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    echo "$table" >>"$GITHUB_STEP_SUMMARY"
  fi
  [ "$failed" -eq 0 ]
}

command=${1:-}
if [ "$#" -gt 0 ]; then
  shift
fi
case "$command" in
  add) add "$@" ;;
  report) report "$@" ;;
  *) usage ;;
esac
