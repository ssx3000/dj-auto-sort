"""Metadata cleanup: case normalization, junk-tag stripping, artist standardization.

Phase 4 implementation.
"""

from __future__ import annotations

from dj_auto_sort.core.track_record import TrackRecord


def clean(track: TrackRecord) -> TrackRecord:
    raise NotImplementedError("Phase 4")
