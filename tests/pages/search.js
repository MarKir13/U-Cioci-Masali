import { expect } from "../support/fixtures.js";

// PrestaShop ignores words shorter than this (PS_SEARCH_MINWORDLEN, 3 by default)
const MIN_WORD_LENGTH = 3;

const containsQuery = (name, query) => name.toLocaleLowerCase("pl").includes(query.toLocaleLowerCase("pl"));

// Search: the header field (shop/themes/ciocia/modules/ps_searchbar) and the results page, which is
// Classic's product list. Result names are read from the page's schema.org ItemList (JSON-LD), because the
// product tiles cut long names to 30 characters.
export class SearchPage {
  constructor(page) {
    this.page = page;
    this.input = page.locator('#search_widget input[name="s"]');
    this.resultTiles = page.locator("#js-product-list .product-miniature");
    this.jsonLd = page.locator('script[type="application/ld+json"]');
  }

  // As a customer does it: type in the header field, press Enter
  async searchFromHeader(query) {
    await this.input.fill(query);
    await this.input.press("Enter");
    await expect(this.page.locator("body#search"), `search results page for "${query}"`).toBeVisible();
    await expect(this.input).toHaveValue(query);
  }

  // Full names of the results on the open results page, in the order shown
  async resultNames() {
    const names = await this.jsonLd.evaluateAll((scripts) => {
      const list = scripts.map((s) => JSON.parse(s.textContent)).find((data) => data["@type"] === "ItemList");
      // The shop HTML-escapes the names inside the JSON (an apostrophe is &#039;); let the browser decode them
      const decode = (text) => {
        const area = globalThis.document.createElement("textarea");
        area.innerHTML = text;
        return area.value;
      };
      return (list?.itemListElement ?? []).map((item) => decode(item.name));
    });
    // The list and the tiles must describe the same results
    await expect(this.resultTiles, "result tiles = results in the ItemList").toHaveCount(names.length);
    return names;
  }

  // A word of `productName` for which every result has the word in its name, and the product itself is
  // among the results. PrestaShop also searches descriptions, categories and tags, so many words find
  // products that have them elsewhere; those are passed over. Words are tried in an order drawn from the
  // seed, each through the results page itself. Returns null when no word of the name qualifies.
  async queryFor(productName, rng) {
    const words = [...new Set(productName.match(/[\p{L}\p{N}]+/gu) ?? [])].filter(
      (word) => word.length >= MIN_WORD_LENGTH,
    );
    const searchUrl = await this.page.evaluate(() => globalThis.prestashop.urls.pages.search);
    for (const word of rng.sample(words, words.length)) {
      const url = new URL(searchUrl);
      url.searchParams.set("s", word);
      await this.page.goto(url.href);
      const names = await this.resultNames();
      if (names.includes(productName) && names.every((name) => containsQuery(name, word))) {
        return word;
      }
    }
    return null;
  }

  // Results whose name does not contain the query; the step expects none
  static namesWithout(names, query) {
    return names.filter((name) => !containsQuery(name, query));
  }
}
