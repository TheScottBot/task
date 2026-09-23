"""The validation table from SPEC.md, expressed once for the code to read from."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    """A finding's severity decides the record's fate."""

    REJECT = "reject"
    WARN = "warn"
    AUTO_CORRECT = "auto_correct"


class RuleId(Enum):
    """Identifiers exactly as SPEC.md names them, so a report line maps to the spec."""

    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"
    R6 = "R6"
    # The within-file duplicate key rule is named after the client decision that
    # settled it rather than given a new R number the spec does not carry.
    DEC_1 = "DEC-1"
    W1 = "W1"
    W3 = "W3"
    W4 = "W4"
    W5 = "W5"
    W6 = "W6"
    W7 = "W7"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"


@dataclass(frozen=True)
class RuleDefinition:
    """One row of the validation table."""

    rule_id: RuleId
    severity: Severity
    reason_category: str
    description: str


def _define(
    rule_id: RuleId, severity: Severity, reason_category: str, description: str
) -> tuple[RuleId, RuleDefinition]:
    return rule_id, RuleDefinition(rule_id, severity, reason_category, description)


VALIDATION_RULES: dict[RuleId, RuleDefinition] = dict(
    [
        _define(RuleId.R1, Severity.REJECT, "missing_source_row_id",
                "source_row_id blank: no audit key, cannot key the position"),
        _define(RuleId.R2, Severity.REJECT, "negative_nav",
                "nav below zero: a NAV cannot be negative"),
        _define(RuleId.R3, Severity.REJECT, "closed_with_non_zero_nav",
                "status Closed with non-zero nav: a source bug the client asked us to flag, not ingest"),
        _define(RuleId.R4, Severity.REJECT, "unknown_status",
                "status neither Active nor Closed: an unknown state is not tolerated"),
        _define(RuleId.R5, Severity.REJECT, "missing_or_unparseable_required_field",
                "a required field missing or unparseable: no silent default for a required field"),
        _define(RuleId.R6, Severity.REJECT, "blank_currency",
                "currency blank: the client prefers a reject to a silent default (DEC-2)"),
        _define(RuleId.DEC_1, Severity.REJECT, "duplicate_source_row_id_in_file",
                "source_row_id repeated within one file: every row carrying it is rejected, file order is not relied on"),
        _define(RuleId.W1, Severity.WARN, "commitment_defaulted_to_zero",
                "commitment blank or non-numeric: set to 0 and flagged for correction at source"),
        _define(RuleId.W3, Severity.WARN, "non_usd_currency",
                "currency valid but not USD: landed, to be confirmed as intentional"),
        _define(RuleId.W4, Severity.WARN, "nav_date_not_iso",
                "nav_date arrived in a non-ISO format: landed, normalisation recorded"),
        _define(RuleId.W5, Severity.WARN, "fund_name_needed_trimming",
                "fund_name arrived with surrounding whitespace: landed, trim recorded"),
        _define(RuleId.W6, Severity.WARN, "nav_high_against_commitment",
                "nav more than five times a non-zero commitment: landed, to be confirmed as not a typo"),
        _define(RuleId.W7, Severity.WARN, "commitment_lower_than_previously_delivered",
                "commitment below the value last delivered for this position: landed, since the latest delivery wins, and flagged because a commitment should not fall"),
        _define(RuleId.C1, Severity.AUTO_CORRECT, "currency_upper_cased",
                "currency in lower case: upper-cased"),
        _define(RuleId.C2, Severity.AUTO_CORRECT, "fund_name_trimmed",
                "fund_name surrounding whitespace: trimmed"),
        _define(RuleId.C3, Severity.AUTO_CORRECT, "nav_date_normalised_to_iso",
                "nav_date in a non-ISO format: converted to ISO 8601"),
        _define(RuleId.C4, Severity.AUTO_CORRECT, "share_class_split_from_fund_name",
                "fund_name carries a share class suffix: split into fund_name and share_class"),
    ]
)
