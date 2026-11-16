"""Loads scraper-results/ into the shop through the Webservice API (issue #70, D2).

    docker compose -f deploy/compose.yaml --profile init run --rm importer [options]

Options are listed by --help. Exit code: 0 when everything was saved, 1 when anything was rejected (the
reasons are in the log), 2 when the import could not start (no key, shop not reachable).
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import requests

from . import data, mapping, steps
from .api import ApiError, ShopApi
from .config import Config, ConfigError
from .report import Report

log = logging.getLogger("importer")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="importer", description="Import scraper-results/ into the shop")
    parser.add_argument("--data-dir", type=Path, default=Path("/data"), help="scraper-results folder")
    parser.add_argument("--log-file", type=Path, default=Path("/logs/importer.log"))
    parser.add_argument("--limit", type=int, help="import only the first N products (for development)")
    parser.add_argument(
        "--categories", help="import only products of these source category IDs and their subcategories, e.g. 8,193"
    )
    parser.add_argument("--workers", type=int, default=8, help="products handled at the same time (default 8)")
    parser.add_argument("--dry-run", action="store_true", help="read and compare everything, write nothing")
    parser.add_argument("--verbose", action="store_true", help="show DEBUG messages on the console")
    return parser.parse_args(argv)


def setup_logging(log_file: Path, verbose: bool) -> None:
    """INFO and above on the console, everything in the log file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    file = logging.FileHandler(log_file, encoding="utf-8")
    file.setLevel(logging.DEBUG)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[console, file],
        force=True,
    )
    # urllib3 logs every connection at DEBUG level, which would drown our own messages
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def select_products(products: list[dict], categories: list[dict], args: argparse.Namespace) -> list[dict]:
    if args.categories:
        wanted = {int(i) for i in args.categories.split(",") if i.strip()}
        wanted = mapping.with_descendants(wanted, categories)
        products = [p for p in products if wanted & set(p["category_ids"])]
    if args.limit is not None:
        products = products[: args.limit]
    return products


def run(api: ShopApi, args: argparse.Namespace) -> int:
    started = time.monotonic()
    report = Report()

    # Step 0: the data, validated, and what the shop already has
    schema = data.load_schema(args.data_dir)
    categories, rejected = data.load_categories(args.data_dir, schema)
    for source_id, reason in rejected:
        report.reject("categories", source_id, reason)
    products, rejected, unreadable = data.load_products(args.data_dir, schema)
    for source_id, reason in rejected:
        report.reject("products", source_id, reason)
    for line_number, reason in unreadable:
        report.reject("products", f"products.jsonl line {line_number}", reason)
    # Rejected products are still in the data: the delete step must keep their copies in the shop
    rejected_product_ids = {source_id for source_id, _ in rejected}
    full_run = not args.limit and not args.categories
    selected = select_products(products, categories, args)
    log.info("data: %d categories, %d products (%d selected)", len(categories), len(products), len(selected))

    api.load_languages()
    shop = steps.read_shop(api)
    log.info("shop: %d products, %d categories before the import", len(shop.all_products), len(shop.categories))

    # Steps 1-2: categories (all of them, also for a subset) and brands
    category_ids = steps.import_categories(api, shop, categories, report)
    brand_ids = steps.import_manufacturers(api, shop, products, report)

    # Steps 3-6: each product with its stock, promotion and images, several at a time
    steps.import_products(api, shop, selected, category_ids, brand_ids, args.data_dir, args.workers, report)

    # Step 7: the installer's demo catalogue and anything else that is not in the data
    if full_run:
        steps.remove_other_records(
            api, shop, products, rejected_product_ids, category_ids, brand_ids, report, all_lines_read=not unreadable
        )
    else:
        log.info("subset run (--limit or --categories): nothing is deleted")

    log.info("summary%s:\n%s", " (dry run, nothing written)" if args.dry_run else "", report.summary())
    log.info("finished in %.0f s; log: %s", time.monotonic() - started, args.log_file)
    if report.rejected:
        log.error("%d record(s) rejected, see REJECTED lines in the log", report.rejected)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(args.log_file, args.verbose)
    try:
        config = Config.from_environment()
    except ConfigError as error:
        log.error("%s", error)
        return 2
    api = ShopApi(config.api_url, config.shop_domain, config.key, dry_run=args.dry_run)
    try:
        api.check()
    except ApiError as error:
        hints = {
            302: f"the shop redirects: SHOP_DOMAIN/HTTPS_PORT must give its own domain (now {config.shop_domain})",
            401: "the key was refused: check PS_WEBSERVICE_KEY and run post-install/40-webservice.sh",
            503: "the Webservice API is off: run post-install/40-webservice.sh",
        }
        log.error("cannot use the API at %s: %s", config.api_url, hints.get(error.status, error.message))
        return 2
    except requests.ConnectionError:
        log.error("the shop is not reachable at %s: is the `shop` container running and healthy?", config.api_url)
        return 2
    return run(api, args)


if __name__ == "__main__":
    sys.exit(main())
