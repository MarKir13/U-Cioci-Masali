"""Settings shared by the whole scraper."""

from pathlib import Path

BASE_URL = "https://www.magiczne-indie.pl"

# Identifies us to the shop owner and links to the project, as the course rules require.
USER_AGENT = "UCioMasaliScraper/0.1 (university project; +https://github.com/MarKir13/U-Cioci-Masali)"

# Seconds between consecutive requests. robots.txt has no Crawl-delay, so this is our own choice.
DEFAULT_DELAY = 1.0
# Minimal delay possible to be set in seconds
MIN_DELAY = 0.5
# Maximal delay in seconds, for --delay and robots.txt Crawl-delay. A longer one is no longer a crawl,
# and time.sleep() overflows on values around 1e10.
MAX_DELAY = 3600
# Seconds to wait for the server to connect and to send data.
TIMEOUT = 20
# Extra attempts after a 5xx response or a network error.
MAX_RETRIES = 3
# Pause before the first retry, in seconds. It doubles with each next retry.
BACKOFF = 5.0
# Redirects followed for one page before giving up.
MAX_REDIRECTS = 10
# Redirects followed for robots.txt. RFC 9309 asks crawlers to follow at least five.
MAX_ROBOTS_REDIRECTS = 5

# Path from pathlib takes the absolute path of file independently from system
SCRAPER_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = SCRAPER_DIR / "scraper.log"
RESULTS_DIR = SCRAPER_DIR.parent / "scraper-results"
SCHEMA_FILE = RESULTS_DIR / "schema.json"

# Crawl results (see docs/adr/0003-crawl-sources-and-category-assignment.md)
CATEGORIES_FILE = RESULTS_DIR / "categories.json"
# One product per line, appended as soon as it is parsed, so an interrupted run loses nothing saved
PRODUCTS_FILE = RESULTS_DIR / "products.jsonl"
# Product ids found on category listings, and where each unfinished listing continues
LISTINGS_FILE = RESULTS_DIR / "listings.json"
# Downloaded pages, gzipped, so a parser fix can be re-run without the network. Not committed.
CACHE_DIR = SCRAPER_DIR / "cache"

# Sitemap index named in the source shop's robots.txt and recon notes
SITEMAP_INDEX = "/1_index_sitemap.xml"
# Na prezent and Nowości: products never have them as their default category, so they appear neither
# in the product's data nor in its breadcrumb. Their listings are walked to the last page.
FULL_LISTING_CATEGORY_IDS = (458, 50)
