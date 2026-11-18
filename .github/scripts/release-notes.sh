#!/bin/sh
# Writes the notes of a stage release (tag etap1 and the like) as Markdown to standard output: how to start that
# version, its images in GHCR, and the newest CI, E2E and acceptance run of the tagged commit.
# CI runs it in the `release` job of .github/workflows/publish.yml, with the tag and commit from GitHub. Try it
# locally, from the repository root, with gh logged in (Git Bash, Linux, macOS):
#   TAG=etap1 SHA=$(git rev-parse origin/main) sh .github/scripts/release-notes.sh
# A missing or unfinished run is written into the notes, not treated as an error: the person handing in reads the
# notes on the release page and decides (README, "Handing in a stage").
set -eu

# GitHub Actions sets GITHUB_REF_NAME (the tag), GITHUB_SHA (its commit) and GITHUB_REPOSITORY (owner/name)
TAG=${TAG:-${GITHUB_REF_NAME:-}}
SHA=${SHA:-${GITHUB_SHA:-}}
REPO=${GITHUB_REPOSITORY:-MarKir13/U-Cioci-Masali}
# Lowercase: GHCR rejects the owner's name as written (see publish.yml)
IMAGES=ghcr.io/markir13/u-cioci-masali
# Workflows whose runs the notes list, in this order
WORKFLOWS="ci.yml e2e.yml acceptance.yml"

if [ -z "$TAG" ] || [ -z "$SHA" ]; then
  echo "Set TAG and SHA, for example: TAG=etap1 SHA=\$(git rev-parse origin/main) sh $0" >&2
  exit 2
fi
# gh finds runs only by the full commit hash, so a short one (757a2e6) or a tag name (etap1) becomes the full hash
# here; ^{commit} also turns an annotated tag into its commit. A commit missing from this clone stops here, before
# every row would wrongly say "not in this commit".
# A separate variable, so the message below still shows what was given
if ! commit=$(git rev-parse --verify --quiet "$SHA^{commit}"); then
  echo "Commit $SHA not found in this clone; run git fetch origin first" >&2
  exit 2
fi
SHA=$commit
# The images are tagged sha-<first 7 characters of the commit>, as metadata-action in publish.yml makes them
short=$(echo "$SHA" | cut -c1-7)

# run_row WORKFLOW_FILE: one table row with the newest run of that workflow for the commit
run_row() {
  # The workflow file as it is in the tagged commit, not in the working tree. acceptance.yml, for example, may not
  # exist yet in an older commit.
  if ! git cat-file -e "$SHA:.github/workflows/$1" 2>/dev/null; then
    echo "| \`$1\` | not in this commit | - |"
    return
  fi
  # gh finds the workflow by its file on main (the default branch). A release tag always points to a commit of main
  # (publish.yml checks it), so its workflows are there; for a commit of an unmerged branch a new workflow gives
  # "could not read". conclusion is empty while a run is still going; then its status (queued, in_progress) is shown.
  if run=$(gh run list --repo "$REPO" --workflow "$1" --commit "$SHA" --limit 1 \
    --json conclusion,status,url \
    --jq '.[0] // empty | "\(if .conclusion == "" then .status else .conclusion end) \(.url)"'); then
    if [ -n "$run" ]; then
      echo "| \`$1\` | ${run%% *} | ${run#* } |"
    else
      echo "| \`$1\` | no run for this commit | - |"
    fi
  else
    # gh printed its error to stderr, which is the job log in CI
    echo "| \`$1\` | could not read the runs (see the job log) | - |"
  fi
}

cat <<EOF
Version \`$TAG\` of the U Cioci Masali shop, commit \`$SHA\`.

## Start it

From a clean clone of this tag, as the README describes:

\`\`\`sh
git clone --branch $TAG https://github.com/$REPO.git
\`\`\`

## Images

Built for \`linux/amd64\` by \`publish.yml\`, public in GitHub's registry, so they can be pulled without logging in.
Both tags of each row are the same image.

| Image | Tag | Same image |
|---|---|---|
| Shop | \`$IMAGES/shop:$TAG\` | \`$IMAGES/shop:sha-$short\` |
| Proxy | \`$IMAGES/proxy:$TAG\` | \`$IMAGES/proxy:sha-$short\` |

To run them instead of building, from the clone:

\`\`\`sh
SHOP_IMAGE=$IMAGES/shop:$TAG PROXY_IMAGE=$IMAGES/proxy:$TAG \\
  docker compose -f deploy/compose.yaml up -d --no-build
\`\`\`

## Checks of this commit

The newest run of each workflow for commit \`$short\`.

| Workflow | Result | Run |
|---|---|---|
EOF

for workflow in $WORKFLOWS; do
  run_row "$workflow"
done
