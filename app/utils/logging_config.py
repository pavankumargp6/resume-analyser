"""Safe default logging configuration."""

import logging


def configure_logging() -> None:
    """Configure application logs without recording user resume content."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
