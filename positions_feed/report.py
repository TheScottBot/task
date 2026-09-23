"""The per-file exceptions report: structured JSON, and a short human summary.

Both carry row numbers, keys, field names, rule ids, reason categories and, for
a transform, the before and after of a non-personal field. Neither carries
``account_holder`` or ``advisor_email``, which no finding ever records.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .findings import Finding, RecordDecision
from .ingestion import FeedIngestionResult, FileOutcome, RecordResult
from .rules import VALIDATION_RULES, Severity
from .store import StoreOutcome

# Bumped whenever a consumer of the JSON would need to change how it reads it.
REPORT_FORMAT_VERSION = 1


def _finding_to_dictionary(finding: Finding) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id.value,
        "severity": finding.severity.value,
        "reason_category": finding.reason_category,
        "field": finding.field_name,
        "before": finding.value_before,
        "after": finding.value_after,
        "value_length": finding.value_length,
        "detail": finding.detail,
    }


def _record_to_dictionary(record_result: RecordResult) -> dict[str, Any]:
    validated_record = record_result.validated_record
    return {
        "row_number": validated_record.row_number,
        "source_row_id": validated_record.source_row_id,
        "decision": validated_record.decision.value,
        "store_outcome": None if record_result.store_outcome is None else record_result.store_outcome.value,
        "findings": [_finding_to_dictionary(finding) for finding in validated_record.findings],
    }


def _count_by_reason_category(ingestion_result: FeedIngestionResult) -> dict[str, int]:
    reason_category_counts = Counter(
        finding.reason_category
        for record_result in ingestion_result.record_results
        for finding in record_result.validated_record.findings
    )
    # Table order, so the report reads rejects, then warnings, then corrections.
    return {
        rule.reason_category: reason_category_counts[rule.reason_category]
        for rule in VALIDATION_RULES.values()
        if reason_category_counts[rule.reason_category]
    }


def build_structured_report(ingestion_result: FeedIngestionResult) -> dict[str, Any]:
    """Return the machine-readable report for one file, ready for ``json.dumps``."""
    decision_counts = Counter(
        record_result.validated_record.decision for record_result in ingestion_result.record_results
    )
    store_outcome_counts = Counter(
        record_result.store_outcome for record_result in ingestion_result.record_results
    )
    return {
        "report_format_version": REPORT_FORMAT_VERSION,
        "feed_file_name": ingestion_result.feed_file_name,
        "ingested_at": ingestion_result.ingested_at.isoformat(),
        "file_outcome": ingestion_result.file_outcome.value,
        "refusal_reason_category": ingestion_result.refusal_reason_category,
        "counts": {
            "rows_read": ingestion_result.rows_read,
            "by_decision": {
                record_decision.value: decision_counts[record_decision]
                for record_decision in RecordDecision
            },
            "by_reason_category": _count_by_reason_category(ingestion_result),
            "by_store_outcome": {
                store_outcome.value: store_outcome_counts[store_outcome]
                for store_outcome in StoreOutcome
            },
        },
        "records": [
            _record_to_dictionary(record_result) for record_result in ingestion_result.record_results
        ],
    }


def _describe_rejected_row(record_result: RecordResult) -> str:
    validated_record = record_result.validated_record
    row_label = validated_record.source_row_id or "(no source_row_id)"
    # The field, and the detail where there is one, tell the client which cell to
    # fix without the summary carrying the cell's value.
    reject_descriptions = ", ".join(
        f"{finding.rule_id.value} ({finding.field_name}"
        + (f": {finding.detail})" if finding.detail else ")")
        for finding in validated_record.findings
        if finding.severity is Severity.REJECT
    )
    return f"  row {validated_record.row_number} {row_label}: {reject_descriptions}"


def render_human_summary(ingestion_result: FeedIngestionResult) -> str:
    """Return a short plain-text summary suitable for the per-file email."""
    summary_lines = [
        f"Positions feed summary: {ingestion_result.feed_file_name}",
        f"Ingested at {ingestion_result.ingested_at.isoformat()}",
        f"File outcome: {ingestion_result.file_outcome.value}",
    ]
    if ingestion_result.file_outcome is not FileOutcome.PROCESSED:
        if ingestion_result.refusal_reason_category is not None:
            summary_lines.append(f"Reason: {ingestion_result.refusal_reason_category}")
        return "\n".join(summary_lines) + "\n"

    structured_report = build_structured_report(ingestion_result)
    decision_counts = structured_report["counts"]["by_decision"]
    store_outcome_counts = structured_report["counts"]["by_store_outcome"]
    landed_count = ingestion_result.rows_read - decision_counts["rejected"]
    summary_lines += [
        "",
        f"{ingestion_result.rows_read} rows read: {landed_count} landed, "
        f"{decision_counts['rejected']} rejected",
        f"  landed clean: {decision_counts['landed_clean']}, "
        f"with corrections: {decision_counts['landed_corrected']}, "
        f"flagged: {decision_counts['landed_flagged']}",
        f"  store: {store_outcome_counts['inserted']} new, "
        f"{store_outcome_counts['unchanged']} unchanged, "
        f"{store_outcome_counts['superseded']} superseded by this delivery",
        "",
        "Findings by rule:",
    ]
    reason_category_counts = structured_report["counts"]["by_reason_category"]
    for rule in VALIDATION_RULES.values():
        if rule.reason_category in reason_category_counts:
            summary_lines.append(
                f"  {rule.rule_id.value} {rule.reason_category}: "
                f"{reason_category_counts[rule.reason_category]}"
            )
    rejected_results = [
        record_result
        for record_result in ingestion_result.record_results
        if record_result.validated_record.decision is RecordDecision.REJECTED
    ]
    if rejected_results:
        summary_lines += ["", "Rejected rows:"]
        summary_lines += [_describe_rejected_row(record_result) for record_result in rejected_results]
    return "\n".join(summary_lines) + "\n"
