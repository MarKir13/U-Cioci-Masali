# 0001. Results schema and validation with pydantic

- Status: Accepted
- Date: 2026-11-04
- Authors: Piotr Bortnowski

## Context

Requirement W2 asks for scraped data validated against a schema, with errors written to a log. The data goes into
`scraper-results/` and later into the shop, where names, descriptions, prices and VAT rates must match the source.

Two things had to be decided:

1. **How to define the schema and validate records.** A full run covers 2167 products, so one bad page must be logged
   and skipped rather than stop the run. Everyone on the team has to be able to explain and change the code live.
2. **How to store prices.** The source gives raw floats: `price_without_reduction` is `69.58764` on a product whose
   shop page shows 69.59 zł, and `272.989999` on one whose `price_amount` is `272.99`.

## Options considered

### Schema and validation

**pydantic models (chosen)**

- Pro: one definition gives validation, typed objects for the parser and crawl code, and the JSON schema.
- Pro: errors name the exact field (`images.0.source_url`), which makes short log entries easy to write.
- Con: a new dependency that brings four more packages, including a compiled core.
- Con: `HttpUrl` fields hold URL objects rather than strings, so code that compares URLs has to call `str()`.

**Hand-written JSON schema, checked with the `jsonschema` library**

- Pro: the schema file is the single source of truth and is readable without Python.
- Con: records stay plain dictionaries, so a misspelled key shows up only when the record is validated.
- Con: rules such as "the description has visible text" do not fit in JSON Schema and would need separate code.

**Standard library `dataclasses` with hand-written checks**

- Pro: no new dependency, and every rule is plain Python.
- Con: type conversion, collecting all errors of a record and nested validation would all be our own code to test.
- Con: the JSON schema would be written by hand and could drift from the checks.

### Price format

**`Decimal` with at most two decimal places, saved as a JSON string (chosen)**

- Pro: an unrounded value such as `69.58764` is rejected, so a parser that forgets to round fails visibly.
- Pro: `NaN` and `Infinity` are rejected.
- Con: prices in `products.jsonl` are strings (`"64.72"`), which a reader might not expect.

**`float`, saved as a JSON number**

- Pro: simple, and the JSON looks natural.
- Con: pydantic accepts `69.58764` and `Infinity` under `gt=0`, so these need extra checks.

## Decision

Use pydantic models in `scraper/scraper/models.py`. All records pass through `validate_record()`, which returns the
validated record, or logs the reason with the page URL and returns `None`. `scraper-results/schema.json` is generated
from the models, never edited by hand.

Store prices as `Decimal` with at most two decimal places, because keeping prices identical to the source matters more
than a natural-looking JSON type. Parsers round the raw values first.

## Consequences

- Parsers (#7, #8, #9) have to produce the exact field names and round prices themselves.
- The crawl (#10) has to call `validate_record()` for every record and save only what it returns.
- The import script has to read prices as strings and convert them to decimals, not assume JSON numbers.
- After a model change, `python -m scraper schema` has to be run. A test fails if the committed file is out of date.
- `schema.json` is weaker than the models: its price pattern accepts `"0"`, and the visible text rule is missing. It
  documents the file format. The models remain the actual check.
- An invalid product is missing from the results until the parser is fixed. The rules have been tried on only 3 saved
  product pages, so the full run in #12 may show that some need changing.
