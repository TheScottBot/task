"""Ingestion and validation batch job for the Meridian Capital positions feed.

Reads one delivered CSV, validates every row against the table in SPEC.md, lands
what passes in a file-backed SQLite store keyed on ``source_row_id``, and writes
a per-file exceptions report. The core depends on the standard library only.
"""

from __future__ import annotations

import logging

# Library code attaches a NullHandler so it is silent unless the host (here the
# CLI) configures logging, leaving level and destination to the operator.
logging.getLogger(__name__).addHandler(logging.NullHandler())
