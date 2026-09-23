"""Reads a delivered feed file into raw rows, enforcing the contract's bounds.

The CSV crosses a trust boundary, so it is treated as hostile (datum 0.10): the
size is checked before a byte is decoded, every field is length-checked before
anything is interpreted, the header must match the contract exactly, and any
structural failure refuses the whole file rather than reading around it.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from .contract import CONTRACT_FEED_BOUNDS, SOURCE_COLUMNS, FeedBounds
from .exceptions import FeedRefusedError


@dataclass(frozen=True)
class RawFeedRow:
    """One data row as delivered, before any validation.

    ``values_by_column`` is ``None`` when the row's field count does not match
    the header: with columns out of step there is no trustworthy mapping, and
    the row is rejected whole rather than guessed at.
    """

    row_number: int
    values_by_column: dict[str, str] | None
    field_count: int


def _read_bounded_bytes(feed_path: Path, maximum_file_size_bytes: int) -> bytes:
    try:
        if feed_path.stat().st_size > maximum_file_size_bytes:
            raise FeedRefusedError("file_too_large")
        with feed_path.open("rb") as feed_file:
            # Read one byte past the bound so a file still growing after the
            # size check (an upload in progress) is caught rather than truncated.
            feed_bytes = feed_file.read(maximum_file_size_bytes + 1)
    except OSError as read_error:
        raise FeedRefusedError("unreadable") from read_error
    if len(feed_bytes) > maximum_file_size_bytes:
        raise FeedRefusedError("file_too_large")
    return feed_bytes


def _decode(feed_bytes: bytes) -> str:
    try:
        # utf-8-sig drops a leading byte order mark, which spreadsheet exports
        # commonly add and which would otherwise corrupt the first column name.
        return feed_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as decode_error:
        raise FeedRefusedError("not_utf8") from decode_error


def _check_header(header_fields: list[str]) -> None:
    if len(set(header_fields)) != len(header_fields):
        raise FeedRefusedError("duplicate_column")
    if set(header_fields) - set(SOURCE_COLUMNS):
        raise FeedRefusedError("unknown_column")
    if set(SOURCE_COLUMNS) - set(header_fields):
        raise FeedRefusedError("missing_column")


def _check_field_lengths(row_fields: list[str], maximum_field_length: int) -> None:
    if any(len(field_value) > maximum_field_length for field_value in row_fields):
        raise FeedRefusedError("field_too_long")


def read_feed_rows(
    feed_path: Path, feed_bounds: FeedBounds = CONTRACT_FEED_BOUNDS
) -> list[RawFeedRow]:
    """Return the file's data rows, or raise ``FeedRefusedError`` naming why not.

    A zero-byte or header-only file returns an empty list: whether that is a
    problem is the caller's decision, not the reader's.
    """
    feed_text = _decode(_read_bounded_bytes(feed_path, feed_bounds.maximum_file_size_bytes))
    csv_rows = csv.reader(io.StringIO(feed_text, newline=""), strict=True)

    try:
        header_fields = next(csv_rows, None)
        if header_fields is None:
            return []
        _check_field_lengths(header_fields, feed_bounds.maximum_field_length)
        _check_header(header_fields)

        raw_rows: list[RawFeedRow] = []
        for row_number, row_fields in enumerate(csv_rows, start=1):
            if row_number > feed_bounds.maximum_data_rows:
                raise FeedRefusedError("too_many_rows")
            _check_field_lengths(row_fields, feed_bounds.maximum_field_length)
            values_by_column = (
                dict(zip(header_fields, row_fields, strict=True))
                if len(row_fields) == len(header_fields)
                else None
            )
            raw_rows.append(RawFeedRow(row_number, values_by_column, len(row_fields)))
    except csv.Error as csv_error:
        raise FeedRefusedError("not_csv") from csv_error

    # Blank lines after the last row are an export artefact and carry nothing.
    # A blank line between rows is kept, and rejected, because it may mark lost data.
    while raw_rows and raw_rows[-1].field_count == 0:
        raw_rows.pop()
    return raw_rows
