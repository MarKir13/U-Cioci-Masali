"""Tests for HttpClient. No real network: a fake session returns scripted responses."""

import logging
from pathlib import Path

import pytest
import requests

from scraper.http_client import DisallowedByRobots, HttpClient

BASE = "https://shop.test"
ROBOTS_URL = f"{BASE}/robots.txt"
REAL_ROBOTS = (Path(__file__).parent / "fixtures" / "robots.txt").read_text(encoding="utf-8")

""" ========== HELPER FUNCTIONS =========="""

def make_response(url: str, status: int = 200, body: str = "") -> requests.Response:
    response = requests.Response()
    response.url = url
    response.status_code = status
    response.reason = ""
    response._content = body.encode("utf-8")
    response.encoding = "utf-8"
    return response


class FakeSession:
    """Stands in for requests.Session. `script` maps a URL to the list of results for its next calls."""

    def __init__(self, script: dict[str, list]):
        self.headers = {}
        self.script = {url: list(results) for url, results in script.items()}
        self.calls = []

    def get(self, url, timeout):
        self.calls.append(url)
        result = self.script[url].pop(0)
        if isinstance(result, Exception):
            raise result
        status, body = result if isinstance(result, tuple) else (result, "")
        return make_response(url, status, body)


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


def make_client(script, robots=(200, ""), **kwargs):
    clock = FakeClock()
    session = FakeSession({ROBOTS_URL: [robots], **script})
    kwargs = {"delay": 1.0, "backoff": 5.0, "max_retries": 3, **kwargs}
    client = HttpClient(base_url=BASE, session=session, sleep=clock.sleep, clock=clock, **kwargs)
    return client, session, clock






""" ========== TESTS (WIHTOUT USING SLEEP METHOD FOR SAVING TIME) =========="""

def test_sets_user_agent():
    client, session, _ = make_client({}, user_agent="TestBot/1.0")
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


def test_crawl_delay_from_robots_txt_wins_over_a_shorter_delay():
    client, _, _ = make_client({}, robots=(200, "User-agent: *\nCrawl-delay: 3"))
    client.allowed(f"{BASE}/")
    assert client.delay == 3


def test_url_outside_the_shop_is_rejected():
    client, session, _ = make_client({})
    with pytest.raises(ValueError):
        client.get("https://other.test/page")
    assert session.calls == []


def test_consecutive_requests_are_spaced_by_the_delay():
    pages = {f"{BASE}/{n}": [200] for n in range(3)}
    client, _, clock = make_client(pages, delay=1.5)
    for n in range(3):
        client.get(f"/{n}")
    # robots.txt, then 3 pages: a full delay before each page, because the fake clock does not move by itself.
    assert clock.sleeps == [1.5, 1.5, 1.5]


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


def test_network_error_is_raised_after_max_retries():
    client, _, _ = make_client({f"{BASE}/a": [requests.Timeout()] * 2}, max_retries=1)
    with pytest.raises(requests.Timeout):
        client.get("/a")


def test_404_is_not_retried():
    client, session, _ = make_client({f"{BASE}/a": [404]})
    with pytest.raises(requests.HTTPError):
        client.get("/a")
    assert session.calls.count(f"{BASE}/a") == 1
