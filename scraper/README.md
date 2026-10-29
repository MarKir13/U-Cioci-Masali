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
```

Options before the command: `--delay SECONDS` (default 1.0), `-v` for DEBUG messages in the console.
Everything, including DEBUG messages, is also written to `scraper.log` (not committed).

## Politeness

All requests go through `HttpClient` in [scraper/http_client.py](scraper/http_client.py):

- `User-Agent` names the project and links to this repository.
- `robots.txt` is downloaded once and checked before every request. Disallowed URLs are skipped and logged.
  If robots.txt cannot be read (other than 404), the run stops.
- At least `--delay` seconds between requests, or the robots.txt `Crawl-delay` if it is longer.
- 5xx, 429 and network errors are retried 3 times, with pauses of 5, 10 and 20 s. Other 4xx errors are not retried.

## Tests

```sh
python -m pytest
```

Tests do not use the network. HTML pages saved from the source shop are in [tests/fixtures/](tests/fixtures/).

## Layout

| Path | Contents |
|---|---|
| `scraper/__main__.py` | Command line interface |
| `scraper/config.py` | Base URL, User-Agent, delay, timeouts |
| `scraper/http_client.py` | Polite HTTP client |
| `scraper/logging_config.py` | Logging to the console and `scraper.log` |
| `tests/` | Unit tests and saved pages (`fixtures/`) |
