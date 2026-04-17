"""Render a target path for a TrackRecord from a configurable template.

Template tokens (resolved case-insensitively, missing tokens -> 'Unknown'):
  {genre} {artist} {album} {title} {bpm} {key} {energy}

Phase 4 implementation.
"""

from __future__ import annotations

from pathlib import Path

from dj_auto_sort.core.track_record import TrackRecord


def render_target_path(template: str, track: TrackRecord, root: Path) -> Path:
    raise NotImplementedError("Phase 4")
