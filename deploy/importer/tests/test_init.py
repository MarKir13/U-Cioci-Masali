"""The init command (importer/init.py): images, waiting for the shop, the messages. No shop, no internet.

A small HTTP server on localhost stands in for the GitHub Release, and the waits get a fake clock.
"""

import hashlib
import io
import json
import os
import shutil
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import requests

from importer import init

RESULTS = Path(__file__).resolve().parents[3] / "scraper-results"

# 8 Kosmetyki > 99 okolice oczu (product 1, two images); 193 Żywność (product 2)
CATEGORIES = [
    {"id": 8, "name": "Kosmetyki", "url": "https://www.magiczne-indie.pl/8-kosmetyki", "parent_id": None},
    {"id": 99, "name": "Oczy", "url": "https://www.magiczne-indie.pl/99-oczy", "parent_id": 8},
    {"id": 193, "name": "Żywność", "url": "https://www.magiczne-indie.pl/193-zywnosc", "parent_id": None},
]


def product(product_id: int, category_ids: list[int], image_names: list[str]) -> dict:
    return {
        "id": product_id,
        "url": f"https://www.magiczne-indie.pl/{product_id}-x.html",
        "name": f"Produkt {product_id}",
        "description": "<p>Opis</p>",
        "price": "10.00",
        "regular_price": "10.00",
        "has_discount": False,
        "vat_rate": 23.0,
        "category_ids": category_ids,
        "images": [
            {"source_url": f"https://www.magiczne-indie.pl/1-product_main_2x/{n}", "local_path": f"images/{n}"}
            for n in image_names
        ],
    }


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    if not (RESULTS / "schema.json").is_file():
        pytest.skip("scraper-results/schema.json not found")
    shutil.copy(RESULTS / "schema.json", tmp_path / "schema.json")
    (tmp_path / "categories.json").write_text(json.dumps(CATEGORIES), encoding="utf-8")
    products = [product(1, [99, 8], ["1-1.jpg", "1-2.jpg"]), product(2, [193], ["2-1.jpg"])]
    (tmp_path / "products.jsonl").write_text("".join(json.dumps(p) + "\n" for p in products), encoding="utf-8")
    (tmp_path / "images").mkdir()
    return tmp_path


def tar_gz(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


@pytest.fixture
def release():
    """A local web server: put bytes into `files[path]`, get them at `url + path`; other paths answer 404."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - the name http.server calls
            body = files.get(self.path)
            self.send_response(200 if body is not None else 404)
            self.send_header("Content-Length", str(len(body or b"")))
            self.end_headers()
            self.wfile.write(body or b"")

        def log_message(self, *args):
            pass

    files: dict[str, bytes] = {}
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield files, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def archive_for(content: bytes, categories: tuple[int, ...] = ()) -> init.Archive:
    return init.Archive("subset-images.tar.gz", hashlib.sha256(content).hexdigest(), categories)


# --- Images -----------------------------------------------------------------------------------------------


def test_the_subset_needs_only_the_images_of_its_categories_and_subcategories(data_dir):
    needed = init.needed_files(data_dir, init.Archive("x.tar.gz", "", (8,)))
    assert [file.name for file in needed] == ["1-1.jpg", "1-2.jpg"]
    assert len(init.needed_files(data_dir, init.Archive("x.tar.gz", ""))) == 3


def test_nothing_is_downloaded_when_every_needed_file_is_there(data_dir):
    (data_dir / "images" / "1-1.jpg").write_bytes(b"a")
    (data_dir / "images" / "1-2.jpg").write_bytes(b"b")
    # Product 2's image is missing, but the subset does not need it; the URL would fail if it were used
    init.ensure_images(data_dir, init.Archive("x.tar.gz", "", (8,)), "http://127.0.0.1:9/nothing-here")


def test_a_missing_image_downloads_and_unpacks_the_archive(data_dir, release):
    files, url = release
    content = tar_gz({"images/1-1.jpg": b"a", "images/1-2.jpg": b"b", "images/2-1.jpg": b"c"})
    files["/full.tar.gz"] = content
    init.ensure_images(data_dir, archive_for(content), url + "/full.tar.gz")
    assert (data_dir / "images" / "2-1.jpg").read_bytes() == b"c"
    # The download itself is removed after unpacking
    assert list(data_dir.glob("*.tar.gz")) == []


def test_an_interrupted_unpack_leaves_no_half_written_image_and_the_next_run_completes(data_dir, release, monkeypatch):
    files, url = release
    content = tar_gz({"images/1-1.jpg": b"a", "images/1-2.jpg": b"b", "images/2-1.jpg": b"c"})
    files["/full.tar.gz"] = content
    renames = []
    real_replace = os.replace

    def replace_then_stop(source, target):
        # Stops (like Ctrl+C) when the second file is written but not yet renamed
        if renames:
            raise RuntimeError("interrupted")
        renames.append(target)
        real_replace(source, target)

    monkeypatch.setattr(init.os, "replace", replace_then_stop)
    with pytest.raises(RuntimeError, match="interrupted"):
        init.ensure_images(data_dir, archive_for(content), url + "/full.tar.gz")
    assert sorted(p.name for p in (data_dir / "images").iterdir()) == ["1-1.jpg", "1-2.jpg.partial"]

    monkeypatch.undo()
    init.ensure_images(data_dir, archive_for(content), url + "/full.tar.gz")
    assert sorted(p.name for p in (data_dir / "images").iterdir()) == ["1-1.jpg", "1-2.jpg", "2-1.jpg"]


def test_a_missing_file_in_the_release_stops_with_the_http_status(data_dir, release):
    _, url = release
    with pytest.raises(init.ImagesUnavailable, match="HTTP 404"):
        init.ensure_images(data_dir, archive_for(b""), url + "/missing.tar.gz")
    assert list(data_dir.glob("*.tar.gz")) == []


def test_a_file_with_another_hash_is_refused_and_removed(data_dir, release):
    files, url = release
    files["/full.tar.gz"] = tar_gz({"images/2-1.jpg": b"c"})
    with pytest.raises(init.ImagesUnavailable, match="not the published archive"):
        init.ensure_images(data_dir, archive_for(b"something else"), url + "/full.tar.gz")
    assert list(data_dir.glob("*.tar.gz")) == []
    assert not (data_dir / "images" / "2-1.jpg").exists()


@pytest.mark.parametrize("name", ["schema.json", "images/sub/1.jpg", "../outside.jpg"])
def test_an_archive_with_files_outside_images_is_refused(data_dir, release, name):
    files, url = release
    content = tar_gz({"images/2-1.jpg": b"c", name: b"x"})
    files["/full.tar.gz"] = content
    with pytest.raises(init.ImagesUnavailable, match="more than images/"):
        init.ensure_images(data_dir, archive_for(content), url + "/full.tar.gz")
    assert not (data_dir / "images" / "2-1.jpg").exists()


def test_an_archive_that_lacks_a_needed_file_is_reported(data_dir, release):
    files, url = release
    content = tar_gz({"images/1-1.jpg": b"a"})
    files["/subset.tar.gz"] = content
    with pytest.raises(init.ImagesUnavailable, match="lacks 1 files"):
        init.ensure_images(data_dir, archive_for(content, (8,)), url + "/subset.tar.gz")


# --- Shop -------------------------------------------------------------------------------------------------


class FakeClock:
    """time.monotonic and time.sleep in one: sleeping only moves the clock forward."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_a_shop_container_that_is_not_running_stops_init_early():
    clock = FakeClock()

    def resolve(host, port):
        raise OSError("Name or service not known")

    with pytest.raises(init.InitError, match="the shop is not running"):
        init.check_shop_container(clock=clock, sleep=clock.sleep, resolve=resolve)
    assert clock.now == init.SHOP_MISSING_SECONDS


class Answer:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_init_waits_while_the_shop_installs_and_goes_on_once_it_answers():
    clock = FakeClock()
    answers = [requests.ConnectionError(), requests.ConnectionError(), Answer(302)]

    def get(url, **kwargs):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    init.wait_for_shop(clock=clock, sleep=clock.sleep, get=get)
    assert answers == []
    assert clock.now == 2 * init.POLL_SECONDS


def test_a_shop_that_never_gets_ready_stops_init_with_where_to_look():
    clock = FakeClock()
    with pytest.raises(init.InitError, match=r"\[setup\] FAILED"):
        init.wait_for_shop(timeout=60, clock=clock, sleep=clock.sleep, get=lambda url, **kwargs: Answer(500))


# --- Messages ---------------------------------------------------------------------------------------------


@pytest.fixture
def no_shop_needed(monkeypatch):
    """main() up to the images: the shop container counts as running."""
    monkeypatch.setattr(init, "check_shop_container", lambda: None)


# main() sets up logging itself (setup_logging replaces every handler, pytest's caplog too), so these tests read
# the console output, which is also what a person sees


def test_without_the_archive_init_prints_the_fallback_command(data_dir, release, monkeypatch, capsys, no_shop_needed):
    _, url = release
    monkeypatch.setenv("IMAGES_URL", url + "/missing.tar.gz")
    monkeypatch.delenv("CI", raising=False)
    assert init.main(["--data-dir", str(data_dir), "--log-file", str(data_dir / "init.log")]) == 2
    console = capsys.readouterr().err
    assert "HTTP 404" in console
    assert "run --rm --build scraper images" in console
    assert "1 h 40 min" in console


def test_in_ci_init_never_suggests_the_source_shop(data_dir, release, monkeypatch, capsys, no_shop_needed):
    _, url = release
    monkeypatch.setenv("IMAGES_URL", url + "/missing.tar.gz")
    monkeypatch.setenv("CI", "true")
    assert init.main(["--subset", "--data-dir", str(data_dir), "--log-file", str(data_dir / "init.log")]) == 2
    console = capsys.readouterr().err
    assert "scraper images" not in console
    assert "never downloaded from the source shop" in console


def test_init_runs_the_importer_with_the_subset_categories(data_dir, monkeypatch, no_shop_needed):
    for name in ("1-1.jpg", "1-2.jpg"):
        (data_dir / "images" / name).write_bytes(b"x")
    monkeypatch.setattr(init, "SUBSET", init.Archive("subset-images.tar.gz", "", (8,)))
    monkeypatch.setattr(init, "wait_for_shop", lambda: None)
    calls = []
    monkeypatch.setattr(init, "run_importer", lambda argv: calls.append(argv) or 0)
    log_file = str(data_dir / "init.log")
    assert init.main(["--subset", "--workers", "4", "--data-dir", str(data_dir), "--log-file", log_file]) == 0
    assert calls == [["--data-dir", str(data_dir), "--log-file", log_file, "--workers", "4", "--categories", "8"]]
