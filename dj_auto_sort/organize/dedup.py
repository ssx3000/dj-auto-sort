"""Duplicate detection. Filesize+duration heuristic + optional chromaprint.

Phase 4 implementation.
"""

from __future__ import annotations

from dj_auto_sort.core.track_record import TrackRecord


def find_duplicates(tracks: list[TrackRecord]) -> list[list[TrackRecord]]:
    """Group tracks into duplicate clusters (each cluster has >= 2 tracks)."""
    raise NotImplementedError("Phase 4")
