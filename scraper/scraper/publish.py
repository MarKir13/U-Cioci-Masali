"""Prepare the images for publishing: a few sample files for git and one archive for GitHub Releases. No network."""

import hashlib
import logging
import random
import shutil
import tarfile
from pathlib import Path

from . import config
from .crawl import load_lines

log = logging.getLogger(__name__)


def make_samples(results_dir: Path = config.RESULTS_DIR, count: int = config.SAMPLE_COUNT, seed: int = 1) -> int:
    """Copy the first image of `count` randomly chosen products into sample-images/. Returns the exit code.

    The choice depends only on `seed` and the products, so the same results give the same samples. Files from an
    earlier call are removed first, so the folder always holds exactly this selection.
    """
    products = [
        product
        for product in load_lines(results_dir / config.PRODUCTS_FILE.name)
        if any(image.get("local_path") for image in product["images"])
    ]
    if not products:
        log.error("No product has an image file. Run `python -m scraper images` first.")
        return 1
    chosen = random.Random(seed).sample(sorted(products, key=lambda p: p["id"]), min(count, len(products)))
    target = results_dir / config.SAMPLE_IMAGES_DIR.name
    target.mkdir(exist_ok=True)
    for old in target.glob("*.jpg"):
        old.unlink()
    for product in chosen:
        source = results_dir / next(image["local_path"] for image in product["images"] if image.get("local_path"))
        shutil.copy2(source, target / source.name)
    log.info("Copied %d sample images to %s", len(chosen), target)
    return 0


def make_archive(results_dir: Path = config.RESULTS_DIR, output: Path | None = None) -> int:
    """Pack images/ into one tar.gz for the GitHub Release. Returns 1 if there are no images or it is too big."""
    images_dir = results_dir / config.IMAGES_DIR.name
    files = sorted(images_dir.glob("*.jpg")) if images_dir.is_dir() else []
    if not files:
        log.error("No images in %s. Run `python -m scraper images` first.", images_dir)
        return 1
    output = output or results_dir / config.IMAGES_ARCHIVE.name
    temporary = output.with_name(output.name + ".part")
    with tarfile.open(temporary, "w:gz") as archive:
        for file in files:
            archive.add(file, arcname=f"{images_dir.name}/{file.name}")
    size = temporary.stat().st_size
    if size > config.ARCHIVE_MAX_BYTES:
        temporary.unlink()
        log.error("The archive would be %d bytes, over the limit of %d", size, config.ARCHIVE_MAX_BYTES)
        return 1
    temporary.replace(output)
    digest = hashlib.sha256()
    with output.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    log.info("Wrote %s: %d images, %d bytes, sha256 %s", output, len(files), size, digest.hexdigest())
    return 0
