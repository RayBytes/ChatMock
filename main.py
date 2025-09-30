"""Entry point helper for ChatMock."""

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entry, prints a friendly startup line."""
    logger.info("Hello from chatmock!")


if __name__ == "__main__":
    main()
