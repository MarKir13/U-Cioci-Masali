# Runtime checks (phase 2)

You hold the only Docker slot. Build the shop from your PR's worktree as a separate Compose project
on its own ports, check it, and remove it again. The user's own stack (project `ciocia`, ports 8080,
8443, 8025, images `ciocia-shop:local` and `ciocia-proxy:local`) must stay untouched.

## 1. Start a clean install

From the worktree, in Git Bash. `--env-file deploy/.env.example` uses the example values, so
`deploy/.env` is never read. The exported variables override the file's ports and image tags.

```sh
export COMPOSE_PROJECT_NAME=review-pr-<N>
export HTTP_PORT=18080 HTTPS_PORT=18443 MAILPIT_PORT=18025
export SHOP_IMAGE=ciocia-shop:review-pr-<N> PROXY_IMAGE=ciocia-proxy:review-pr-<N>

# The ports must be free: stop and tell the orchestrator if any of them answers
for port in "$HTTP_PORT" "$HTTPS_PORT" "$MAILPIT_PORT"; do
  curl -s -o /dev/null --max-time 2 "http://localhost:$port/" && echo "port $port in use"
done

start=$(date +%s)
docker compose -p "$COMPOSE_PROJECT_NAME" -f deploy/compose.yaml --env-file deploy/.env.example \
  up -d --build --wait --wait-timeout 900
echo "ready after $(( $(date +%s) - start )) s"
```

Every `docker compose` call in this phase uses `-p review-pr-<N> -f deploy/compose.yaml --env-file
deploy/.env.example`. Never run one without `-p`.

If `up` fails or times out, collect `docker compose ... ps -a` and `logs --no-color shop` (look for
`[setup] FAILED`), report the failure as a Required point with the relevant log lines, and go to
step 4.

## 2. Check the shop

The storefront is `https://localhost:18443` (self-signed certificate), admin at
`https://localhost:18443/admin-ciocia`, Mailpit at `http://localhost:18025`.

1. **Smoke test:** `HTTP_PORT=18080 HTTPS_PORT=18443 sh .github/scripts/smoke-test.sh`.
2. **Pages in a browser.** Use Playwright with headless Chromium. If the worktree has
   `tests/package.json`, use it (`npm ci --prefix tests`, then `npx --prefix tests playwright install
   chromium`); otherwise install `@playwright/test` at the version pinned on `main`, or 1.64.1, into
   your scratchpad. Write the script in your scratchpad with `ignoreHTTPSErrors: true`. Wait on
   conditions, not fixed timeouts. Visit home, a category, a product, the cart with one product and
   checkout (`index.php?controller=order`), each at 1280×800 and 360×740. If the cookie notice covers
   buttons, click "Tylko niezbędne" first. For every page record:
   - console errors and uncaught exceptions (AGENTS.md metric: 0 on home, category, product, cart);
   - responses with status 4xx or 5xx, other than deliberate 404s;
   - horizontal scroll at 360 px (`document.documentElement.scrollWidth > innerWidth`);
   - a screenshot, saved to your scratchpad.
   If the shop has no products yet (no data init), say which pages could not be reached instead of
   failing them.
3. **What this PR changes.** Exercise the behaviour the PR and its issue describe, and the
   PR-specific checks you listed in phase 1: for example the banner and its link, the delivery
   threshold in the cart, a carrier at checkout, the e-mail in Mailpit after registering or ordering,
   a setup script run a second time (`docker compose ... exec shop sh /tmp/post-install-scripts/<script>.sh`,
   with `MSYS_NO_PATHCONV=1` in Git Bash) to prove it is idempotent.
4. **E2E tests changed in the PR.** Run the suite against this stack with the address variable its
   `playwright.config.js` reads, three times in a row (W4: 3 of 3 runs pass, each within 5 minutes).
   Record each run's result and duration, and check that the JUnit or HTML report and the screenshots
   on failure are produced. A failure caused by missing data rather than by the tests is a finding
   about setup, not about the tests; say which.

Fold the results into the review: real problems become Required or Suggestions points, and what you
checked goes under **Checked** with numbers (install time, pages, viewports, error counts, run times).

## 3. Lighthouse (only if the PR changes the theme)

Optional, and only when the PR touches `shop/themes/`: `npx -y lighthouse@12 https://localhost:18443/
--chrome-flags="--headless --ignore-certificate-errors" --only-categories=performance,accessibility
--preset=desktop --output=json --output-path=<scratchpad>/lh.json --quiet`. Thresholds: Performance
≥60, Accessibility ≥85. If it does not run, write that it was not checked.

## 4. Tear down (always, even after a failure)

```sh
docker compose -p review-pr-<N> -f deploy/compose.yaml --env-file deploy/.env.example down -v --remove-orphans
docker image rm "ciocia-shop:review-pr-<N>" "ciocia-proxy:review-pr-<N>"
docker compose ls --all   # must not list review-pr-<N>
```

`down -v` is allowed here only because the volumes belong to the throwaway `review-pr-<N>` project.
It must never run on any other project.
