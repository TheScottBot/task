"""Shared fixtures, builders and constants for the positions feed test suite.

Every row built here is synthetic. The only other fixture is the provided
fictional sample feed, read in place from ``AdditionalReferences`` so there is
exactly one copy of it in the tree.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from positions_feed.contract import SOURCE_COLUMNS
from positions_feed.feed_reader import RawFeedRow
from positions_feed.store import PositionStore

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_FEED_PATH = REPOSITORY_ROOT / "AdditionalReferences" / "sample-positions-feed.csv"

FIXED_INGESTION_MOMENT = datetime(2026, 9, 23, 2, 0, tzinfo=UTC)
FIXED_RUN_DATE = FIXED_INGESTION_MOMENT.date()

# Every account holder and advisor email in the sample feed. Anything emitted
# (report, summary, log) is checked against these, because both are personal data.
SAMPLE_FEED_ACCOUNT_HOLDERS = (
    "Halloway Family Trust",
    "Beaumont Holdings LP",
    "Alvarez Revocable Trust",
    "Donnelly Irrevocable Trust",
    "Osei Family Office",
    "Petrova 2015 Trust",
    "Chen & Associates Pension",
    "Lindqvist Stiftelse",
    "Okafor Dynasty Trust",
    "Rasmussen Holdings",
    "Fernandez 2020 Trust",
    "Baird Family Partnership",
    "Vaughn Charitable Trust",
)
SAMPLE_FEED_ADVISOR_EMAILS = (
    "k.brennan@meridiancap.example",
    "s.okafor@meridiancap.example",
    "j.lam@meridiancap.example",
)


def build_clean_row_values(**overrides: str) -> dict[str, str]:
    """Return one synthetic, fully valid feed row, with named columns overridden."""
    clean_row_values = {
        "source_row_id": "test-0001",
        "account_id": "TA-00001",
        "account_holder": "Synthetic Test Holder",
        "fund_name": "Synthetic Fund I",
        "vintage_year": "2020",
        "commitment": "1000000",
        "nav": "900000.00",
        "nav_date": "2026-03-31",
        "currency": "USD",
        "status": "Active",
        "advisor_email": "advisor@example.test",
    }
    unknown_columns = set(overrides) - set(clean_row_values)
    if unknown_columns:
        raise KeyError(f"Not feed columns: {sorted(unknown_columns)}")
    clean_row_values.update(overrides)
    return clean_row_values


def build_raw_row(row_number: int = 1, **overrides: str) -> RawFeedRow:
    """Return a well-shaped ``RawFeedRow`` built from a clean synthetic row."""
    return RawFeedRow(
        row_number=row_number,
        values_by_column=build_clean_row_values(**overrides),
        field_count=len(SOURCE_COLUMNS),
    )


def write_feed_file(
    directory: Path,
    rows: Sequence[dict[str, str]],
    header: Sequence[str] = SOURCE_COLUMNS,
    file_name: str = "positions-feed.csv",
) -> Path:
    """Write rows as a CRLF CSV feed, the line ending the client's export uses."""
    feed_path = directory / file_name
    with feed_path.open("w", encoding="utf-8", newline="") as feed_file:
        feed_writer = csv.writer(feed_file, lineterminator="\r\n")
        feed_writer.writerow(header)
        for row_values in rows:
            feed_writer.writerow([row_values[column_name] for column_name in header])
    return feed_path


@pytest.fixture
def in_memory_position_store() -> Iterator[PositionStore]:
    """An isolated in-memory store; the idempotency logic, not the file, is under test."""
    position_store = PositionStore.open_in_memory()
    yield position_store
    position_store.close()
