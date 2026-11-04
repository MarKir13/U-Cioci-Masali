"""Logging to the console and to a file."""

import logging
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_file: Path, verbose: bool = False) -> None:
    """Log INFO and above to the console (DEBUG with `verbose`) and everything to `log_file`."""
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)

    file = logging.FileHandler(log_file, encoding="utf-8")
    file.setLevel(logging.DEBUG)

    logging.basicConfig(level=logging.DEBUG, format=FORMAT, handlers=[console, file], force=True)
    # urllib3 logs every connection at DEBUG level, which would drown our own messages.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
