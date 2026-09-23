"""One pass over one delivered file: read, validate, store, in a single transaction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path

from .contract import CONTRACT_FEED_BOUNDS, FeedBounds
from .exceptions import FeedRefusedError
from .feed_reader import read_feed_rows
from .findings import Finding
from .rules import RuleId
from .store import PositionStore, StoreOutcome
from .validation import ValidatedRecord, validate_feed_rows


class FileOutcome(Enum):
    """The three file states the execution model keeps apart, plus success.

    ``ABSENT`` is benign on a schedule that fires whether or not a drop arrived.
    ``EMPTY`` is a probable source error. ``REFUSED`` is a real failure.
    """

    PROCESSED = "processed"
    ABSENT = "absent"
    EMPTY = "empty"
    REFUSED = "refused"


@dataclass(frozen=True)
class RecordResult:
    """A validated record and what the store did with it (``None`` when rejected)."""

    validated_record: ValidatedRecord
    store_outcome: StoreOutcome | None


@dataclass(frozen=True)
class FeedIngestionResult:
    """Everything the report needs about one file's ingestion."""

    feed_file_name: str
    ingested_at: datetime
    file_outcome: FileOutcome
    refusal_reason_category: str | None
    rows_read: int
    record_results: tuple[RecordResult, ...]


def _flag_commitment_lower_than_stored(
    validated_record: ValidatedRecord, position_store: PositionStore
) -> ValidatedRecord:
    """Add W7 when a landing position's commitment is below the one already stored.

    W7 lives here rather than in validation because it compares against the
    store, not against the row alone. A commitment is contractual and should not
    fall, and a blank one defaulted to 0 by W1 would otherwise wipe a known value
    with only the blank flagged. The new value still lands: the latest delivery
    wins, and the audit row keeps the old one.
    """
    assert validated_record.position is not None  # only landing records are checked
    stored_position = position_store.find_position(validated_record.position.source_row_id)
    if stored_position is None or validated_record.position.commitment >= stored_position.commitment:
        return validated_record
    w7_finding = Finding(
        RuleId.W7,
        "commitment",
        str(stored_position.commitment),
        str(validated_record.position.commitment),
    )
    return replace(validated_record, findings=(*validated_record.findings, w7_finding))


def ingest_feed_file(
    feed_path: Path,
    position_store: PositionStore,
    ingested_at: datetime,
    feed_bounds: FeedBounds = CONTRACT_FEED_BOUNDS,
) -> FeedIngestionResult:
    """Ingest one file. Idempotent: re-running it on the same file changes nothing.

    Any exception while storing propagates after the transaction has rolled the
    whole file back, so the store is left at the last complete delivery.
    """
    feed_file_name = feed_path.name

    def file_level_result(file_outcome: FileOutcome, reason: str | None = None) -> FeedIngestionResult:
        return FeedIngestionResult(feed_file_name, ingested_at, file_outcome, reason, 0, ())

    if not feed_path.exists():
        return file_level_result(FileOutcome.ABSENT)
    try:
        raw_rows = read_feed_rows(feed_path, feed_bounds)
    except FeedRefusedError as refusal:
        return file_level_result(FileOutcome.REFUSED, refusal.reason_category)
    if not raw_rows:
        return file_level_result(FileOutcome.EMPTY)

    validated_records = validate_feed_rows(raw_rows, ingested_at.date())
    record_results: list[RecordResult] = []
    with position_store.transaction():
        for validated_record in validated_records:
            if validated_record.position is None:
                record_results.append(RecordResult(validated_record, None))
                continue
            checked_record = _flag_commitment_lower_than_stored(validated_record, position_store)
            store_outcome = position_store.upsert_position(
                validated_record.position, ingested_at, feed_file_name
            )
            record_results.append(RecordResult(checked_record, store_outcome))

    return FeedIngestionResult(
        feed_file_name,
        ingested_at,
        FileOutcome.PROCESSED,
        None,
        len(raw_rows),
        tuple(record_results),
    )
