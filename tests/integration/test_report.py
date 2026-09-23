"""The exceptions report: structure, counts, and that no personal data leaves in it."""

from __future__ import annotations

import json

import pytest

from positions_feed.ingestion import ingest_feed_file
from positions_feed.report import (
    REPORT_FORMAT_VERSION,
    build_structured_report,
    render_human_summary,
)
from tests.conftest import (
    FIXED_INGESTION_MOMENT,
    SAMPLE_FEED_ACCOUNT_HOLDERS,
    SAMPLE_FEED_ADVISOR_EMAILS,
    SAMPLE_FEED_PATH,
    build_clean_row_values,
    write_feed_file,
)


@pytest.fixture
def sample_ingestion_result(in_memory_position_store):
    return ingest_feed_file(SAMPLE_FEED_PATH, in_memory_position_store, FIXED_INGESTION_MOMENT)


@pytest.fixture
def sample_structured_report(sample_ingestion_result):
    return build_structured_report(sample_ingestion_result)


def test_report_header_identifies_the_file_and_run(sample_structured_report):
    assert sample_structured_report["report_format_version"] == REPORT_FORMAT_VERSION
    assert sample_structured_report["feed_file_name"] == "sample-positions-feed.csv"
    assert sample_structured_report["ingested_at"] == "2026-09-23T02:00:00+00:00"
    assert sample_structured_report["file_outcome"] == "processed"
    assert sample_structured_report["refusal_reason_category"] is None


def test_report_counts_by_decision(sample_structured_report):
    assert sample_structured_report["counts"]["rows_read"] == 25
    assert sample_structured_report["counts"]["by_decision"] == {
        "rejected": 9,
        "landed_flagged": 4,
        "landed_corrected": 3,
        "landed_clean": 9,
    }


def test_report_counts_by_reason_category(sample_structured_report):
    assert sample_structured_report["counts"]["by_reason_category"] == {
        "missing_source_row_id": 1,
        "negative_nav": 1,
        "closed_with_non_zero_nav": 2,
        "missing_or_unparseable_required_field": 2,
        "blank_currency": 1,
        "duplicate_source_row_id_in_file": 2,
        "commitment_defaulted_to_zero": 1,
        "non_usd_currency": 1,
        "nav_date_not_iso": 2,
        "fund_name_needed_trimming": 1,
        "currency_upper_cased": 1,
        "fund_name_trimmed": 1,
        "nav_date_normalised_to_iso": 2,
        "share_class_split_from_fund_name": 3,
    }


def test_report_counts_by_store_outcome(sample_structured_report):
    assert sample_structured_report["counts"]["by_store_outcome"] == {
        "inserted": 16,
        "unchanged": 0,
        "superseded": 0,
    }


def test_report_records_every_row_with_its_findings(sample_structured_report):
    records = sample_structured_report["records"]
    assert len(records) == 25
    src_1013 = next(record for record in records if record["source_row_id"] == "src-1013")
    assert src_1013["row_number"] == 13
    assert src_1013["decision"] == "landed_flagged"
    assert src_1013["store_outcome"] == "inserted"
    normalisation = next(finding for finding in src_1013["findings"] if finding["rule_id"] == "C3")
    assert normalisation == {
        "rule_id": "C3",
        "severity": "auto_correct",
        "reason_category": "nav_date_normalised_to_iso",
        "field": "nav_date",
        "before": "31-Mar-2026",
        "after": "2026-03-31",
        "value_length": None,
        "detail": None,
    }


@pytest.mark.parametrize("source_row_id", ["src-1004", "src-1020"])
def test_report_flags_slash_dates_as_rejected_with_the_reason(sample_structured_report, source_row_id):
    slash_date_record = next(
        record
        for record in sample_structured_report["records"]
        if record["source_row_id"] == source_row_id
    )
    assert slash_date_record["decision"] == "rejected"
    assert slash_date_record["store_outcome"] is None
    assert slash_date_record["findings"] == [
        {
            "rule_id": "R5",
            "severity": "reject",
            "reason_category": "missing_or_unparseable_required_field",
            "field": "nav_date",
            "before": None,
            "after": None,
            "value_length": len("03/31/2026"),
            "detail": "slash_date_order_unconfirmed",
        }
    ]


def test_report_row_without_key_is_identified_by_row_number(sample_structured_report):
    keyless_record = sample_structured_report["records"][11]
    assert keyless_record["row_number"] == 12
    assert keyless_record["source_row_id"] is None
    assert keyless_record["findings"][0]["rule_id"] == "R1"


def test_report_is_json_serialisable_and_carries_no_personal_data(sample_structured_report):
    report_text = json.dumps(sample_structured_report)
    for personal_value in (*SAMPLE_FEED_ACCOUNT_HOLDERS, *SAMPLE_FEED_ADVISOR_EMAILS):
        assert personal_value not in report_text
    assert "@" not in report_text


def test_superseded_positions_are_counted_as_their_own_category(tmp_path, in_memory_position_store):
    first_feed = write_feed_file(tmp_path, [build_clean_row_values()], file_name="day-one.csv")
    later_feed = write_feed_file(
        tmp_path, [build_clean_row_values(nav="1")], file_name="day-two.csv"
    )
    ingest_feed_file(first_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    later_report = build_structured_report(
        ingest_feed_file(later_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    )
    assert later_report["counts"]["by_store_outcome"]["superseded"] == 1
    assert later_report["counts"]["by_decision"]["rejected"] == 0


def test_lower_commitment_on_redelivery_is_counted_and_summarised(tmp_path, in_memory_position_store):
    first_feed = write_feed_file(
        tmp_path, [build_clean_row_values(commitment="5000000")], file_name="day-one.csv"
    )
    later_feed = write_feed_file(
        tmp_path, [build_clean_row_values(commitment="4000000")], file_name="day-two.csv"
    )
    ingest_feed_file(first_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    later_result = ingest_feed_file(later_feed, in_memory_position_store, FIXED_INGESTION_MOMENT)
    later_report = build_structured_report(later_result)
    assert later_report["counts"]["by_reason_category"] == {
        "commitment_lower_than_previously_delivered": 1
    }
    assert later_report["counts"]["by_decision"]["landed_flagged"] == 1
    assert "W7 commitment_lower_than_previously_delivered: 1" in render_human_summary(later_result)


def test_refused_file_report_names_the_reason_and_has_no_records(tmp_path, in_memory_position_store):
    feed_path = tmp_path / "not-a-feed.csv"
    feed_path.write_bytes(b"\xff\xfe")
    refused_report = build_structured_report(
        ingest_feed_file(feed_path, in_memory_position_store, FIXED_INGESTION_MOMENT)
    )
    assert refused_report["file_outcome"] == "refused"
    assert refused_report["refusal_reason_category"] == "not_utf8"
    assert refused_report["records"] == []


# ── Human summary ─────────────────────────────────────────────────────────────


def test_human_summary_states_the_outcome_and_counts(sample_ingestion_result):
    summary_text = render_human_summary(sample_ingestion_result)
    assert "sample-positions-feed.csv" in summary_text
    assert "25 rows read" in summary_text
    assert "9 rejected" in summary_text
    assert "16 landed" in summary_text
    assert "R3 closed_with_non_zero_nav: 2" in summary_text


def test_human_summary_lists_each_rejected_row(sample_ingestion_result):
    summary_text = render_human_summary(sample_ingestion_result)
    assert "row 12 (no source_row_id): R1 (source_row_id)" in summary_text
    assert "row 19 src-1019: R6 (currency)" in summary_text


def test_human_summary_names_the_field_and_reason_for_a_rejected_slash_date(sample_ingestion_result):
    summary_text = render_human_summary(sample_ingestion_result)
    assert "row 4 src-1004: R5 (nav_date: slash_date_order_unconfirmed)" in summary_text
    assert "row 20 src-1020: R5 (nav_date: slash_date_order_unconfirmed)" in summary_text


def test_human_summary_carries_no_personal_data(sample_ingestion_result):
    summary_text = render_human_summary(sample_ingestion_result)
    for personal_value in (*SAMPLE_FEED_ACCOUNT_HOLDERS, *SAMPLE_FEED_ADVISOR_EMAILS):
        assert personal_value not in summary_text
