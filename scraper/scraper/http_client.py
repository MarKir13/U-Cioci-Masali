"""HTTP client that is polite to the source shop.

Every request goes through `HttpClient.get`, which:
- checks robots.txt and skips disallowed URLs,
- keeps at least `delay` seconds between consecutive requests,
- manually handles 3xx responses (redirects) for both robots.txt and normal sites,
- retries 5xx responses and network errors with a growing pause.
"""

import logging
import time
from urllib.parse import urldefrag, urljoin, urlsplit

import requests
from protego import Protego

from . import config

log = logging.getLogger(__name__)

# 429 (Too Many Requests) is not a server error, but waiting and retrying is the right reaction to it too.
RETRY_STATUSES = {429, 500, 502, 503, 504}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
DEFAULT_PORTS = {"http": 80, "https": 443}


class SkippedURL(Exception):
    """Base class: the URL was deliberately not requested."""


class DisallowedByRobots(SkippedURL):
    """The URL is blocked by robots.txt, so it was not requested."""


class OutsideShop(SkippedURL):
    """The URL (or a redirect target) points outside the source shop."""


# Helper function to check if url is inside the shop
def _origin(url: str) -> tuple[str, str, int | None]:
    """(scheme, host, port) with the default port filled in,
    so https://sklep.pl and https://sklep.pl:443 are the same origin."""
    p = urlsplit(url)
    scheme = p.scheme.lower()
    return scheme, p.hostname or "", p.port or DEFAULT_PORTS.get(scheme)


def _raise_for_status(response: requests.Response) -> None:
    """Like `response.raise_for_status()`, but a 3xx that was not followed is an error too."""
    if 300 <= response.status_code < 400:
        log.warning("HTTP %d without a usable redirect for %s", response.status_code, response.url)
        raise requests.HTTPError(
            f"{response.status_code} Redirect without a usable Location for url: {response.url}",
            response=response,
        )
    # raise_for_status() throws an error if the response is an error (4xx/5xx)
    response.raise_for_status()


class HttpClient:
    def __init__(
        self,
        base_url: str = config.BASE_URL,  # all config.* are imported from config.py
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

        Raises `DisallowedByRobots` if robots.txt blocks it, `OutsideShop` if it (or a redirect)
        leads outside the shop, `TooManyRedirects` when the redirect limit is exceeded, and
        `requests.HTTPError` if the final response is an error.
        """
        url = urldefrag(urljoin(self.base_url, url)).url
        history: list[requests.Response] = []
        seen: set[str] = set()

        # Redirects are followed here, not by requests: each hop goes through
        # allowed() (domain + robots.txt) and _send() (delay + retries) like a new request.
        for _ in range(config.MAX_REDIRECTS + 1):
            # Save and check visited urls
            if url in seen:
                raise requests.TooManyRedirects(f"Redirect loop at {url}")
            seen.add(url)

            if not self._in_shop(url):
                log.warning("Skipped, outside the source shop: %s", url)
                raise OutsideShop(url)

            if not self.allowed(url):
                log.warning("Skipped, disallowed by robots.txt: %s", url)
                raise DisallowedByRobots(url)
            response = self._send(url)

            location = response.headers.get("Location")
            if response.status_code not in REDIRECT_STATUSES or not location:
                response.history = history
                _raise_for_status(response)
                return response

            # Only redirects (3xx) go here.
            # Location may be relative; the fragment (#...) is never sent to the server.
            next_url = urldefrag(urljoin(response.url, location)).url
            log.info("Redirect %d: %s -> %s", response.status_code, url, next_url)
            history.append(response)
            response.close()  # the body of a 30x is not needed
            url = next_url

        raise requests.TooManyRedirects(f"More than {config.MAX_REDIRECTS} redirects")

    def allowed(self, url: str) -> bool:
        """Whether robots.txt lets us fetch `url`. Downloads robots.txt on first use."""
        # Check if request domain is different to shop original shop domain
        if not self._in_shop(url):
            raise OutsideShop(url)

        if self._robots is None:
            self._robots = self._load_robots()

        # Use Protego's can_fetch method with our url with User-Agent
        return self._robots.can_fetch(url, self.user_agent)

    def _in_shop(self, url: str) -> bool:
        """Same scheme, host and port as base_url."""
        return _origin(url) == _origin(self.base_url)

    def _load_robots(self) -> Protego:
        # Get robots.txt from source shop
        url = urljoin(self.base_url, "/robots.txt")
        for _ in range(config.MAX_ROBOTS_REDIRECTS + 1):
            response = self._send(url)
            location = response.headers.get("Location")
            if response.status_code not in REDIRECT_STATUSES or not location:
                break

            # Only valid redirects go here and the loop is continuing
            url = urldefrag(urljoin(response.url, location)).url
            log.info("robots.txt redirected to %s", url)
        else:
            raise requests.TooManyRedirects(f"robots.txt: more than {config.MAX_ROBOTS_REDIRECTS} redirects")

        if response.status_code == 404:
            log.info("No robots.txt at %s, every path is allowed", url)
            return Protego.parse("")

        # Any other error stops the run: we must not crawl without knowing the rules.
        _raise_for_status(response)

        robots = Protego.parse(response.text)

        # Client selects the longer delay of one in config.py and one specified in robots.txt
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

            try:  # Get response with timeout
                response = self.session.get(url, timeout=self.timeout, allow_redirects=False)

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
