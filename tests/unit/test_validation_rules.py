"""One or more tests per row of the validation table in SPEC.md, on synthetic rows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from positions_feed.feed_reader import RawFeedRow
from positions_feed.findings import RecordDecision
from positions_feed.model import PositionStatus
from positions_feed.nav_dates import SLASH_DATE_ORDER_UNCONFIRMED
from positions_feed.rules import VALIDATION_RULES, RuleId, Severity
from positions_feed.validation import ROW_SHAPE_FIELD_NAME, ValidatedRecord, validate_feed_rows
from tests.conftest import FIXED_RUN_DATE, build_raw_row


def _validate_single_row(**overrides: str) -> ValidatedRecord:
    return validate_feed_rows([build_raw_row(**overrides)], FIXED_RUN_DATE)[0]


def _rule_ids(validated_record: ValidatedRecord) -> set[RuleId]:
    return {finding.rule_id for finding in validated_record.findings}


def _only_finding_for(validated_record: ValidatedRecord, rule_id: RuleId):
    matching_findings = [
        finding for finding in validated_record.findings if finding.rule_id == rule_id
    ]
    assert len(matching_findings) == 1, f"expected exactly one {rule_id} finding"
    return matching_findings[0]


# ── The table itself ──────────────────────────────────────────────────────────


def test_every_rule_id_has_exactly_one_definition():
    assert set(VALIDATION_RULES) == set(RuleId)


def test_rule_reason_categories_are_unique():
    reason_categories = [rule.reason_category for rule in VALIDATION_RULES.values()]
    assert len(reason_categories) == len(set(reason_categories))


@pytest.mark.parametrize(
    "rule_id, expected_severity",
    [
        (RuleId.R1, Severity.REJECT),
        (RuleId.R2, Severity.REJECT),
        (RuleId.R3, Severity.REJECT),
        (RuleId.R4, Severity.REJECT),
        (RuleId.R5, Severity.REJECT),
        (RuleId.R6, Severity.REJECT),
        (RuleId.DEC_1, Severity.REJECT),
        (RuleId.W1, Severity.WARN),
        (RuleId.W3, Severity.WARN),
        (RuleId.W4, Severity.WARN),
        (RuleId.W5, Severity.WARN),
        (RuleId.C1, Severity.AUTO_CORRECT),
        (RuleId.C2, Severity.AUTO_CORRECT),
        (RuleId.C3, Severity.AUTO_CORRECT),
        (RuleId.C4, Severity.AUTO_CORRECT),
    ],
)
def test_rule_severity_matches_the_specification(rule_id, expected_severity):
    assert VALIDATION_RULES[rule_id].severity == expected_severity


# ── Clean row ─────────────────────────────────────────────────────────────────


def test_clean_row_lands_with_no_findings_and_exact_canonical_values():
    validated_record = _validate_single_row()
    assert validated_record.findings == ()
    assert validated_record.decision == RecordDecision.LANDED_CLEAN
    position = validated_record.position
    assert position is not None
    assert position.source_row_id == "test-0001"
    assert position.account_id == "TA-00001"
    assert position.account_holder == "Synthetic Test Holder"
    assert position.fund_name == "Synthetic Fund I"
    assert position.share_class is None
    assert position.vintage_year == 2020
    assert position.commitment == Decimal("1000000")
    assert position.nav == Decimal("900000.00")
    assert position.nav_date == date(2026, 3, 31)
    assert position.currency == "USD"
    assert position.status == PositionStatus.ACTIVE
    assert position.advisor_email == "advisor@example.test"


def test_money_is_decimal_and_keeps_every_digit():
    position = _validate_single_row(nav="4123500.25", commitment="0.10").position
    assert isinstance(position.nav, Decimal)
    assert position.nav == Decimal("4123500.25")
    assert position.commitment == Decimal("0.10")


# ── R1 blank source_row_id ────────────────────────────────────────────────────


@pytest.mark.parametrize("blank_value", ["", "   "])
def test_r1_blank_source_row_id_rejects(blank_value):
    validated_record = _validate_single_row(source_row_id=blank_value)
    assert RuleId.R1 in _rule_ids(validated_record)
    assert validated_record.decision == RecordDecision.REJECTED
    assert validated_record.position is None
    assert validated_record.source_row_id is None


# ── R2 negative NAV ───────────────────────────────────────────────────────────


def test_r2_negative_nav_rejects():
    validated_record = _validate_single_row(nav="-42100.00")
    assert _rule_ids(validated_record) == {RuleId.R2}
    assert validated_record.decision == RecordDecision.REJECTED


def test_r2_zero_nav_on_active_position_is_clean():
    assert _validate_single_row(nav="0").findings == ()


# ── R3 Closed with non-zero NAV ───────────────────────────────────────────────


def test_r3_closed_with_non_zero_nav_rejects():
    validated_record = _validate_single_row(status="Closed", nav="618450.00")
    assert _rule_ids(validated_record) == {RuleId.R3}
    assert validated_record.decision == RecordDecision.REJECTED


@pytest.mark.parametrize("zero_nav", ["0", "0.00"])
def test_r3_closed_with_zero_nav_lands(zero_nav):
    validated_record = _validate_single_row(status="Closed", nav=zero_nav)
    assert validated_record.findings == ()
    assert validated_record.position.status == PositionStatus.CLOSED


def test_r3_closed_with_negative_nav_reports_both_r2_and_r3():
    assert _rule_ids(_validate_single_row(status="Closed", nav="-1")) == {RuleId.R2, RuleId.R3}


# ── R4 unknown status ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("unknown_status", ["Pending", "active", "ACTIVE", "closed", " Active"])
def test_r4_unknown_status_rejects_without_case_folding(unknown_status):
    validated_record = _validate_single_row(status=unknown_status)
    assert _rule_ids(validated_record) == {RuleId.R4}
    assert validated_record.decision == RecordDecision.REJECTED


# ── R5 required field missing ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "required_column",
    [
        "account_id",
        "account_holder",
        "fund_name",
        "vintage_year",
        "nav",
        "nav_date",
        "status",
        "advisor_email",
    ],
)
@pytest.mark.parametrize("blank_value", ["", "   "])
def test_r5_blank_required_field_rejects(required_column, blank_value):
    validated_record = _validate_single_row(**{required_column: blank_value})
    assert _rule_ids(validated_record) == {RuleId.R5}
    assert _only_finding_for(validated_record, RuleId.R5).field_name == required_column
    assert validated_record.decision == RecordDecision.REJECTED


# ── R5 required field unparseable ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "column_name, unparseable_value",
    [
        ("vintage_year", "twenty"),
        ("vintage_year", "2019.0"),
        ("vintage_year", "19"),
        ("nav", "abc"),
        ("nav", "1e5"),
        ("nav", "NaN"),
        ("nav", "Infinity"),
        ("nav", "1,000.00"),
        ("nav", "$100"),
        ("nav", "100."),
        ("nav", ".5"),
        ("nav_date", "2026/03/31"),
        ("currency", "US$"),
        ("currency", "US"),
        ("currency", "USDX"),
        ("currency", "U5D"),
        ("currency", " USD"),
        ("advisor_email", "not-an-email"),
        ("advisor_email", "missing-domain@"),
        ("advisor_email", "two@@example.test"),
        ("advisor_email", "no-dot@example"),
        ("advisor_email", "space in@example.test"),
        ("commitment", "-5"),
        ("source_row_id", " src-1001"),
        ("source_row_id", "src-1001 "),
    ],
)
def test_r5_unparseable_required_field_rejects(column_name, unparseable_value):
    validated_record = _validate_single_row(**{column_name: unparseable_value})
    assert _rule_ids(validated_record) == {RuleId.R5}
    assert _only_finding_for(validated_record, RuleId.R5).field_name == column_name
    assert validated_record.position is None


@pytest.mark.parametrize("slash_nav_date", ["03/31/2026", "03/04/2026", "31/03/2026"])
def test_r5_slash_nav_date_rejects_with_the_unconfirmed_order_named(slash_nav_date):
    validated_record = _validate_single_row(nav_date=slash_nav_date)
    assert _rule_ids(validated_record) == {RuleId.R5}
    r5_finding = _only_finding_for(validated_record, RuleId.R5)
    assert r5_finding.field_name == "nav_date"
    assert r5_finding.detail == SLASH_DATE_ORDER_UNCONFIRMED
    assert validated_record.decision == RecordDecision.REJECTED
    assert validated_record.position is None


@pytest.mark.parametrize(
    "vintage_year, expected_rule_ids",
    [
        ("1979", {RuleId.R5}),
        ("1980", set()),
        (str(FIXED_RUN_DATE.year), set()),
        (str(FIXED_RUN_DATE.year + 1), {RuleId.R5}),
    ],
)
def test_r5_vintage_year_is_bounded_from_1980_to_the_run_year(vintage_year, expected_rule_ids):
    assert _rule_ids(_validate_single_row(vintage_year=vintage_year)) == expected_rule_ids


def test_r5_row_with_wrong_number_of_fields_rejects():
    ragged_row = RawFeedRow(row_number=1, values_by_column=None, field_count=9)
    validated_record = validate_feed_rows([ragged_row], FIXED_RUN_DATE)[0]
    assert _rule_ids(validated_record) == {RuleId.R5}
    r5_finding = _only_finding_for(validated_record, RuleId.R5)
    assert r5_finding.field_name == ROW_SHAPE_FIELD_NAME
    assert r5_finding.value_length == 9
    assert validated_record.source_row_id is None
    assert validated_record.decision == RecordDecision.REJECTED


def test_reject_finding_carries_length_not_value():
    validated_record = _validate_single_row(advisor_email="not-an-email")
    r5_finding = _only_finding_for(validated_record, RuleId.R5)
    assert r5_finding.value_before is None
    assert r5_finding.value_after is None
    assert r5_finding.value_length == len("not-an-email")


# ── R6 blank currency ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("blank_value", ["", "   "])
def test_r6_blank_currency_rejects_rather_than_defaulting(blank_value):
    validated_record = _validate_single_row(currency=blank_value)
    assert _rule_ids(validated_record) == {RuleId.R6}
    assert validated_record.decision == RecordDecision.REJECTED
    assert validated_record.position is None


# ── DEC-1 within-file duplicate key ───────────────────────────────────────────


def test_dec_1_duplicate_key_within_file_rejects_every_row_carrying_it():
    raw_rows = [
        build_raw_row(row_number=1, source_row_id="test-0007", nav="3298800.00"),
        build_raw_row(row_number=2, source_row_id="test-0008"),
        build_raw_row(row_number=3, source_row_id="test-0007", nav="3301100.00"),
    ]
    first_duplicate, distinct_row, second_duplicate = validate_feed_rows(raw_rows, FIXED_RUN_DATE)
    assert _rule_ids(first_duplicate) == {RuleId.DEC_1}
    assert _rule_ids(second_duplicate) == {RuleId.DEC_1}
    assert first_duplicate.decision == RecordDecision.REJECTED
    assert second_duplicate.decision == RecordDecision.REJECTED
    assert distinct_row.decision == RecordDecision.LANDED_CLEAN


def test_dec_1_identical_duplicate_rows_are_still_both_rejected():
    raw_rows = [build_raw_row(row_number=1), build_raw_row(row_number=2)]
    assert all(
        validated_record.decision == RecordDecision.REJECTED
        for validated_record in validate_feed_rows(raw_rows, FIXED_RUN_DATE)
    )


def test_dec_1_blank_keys_are_not_duplicates_of_each_other():
    raw_rows = [
        build_raw_row(row_number=1, source_row_id=""),
        build_raw_row(row_number=2, source_row_id=""),
    ]
    for validated_record in validate_feed_rows(raw_rows, FIXED_RUN_DATE):
        assert _rule_ids(validated_record) == {RuleId.R1}


# ── W1 commitment blank or non-numeric ────────────────────────────────────────


@pytest.mark.parametrize("unusable_commitment", ["", "N/A", "tbc"])
def test_w1_unusable_commitment_lands_as_zero_and_is_flagged(unusable_commitment):
    validated_record = _validate_single_row(commitment=unusable_commitment)
    assert _rule_ids(validated_record) == {RuleId.W1}
    w1_finding = _only_finding_for(validated_record, RuleId.W1)
    assert w1_finding.value_before == unusable_commitment
    assert w1_finding.value_after == "0"
    assert validated_record.position.commitment == Decimal("0")
    assert validated_record.decision == RecordDecision.LANDED_FLAGGED


def test_w1_explicit_zero_commitment_is_clean():
    assert _validate_single_row(commitment="0").findings == ()


# ── W3 currency valid but not USD ─────────────────────────────────────────────


def test_w3_non_usd_currency_lands_flagged():
    validated_record = _validate_single_row(currency="EUR")
    assert _rule_ids(validated_record) == {RuleId.W3}
    assert validated_record.position.currency == "EUR"
    assert validated_record.decision == RecordDecision.LANDED_FLAGGED


def test_w3_and_c1_both_apply_to_lower_case_non_usd_currency():
    validated_record = _validate_single_row(currency="eur")
    assert _rule_ids(validated_record) == {RuleId.W3, RuleId.C1}
    assert validated_record.position.currency == "EUR"


# ── W4 and C3 NAV date normalised ─────────────────────────────────────────────


@pytest.mark.parametrize("non_iso_nav_date", ["31-Mar-2026", "31-MAR-2026"])
def test_w4_and_c3_written_month_nav_date_is_normalised_and_flagged(non_iso_nav_date):
    validated_record = _validate_single_row(nav_date=non_iso_nav_date)
    assert _rule_ids(validated_record) == {RuleId.W4, RuleId.C3}
    c3_finding = _only_finding_for(validated_record, RuleId.C3)
    assert c3_finding.field_name == "nav_date"
    assert c3_finding.value_before == non_iso_nav_date
    assert c3_finding.value_after == "2026-03-31"
    assert validated_record.position.nav_date == date(2026, 3, 31)
    assert validated_record.decision == RecordDecision.LANDED_FLAGGED


# ── W5 and C2 fund name trimmed ───────────────────────────────────────────────


@pytest.mark.parametrize("untrimmed_fund_name", ["North Haven VII ", " North Haven VII", "\tNorth Haven VII"])
def test_w5_and_c2_fund_name_is_trimmed_and_flagged(untrimmed_fund_name):
    validated_record = _validate_single_row(fund_name=untrimmed_fund_name)
    assert _rule_ids(validated_record) == {RuleId.W5, RuleId.C2}
    c2_finding = _only_finding_for(validated_record, RuleId.C2)
    assert c2_finding.value_before == untrimmed_fund_name
    assert c2_finding.value_after == "North Haven VII"
    assert validated_record.position.fund_name == "North Haven VII"


# ── C1 currency upper-cased ───────────────────────────────────────────────────


@pytest.mark.parametrize("lower_case_currency", ["usd", "Usd"])
def test_c1_lower_case_currency_is_upper_cased(lower_case_currency):
    validated_record = _validate_single_row(currency=lower_case_currency)
    assert _rule_ids(validated_record) == {RuleId.C1}
    c1_finding = _only_finding_for(validated_record, RuleId.C1)
    assert (c1_finding.value_before, c1_finding.value_after) == (lower_case_currency, "USD")
    assert validated_record.position.currency == "USD"
    assert validated_record.decision == RecordDecision.LANDED_CORRECTED


# ── C4 share class split ──────────────────────────────────────────────────────


@pytest.mark.parametrize("share_class", ["A", "B"])
def test_c4_share_class_suffix_is_split_out(share_class):
    validated_record = _validate_single_row(fund_name=f"Meridian Growth VI - Class {share_class}")
    assert _rule_ids(validated_record) == {RuleId.C4}
    assert validated_record.position.fund_name == "Meridian Growth VI"
    assert validated_record.position.share_class == share_class
    c4_finding = _only_finding_for(validated_record, RuleId.C4)
    assert c4_finding.value_before == f"Meridian Growth VI - Class {share_class}"
    assert c4_finding.value_after == "Meridian Growth VI"
    assert validated_record.decision == RecordDecision.LANDED_CORRECTED


def test_c4_split_follows_the_trim():
    validated_record = _validate_single_row(fund_name="Meridian Growth VI - Class A ")
    assert _rule_ids(validated_record) == {RuleId.C2, RuleId.W5, RuleId.C4}
    assert validated_record.position.share_class == "A"


@pytest.mark.parametrize(
    "fund_name_without_suffix", ["Class A Holdings", "Meridian Growth VI - Class", "Meridian Growth VI Class A"]
)
def test_c4_does_not_split_without_a_well_formed_suffix(fund_name_without_suffix):
    validated_record = _validate_single_row(fund_name=fund_name_without_suffix)
    assert validated_record.findings == ()
    assert validated_record.position.share_class is None


# ── Decision and collection ───────────────────────────────────────────────────


def test_every_problem_on_a_row_is_reported_not_just_the_first():
    validated_record = _validate_single_row(nav="-1", advisor_email="", currency="usd")
    assert _rule_ids(validated_record) == {RuleId.R2, RuleId.R5, RuleId.C1}
    assert validated_record.decision == RecordDecision.REJECTED


def test_warn_outranks_auto_correct_in_the_record_decision():
    validated_record = _validate_single_row(currency="eur")
    assert validated_record.decision == RecordDecision.LANDED_FLAGGED
