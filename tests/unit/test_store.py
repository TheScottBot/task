"""The position store: insert, no-op, supersede with audit, and transactions."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from positions_feed.store import CROSS_FILE_CORRECTION_REASON, PositionStore, StoreOutcome
from positions_feed.validation import validate_feed_rows
from tests.conftest import FIXED_INGESTION_MOMENT, FIXED_RUN_DATE, build_raw_row


def _clean_position(**overrides: str):
    return validate_feed_rows([build_raw_row(**overrides)], FIXED_RUN_DATE)[0].position


def test_absent_key_is_inserted(in_memory_position_store):
    position = _clean_position()
    with in_memory_position_store.transaction():
        outcome = in_memory_position_store.upsert_position(
            position, FIXED_INGESTION_MOMENT, "day-one.csv"
        )
    assert outcome == StoreOutcome.INSERTED
    assert in_memory_position_store.find_position("test-0001") == position


def test_same_position_again_is_a_no_op(in_memory_position_store):
    position = _clean_position()
    with in_memory_position_store.transaction():
        in_memory_position_store.upsert_position(position, FIXED_INGESTION_MOMENT, "day-one.csv")
        outcome = in_memory_position_store.upsert_position(
            position, FIXED_INGESTION_MOMENT, "day-two.csv"
        )
    assert outcome == StoreOutcome.UNCHANGED
    assert in_memory_position_store.count_positions() == 1
    assert in_memory_position_store.list_audit_entries("test-0001") == []


def test_trailing_zeros_alone_are_not_a_change(in_memory_position_store):
    with in_memory_position_store.transaction():
        in_memory_position_store.upsert_position(
            _clean_position(nav="2210800.00"), FIXED_INGESTION_MOMENT, "day-one.csv"
        )
        outcome = in_memory_position_store.upsert_position(
            _clean_position(nav="2210800"), FIXED_INGESTION_MOMENT, "day-two.csv"
        )
    assert outcome == StoreOutcome.UNCHANGED


def test_changed_position_supersedes_and_writes_an_audit_row(in_memory_position_store):
    original_position = _clean_position(nav="3298800.00")
    corrected_position = replace(original_position, nav=Decimal("3301100.00"))
    with in_memory_position_store.transaction():
        in_memory_position_store.upsert_position(
            original_position, FIXED_INGESTION_MOMENT, "day-one.csv"
        )
        outcome = in_memory_position_store.upsert_position(
            corrected_position, FIXED_INGESTION_MOMENT, "day-two.csv"
        )
    assert outcome == StoreOutcome.SUPERSEDED
    assert in_memory_position_store.find_position("test-0001") == corrected_position
    (audit_entry,) = in_memory_position_store.list_audit_entries("test-0001")
    assert audit_entry.previous_position == original_position
    assert audit_entry.new_position == corrected_position
    assert audit_entry.reason == CROSS_FILE_CORRECTION_REASON
    assert audit_entry.recorded_at == FIXED_INGESTION_MOMENT
    assert audit_entry.source_file_name == "day-two.csv"


def test_decimal_money_round_trips_exactly(in_memory_position_store):
    position = _clean_position(nav="4123500.25", commitment="0.10")
    with in_memory_position_store.transaction():
        in_memory_position_store.upsert_position(position, FIXED_INGESTION_MOMENT, "day-one.csv")
    stored_position = in_memory_position_store.find_position("test-0001")
    assert stored_position.nav == Decimal("4123500.25")
    assert str(stored_position.commitment) == "0.10"


def test_failure_inside_a_transaction_rolls_everything_back(in_memory_position_store):
    with pytest.raises(RuntimeError), in_memory_position_store.transaction():
        in_memory_position_store.upsert_position(
            _clean_position(), FIXED_INGESTION_MOMENT, "day-one.csv"
        )
        raise RuntimeError("simulated crash mid-file")
    assert in_memory_position_store.count_positions() == 0


def test_file_backed_store_keeps_positions_across_a_restart(tmp_path):
    database_path = tmp_path / "positions.sqlite3"
    first_store = PositionStore.open_file(database_path)
    with first_store.transaction():
        first_store.upsert_position(_clean_position(), FIXED_INGESTION_MOMENT, "day-one.csv")
    first_store.close()

    reopened_store = PositionStore.open_file(database_path)
    assert reopened_store.find_position("test-0001") == _clean_position()
    reopened_store.close()


def test_unknown_key_is_not_found(in_memory_position_store):
    assert in_memory_position_store.find_position("never-delivered") is None
