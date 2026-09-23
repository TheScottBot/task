# Positions Feed Onboarding: specification

A small ingestion and validation batch job for the Meridian Capital positions
feed, run on a schedule (see Execution model). Working specification for a
two-hour take-home, written to be built from top to bottom.

## Applying the datum

Applies `ENGINEERING_DATUM.md` version 2, dated 20 September 2026, by reference,
cherry-picked. The timebox makes the full stage machinery inappropriate, so this
spec states plainly what it takes and what it declines, per the datum's own
"applying this datum" section. It does not restate any datum rule; it references
by number.

Taken and honoured:

- 0.5 language idiom and verbose naming; 0.6 comments explain why, used
  sparingly. The code is the truth and cannot drift; a comment can. So a comment
  earns its place only where the why is not already legible from a descriptive
  name or the structure, and never restates what the code says.
- 0.7 one owner per rule: the field mapping and the validation table below are
  each expressed once and are the single source of truth the code reads from.
- 0.8 prose and typography: UK and Irish spelling, no em or en dashes, no
  quotation marks for emphasis. Applied to every artefact.
- 0.9 no placeholders in any command or the README.
- 0.10 untrusted input: the CSV crosses a trust boundary and is treated as
  hostile. Bounds from the contract not the input, reject rather than truncate,
  reject missing required fields and unknown columns, check every operation,
  surface every failure.
- 0.11 contracts: no silent default for a required field, no silent improvement.
  Every auto-correction is reported as an applied transformation, never hidden.
- 0.14 destructive and idempotent operations: re-ingest is idempotent and
  conflicts are resolved deliberately with an audit record.
- 0.15 observability: the report counts rejects by reason category; logs carry
  verb, reason category and length, never a payload or personal data.

Declined, with reason (recorded here in lieu of a fuller
`IMPLEMENTATION_DEVIATIONS.md`, which the submission includes in short form):

- Stage one Plan and `docs/evaluation/ACTUAL_CONTRACT_EVALUATION.md`: declined
  for the timebox. The mapping doc is the contract and is read directly. The
  `ftrio-python` reference is not declined: reading it in full before any code is
  a MUST (see Language and conventions).
- Strict red-green-refactor with each check first seen to fail on a planted
  violation (0.4): compressed to tests that prove each rule; noted as a
  deviation.
- The full CI suite (fuzz, sanitisers, warnings as errors across targets, the
  tree-wide prose scan): declined for the timebox. Fuzzing the CSV parser
  (0.10 guidance) is named as the first thing to add at real scale, which is the
  100k-row debrief point.
- Module A (memory-unsafe languages): not applied; see language choice.
- Module B (several products in one repo): not applicable, single deliverable.
- The identifier and tag ceremony: used lightly, only where it earns its place.

## Language and conventions

Python, fixed. It reaches a readable, tested solution fastest here, `Decimal`
gives correct money handling, and it keeps Module A out of scope. Core logic
uses the standard library only (csv, dataclasses, decimal, datetime, json),
matching ftrio-python's dependency-free core and datum 0.13.

Naming, structure, tests, configuration and continuous integration follow
`ftrio-python` as the reference implementation, per the datum's Reference
implementations section. This spec does not restate its conventions (datum
forbids restating a reference).

MUST, before writing any code: pull and read `https://github.com/FtrOnOff/ftrio-python`
in full. Confirm the repository exists at that exact path before cloning and
reproduce its casing exactly. Read it for type and function naming, test naming,
test double naming, configuration naming, comment style, error naming, repository
layout, deviation notes, test isolation and continuous integration checks, and
apply that style here. What transfers is the approach, not any single file's
syntax.

## Goal and non-goals

Goal: ingest `sample-positions-feed.csv`, map it to a canonical position model,
validate it into a structured report of every problem bucketed as reject, warn
or auto-correct, and make re-ingestion safe.

Non-goals, per the assignment ground rules: no auth, no UI, no deployment, no
server database. Behaviour at 100k rows is a debrief topic, not code.

## Execution model

The job is a script run on a schedule (cron), not a long-running service. It
starts, does one pass over the drop location, and exits. This shapes the design:

- State lives between runs in the file-backed SQLite store, not in process
  memory, because nothing stays resident.
- Outcome is signalled by exit code, since a scheduler reads the exit code, not
  stdout. Clean pass, or nothing to do, exits 0; a real failure exits non-zero so
  the scheduler's monitoring catches it.
- The three file states are handled deliberately and kept apart:
  - No file at the location: benign, expected on a schedule that fires whether or
    not a drop arrived. Do nothing, log one internal line (datum 0.15, absence is
    observable not silent), exit 0. No client exceptions report, they know they
    sent nothing.
  - File present but empty (zero data rows): treated as a probable source error,
    flagged, not silently passed.
  - File present but unreadable (corrupt, wrong encoding, not CSV, permissions):
    a real failure, loud, non-zero exit, logged with reason category and no
    payload. Never routed through the benign no-file path.

Debrief, not code: a schedule reading a file while SFTP is still writing it is
the classic race; the production version gates on an atomic rename or a `.done`
marker rather than the raw file appearing.

## Canonical position model

Money is parsed as `Decimal`, never float, because these are financial balances.
The model is the one place the shape is defined; the mapping and validation read
from it.

| Field | Type | Source column | Notes |
|---|---|---|---|
| `source_row_id` | string, required, non-empty | `source_row_id` | audit key, positions are keyed on it |
| `account_id` | string, required | `account_id` | not the client's name |
| `account_holder` | string, required | `account_holder` | display only, nothing keys off it, personal data |
| `fund_name` | string, required | `fund_name` | after share-class split and trim |
| `share_class` | string, optional | derived from `fund_name` | split from a `- Class X` suffix |
| `vintage_year` | integer year, required | `vintage_year` | sanity-bounded |
| `commitment` | Decimal, >= 0 | `commitment` | blank or non-numeric becomes 0 with a warning |
| `nav` | Decimal, >= 0 | `nav` | Closed positions must be 0 |
| `nav_date` | ISO date | `nav_date` | written-month format normalised; slash dates rejected until their convention is confirmed |
| `currency` | ISO 4217, upper | `currency` | almost always USD |
| `status` | enum Active or Closed | `status` | |
| `advisor_email` | email-shaped, required | `advisor_email` | notifications, personal data |

## Validation table (single source of truth)

Severity decides the record's fate: a reject does not land, a warn lands flagged,
an auto-correct lands with the transformation recorded. Each rule names the
sample row that exercises it, which is also the test set.

Reject (record does not land):

| id | condition | reason | sample |
|---|---|---|---|
| R1 | `source_row_id` blank | no audit key, cannot key the position | row with empty first column |
| R2 | `nav` < 0 | a NAV cannot be negative | src-1011 |
| R3 | `status` Closed and `nav` != 0 | mapping doc says flag not ingest, source bug | src-1015, src-1017 |
| R4 | `status` not Active or Closed | unknown state, per 0.11 not tolerated | defensive |
| R5 | a required field missing or unparseable: `account_id`, `account_holder`, `fund_name`, `vintage_year` (or outside its bounds), `nav`, `nav_date` (unrecognised format, or any slash date until its convention is confirmed), `currency` present but not three letters, `status` blank, `advisor_email`, `commitment` negative, `source_row_id` carrying surrounding whitespace, or a row with the wrong number of fields | incomplete record; no silent default for a required field, per 0.11 | defensive |
| R6 | `currency` blank | client confirmed reject not default; explicit data over silent default, per DEC-2 | src-1019 |

Warn (lands, flagged in the exceptions report):

| id | condition | action | sample |
|---|---|---|---|
| W1 | `commitment` blank or non-numeric | set 0, flag for source correction (commitment-free secondary) | src-1010 (N/A) |
| W3 | `currency` valid but not USD | land, confirm intentional, raises the FX question | src-1016 (EUR) |
| W4 | `nav_date` normalised from a non-ISO format | land, record the normalisation | src-1013, src-1023 |
| W5 | `fund_name` needed trimming | land, record the trim | src-1007 |

Auto-correct (lands, transformation reported, never silent per 0.11):

| id | condition | transform | sample |
|---|---|---|---|
| C1 | `currency` lower case | upper case | src-1009 (usd) |
| C2 | `fund_name` surrounding whitespace | trim | src-1007 |
| C3 | `nav_date` written-month format | to ISO 8601 | src-1013, src-1023 |
| C4 | `fund_name` carries a `- Class X` suffix | split into `fund_name` and `share_class` | src-1005, src-1010, src-1018 |

## Store, idempotency and conflict (0.14)

Store: file-backed SQLite via the standard library `sqlite3`, no server, no
external dependency. Chosen because the job runs on a schedule and must keep
state between runs (see Execution model); an in-memory store would lose it on
exit. Positions are keyed on `source_row_id` as the primary key.

Idempotency is a property of the logic, not the store: ingest looks up the key,
inserts when absent, no-ops when present and unchanged, and applies-with-audit
when present and changed. So re-running the cron on the same file, which happens,
converges to the same state. Durability across a restart comes from the file
being on disk. Unit tests run against an in-memory store because the logic, not
the store, provides the guarantee.

Two distinct mechanisms, not to be blurred:

- Within-file duplicate key (DEC-1, src-1007): a validation reject before the
  store. Both rows rejected and flagged. This is not a correction.
- Cross-file correction (same `source_row_id`, later delivery, changed value):
  an upsert that supersedes the stored row, last-delivery-wins per the mapping
  doc, writing an audit row (previous, new, reason, time). A legitimate update,
  not an error, and reported as its own category, never as a reject.

Commit per file (or per validated batch), so a crash mid-ingest rolls back
cleanly to the last good state rather than leaving half a night's positions.

## Report and observability (0.15)

Structured (JSON) for a machine, plus a short human summary. Per record:
`source_row_id`, decision, and each finding as rule id, severity, reason
category, field, and before and after for a transform. Per file: counts by
decision and by reason category. Logs and the structured report carry field
names, reason categories and lengths, not payloads; `account_holder` and
`advisor_email` are personal data and are minimised in anything emitted.

## Tests first (0.4, compressed)

One test per reject, warn and auto-correct rule, one for idempotent re-ingest,
one for the within-file conflict and one for a cross-file correction. Fixtures
are shared (0.7). Fixtures are synthetic or the provided fictional feed, never
real personal data (0.17 item 17).

## Client decisions (confirmed)

Both raised by email on 23 September 2026 and confirmed by Arseniy at Meridian
the same day, batched as a single clarification because they share one answer
(the per-file exceptions report). Neither is decided silently.

- DEC-1 within-file duplicate key (src-1007). Confirmed: reject both rows and
  flag them in the exceptions report. The client agreed file ordering is not to
  be relied on. Matches the interim behaviour; no change.
- DEC-2 blank currency (src-1019). Confirmed: flag and reject, not default. The
  client prefers explicit data over a silent default to keep the audit trail.
  This changed the interim behaviour, which was to land the record flagged;
  blank currency is now a reject (rule R6), not a warn.

Both feed the per-file exceptions report (requirement 4), so anything corrected
or rejected programmatically leaves a trail on both sides.

## Author decisions (settled, to defend)

- D3 EUR position: land and confirm, valid ISO 4217 but unusual, raises FX.
- D4 Closed with non-zero NAV: reject, the mapping doc instructs flag not ingest.

## Deliverables

- The cron-run script (a CLI entry point), `Decimal` money, file-backed SQLite
  store.
- `README.md`: how to run, and design decisions in ten bullets or fewer.
- This `SPEC.md`.
- A sample validation report (the exceptions report) produced from the feed.
- A short `IMPLEMENTATION_DEVIATIONS.md`: the datum declines above, with covering
  tests where they apply.
- The AI usage note (assignment Part 3).
- The email to Dana (assignment Part 2).
