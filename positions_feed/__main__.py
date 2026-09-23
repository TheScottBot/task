"""Allows ``python -m positions_feed``."""

from __future__ import annotations

import sys

from .cli import main

sys.exit(main())
