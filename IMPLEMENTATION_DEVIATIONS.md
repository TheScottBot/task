# Implementation deviations

Every departure from `ENGINEERING_DATUM.md` version 2 and from `SPEC.md`, with
what was done instead, why, the author's decision and the covering test. The
declines were set by the author in `SPEC.md` for the two-hour timebox.

## From the datum

| rule | done instead | why | author's decision | covering test |
|---|---|---|---|---|
| Stage one Plan, `docs/evaluation/ACTUAL_CONTRACT_EVALUATION.md` | The evaluation record below, in short form. | Timebox. | Declined in `SPEC.md`. | none |
| 0.4 red, green, refactor per behaviour; each check first seen to fail on a planted violation | The suite was written before the package existed and seen to fail on import. Four reader tests added mid-build were seen to fail before the change they cover. Eleven checks were then proven against planted faults in a scratch copy: slash dates read month first, slash dates reported as unrecognised rather than unconfirmed, ASCII-only digits in the ISO and slash shapes, ISO not treated as a normalisation, month case-insensitivity, within-file duplicates, transaction rollback, blank currency, Closed with NAV, field bound. All eleven were caught. The date policy change of 23 September 2026 was driven the same way: tests changed first and seen to fail, then the code. | Timebox. | Compressed in `SPEC.md`. | the whole suite |
| 0.10 field length bounded before parsing | The file size is bounded before a byte is decoded; field lengths are checked after `csv` tokenises a row and before any value is interpreted or stored. | The standard `csv` field limit is process-global state; the file bound already caps what the tokeniser can hold. | Author to confirm. | `test_field_longer_than_bound_is_refused` |
| Part 2 `TESTING.md`, `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, `PRIVACY.md` | Test commands are in `README.md`; the trust boundary and personal data handling are summarised there. | Timebox and deliverable list in `SPEC.md`. | Not in the `SPEC.md` deliverables. | none |

## From the spec

| item | done instead | why | covering test |
|---|---|---|---|
| Model: `currency` is ISO 4217 | Shape check only: three letters, upper-cased. A well-formed code that does not exist, such as `XYZ`, would land and, not being USD, be flagged W3. | No code list in the standard library (0.13). W3 makes such a value visible rather than silent. | `test_w3_non_usd_currency_lands_flagged` |
| Validation table: the single source of truth the code reads from | The code's rules table carries two warn rules the spec's table does not, W6 and W7 (`DECISIONS.md` D13, D14). | The author chose to record them in `DECISIONS.md` rather than change `SPEC.md`. | `test_rule_severity_matches_the_specification`, `test_w6_...`, `test_w7_...` |
| Execution model: a partly written SFTP file | Not handled in code. | A debrief topic in `SPEC.md`: gate on an atomic rename or a `.done` marker. | none |

## Evaluation record (short form of Stage one)

Read on 23 September 2026.

| item | source | version |
|---|---|---|
| Engineering datum | `AdditionalReferences/ENGINEERING_DATUM.md` | version 2, 20 September 2026 |
| Reference implementation | `https://github.com/FtrOnOff/ftrio-python`, confirmed to exist at that path | commit `b95ec4e1feaf1b3c74a30a43edd5e03c90f7ad68`, 8 July 2026 |
| Assignment, mapping notes, sample feed | `https://github.com/tangiblemarkets/fde-assignment`, copied verbatim into `AdditionalReferences/` | commit `ebdbb6c7fbf880a0cc7ae8a2f355c670f764b570`, 17 August 2026 |
| Toolchain | CPython on Windows 11 (arm64) | Python 3.14.7, pytest 9.1.1, ruff 0.16.8, mypy 2.3.1 |

Taken from ftrio-python: package layout with `tests/unit` and `tests/integration`,
shared fixtures and test doubles in `tests/conftest.py`, descriptive
`test_<behaviour>` names, `*Error` exception naming, a standard-library-only core
with a `NullHandler` on the package logger, why-first docstrings, `pyproject.toml`
with the same ruff rule set, and a CI job running ruff, mypy and pytest across
supported Python versions.
