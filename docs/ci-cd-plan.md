# CI/CD plan

Plan for the GitHub Actions pipeline, with issues ready to paste into GitHub. First measured on 2026-11-01 and
2026-11-02; status updated on 2026-11-10.

## Where we stand

Results of running the checks on the current code (2026-11-09 unless noted):

| Check | Result | Consequence |
|---|---|---|
| gitleaks on `main`, full history | **0 findings** in 52 commits | W1 secret metric met on `main` |
| gitleaks on all branches | **2 findings**: `4330d00` on `feature/scraper-product-list-parser` and `feature/scraper-product-page-parser`, `8638e6e` on the second | PR #37 fails `repo-hygiene` and the nightly scan is red until both branches are rewritten or deleted |
| gitleaks on PR #4 | The 12 findings in `d81f787` stayed off `main` (squash merge, branch deleted) | They remain only in GitHub's `refs/pull/4`, which clones do not fetch. Only GitHub Support can remove it |
| ruff and pytest | Run by `ci.yml` on every PR since CI-1 (#22) | D5 met while no PR merges red |
| hadolint 2.15.1 on both Dockerfiles, shellcheck 0.11.0 on all 4 tracked `*.sh`, `docker compose config`, ESLint on the theme JS | Clean (2026-11-10). The only finding, `DL3018` (unpinned `openssl` in `deploy/proxy/Dockerfile`), is silenced on that line with the reason | Run by `infra-lint` on every PR once CI-3 merges |
| Repository size | About 0.6 MB packed; largest file 0.34 MB | Far below the limits |
| `main` branch protection | Ruleset active since 2026-11-09: PR with 1 approval, `ci-gate` required, no force pushes or deletion | After CI-2 merges, also require `ai-log` and dismiss stale approvals on new commits |
| PR #36 | Merged by its author without approval and with a failing pipeline; reverted by #38 | Both commits stay in `main`'s history. The content comes back through #35 and a new reviewed PR |

## Design decisions

- **CD stops at the registry in Stage 1.** The output is a versioned `linux/amd64` image in GHCR and a GitHub Release.
  Nothing is deployed anywhere: the shop must not be public, and Stage 2 adds the Swarm step once cluster access is
  known.
- **Fast checks on every PR, full data elsewhere.** Importing 1000 products with images may take up to 30 minutes, so
  it cannot run per PR. PRs get lint, unit tests and a boot test; E2E and full acceptance run on `main`, nightly or on
  demand.
- **One stable gate.** A `ci-gate` job depends on all other jobs. Branch protection requires only this job, so adding
  jobs later needs no settings change.
- **gitleaks runs with default rules and no allowlist,** which matches how the lecturer measures it.
- **Merge commits, with every commit scanned.** PRs are merged with merge commits to keep branch history, so anything
  in any commit of a PR lands on `main` for good. `repo-hygiene` therefore scans all of `main` plus every commit of the
  PR, and a secret removed in a later commit still fails. The fix is to rewrite the feature branch.
- **PRs are not blocked by other branches.** A PR scans only `main` and its own commits. The nightly `secret-scan.yml`
  scans every branch, as the lecturer does, and shows which branch needs cleaning.
- **The workflows stay plain.** Everyone may be questioned on them at the defence, so we use short shell steps and
  official actions in preference to clever third-party ones.
- **CI never contacts the source shop.** Scraper tests run on saved pages only.
- **Linters run from pinned Docker images.** hadolint, shellcheck and `php -l` need nothing installed and give the same
  result locally and in CI. ESLint is the exception: it is pinned in the root `package-lock.json`.
- **Findings are fixed, not silenced.** Where a rule really does not fit, only that line is silenced, with the reason
  above it. No rule is turned off for the whole repository. See [ADR 0003](adr/0003-ci-checks-and-merge-policy.md).

## Pipeline overview

Times are estimates until the first real runs.

| Workflow | Trigger | Jobs | Covers | Time |
|---|---|---|---|---|
| `ci.yml` | Every PR, push to `main` | `scraper`, `repo-hygiene`, `infra-lint`, `smoke` (only when `shop/` or `deploy/` changed), `ci-gate` | D5, W1, W3 | 2 min, about 8 with `smoke` |
| `pr-policy.yml` | PR opened, updated or relabelled | `ai-log` | D6 | Under 1 min |
| `secret-scan.yml` | Nightly, manual | `all-branches`: gitleaks and repository limits over every branch | W1 | 1 min |
| `publish.yml` | Push to `main`, tag `etap*` | Build and push the image, create a release on tags | Stage 2 | 3 min |
| `e2e.yml` | Push to `main`, nightly, manual | Stack, seed subset, Playwright, reports | W4 | 15 min |
| `acceptance.yml` | Manual, before tagging | Clean clone, full data, all lecturer metrics | W3, W4, D1 | 45 min |

## Steps

### Step 0: before anything else merges

Status on 2026-11-09: items 1 and 2 are done. Item 3 is partly done: the ruleset is active and requires `ci-gate`;
`ai-log` is added once CI-2 merges. The label is called `ci/cd`.

**1. Remove the tokens from PR #4.** Six saved pages contain PrestaShop's `static_token` and `token` values. They are
guest page tokens rather than our credentials (the pages were saved logged out), but the W1 threshold is 0 findings.
No test reads them. `main` cannot be rewritten, so this has to happen before the merge. PR #2 was merged with a merge
commit, and doing the same here would put `d81f787` on `main` for good.

Run from `scraper/` on the PR branch, then commit:

```sh
python -c "
import glob, re
for path in glob.glob('tests/fixtures/*.html'):
    text = open(path, encoding='utf-8', newline='').read()
    text = re.sub(r'(\"(?:static_token|token)\":\")[^\"]*\"', r'\g<1>REMOVED\"', text)
    open(path, 'w', encoding='utf-8', newline='').write(text)
"
```

Tested on a copy: 18 values replaced, gitleaks reports no leaks, all 56 tests still pass.

**2. Merge PR #4 with "Squash and merge" and delete its branch.** The new commit cleans the files, but `d81f787` stays
in the branch history. A squash keeps it off `main` without rewriting anything, and deleting the branch keeps it out of
clones. Any branch cut from `feature/scraper-setup` must be rebased onto `main` afterwards.

**3. Change the repository settings (owner only).**
- Add a ruleset on `main`: require a PR with 1 approval, block force pushes, no bypass. The course does not require
  this, but one accidental push fails a `[K]` condition. After CI-1 merges, also require the `ci-gate` check.
- Create the `ci` label.

### Step 1 onwards: order of work

| Order | Issue | Needs first |
|---|---|---|
| 1 | CI-1 Ruff and scraper tests | Done in #22. **This alone earns D5** |
| 2 | CI-2 Repository hygiene and AI log | PR #4 tokens removed (done) |
| 3 | CI-3 Docker, shell and compose lint | CI-1 (done). Stacked on CI-2 (#39), because both change the same lines of `ci.yml` and the docs |
| 4 | CI-4 Image build and smoke test | CI-3 |
| 5 | CI-5 Publish image to GHCR | CI-4 |
| 6 | CI-6 E2E in CI | CI-5, plus the gaps below |
| 7 | CI-7 Release for `etap1` | CI-5 |
| 8 | CI-8 Acceptance run | CI-6 |

After each CI PR merges, push to the open PRs so they get the new jobs. An open PR does not run new workflows until its
next update.

### Gaps outside CI

CI-6 and CI-8 test things that have no issue yet. These need their own issues:

- HTTPS with a generated certificate and the HTTP to HTTPS 301 redirect (W3 `[K]`). Done in #34.
- Mailpit or MailHog in `compose.yaml`.
- A one-command data init, such as `make init`, with an option to load a small subset for CI.
- The API import script (D2).
- The Playwright suite in `tests/` (W4).

### Stage 2 notes

CI-5 prepares the image, but these are still open for the cluster:

- `docker stack deploy` ignores `build:` and `depends_on` conditions, so the stack needs a registry image and its own
  start-up ordering.
- `shop-data` is a node-local named volume holding application files, which does not fit multiple Swarm nodes.
- How CI reaches the cluster is unknown until we have access details. Cluster credentials go in GitHub secrets only.

## Team notes

- **W1 quota:** 5 people with 3 authored and 3 reviewed PRs each means at least 15 merged PRs; 10 are merged as of
  2026-11-09. Assign these issues to whoever has the fewest.
- **Merging:** only after an approval from someone else and a green `ci-gate` (and `ai-log` once CI-2 merges). The
  ruleset enforces this since #36 was merged without either.
- **Open question for the lecturer:** the repository is public, so `scraper-results/` and the image archive will be
  public too. The brief only forbids a public *shop*. Public also means free Actions minutes and free GHCR pulls; a
  private repository on the free plan has a monthly minute quota, which the nightly E2E would strain.

## Issues

Use the `ci/cd` label. Paste each issue with its title; the bodies follow the team's existing format. Action
versions below are the latest releases as of 2026-11-01.

### [CI 1/8] CI: run ruff and scraper tests on every PR

```md
## Goal
Run a linter and the scraper unit tests on every PR (requirement D5).

## Tasks
- [ ] Add `ruff.toml` in the repository root (see below)
- [ ] Add `.github/workflows/ci.yml` (see below)
- [ ] Remove the `hashFiles` guards once `scraper/` is on `main`
- [ ] README: add a "Continuous integration" section with the commands to run the checks locally
- [ ] PR #4: fix the ruff errors (`B904`, `B018`) and run `ruff format`

`ruff.toml`:

    # Ruff settings for all Python code in this repository.
    # `src` marks `scraper` as our own package, so imports sort the same from any directory.
    line-length = 120
    target-version = "py312"
    src = ["scraper"]

    [lint]
    select = ["E", "F", "I", "UP", "B"]

`.github/workflows/ci.yml`:

    name: CI

    on:
      pull_request:
      push:
        branches: [main]

    permissions:
      contents: read

    concurrency:
      group: ci-${{ github.ref }}
      cancel-in-progress: true

    jobs:
      scraper:
        runs-on: ubuntu-24.04
        steps:
          - uses: actions/checkout@v7
          - uses: actions/setup-python@v7
            with:
              python-version: "3.12"
          - name: Install ruff
            run: pip install ruff==0.17.3
          - name: Lint
            run: ruff check .
          - name: Check formatting
            run: ruff format --check .
          - name: Install scraper dependencies
            run: pip install -r scraper/requirements.txt
          - name: Unit tests
            working-directory: scraper
            run: python -m pytest

      ci-gate:
        if: always()
        needs: [scraper]
        runs-on: ubuntu-24.04
        steps:
          - name: Fail if any required job did not succeed
            run: test "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') }}" = "false"

## Acceptance criteria
- The pipeline runs on the PR that adds it and passes
- A PR with a lint error or a failing test shows a failed `ci-gate`
- PR #4 and PR #13 merged before the pipeline ran on them; their code is verified by this PR's run on the merged
  `main`, and ruff plus the scraper tests were also run locally on `main` before that
```

### [CI 2/8] CI: repository hygiene and AI log check

```md
## Goal
Catch the W1 and D6 problems the lecturer measures, on every PR.

## Tasks
- [ ] Add a `repo-hygiene` job to `ci.yml`, with `fetch-depth: 0` so the whole history is available
- [ ] Secret scan with default rules, no allowlist, over `main` plus the PR's commits:
      `docker run --rm -v "$PWD:/repo:ro" zricethezav/gitleaks:v8.30.1 git /repo --no-banner --redact --ignore-gitleaks-allow --log-opts="HEAD"`
- [ ] Add `.github/scripts/check-repo-limits.sh` (limits at the top, `--all` for every branch), failing on:
  - [ ] any blob over 10 MB in history
  - [ ] repository size over 200 MB (`git count-objects -v`)
  - [ ] more than 20 tracked images in `scraper-results/`
  - [ ] a `.env` file other than `.env.example`, a private key or a certificate in any commit
  - [ ] a committed `.gitleaks.toml` or `.gitleaksignore`, which gitleaks would read from the repository and use to
        skip findings (`--ignore-gitleaks-allow` above covers inline `gitleaks:allow` comments)
- [ ] Add `.github/workflows/pr-policy.yml`, triggered on `opened`, `synchronize`, `reopened`, `labeled`, `unlabeled`:
      if the PR has the `ai-assisted` label, it must add or update a row in `docs/AI_LOG.md`
- [ ] Add `.github/workflows/secret-scan.yml`: gitleaks and the limits over every branch, nightly and by hand
- [ ] Add `repo-hygiene` to the `needs` of `ci-gate`
- [ ] README, AGENTS.md: the local commands

## Depends on
PR #4 with its tokens removed (done). PRs scan only `main` plus their own commits, so an unclean branch fails only
its own PR and the nightly scan.

## Acceptance criteria
- A repository with a fake token fails the secret scan, even after the token is removed in a later commit (tested
  locally: a pushed token would stay in the branch history and in `refs/pull/N`)
- A PR labelled `ai-assisted` without an AI log row fails `ai-log`
- A file over the limit fails the limit check (shown in CI with a temporarily lowered limit)
```

### [CI 3/8] CI: lint Docker, shell and compose files

```md
## Goal
Catch container mistakes early. "Repair a broken container setting" is one of the live defence tasks, so these files
should stay clean.

## Tasks
- [ ] Add an `infra-lint` job to `ci.yml`, one step per tool, each run even if an earlier one failed
- [ ] hadolint (Docker image `hadolint/hadolint:v2.15.1`) on `shop/Dockerfile` and `deploy/proxy/Dockerfile`
- [ ] shellcheck (Docker image `koalaman/shellcheck:v0.11.0`) on every tracked `*.sh`
- [ ] `cp deploy/.env.example deploy/.env`, then `docker compose -f deploy/compose.yaml config --quiet`, failing on any
      output: Compose only warns about an unknown variable
- [ ] ESLint on `shop/themes/ciocia/assets/js/`, pinned in a root `package.json` and `package-lock.json`, with a root
      `eslint.config.mjs`. Add `tests/` once the Playwright suite exists
- [ ] `php -l` (Docker image `php:8.1.34-cli`) on PHP files in `shop/` (modules, setup scripts, settings)
- [ ] Fix or silence the current findings: silence only single lines, with the reason above them
- [ ] Add `infra-lint` to the `needs` of `ci-gate`
- [ ] ADR on the CI checks and merge policy
- [ ] README, AGENTS.md: the local commands

## Acceptance criteria
- The job passes on `main`
- A wrong variable name in `compose.yaml`, a shell syntax error or unquoted variable, `ADD` instead of `COPY` in a
  Dockerfile, and an undefined variable in the theme JS each fail the job, shown in CI with one temporary commit
```

### [CI 4/8] CI: build the shop image and smoke-test a clean install

```md
## Goal
Prove on every relevant PR that the shop installs from scratch. A clean-clone failure means W3 is not passed.

## Tasks
- [ ] `deploy/compose.yaml`: add a healthcheck to `shop` using `curl` (present in the image), with a `start_period` long
      enough for the first install
- [ ] Add a `changes` job that sets outputs from `git diff --name-only` for `shop/` and `deploy/`
- [ ] Add a `smoke` job, run only when those paths changed:
  - [ ] `cp deploy/.env.example deploy/.env`
  - [ ] `docker compose -f deploy/compose.yaml up -d --build --wait --wait-timeout 600`
  - [ ] Assert the storefront returns 200 and is in Polish
  - [ ] Assert the theme `ciocia` is active
  - [ ] Print container logs when the job fails
  - [ ] Always run `down -v`
- [ ] Update `ci-gate` so a skipped `smoke` counts as a pass (the current check already does) and add it to `needs`
- [ ] When HTTPS lands: assert 301 from HTTP and 200 from HTTPS

## Acceptance criteria
- A PR that breaks `shop/Dockerfile` or `deploy/compose.yaml` fails `smoke`
- A PR that changes only `docs/` skips it and `ci-gate` still passes
- The job finishes in under 10 minutes
```

### [CI 5/8] CD: publish the amd64 shop image to GHCR

```md
## Goal
Produce a versioned image that Stage 2 can pull on the Swarm cluster.

## Tasks
- [ ] Add `.github/workflows/publish.yml`, on push to `main` and tags `etap*`, with `packages: write` and logging in
      through `GITHUB_TOKEN`
- [ ] Use `docker/setup-buildx-action@v4`, `docker/login-action@v4`, `docker/metadata-action@v6`,
      `docker/build-push-action@v7`
- [ ] Hard-code the lowercase name `ghcr.io/markir13/u-cioci-masali/shop`, since GHCR rejects uppercase
- [ ] Build with `platforms: linux/amd64`
- [ ] Tags: `main`, `sha-<short>`, and the git tag name
- [ ] `deploy/compose.yaml`: `image: ${SHOP_IMAGE:-ciocia-shop:local}` and `platform: linux/amd64`
- [ ] Set the package to public, so cluster nodes need no registry credentials
- [ ] Write an ADR on how images are built and distributed

## Acceptance criteria
- `docker pull ghcr.io/markir13/u-cioci-masali/shop:main` works while logged out
- `docker image inspect` reports `amd64`
- The image holds no `.env`, product data or product images
```

### [CI 6/8] CI: run Playwright E2E against the full stack

```md
## Goal
Run the W4 scenario automatically, with the same command the lecturer uses.

## Depends on
HTTPS, one-command data init with a subset option, Playwright suite in `tests/`.

## Tasks
- [ ] Add `.github/workflows/e2e.yml`: push to `main`, nightly, manual
- [ ] Start the stack and seed a subset with at least 10 products in 2 categories, searchable by name
- [ ] Run the README command with the shop address from `BASE_URL`, accepting the self-signed certificate
- [ ] Upload the HTML and JUnit reports and failure screenshots with `actions/upload-artifact@v7`, also on failure
- [ ] Add a manual `repeat` input, default 3, that runs the whole suite that many times in a row
- [ ] Add the `.gitignore` entries `test-results/` and `playwright-report/`

## Acceptance criteria
- The nightly run passes on `main`
- A manual run passes 3 of 3, each within 5 minutes
- The report is downloadable from the run page
```

### [CI 7/8] CD: release workflow for the etap1 tag

```md
## Goal
Make handing in repeatable. Only the tagged version is graded, and it is due at least 48 hours before the meeting.

## Tasks
- [ ] Extend `publish.yml`: on tag `etap*`, push the image under that tag and create a GitHub Release with
      `softprops/action-gh-release@v3` and `contents: write`
- [ ] Fail if the tagged commit is not on `main` (`git merge-base --is-ancestor`)
- [ ] Include the image reference and the `ci`, E2E and acceptance run links in the release notes
- [ ] Publish the product image archive under a separate tag such as `images-v1`, so the init script's URL exists
      before `etap1` does (coordinate with issue #12)
- [ ] README: document the release steps

## Acceptance criteria
- A trial tag such as `etap0-test` produces an image and a release, both deleted afterwards
- The init script downloads the archive from the fixed `images-v1` URL
```

### [CI 8/8] CI: acceptance run with the lecturer's metrics

```md
## Goal
Measure the W3, W4 and D1 thresholds before the lecturer does.

## Depends on
CI-6 and the full data import.

## Tasks
- [ ] Add `.github/workflows/acceptance.yml`, manual only
- [ ] From a fresh clone, follow the README and time start plus data init: at most 15 minutes
- [ ] SQL checks: at least 1000 products, at least 4 categories each with at least 2 non-empty subcategories, 5–20% of
      products with stock 0, maximum stock 10
- [ ] Crawl at least 200 pages: 0 4xx/5xx
- [ ] Check for console errors on the home, category, product and cart pages
- [ ] Run Lighthouse on desktop, ignoring the certificate: Performance at least 60, Accessibility at least 85
- [ ] Run the full E2E suite
- [ ] Write the results to `$GITHUB_STEP_SUMMARY` as a pass/fail table
- [ ] Once the backup scripts exist: time a restore, at most 10 minutes

## Acceptance criteria
- A run on `main` lists every threshold with its measured value
- The workflow runs successfully at least once before the `etap1` tag
```
