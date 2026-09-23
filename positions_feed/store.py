"""The file-backed SQLite position store, keyed on ``source_row_id``.

Idempotency is a property of ``upsert_position``, not of the database: it looks
the key up and inserts when absent, does nothing when present and unchanged, and
supersedes with an audit row when present and changed. The caller wraps a whole
file in ``transaction`` so a crash part way through leaves no partial night.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .model import Position, PositionStatus

CROSS_FILE_CORRECTION_REASON = "cross_file_correction"

# Money is stored as TEXT: SQLite's REAL is a binary float and would not keep a
# balance to the cent, which is the reason the model uses Decimal at all.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    source_row_id  TEXT PRIMARY KEY,
    account_id     TEXT NOT NULL,
    account_holder TEXT NOT NULL,
    fund_name      TEXT NOT NULL,
    share_class    TEXT,
    vintage_year   INTEGER NOT NULL,
    commitment     TEXT NOT NULL,
    nav            TEXT NOT NULL,
    nav_date       TEXT NOT NULL,
    currency       TEXT NOT NULL,
    status         TEXT NOT NULL,
    advisor_email  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS position_audit (
    audit_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_row_id     TEXT NOT NULL,
    previous_position TEXT NOT NULL,
    new_position      TEXT NOT NULL,
    reason            TEXT NOT NULL,
    recorded_at       TEXT NOT NULL,
    source_file_name  TEXT NOT NULL
);
"""

_POSITION_COLUMNS = (
    "source_row_id",
    "account_id",
    "account_holder",
    "fund_name",
    "share_class",
    "vintage_year",
    "commitment",
    "nav",
    "nav_date",
    "currency",
    "status",
    "advisor_email",
)


class StoreOutcome(Enum):
    """What storing a landed position did."""

    INSERTED = "inserted"
    UNCHANGED = "unchanged"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class AuditEntry:
    """A record of one position superseded by a later delivery."""

    source_row_id: str
    previous_position: Position
    new_position: Position
    reason: str
    recorded_at: datetime
    source_file_name: str


def _position_to_column_values(position: Position) -> dict[str, Any]:
    return {
        "source_row_id": position.source_row_id,
        "account_id": position.account_id,
        "account_holder": position.account_holder,
        "fund_name": position.fund_name,
        "share_class": position.share_class,
        "vintage_year": position.vintage_year,
        "commitment": str(position.commitment),
        "nav": str(position.nav),
        "nav_date": position.nav_date.isoformat(),
        "currency": position.currency,
        "status": position.status.value,
        "advisor_email": position.advisor_email,
    }


def _position_from_column_values(column_values: dict[str, Any]) -> Position:
    return Position(
        source_row_id=column_values["source_row_id"],
        account_id=column_values["account_id"],
        account_holder=column_values["account_holder"],
        fund_name=column_values["fund_name"],
        share_class=column_values["share_class"],
        vintage_year=int(column_values["vintage_year"]),
        commitment=Decimal(column_values["commitment"]),
        nav=Decimal(column_values["nav"]),
        nav_date=date.fromisoformat(column_values["nav_date"]),
        currency=column_values["currency"],
        status=PositionStatus(column_values["status"]),
        advisor_email=column_values["advisor_email"],
    )


class PositionStore:
    """Positions and their audit trail, in one SQLite database."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(_SCHEMA)

    @classmethod
    def open_file(cls, database_path: Path) -> PositionStore:
        """Open, creating if absent, the store that persists between scheduled runs."""
        return cls(sqlite3.connect(database_path))

    @classmethod
    def open_in_memory(cls) -> PositionStore:
        """Open a throwaway store; the logic under test is identical to the file's."""
        return cls(sqlite3.connect(":memory:"))

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit everything inside on success; roll all of it back on any exception."""
        with self._connection:
            yield

    def find_position(self, source_row_id: str) -> Position | None:
        stored_row = self._connection.execute(
            "SELECT * FROM positions WHERE source_row_id = ?", (source_row_id,)
        ).fetchone()
        return None if stored_row is None else _position_from_column_values(dict(stored_row))

    def upsert_position(
        self, position: Position, recorded_at: datetime, source_file_name: str
    ) -> StoreOutcome:
        """Insert, leave alone, or supersede with audit; never duplicate a key."""
        stored_position = self.find_position(position.source_row_id)
        if stored_position is None:
            column_values = _position_to_column_values(position)
            self._connection.execute(
                f"INSERT INTO positions ({', '.join(_POSITION_COLUMNS)}) "
                f"VALUES ({', '.join(':' + column for column in _POSITION_COLUMNS)})",
                column_values,
            )
            return StoreOutcome.INSERTED
        # Position equality compares Decimal values numerically, so a re-export
        # writing 2210800 where it once wrote 2210800.00 is not a correction.
        if stored_position == position:
            return StoreOutcome.UNCHANGED
        self._connection.execute(
            f"UPDATE positions SET {', '.join(column + ' = :' + column for column in _POSITION_COLUMNS)} "
            "WHERE source_row_id = :source_row_id",
            _position_to_column_values(position),
        )
        self._connection.execute(
            "INSERT INTO position_audit "
            "(source_row_id, previous_position, new_position, reason, recorded_at, source_file_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                position.source_row_id,
                json.dumps(_position_to_column_values(stored_position)),
                json.dumps(_position_to_column_values(position)),
                CROSS_FILE_CORRECTION_REASON,
                recorded_at.isoformat(),
                source_file_name,
            ),
        )
        return StoreOutcome.SUPERSEDED

    def count_positions(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0])

    def count_audit_entries(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM position_audit").fetchone()[0])

    def list_audit_entries(self, source_row_id: str) -> list[AuditEntry]:
        audit_rows = self._connection.execute(
            "SELECT * FROM position_audit WHERE source_row_id = ? ORDER BY audit_id",
            (source_row_id,),
        ).fetchall()
        return [
            AuditEntry(
                source_row_id=audit_row["source_row_id"],
                previous_position=_position_from_column_values(json.loads(audit_row["previous_position"])),
                new_position=_position_from_column_values(json.loads(audit_row["new_position"])),
                reason=audit_row["reason"],
                recorded_at=datetime.fromisoformat(audit_row["recorded_at"]),
                source_file_name=audit_row["source_file_name"],
            )
            for audit_row in audit_rows
        ]
