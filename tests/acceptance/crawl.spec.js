import { readFileSync } from "node:fs";
import { test, expect } from "../support/fixtures.js";
import { blockedByUrl, isDescriptionMedia, keepToShop, recordMetric } from "../support/acceptance.js";
import { StorefrontPage } from "../pages/storefront.js";

// W3 metrics: 0 responses 4xx/5xx over at least 200 pages, and 10 of 10 random products match the source shop.
// Breadth first from the home page over the shop's own links, as a customer who clicks everything would. Every
// response counts, the page's and its images', styles' and scripts'.

const MIN_PAGES = 200;
// A margin above MIN_PAGES, in case some pages are not HTML. ACCEPTANCE_PAGES changes it (a quick local try).
const MAX_PAGES = Number(process.env.ACCEPTANCE_PAGES || 250);
const MATCHED_PRODUCTS = 10;
// The crawl stops after this long even below MAX_PAGES, so the test always reaches its numbers before its own
// timeout (TEST_TIMEOUT); a crawl cut short shows as fewer pages. 250 pages took 11 minutes on Docker Desktop.
const CRAWL_BUDGET = 12 * 60_000;
const TEST_TIMEOUT = 15 * 60_000;

// Links with a file extension other than these are files (images, PDF), not pages
const PAGE_EXTENSIONS = new Set(["", ".html", ".php"]);

// Data the shop was filled from: one product per line, and the products joined into one with variants. A product
// with variants takes its name from variants.json and its price from one of its variants, so it is not compared.
const sourceProducts = new Map(
  readFileSync(new URL("../../scraper-results/products.jsonl", import.meta.url), "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .map((product) => [String(product.id), product]),
);
const variantSources = new Set(
  JSON.parse(readFileSync(new URL("../../deploy/importer/variants.json", import.meta.url), "utf8")).products.flatMap(
    (product) => product.values.map((value) => String(value.source_id)),
  ),
);

// The URL to visit for a link, or null if the crawler skips it. The query and the fragment are dropped: in this
// shop a query only sorts, filters or pages a list, or is an action (add to cart, delete, log out), which a crawler
// must not do, and a link that differs only in its query is the same page for this count. So list pages 2, 3, ...
// (?page=2) are not visited, nor the products shown only there.
function pageToVisit(href, origin) {
  let url;
  try {
    url = new URL(href);
  } catch {
    return null;
  }
  if (url.origin !== origin) return null;
  const extension = url.pathname.match(/\.[a-z0-9]+$/i)?.[0].toLowerCase() ?? "";
  if (!PAGE_EXTENSIONS.has(extension)) return null;
  return `${url.origin}${url.pathname}`;
}

// The pages still to visit, in two queues taken in turn: product pages and the others, each first in, first out.
// One queue (plain breadth first) would visit every category of the menu, about 160, before the first product, so
// the compared products would all come from the first categories' lists, and a short crawl would compare none.
// PrestaShop's product URLs end in .html ({category}/{id}-{name}.html). A wrong guess only changes the order: the
// page itself tells whether it is a product (StorefrontPage.isProductPage).
class PageQueue {
  constructor(first) {
    this.products = [];
    this.others = [];
    // Every URL ever added, so none is queued twice
    this.found = new Set();
    this.productTurn = false;
    this.add(first);
  }

  add(url) {
    if (this.found.has(url)) return;
    this.found.add(url);
    (url.endsWith(".html") ? this.products : this.others).push(url);
  }

  get waiting() {
    return this.products.length + this.others.length;
  }

  // From the queue whose turn it is, or from the other one when that is empty
  next() {
    const [first, second] = this.productTurn ? [this.products, this.others] : [this.others, this.products];
    this.productTurn = !this.productTurn;
    return first.shift() ?? second.shift();
  }
}

// What differs between a product page and its source record; an empty list when it matches
function differences(facts) {
  const source = sourceProducts.get(facts.reference);
  if (!source) return [`reference ${facts.reference} is not in scraper-results/products.jsonl`];
  const found = [];
  // Whitespace as in HTML: a run of spaces or a line break shows as one space
  const name = source.name.replace(/\s+/g, " ").trim();
  if (facts.name !== name) found.push(`name "${facts.name}", source "${name}"`);
  if (facts.price !== Number(source.price)) found.push(`price ${facts.price}, source ${source.price}`);
  if (facts.images !== source.images.length) found.push(`${facts.images} images, source ${source.images.length}`);
  return found;
}

test("crawl: no 4xx/5xx over 200 pages, and 10 random products match the source", async ({
  page,
  baseURL,
  rng,
}, testInfo) => {
  test.setTimeout(TEST_TIMEOUT);
  const origin = new URL(baseURL).origin;
  const storefront = new StorefrontPage(page);
  const blocked = await keepToShop(page, baseURL);

  // Every response with status 400 or more, with the page that was open when it came
  const errors = [];
  let current = `${origin}/`;
  page.on("response", (response) => {
    if (response.status() >= 400) {
      errors.push({ status: response.status(), url: response.url(), page: current });
    }
  });

  const queue = new PageQueue(current);
  const products = [];
  let visited = 0;
  let picked = [];
  let mismatches = [];
  // The blocked requests in two groups, set in the finally block below
  let media;
  let unexpected;
  // Stays so if anything below throws (for example a product page without its data): its row then fails
  let matched = "did not finish";
  try {
    const deadline = Date.now() + CRAWL_BUDGET;
    while (queue.waiting > 0 && visited < MAX_PAGES && Date.now() < deadline) {
      current = queue.next();
      visited += 1;
      try {
        // "load": after the page's images, styles and scripts, so their responses are counted for this page
        await page.goto(current, { waitUntil: "load" });
      } catch (error) {
        // A page that cannot be opened at all (timeout, connection reset) is an error too
        errors.push({ status: "no response", url: current, page: current, error: error.message.split("\n")[0] });
        continue;
      }
      for (const href of await storefront.linkTargets()) {
        const next = pageToVisit(href, origin);
        if (next) queue.add(next);
      }
      if (await storefront.isProductPage()) {
        products.push(await storefront.productFacts());
      }
    }

    // 10 random product pages from those the crawl opened, in a choice drawn from the seed
    const comparable = products.filter((product) => !variantSources.has(product.reference));
    picked = rng.sample(comparable, MATCHED_PRODUCTS);
    mismatches = picked
      .map((product) => ({ url: product.url, differences: differences(product) }))
      .filter((product) => product.differences.length > 0);
    matched = picked.length - mismatches.length;
  } finally {
    // Blocked either way; only the ones that are not description media are a mistake (DESCRIPTION_MEDIA)
    media = blocked.filter((request) => isDescriptionMedia(request.url));
    unexpected = blocked.filter((request) => !isDescriptionMedia(request.url));
    // Also when the crawl threw: the table then shows what was measured, instead of missing these rows.
    // The details go into the HTML report; the numbers into the acceptance table.
    await testInfo.attach("crawl.json", {
      body: JSON.stringify(
        { visited, errors, otherHosts: blockedByUrl(unexpected), media: blockedByUrl(media), picked, mismatches },
        null,
        2,
      ),
      contentType: "application/json",
    });
    recordMetric(testInfo, "Pages crawled", visited, MIN_PAGES);
    recordMetric(testInfo, "Responses 4xx/5xx while crawling", errors.length, 0, 0);
    recordMetric(testInfo, "Requests to other hosts while crawling (blocked)", unexpected.length, 0, 0);
    recordMetric(testInfo, "Description media from the source shop and YouTube (blocked)", media.length);
    recordMetric(testInfo, `Random crawled products matching the source (of ${MATCHED_PRODUCTS})`, matched, MATCHED_PRODUCTS);
  }

  // Soft: every number is checked and shown, not only the first one that fails
  expect.soft(visited, `pages crawled (${queue.found.size} found)`).toBeGreaterThanOrEqual(MIN_PAGES);
  expect.soft(errors, "responses with status 400 or more").toEqual([]);
  expect.soft(blockedByUrl(unexpected), "requests to other hosts than the shop, with the pages that made them").toEqual({});
  expect.soft(picked.length, "product pages to compare").toBe(MATCHED_PRODUCTS);
  expect.soft(mismatches, "products that differ from the source").toEqual([]);
});
