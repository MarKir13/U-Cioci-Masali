# 0014. Brand pages: scraped text, FAQ storage and import into manufacturers

- Status: Accepted
- Date: 2026-11-23
- Authors: Jakub Bugnacki

## Context

A brand page of the source (`/brand/3-himalaya`) is more than a product list. Above the grid it has an H1, an intro,
sections with lists and bold text, and for Himalaya an FAQ built as an accordion. Our scraper kept only the brand name
of each product, so the manufacturer pages that the importer creates (ADR 0008) have no title, text or FAQ.

Looking at the 76 brand pages of the source (all brands of `products.jsonl` are linked from `/producenci`):

- 9 pages have any text, the other 67 only an H1. Only Himalaya has the structured intro + sections + FAQ; Dabur has
  one paragraph; Hari Tea and Shoti Maa have long texts written in the source's editor (`<address>`, `<span>`,
  `<br>`, text outside any paragraph; Shoti Maa has one image).
- The meta tags are filled for some brands (Himalaya, Satya, Yogi Tea ...) and empty for most. The page's `<title>`
  differs from its H1 and carries the source shop's name ("... | Magiczne Indie").
- The text links to source categories (Himalaya links to `/335-suplementy-himalaya-herbals-himalaya-herbs`), and in
  other brands to products and articles.

The task asks for the HTML to be safe (only `h2`, `h3`, `p`, `ul`, `li`, `strong`, `a`; no scripts, styles or
`on*=`), for the importer to stay idempotent, and for the FAQ to be stored so that the theme (#107) can draw an
accordion. PrestaShop cleans manufacturer text with HTMLPurifier on save, so what we send must survive that.

## Options considered

**FAQ as `<details><summary>` inside the description.**

- Pro: an accordion without JavaScript; the theme has nothing to do.
- Con: we could not check that PrestaShop's HTMLPurifier keeps `details` and `summary`. If it drops them, the
  question and the answer run together in one paragraph, and the shop shows it wrong without any error.
- Con: markup of the page's presentation inside the data.

**A separate field for the FAQ (a module table or a custom Webservice resource, like ADR 0013).**

- Pro: the theme gets structured data.
- Con: a new table, resource and permission just for one brand (only Himalaya has an FAQ), and one more thing to
  back up and restore (ADR 0012).

**The FAQ kept structured in `brands.json`, and written to the description as plain headings (chosen).**

- Pro: `brands.json` keeps `faq` as a list of questions and answers, so any later use (a module, JSON-LD
  `FAQPage`) needs no parsing.
- Pro: in the manufacturer's `description` the FAQ is an `<h2>` and an `<h3>` + `<p>` per question. These tags are the
  ones the source uses, so they survive the purifier; the brand text reads correctly even if the theme does nothing.
- Con: the theme has to build the accordion: the FAQ is the last `<h2>` and the pairs after it. That is a convention,
  documented in the importer README, not a marked-up block.

**Where the intro goes.** The source has the intro and the sections in two containers. `description` holds both (one
block, in the order of the page); `short_description` gets only the first paragraph as plain text. The theme can show
the short text above the product list and the rest below, or the description alone.

## Decision

- `scraper/brands.py` and the command `python -m scraper brands` read the brands from `products.jsonl`, find their
  pages on `/producenci` and save `scraper-results/brands.json` (`Brand` in the schema). One record per brand, resumable,
  through the same polite client. A brand without a page is saved with its name only and reported.
- The HTML is cleaned in the scraper (`scraper/sanitize.py`), before it is saved, so `brands.json` and the repository
  hold no scripts, styles or event handlers, and the model rejects them as a second check. The editor's markup becomes
  paragraphs; images are dropped.
- The FAQ is stored as `faq` (+ `faq_title`) in `brands.json`, and the importer appends it to the manufacturer's
  `description` as headings. Nothing about the accordion is stored.
- The importer (`import_manufacturers`) writes `description`, `short_description`, `meta_title` and `meta_description`
  through the Webservice API, comparing the visible text so that a second run changes nothing. Links to source
  categories are mapped by category ID to our shop; other links to the source become plain text.
- A manufacturer has no field for an H1, and the theme prints its `meta_title` as the page heading (and the browser
  uses it as the tab title). The importer therefore sends the scraped `title` (the page's H1) as `meta_title`. The
  scraped `meta_title` (the source's `<title>`) stays in `brands.json` but does not reach the shop: it would put the
  source shop's name in our heading and not match the source's H1. `meta_description` is sent as scraped.
- Links to the source's own host keep no query string or fragment (`sanitize.py`): the editor's preview links carry
  its back-office token (`adtoken`), the name of its admin folder (`ad`) and an employee id, and none of that belongs
  in the repository.
- Brands are matched by name without case. "Himalaya" and "Himalaya's Dreams" stay two manufacturers.

## Consequences

- The brand page is drawn by `manufacturer.tpl` (issue #107): the manufacturer's meta title as the heading, then the
  description. `custom.js` (`buildFaq`) turns the FAQ into an accordion: when the last `<h2>` of the description is
  followed only by `<h3>` questions that end with "?" and their answers (`<p>`, `<ul>`), each pair becomes a
  `<details>`. A description with ordinary sections and no such block is left as it is, and without JavaScript the
  FAQ stays plain headings. A question that does not end with "?" keeps the whole block unchanged.
- If the theme later wants a real accordion without JavaScript, `details` can be tried in the importer in one place
  (`mapping.faq_html`) once someone has checked it against the shop's purifier. `brands.json` would not change.
- Images in brand texts (Shoti Maa has one) are not imported. The text is the same, the picture is missing.
- A brand page that changes on the source is not refreshed by a resumed run (like products): delete `brands.json` to
  scrape again.
- The cleaned text is limited to what the source's pages showed on the day of the scrape. A new tag in the source
  (a table, say) is removed with its markup and its text stays.
