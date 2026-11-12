"""Command line entry point: `python -m scraper` (run from the `scraper/` directory)."""

import argparse
import logging
import sys
from pathlib import Path

import requests

from . import config
from .crawl import Crawler, PageCache
from .http_client import HttpClient, SkippedURL, check_delay
from .images import ImageDownloader
from .logging_config import setup_logging
from .models import export_schema
from .publish import make_archive, make_samples
from .verify import run as run_verify

log = logging.getLogger("scraper")


def validate_positive_float(value):
    try:
        float_value = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a real number") from None

    try:
        return check_delay(float_value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Delay option must be a finite number of at least {config.MIN_DELAY} and at most {config.MAX_DELAY}"
        ) from None


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a whole number") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main(argv: list[str] | None = None) -> int:

    # Create a parser for running with args from terminal
    parser = argparse.ArgumentParser(
        prog="python -m scraper",
        description="Scraper of magiczne-indie.pl for the U Cioci Masali project.",
    )

    # Delay argument
    parser.add_argument(
        "--delay",
        type=validate_positive_float,
        default=config.DEFAULT_DELAY,
        help=f"seconds between requests (default: {config.DEFAULT_DELAY})",
    )

    # Verbosity argument
    parser.add_argument("-v", "--verbose", action="store_true", help="show DEBUG messages in the console")

    # Subcommands
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Fetch subcommand
    fetch = commands.add_parser("fetch", help="download one page, e.g. to save a test fixture")
    fetch.add_argument("url", help="absolute URL, or a path such as /8-kosmetyki")
    fetch.add_argument("-o", "--output", type=Path, help="save the response body to this file")

    # Crawl subcommand
    crawl = commands.add_parser("crawl", help="download categories and products into scraper-results/ (resumable)")
    crawl.add_argument(
        "--limit",
        type=positive_int,
        metavar="N",
        help="test run: at most N new pages in each stage (categories, listing pages, products)",
    )
    crawl.add_argument("--no-cache", action="store_true", help="do not read or write saved pages in scraper/cache/")

    # Images subcommand
    images = commands.add_parser(
        "images", help="download product images into scraper-results/images/ and fit them to the store's limits"
    )
    images.add_argument("--limit", type=positive_int, metavar="N", help="test run: download at most N new images")

    # Commands for the finished results (no network)
    commands.add_parser("verify", help="check the results against the requirements and write verification-report.md")
    sample = commands.add_parser(
        "sample", help=f"copy {config.SAMPLE_COUNT} sample images to {config.SAMPLE_IMAGES_DIR.name}/ (committed)"
    )
    sample.add_argument("--seed", type=int, default=1, help="random seed, so the same selection can be repeated")
    commands.add_parser("archive", help=f"pack all images into {config.IMAGES_ARCHIVE.name} for the GitHub Release")

    # Schema subcommand
    commands.add_parser("schema", help=f"write the JSON schema of the results to {config.SCHEMA_FILE.name}")

    # Parse the arguments
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    setup_logging(config.LOG_FILE, args.verbose)
    if args.command == "schema":  # needs no network
        export_schema(config.SCHEMA_FILE)
        return 0
    if args.command == "verify":
        return run_verify()
    if args.command == "sample":
        return make_samples(seed=args.seed)
    if args.command == "archive":
        return make_archive()
    client = HttpClient(delay=args.delay)
    if args.command == "fetch":  # start fetching
        return fetch_page(client, args.url, args.output)
    if args.command == "crawl":
        cache = None if args.no_cache else PageCache(config.CACHE_DIR)
        return Crawler(client, cache=cache, limit=args.limit).run()
    if args.command == "images":
        return ImageDownloader(client, limit=args.limit).run()
    return 0


def fetch_page(client: HttpClient, url: str, output: Path | None) -> int:
    try:
        response = client.get(url)
    # Already logged by the client (robots.txt or outside the shop)
    except SkippedURL:
        return 1
    except requests.RequestException as exc:
        log.error("Could not download %s: %s", url, exc)
        return 1

    if output:
        output.write_bytes(response.content)
        log.info("Saved %d bytes to %s", len(response.content), output)
    else:
        log.info("%d %s, %d bytes", response.status_code, response.headers.get("Content-Type"), len(response.content))
    return 0


if __name__ == "__main__":
    sys.exit(main())
