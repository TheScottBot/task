"""Whole-file ingestion: idempotent re-ingest, conflicts, rollback and file states."""

from __future__ import annotations

import pytest

from positions_feed.findings import RecordDecision
from positions_feed.ingestion import FileOutcome, ingest_feed_file
from positions_feed.rules import RuleId
from positions_feed.store import PositionStore, StoreOutcome
from tests.conftest import (
    FIXED_INGESTION_MOMENT,
    SAMPLE_FEED_PATH,
    build_clean_row_values,
    write_feed_file,
)


def _store_outcomes(ingestion_result) -> list[StoreOutcome | None]:
    return [record_result.store_outcome for record_result in ingestion_result.record_results]


# ── The sample feed ───────────────────────────────────────────────────────────


def test_sample_feed_lands_every_non_rejected_record(in_memory_position_store):
    ingestion_result = ingest_feed_file(
        SAMPLE_FEED_PATH, in_memory_position_store, FIXED_INGESTION_MOMENT
    )
    assert ingestion_result.file_outcome == FileOutcome.PROCESSED
    assert in_memory_position_store.count_positions() == 16
    for record_result in ingestion_result.record_results:
        if record_result.validated_record.decision == RecordDecision.REJECTED:
            assert record_result.store_outcome is None
        else:
            assert record_result.store_outcome == StoreOutcome.INSERTED


# ── Idempotent re-ingest ──────────────────────────────────────────────────────


def test_reingesting_the_same_file_changes_nothing(in_memory_position_store):
    ingest_feed_file(SAMPLE_FEED_PATH, in_memory_position_store, FIXED_INGESTION_MOMENT)
    second_result = ingest_feed_file(
        SAMPLE_FEED_PATH, in_memory_position_store, FIXED_INGESTION_MOMENT
    )
    assert in_memory_position_store.count_positions() == 16
    assert StoreOutcome.INSERTED not in _store_outcomes(second_result)
    assert StoreOutcome.SUPERSEDED not in _store_outcomes(second_result)
    assert _store_outcomes(second_result).count(StoreOutcome.UNCHANGED) == 16
    assert in_memory_position_store.count_audit_entries() == 0


# ── Cross-file correction ─────────────────────────────────────────────────────


def test_changed_redelivery_in_a_later_file_supersedes_with_audit(tmp_path, in_memory_position_store):
    first_feed = write_feed_file(
        tmp_path, [build_clean_row_values(nav="3298800.00")], file_name="day-one.csv"
    )
    later_feed = write_feed_file(
        tmp_path, [build_clean_row_values(nav="3301100.00")], file_name="day-two.csv"
    )
    ingest_feed_file(first_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    later_result = ingest_feed_file(later_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)

    assert _store_outcomes(later_result) == [StoreOutcome.SUPERSEDED]
    assert later_result.record_results[0].validated_record.decision == RecordDecision.LANDED_CLEAN
    assert str(in_memory_position_store.find_position("test-0001").nav) == "3301100.00"
    (audit_entry,) = in_memory_position_store.list_audit_entries("test-0001")
    assert str(audit_entry.previous_position.nav) == "3298800.00"
    assert audit_entry.source_file_name == "day-two.csv"


def test_rejected_redelivery_leaves_the_stored_position_alone(tmp_path, in_memory_position_store):
    first_feed = write_feed_file(tmp_path, [build_clean_row_values()], file_name="day-one.csv")
    later_feed = write_feed_file(
        tmp_path, [build_clean_row_values(nav="-1")], file_name="day-two.csv"
    )
    ingest_feed_file(first_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    later_result = ingest_feed_file(later_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)

    assert _store_outcomes(later_result) == [None]
    assert str(in_memory_position_store.find_position("test-0001").nav) == "900000.00"
    assert in_memory_position_store.count_audit_entries() == 0


# ── W7 commitment lower than previously delivered ─────────────────────────────


def _ingest_then_redeliver(tmp_path, position_store, first_commitment, later_commitment):
    first_feed = write_feed_file(
        tmp_path, [build_clean_row_values(commitment=first_commitment)], file_name="day-one.csv"
    )
    later_feed = write_feed_file(
        tmp_path,
        [build_clean_row_values(commitment=later_commitment, nav="950000.00")],
        file_name="day-two.csv",
    )
    ingest_feed_file(first_feed, position_store, FIXED_INGESTION_MOMENT)
    return ingest_feed_file(later_feed, position_store, FIXED_INGESTION_MOMENT)


def _only_record_result(ingestion_result):
    (record_result,) = ingestion_result.record_results
    return record_result


def test_w7_lower_commitment_than_stored_lands_flagged_with_both_values(
    tmp_path, in_memory_position_store
):
    later_result = _ingest_then_redeliver(tmp_path, in_memory_position_store, "5000000", "4000000")
    record_result = _only_record_result(later_result)
    assert record_result.store_outcome == StoreOutcome.SUPERSEDED
    assert record_result.validated_record.decision == RecordDecision.LANDED_FLAGGED
    (w7_finding,) = [
        finding for finding in record_result.validated_record.findings if finding.rule_id == RuleId.W7
    ]
    assert w7_finding.field_name == "commitment"
    assert (w7_finding.value_before, w7_finding.value_after) == ("5000000", "4000000")
    assert str(in_memory_position_store.find_position("test-0001").commitment) == "4000000"
    assert in_memory_position_store.count_audit_entries() == 1


def test_w7_blank_commitment_that_would_zero_a_known_one_is_flagged(
    tmp_path, in_memory_position_store
):
    later_result = _ingest_then_redeliver(tmp_path, in_memory_position_store, "5000000", "")
    record_result = _only_record_result(later_result)
    assert {finding.rule_id for finding in record_result.validated_record.findings} == {
        RuleId.W1,
        RuleId.W7,
    }
    assert str(in_memory_position_store.find_position("test-0001").commitment) == "0"


@pytest.mark.parametrize(
    "first_commitment, later_commitment",
    [("5000000", "5000000"), ("5000000", "5000000.00"), ("5000000", "6000000")],
)
def test_w7_equal_or_higher_commitment_is_not_flagged(
    tmp_path, in_memory_position_store, first_commitment, later_commitment
):
    later_result = _ingest_then_redeliver(
        tmp_path, in_memory_position_store, first_commitment, later_commitment
    )
    record_result = _only_record_result(later_result)
    assert RuleId.W7 not in {finding.rule_id for finding in record_result.validated_record.findings}


def test_w7_does_not_apply_to_a_first_delivery(tmp_path, in_memory_position_store):
    feed_path = write_feed_file(tmp_path, [build_clean_row_values(commitment="0")])
    ingestion_result = ingest_feed_file(feed_path, in_memory_position_store, FIXED_INGESTION_MOMENT)
    assert _only_record_result(ingestion_result).validated_record.findings == ()


def test_w7_rejected_redelivery_is_not_compared(tmp_path, in_memory_position_store):
    later_result = _ingest_then_redeliver(tmp_path, in_memory_position_store, "5000000", "-1")
    record_result = _only_record_result(later_result)
    assert {finding.rule_id for finding in record_result.validated_record.findings} == {RuleId.R5}
    assert str(in_memory_position_store.find_position("test-0001").commitment) == "5000000"


# ── Within-file conflict (DEC-1) ──────────────────────────────────────────────


def test_duplicate_key_within_a_file_lands_neither_row(tmp_path, in_memory_position_store):
    feed_path = write_feed_file(
        tmp_path,
        [build_clean_row_values(nav="3298800.00"), build_clean_row_values(nav="3301100.00")],
    )
    ingestion_result = ingest_feed_file(feed_path, in_memory_position_store, FIXED_INGESTION_MOMENT)
    assert _store_outcomes(ingestion_result) == [None, None]
    assert in_memory_position_store.count_positions() == 0


def test_duplicate_key_within_a_file_does_not_touch_an_earlier_delivery(
    tmp_path, in_memory_position_store
):
    first_feed = write_feed_file(tmp_path, [build_clean_row_values()], file_name="day-one.csv")
    conflicting_feed = write_feed_file(
        tmp_path,
        [build_clean_row_values(nav="1"), build_clean_row_values(nav="2")],
        file_name="day-two.csv",
    )
    ingest_feed_file(first_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    ingest_feed_file(conflicting_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    assert str(in_memory_position_store.find_position("test-0001").nav) == "900000.00"
    assert in_memory_position_store.count_audit_entries() == 0


# ── A crash mid-file rolls the whole file back ────────────────────────────────


class _PositionStoreFailingOnSecondUpsert(PositionStore):
    """Simulates the process dying partway through a file's writes."""

    upsert_calls = 0

    def upsert_position(self, position, recorded_at, source_file_name):
        self.upsert_calls += 1
        if self.upsert_calls == 2:
            raise RuntimeError("simulated crash mid-file")
        return super().upsert_position(position, recorded_at, source_file_name)


def test_crash_mid_file_leaves_no_partial_positions(tmp_path):
    failing_store = _PositionStoreFailingOnSecondUpsert.open_in_memory()
    feed_path = write_feed_file(
        tmp_path,
        [build_clean_row_values(source_row_id=f"test-{index}") for index in range(3)],
    )
    with pytest.raises(RuntimeError):
        ingest_feed_file(feed_path, failing_store, FIXED_INGESTION_MOMENT)
    assert failing_store.count_positions() == 0
    failing_store.close()


# ── File states ───────────────────────────────────────────────────────────────


def test_absent_file_is_benign_and_touches_nothing(tmp_path, in_memory_position_store):
    ingestion_result = ingest_feed_file(
        tmp_path / "not-delivered.csv", in_memory_position_store, FIXED_INGESTION_MOMENT
    )
    assert ingestion_result.file_outcome == FileOutcome.ABSENT
    assert ingestion_result.record_results == ()


def test_header_only_file_is_empty_and_touches_nothing(tmp_path, in_memory_position_store):
    feed_path = write_feed_file(tmp_path, [])
    ingestion_result = ingest_feed_file(feed_path, in_memory_position_store, FIXED_INGESTION_MOMENT)
    assert ingestion_result.file_outcome == FileOutcome.EMPTY
    assert in_memory_position_store.count_positions() == 0


def test_refused_file_names_its_reason_and_touches_nothing(tmp_path, in_memory_position_store):
    feed_path = tmp_path / "not-a-feed.csv"
    feed_path.write_bytes(b"\xff\xfe\x00garbage")
    ingestion_result = ingest_feed_file(feed_path, in_memory_position_store, FIXED_INGESTION_MOMENT)
    assert ingestion_result.file_outcome == FileOutcome.REFUSED
    assert ingestion_result.refusal_reason_category == "not_utf8"
    assert in_memory_position_store.count_positions() == 0
