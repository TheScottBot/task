"""Exception types raised by the positions feed job."""

from __future__ import annotations


class FeedRefusedError(Exception):
    """Raised when a delivered file cannot be accepted as a feed at all.

    Distinct from a rejected record: a refused file has nothing trustworthy in
    it, so no row is validated and nothing reaches the store. ``reason_category``
    is a fixed code, safe to log, and never carries any of the file's content.
    """

    def __init__(self, reason_category: str) -> None:
        super().__init__(reason_category)
        self.reason_category = reason_category
