"""Validates raw feed rows against the validation table and maps them to positions.

Every rule in ``rules.VALIDATION_RULES`` is raised here and nowhere else. Every
problem on a row is collected, not just the first, so the client sees the whole
picture from one report rather than fixing one problem per nightly run.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .contract import EARLIEST_VINTAGE_YEAR, EXPECTED_CURRENCY
from .feed_reader import RawFeedRow
from .findings import Finding, RecordDecision, decide_record
from .model import Position, PositionStatus
from .nav_dates import parse_nav_date
from .rules import RuleId

# Names the whole row, rather than one field, in a finding about the row's shape.
ROW_SHAPE_FIELD_NAME = "row_shape"
VINTAGE_YEAR_OUT_OF_BOUNDS = "vintage_year_out_of_bounds"

# Plain decimal notation only. Decimal() itself would also accept "NaN",
# "Infinity" and exponents such as "1e5", none of which is a balance.
_DECIMAL_SHAPE = re.compile(r"-?[0-9]+(\.[0-9]+)?")
_VINTAGE_YEAR_SHAPE = re.compile(r"[0-9]{4}")
# The shape of an ISO 4217 code; the standard library carries no list of codes.
_CURRENCY_SHAPE = re.compile(r"[A-Za-z]{3}")
_EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_SHARE_CLASS_SUFFIX = re.compile(r"(?P<fund_name>.+?) - Class (?P<share_class>[A-Za-z0-9]+)")


@dataclass(frozen=True)
class ValidatedRecord:
    """A row's findings, and the position it maps to when nothing rejected it."""

    row_number: int
    source_row_id: str | None
    findings: tuple[Finding, ...]
    position: Position | None

    @property
    def decision(self) -> RecordDecision:
        return decide_record(self.findings)


def _is_blank(raw_value: str) -> bool:
    return raw_value.strip() == ""


def _reject_field(
    findings: list[Finding], rule_id: RuleId, field_name: str, raw_value: str, detail: str | None = None
) -> None:
    findings.append(Finding(rule_id, field_name, value_length=len(raw_value), detail=detail))


def _parse_source_row_id(raw_value: str, findings: list[Finding]) -> str | None:
    if _is_blank(raw_value):
        _reject_field(findings, RuleId.R1, "source_row_id", raw_value)
        return None
    if raw_value != raw_value.strip():
        # A padded key would be a different key from the unpadded one, splitting
        # one position into two across deliveries, so it is refused, not trimmed.
        _reject_field(findings, RuleId.R5, "source_row_id", raw_value)
        return None
    return raw_value


def _parse_required_text(field_name: str, raw_value: str, findings: list[Finding]) -> str | None:
    if _is_blank(raw_value):
        _reject_field(findings, RuleId.R5, field_name, raw_value)
        return None
    return raw_value


def _parse_fund_name(raw_value: str, findings: list[Finding]) -> tuple[str | None, str | None]:
    if _is_blank(raw_value):
        _reject_field(findings, RuleId.R5, "fund_name", raw_value)
        return None, None
    trimmed_fund_name = raw_value.strip()
    if trimmed_fund_name != raw_value:
        findings.append(Finding(RuleId.W5, "fund_name"))
        findings.append(Finding(RuleId.C2, "fund_name", raw_value, trimmed_fund_name))
    share_class_match = _SHARE_CLASS_SUFFIX.fullmatch(trimmed_fund_name)
    if share_class_match is None:
        return trimmed_fund_name, None
    base_fund_name = share_class_match["fund_name"]
    findings.append(Finding(RuleId.C4, "fund_name", trimmed_fund_name, base_fund_name))
    return base_fund_name, share_class_match["share_class"]


def _parse_vintage_year(raw_value: str, run_date: date, findings: list[Finding]) -> int | None:
    if not _VINTAGE_YEAR_SHAPE.fullmatch(raw_value):
        _reject_field(findings, RuleId.R5, "vintage_year", raw_value)
        return None
    vintage_year = int(raw_value)
    if not EARLIEST_VINTAGE_YEAR <= vintage_year <= run_date.year:
        _reject_field(findings, RuleId.R5, "vintage_year", raw_value, VINTAGE_YEAR_OUT_OF_BOUNDS)
        return None
    return vintage_year


def _parse_commitment(raw_value: str, findings: list[Finding]) -> Decimal | None:
    if not _DECIMAL_SHAPE.fullmatch(raw_value):
        # The client reads a blank or non-numeric commitment as a commitment-free
        # secondary purchase and asked for 0, flagged so they can fix the source.
        findings.append(Finding(RuleId.W1, "commitment", raw_value, "0"))
        return Decimal("0")
    commitment = Decimal(raw_value)
    if commitment < 0:
        _reject_field(findings, RuleId.R5, "commitment", raw_value)
        return None
    return commitment


def _parse_nav(raw_value: str, findings: list[Finding]) -> Decimal | None:
    if not _DECIMAL_SHAPE.fullmatch(raw_value):
        _reject_field(findings, RuleId.R5, "nav", raw_value)
        return None
    nav = Decimal(raw_value)
    if nav < 0:
        _reject_field(findings, RuleId.R2, "nav", raw_value)
    return nav


def _parse_nav_date(raw_value: str, findings: list[Finding]) -> date | None:
    if _is_blank(raw_value):
        _reject_field(findings, RuleId.R5, "nav_date", raw_value)
        return None
    parse_result = parse_nav_date(raw_value)
    if parse_result.parsed_date is None:
        _reject_field(findings, RuleId.R5, "nav_date", raw_value, parse_result.failure_detail)
        return None
    if parse_result.was_normalised:
        normalised_nav_date = parse_result.parsed_date.isoformat()
        findings.append(Finding(RuleId.W4, "nav_date", detail=parse_result.source_format))
        findings.append(Finding(RuleId.C3, "nav_date", raw_value, normalised_nav_date))
    return parse_result.parsed_date


def _parse_currency(raw_value: str, findings: list[Finding]) -> str | None:
    if _is_blank(raw_value):
        _reject_field(findings, RuleId.R6, "currency", raw_value)
        return None
    if not _CURRENCY_SHAPE.fullmatch(raw_value):
        _reject_field(findings, RuleId.R5, "currency", raw_value)
        return None
    currency = raw_value.upper()
    if currency != raw_value:
        findings.append(Finding(RuleId.C1, "currency", raw_value, currency))
    if currency != EXPECTED_CURRENCY:
        findings.append(Finding(RuleId.W3, "currency"))
    return currency


def _parse_status(raw_value: str, findings: list[Finding]) -> PositionStatus | None:
    if _is_blank(raw_value):
        _reject_field(findings, RuleId.R5, "status", raw_value)
        return None
    # Matched exactly: the client's two states are an accepted contract, and a
    # variant spelling is an unknown state rather than something to fold.
    for position_status in PositionStatus:
        if raw_value == position_status.value:
            return position_status
    _reject_field(findings, RuleId.R4, "status", raw_value)
    return None


def _parse_advisor_email(raw_value: str, findings: list[Finding]) -> str | None:
    if not _EMAIL_SHAPE.fullmatch(raw_value):
        _reject_field(findings, RuleId.R5, "advisor_email", raw_value)
        return None
    return raw_value


def _validate_row(raw_row: RawFeedRow, duplicated_keys: set[str], run_date: date) -> ValidatedRecord:
    if raw_row.values_by_column is None:
        row_shape_finding = Finding(RuleId.R5, ROW_SHAPE_FIELD_NAME, value_length=raw_row.field_count)
        return ValidatedRecord(raw_row.row_number, None, (row_shape_finding,), None)

    raw_values = raw_row.values_by_column
    findings: list[Finding] = []

    source_row_id = _parse_source_row_id(raw_values["source_row_id"], findings)
    if raw_values["source_row_id"] in duplicated_keys:
        findings.append(Finding(RuleId.DEC_1, "source_row_id"))
    account_id = _parse_required_text("account_id", raw_values["account_id"], findings)
    account_holder = _parse_required_text("account_holder", raw_values["account_holder"], findings)
    fund_name, share_class = _parse_fund_name(raw_values["fund_name"], findings)
    vintage_year = _parse_vintage_year(raw_values["vintage_year"], run_date, findings)
    commitment = _parse_commitment(raw_values["commitment"], findings)
    nav = _parse_nav(raw_values["nav"], findings)
    nav_date = _parse_nav_date(raw_values["nav_date"], findings)
    currency = _parse_currency(raw_values["currency"], findings)
    status = _parse_status(raw_values["status"], findings)
    advisor_email = _parse_advisor_email(raw_values["advisor_email"], findings)

    if status is PositionStatus.CLOSED and nav is not None and nav != 0:
        # The client's rule: a Closed position is fully exited, so a residual NAV
        # is a bug on their side to flag, never a value to land.
        _reject_field(findings, RuleId.R3, "nav", raw_values["nav"])

    reported_source_row_id = None if _is_blank(raw_values["source_row_id"]) else raw_values["source_row_id"]
    if decide_record(findings) is RecordDecision.REJECTED:
        return ValidatedRecord(raw_row.row_number, reported_source_row_id, tuple(findings), None)

    # Each parser either returned a value or recorded a reject, and there was no
    # reject, so none is None here; the asserts narrow the types for mypy.
    assert source_row_id is not None and account_id is not None and account_holder is not None
    assert fund_name is not None and vintage_year is not None and commitment is not None
    assert nav is not None and nav_date is not None and currency is not None
    assert status is not None and advisor_email is not None
    position = Position(
        source_row_id=source_row_id,
        account_id=account_id,
        account_holder=account_holder,
        fund_name=fund_name,
        share_class=share_class,
        vintage_year=vintage_year,
        commitment=commitment,
        nav=nav,
        nav_date=nav_date,
        currency=currency,
        status=status,
        advisor_email=advisor_email,
    )
    return ValidatedRecord(raw_row.row_number, reported_source_row_id, tuple(findings), position)


def _find_duplicated_keys(raw_rows: Sequence[RawFeedRow]) -> set[str]:
    key_counts = Counter(
        raw_row.values_by_column["source_row_id"]
        for raw_row in raw_rows
        if raw_row.values_by_column is not None
        and not _is_blank(raw_row.values_by_column["source_row_id"])
    )
    return {source_row_id for source_row_id, occurrences in key_counts.items() if occurrences > 1}


def validate_feed_rows(raw_rows: Sequence[RawFeedRow], run_date: date) -> list[ValidatedRecord]:
    """Validate every row of one file; ``run_date`` bounds the vintage year."""
    duplicated_keys = _find_duplicated_keys(raw_rows)
    return [_validate_row(raw_row, duplicated_keys, run_date) for raw_row in raw_rows]
