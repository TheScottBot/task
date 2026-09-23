"""The feed reader: bounds, header contract, encoding and row shape."""

from __future__ import annotations

import pytest

from positions_feed.contract import CONTRACT_FEED_BOUNDS, SOURCE_COLUMNS, FeedBounds
from positions_feed.exceptions import FeedRefusedError
from positions_feed.feed_reader import read_feed_rows
from tests.conftest import SAMPLE_FEED_PATH, build_clean_row_values, write_feed_file


def _refusal_reason(feed_path, feed_bounds: FeedBounds = CONTRACT_FEED_BOUNDS) -> str:
    with pytest.raises(FeedRefusedError) as refusal:
        read_feed_rows(feed_path, feed_bounds)
    return refusal.value.reason_category


# ── The provided sample ───────────────────────────────────────────────────────


def test_sample_feed_reads_every_data_row_in_order():
    raw_rows = read_feed_rows(SAMPLE_FEED_PATH)
    assert len(raw_rows) == 25
    assert [raw_row.row_number for raw_row in raw_rows] == list(range(1, 26))
    assert raw_rows[0].values_by_column["source_row_id"] == "src-1001"
    assert raw_rows[0].values_by_column["advisor_email"] == "k.brennan@meridiancap.example"
    assert raw_rows[11].values_by_column["source_row_id"] == ""


def test_sample_feed_line_endings_do_not_leak_into_values():
    for raw_row in read_feed_rows(SAMPLE_FEED_PATH):
        assert not raw_row.values_by_column["advisor_email"].endswith("\r")


# ── Header contract ───────────────────────────────────────────────────────────


def test_unknown_column_refuses_the_file(tmp_path):
    header = (*SOURCE_COLUMNS, "tax_lot")
    row_values = {**build_clean_row_values(), "tax_lot": "7"}
    feed_path = write_feed_file(tmp_path, [row_values], header=header)
    assert _refusal_reason(feed_path) == "unknown_column"


def test_missing_column_refuses_the_file(tmp_path):
    header = tuple(column for column in SOURCE_COLUMNS if column != "nav_date")
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()], header=header)
    assert _refusal_reason(feed_path) == "missing_column"


def test_duplicated_column_refuses_the_file(tmp_path):
    header = (*SOURCE_COLUMNS, "nav")
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()], header=header)
    assert _refusal_reason(feed_path) == "duplicate_column"


def test_header_with_padded_column_name_refuses_the_file(tmp_path):
    feed_path = tmp_path / "padded.csv"
    padded_header = ",".join(SOURCE_COLUMNS).replace("nav_date", " nav_date")
    feed_path.write_text(padded_header + "\r\n", encoding="utf-8", newline="")
    assert _refusal_reason(feed_path) == "unknown_column"


def test_reordered_columns_are_read_by_name(tmp_path):
    header = tuple(reversed(SOURCE_COLUMNS))
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()], header=header)
    raw_rows = read_feed_rows(feed_path)
    assert raw_rows[0].values_by_column == build_clean_row_values()


# ── Empty files ───────────────────────────────────────────────────────────────


def test_zero_byte_file_has_no_data_rows(tmp_path):
    feed_path = tmp_path / "empty.csv"
    feed_path.write_bytes(b"")
    assert read_feed_rows(feed_path) == []


@pytest.mark.parametrize("line_ending", ["\r\n", ""])
def test_header_only_file_has_no_data_rows(tmp_path, line_ending):
    feed_path = tmp_path / "header-only.csv"
    feed_path.write_text(",".join(SOURCE_COLUMNS) + line_ending, encoding="utf-8", newline="")
    assert read_feed_rows(feed_path) == []


# ── Encoding and structure ────────────────────────────────────────────────────


def test_non_utf8_bytes_refuse_the_file(tmp_path):
    feed_path = tmp_path / "latin1.csv"
    feed_path.write_bytes((",".join(SOURCE_COLUMNS) + "\r\n").encode("utf-8") + b"\xff\xfe\r\n")
    assert _refusal_reason(feed_path) == "not_utf8"


def test_utf8_byte_order_mark_is_accepted(tmp_path):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()])
    feed_path.write_bytes(b"\xef\xbb\xbf" + feed_path.read_bytes())
    assert len(read_feed_rows(feed_path)) == 1


def test_unterminated_quote_refuses_the_file(tmp_path):
    feed_path = tmp_path / "broken-quote.csv"
    feed_path.write_text(",".join(SOURCE_COLUMNS) + '\r\n"src-1,unterminated', encoding="utf-8", newline="")
    assert _refusal_reason(feed_path) == "not_csv"


def test_directory_in_place_of_file_refuses_as_unreadable(tmp_path):
    assert _refusal_reason(tmp_path) == "unreadable"


def test_row_with_wrong_field_count_is_returned_unmapped(tmp_path):
    feed_path = tmp_path / "ragged.csv"
    feed_path.write_text(
        ",".join(SOURCE_COLUMNS) + "\r\n" + "src-1,only,three\r\n", encoding="utf-8", newline=""
    )
    (ragged_row,) = read_feed_rows(feed_path)
    assert ragged_row.values_by_column is None
    assert ragged_row.field_count == 3


def test_blank_line_between_rows_is_returned_as_an_empty_row(tmp_path):
    clean_line = ",".join(build_clean_row_values().values())
    feed_path = tmp_path / "blank-line.csv"
    feed_path.write_text(
        ",".join(SOURCE_COLUMNS) + "\r\n" + clean_line + "\r\n\r\n" + clean_line + "\r\n",
        encoding="utf-8",
        newline="",
    )
    raw_rows = read_feed_rows(feed_path)
    assert [raw_row.field_count for raw_row in raw_rows] == [11, 0, 11]
    assert raw_rows[1].values_by_column is None


@pytest.mark.parametrize("trailing_blank_lines", ["\r\n", "\r\n\r\n\r\n", "\n"])
def test_trailing_blank_lines_at_end_of_file_are_not_rows(tmp_path, trailing_blank_lines):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()])
    feed_path.write_bytes(feed_path.read_bytes() + trailing_blank_lines.encode("utf-8"))
    assert [raw_row.field_count for raw_row in read_feed_rows(feed_path)] == [11]


def test_header_followed_only_by_blank_lines_has_no_data_rows(tmp_path):
    feed_path = tmp_path / "header-then-blank.csv"
    feed_path.write_text(",".join(SOURCE_COLUMNS) + "\r\n\r\n", encoding="utf-8", newline="")
    assert read_feed_rows(feed_path) == []


def test_quoted_comma_inside_a_value_is_one_field(tmp_path):
    feed_path = write_feed_file(
        tmp_path, [build_clean_row_values(account_holder="Chen, Associates Pension")]
    )
    assert read_feed_rows(feed_path)[0].values_by_column["account_holder"] == "Chen, Associates Pension"


# ── Bounds come from the contract, and are refused, never truncated ───────────


def test_contract_bounds_are_the_agreed_values():
    assert CONTRACT_FEED_BOUNDS == FeedBounds(
        maximum_file_size_bytes=64 * 1024 * 1024,
        maximum_data_rows=200_000,
        maximum_field_length=256,
    )


def test_file_larger_than_bound_is_refused(tmp_path):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()])
    file_size = feed_path.stat().st_size
    tight_bounds = FeedBounds(file_size - 1, 10, 256)
    assert _refusal_reason(feed_path, tight_bounds) == "file_too_large"


def test_file_exactly_at_size_bound_is_read(tmp_path):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values()])
    exact_bounds = FeedBounds(feed_path.stat().st_size, 10, 256)
    assert len(read_feed_rows(feed_path, exact_bounds)) == 1


def test_more_rows_than_bound_is_refused(tmp_path):
    rows = [build_clean_row_values(source_row_id=f"test-{index}") for index in range(3)]
    feed_path = write_feed_file(tmp_path, rows)
    assert _refusal_reason(feed_path, FeedBounds(1_000_000, 2, 256)) == "too_many_rows"


def test_rows_exactly_at_bound_are_read(tmp_path):
    rows = [build_clean_row_values(source_row_id=f"test-{index}") for index in range(2)]
    feed_path = write_feed_file(tmp_path, rows)
    assert len(read_feed_rows(feed_path, FeedBounds(1_000_000, 2, 256))) == 2


def test_field_longer_than_bound_is_refused(tmp_path):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values(account_holder="x" * 31)])
    assert _refusal_reason(feed_path, FeedBounds(1_000_000, 10, 30)) == "field_too_long"


def test_field_exactly_at_bound_is_read(tmp_path):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values(account_holder="x" * 30)])
    assert len(read_feed_rows(feed_path, FeedBounds(1_000_000, 10, 30))) == 1


def test_header_field_longer_than_bound_is_refused(tmp_path):
    feed_path = tmp_path / "long-header.csv"
    feed_path.write_text(",".join(SOURCE_COLUMNS) + "," + "h" * 40 + "\r\n", encoding="utf-8", newline="")
    assert _refusal_reason(feed_path, FeedBounds(1_000_000, 10, 30)) == "field_too_long"
