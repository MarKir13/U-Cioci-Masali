# scraper-results

What the scraper (`scraper/`) saves, all UTF-8. How each file is made is in [scraper/README.md](../scraper/README.md).

| File | Contents |
|---|---|
| `categories.json` | Categories and subcategories (`Category` in `schema.json`) |
| `products.jsonl` | One product per line (`Product`), with the source URLs of its images |
| `brands.json` | One record per brand of the products (`Brand`): the text of its page on the source |
| `schema.json` | JSON Schema of the three record types above; the importer validates against it |
| `rejected.json`, `listings.json`, `image_problems.json` | Products left out, listing progress, unusable images |
| `verification-report.md` | Result of `python -m scraper verify` |
| `sample-images/` | 20 sample images (the full set is a GitHub Release asset, not committed) |

## brands.json

A JSON list of brands, sorted by name, written by `python -m scraper brands`. The source's brand pages are
`/brand/<id>-<slug>`; the importer writes each record into the shop's manufacturer of the same name (ADR 0014).

```json
{
  "name": "Himalaya",
  "url": "https://www.magiczne-indie.pl/brand/3-himalaya",
  "title": "Himalaya Herbals – oryginalne suplementy i kosmetyki ajurwedyjskie",
  "description": "<p>Szukasz sklepu z oryginalną Himalaya Herbals? …</p>\n<h2>Czym jest Himalaya Herbals</h2>\n…",
  "faq_title": "Najczęstsze pytania o Himalaya",
  "faq": [{"question": "Na co jest Himalaya?", "answer": "<p>…</p>"}],
  "meta_title": "Himalaya Herbals – sklep online | Suplementy i kosmetyki | Magiczne Indie",
  "meta_description": "Oryginalne Himalaya Herbals z Indii – …"
}
```

- Everything except `name` is optional (`null`, or `[]` for `faq`). A brand without a page on the source has only `name`;
  most brand pages have a title but no description.
- `description` and the FAQ answers are HTML with only `h2`, `h3`, `p`, `ul`, `li`, `strong` and `a` (absolute
  `href`). They hold no `<script>`, `<style>` or `on*=` attribute.
- The FAQ is not part of `description`. Himalaya, the only brand with one, has 4 questions.
- Himalaya (46 products) and Himalaya's Dreams (9 products) are different brands.
- The data is scraped for teaching purposes only; the shop must not be publicly available.
