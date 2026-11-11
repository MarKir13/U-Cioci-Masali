"""Download product images and fit them to the store's limits.

Every image listed in products.jsonl is downloaded from the shop (the `product_main_2x` size, 1440 px)
and saved as images/<product id>-<number>.jpg, with the longer side between 800 and 1600 px and at most
300 KB. The file name goes into `local_path` of the image in products.jsonl.

Resuming: a file that is already on disk is never downloaded again, and a source URL that gave a bad image
(too small, corrupted) is remembered in image_problems.json. Files appear under their final name only when
complete (`save_bytes`), and products.jsonl is rewritten the same way, so Ctrl+C at any moment is safe.
"""

import io
import json
import logging
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config
from .crawl import load_json, load_lines, save_json
from .http_client import HttpClient, SkippedURL

log = logging.getLogger(__name__)


class ImageProblem(Exception):
    """The downloaded bytes cannot be turned into a usable image. The message says why."""


class CorruptImage(ImageProblem):
    pass


class TooSmallImage(ImageProblem):
    pass


class TooLargeImage(ImageProblem):
    """Even the smallest allowed picture at the lowest quality is over the size limit."""


# ---------- Processing (no network, no files) ----------


def _to_rgb(image: Image.Image) -> Image.Image:
    """JPEG has no transparency and no palette: transparent areas become white."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _encode(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def _best_quality(image: Image.Image, max_bytes: int) -> bytes | None:
    """The highest quality whose JPEG fits in `max_bytes`, or None if even the lowest does not.

    Size grows with quality, so a binary search needs about 6 encodings instead of 50.
    """
    data = _encode(image, config.IMAGE_QUALITY_START)
    if len(data) <= max_bytes:
        return data
    low, high = config.IMAGE_QUALITY_MIN, config.IMAGE_QUALITY_START - 1
    best = None
    while low <= high:
        middle = (low + high) // 2
        data = _encode(image, middle)
        if len(data) <= max_bytes:
            best, low = data, middle + 1
        else:
            high = middle - 1
    return best


def _scaled(image: Image.Image, longer_side: int) -> Image.Image:
    factor = longer_side / max(image.size)
    size = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    return image.resize(size, Image.Resampling.LANCZOS)


def process_image(
    data: bytes,
    min_side: int = config.IMAGE_MIN_SIDE,
    max_side: int = config.IMAGE_MAX_SIDE,
    max_bytes: int = config.IMAGE_MAX_BYTES,
) -> bytes:
    """JPEG bytes of the picture in `data`: longer side in [min_side, max_side], at most `max_bytes`.

    A picture is never enlarged, so one whose longer side is below `min_side` is `TooSmallImage`.
    One above `max_side` is scaled down to it. If the file is still too big, the quality is lowered
    first (see `_best_quality`), and only then the picture is shrunk, down to `min_side`.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()  # open() reads only the header; a cut-off file fails here
            image = ImageOps.exif_transpose(opened)  # apply the camera rotation before measuring
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise CorruptImage(f"cannot be read as an image: {exc}") from exc

    longer = max(image.size)
    if longer < min_side:
        raise TooSmallImage(f"longer side is {longer} px, the minimum is {min_side} px")

    image = _to_rgb(image)
    side = min(longer, max_side)
    while True:
        candidate = image if side == longer else _scaled(image, side)
        result = _best_quality(candidate, max_bytes)
        if result is not None:
            return result
        if side <= min_side:
            raise TooLargeImage(f"over {max_bytes} bytes even at {min_side} px and quality {config.IMAGE_QUALITY_MIN}")
        side = max(min_side, int(side * config.IMAGE_SHRINK_STEP))


# ---------- Files ----------


def save_bytes(path: Path, data: bytes) -> None:
    """Write `data` so that `path` is either missing or complete, never half-written."""
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def save_lines(path: Path, records: list[dict]) -> None:
    """Rewrite a JSON Lines file in one step (the counterpart of crawl.append_line)."""
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def image_name(product_id: int, number: int) -> str:
    return f"{product_id}-{number}.jpg"


# ---------- The run ----------


@dataclass
class ImageDownloader:
    client: HttpClient
    results_dir: Path = config.RESULTS_DIR
    limit: int | None = None
    # How often products.jsonl is rewritten while downloading, in downloaded images
    save_every: int = 50

    def __post_init__(self):
        self.products_file = self.results_dir / config.PRODUCTS_FILE.name
        self.images_dir = self.results_dir / config.IMAGES_DIR.name
        self.problems_file = self.results_dir / config.IMAGE_PROBLEMS_FILE.name

    def run(self) -> int:
        """Download every missing image. Returns the exit code for the command line."""
        products = load_lines(self.products_file)
        if not products:
            log.error("No products in %s. Run `python -m scraper crawl` first.", self.products_file)
            return 1
        try:
            self.client.load_robots()
        except requests.RequestException as exc:
            log.error("Could not read robots.txt, stopping: %s", exc)
            return 1

        self.images_dir.mkdir(parents=True, exist_ok=True)
        problems: dict[str, str] = load_json(self.problems_file, {})
        stats = Counter()
        try:
            self._process(products, problems, stats)
        except KeyboardInterrupt:
            log.warning("Interrupted. Everything saved so far is kept; run the same command to resume.")
            self._save(products, problems)
            return 130
        self._save(products, problems)
        self._report(products, problems, stats)
        return 0

    def _process(self, products: list[dict], problems: dict[str, str], stats: Counter) -> None:
        since_save = 0
        for product in products:
            for number, image in enumerate(product["images"], start=1):
                name = image_name(product["id"], number)
                path = self.images_dir / name
                url = image["source_url"]
                relative = f"{self.images_dir.name}/{name}"

                if path.exists():
                    image["local_path"] = relative
                    stats["already on disk"] += 1
                    continue
                image["local_path"] = None
                if url in problems:
                    stats["known problem"] += 1
                    continue
                if self.limit is not None and stats["downloaded"] >= self.limit:
                    stats["left for later"] += 1
                    continue

                stats["downloaded"] += 1
                if self._download(product["id"], url, path, problems, stats):
                    image["local_path"] = relative
                    stats["saved"] += 1
                since_save += 1
                if since_save >= self.save_every:
                    self._save(products, problems)
                    since_save = 0

    def _download(self, product_id: int, url: str, path: Path, problems: dict[str, str], stats: Counter) -> bool:
        """Download and save one image. True if the file was saved; otherwise the reason is logged."""
        try:
            response = self.client.get(url)
        except SkippedURL:  # already logged by the client
            stats["failed"] += 1
            return False
        except requests.RequestException as exc:
            log.error("Product %d: could not download %s: %s", product_id, url, exc)
            stats["failed"] += 1
            return False

        try:
            data = process_image(response.content)
        except ImageProblem as exc:
            # Not remembered as "failed": the same bytes would fail again, so later runs skip this URL
            log.warning("Product %d: image %s %s", product_id, url, exc)
            problems[url] = f"{type(exc).__name__}: {exc}"
            stats["too small" if isinstance(exc, TooSmallImage) else "unusable"] += 1
            return False
        save_bytes(path, data)
        log.debug("Saved %s (%d bytes)", path.name, len(data))
        return True

    def _save(self, products: list[dict], problems: dict[str, str]) -> None:
        save_lines(self.products_file, products)
        save_json(self.problems_file, problems)

    def _report(self, products: list[dict], problems: dict[str, str], stats: Counter) -> None:
        total = sum(len(product["images"]) for product in products)
        with_file = sum(1 for product in products for image in product["images"] if image["local_path"])
        log.info("Images: %d of %d have a file. %s", with_file, total, dict(stats))
        without = [product["id"] for product in products if not any(image["local_path"] for image in product["images"])]
        if without:
            log.error(
                "%d products have no usable image (W2 needs at least one each): %s%s",
                len(without),
                without[:20],
                " ..." if len(without) > 20 else "",
            )
        for url, reason in problems.items():
            log.warning("Unusable source image %s: %s", url, reason)
