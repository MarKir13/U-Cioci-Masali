"""Command line entry point: `python -m scraper` (run from the `scraper/` directory)."""

import argparse
import logging
import sys
from pathlib import Path

import requests

from . import config
from .http_client import HttpClient, SkippedURL
from .logging_config import setup_logging

log = logging.getLogger("scraper")


def validate_positive_float(value):
    try:
        float_value = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a real number")

    if float_value < config.MIN_DELAY:
        raise argparse.ArgumentTypeError(f"Delay option must be at least {config.MIN_DELAY}")

    return float_value


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

    # Parse the arguments
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    setup_logging(config.LOG_FILE, args.verbose)
    client = HttpClient(delay=args.delay)
    if args.command == "fetch": # start fetching
        return fetch_page(client, args.url, args.output)
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
