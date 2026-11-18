// Any page of the shop, as the acceptance crawler (tests/acceptance/crawl.spec.js) reads it: its links, and on a
// product page what the lecturer compares with the source shop (name, price, number of images).
// The product page is Classic's, kept by the ciocia theme: #product-details with data-product, the price in
// .current-price-value, one .js-thumb per image.
export class StorefrontPage {
  constructor(page) {
    this.page = page;
    this.links = page.locator("a[href]");
    this.productBody = page.locator("body#product");
    this.productDetails = page.locator("#product-details");
    this.title = page.locator("h1").first();
    this.price = page.locator(".current-price-value").first();
    this.thumbnails = page.locator(".js-thumb");
  }

  // Every link target on the page, as absolute URLs (the browser resolves relative ones)
  async linkTargets() {
    return this.links.evaluateAll((links) => links.map((a) => a.href));
  }

  async isProductPage() {
    return (await this.productBody.count()) > 0;
  }

  // { reference, name, price, images } of the open product page. The importer stores the product's ID in the
  // source shop as its reference (deploy/importer/importer/steps.py), and data-product carries it.
  async productFacts() {
    const product = JSON.parse(await this.productDetails.getAttribute("data-product"));
    return {
      url: this.page.url(),
      reference: String(product.reference),
      name: (await this.title.innerText()).trim(),
      // The price as a number in its content attribute, so no "1 234,56 zł" to parse
      price: Number(await this.price.getAttribute("content")),
      images: await this.thumbnails.count(),
    };
  }
}
