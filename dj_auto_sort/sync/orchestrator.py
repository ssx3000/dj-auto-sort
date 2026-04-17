"""Fan out a canonical TrackRecord set to all enabled DJ-app adapters.

Also owns the backup-before-write safety helper.
Phase 5 implementation.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dj_auto_sort.adapters.base import LibraryAdapter
from dj_auto_sort.core.track_record import TrackRecord


def sync(
    tracks: Iterable[TrackRecord],
    adapters: list[tuple[LibraryAdapter, Path]],
    *,
    backup: bool = True,
) -> None:
    raise NotImplementedError("Phase 5")
