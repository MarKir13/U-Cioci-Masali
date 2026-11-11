# Scraper

Downloads categories, products and images from [magiczne-indie.pl](https://www.magiczne-indie.pl) for the
U Cioci Masali shop. Data is used for teaching purposes only. Findings about the source shop are in
[docs/scraper-recon.md](../docs/scraper-recon.md).

## Setup

Requires Python 3.12. All commands are run from this directory (`scraper/`).

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

## Usage

```sh
python -m scraper --help
python -m scraper crawl                                         # full run into ../scraper-results/ (resumable)
python -m scraper crawl --limit 5                               # test run: at most 5 new pages per stage
python -m scraper images                                        # download and fit the product images (resumable)
python -m scraper images --limit 5                              # test run: at most 5 new images
python -m scraper fetch /8-kosmetyki                            # download one page, print status and size
python -m scraper fetch /8-kosmetyki -o tests/fixtures/x.html   # save it, e.g. as a test fixture
python -m scraper schema                                        # write ../scraper-results/schema.json
```

Options before the command: `--delay SECONDS` (default 1.0, minimum 0.5, maximum 3600), `-v` for DEBUG messages in the console.
Everything, including DEBUG messages, is also written to `scraper.log` (not committed).

## Crawl

`python -m scraper crawl` runs these stages in order ([scraper/crawl.py](scraper/crawl.py)). Why the data comes from
these pages: [ADR 0004](../docs/adr/0004-crawl-sources-and-category-assignment.md).

1. **robots.txt** is loaded first. If that fails, the run stops before requesting any other page.
2. **Sitemap** (`/1_index_sitemap.xml` and the sitemap it lists): product and category URLs. Downloaded on every run.
   If it fails, the run stops.
3. **Categories:** each category page. It is also page 1 of the category's product listing, so the product URLs on it
   are kept too.
4. **Full listings:** Na prezent (458) and Nowości (50) are walked to the last page with `?page=N`, because no
   product has them as its default category. Other listings stop at page 1 (`FULL_LISTING_CATEGORY_IDS` in
   [config.py](scraper/config.py)).
5. **Products:** every product from the sitemap, plus any product seen only on a listing. The categories from the
   product page (default category and its breadcrumb) are merged with the listings it was seen on, without duplicates.
6. **Report:** a warning for each category that lists products in the source shop but has none saved, and for
   category ids that products use but that were not saved.

A page that fails (blocked by robots.txt, HTTP error, network error, parse or validation error) is logged and skipped,
and the run goes on. Any other exception is a bug: the run stops with a traceback, and everything saved so far is kept.
At the end of each stage the log shows how many records were saved, already saved and failed.

### Results

| File in `scraper-results/` | Contents | Written |
|---|---|---|
| `categories.json` | List of categories (`Category` in the schema) | Whole file again after each new category |
| `listings.json` | Per category id: product URLs seen on its listing, and `next_page` (`null` once finished) | Whole file again after each listing page |
| `products.jsonl` | One product per line (`Product` in the schema) | One line appended per product |

All files are UTF-8 with Polish characters as they are (`ensure_ascii=False`). Whole files are written to a `.tmp` file
first and then renamed over the old one, so Ctrl+C leaves either the old or the new version. A product line is written
in one call; a last line cut off anyway is removed on the next start and that product is downloaded again.

### Stopping and resuming

Stop with Ctrl+C at any time and run the same command again. Saved categories and products, and finished listings,
are skipped (the log says how many). An unfinished listing continues from its `next_page`. Only robots.txt and the
sitemap are downloaded again. Pages that failed are tried again.

To start from scratch, delete the three files above.

### Page cache

Every downloaded category, listing and product page is also saved, gzipped, in `scraper/cache/` (not committed;
about 40 KB per page, so about 90 MB for a full run). Pages found there are not downloaded again, so after a parser fix you can delete
`products.jsonl` and rebuild it without the network. Use `--no-cache` to turn this off, and delete the folder to
download fresh pages.

## Images

`python -m scraper images` (run after `crawl`) downloads every image listed in `products.jsonl` and fits it to the
store's limits ([scraper/images.py](scraper/images.py)). The source URLs are the `product_main_2x` size (1440 px), taken
from the product pages by the crawl. Images are fetched through the same polite `HttpClient` as pages.

Each image is saved as `scraper-results/images/<product id>-<number>.jpg` (`images/` is in `.gitignore`: the full set
goes to a GitHub Release). Its path, relative to `scraper-results/`, is written to `local_path` of the image in
`products.jsonl`.

| Rule | Value |
|---|---|
| Longer side | 800-1600 px. A larger picture is scaled down to 1600; a picture is never enlarged |
| Format | JPEG. Transparent areas become white |
| Size | At most 300 000 bytes. The JPEG quality is lowered from 90 to 40 (binary search) until the file fits; if quality 40 is still too big, the picture is shrunk in 10% steps, but not below 800 px |

A source image is not saved and is reported (a warning in the log, a line in the final summary and an entry in
`scraper-results/image_problems.json`) when:

- its longer side is below 800 px (`TooSmallImage`),
- it cannot be read, e.g. the download was cut off or the server sent HTML (`CorruptImage`),
- it cannot get under 300 KB even at 800 px and quality 40 (`TooLargeImage`).

`image_problems.json` is also the list of URLs a later run does not ask for again, since the same bytes would fail
again. Download errors (HTTP error, network error) are not remembered, so they are tried again. At the end the log
lists products that have no usable image at all, because the project needs at least one for each product.

Stopping and resuming works like the crawl: a file is written under its final name only when complete, so an image
that is on disk is skipped, and `products.jsonl` is rewritten (to a `.tmp` file, then renamed) every 50 downloaded
images and on Ctrl+C. To fetch an image again, delete its file. Do not run `crawl` and `images` at the same time:
both write `products.jsonl`.

Expect about one image per second (`--delay`), so the whole set takes roughly an hour.

## Politeness

All requests go through `HttpClient` in [scraper/http_client.py](scraper/http_client.py):

- `User-Agent` names the project and links to this repository.
- `robots.txt` is downloaded once and checked before every request. Disallowed URLs are skipped and logged.
  If robots.txt cannot be read (other than 404) or redirects outside the shop, the run stops.
- At least `--delay` seconds from the end of one request to the start of the next, or the robots.txt
  `Crawl-delay` if it is longer. A `Crawl-delay` above 3600 s stops the run.
- Redirects are followed by the client itself: every hop is checked against the shop's domain and robots.txt
  and waits for the delay. Malformed URLs are reported as errors instead of crashing the run.
- URLs are normalized the way `requests` sends them (`/a/../b` and `/a/%2e%2e/b` become `/b`) before these checks,
  so the checked URL is exactly the URL that is requested.
- 5xx, 429 and network errors (also a connection dropped mid-download) are retried 3 times, with pauses of 5, 10
  and 20 s. Other 4xx errors are not retried.
- A redirect back to a URL already visited for the same page is reported as a redirect loop (`TooManyRedirects`).
  That includes a redirect to the very same URL, which some shops send once to set a cookie. In a crawl the page is
  logged as `Could not download ...: Redirect loop at ...` and skipped, so if the source shop ever does this it shows
  in `scraper.log`.

## Data model

[scraper/models.py](scraper/models.py) defines `Category` and `Product` with pydantic. Pass every scraped record through
`validate_record()`: it returns the validated record, or writes the reason and the page URL to `scraper.log` and returns
`None`, so one bad page does not stop the run and is not saved.

- Prices have at most two decimal places and 12 digits, and are saved as JSON strings (`"64.72"`). Parsers must round
  raw values such as `69.58764` first. Other spellings of a valid price are normalized: `"69.590000"` is saved as
  `"69.59"` and `"1e2"` as `"100"`.
- `price` cannot exceed `regular_price`. `has_discount` comes from the page and is not derived from the prices.
- `category_ids`, `family` and `images` (compared by `source_url`) cannot contain duplicates. A product with a duplicate
  is rejected, so parsers and the crawl have to remove them before validation.
- Weight stays as raw text (`"250.000000"`, `"g"`), because the unit on the source page is unreliable.
- A description needs visible text: `<p>&nbsp;</p>` counts as empty.

After changing a model, run `python -m scraper schema` and commit the new `schema.json`. A test fails if it is out of date.

## Parsers

[scraper/parsers.py](scraper/parsers.py) turns downloaded text into data. The functions do not use the network: the crawl downloads the pages and passes their text in.

- `parse_sitemap_index(xml)` returns the URLs of the sitemaps listed in `1_index_sitemap.xml`.
- `parse_sitemap(xml)` returns `(product_urls, category_urls)`. Products are `/{id}-{slug}.html` and categories
  `/{id}-{slug}`, right after the domain. Home, CMS (`/content/...`), module (`?controller=...`) and brand
  (`/brand/...`) pages and image URLs are skipped. `<![CDATA[...]]>` in `<loc>` is removed by the XML parser itself.
- `parse_category(url, html)` returns a `Category`. The id comes from the URL, the name from `h1.page-title-section`
  and the parent from the second-to-last item of the JSON-LD `BreadcrumbList` (`None` when that item is the home
  page). A page without the name or the breadcrumb raises `ValueError` with the page URL, so the crawl can log it and
  go on. A record that fails validation is logged by `validate_record()` and returned as `None`.
- `children_by_parent(categories)` returns `{parent_id: [children]}`, with top-level categories under `None`.
- `missing_parents(categories)` returns the categories whose parent is not in the list.
- `product_urls(url, html)` returns absolute, unique product URLs from a product list page.
- `next_page_url(url, html)` returns the absolute URL of the next page of results, or `None` if there is no next page.
- `parse_product(url, html)` returns a `Product` from the `data-product` JSON and the JSON-LD blocks. It raises
  `ValueError` (with the page URL) when `data-product` is missing or not valid JSON.
  - Both prices go through `round_price()`: two decimal places, halves up (`2.675` becomes `2.68`; `round(float(...), 2)`
    would give `2.67` and could put `price` above `regular_price`). A value that is not a number is passed on as it is,
    so validation rejects the product and logs the URL.
  - Weight is optional. A weight without a unit is skipped with a warning and the product is kept.

## Tests

```sh
python -m pytest
```

Tests do not use the network. HTML pages saved from the source shop are in [tests/fixtures/](tests/fixtures/).
Every saved page contains PrestaShop's `static_token` and `token` values, which the secret scan flags. Replace them
with `REMOVED` before committing a new fixture.

## Layout

| Path | Contents |
|---|---|
| `scraper/__main__.py` | Command line interface |
| `scraper/config.py` | Base URL, User-Agent, delay, timeouts |
| `scraper/http_client.py` | Polite HTTP client |
| `scraper/crawl.py` | Full run: stages, saving and resuming, page cache |
| `scraper/images.py` | Image download, resizing and recompression (Pillow), `local_path` |
| `scraper/logging_config.py` | Logging to the console and `scraper.log` |
| `scraper/models.py` | Schema of the results and validation of records |
| `scraper/parsers.py` | Parsers of the sitemap, category, listing and product pages (no network) |
| `tests/` | Unit tests and saved pages (`fixtures/`) |
