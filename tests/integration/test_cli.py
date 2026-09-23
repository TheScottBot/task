"""The cron entry point: exit codes, archived reports, and what reaches the log.

Every run here uses a copy of the feed in a temporary drop folder, because a run
archives the file it processed and the provided sample must stay where it is.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import stat

import pytest

from positions_feed.cli import ExitCode, main
from positions_feed.store import PositionStore
from tests.conftest import (
    FIXED_INGESTION_MOMENT,
    SAMPLE_FEED_ACCOUNT_HOLDERS,
    SAMPLE_FEED_ADVISOR_EMAILS,
    SAMPLE_FEED_PATH,
    write_feed_file,
)

_SAMPLE_ARCHIVE_STEM = "sample-positions-feed.20260923T020000Z"


def _fixed_clock():
    return FIXED_INGESTION_MOMENT


def _invoke(feed_path, database_path, *extra_arguments: str) -> int:
    return main(
        ["--feed-path", str(feed_path), "--database-path", str(database_path), *extra_arguments],
        current_moment_provider=_fixed_clock,
    )


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "positions.sqlite3"


@pytest.fixture
def drop_directory(tmp_path):
    incoming_directory = tmp_path / "incoming"
    incoming_directory.mkdir()
    return incoming_directory


def _drop_sample_feed(drop_directory):
    return shutil.copyfile(SAMPLE_FEED_PATH, drop_directory / SAMPLE_FEED_PATH.name)


def _stored_position_count(database_path) -> int:
    connection = sqlite3.connect(database_path)
    try:
        return connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    finally:
        connection.close()


def _read_structured_report(directory, archive_stem: str) -> dict:
    return json.loads((directory / f"{archive_stem}.report.json").read_text(encoding="utf-8"))


def test_exit_codes_are_the_agreed_values():
    assert (ExitCode.SUCCESS, ExitCode.FAILURE, ExitCode.FILE_EMPTY) == (0, 1, 2)


# ── Absent file ───────────────────────────────────────────────────────────────


def test_absent_file_exits_zero_logs_one_line_and_writes_nothing(
    drop_directory, database_path, caplog
):
    caplog.set_level(logging.INFO, logger="positions_feed")
    exit_code = _invoke(drop_directory / "not-delivered.csv", database_path)
    assert exit_code == ExitCode.SUCCESS
    assert list(drop_directory.iterdir()) == []
    positions_feed_records = [
        record for record in caplog.records if record.name.startswith("positions_feed")
    ]
    assert len(positions_feed_records) == 1
    assert "outcome=absent" in positions_feed_records[0].getMessage()


# ── Processed file: feed, report and summary archived together ────────────────


def test_sample_feed_is_archived_with_its_reports_under_one_stamp(drop_directory, database_path):
    feed_path = _drop_sample_feed(drop_directory)
    assert _invoke(feed_path, database_path) == ExitCode.SUCCESS

    archive_directory = drop_directory / "archive"
    assert {path.name for path in archive_directory.iterdir()} == {
        f"{_SAMPLE_ARCHIVE_STEM}.csv",
        f"{_SAMPLE_ARCHIVE_STEM}.report.json",
        f"{_SAMPLE_ARCHIVE_STEM}.summary.txt",
    }
    assert (archive_directory / f"{_SAMPLE_ARCHIVE_STEM}.csv").read_bytes() == SAMPLE_FEED_PATH.read_bytes()
    structured_report = _read_structured_report(archive_directory, _SAMPLE_ARCHIVE_STEM)
    assert structured_report["counts"]["by_decision"]["rejected"] == 9
    assert not feed_path.exists()
    assert _stored_position_count(database_path) == 16


def test_archive_directory_argument_moves_feed_and_reports(tmp_path, drop_directory, database_path):
    feed_path = _drop_sample_feed(drop_directory)
    chosen_archive_directory = tmp_path / "long-term" / "archive"
    assert (
        _invoke(feed_path, database_path, "--archive-directory", str(chosen_archive_directory))
        == ExitCode.SUCCESS
    )
    assert (chosen_archive_directory / f"{_SAMPLE_ARCHIVE_STEM}.csv").is_file()
    assert (chosen_archive_directory / f"{_SAMPLE_ARCHIVE_STEM}.report.json").is_file()
    assert (chosen_archive_directory / f"{_SAMPLE_ARCHIVE_STEM}.summary.txt").is_file()
    assert not (drop_directory / "archive").exists()


def test_report_directory_argument_separates_reports_from_the_archived_feed(
    tmp_path, drop_directory, database_path
):
    feed_path = _drop_sample_feed(drop_directory)
    chosen_report_directory = tmp_path / "reports"
    assert (
        _invoke(feed_path, database_path, "--report-directory", str(chosen_report_directory))
        == ExitCode.SUCCESS
    )
    assert {path.name for path in chosen_report_directory.iterdir()} == {
        f"{_SAMPLE_ARCHIVE_STEM}.report.json",
        f"{_SAMPLE_ARCHIVE_STEM}.summary.txt",
    }
    assert {path.name for path in (drop_directory / "archive").iterdir()} == {
        f"{_SAMPLE_ARCHIVE_STEM}.csv"
    }


def test_redelivering_the_same_file_converges_to_the_same_state(drop_directory, database_path):
    _invoke(_drop_sample_feed(drop_directory), database_path)
    shutil.rmtree(drop_directory / "archive")
    assert _invoke(_drop_sample_feed(drop_directory), database_path) == ExitCode.SUCCESS
    assert _stored_position_count(database_path) == 16
    structured_report = _read_structured_report(drop_directory / "archive", _SAMPLE_ARCHIVE_STEM)
    assert structured_report["counts"]["by_store_outcome"]["unchanged"] == 16


def test_rerun_in_the_same_second_keeps_every_report(drop_directory, database_path):
    _invoke(_drop_sample_feed(drop_directory), database_path)
    feed_path = _drop_sample_feed(drop_directory)
    assert _invoke(feed_path, database_path) == ExitCode.SUCCESS
    assert not feed_path.exists()
    archive_directory = drop_directory / "archive"
    first_report = _read_structured_report(archive_directory, _SAMPLE_ARCHIVE_STEM)
    second_report = _read_structured_report(archive_directory, f"{_SAMPLE_ARCHIVE_STEM}-2")
    assert first_report["counts"]["by_store_outcome"]["inserted"] == 16
    assert second_report["counts"]["by_store_outcome"]["unchanged"] == 16
    assert (archive_directory / f"{_SAMPLE_ARCHIVE_STEM}-2.csv").is_file()
    assert (archive_directory / f"{_SAMPLE_ARCHIVE_STEM}-2.summary.txt").is_file()


def test_run_after_archiving_finds_nothing_to_do(drop_directory, database_path, caplog):
    feed_path = _drop_sample_feed(drop_directory)
    _invoke(feed_path, database_path)
    caplog.set_level(logging.INFO, logger="positions_feed")
    assert _invoke(feed_path, database_path) == ExitCode.SUCCESS
    assert any("outcome=absent" in record.getMessage() for record in caplog.records)


# ── Empty and refused files are archived with their reports too ───────────────


def test_empty_file_exits_two_and_is_archived_with_its_report(drop_directory, database_path):
    feed_path = write_feed_file(drop_directory, [], file_name="empty-feed.csv")
    assert _invoke(feed_path, database_path) == ExitCode.FILE_EMPTY
    archive_directory = drop_directory / "archive"
    structured_report = _read_structured_report(archive_directory, "empty-feed.20260923T020000Z")
    assert structured_report["file_outcome"] == "empty"
    assert (archive_directory / "empty-feed.20260923T020000Z.csv").is_file()
    assert not feed_path.exists()


def test_unreadable_file_exits_one_and_is_archived_with_its_report(
    drop_directory, database_path, caplog
):
    feed_path = drop_directory / "corrupt-feed.csv"
    feed_path.write_bytes(b"\xff\xfe\x00")
    caplog.set_level(logging.INFO, logger="positions_feed")
    assert _invoke(feed_path, database_path) == ExitCode.FAILURE
    archive_directory = drop_directory / "archive"
    structured_report = _read_structured_report(archive_directory, "corrupt-feed.20260923T020000Z")
    assert structured_report["refusal_reason_category"] == "not_utf8"
    assert any("reason=not_utf8" in record.getMessage() for record in caplog.records)
    assert (archive_directory / "corrupt-feed.20260923T020000Z.csv").is_file()


# ── Failures leave the file where it is ───────────────────────────────────────


def test_store_that_cannot_be_opened_exits_one_and_leaves_the_file(
    tmp_path, drop_directory, caplog
):
    feed_path = _drop_sample_feed(drop_directory)
    caplog.set_level(logging.INFO, logger="positions_feed")
    # A directory where the database file should be cannot be opened as SQLite.
    assert _invoke(feed_path, tmp_path) == ExitCode.FAILURE
    assert any("outcome=store_failure" in record.getMessage() for record in caplog.records)
    assert feed_path.is_file()
    assert not (drop_directory / "archive").exists()


def test_store_failure_during_ingest_exits_one_and_leaves_the_file(
    drop_directory, database_path, caplog
):
    PositionStore.open_file(database_path).close()
    # Read-only: the store opens, but the first write of the ingest fails.
    database_path.chmod(stat.S_IREAD)
    feed_path = _drop_sample_feed(drop_directory)
    caplog.set_level(logging.INFO, logger="positions_feed")
    try:
        assert _invoke(feed_path, database_path) == ExitCode.FAILURE
    finally:
        database_path.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert any("outcome=store_failure" in record.getMessage() for record in caplog.records)
    assert feed_path.is_file()
    assert not (drop_directory / "archive").exists()
    assert _stored_position_count(database_path) == 0


def test_archive_that_fails_exits_one_and_leaves_the_file(
    tmp_path, drop_directory, database_path, caplog
):
    feed_path = _drop_sample_feed(drop_directory)
    blocked_archive_directory = tmp_path / "blocked-archive"
    blocked_archive_directory.write_bytes(b"not a directory")
    caplog.set_level(logging.INFO, logger="positions_feed")

    exit_code = _invoke(
        feed_path, database_path, "--archive-directory", str(blocked_archive_directory)
    )

    assert exit_code == ExitCode.FAILURE
    assert any("archive outcome=failed" in record.getMessage() for record in caplog.records)
    assert feed_path.is_file()
    # The ingest itself committed; leaving the file only means the next run
    # re-ingests it, which changes nothing.
    assert _stored_position_count(database_path) == 16


def test_report_that_cannot_be_written_exits_one_and_leaves_the_file(
    tmp_path, drop_directory, database_path, caplog
):
    feed_path = _drop_sample_feed(drop_directory)
    blocked_report_directory = tmp_path / "blocked-reports"
    blocked_report_directory.write_bytes(b"not a directory")
    caplog.set_level(logging.INFO, logger="positions_feed")

    exit_code = _invoke(
        feed_path, database_path, "--report-directory", str(blocked_report_directory)
    )

    assert exit_code == ExitCode.FAILURE
    assert feed_path.is_file()
    assert not (drop_directory / "archive" / f"{_SAMPLE_ARCHIVE_STEM}.csv").exists()


# ── Personal data ─────────────────────────────────────────────────────────────


def test_log_lines_carry_no_personal_data(drop_directory, database_path, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    _invoke(_drop_sample_feed(drop_directory), database_path)
    captured_output = capsys.readouterr()
    emitted_text = caplog.text + captured_output.out + captured_output.err
    for personal_value in (*SAMPLE_FEED_ACCOUNT_HOLDERS, *SAMPLE_FEED_ADVISOR_EMAILS):
        assert personal_value not in emitted_text
