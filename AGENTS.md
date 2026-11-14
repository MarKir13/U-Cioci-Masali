# AGENTS.md

Instructions for every coding agent working in this repository (Codex reads this file directly, Claude Code
through `CLAUDE.md`). Task status lives in GitHub issues and PRs, not here.

## Project

**U Cioci Masali** is a team project for the *Biznes Elektroniczny* course at Gdansk University of Technology:
a reconstruction of the online shop **[magiczne-indie.pl](https://www.magiczne-indie.pl/)** (Indian cosmetics, food,
health products and gifts) on PrestaShop 8.

- **Stage 1 (current):** run the shop in containers, fill it with data scraped from the source shop, test it
  automatically. Graded at the 4th project meeting; 8 weeks in total.
- **Stage 2:** deploy the Stage 1 shop on a Docker Swarm cluster (`linux/amd64`). Decisions made now about images,
  repository structure and data initialisation carry over, so do not design for local use only.
- **Legal limit:** data is scraped for teaching only. The shop with this data must **never** be publicly reachable
  on the internet. Do not add public hosting, tunnels or deploy targets.
- **Team:** five people, listed in [README.md](README.md). Each one is individually questioned on the whole codebase
  and must modify it live, so prefer simple solutions that all of them can explain.

## Source shop

Full findings: `docs/scraper-recon.md` (on PR #4 until it merges). The essentials:

- PrestaShop with a custom theme and custom `ndx*` modules. 2167 products, 314 categories.
- Top-level categories: Kosmetyki (8), Żywność (193), Zdrowie (80), Różności (232), plus the special categories
  Na prezent (458) and Nowości (50). "Promocje" and "Himalaya" in its menu are not categories.
- Best data source on a product page: the JSON in `data-product` on `div.js-product-details`, plus the JSON-LD
  `Product` block. Standard Classic selectors do not exist there.
- Image size to download: `product_main_2x` (1440 px). A sampled file was 311 KB, over the 300 KB limit, so images
  must be recompressed.
- `price_amount` is the discounted price; keep `price_without_reduction` too.
- Weight units are unreliable: JSON-LD always says `g`, but values mix grams and kilograms. Store the raw value and
  convert on import.
- Variants are not PrestaShop combinations. They are separate products linked by the `ndx-family` module.
- `urllib.robotparser` ignores `*` in robots.txt paths; the scraper uses Protego.

## Stack and layout

| Component | Version |
|---|---|
| PrestaShop | 8.2.8, image `prestashop/prestashop:8.2.8-8.1-apache` |
| PHP | 8.1 (Apache) |
| Database | MariaDB 10.11.18 |
| Containers | Docker Engine, Compose v2 (`compose.yaml`, `docker compose`, no `version:` key) |
| Scraper | Python 3.12, `requests`, Protego, pytest |
| E2E tests | Playwright 1.64.1, headless Chromium, pinned in `tests/package.json` (Selenium is not allowed) |
| Test mail | Mailpit or MailHog in a container |
| Linters | hadolint 2.15.1, shellcheck 0.11.0, `php -l` (`php:8.1.34-cli`), all as Docker images; ESLint 10.13.0 on Node 24, pinned in the root `package.json` (development tools only) |
| Published images | `ghcr.io/markir13/u-cioci-masali/shop` and `.../proxy`, `linux/amd64`, built by `publish.yml`; tags `sha-<7 characters>`, `main`, `etap*` |

| Path | Contents |
|---|---|
| `shop/` | Dockerfile, PHP config, child theme `ciocia`, own modules. PrestaShop itself is not stored here |
| `scraper/` | Scraper source and unit tests |
| `scraper-results/` | Scraped data in UTF-8 with source image URLs, plus up to 20 sample images |
| `deploy/` | `compose.yaml`, `.env.example`, scripts for install, data init, backup and restore |
| `docs/` | `AI_LOG.md`, ADRs in `adr/`, [ci-cd-plan.md](docs/ci-cd-plan.md), other documentation |
| `tests/` | Playwright E2E tests: specs in `e2e/`, page helpers in `pages/`, shared code in `support/`; own `package.json` |

The structure is a graded requirement. Do not add new top-level directories, apart from tool config such as
`.github/`.

## Commands

Run from the repository root unless noted.

| Task | Command |
|---|---|
| First setup | `cp deploy/.env.example deploy/.env` |
| Build and start the shop | `docker compose -f deploy/compose.yaml up -d --build` |
| Apply changes from `shop/` | same command as above |
| Follow install logs (done at `Starting web server`) | `docker compose -f deploy/compose.yaml logs -f shop` |
| Re-apply `shop/config/shop-settings.php` and shop content to a running shop, after a rebuild (Git Bash: prefix `MSYS_NO_PATHCONV=1`) | `docker compose -f deploy/compose.yaml exec shop sh /tmp/post-install-scripts/20-shop-content.sh`, then the same with `30-configure-shop.sh` |
| Stop, keeping data | `docker compose -f deploy/compose.yaml down` |
| Scraper unit tests (from `scraper/`) | `python -m pytest` |
| Scraper lint | `ruff check .` and `ruff format --check .` |
| Secret scan, as on a PR (Git Bash on Windows: prefix `MSYS_NO_PATHCONV=1`) | `docker run --rm -v "$PWD:/repo:ro" zricethezav/gitleaks:v8.30.1 git /repo --no-banner --redact --ignore-gitleaks-allow --log-opts="HEAD"` |
| Repository limits (`--all` for every branch) | `sh .github/scripts/check-repo-limits.sh` |
| Dockerfile lint (Git Bash: prefix `MSYS_NO_PATHCONV=1`) | `docker run --rm -v "$PWD:/repo:ro" -w /repo hadolint/hadolint:v2.15.1 hadolint shop/Dockerfile deploy/proxy/Dockerfile` |
| Shell lint (Git Bash: `MSYS_NO_PATHCONV=1` before `xargs`) | `git ls-files -z '*.sh' \| xargs -0 docker run --rm -v "$PWD:/repo:ro" -w /repo koalaman/shellcheck:v0.11.0` |
| Compose check, must print nothing. Never drop `--quiet` or use `deploy/.env` | `docker compose -f deploy/compose.yaml --env-file deploy/.env.example config --quiet` |
| PHP syntax (Git Bash: `MSYS_NO_PATHCONV=1` before `xargs`) | `git ls-files -z 'shop/*.php' \| xargs -0 -r -n1 docker run --rm -v "$PWD:/repo:ro" -w /repo php:8.1.34-cli php -l` |
| JavaScript lint (after `npm ci` once) | `npx eslint` |
| E2E setup, once (from `tests/`) | `npm ci` and `npx playwright install chromium` |
| E2E tests (from `tests/`; another shop: `BASE_URL=https://host:port npm test`) | `npm test` |
| Open the last E2E report (from `tests/`) | `npm run report` |
| Smoke test of the running shop (ports from `HTTP_PORT`, `HTTPS_PORT`) | `sh .github/scripts/smoke-test.sh` |
| Review the open PRs that wait for your review (Claude Code; prints review comments to paste, posts nothing) | `/review-prs`, or `/review-prs 67` for chosen PRs |
| Run the published images instead of building (tags in README) | `SHOP_IMAGE=ghcr.io/markir13/u-cioci-masali/shop:main PROXY_IMAGE=ghcr.io/markir13/u-cioci-masali/proxy:main docker compose -f deploy/compose.yaml up -d --no-build` |
| Back up the running shop into `deploy/backups/` (gitignored, holds customer data) | `sh deploy/backup.sh` |
| Restore a backup into the running shop: replaces its database and images, asks first (`--yes` skips the question) | `sh deploy/restore.sh deploy/backups/<archive>.tar.gz` |

Storefront: `https://localhost:8443` (HTTP on 8080 redirects there). Admin: `https://localhost:8443/admin-ciocia`.
Shop e-mails: `http://localhost:8025` (Mailpit). A one-command data init is required but not built yet; update this
table when it lands.

## Hard rules

Breaking a rule marked **[K]** scores 0 for that requirement, whatever else works.

1. **[K] Never commit or push to `main`, and never force-push it.** Work on a `feature/...` branch. Everything reaches
   `main` through a PR approved by another person. An agent does not approve or merge PRs, and only commits or pushes
   when asked.
2. **[K] No secrets in git, in any commit on any branch.** Configuration goes through `deploy/.env`; only `.env.example`
   is committed. The check is `gitleaks` over the full history, and what lands on `main` cannot be rewritten. CI runs
   it on every PR (all commits of `main` plus the PR) and nightly over every branch. A secret removed in a later
   commit still fails, so remove it by rewriting the feature branch, not with a new commit.
3. **Do not read or print `deploy/.env`,** and do not handle passwords, API keys or cluster credentials. Course rules
   forbid passing them to AI tools.
4. **Log AI use in the same PR.** Add a row to `docs/AI_LOG.md` (in Polish), give the PR the `ai-assisted` label, and
   explain in its description how the result was verified. Columns: date and author, tool and model, task (issue or
   PR), what was received, what was wrong, verification. List real mistakes in "what was wrong".
5. **No product images in git or Git LFS.** The full set is one archive (zip or tar.gz, up to 1 GB) in GitHub Releases.
   The init script downloads it, or re-downloads from source URLs if it is unavailable.
6. **Child theme only.** Change the look through `shop/themes/ciocia`, never through Classic files. Read the warning in
   its `theme.yml` before adding top-level keys.
7. **Keep the source shop safe from us.** Tests and CI never touch the network; they use saved pages in
   `scraper/tests/fixtures/`. Live scraper runs happen only when a person asks, stay at 2 requests per second or fewer,
   respect robots.txt and send the project User-Agent.
8. **Strip tokens from saved pages.** Every page of the source shop embeds `static_token` and `token`, which gitleaks
   flags. Replace the values before committing a fixture.
9. **No fixed sleeps in E2E tests.** Wait on conditions. The shop address comes from a parameter or environment
   variable, because Stage 2 runs the same tests on the cluster.
10. **Ask before destructive commands.** `docker compose ... down -v` deletes the local shop and its database.
11. **Do not assume paid modules.** Every requirement can be met without them.

## How to work on a task

1. Start from a GitHub issue. Issues use `## Goal`, `## Tasks`, `## Acceptance criteria`; each issue ends in a PR.
2. Branch from an up-to-date `main`. Commit in small steps using the existing style: `feat:`, `fix:`, `docs:`, `test:`,
   `chore:`, optionally scoped, as in `feat(theme): ...`.
3. Run the result, not only the build. Before calling shop work done, check it at desktop width and at 360 px on the
   home, category, product, cart **and checkout** pages, with no errors in the browser console. Checkout has its own
   header template in Classic, so theme changes there are easy to miss.
4. Add tests where the area has them. Parsers get tests on saved HTML pages.
5. Update whatever the change makes stale: `README.md`, this file, `.env.example`.
6. For a real choice between alternatives that is hard to reverse, add an ADR in `docs/adr/`. Accepted ADRs are not
   edited; a new one supersedes them.
7. Write the PR description for a human reviewer: what changed, why, how it was verified.

Documentation is in English, except `docs/AI_LOG.md`.

## Known pitfalls

- `/var/www/html` is a named volume that is filled from the image only once. `shop/scripts/sync-code.sh` copies the
  theme and modules from `/opt/ciocia` on every start. A file in the image will not reach the running shop unless it
  goes through that path. The same script deletes `var/cache/prod` and `var/cache/dev` on every start, so new module
  template overrides need no manual cache clear.
- Shop content and settings live in the database. Set them in `shop/scripts/setup/` (ADR 0005), never only in the
  back office. Scripts in `shop/scripts/post-install/` run once, in name order, right after the automatic install,
  and never on an existing install; the image keeps starting if one fails: look for `[setup] FAILED` in the shop log.
- All values (store details, currency, carriers, payments, e-mail) live in `shop/config/shop-settings.php`. Both
  `shop-content.php` (CMS pages, footer links, store details) and `configure-shop.php` read it, so the pages match
  the checkout. Setup scripts must stay idempotent so they can be re-run by hand, and must not rely on fixed CMS
  page IDs.
- `PS_COUNTRY` must be lowercase (`pl`): the installer loads `localization/<value>.xml`, and with `PL` it silently
  falls back to EUR/USD and no VAT rates.
- Scripts run on Linux but are edited on Windows and macOS. `.gitattributes` forces LF for `*.sh`, `*.php`, Dockerfiles
  and YAML; keep new script types covered.
- `.gitignore` excludes `*.crt`, `*.key`, `*.pem`, `*.zip` and `*.tar.gz`, so certificates and archives must be
  generated or downloaded at runtime.
- Images for the Stage 2 cluster come only from `publish.yml`, built on `amd64` runners. A local build on Apple Silicon
  is `arm64`, which will not run there, so never push a locally built image. `compose.yaml` sets no `platform:`, so
  local builds stay native and fast.
- GHCR image names must be lowercase, while the repository owner is `MarKir13`.
- Without `SHOP_IMAGE` and `PROXY_IMAGE`, every Compose project builds into the same tags `ciocia-shop:local` and
  `ciocia-proxy:local`, whatever `-p` says. Set both to your own names for a second local stack.
- Fix lint findings instead of silencing them. If a rule really does not fit, silence only that line and put the reason
  above it (as `# hadolint ignore=DL3018` in `deploy/proxy/Dockerfile`); never turn a rule off for the repository.
- E2E tests take the shop address from `BASE_URL`, and its host must be the shop's domain (`PS_DOMAIN`): PrestaShop
  redirects any other host there. Tests import `test` from `tests/support/fixtures.js`, keep selectors in
  `tests/pages/` and never call `waitForTimeout`; ESLint fails on it. A failed run is repeated with the `E2E_SEED`
  shown in the report.
- A backup holds the database, `img/` and the banner slides, but not `app/config/parameters.php` or `.htaccess`
  (ADR 0009). After a restore the back office login is the one from the backup. A new kind of file that lives
  only in the `shop-data` volume and is not rebuilt from the image must be added to both `deploy/backup.sh` and
  `deploy/restore.sh`.
  
## Requirements: Stage 1

Condensed from the course brief, which remains authoritative. `[K]` means critical: missing it gives 0 for the whole
requirement. W1–W4 must pass before D1–D6 are graded. Passing needs every `[K]` and at least half the points in each
of W1–W4. Total: 40 points.

### Mandatory (20 points)

**W1. Repository and process (3)**
- [K] GitHub repository accessible to the team and the lecturer.
- [K] Nothing reaches `main` directly: every change after the initial commit is a merged PR approved by someone else.
  No force pushes.
- [K] No secrets in the repository.
- `.gitignore` excludes cache, uploads, logs, `vendor/`, `node_modules/`.
- `README.md` covers the project, PrestaShop version, step-by-step start and the team.
- `main` holds the version presented at acceptance.
- Tasks are issues with an assignee, each ending in a PR. Reviews contain real comments, not only approval.
- Directory structure as listed above.

**W2. Scraper (4)**
- [K] Code and UTF-8 results are in the repository.
- [K] Results cover categories, subcategories and products: name, description, gross price, VAT rate (if available),
  attributes such as colour, material, size, weight (if available), and images: at least one per product and at least
  two for 50 chosen products, sharp when zoomed. Thumbnails are not accepted.
- Rate limit, robots.txt respected, identifying User-Agent.
- Can be interrupted and resumed without downloading saved data again.
- Data validated against a schema, errors written to a log.
- Parser unit tests run on locally saved HTML pages.
- Images: longer side 800–1600 px, JPEG or WebP, at most 300 KB per file.

**W3. Shop (8)**
- [K] Runs in containers managed by Compose v2.
- [K] Starts from a clean clone following the README, with one start command and one data init command
  (for example `docker compose up -d` and `make init`).
- [K] HTTPS only, with a self-generated certificate. HTTP answers 301 to HTTPS.
- Shop e-mail goes to Mailpit or MailHog: the customer gets mail after registering and after ordering.
- [K] Top menu, footer, search, registration, login, product list, product page, cart, purchase and order history work
  without errors.
- [K] Customer interface in Polish, with Polish characters displayed correctly.
- CMS pages: O sklepie, Regulamin, Polityka prywatności, Dostawa, Formy płatności. Content fits the shop, with no
  installer defaults and no lorem ipsum.
- Cookie notice.
- [K] At least 1000 products (unless the source has fewer) in at least 4 categories, each with at least 2 non-empty
  subcategories.
- [K] Names, descriptions, images, prices and VAT rates match the source shop.
- Stock is 0–10 for every product, and some products are unavailable.
- At least two payment methods used in Poland, including bank transfer and cash on delivery, with no payment operator
  integration. No methods that are not used in Poland.
- Two new carriers with different fees. Free delivery above 2000 PLN gross; delivery impossible above 50 kg.

**W4. E2E tests (5)**, Playwright, headless, whole run within 5 minutes:
1. Add 10 products in varying quantities from 2 categories to the cart.
2. Search by name and add a random result to the cart.
3. Remove 3 products from the cart.
4. Register a new account.
5. Order the cart contents.
6. Choose cash on delivery.
7. Choose one of the two new carriers.
8. Confirm the order.
9. Check the order status.
10. Download the VAT invoice.

- [K] One command, documented in the README. The shop address comes from a parameter or environment variable.
- Every step asserts its effect, not only the click.
- Produces a JUnit XML or HTML report, and a screenshot on failure.
- No fixed sleeps as the main synchronisation.

### Additional (20 points, partial credit possible)

**D1. Look (5).** Variant A: layout identical or close to the source shop (the colours need not match). Variant B:
original design. Issue #5 follows variant A by recreating the source header. In both: at least one working themed
banner on the home page, correct at 360 px, Lighthouse accessibility threshold met, child theme only.

**D2. API import (4).** A script creates categories, subcategories and products (with images, prices, VAT rates, stock
and weight) through the PrestaShop Webservice API from the scraped results. Idempotent: a second run updates and does
not duplicate. API key from an environment variable, limited to the resources needed. Reports created, updated and
rejected counts.

**D3. Promotions and variants (3).** At least 20 products with a price promotion. Every promotion shows the lowest
price from the 30 days before the discount (Omnibus directive). At least 5 products with at least 2 variants, each with
its own stock.

**D4. Backup and restore (3).** Scripts in `deploy/` back up the database, product images and config, and restore from
that backup. A settings export in the repository restores shop configuration, with no customer data or secrets. Demo of
a restore onto a clean environment at acceptance.

**D5. CI (2).** A pipeline on every PR runs a linter and the scraper unit tests. No PR merged with a failed pipeline.
See [docs/ci-cd-plan.md](docs/ci-cd-plan.md).

**D6. AI log and ADRs (3).** AI log in the required format, ending with a team reflection (up to one page). At least 3
ADRs in `docs/adr/`: context, options, decision, consequences.

### Metrics checked by the lecturer

| Req | Metric | Threshold |
|---|---|---|
| W1 | Changes on `main` through approved PRs | 100% after the initial commit |
| W1 | Each person's share | Author of ≥3 and reviewer of ≥3 merged PRs |
| W1 | Secrets | 0 findings from gitleaks on the full history |
| W1 | Repository size | ≤200 MB, no file >10 MB, no full image set |
| W2 | Scraper rate | ≤2 requests per second |
| W2 | Record completeness | 0 products without name, price, description or images |
| W2, W3 | Images | ≥1 per product, ≥2 for 50 products, longer side 800–1600 px, ≤300 KB |
| W3 | Clean clone to working shop with data | ≤15 min |
| W3 | Products | ≥1000 |
| W3 | Categories | ≥4, each with ≥2 subcategories, 0 empty |
| W3 | Out-of-stock products | 5–20% with stock 0 |
| W3 | Maximum stock | ≤10 for every product and variant |
| W3 | Match with source | 10 of 10 random products (name, price, images) |
| W3 | HTTP errors | 0 4xx/5xx, except deliberate 404s, over ≥200 pages |
| W3 | JavaScript errors | 0 in the console on home, category, product, cart |
| W3 | Home page performance | Lighthouse Performance ≥60 on desktop |
| W4 | Test duration | ≤5 min |
| W4 | Stability | 3 of 3 consecutive runs pass |
| D1 | Accessibility | Lighthouse Accessibility ≥85 |
| D2 | Idempotence | 0 duplicates after a second run |
| D2 | Import time | ≤30 min for 1000 products with images |
| D4 | Restore time | ≤10 min |
| D6 | AI log | ≥2 entries per person |

### Acceptance

At least 48 hours before the meeting, the version on `main` gets the tag `etap1` and a release; only that version is
graded. The lecturer clones it and starts it following the README, and if that fails, W3 fails. The team presents for
up to 10 minutes, including a live E2E run.

Each person then defends any part of the project, including parts written by someone else, and has 15 minutes for a
live change. Saying that AI wrote something is not a defence. Team points are multiplied by a personal factor from 0
to 1. Example live changes:

- Change the free delivery threshold to 1500 PLN and show it in the cart.
- Add a new product attribute to the scraper and its validation schema.
- Add an E2E step that checks the Regulamin page.
- Repair a deliberately broken container setting, such as an environment variable or port.
- Change the home page banner text or link.
- Add a variant to a product through the import script or admin panel.

Keep these changes easy: store thresholds, banners and shop settings where a person can find them quickly.
