"""The canonical position model: the one place a landed position's shape is defined."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class PositionStatus(Enum):
    """The two lifecycle states the client exports; anything else is refused (R4)."""

    ACTIVE = "Active"
    CLOSED = "Closed"


@dataclass(frozen=True)
class Position:
    """A validated LP position, keyed on the client's ``source_row_id``.

    Money is ``Decimal`` because these are financial balances and a float would
    not reconcile to the cent against the client's own statements.
    ``account_holder`` and ``advisor_email`` are personal data: they are stored
    but never emitted in a report or a log line.
    """

    source_row_id: str
    account_id: str
    account_holder: str
    fund_name: str
    share_class: str | None
    vintage_year: int
    commitment: Decimal
    nav: Decimal
    nav_date: date
    currency: str
    status: PositionStatus
    advisor_email: str
