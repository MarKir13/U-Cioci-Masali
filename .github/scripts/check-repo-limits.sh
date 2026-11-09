#!/bin/sh
# Checks the repository against the size and content limits the lecturer measures (W1):
# no file over 10 MB in history, packed size up to 200 MB, at most 20 sample images
# in scraper-results/, and no .env files, private keys or certificates ever committed.
#
# Usage, from anywhere inside the repository:
#   sh .github/scripts/check-repo-limits.sh          history of HEAD (CI on a pull request)
#   sh .github/scripts/check-repo-limits.sh --all    every branch and tag (nightly scan)
# Any other arguments are passed to `git rev-list` and `git log` as the history to check.
#
# Prints one line per check and exits with 1 if any check failed.
set -eu

# Limits in MB except MAX_RESULT_IMAGES which is count of objects. Decimals are allowed, e.g. MAX_BLOB_MB=0.5
MAX_BLOB_MB=10
MAX_PACK_MB=200
MAX_RESULT_IMAGES=20

if [ "$#" -eq 0 ]; then
  set -- HEAD
fi

cd "$(git rev-parse --show-toplevel)"

failed=0
ok() { echo "OK    $1"; }
fail() {
  echo "FAIL  $1"
  failed=1
}

echo "Repository limits, history checked: $*"

# Stop on a mistyped argument. In the pipelines below, a git error would not stop the script,
# and the checks would report OK on an empty history.
git rev-list --quiet "$@"

# 1. No file over MAX_BLOB_MB in any commit of the checked history.
#    Each line: <type> <size in bytes> <path>
blobs=$(git rev-list --objects "$@" |
  git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' |
  awk '$1 == "blob"')
too_large=$(printf '%s\n' "$blobs" | awk -v max="$MAX_BLOB_MB" '
  $2 > max * 1048576 {
    size = $2
    sub(/^[^ ]+ [^ ]+ /, "")
    printf "        %.2f MB  %s\n", size / 1048576, $0
  }')
largest=$(printf '%s\n' "$blobs" | awk '$2 > max { max = $2 } END { printf "%.2f", max / 1048576 }')
if [ -z "$too_large" ]; then
  ok "largest file in history: $largest MB (limit $MAX_BLOB_MB MB)"
else
  fail "files over $MAX_BLOB_MB MB in history:"
  echo "$too_large"
fi

# 2. Packed size of the whole local repository, loose objects included.
#    `git count-objects -v` reports both sizes in KiB.
repo_mb=$(git count-objects -v | awk '$1 == "size:" || $1 == "size-pack:" { kib += $2 } END { printf "%.1f", kib / 1024 }')
if awk -v size="$repo_mb" -v max="$MAX_PACK_MB" 'BEGIN { exit !(size <= max) }'; then
  ok "repository size: $repo_mb MB (limit $MAX_PACK_MB MB)"
else
  fail "repository size: $repo_mb MB (limit $MAX_PACK_MB MB)"
fi

# 3. Only sample images in scraper-results/. The full set goes to GitHub Releases.
images=$(git ls-files -- scraper-results/ | grep -ciE '\.(jpe?g|png|webp|gif)$' || true)
if [ "$images" -le "$MAX_RESULT_IMAGES" ]; then
  ok "images in scraper-results/: $images (limit $MAX_RESULT_IMAGES)"
else
  fail "images in scraper-results/: $images (limit $MAX_RESULT_IMAGES)"
fi

# 4. No .env file, private key or certificate added in any commit of the checked history.
#    Only .env.example may be committed. --no-renames lists a file renamed to .env as added.
forbidden=$(git log --format= --name-only --diff-filter=A --no-renames "$@" |
  sort -u |
  grep -E '(^|/)\.env(\.[^/]*)?$|\.(key|pem|crt)$' |
  grep -vE '(^|/)\.env\.example$' || true)
if [ -z "$forbidden" ]; then
  ok "no .env files, keys or certificates committed"
else
  fail ".env files, keys or certificates committed (remove them and rotate the values):"
  printf '%s\n' "$forbidden" | sed 's/^/        /'
fi

exit "$failed"
