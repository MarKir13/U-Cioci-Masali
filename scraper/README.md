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
python -m scraper fetch /8-kosmetyki                            # download one page, print status and size
python -m scraper fetch /8-kosmetyki -o tests/fixtures/x.html   # save it, e.g. as a test fixture
python -m scraper schema                                        # write ../scraper-results/schema.json
```

Options before the command: `--delay SECONDS` (default 1.0, minimum 0.5, maximum 3600), `-v` for DEBUG messages in the console.
Everything, including DEBUG messages, is also written to `scraper.log` (not committed).

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

## Data model

[scraper/models.py](scraper/models.py) defines `Category` and `Product` with pydantic. Pass every scraped record through
`validate_record()`: it returns the validated record, or writes the reason and the page URL to `scraper.log` and returns
`None`, so one bad page does not stop the run and is not saved.

- Prices have at most two decimal places and are saved as JSON strings (`"64.72"`). Parsers must round raw values
  such as `69.58764` first.
- Weight stays as raw text (`"250.000000"`, `"g"`), because the unit on the source page is unreliable.
- A description needs visible text: `<p>&nbsp;</p>` counts as empty.

After changing a model, run `python -m scraper schema` and commit the new `schema.json`. A test fails if it is out of date.

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
| `scraper/logging_config.py` | Logging to the console and `scraper.log` |
| `scraper/models.py` | Schema of the results and validation of records |
| `tests/` | Unit tests and saved pages (`fixtures/`) |
