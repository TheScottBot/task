"""Archiving a processed feed file with its reports: naming, moving, never overwriting."""

from __future__ import annotations

from pathlib import Path

import pytest

from positions_feed.archive import (
    archive_feed_file,
    build_archive_stem,
    default_archive_directory,
    reserve_archive_names,
)
from tests.conftest import FIXED_INGESTION_MOMENT


def test_default_archive_directory_is_a_subfolder_of_the_drop_location():
    feed_path = Path("incoming") / "positions-feed.csv"
    assert default_archive_directory(feed_path) == Path("incoming") / "archive"


def test_archive_stem_carries_the_utc_processing_moment():
    feed_path = Path("incoming") / "positions-feed.csv"
    assert build_archive_stem(feed_path, FIXED_INGESTION_MOMENT) == "positions-feed.20260923T020000Z"


def test_archive_stem_for_a_later_file_in_the_same_second():
    feed_path = Path("incoming") / "positions-feed.csv"
    assert (
        build_archive_stem(feed_path, FIXED_INGESTION_MOMENT, sequence_number=2)
        == "positions-feed.20260923T020000Z-2"
    )


def test_reserved_names_pair_the_feed_with_its_reports(tmp_path):
    feed_path = tmp_path / "positions-feed.csv"
    archive_directory = tmp_path / "archive"
    archive_names = reserve_archive_names(
        feed_path, archive_directory, archive_directory, FIXED_INGESTION_MOMENT
    )
    assert archive_names.archived_feed_path == archive_directory / "positions-feed.20260923T020000Z.csv"
    assert archive_names.report_path == archive_directory / "positions-feed.20260923T020000Z.report.json"
    assert archive_names.summary_path == archive_directory / "positions-feed.20260923T020000Z.summary.txt"
    assert archive_directory.is_dir()


def test_reserved_names_keep_the_feed_extension_or_its_absence(tmp_path):
    archive_names = reserve_archive_names(
        tmp_path / "positions-feed", tmp_path, tmp_path, FIXED_INGESTION_MOMENT
    )
    assert archive_names.archived_feed_path.name == "positions-feed.20260923T020000Z"


def test_reports_can_live_apart_from_the_archived_feed(tmp_path):
    archive_names = reserve_archive_names(
        tmp_path / "positions-feed.csv",
        tmp_path / "archive",
        tmp_path / "reports",
        FIXED_INGESTION_MOMENT,
    )
    assert archive_names.archived_feed_path.parent == tmp_path / "archive"
    assert archive_names.report_path.parent == tmp_path / "reports"
    assert (tmp_path / "reports").is_dir()


@pytest.mark.parametrize(
    "taken_name",
    [
        "positions-feed.20260923T020000Z.csv",
        "positions-feed.20260923T020000Z.report.json",
        "positions-feed.20260923T020000Z.summary.txt",
    ],
)
def test_any_one_name_taken_moves_the_whole_set_to_the_next_sequence(tmp_path, taken_name):
    archive_directory = tmp_path / "archive"
    archive_directory.mkdir()
    (archive_directory / taken_name).write_bytes(b"earlier")
    archive_names = reserve_archive_names(
        tmp_path / "positions-feed.csv", archive_directory, archive_directory, FIXED_INGESTION_MOMENT
    )
    assert archive_names.archived_feed_path.name == "positions-feed.20260923T020000Z-2.csv"
    assert archive_names.report_path.name == "positions-feed.20260923T020000Z-2.report.json"
    assert (archive_directory / taken_name).read_bytes() == b"earlier"


def test_archive_moves_the_file_to_its_reserved_name(tmp_path):
    feed_path = tmp_path / "positions-feed.csv"
    feed_path.write_bytes(b"feed bytes")
    archive_names = reserve_archive_names(
        feed_path, tmp_path / "archive", tmp_path / "archive", FIXED_INGESTION_MOMENT
    )
    archive_feed_file(feed_path, archive_names.archived_feed_path)
    assert archive_names.archived_feed_path.read_bytes() == b"feed bytes"
    assert not feed_path.exists()


def test_archive_never_overwrites_even_if_the_name_was_taken_after_reserving(tmp_path):
    feed_path = tmp_path / "positions-feed.csv"
    feed_path.write_bytes(b"new delivery")
    archive_names = reserve_archive_names(
        feed_path, tmp_path / "archive", tmp_path / "archive", FIXED_INGESTION_MOMENT
    )
    archive_names.archived_feed_path.write_bytes(b"earlier delivery")

    with pytest.raises(FileExistsError):
        archive_feed_file(feed_path, archive_names.archived_feed_path)

    assert archive_names.archived_feed_path.read_bytes() == b"earlier delivery"
    assert feed_path.read_bytes() == b"new delivery"


def test_archive_directory_that_cannot_be_made_raises(tmp_path):
    # A file where the archive directory should be: the directory cannot be made.
    blocked_archive_directory = tmp_path / "archive"
    blocked_archive_directory.write_bytes(b"not a directory")
    with pytest.raises(OSError):
        reserve_archive_names(
            tmp_path / "positions-feed.csv",
            blocked_archive_directory,
            blocked_archive_directory,
            FIXED_INGESTION_MOMENT,
        )
