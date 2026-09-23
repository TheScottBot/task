"""Moves a processed feed file out of the drop location, with its reports beside it.

Left in place, a processed file would be ingested and reported on again every
night. That changes nothing in the store, but it would send the client the same
exceptions report twice, and forgetting a manual move is easy.

A feed and the reports on it share one stamped stem, the feed's name plus the
UTC moment it was processed, so each night's file and its reports stay paired
and no night's report ever replaces another's.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ARCHIVE_DIRECTORY_NAME = "archive"
REPORT_SUFFIX = ".report.json"
SUMMARY_SUFFIX = ".summary.txt"

# A full UTC timestamp rather than the date alone, so a manual re-run on the same
# day cannot collide with that morning's archive. No colons, which Windows forbids.
_ARCHIVE_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

# A second run in the same second is rare but real (a quick manual re-drop); this
# many is far beyond it, and only bounds the search for a free name.
_MAXIMUM_ARCHIVES_PER_SECOND = 100


@dataclass(frozen=True)
class ArchiveNames:
    """Where one run's feed and reports go, all under the same stamped stem."""

    archived_feed_path: Path
    report_path: Path
    summary_path: Path


def default_archive_directory(feed_path: Path) -> Path:
    """A subfolder of the drop location, so the drop folder holds only what is waiting."""
    return feed_path.parent / ARCHIVE_DIRECTORY_NAME


def build_archive_stem(feed_path: Path, processed_at: datetime, sequence_number: int = 1) -> str:
    """Return the feed's stem and the processing moment, plus ``-n`` for a later same-second file."""
    processed_timestamp = processed_at.astimezone(UTC).strftime(_ARCHIVE_TIMESTAMP_FORMAT)
    sequence_suffix = f"-{sequence_number}" if sequence_number > 1 else ""
    return f"{feed_path.stem}.{processed_timestamp}{sequence_suffix}"


def reserve_archive_names(
    feed_path: Path, archive_directory: Path, report_directory: Path, processed_at: datetime
) -> ArchiveNames:
    """Create the directories and return the first stamped stem free for all three files.

    Taking the next sequence number when any one of the three names is taken keeps
    a feed and its reports under the same stem, and never overwrites an earlier
    one. Raises ``OSError`` if a directory cannot be created.
    """
    archive_directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)
    for sequence_number in range(1, _MAXIMUM_ARCHIVES_PER_SECOND + 1):
        archive_stem = build_archive_stem(feed_path, processed_at, sequence_number)
        archive_names = ArchiveNames(
            archived_feed_path=archive_directory / f"{archive_stem}{feed_path.suffix}",
            report_path=report_directory / f"{archive_stem}{REPORT_SUFFIX}",
            summary_path=report_directory / f"{archive_stem}{SUMMARY_SUFFIX}",
        )
        if not any(
            reserved_path.exists()
            for reserved_path in (
                archive_names.archived_feed_path,
                archive_names.report_path,
                archive_names.summary_path,
            )
        ):
            return archive_names
    raise FileExistsError(f"no free archive name for {feed_path.name}")


def archive_feed_file(feed_path: Path, archived_feed_path: Path) -> None:
    """Move the feed to its reserved name, refusing to overwrite anything already there.

    An archive is the record of what the client actually sent, so even a name
    taken between reserving and moving raises ``FileExistsError`` rather than
    replacing it, and the feed is left where it was.
    """
    if archived_feed_path.exists():
        raise FileExistsError(archived_feed_path.name)
    # shutil.move rather than a rename, so an archive directory on another
    # filesystem still works; it falls back to copy then delete there.
    shutil.move(feed_path, archived_feed_path)
