"""Tests of image processing and downloading. Images are generated here; there is no network."""

import functools
import io
import json
import logging
import random

import pytest
import requests
from PIL import Image

from scraper.__main__ import main
from scraper.config import IMAGE_MAX_BYTES, IMAGE_MAX_SIDE, IMAGE_MIN_SIDE
from scraper.crawl import load_lines
from scraper.http_client import HttpClient
from scraper.images import (
    CorruptImage,
    ImageDownloader,
    TooLargeImage,
    TooSmallImage,
    image_name,
    process_image,
    save_bytes,
)

BASE = "https://shop.test"


@functools.cache  # generating a big picture pixel by pixel takes seconds; the arguments are all hashable
def make_image(size=(1440, 1440), noise=True, mode="RGB", fmt="PNG", grain=255) -> bytes:
    """A picture of `size`: a gradient with random grain of up to `grain` per pixel.

    grain=255 is pure static, which JPEG cannot compress. A small grain looks more like a photo.
    With noise=False the picture is plain white.
    """
    if noise:
        generator = random.Random(1)
        width, height = size
        raw = bytearray()
        for y in range(height):
            for x in range(width):
                base = (x * 255 // width, y * 255 // height, (x + y) * 255 // (width + height))
                raw += bytes(min(255, max(0, c + generator.randrange(grain) - grain // 2)) for c in base)
        image = Image.frombytes("RGB", size, bytes(raw)).convert(mode)
    else:
        image = Image.new(mode, size, "white")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def jpeg_size(data: bytes, quality: int = 90) -> int:
    with Image.open(io.BytesIO(data)) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return len(buffer.getvalue())


def dimensions(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


# ---------- process_image ----------


def test_noisy_image_is_recompressed_under_the_size_limit():
    source = make_image((1440, 1440), grain=60)
    assert jpeg_size(source) > IMAGE_MAX_BYTES  # the test is only meaningful if the source is too big
    result = process_image(source)
    assert len(result) <= IMAGE_MAX_BYTES
    assert dimensions(result) == (1440, 1440)  # quality was lowered first, the size was kept


def test_result_is_a_jpeg():
    with Image.open(io.BytesIO(process_image(make_image((900, 900), noise=False)))) as image:
        assert image.format == "JPEG"


def test_image_above_the_maximum_is_scaled_down_keeping_proportions():
    result = process_image(make_image((2400, 1200), noise=False))
    assert dimensions(result) == (IMAGE_MAX_SIDE, 800)


def test_portrait_image_is_measured_by_its_longer_side():
    assert dimensions(process_image(make_image((900, 2000), noise=False))) == (720, IMAGE_MAX_SIDE)


@pytest.mark.parametrize("side", [IMAGE_MIN_SIDE, 1000, IMAGE_MAX_SIDE])
def test_image_within_the_range_keeps_its_size(side):
    assert dimensions(process_image(make_image((side, side // 2), noise=False))) == (side, side // 2)


def test_image_below_the_minimum_is_rejected_not_enlarged():
    with pytest.raises(TooSmallImage, match="799"):
        process_image(make_image((799, 400), noise=False))


@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20])
def test_unreadable_data_is_corrupt(data):
    with pytest.raises(CorruptImage):
        process_image(data)


def test_truncated_image_is_corrupt():
    source = make_image((900, 900), noise=True)
    with pytest.raises(CorruptImage):
        process_image(source[: len(source) // 2])


def test_transparent_png_gets_a_white_background():
    image = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    with Image.open(io.BytesIO(process_image(buffer.getvalue()))) as result:
        assert result.mode == "RGB"
        assert min(result.getpixel((10, 10))) > 240


def test_webp_source_is_accepted():
    assert dimensions(process_image(make_image((1000, 1000), noise=False, fmt="WEBP"))) == (1000, 1000)


def test_image_that_cannot_fit_is_shrunk_and_then_rejected():
    source = make_image((900, 900))  # static
    # With a tiny limit nothing fits, not even 800 px at the lowest quality
    with pytest.raises(TooLargeImage):
        process_image(source, max_bytes=2_000)


def test_image_is_shrunk_when_the_lowest_quality_is_not_enough():
    source = make_image((1440, 1440), grain=120)
    limit = 250_000
    assert jpeg_size(source, quality=40) > limit  # lowering the quality alone cannot be enough
    result = process_image(source, max_bytes=limit)
    assert len(result) <= limit
    assert IMAGE_MIN_SIDE <= dimensions(result)[0] < 1440


def test_highest_quality_that_fits_is_used():
    """A looser limit must give a bigger file, so quality is not lowered more than needed."""
    source = make_image((1200, 1200), grain=60)
    tight = process_image(source, max_bytes=250_000)
    loose = process_image(source, max_bytes=500_000)
    assert len(tight) <= 250_000 < len(loose) <= 500_000


# ---------- save_bytes ----------


def test_save_bytes_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "a.jpg"
    save_bytes(path, b"abc")
    assert path.read_bytes() == b"abc"
    assert [p.name for p in tmp_path.iterdir()] == ["a.jpg"]


# ---------- ImageDownloader ----------


IMAGE_IDS = {"a": 101, "b": 102, "c": 103}


def url(name: str) -> str:
    """Source URL in the shop's form; `name` is a letter standing for an image id."""
    return f"{BASE}/{IMAGE_IDS[name]}-product_main_2x/{name}.jpg"


def product(product_id: int, *names: str) -> dict:
    return {
        "id": product_id,
        "name": f"Produkt {product_id}",
        "images": [{"source_url": url(n), "local_path": None} for n in names],
    }


class FakeShop:
    """Stands in for requests.Session: serves `files` (bytes, or (bytes, Content-Type)), 404 for anything else."""

    def __init__(self, files: dict):
        self.headers = {}
        self.files = files
        self.calls: list[str] = []

    get_redirect_target = requests.Session.get_redirect_target

    def get(self, target, timeout, allow_redirects=True):
        self.calls.append(target)
        response = requests.Response()
        response.url = target
        data = self.files.get(target)
        if isinstance(data, BaseException):
            raise data
        content_type = "image/jpeg"
        if isinstance(data, tuple):  # (bytes, Content-Type)
            data, content_type = data
        response.status_code = 404 if data is None else 200
        response.headers["Content-Type"] = content_type
        response._content = data or b""
        return response


def run_downloader(tmp_path, products, files, **kwargs):
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)
    (results / "products.jsonl").write_text("".join(json.dumps(p) + "\n" for p in products), encoding="utf-8")
    shop = FakeShop({f"{BASE}/robots.txt": b"", **files})
    client = HttpClient(base_url=BASE, session=shop, sleep=lambda seconds: None, max_retries=1)
    code = ImageDownloader(client, results_dir=results, **kwargs).run()
    return code, shop, results


def saved(results):
    return load_lines(results / "products.jsonl")


def test_images_are_saved_and_local_paths_filled_in(tmp_path):
    good = make_image((1440, 1440), grain=60)
    products = [product(7, "a", "b"), product(8, "c")]
    code, _, results = run_downloader(tmp_path, products, {url("a"): good, url("b"): good, url("c"): good})

    assert code == 0
    first, second = saved(results)
    assert [i["local_path"] for i in first["images"]] == ["images/7-101.jpg", "images/7-102.jpg"]
    assert second["images"][0]["local_path"] == "images/8-103.jpg"
    for name in ("7-101.jpg", "7-102.jpg", "8-103.jpg"):
        data = (results / "images" / name).read_bytes()
        assert len(data) <= IMAGE_MAX_BYTES
        assert IMAGE_MIN_SIDE <= max(dimensions(data)) <= IMAGE_MAX_SIDE
    assert not list((results / "images").glob("*.part"))


def test_second_run_downloads_nothing(tmp_path):
    files = {url("a"): make_image((1000, 1000), noise=False)}
    products = [product(7, "a")]
    run_downloader(tmp_path, products, files)
    code, shop, results = run_downloader(tmp_path, saved(tmp_path / "results"), files)

    assert code == 0
    assert shop.calls == [f"{BASE}/robots.txt"]
    assert saved(results)[0]["images"][0]["local_path"] == "images/7-101.jpg"


def test_run_after_an_interruption_continues_with_the_missing_images(tmp_path):
    good = make_image((1000, 1000), noise=False)
    files = {url("a"): good, url("b"): good}
    products = [product(7, "a", "b")]
    # The first run is cut off after one image
    run_downloader(tmp_path, products, files, limit=1)
    assert [i["local_path"] for i in saved(tmp_path / "results")[0]["images"]] == ["images/7-101.jpg", None]

    _, shop, results = run_downloader(tmp_path, saved(tmp_path / "results"), files)
    assert shop.calls == [f"{BASE}/robots.txt", url("b")]
    assert [i["local_path"] for i in saved(results)[0]["images"]] == ["images/7-101.jpg", "images/7-102.jpg"]


def test_file_deleted_from_disk_is_downloaded_again(tmp_path):
    files = {url("a"): make_image((1000, 1000), noise=False)}
    _, _, results = run_downloader(tmp_path, [product(7, "a")], files)
    (results / "images" / "7-101.jpg").unlink()

    _, shop, results = run_downloader(tmp_path, saved(results), files)
    assert url("a") in shop.calls
    assert (results / "images" / "7-101.jpg").exists()


def test_too_small_image_is_logged_reported_and_not_requested_again(tmp_path, caplog):
    small = make_image((500, 500), noise=False)
    files = {url("a"): small, url("b"): make_image((1000, 1000), noise=False)}
    with caplog.at_level(logging.WARNING):
        _, _, results = run_downloader(tmp_path, [product(7, "a", "b")], files)

    assert "longer side is 500 px" in caplog.text
    assert not (results / "images" / "7-101.jpg").exists()
    first = saved(results)[0]["images"]
    assert first[0]["local_path"] is None and first[1]["local_path"] == "images/7-102.jpg"
    problems = json.loads((results / "image_problems.json").read_text(encoding="utf-8"))
    assert list(problems) == [url("a")] and "TooSmallImage" in problems[url("a")]

    _, shop, _ = run_downloader(tmp_path, saved(results), files)
    assert url("a") not in shop.calls


def test_corrupted_image_is_logged_and_does_not_stop_the_run(tmp_path, caplog):
    files = {url("a"): b"<html>not an image</html>", url("b"): make_image((1000, 1000), noise=False)}
    with caplog.at_level(logging.WARNING):
        code, _, results = run_downloader(tmp_path, [product(7, "a"), product(8, "b")], files)

    assert code == 1  # product 7 has no image
    assert "cannot be read as an image" in caplog.text
    assert (results / "images" / "8-102.jpg").exists()


def test_product_without_any_usable_image_is_reported(tmp_path, caplog):
    with caplog.at_level(logging.ERROR):
        run_downloader(tmp_path, [product(7, "a")], {url("a"): make_image((300, 300), noise=False)})
    assert "1 products have no usable image" in caplog.text and "[7]" in caplog.text


def test_download_error_is_retried_by_a_later_run_not_remembered(tmp_path):
    good = make_image((1000, 1000), noise=False)
    _, _, results = run_downloader(tmp_path, [product(7, "a")], {})  # 404
    assert not (results / "image_problems.json").read_text(encoding="utf-8").strip("{}\n ")

    _, _, results = run_downloader(tmp_path, saved(results), {url("a"): good})
    assert (results / "images" / "7-101.jpg").exists()


def test_image_on_another_host_is_skipped_not_downloaded(tmp_path):
    other = {"id": 7, "images": [{"source_url": "https://cdn.other.test/a.jpg", "local_path": None}]}
    code, shop, results = run_downloader(
        tmp_path, [other], {"https://cdn.other.test/a.jpg": make_image((1000, 1000), noise=False)}
    )
    assert code == 1  # the product is left without an image
    assert "https://cdn.other.test/a.jpg" not in shop.calls
    assert saved(results)[0]["images"][0]["local_path"] is None


def test_ctrl_c_saves_the_paths_of_finished_images(tmp_path):
    good = make_image((1000, 1000), noise=False)
    products = [product(1, "a"), product(2, "b"), product(3, "c")]
    files = {url("a"): good, url("b"): KeyboardInterrupt(), url("c"): good}
    code, _, results = run_downloader(tmp_path, products, files)

    assert code == 130
    assert [p["images"][0]["local_path"] for p in saved(results)] == ["images/1-101.jpg", None, None]


def test_products_file_is_saved_every_save_every_images(tmp_path):
    """A crash that no handler catches must not lose the paths of images that are already on disk."""
    good = make_image((1000, 1000), noise=False)
    products = [product(1, "a"), product(2, "b"), product(3, "c")]
    files = {url("a"): good, url("b"): good, url("c"): RuntimeError("bug")}
    with pytest.raises(RuntimeError):
        run_downloader(tmp_path, products, files, save_every=1)

    paths = [p["images"][0]["local_path"] for p in saved(tmp_path / "results")]
    assert paths == ["images/1-101.jpg", "images/2-102.jpg", None]


def test_a_crash_without_periodic_saving_loses_the_paths(tmp_path):
    """The same crash with a huge save_every: proves the test above really depends on the periodic save."""
    good = make_image((1000, 1000), noise=False)
    products = [product(1, "a"), product(2, "b"), product(3, "c")]
    files = {url("a"): good, url("b"): good, url("c"): RuntimeError("bug")}
    with pytest.raises(RuntimeError):
        run_downloader(tmp_path, products, files, save_every=10**9)

    assert [p["images"][0]["local_path"] for p in saved(tmp_path / "results")] == [None, None, None]


# ---------- Not an image ----------


def test_html_with_status_200_is_a_download_error_and_not_remembered(tmp_path, caplog):
    html = (b"<html>maintenance</html>", "text/html; charset=utf-8")
    with caplog.at_level(logging.ERROR):
        code, _, results = run_downloader(tmp_path, [product(7, "a")], {url("a"): html})

    assert code == 1
    assert "is not an image" in caplog.text and "text/html" in caplog.text
    assert json.loads((results / "image_problems.json").read_text(encoding="utf-8")) == {}

    # The shop is back: the same URL is requested again and saved
    good = make_image((1000, 1000), noise=False)
    code, shop, results = run_downloader(tmp_path, saved(results), {url("a"): good})
    assert code == 0 and url("a") in shop.calls


def test_response_without_content_type_is_left_to_pillow(tmp_path):
    good = make_image((1000, 1000), noise=False)
    code, _, results = run_downloader(tmp_path, [product(7, "a")], {url("a"): (good, "")})
    assert code == 0 and (results / "images" / "7-101.jpg").exists()


# ---------- File names ----------


def test_file_belongs_to_its_source_image_when_the_order_changes(tmp_path):
    """products.jsonl rebuilt with the images in another order must not give a file to the wrong image."""
    a, b = make_image((1000, 1000), noise=False), make_image((900, 900), noise=False)
    files = {url("a"): a, url("b"): b}
    _, _, results = run_downloader(tmp_path, [product(7, "a", "b")], files)
    before = {name: (results / "images" / name).read_bytes() for name in ("7-101.jpg", "7-102.jpg")}

    reordered = saved(results)
    reordered[0]["images"].reverse()
    for image in reordered[0]["images"]:
        image["local_path"] = None
    _, shop, results = run_downloader(tmp_path, reordered, files)

    assert shop.calls == [f"{BASE}/robots.txt"]  # nothing downloaded again
    paths = {i["source_url"]: i["local_path"] for i in saved(results)[0]["images"]}
    assert paths == {url("a"): "images/7-101.jpg", url("b"): "images/7-102.jpg"}
    assert {name: (results / "images" / name).read_bytes() for name in before} == before


# ---------- Exit code ----------


def test_exit_code_is_1_when_a_download_failed(tmp_path):
    code, _, _ = run_downloader(tmp_path, [product(7, "a")], {})  # 404
    assert code == 1


def test_exit_code_is_0_for_a_test_run_that_left_images_for_later(tmp_path):
    good = make_image((1000, 1000), noise=False)
    code, _, _ = run_downloader(tmp_path, [product(7, "a"), product(8, "b")], {url("a"): good, url("b"): good}, limit=1)
    assert code == 0


def test_exit_code_is_1_when_a_product_has_no_usable_image(tmp_path):
    code, _, _ = run_downloader(tmp_path, [product(7, "a")], {url("a"): make_image((300, 300), noise=False)})
    assert code == 1


def test_quality_is_logged_at_debug_level(caplog):
    with caplog.at_level(logging.DEBUG, logger="scraper.images"):
        process_image(make_image((900, 900), noise=False))
    assert "quality 90" in caplog.text


def test_no_products_file_is_an_error(tmp_path):
    shop = FakeShop({})
    client = HttpClient(base_url=BASE, session=shop, sleep=lambda seconds: None)
    assert ImageDownloader(client, results_dir=tmp_path).run() == 1


def test_image_name_uses_the_image_id_from_the_url():
    assert image_name(12, f"{BASE}/14452-product_main_2x/olejek.jpg") == "12-14452.jpg"


def test_image_name_without_an_image_id_uses_a_hash_of_the_url():
    name = image_name(12, "https://shop.test/other/olejek.jpg")
    assert name.startswith("12-") and name.endswith(".jpg") and name != "12-.jpg"
    assert name == image_name(12, "https://shop.test/other/olejek.jpg")


def test_images_command_is_registered(capsys):
    with pytest.raises(SystemExit):
        main(["images", "--help"])
    assert "--limit" in capsys.readouterr().out
