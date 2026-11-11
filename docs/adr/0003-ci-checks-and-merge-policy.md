# 0003. CI checks and merge policy

- Status: Accepted
- Date: 2026-11-10
- Authors: Marcel Kiraga

## Context

Several Stage 1 requirements are about process rather than code, and the lecturer measures them on the repository
itself:

- W1 [K]: every change reaches `main` through an approved PR, and gitleaks over the full history finds 0 secrets.
  What lands on `main` cannot be rewritten, so a secret there fails the requirement for good.
- D5: a pipeline on every PR runs a linter and the scraper tests, and no PR is merged with a failed pipeline.
- The defence: each of the five team members must explain and change any part of the project live, including the
  workflows, and "Repair a broken container setting" is one of the example tasks.

CI-1 and CI-2 added ruff, the scraper tests, the secret scan and the repository limits. CI-3 adds linters for the
Dockerfiles, shell scripts, the compose file, PHP and JavaScript. That leaves four questions: how PRs are merged, which
history the secret scan covers, how the linters are installed and pinned, and what to do when a lint rule does not
fit.

## Options considered

### How PRs are merged

**Merge commits only (chosen)**

- Pro: every commit of a PR stays on `main` with its author, so the history shows who did what (W1 counts authored and
  reviewed PRs per person).
- Pro: the commits CI scanned are the commits that land on `main`.
- Con: a secret in any commit of the PR reaches `main` for good, even if a later commit removes it. The branch must be
  rewritten before merging.

**Squash merge**

- Pro: one clean commit per PR; a secret removed later in the branch never reaches `main`. PR #4 was squashed for this
  reason.
- Con: the individual commits and their authors disappear from `main`, and one commit per PR hides how the work was
  split up.

**Rebase merge**

- Con: rewrites the PR's commits, so the commits on `main` are not the ones CI ran on.

### Which history the secret scan covers

**On a PR: all of `main` plus every commit of the PR. Nightly: every branch (chosen)**

- Pro: a PR fails only for its own commits, never because another branch is unclean.
- Pro: the nightly run is the lecturer's measurement (`--all`) and shows which branch needs cleaning.
- Con: a branch with a secret is only reported at night, or when it is opened as a PR.

**Every branch on every PR**

- Con: one unclean branch blocks every PR in the repository until it is cleaned.

**Only the PR's diff**

- Con: misses secrets in earlier commits of the PR, which merge commits put on `main`.

gitleaks runs with its default rules. Inline `gitleaks:allow` comments are reported anyway
(`--ignore-gitleaks-allow`), and the limits script fails on a committed `.gitleaks.toml` or `.gitleaksignore`, because
gitleaks would read either one and skip findings.

### How the linters are installed

**Pinned Docker images for hadolint, shellcheck and `php -l`; ESLint from a root `package-lock.json` (chosen)**

- Pro: the same image tag gives the same result in CI and on any laptop with Docker, with nothing to install.
- Pro: each CI step is one `docker run` line that can be copied into a terminal and explained.
- Pro: a new release of a tool cannot turn CI red overnight; updates are deliberate changes in a PR.
- Con: updates are manual. The version appears in `ci.yml`, the README and AGENTS.md, and all three must change.
- Con: ESLint needs Node.js and npm, a second toolchain in a PHP and Python project. Its plugins and config are npm
  packages, so a Docker image would not make it simpler.

**Marketplace actions, such as a hadolint or shellcheck action**

- Pro: shorter workflow files.
- Con: third-party code with access to the runner, a hidden tool version, and no matching local command.

**Install with `apt-get` on the runner**

- Con: the Ubuntu package versions change with the runner image and differ from what each person has locally.

### When a lint rule does not fit

**Silence only that line, with the reason above it (chosen)**

- Pro: the exception is visible where it applies, and every other line stays checked by the rule.
- Example: `deploy/proxy/Dockerfile` installs `openssl` with `apk add` and no version, which triggers hadolint `DL3018`.
  openssl only generates the self-signed certificate, any current version does that, and Alpine removes old package
  versions from its mirrors, so a pinned version would break the build later.

**Turn the rule off in a config file**

- Con: the rule disappears for every file, including future ones where it would be right.

**Change the code to satisfy the rule anyway**

- Con: for `DL3018`, a pinned `openssl` version would make the image fail to build after the next Alpine update.

## Decision

- PRs are merged with merge commits only. The ruleset on `main` allows only merge commits once CI-2 is merged.
- `repo-hygiene` scans all of `main` plus every commit of the PR; `secret-scan.yml` scans every branch nightly.
  gitleaks uses its default rules with no allowlist.
- hadolint, shellcheck and `php -l` run from Docker images pinned by tag. ESLint is pinned exactly in the root
  `package.json` and `package-lock.json`, with versions at least two weeks old.
- Lint findings are fixed. Where a rule does not fit, only that line is silenced, with the reason in a comment above it.
- Branch protection requires the single `ci-gate` job, which depends on all other jobs, plus `ai-log`.

## Consequences

- A secret committed to a feature branch must be removed by rewriting that branch (force-pushing a feature branch is
  allowed, `main` never). Until then its PR fails `repo-hygiene` and the nightly scan is red.
- PRs that change the same lines are stacked, with each one based on the previous branch, instead of being merged
  against each other.
- Updating a linter means changing the version in `ci.yml`, the README and AGENTS.md (for ESLint: `package.json`
  and `package-lock.json`) in one PR, and fixing any new findings in that PR.
- Every suppression must name its reason, and reviewers should ask for one if it is missing.
- New jobs only need to be added to the `needs` of `ci-gate`; the branch protection settings stay the same.
