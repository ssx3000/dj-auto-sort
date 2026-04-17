"""Duplicate detection for a library of TrackRecords.

Two-stage matching, cheapest-first so we never hash a file unless we have to:

1. **Size + duration bucket.** Any pair that shares an exact file size *and*
   a duration within ``duration_tolerance_ms`` is a candidate. This catches
   the 95% case where the same file was ripped once and then copied into
   multiple library folders.

2. **Tie-break by hash.** Inside each size+duration bucket we blake2b the
   file contents to distinguish near-matches (same size, different bytes —
   can happen with identical-length tracks at the same bitrate).

The normalized title/artist pair is *not* used as a dedup key here: two
different masters of the same song are legitimately different tracks and
should not collapse. Callers that want title-based clustering should do it
at a higher level.

If ``TrackRecord.path`` is missing from disk, that track is skipped (not
raised) so a partially-indexed library doesn't crash dedup.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from dj_auto_sort.core.track_record import TrackRecord


@dataclass(frozen=True)
class DuplicateGroup:
    tracks: tuple[TrackRecord, ...]
    keeper: TrackRecord  # the track we'd keep if resolving automatically

    @property
    def redundant(self) -> tuple[TrackRecord, ...]:
        return tuple(t for t in self.tracks if t is not self.keeper)


def find_duplicates(
    tracks: list[TrackRecord],
    *,
    duration_tolerance_ms: int = 500,
) -> list[DuplicateGroup]:
    """Return clusters of duplicates (each group has >= 2 tracks)."""
    by_size_duration: dict[tuple[int, int], list[TrackRecord]] = defaultdict(list)
    for t in tracks:
        if not t.path.exists():
            continue
        try:
            size = t.path.stat().st_size
        except OSError:
            continue
        # Bucket duration in ``duration_tolerance_ms`` slots so tracks near a
        # bucket boundary only match within one slot. Good enough for the
        # "same rip, different folder" case; fuzzy matching is out of scope.
        bucket = (t.duration_ms or 0) // max(1, duration_tolerance_ms)
        by_size_duration[(size, bucket)].append(t)

    groups: list[DuplicateGroup] = []
    for cluster in by_size_duration.values():
        if len(cluster) < 2:
            continue
        for hash_cluster in _cluster_by_content_hash(cluster):
            if len(hash_cluster) < 2:
                continue
            keeper = _pick_keeper(hash_cluster)
            groups.append(DuplicateGroup(tracks=tuple(hash_cluster), keeper=keeper))
    return groups


def _cluster_by_content_hash(tracks: list[TrackRecord]) -> list[list[TrackRecord]]:
    by_hash: dict[str, list[TrackRecord]] = defaultdict(list)
    for t in tracks:
        digest = _file_digest(t.path)
        if digest is None:
            continue
        by_hash[digest].append(t)
    return list(by_hash.values())


def _file_digest(path: Path, *, chunk_size: int = 1 << 20) -> str | None:
    h = hashlib.blake2b(digest_size=16)
    try:
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _pick_keeper(cluster: list[TrackRecord]) -> TrackRecord:
    """Keep the track with the richest metadata, falling back to shortest path.

    Scoring rewards filled-in analysis fields and tag text. Ties (same score)
    break toward the shortest path, which is usually the canonical copy
    rather than a ``/downloads/backup_2024_copy`` offshoot.
    """

    def score(t: TrackRecord) -> tuple[int, int]:
        filled = sum(
            1
            for v in (
                t.title,
                t.artist,
                t.album,
                t.genre,
                t.bpm,
                t.key_camelot,
                t.energy,
            )
            if v
        )
        return (filled, -len(str(t.path)))

    return max(cluster, key=score)
