"""NAV date normalisation: which input formats are accepted, and which are refused.

The client's legacy system emits some NAV dates in formats other than ISO. The
whole policy lives in ``_NAV_DATE_FORMATS``, so a change to it is a change to
that one table.

Current policy, set by the author on 23 September 2026 and put to the client:

* ISO 8601 ``YYYY-MM-DD`` is canonical and is not a normalisation.
* ``DD-Mon-YYYY`` with an English month abbreviation, in any letter case, is
  normalised to ISO: a written month cannot be misread.
* A numeric slash date is recognised but always refused. Without confirmation
  that the source writes one convention, month first or day first, reading it
  would be a guess, and a guessed valuation date is worse than a flagged one. If
  the client confirms a convention, the slash entry gains a date builder for it.

Shapes are spelled with ``[0-9]`` rather than ``\\d`` because ``\\d`` also matches
non-ASCII digits, which ``int`` would then quietly accept.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

ISO_8601_FORMAT = "iso_8601"
DAY_MONTH_ABBREVIATION_YEAR_FORMAT = "day_month_abbreviation_year"
NUMERIC_SLASH_FORMAT = "numeric_slash"

UNRECOGNISED_FORMAT = "unrecognised_format"
SLASH_DATE_ORDER_UNCONFIRMED = "slash_date_order_unconfirmed"
NOT_A_CALENDAR_DATE = "not_a_calendar_date"

# Spelled out rather than read through strptime's %b, which follows the process
# locale and would accept different month names on a differently configured host.
_MONTH_NUMBER_BY_ABBREVIATION = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


@dataclass(frozen=True)
class NavDateParseResult:
    """A parsed date and the format it arrived in, or why it was refused."""

    parsed_date: date | None
    source_format: str | None
    failure_detail: str | None

    @property
    def was_normalised(self) -> bool:
        return self.parsed_date is not None and self.source_format != ISO_8601_FORMAT


def _build_iso_date(date_match: re.Match[str]) -> date:
    return date(int(date_match["year"]), int(date_match["month"]), int(date_match["day"]))


def _build_day_month_abbreviation_date(date_match: re.Match[str]) -> date:
    month_number = _MONTH_NUMBER_BY_ABBREVIATION.get(date_match["month"].lower())
    if month_number is None:
        raise LookupError(date_match["month"])
    return date(int(date_match["year"]), month_number, int(date_match["day"]))


@dataclass(frozen=True)
class _NavDateFormat:
    """A recognised shape, and how to build a date from it.

    ``build_date`` is ``None`` for a shape that is recognised only so it can be
    refused with a specific reason, rather than reported as unrecognised.
    """

    format_name: str
    shape: re.Pattern[str]
    build_date: Callable[[re.Match[str]], date] | None
    refusal_detail: str | None = None


_NAV_DATE_FORMATS: tuple[_NavDateFormat, ...] = (
    _NavDateFormat(
        ISO_8601_FORMAT,
        re.compile(r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})"),
        _build_iso_date,
    ),
    _NavDateFormat(
        DAY_MONTH_ABBREVIATION_YEAR_FORMAT,
        re.compile(r"(?P<day>[0-9]{2})-(?P<month>[A-Za-z]{3})-(?P<year>[0-9]{4})"),
        _build_day_month_abbreviation_date,
    ),
    _NavDateFormat(
        NUMERIC_SLASH_FORMAT,
        re.compile(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}"),
        None,
        SLASH_DATE_ORDER_UNCONFIRMED,
    ),
)


def parse_nav_date(raw_value: str) -> NavDateParseResult:
    """Parse a raw NAV date against the recognised formats, refusing rather than guessing."""
    for nav_date_format in _NAV_DATE_FORMATS:
        date_match = nav_date_format.shape.fullmatch(raw_value)
        if date_match is None:
            continue
        if nav_date_format.build_date is None:
            return NavDateParseResult(None, nav_date_format.format_name, nav_date_format.refusal_detail)
        try:
            parsed_date = nav_date_format.build_date(date_match)
        except LookupError:
            return NavDateParseResult(None, None, UNRECOGNISED_FORMAT)
        except ValueError:
            return NavDateParseResult(None, nav_date_format.format_name, NOT_A_CALENDAR_DATE)
        return NavDateParseResult(parsed_date, nav_date_format.format_name, None)
    return NavDateParseResult(None, None, UNRECOGNISED_FORMAT)
