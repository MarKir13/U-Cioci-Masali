"""HTTP client that is polite to the source shop.

Every request goes through `HttpClient.get`, which:
- checks robots.txt and skips disallowed URLs,
- keeps at least `delay` seconds between consecutive requests,
- retries 5xx responses and network errors with a growing pause.
"""

import logging
import time
from urllib.parse import urljoin, urlsplit

import requests
from protego import Protego

from . import config

log = logging.getLogger(__name__)

# 429 (Too Many Requests) is not a server error, but waiting and retrying is the right reaction to it too.
RETRY_STATUSES = {429, 500, 502, 503, 504}


class DisallowedByRobots(Exception):
    """The URL is blocked by robots.txt, so it was not requested."""


class HttpClient:
    def __init__(
        self,
        base_url: str = config.BASE_URL, # all config.* are imported from config.py
        user_agent: str = config.USER_AGENT,
        delay: float = config.DEFAULT_DELAY,
        timeout: float = config.TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        backoff: float = config.BACKOFF,
        session: requests.Session | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.base_url = base_url
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        # One session for the whole run: it reuses the TCP connection and keeps the cookies.
        self.session = session or requests.Session()
        # Set User-Agent for the shop knows who is visiting - set in config.py
        self.session.headers["User-Agent"] = user_agent
        # Injectable so tests can run without real waiting.
        self.sleep = sleep
        self.clock = clock
        self._robots: Protego | None = None
        self._last_request: float | None = None

    def get(self, url: str) -> requests.Response:
        """Download `url` (absolute, or relative to `base_url`).

        Raises `DisallowedByRobots` if robots.txt blocks it, and `requests.HTTPError` if the final
        response is an error.
        """
        url = urljoin(self.base_url, url)
        if not self.allowed(url):
            log.warning("Skipped, disallowed by robots.txt: %s", url)
            raise DisallowedByRobots(url)
        response = self._send(url)

        # raise_for_status() throws an error if last response is an error (4xx/5xx)
        response.raise_for_status()
        return response

    def allowed(self, url: str) -> bool:
        """Whether robots.txt lets us fetch `url`. Downloads robots.txt on first use."""
        
        # Check if request domain is different to shop original shop domain
        if urlsplit(url).netloc != urlsplit(self.base_url).netloc:
            raise ValueError(f"URL outside the source shop: {url}")
        if self._robots is None:
            self._robots = self._load_robots()
        
        # Use Protego's can_fetch method with our url with User-Agent
        return self._robots.can_fetch(url, self.user_agent)

    def _load_robots(self) -> Protego:
        # Get robots.txt from source shop
        url = urljoin(self.base_url, "/robots.txt")
        response = self._send(url)
        if response.status_code == 404:
            log.info("No robots.txt at %s, every path is allowed", url)
            return Protego.parse("")

        # Any other error stops the run: we must not crawl without knowing the rules.
        response.raise_for_status()

        robots = Protego.parse(response.text)

        # client selects the longer delay of one in config.py and one specified in robots.txt
        crawl_delay = robots.crawl_delay(self.user_agent)
        if crawl_delay and crawl_delay > self.delay:
            log.info("robots.txt asks for Crawl-delay %s s, using it instead of %s s", crawl_delay, self.delay)
            self.delay = crawl_delay

        log.info("Loaded robots.txt from %s", url)
        return robots

    def _send(self, url: str) -> requests.Response:
        """GET `url` with the delay and retries. Returns the last response, whatever its status."""
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            self._wait_for_turn()

            try: # Get respone with timeout
                response = self.session.get(url, timeout=self.timeout)

            # network exception -> log last attempt or remember the reason and retry after backoff
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == attempts:
                    log.error("Giving up on %s after %d attempts: %s", url, attempts, exc)
                    raise
                reason = type(exc).__name__

            else:
                # Response that means no retry OR last attempt on code that means retry -> automatically return response
                if response.status_code not in RETRY_STATUSES or attempt == attempts:
                    log.debug("GET %s -> %d (%d bytes)", url, response.status_code, len(response.content))
                    return response
                
                # save the status if retry
                reason = f"HTTP {response.status_code}"
            
            # Backoff that doubles
            pause = self.backoff * 2 ** (attempt - 1)
            log.warning("%s for %s (attempt %d/%d), retrying in %.0f s", reason, url, attempt, attempts, pause)
            self.sleep(pause)
        raise AssertionError("unreachable")

    def _wait_for_turn(self) -> None:
        """Sleep until at least `delay` seconds have passed since the previous request."""
        if self._last_request is not None:
            remaining = self.delay - (self.clock() - self._last_request)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request = self.clock()
