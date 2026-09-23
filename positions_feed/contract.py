"""The feed contract: its columns and the bounds every delivery is held to.

Bounds are taken from here and never from the input itself (datum 0.10). A file
that reaches any of them is refused whole rather than truncated, because a
silently shortened nightly file would look like closed positions downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# The client's column names, which are also the canonical field names except for
# ``share_class``, derived from ``fund_name`` rather than delivered.
SOURCE_COLUMNS: tuple[str, ...] = (
    "source_row_id",
    "account_id",
    "account_holder",
    "fund_name",
    "vintage_year",
    "commitment",
    "nav",
    "nav_date",
    "currency",
    "status",
    "advisor_email",
)

EXPECTED_CURRENCY = "USD"

# A NAV more than this many times the commitment is flagged (W6). A fund worth
# over three or four times what was invested is exceptional, so five leaves room
# for a genuinely strong position while catching a dropped digit or a typo.
MAXIMUM_NAV_TO_COMMITMENT_MULTIPLE = Decimal("5")

# Private-market vintages before this are implausible for the funds this feed
# carries; the upper bound is the run year, since a fund cannot be vintaged later.
EARLIEST_VINTAGE_YEAR = 1980


@dataclass(frozen=True)
class FeedBounds:
    """Upper limits on a single delivery, each checked before the bytes are used."""

    maximum_file_size_bytes: int
    maximum_data_rows: int
    maximum_field_length: int


# Sized for the second batch (about 100k positions) with headroom, while still
# small enough that the whole file is safely held in memory for one pass.
CONTRACT_FEED_BOUNDS = FeedBounds(
    maximum_file_size_bytes=64 * 1024 * 1024,
    maximum_data_rows=200_000,
    maximum_field_length=256,
)
