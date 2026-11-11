"""Tests for HttpClient. No real network: a fake session returns scripted responses."""

import io
import logging
from pathlib import Path

import pytest
import requests
import urllib3
from requests.adapters import BaseAdapter, HTTPAdapter

from scraper.__main__ import fetch_page, main, validate_positive_float
from scraper.config import MAX_DELAY, MAX_REDIRECTS, MAX_ROBOTS_REDIRECTS
from scraper.http_client import (
    CrawlDelayTooLong,
    DisallowedByRobots,
    HttpClient,
    OutsideShop,
    RobotsOutsideShop,
)

BASE = "https://shop.test"
ROBOTS_URL = f"{BASE}/robots.txt"
REAL_ROBOTS = (Path(__file__).parent / "fixtures" / "robots.txt").read_text(encoding="utf-8")

""" ========== HELPER FUNCTIONS =========="""


def make_response(url: str, status: int = 200, body: str = "", headers: dict | None = None) -> requests.Response:
    response = requests.Response()
    response.url = url
    response.status_code = status
    response.reason = ""
    response._content = body.encode("utf-8")
    response.encoding = "utf-8"
    response.headers.update(headers or {})
    return response


def redirect(location: str, status: int = 301) -> tuple:
    """A scripted 3xx response pointing to `location`."""
    return (status, "", {"Location": location})


class FakeSession:
    """Stands in for requests.Session. `script` maps a URL to the list of results for its next calls.

    A result is a status, a (status, body) or (status, body, headers) tuple, or an exception to raise.
    """

    def __init__(self, script: dict[str, list], clock=None, response_time: float = 0.0):
        self.headers = {}
        self.script = {url: list(results) for url, results in script.items()}
        self.calls = []
        # Optional: every request moves the fake clock forward, like a slow server would.
        self.clock = clock
        self.response_time = response_time

    # The client reads Location with requests' own code, so the fake session uses it too.
    get_redirect_target = requests.Session.get_redirect_target

    def get(self, url, timeout, allow_redirects=True):
        # requests would follow redirects on its own, skipping robots.txt and the delay.
        assert allow_redirects is False, "the client must handle redirects itself"
        self.calls.append(url)
        if self.clock is not None:
            self.clock.now += self.response_time
        result = self.script[url].pop(0)
        if isinstance(result, Exception):
            raise result
        status, body, headers = (*result, None)[:3] if isinstance(result, tuple) else (result, "", None)
        return make_response(url, status, body, headers)


class FakeClock:
    """Time that only moves when the client sleeps. Records every sleep."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(script, robots=(200, ""), response_time=0.0, **kwargs):
    clock = FakeClock()
    session = FakeSession({ROBOTS_URL: [robots], **script}, clock=clock, response_time=response_time)
    kwargs = {"delay": 1.0, "backoff": 5.0, "max_retries": 3, **kwargs}
    client = HttpClient(base_url=BASE, session=session, sleep=clock.sleep, clock=clock, **kwargs)
    return client, session, clock


""" ========== TESTS (WIHTOUT USING SLEEP METHOD FOR SAVING TIME) =========="""


def test_sets_user_agent():
    _client, session, _ = make_client({}, user_agent="TestBot/1.0")
    assert session.headers["User-Agent"] == "TestBot/1.0"


def test_relative_url_is_resolved_against_base_url():
    client, session, _ = make_client({f"{BASE}/8-kosmetyki": [(200, "ok")]})
    assert client.get("/8-kosmetyki").text == "ok"
    assert session.calls == [ROBOTS_URL, f"{BASE}/8-kosmetyki"]


def test_disallowed_url_is_skipped_and_logged(caplog):
    client, session, _ = make_client({}, robots=(200, "User-agent: *\nDisallow: /koszyk"))
    with caplog.at_level(logging.WARNING), pytest.raises(DisallowedByRobots):
        client.get("/koszyk")
    assert session.calls == [ROBOTS_URL]
    assert "disallowed by robots.txt" in caplog.text


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/104-olejki-do-wlosow", True),
        ("/104-olejki-do-wlosow?page=2", True),
        ("/242-olejek-amla-do-wlosow-ciemnych-200ml-dabur.html", True),
        ("/1234-product_main_2x/olejek-amla.jpg", True),
        ("/8-kosmetyki?order=product.price.asc", False),
        ("/8-kosmetyki?q=Marka-Dabur", False),
        ("/8-kosmetyki?page=2&n=50", False),
        ("/szukaj?s=amla", False),
        ("/koszyk", False),
        ("/index.php?controller=cart", False),
    ],
)
def test_rules_of_the_real_robots_txt(path, allowed):
    """The source shop uses wildcards (`Disallow: /*?order=`), which urllib.robotparser would ignore."""
    client, _, _ = make_client({}, robots=(200, REAL_ROBOTS))
    assert client.allowed(BASE + path) is allowed


def test_missing_robots_txt_allows_everything():
    client, _, _ = make_client({f"{BASE}/koszyk": [200]}, robots=404)
    assert client.get("/koszyk").status_code == 200


def test_unreadable_robots_txt_stops_the_run():
    client, _, _ = make_client({}, robots=403)
    with pytest.raises(requests.HTTPError):
        client.get("/8-kosmetyki")


def test_load_robots_downloads_robots_txt_only_once():
    client, session, _ = make_client({f"{BASE}/8-kosmetyki": [200]})
    client.load_robots()
    client.load_robots()
    client.get("/8-kosmetyki")
    assert session.calls == [ROBOTS_URL, f"{BASE}/8-kosmetyki"]


def test_load_robots_raises_when_robots_txt_cannot_be_read():
    """The crawl calls load_robots() before its loop and stops on this error."""
    client, session, _ = make_client({}, robots=403)
    with pytest.raises(requests.HTTPError):
        client.load_robots()
    assert session.calls == [ROBOTS_URL]


def test_crawl_delay_from_robots_txt_wins_over_a_shorter_delay():
    client, _, _ = make_client({}, robots=(200, "User-agent: *\nCrawl-delay: 3"))
    client.allowed(f"{BASE}/")
    assert client.delay == 3


def test_crawl_delay_up_to_the_maximum_is_followed():
    client, _, _ = make_client({}, robots=(200, f"User-agent: *\nCrawl-delay: {MAX_DELAY}"))
    client.allowed(f"{BASE}/")
    assert client.delay == MAX_DELAY


def test_crawl_delay_above_the_maximum_stops_the_run(caplog):
    """time.sleep() would overflow on it, and ignoring it would break the shop's rules."""
    robots = (200, "User-agent: *\nCrawl-delay: 99999999999")
    client, session, _ = make_client({}, robots=robots)
    with pytest.raises(CrawlDelayTooLong):
        client.get("/8-kosmetyki")
    assert session.calls == [ROBOTS_URL]

    client, _, _ = make_client({}, robots=robots)
    with caplog.at_level(logging.ERROR):
        assert fetch_page(client, "/8-kosmetyki", None) == 1
    assert "Could not download /8-kosmetyki" in caplog.text


@pytest.mark.parametrize("path", ["/koszyk", "/a/../koszyk", "/a/%2e%2e/koszyk", "/a/%2e/../koszyk"])
def test_allowed_normalizes_the_url_like_get(path):
    client, _, _ = make_client({}, robots=(200, REAL_ROBOTS))
    assert client.allowed(path) is False
    assert client.allowed(BASE + path) is False


def test_allowed_with_a_malformed_url_is_an_invalid_url_error():
    client, _, _ = make_client({})
    with pytest.raises(requests.exceptions.InvalidURL):
        client.allowed("https://shop.test:abc/x")


def test_url_outside_the_shop_is_rejected():
    client, session, _ = make_client({})
    with pytest.raises(OutsideShop):
        client.get("https://other.test/page")
    assert session.calls == []


def test_consecutive_requests_are_spaced_by_the_delay():
    pages = {f"{BASE}/{n}": [200] for n in range(3)}
    client, _, clock = make_client(pages, delay=1.5)
    for n in range(3):
        client.get(f"/{n}")
    # robots.txt, then 3 pages: a full delay before each page, because the fake clock does not move by itself.
    assert clock.sleeps == [1.5, 1.5, 1.5]


def test_slow_responses_still_get_the_full_delay_between_requests():
    """The delay counts from the end of the previous request, not its start."""
    pages = {f"{BASE}/{n}": [200] for n in range(2)}
    client, _, clock = make_client(pages, delay=1.0, response_time=1.5)
    for n in range(2):
        client.get(f"/{n}")
    # robots.txt, then 2 pages; each response takes 1.5 s, longer than the delay.
    assert clock.sleeps == [1.0, 1.0]


def test_delay_counts_from_the_end_of_a_failed_request():
    client, _, clock = make_client(
        {f"{BASE}/a": [requests.Timeout("slow")], f"{BASE}/b": [200]},
        delay=1.0,
        max_retries=0,
        response_time=1.5,
    )
    with pytest.raises(requests.Timeout):
        client.get("/a")
    client.get("/b")
    # robots.txt -> 1.0 before /a, /a times out after 1.5 s -> still 1.0 before /b.
    assert clock.sleeps == [1.0, 1.0]


def test_no_extra_wait_when_the_delay_has_already_passed():
    client, _, clock = make_client({f"{BASE}/a": [200]}, delay=1.0)
    client.allowed(f"{BASE}/a")
    clock.now += 10
    client.get("/a")
    assert clock.sleeps == []


def test_5xx_is_retried_with_growing_pause():
    client, session, clock = make_client({f"{BASE}/a": [503, 502, (200, "ok")]})
    assert client.get("/a").text == "ok"
    assert session.calls.count(f"{BASE}/a") == 3
    # robots.txt -> delay, 503 -> backoff 5, 502 -> backoff 10. The backoff already covers the delay.
    assert clock.sleeps == [1.0, 5.0, 10.0]


def test_gives_up_after_max_retries():
    client, session, _ = make_client({f"{BASE}/a": [500] * 4}, max_retries=3)
    with pytest.raises(requests.HTTPError):
        client.get("/a")
    assert session.calls.count(f"{BASE}/a") == 4


def test_network_error_is_retried():
    client, _, _ = make_client({f"{BASE}/a": [requests.ConnectionError("reset"), requests.Timeout(), 200]})
    assert client.get("/a").status_code == 200


@pytest.mark.parametrize(
    "error",
    [requests.exceptions.ChunkedEncodingError("cut body"), requests.exceptions.ContentDecodingError("broken gzip")],
)
def test_error_while_reading_the_body_is_retried(error):
    """Not a ConnectionError: the connection drops after the headers, while the body is read."""
    client, session, _ = make_client({f"{BASE}/a": [error, (200, "ok")]})
    assert client.get("/a").text == "ok"
    assert session.calls.count(f"{BASE}/a") == 2


def test_network_error_is_raised_after_max_retries():
    client, _, _ = make_client({f"{BASE}/a": [requests.Timeout()] * 2}, max_retries=1)
    with pytest.raises(requests.Timeout):
        client.get("/a")


@pytest.mark.parametrize("status", [429, 500, 501, 503, 599])
def test_every_5xx_and_429_is_retried(status):
    client, session, _ = make_client({f"{BASE}/a": [status, (200, "ok")]})
    assert client.get("/a").text == "ok"
    assert session.calls.count(f"{BASE}/a") == 2


def test_successful_response_is_not_retried():
    client, session, clock = make_client({f"{BASE}/a": [(200, "ok")]})
    assert client.get("/a").text == "ok"
    assert session.calls == [ROBOTS_URL, f"{BASE}/a"]
    # Only the delay between robots.txt and the page, no backoff.
    assert clock.sleeps == [1.0]


@pytest.mark.parametrize("status", [400, 403, 404, 410])
def test_4xx_is_not_retried(status):
    client, session, _ = make_client({f"{BASE}/a": [status]})
    with pytest.raises(requests.HTTPError):
        client.get("/a")
    assert session.calls.count(f"{BASE}/a") == 1


""" ========== REDIRECTS =========="""


def test_redirect_is_followed_with_the_delay_before_each_hop():
    client, session, clock = make_client({f"{BASE}/a": [redirect("/b")], f"{BASE}/b": [(200, "ok")]})
    response = client.get("/a")
    assert response.text == "ok"
    assert [r.status_code for r in response.history] == [301]
    assert session.calls == [ROBOTS_URL, f"{BASE}/a", f"{BASE}/b"]
    assert clock.sleeps == [1.0, 1.0]


def test_redirect_to_a_disallowed_url_is_not_requested(caplog):
    client, session, _ = make_client(
        {f"{BASE}/a": [redirect("/koszyk", 302)]},
        robots=(200, "User-agent: *\nDisallow: /koszyk"),
    )
    with caplog.at_level(logging.WARNING), pytest.raises(DisallowedByRobots):
        client.get("/a")
    assert session.calls == [ROBOTS_URL, f"{BASE}/a"]
    assert "disallowed by robots.txt" in caplog.text


def test_redirect_outside_the_shop_is_not_requested():
    client, session, _ = make_client({f"{BASE}/a": [redirect("https://other.test/page")]})
    with pytest.raises(OutsideShop):
        client.get("/a")
    assert session.calls == [ROBOTS_URL, f"{BASE}/a"]


@pytest.mark.parametrize(
    "location",
    ["http://shop.test/b", "https://shop.test:8443/b", "https://www.shop.test/b"],
)
def test_redirect_to_another_scheme_port_or_host_is_not_requested(location):
    client, session, _ = make_client({f"{BASE}/a": [redirect(location)]})
    with pytest.raises(OutsideShop):
        client.get("/a")
    assert session.calls == [ROBOTS_URL, f"{BASE}/a"]


def test_explicit_default_port_is_the_same_shop():
    client, _session, _ = make_client({f"{BASE}/a": [redirect("https://shop.test:443/b")], f"{BASE}:443/b": [200]})
    assert client.get("/a").status_code == 200


@pytest.mark.parametrize("status", [302, 304])
def test_3xx_without_location_is_an_error(status):
    client, _, _ = make_client({f"{BASE}/a": [status]})
    with pytest.raises(requests.HTTPError):
        client.get("/a")


BAD_URLS = ["https://shop.test:abc/x", "https://shop.test:99999/x", "http://[bad/x"]


@pytest.mark.parametrize("location", BAD_URLS)
def test_malformed_redirect_is_an_invalid_url_error(location):
    """InvalidURL is a RequestException, so a crawl can log it and go on instead of crashing on ValueError."""
    client, session, _ = make_client({f"{BASE}/a": [redirect(location)]})
    with pytest.raises(requests.exceptions.InvalidURL):
        client.get("/a")
    assert session.calls == [ROBOTS_URL, f"{BASE}/a"]


@pytest.mark.parametrize("location", BAD_URLS)
def test_malformed_robots_txt_redirect_stops_the_run(location):
    client, session, _ = make_client({}, robots=redirect(location))
    with pytest.raises(requests.exceptions.InvalidURL):
        client.get("/a")
    assert session.calls == [ROBOTS_URL]


@pytest.mark.parametrize("url", BAD_URLS)
def test_fetch_of_a_malformed_url_exits_with_1_without_a_traceback(url, caplog):
    client, session, _ = make_client({})
    with caplog.at_level(logging.ERROR):
        assert fetch_page(client, url, None) == 1
    assert session.calls == []
    assert "Could not download" in caplog.text


def test_redirect_loop_is_stopped():
    client, session, _ = make_client({f"{BASE}/a": [redirect("/b")], f"{BASE}/b": [redirect("/a")]})
    with pytest.raises(requests.TooManyRedirects):
        client.get("/a")
    assert session.calls == [ROBOTS_URL, f"{BASE}/a", f"{BASE}/b"]


def test_gives_up_after_max_redirects():
    chain = {f"{BASE}/{n}": [redirect(f"/{n + 1}")] for n in range(MAX_REDIRECTS + 1)}
    client, session, _ = make_client(chain)
    with pytest.raises(requests.TooManyRedirects):
        client.get("/0")
    # The first request and MAX_REDIRECTS hops; the next one is not sent.
    assert len(session.calls) == 1 + 1 + MAX_REDIRECTS


def test_redirected_robots_txt_is_followed():
    client, session, _ = make_client(
        {f"{BASE}/new-robots.txt": [(200, "User-agent: *\nDisallow: /koszyk")]},
        robots=redirect("/new-robots.txt"),
    )
    assert client.allowed(f"{BASE}/koszyk") is False
    assert session.calls == [ROBOTS_URL, f"{BASE}/new-robots.txt"]


@pytest.mark.parametrize(
    "location",
    ["https://evil.test/robots.txt", "http://shop.test/robots.txt", "https://shop.test:8443/robots.txt"],
)
def test_robots_txt_redirect_outside_the_shop_stops_the_run(location, caplog):
    """A foreign `Allow: /` must not replace the shop's rules, and the run must not go on without rules."""
    client, session, _ = make_client({location: [(200, "User-agent: *\nAllow: /")]}, robots=redirect(location))
    with caplog.at_level(logging.ERROR), pytest.raises(RobotsOutsideShop):
        client.get("/koszyk")
    assert session.calls == [ROBOTS_URL]
    assert "robots.txt redirects outside the source shop" in caplog.text


def test_fetch_exits_with_1_when_robots_txt_redirects_outside_the_shop(caplog):
    client, _, _ = make_client({}, robots=redirect("https://evil.test/robots.txt"))
    with caplog.at_level(logging.ERROR):
        assert fetch_page(client, "/8-kosmetyki", None) == 1
    assert "Could not download /8-kosmetyki" in caplog.text


def test_robots_txt_3xx_without_location_stops_the_run():
    """Otherwise the empty body would be parsed as "everything allowed"."""
    client, _, _ = make_client({}, robots=302)
    with pytest.raises(requests.HTTPError):
        client.allowed(f"{BASE}/koszyk")


def test_gives_up_after_max_robots_txt_redirects():
    chain = {f"{BASE}/r{n}.txt": [redirect(f"/r{n + 1}.txt")] for n in range(MAX_ROBOTS_REDIRECTS)}
    client, _, _ = make_client(chain, robots=redirect("/r0.txt"))
    with pytest.raises(requests.TooManyRedirects):
        client.allowed(f"{BASE}/")


""" ========== REAL requests.Session (URL HANDLING DONE BY REQUESTS ITSELF) =========="""


class StubAdapter(BaseAdapter):
    """Transport for a real requests.Session that answers from `routes` instead of the network.

    FakeSession skips the code of requests that prepares the URL and reads Location,
    so the cases where requests reads a URL differently than urllib need a real Session.
    A route is a (status, body) or (status, body, headers) tuple, or a function that builds
    the response from the request; an unknown URL fails the test.
    """

    def __init__(self, routes: dict):
        super().__init__()
        self.routes = routes
        self.sent = []

    def send(self, request, **kwargs):
        self.sent.append(request.url)
        route = self.routes[request.url]
        if callable(route):
            return route(request)
        status, body, headers = (*route, None)[:3]
        response = make_response(request.url, status, body, headers)
        response.request = request
        return response

    def close(self):
        pass


def make_real_client(routes, robots=(200, "")):
    adapter = StubAdapter({ROBOTS_URL: robots, **routes})
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    clock = FakeClock()
    client = HttpClient(base_url=BASE, session=session, sleep=clock.sleep, clock=clock)
    return client, adapter


@pytest.mark.parametrize("location", ["http://[bad/x", "http://x＃.pl/"])
def test_malformed_location_parsed_by_requests_is_an_invalid_url_error(location, caplog):
    """requests reads Location inside Session.send even with allow_redirects=False, before _join_url."""
    client, adapter = make_real_client({f"{BASE}/a": redirect(location)})
    with pytest.raises(requests.exceptions.InvalidURL):
        client.get("/a")
    assert adapter.sent == [ROBOTS_URL, f"{BASE}/a"]
    with caplog.at_level(logging.ERROR):
        assert fetch_page(client, "/a", None) == 1
    assert "Could not download" in caplog.text


# urllib sees host shop.test, requests sends the request to evil.test.
BACKSLASH_URL = "https://evil.test\\@shop.test/x"


def test_backslash_url_outside_the_shop_is_not_requested():
    client, adapter = make_real_client({})
    with pytest.raises(OutsideShop):
        client.get(BACKSLASH_URL)
    assert adapter.sent == []


def test_redirect_to_a_backslash_url_outside_the_shop_is_not_requested():
    client, adapter = make_real_client({f"{BASE}/a": redirect(BACKSLASH_URL)})
    with pytest.raises(OutsideShop):
        client.get("/a")
    assert adapter.sent == [ROBOTS_URL, f"{BASE}/a"]


# Every path is /koszyk once the server decodes %2e and removes the dot segments.
DOT_SEGMENT_PATHS = [
    "/a/../koszyk",
    "/a/b/../../koszyk",
    "/a/%2e%2e/koszyk",
    "/a/%2E%2E/koszyk",
    "/a/.%2e/koszyk",
    "/a/%2e/../koszyk",
]


@pytest.mark.parametrize("path", DOT_SEGMENT_PATHS)
def test_dot_segments_do_not_bypass_robots_txt(path):
    client, adapter = make_real_client({}, robots=(200, REAL_ROBOTS))
    with pytest.raises(DisallowedByRobots):
        client.get(BASE + path)
    assert adapter.sent == [ROBOTS_URL]


@pytest.mark.parametrize("path", DOT_SEGMENT_PATHS)
@pytest.mark.parametrize("origin", [BASE, ""], ids=["absolute", "relative"])
def test_redirect_with_dot_segments_does_not_bypass_robots_txt(path, origin):
    """urljoin removes dot segments only from a relative Location, and before %2e is decoded."""
    client, adapter = make_real_client({f"{BASE}/a": redirect(origin + path)}, robots=(200, REAL_ROBOTS))
    with pytest.raises(DisallowedByRobots):
        client.get("/a")
    assert adapter.sent == [ROBOTS_URL, f"{BASE}/a"]


@pytest.mark.parametrize("path", ["/x/../8-kosmetyki", "/x/%2e%2e/8-kosmetyki", "/x/%2e/../8-kosmetyki"])
def test_the_checked_url_is_the_url_that_is_sent(path):
    client, adapter = make_real_client({f"{BASE}/8-kosmetyki": (200, "ok")}, robots=(200, REAL_ROBOTS))
    response = client.get(BASE + path)
    assert response.text == "ok"
    assert response.url == f"{BASE}/8-kosmetyki"
    assert adapter.sent == [ROBOTS_URL, f"{BASE}/8-kosmetyki"]


def cut_body(request) -> requests.Response:
    """10 of the 1000 bytes promised by Content-Length, as when the connection drops mid-download."""
    raw = urllib3.HTTPResponse(
        io.BytesIO(b"0123456789"),
        headers={"Content-Length": "1000"},
        status=200,
        preload_content=False,
        enforce_content_length=True,
    )
    return HTTPAdapter().build_response(request, raw)


def test_connection_dropped_mid_download_is_retried():
    client, adapter = make_real_client({f"{BASE}/a": cut_body})
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        client.get("/a")
    # The first attempt and 3 retries.
    assert adapter.sent.count(f"{BASE}/a") == 4


# http.client decodes headers as latin-1, so a Location sent as UTF-8 arrives garbled like this.
UTF8_LOCATION = "/zdrowie-żółć".encode().decode("latin-1")
UTF8_TARGET = f"{BASE}/zdrowie-%C5%BC%C3%B3%C5%82%C4%87"


def test_utf8_location_is_followed_like_requests_does():
    client, adapter = make_real_client({f"{BASE}/a": redirect(UTF8_LOCATION), UTF8_TARGET: (200, "ok")})
    assert client.get("/a").text == "ok"
    assert adapter.sent == [ROBOTS_URL, f"{BASE}/a", UTF8_TARGET]


def test_utf8_location_of_robots_txt_is_followed_like_requests_does():
    client, adapter = make_real_client(
        {UTF8_TARGET: (200, "User-agent: *\nDisallow: /koszyk")}, robots=redirect(UTF8_LOCATION)
    )
    assert client.allowed(f"{BASE}/koszyk") is False
    assert adapter.sent == [ROBOTS_URL, UTF8_TARGET]


""" ========== COMMAND LINE =========="""


@pytest.mark.parametrize("url", ["https://other.test/page", "/koszyk"])
def test_fetch_of_a_skipped_url_exits_with_1_without_a_traceback(url):
    client, _, _ = make_client({}, robots=(200, "User-agent: *\nDisallow: /koszyk"))
    assert fetch_page(client, url, None) == 1


@pytest.mark.parametrize(("value", "expected"), [("0.5", 0.5), ("1", 1.0), ("2.5", 2.5), ("3600", 3600.0)])
def test_delay_from_the_minimum_to_the_maximum_is_accepted(value, expected):
    assert validate_positive_float(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("0", "at least 0.5"),
        ("0.49", "at least 0.5"),
        ("-1", "at least 0.5"),
        ("3600.5", "at most 3600"),
        ("1e10", "at most 3600"),
        ("nan", "finite number"),
        ("inf", "finite number"),
        ("abc", "not a real number"),
    ],
)
def test_delay_out_of_range_stops_before_any_request(value, message, capsys, monkeypatch):
    # argparse rejects the value before the client is created, so no request is sent.
    # If it did not, the real client would call the shop: fail the test instead.
    monkeypatch.setattr("scraper.__main__.setup_logging", lambda *args: None)
    monkeypatch.setattr("scraper.__main__.HttpClient", lambda **kwargs: pytest.fail("the client was created"))
    with pytest.raises(SystemExit) as exit_info:
        main(["--delay", value, "fetch", "/8-kosmetyki"])
    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("delay", [0, 0.49, -1, 3600.5, 1e10, float("nan"), float("inf")])
def test_client_rejects_a_delay_out_of_range_or_not_finite(delay):
    """The client checks the delay itself, so code that bypasses the CLI cannot turn it off."""
    with pytest.raises(ValueError, match="at least 0.5"):
        HttpClient(base_url=BASE, delay=delay)
