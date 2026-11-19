import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";

// Shared code of the acceptance specs (tests/acceptance/, run with npm run acceptance).

// The console message Chromium writes for a request stopped by keepToShop(). Nothing else in a headless browser
// blocks requests "by client" (there is no ad blocker), so the specs can leave exactly these messages out of the
// console errors: the blocked requests are counted on their own.
export const BLOCKED_MESSAGE = "net::ERR_BLOCKED_BY_CLIENT";

// Stops every request to another host than the shop's, and returns the list of what it stopped, as
// { url, page }: the address, and the shop page that asked for it (the product whose description needs fixing).
// Imported product descriptions can still embed images from the source shop, and AGENTS.md rule 7 says tests
// never touch it. data: and blob: URLs never reach the network, so route() does not see them.
export async function keepToShop(page, baseURL) {
  const origin = new URL(baseURL).origin;
  const blocked = [];
  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (new URL(url).origin === origin) {
      return route.continue();
    }
    // A page's images load after the browser has switched to it, so page.url() is already that page
    blocked.push({ url, page: page.url() });
    return route.abort("blockedbyclient");
  });
  return blocked;
}

// The blocked requests grouped by address, each with the pages that asked for it: a short list to read, even when
// one image is on many pages
export function blockedByUrl(blocked) {
  const byUrl = new Map();
  for (const { url, page } of blocked) {
    byUrl.set(url, [...new Set([...(byUrl.get(url) ?? []), page])]);
  }
  return Object.fromEntries(byUrl);
}

// One row for the acceptance table: a line "name<TAB>value<TAB>min<TAB>max" in metrics.tsv, in the output folder of
// the run (acceptance-report/test-results/, which Playwright empties when a run starts). acceptance.yml passes
// each line to .github/scripts/acceptance-results.sh add, which decides pass or fail; "-" means no limit.
export function recordMetric(testInfo, name, value, min = "-", max = "-") {
  mkdirSync(testInfo.project.outputDir, { recursive: true });
  appendFileSync(path.join(testInfo.project.outputDir, "metrics.tsv"), `${[name, value, min, max].join("\t")}\n`);
}
