# Positions feed onboarding

A scheduled batch job that ingests Meridian Capital's nightly positions CSV,
validates every row into a structured exceptions report (reject, warn or
auto-correct), and lands what passes in a file-backed SQLite store keyed on the
client's `source_row_id`. Re-running it on the same file changes nothing.

Built against [SPEC.md](SPEC.md), which applies the engineering datum in
`additional_references`. The assignment, the client's field
notes and the sample feed are in `additional_references`, copied verbatim from
`https://github.com/tangiblemarkets/fde-assignment`. The core uses the standard
library only.

## Running it

Python 3.11 or later. A run archives the file it processed, so copy the sample
into a drop folder first rather than pointing the job at `additional_references`.
From the repository root, on Windows (PowerShell):

```console
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
New-Item -ItemType Directory -Force incoming
Copy-Item additional_references\sample-positions-feed.csv incoming\
.venv\Scripts\python -m positions_feed --feed-path incoming\sample-positions-feed.csv --database-path positions.sqlite3
```

On Linux or macOS:

```console
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
mkdir -p incoming
cp additional_references/sample-positions-feed.csv incoming/
.venv/bin/python -m positions_feed --feed-path incoming/sample-positions-feed.csv --database-path positions.sqlite3
```

It prints the summary, logs one line per step to stderr, and leaves three files in
`incoming/archive/`, all named with the UTC time the feed was processed. A run at
06:00 on 23 September 2026 leaves:

```text
sample-positions-feed.20260923T060000Z.csv          the feed, moved out of the drop folder
sample-positions-feed.20260923T060000Z.report.json  the structured report, for a machine
sample-positions-feed.20260923T060000Z.summary.txt  the summary, for the per-file email
```

So each night's file sits beside the reports on it, and no night's report replaces
another's. Nothing is ever overwritten: a second file processed in the same second
gets `-2` added to all three names, and so on. The sample report from the provided
feed is in [reports/](reports/). Copy the sample in and run it again and every
landed position reports `unchanged`.

Two optional arguments move things elsewhere: `--archive-directory` for the
processed feed (and, by default, its reports), for example longer-term storage;
`--report-directory` for the reports alone.

Exit codes, for the scheduler: `0` clean pass, no file dropped, or a file processed
with rejected rows (those are data problems, carried by the report); `1` a
refused file (unreadable, not UTF-8, not CSV, wrong header, over a bound), a store
failure, a report or archive that could not be written, or a mistyped command
(a missing or unknown argument); `2` an empty file, and only that.

## Proposed setup: a scheduled job

The design assumes one thing about how this runs: a job that cron starts, which
makes one pass over a drop folder and exits. It holds no state in memory between
runs; everything that must survive lives in the SQLite file, and the outcome is
the exit code, which is what a scheduler watches.

Proposed layout on the host, with the repository checked out and installed into
its own virtual environment under `app`:

```text
/srv/positions-feed/app/                        this repository, with .venv
/srv/positions-feed/incoming/positions-feed.csv the drop location
/srv/positions-feed/incoming/archive/           each processed feed with its reports
/srv/positions-feed/state/positions.sqlite3     the position store
/srv/positions-feed/logs/positions-feed.log     the job's log lines
```

The crontab entry, run nightly at 06:00 (the time to be agreed with Meridian so it
falls after their export has landed):

```text
0 6 * * * /srv/positions-feed/app/.venv/bin/positions-feed --feed-path /srv/positions-feed/incoming/positions-feed.csv --database-path /srv/positions-feed/state/positions.sqlite3 >> /srv/positions-feed/logs/positions-feed.log 2>&1
```

**Stage one: manual handoff around an automated run.** This is the shape to start
with.

1. Receive the nightly CSV from Meridian and place it in the drop location as
   `positions-feed.csv`.
2. Wait for the scheduled run. No file is not an error: the job logs one line and
   exits 0, so the schedule can fire every night whether or not a file arrived.
3. Check the outcome. Exit 0 means the file was processed, rejected rows included;
   1 means the file was refused whole, the store failed, a report or archive
   could not be written, or the command itself was wrong; 2 means the file was empty. The log line names the
   reason category.
4. Email that night's `.summary.txt` from `incoming/archive/` back to Meridian as
   the exceptions handoff (their requirement 4), attaching the `.report.json` if
   they want the detail.

The job writes the reports and then archives the file itself, processed, empty or
refused alike, so the drop location is empty for the next night. A file is left
in place only when the store failed (nothing was ingested, so the next run
retries) or its report or archive could not be written (re-ingesting it changes
nothing).

**Stage two: automate both ends.** The job itself does not change; only what
surrounds it.

- **Ingest:** Meridian drops to SFTP, writing to a temporary name and renaming on
  completion (or writing a `.done` marker), so a file still arriving is never read
  part way through. `--archive-directory` points the archive at long-term storage,
  and `--report-directory` can send reports wherever the handoff picks them up.
- **Handoff:** the summary is emailed automatically after each run, and later sent
  to a webhook, as Meridian proposed. A non-zero exit alerts us rather than them.

## Tests

```console
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check positions_feed tests
.venv\Scripts\mypy
```

Every rule in the validation table has its own tests, and
`tests/integration/test_sample_feed.py` pins the exact decision and findings for
each of the 25 sample rows. CI runs the same three commands on Python 3.11 to 3.14.

## Design decisions

1. **Severity decides fate, from one table.** `positions_feed/rules.py` is the
   validation table in `SPEC.md`; a reject never lands, a warn lands flagged, an
   auto-correct lands with its before and after recorded. Nothing is changed silently.
2. **Every problem on a row is reported,** not just the first, so the client can fix
   a row in one pass rather than one problem per night.
3. **Two conflict mechanisms, kept apart.** A key repeated within one file rejects
   every row carrying it (DEC-1: file order is not relied on). The same key in a
   later file with changed values supersedes the stored row and writes an audit row
   (previous, new, reason, time, file), reported as `superseded`, never as a reject.
4. **Idempotency lives in the logic.** Look up, then insert, no-op or supersede.
   Values compare numerically, so `2210800.00` against `2210800` is not a change.
5. **One transaction per file.** A crash part way through rolls the whole file back.
6. **Money is `Decimal`,** stored as text, never a float, so balances reconcile to the cent.
7. **The file is hostile until proven otherwise.** Size, row count and field length
   are bounded from the contract (`positions_feed/contract.py`); the header must
   match exactly; anything structural refuses the whole file rather than reading
   around it. Absent, empty and refused files are three different outcomes.
8. **Dates are refused rather than guessed.** A written month (`31-Mar-2026`) is
   normalised to ISO. A slash date (`03/31/2026`) is rejected and flagged until the
   client confirms whether it is month first or day first. The policy is one table in
   `positions_feed/nav_dates.py`.
9. **Personal data stays in the store.** `account_holder` and `advisor_email` never
   appear in a report or a log line; a reject records a field's length, not its value.
10. **Keys are never trimmed.** A padded `source_row_id` is rejected, since trimming
    it could silently merge or split positions across deliveries.

Decisions made during the build are in [DECISIONS.md](DECISIONS.md); departures
from the datum are in [IMPLEMENTATION_DEVIATIONS.md](IMPLEMENTATION_DEVIATIONS.md).

## At 100k rows (debrief notes)

- Stream rows and batch the store writes (one transaction per file still holds);
  add an index-backed bulk lookup rather than one `SELECT` per row.
- Gate on an atomic rename or a `.done` marker so a file still arriving over SFTP is
  never read part way through.
- Fuzz the CSV reader in CI, the first check to add at real scale.
- Record a digest per delivered file so an identical re-send can short-circuit.
