"""The cron entry point: one pass over the drop location, then exit.

The scheduler reads the exit code, not stdout, so the outcome is signalled there:
success (including no file and a file with rejected rows, which are data problems
the report carries, not job failures), failure, or an empty file.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path

from .archive import (
    ARCHIVE_DIRECTORY_NAME,
    ArchiveNames,
    archive_feed_file,
    default_archive_directory,
    reserve_archive_names,
)
from .ingestion import FeedIngestionResult, FileOutcome, ingest_feed_file
from .report import build_structured_report, render_human_summary
from .store import PositionStore

_logger = logging.getLogger("positions_feed.cli")


class ExitCode(IntEnum):
    SUCCESS = 0
    FAILURE = 1
    FILE_EMPTY = 2


_EXIT_CODE_BY_FILE_OUTCOME = {
    FileOutcome.PROCESSED: ExitCode.SUCCESS,
    FileOutcome.ABSENT: ExitCode.SUCCESS,
    FileOutcome.EMPTY: ExitCode.FILE_EMPTY,
    FileOutcome.REFUSED: ExitCode.FAILURE,
}


def _current_utc_moment() -> datetime:
    return datetime.now(UTC)


def _write_reports(ingestion_result: FeedIngestionResult, archive_names: ArchiveNames) -> str:
    summary_text = render_human_summary(ingestion_result)
    # Fixed LF endings, so a report is byte-identical whichever host produced it.
    archive_names.report_path.write_text(
        json.dumps(build_structured_report(ingestion_result), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    archive_names.summary_path.write_text(summary_text, encoding="utf-8", newline="\n")
    return summary_text


def _log_outcome(ingestion_result: FeedIngestionResult) -> None:
    # Verb, outcome, reason category and counts only: never a path, a value or a row.
    if ingestion_result.file_outcome is FileOutcome.ABSENT:
        _logger.info("ingest outcome=absent")
    elif ingestion_result.file_outcome is FileOutcome.REFUSED:
        _logger.error("ingest outcome=refused reason=%s", ingestion_result.refusal_reason_category)
    elif ingestion_result.file_outcome is FileOutcome.EMPTY:
        _logger.warning("ingest outcome=empty reason=zero_data_rows")
    else:
        rejected_count = sum(
            1
            for record_result in ingestion_result.record_results
            if record_result.validated_record.position is None
        )
        _logger.info(
            "ingest outcome=processed rows=%d landed=%d rejected=%d",
            ingestion_result.rows_read,
            ingestion_result.rows_read - rejected_count,
            rejected_count,
        )


def main(
    argv: list[str] | None = None,
    current_moment_provider: Callable[[], datetime] = _current_utc_moment,
) -> int:
    """Ingest the file at ``--feed-path`` if one has been dropped; return the exit code."""
    argument_parser = argparse.ArgumentParser(
        prog="positions-feed",
        description="Ingest and validate one Meridian Capital positions feed file.",
    )
    argument_parser.add_argument("--feed-path", type=Path, required=True,
                                 help="Where the nightly feed file is dropped.")
    argument_parser.add_argument("--database-path", type=Path, required=True,
                                 help="The SQLite position store, created on first use.")
    argument_parser.add_argument("--archive-directory", type=Path, default=None,
                                 help="Where a processed file is moved; defaults to an "
                                      f"'{ARCHIVE_DIRECTORY_NAME}' folder beside the drop location.")
    argument_parser.add_argument("--report-directory", type=Path, default=None,
                                 help="Where the exceptions report and summary are written; "
                                      "defaults to the archive directory, beside the file they describe.")
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s %(message)s")

    try:
        arguments = argument_parser.parse_args(argv)
    except SystemExit as parser_exit:
        # argparse exits 2 on a usage error, which is this job's empty-file code;
        # a mistyped crontab must read as a broken job, not as an empty delivery.
        if parser_exit.code == 0:
            return ExitCode.SUCCESS
        _logger.error("invocation outcome=failed reason=invalid_arguments")
        return ExitCode.FAILURE

    run_moment = current_moment_provider()
    try:
        position_store = PositionStore.open_file(arguments.database_path)
    except sqlite3.Error as store_error:
        _logger.error("ingest outcome=store_failure reason=%s", type(store_error).__name__)
        return ExitCode.FAILURE
    try:
        ingestion_result = ingest_feed_file(arguments.feed_path, position_store, run_moment)
    except sqlite3.Error as store_error:
        # Nothing was committed, so the file stays in the drop location for a retry.
        _logger.error("ingest outcome=store_failure reason=%s", type(store_error).__name__)
        return ExitCode.FAILURE
    finally:
        position_store.close()

    _log_outcome(ingestion_result)
    # No file means nothing was sent, so there is nothing to report on or archive.
    if ingestion_result.file_outcome is FileOutcome.ABSENT:
        return ExitCode.SUCCESS
    archive_directory = arguments.archive_directory or default_archive_directory(arguments.feed_path)
    report_directory = arguments.report_directory or archive_directory
    try:
        archive_names = reserve_archive_names(
            arguments.feed_path, archive_directory, report_directory, run_moment
        )
    except OSError as archive_error:
        _logger.error("archive outcome=failed reason=%s", type(archive_error).__name__)
        return ExitCode.FAILURE
    try:
        summary_text = _write_reports(ingestion_result, archive_names)
    except OSError as report_error:
        _logger.error("report outcome=failed reason=%s", type(report_error).__name__)
        return ExitCode.FAILURE
    print(summary_text, end="")

    # Archived only once its report exists, so every archived file has a report.
    try:
        archive_feed_file(arguments.feed_path, archive_names.archived_feed_path)
    except OSError as archive_error:
        _logger.error("archive outcome=failed reason=%s", type(archive_error).__name__)
        return ExitCode.FAILURE
    _logger.info("archive outcome=archived")
    return _EXIT_CODE_BY_FILE_OUTCOME[ingestion_result.file_outcome]


if __name__ == "__main__":
    sys.exit(main())
