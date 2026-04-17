"""Local SQLite cache of analysis results keyed by (path, mtime, size).

Lets the app skip re-analysis of unchanged tracks. Phase 2 fleshes this out.
"""

from __future__ import annotations

from pathlib import Path


class AnalysisStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # Phase 2: init_schema, get(track_key), put(track_record), invalidate(path)
