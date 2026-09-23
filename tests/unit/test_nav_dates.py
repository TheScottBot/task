"""NAV date normalisation: the accepted formats and every way a date is refused.

The slash format is refused until the client confirms its day and month order, so
this file pins the current policy exactly. A change to the policy should change
these cases.
"""

from __future__ import annotations

from datetime import date

import pytest

from positions_feed.nav_dates import (
    DAY_MONTH_ABBREVIATION_YEAR_FORMAT,
    ISO_8601_FORMAT,
    NOT_A_CALENDAR_DATE,
    NUMERIC_SLASH_FORMAT,
    SLASH_DATE_ORDER_UNCONFIRMED,
    UNRECOGNISED_FORMAT,
    parse_nav_date,
)

# ── Accepted ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw_value, expected_date, expected_format",
    [
        ("2026-03-31", date(2026, 3, 31), ISO_8601_FORMAT),
        ("2028-02-29", date(2028, 2, 29), ISO_8601_FORMAT),
        ("31-Mar-2026", date(2026, 3, 31), DAY_MONTH_ABBREVIATION_YEAR_FORMAT),
        ("31-MAR-2026", date(2026, 3, 31), DAY_MONTH_ABBREVIATION_YEAR_FORMAT),
        ("01-jan-2026", date(2026, 1, 1), DAY_MONTH_ABBREVIATION_YEAR_FORMAT),
        ("29-Feb-2028", date(2028, 2, 29), DAY_MONTH_ABBREVIATION_YEAR_FORMAT),
        ("15-Dec-2025", date(2025, 12, 15), DAY_MONTH_ABBREVIATION_YEAR_FORMAT),
    ],
)
def test_parse_nav_date_accepts_supported_format(raw_value, expected_date, expected_format):
    parse_result = parse_nav_date(raw_value)
    assert parse_result.parsed_date == expected_date
    assert parse_result.source_format == expected_format
    assert parse_result.failure_detail is None


def test_parse_nav_date_iso_input_is_not_a_normalisation():
    assert parse_nav_date("2026-03-31").was_normalised is False


def test_parse_nav_date_written_month_input_is_a_normalisation():
    assert parse_nav_date("31-Mar-2026").was_normalised is True


# ── Refused: slash dates, until the client confirms one convention ────────────


@pytest.mark.parametrize(
    "raw_value",
    [
        # Only one reading is a real day, but the convention is still unconfirmed.
        "03/31/2026",
        "31/03/2026",
        "12/13/2026",
        # Both readings are real, different days.
        "03/04/2026",
        "01/12/2026",
        # Both readings are the same day; still not assumed.
        "05/05/2026",
        # Unpadded forms are the same format and are flagged the same way.
        "3/31/2026",
        "3/4/2026",
        # No reading is a real day, but the reason to give the client is the format.
        "02/30/2026",
        "13/13/2026",
    ],
)
def test_parse_nav_date_refuses_every_slash_date_as_order_unconfirmed(raw_value):
    parse_result = parse_nav_date(raw_value)
    assert parse_result.parsed_date is None
    assert parse_result.source_format == NUMERIC_SLASH_FORMAT
    assert parse_result.failure_detail == SLASH_DATE_ORDER_UNCONFIRMED
    assert parse_result.was_normalised is False


# ── Refused: the right shape but no such day ──────────────────────────────────


@pytest.mark.parametrize(
    "raw_value",
    [
        "2026-02-30",
        "2026-13-01",
        "2026-00-10",
        "0000-01-01",
        "29-Feb-2026",
        "32-Jan-2026",
        "00-Jan-2026",
    ],
)
def test_parse_nav_date_refuses_impossible_calendar_date(raw_value):
    parse_result = parse_nav_date(raw_value)
    assert parse_result.parsed_date is None
    assert parse_result.failure_detail == NOT_A_CALENDAR_DATE


# ── Refused: not an accepted shape at all ─────────────────────────────────────


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "2026-3-31",
        "03/31/26",
        "2026/03/31",
        "31.03.2026",
        "20260331",
        "31 March 2026",
        "31-Mrz-2026",
        "31-March-2026",
        "1-Mar-2026",
        " 2026-03-31",
        "2026-03-31 ",
        " 31-Mar-2026",
        "2026-03-31T00:00:00",
        # Non-ASCII digits match a bare \d, which is why the shapes spell out 0-9.
        "٢٠٢٦-٠٣-٣١",
        "٠٣/٣١/٢٠٢٦",
    ],
)
def test_parse_nav_date_refuses_unrecognised_format(raw_value):
    parse_result = parse_nav_date(raw_value)
    assert parse_result.parsed_date is None
    assert parse_result.failure_detail == UNRECOGNISED_FORMAT
