"""One-command data init (issue #71): the images, then the shop, then the import.

    docker compose -f deploy/compose.yaml --profile init run --rm --build init [--subset] [importer options]

1. Images: if a file this run needs is missing from scraper-results/images/, download the archive from the
   GitHub Release, check its sha256 and unpack it. This needs no shop, so it runs while the shop is still
   installing (the `init` service has no depends_on for that reason).
2. Shop: wait until it answers, the same check as its Compose healthcheck.
3. Import: the importer (importer/__main__.py) on the same data, in this process.

--subset: only the products of SUBSET.categories, with the small archive (CI, quick checks).
Exit codes are the importer's: 0 done, 1 something rejected, 2 could not start (here also: no images, no shop).
"""

import argparse
import hashlib
import logging
import os
import socket
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from . import data, mapping
from .__main__ import main as run_importer
from .__main__ import setup_logging

log = logging.getLogger("importer")

RELEASE = "https://github.com/MarKir13/U-Cioci-Masali/releases/download/images-v1"


@dataclass(frozen=True)
class Archive:
    name: str  # the file in the Release
    sha256: str
    categories: tuple[int, ...] = ()  # only these source categories and their subcategories; empty: all products


# Both made by `python -m scraper archive` (scraper/README.md, "Publishing the images"). A new build has a new hash.
FULL = Archive("product-images.tar.gz", "54e3a0d705e5256a2f1bfee998f6176dc7164d78bd43c9208b0355d7b5f770c5")
# Przyprawy (under Żywność) and Pielęgnacja okolic oczu (under Kosmetyki): two branches of the top menu with enough
# products in stock for the E2E scenario. Made with `archive --categories 85,99`; change both together.
SUBSET = Archive("subset-images.tar.gz", "ee7bab8b91855d2c75c1140384815c4643c5d993819617f1ac897925a06b63b6", (85, 99))

# The shop on the Compose network. Apache starts only after the install and the post-install scripts, so an answer
# means the shop is ready: the same test as the healthcheck in compose.yaml.
SHOP_HOST = "shop"
SHOP_URL = f"http://{SHOP_HOST}/"
# The healthcheck allows 10 minutes for the first install (start_period); a slow machine gets 5 more
SHOP_WAIT_SECONDS = 15 * 60
# "shop" does not resolve when its container is not running: then init stops instead of waiting 15 minutes
SHOP_MISSING_SECONDS = 30
POLL_SECONDS = 5

FALLBACK = """The images can instead be downloaded from the source shop. That takes about 1 h 40 min (at most
2 requests per second, robots.txt respected) and can be interrupted and resumed. To start it, run:
    docker compose -f deploy/compose.yaml --profile init run --rm --build scraper images
and then run init again."""
# AGENTS.md rule 7: tests and CI never touch the source shop
FALLBACK_IN_CI = "In CI the images are never downloaded from the source shop: fix the Release or IMAGES_URL."


class InitError(Exception):
    """Init cannot go on. The message says what to do."""


class ImagesUnavailable(InitError):
    """The archive could not be downloaded or is not the published one; the fallback can help."""


def parse_args(argv: list[str] | None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="init",
        description="Images, then wait for the shop, then the import",
        epilog="Other options go to the importer, for example --workers 4 or --verbose.",
    )
    parser.add_argument(
        "--subset",
        action="store_true",
        help=f"only categories {', '.join(map(str, SUBSET.categories))} with the small archive",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("/data"), help="scraper-results folder")
    parser.add_argument("--log-file", type=Path, default=Path("/logs/importer.log"))
    return parser.parse_known_args(argv)


# --- 1. Images ----------------------------------------------------------------------------------------


def needed_files(data_dir: Path, archive: Archive) -> list[Path]:
    """The image files of the products this run imports: all of them, or only those of archive.categories."""
    schema = data.load_schema(data_dir)
    products, _, _ = data.load_products(data_dir, schema)
    if archive.categories:
        categories, _ = data.load_categories(data_dir, schema)
        wanted = mapping.with_descendants(set(archive.categories), categories)
        products = [p for p in products if wanted & set(p["category_ids"])]
    return sorted({data_dir / image["local_path"] for p in products for image in p["images"]})


def ensure_images(data_dir: Path, archive: Archive, url: str) -> None:
    """Downloads and unpacks the archive unless every needed file is already there."""
    needed = needed_files(data_dir, archive)
    missing = [file for file in needed if not file.is_file()]
    if not missing:
        log.info("images: all %d files are in place, nothing to download", len(needed))
        return
    log.info("images: %d of %d files missing, downloading %s", len(missing), len(needed), url)
    # *.tar.gz is in .gitignore, so the download never shows up in git
    path = download(url, data_dir / archive.name.replace(".tar.gz", ".download.tar.gz"), archive.sha256)
    try:
        unpack(path, data_dir)
    finally:
        path.unlink(missing_ok=True)
    still_missing = [file for file in needed if not file.is_file()]
    if still_missing:
        raise ImagesUnavailable(
            f"the archive lacks {len(still_missing)} files this run needs, for example {still_missing[0].name}: "
            "it does not match products.jsonl"
        )
    log.info("images: unpacked, all %d files are in place", len(needed))


def download(url: str, target: Path, sha256: str) -> Path:
    """Saves `url` to `target` and checks its sha256. On any failure nothing is left behind."""
    digest = hashlib.sha256()
    try:
        with requests.get(url, stream=True, timeout=(30, 120)) as response:
            if response.status_code != 200:
                raise ImagesUnavailable(f"HTTP {response.status_code} for {url}")
            total = int(response.headers.get("Content-Length") or 0)
            done, next_report = 0, 0.1
            with target.open("wb") as file:
                for block in response.iter_content(1 << 20):
                    file.write(block)
                    digest.update(block)
                    done += len(block)
                    if total and done >= next_report * total:
                        log.info("images: %3.0f%% of %d MB", 100 * done / total, total // 1_000_000)
                        next_report += 0.1
    except requests.RequestException as error:
        target.unlink(missing_ok=True)
        raise ImagesUnavailable(f"the download from {url} failed: {error}") from None
    except ImagesUnavailable:
        target.unlink(missing_ok=True)
        raise
    if digest.hexdigest() != sha256:
        target.unlink(missing_ok=True)
        raise ImagesUnavailable(f"{url} is not the published archive: sha256 {digest.hexdigest()}, expected {sha256}")
    return target


def unpack(path: Path, data_dir: Path) -> None:
    """Unpacks images/ from the archive into data_dir. Anything else in the archive refuses the whole archive.

    Each file is written as <name>.partial and renamed when complete, so an interrupted unpack (Ctrl+C) never
    leaves a half-written image under its real name, which the next run would take as present. tarfile's "data"
    filter also refuses links and absolute or ../ paths, so the archive cannot write outside data_dir.
    """
    # Left by an interrupted run; never needed, and would otherwise end up in a rebuilt archive
    for leftover in (data_dir / "images").glob("*.partial"):
        leftover.unlink()
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        outside = [m.name for m in members if not _in_images(m)]
        if outside:
            raise ImagesUnavailable(f"the archive holds more than images/, for example {outside[0]}")
        for member in members:
            if member.isfile():  # the images/ folder itself is created with its first file
                archive.extract(member.replace(name=member.name + ".partial"), data_dir, filter="data")
                os.replace(data_dir / f"{member.name}.partial", data_dir / member.name)


def _in_images(member: tarfile.TarInfo) -> bool:
    if member.isdir():
        return member.name.rstrip("/") == "images"
    folder, _, name = member.name.partition("/")
    return member.isfile() and folder == "images" and name != "" and "/" not in name


def give_to_owner(data_dir: Path) -> None:
    """Files this root container wrote get the owner of scraper-results/ (Linux; Docker Desktop needs nothing).

    On Linux a bind-mounted folder keeps the numbers of its owner, and files written by root would stay root's,
    so the user could not delete them without sudo. Docker Desktop (Windows, macOS) shows the folder as root's
    and maps the files to the user by itself.
    """
    if not hasattr(os, "getuid") or os.getuid() != 0:
        return
    owner = data_dir.stat()
    if owner.st_uid == 0:
        return
    for path in data_dir.rglob("*"):
        if path.stat().st_uid == 0:
            try:
                os.chown(path, owner.st_uid, owner.st_gid)
            except OSError as error:
                log.warning("images: could not give %s to its folder's owner: %s", path, error)
                return


# --- 2. Shop ------------------------------------------------------------------------------------------


def check_shop_container(wait=SHOP_MISSING_SECONDS, clock=time.monotonic, sleep=time.sleep, resolve=socket.getaddrinfo):
    """Stops early when the shop's container is not running: then its name does not resolve on the network."""
    deadline = clock() + wait
    while True:
        try:
            resolve(SHOP_HOST, 80)
            return
        except OSError:
            if clock() >= deadline:
                raise InitError(
                    "the shop is not running: start it with `docker compose -f deploy/compose.yaml up -d`, "
                    "then run init again"
                ) from None
            sleep(1)


def wait_for_shop(timeout=SHOP_WAIT_SECONDS, clock=time.monotonic, sleep=time.sleep, get=requests.get) -> None:
    """Waits until the shop answers without an error, polling every POLL_SECONDS."""
    started = reported = clock()
    while True:
        try:
            if get(SHOP_URL, timeout=5, allow_redirects=False).status_code < 400:
                log.info("shop: ready after %.0f s", clock() - started)
                return
        except requests.RequestException:
            pass  # Apache is not up yet: the install is still running
        now = clock()
        if now - started >= timeout:
            raise InitError(
                f"the shop did not get ready within {timeout // 60} minutes: see "
                "`docker compose -f deploy/compose.yaml logs shop` and look for [setup] FAILED"
            )
        if now - reported >= 30:
            log.info("shop: still installing (%.0f s)", now - started)
            reported = now
        sleep(POLL_SECONDS)


# --- Everything in order ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args, importer_args = parse_args(argv)
    setup_logging(args.log_file, verbose="--verbose" in importer_args)
    started = time.monotonic()
    archive = SUBSET if args.subset else FULL
    # IMAGES_URL replaces the Release address, for example to try what happens when the file is missing
    url = os.environ.get("IMAGES_URL") or f"{RELEASE}/{archive.name}"
    log.info("init: %s", f"subset, categories {list(archive.categories)}" if archive.categories else "all products")

    try:
        check_shop_container()
        try:
            ensure_images(args.data_dir, archive, url)
        finally:
            give_to_owner(args.data_dir)
        wait_for_shop()
    except ImagesUnavailable as error:
        log.error("images: %s", error)
        log.error("%s", FALLBACK_IN_CI if os.environ.get("CI") else FALLBACK)
        return 2
    except InitError as error:
        log.error("%s", error)
        return 2

    importer_argv = ["--data-dir", str(args.data_dir), "--log-file", str(args.log_file), *importer_args]
    if archive.categories:
        importer_argv += ["--categories", ",".join(map(str, archive.categories))]
    code = run_importer(importer_argv)
    if code == 0:
        port = os.environ.get("HTTPS_PORT", "8443")
        log.info("init: done in %.0f s, the shop is at https://localhost:%s", time.monotonic() - started, port)
    else:
        log.error("init: the import ended with exit code %d, see the messages above", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
