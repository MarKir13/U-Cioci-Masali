"""Settings shared by the whole scraper."""

from pathlib import Path

BASE_URL = "https://www.magiczne-indie.pl"

# Identifies us to the shop owner and links to the project, as the course rules require.
USER_AGENT = "UCioMasaliScraper/0.1 (university project; +https://github.com/MarKir13/U-Cioci-Masali)"

# Seconds between consecutive requests. robots.txt has no Crawl-delay, so this is our own choice.
DEFAULT_DELAY = 1.0
# Seconds to wait for the server to connect and to send data.
TIMEOUT = 20
# Extra attempts after a 5xx response or a network error.
MAX_RETRIES = 3
# Pause before the first retry, in seconds. It doubles with each next retry.
BACKOFF = 5.0

# Path from pathlib takes the absolute path of file independently from system
SCRAPER_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = SCRAPER_DIR / "scraper.log"
