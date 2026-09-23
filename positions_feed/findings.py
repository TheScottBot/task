"""Findings raised against a record, and the decision they add up to."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from .rules import VALIDATION_RULES, RuleId, Severity


@dataclass(frozen=True)
class Finding:
    """One problem or transformation on one field of one record.

    A transform carries ``value_before`` and ``value_after``, since the client
    needs to see exactly what we changed. A reject carries only ``value_length``:
    the offending value may be personal data, and the row number and field name
    are enough for the client to find it in their own export.
    """

    rule_id: RuleId
    field_name: str
    value_before: str | None = None
    value_after: str | None = None
    value_length: int | None = None
    detail: str | None = None

    @property
    def severity(self) -> Severity:
        return VALIDATION_RULES[self.rule_id].severity

    @property
    def reason_category(self) -> str:
        return VALIDATION_RULES[self.rule_id].reason_category


class RecordDecision(Enum):
    """What happened to a record, from the most severe finding it carries."""

    REJECTED = "rejected"
    LANDED_FLAGGED = "landed_flagged"
    LANDED_CORRECTED = "landed_corrected"
    LANDED_CLEAN = "landed_clean"


def decide_record(findings: Iterable[Finding]) -> RecordDecision:
    """Return the decision: any reject rejects, then warn outranks auto-correct."""
    severities = {finding.severity for finding in findings}
    if Severity.REJECT in severities:
        return RecordDecision.REJECTED
    if Severity.WARN in severities:
        return RecordDecision.LANDED_FLAGGED
    if Severity.AUTO_CORRECT in severities:
        return RecordDecision.LANDED_CORRECTED
    return RecordDecision.LANDED_CLEAN
