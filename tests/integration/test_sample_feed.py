"""The provided sample feed: every row's decision and findings, pinned exactly.

This is the answer to "does the validator find the real problems in this feed".
Each expectation names the rule from SPEC.md that the row exercises.
"""

from __future__ import annotations

import pytest

from positions_feed.feed_reader import read_feed_rows
from positions_feed.findings import RecordDecision
from positions_feed.rules import RuleId
from positions_feed.validation import validate_feed_rows
from tests.conftest import FIXED_RUN_DATE, SAMPLE_FEED_PATH

_REJECTED = RecordDecision.REJECTED
_FLAGGED = RecordDecision.LANDED_FLAGGED
_CORRECTED = RecordDecision.LANDED_CORRECTED
_CLEAN = RecordDecision.LANDED_CLEAN

# row number: (source_row_id, decision, rule ids)
_EXPECTED_OUTCOME_BY_ROW_NUMBER = {
    1: ("src-1001", _CLEAN, set()),
    2: ("src-1002", _CLEAN, set()),
    3: ("src-1003", _CLEAN, set()),
    4: ("src-1004", _REJECTED, {RuleId.R5}),
    5: ("src-1005", _CORRECTED, {RuleId.C4}),
    6: ("src-1006", _CLEAN, set()),
    7: ("src-1007", _REJECTED, {RuleId.DEC_1, RuleId.W5, RuleId.C2}),
    8: ("src-1007", _REJECTED, {RuleId.DEC_1}),
    9: ("src-1009", _CORRECTED, {RuleId.C1}),
    10: ("src-1010", _FLAGGED, {RuleId.W1, RuleId.C4}),
    11: ("src-1011", _REJECTED, {RuleId.R2}),
    12: (None, _REJECTED, {RuleId.R1}),
    13: ("src-1013", _FLAGGED, {RuleId.W4, RuleId.C3}),
    14: ("src-1014", _CLEAN, set()),
    15: ("src-1015", _REJECTED, {RuleId.R3}),
    16: ("src-1016", _FLAGGED, {RuleId.W3}),
    17: ("src-1017", _REJECTED, {RuleId.R3}),
    18: ("src-1018", _CORRECTED, {RuleId.C4}),
    19: ("src-1019", _REJECTED, {RuleId.R6}),
    20: ("src-1020", _REJECTED, {RuleId.R5}),
    21: ("src-1021", _CLEAN, set()),
    22: ("src-1022", _CLEAN, set()),
    23: ("src-1023", _FLAGGED, {RuleId.W4, RuleId.C3}),
    24: ("src-1024", _CLEAN, set()),
    25: ("src-1025", _CLEAN, set()),
}


@pytest.fixture(scope="module")
def validated_sample_records_by_row_number():
    validated_records = validate_feed_rows(read_feed_rows(SAMPLE_FEED_PATH), FIXED_RUN_DATE)
    return {validated_record.row_number: validated_record for validated_record in validated_records}


def test_every_sample_row_is_accounted_for(validated_sample_records_by_row_number):
    assert set(validated_sample_records_by_row_number) == set(_EXPECTED_OUTCOME_BY_ROW_NUMBER)


@pytest.mark.parametrize("row_number", sorted(_EXPECTED_OUTCOME_BY_ROW_NUMBER))
def test_sample_row_decision_and_findings(row_number, validated_sample_records_by_row_number):
    expected_source_row_id, expected_decision, expected_rule_ids = _EXPECTED_OUTCOME_BY_ROW_NUMBER[
        row_number
    ]
    validated_record = validated_sample_records_by_row_number[row_number]
    assert validated_record.source_row_id == expected_source_row_id
    assert validated_record.decision == expected_decision
    assert {finding.rule_id for finding in validated_record.findings} == expected_rule_ids


def test_sample_share_classes_are_split(validated_sample_records_by_row_number):
    assert validated_sample_records_by_row_number[5].position.share_class == "A"
    assert validated_sample_records_by_row_number[10].position.share_class == "A"
    assert validated_sample_records_by_row_number[18].position.share_class == "B"
    assert validated_sample_records_by_row_number[18].position.fund_name == "Meridian Growth VI"
