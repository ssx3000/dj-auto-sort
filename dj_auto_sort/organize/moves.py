"""Atomic-ish file moves for the organize pipeline.

The organize step rearranges audio files on disk, which is the one place in
this project where a crash can lose user data. We take three precautions:

1. **Plan before touching disk.** ``plan_moves`` is a pure function that
   returns the full list of (src, dst) pairs. UI can show it, tests can
   assert on it, and callers can dry-run without side effects.

2. **Conflict detection.** The plan refuses to proceed if two sources would
   map to the same destination, or if the destination exists and isn't the
   source itself.

3. **Atomic-per-file rename.** ``execute_plan`` uses ``Path.replace`` within
   the same filesystem (atomic on POSIX and on Windows NTFS when the target
   doesn't exist). Cross-filesystem moves fall back to copy → fsync → rename
   into place → unlink source, which is as close to atomic as the stdlib
   offers. If any step fails mid-plan we stop and return partial results so
   the caller can inspect what moved.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.folder_tree import render_target_path


@dataclass(frozen=True)
class MovePlan:
    track: TrackRecord
    src: Path
    dst: Path

    @property
    def is_noop(self) -> bool:
        try:
            return self.src.resolve() == self.dst.resolve()
        except OSError:
            return self.src == self.dst


@dataclass(frozen=True)
class MoveResult:
    plan: MovePlan
    status: str  # "moved", "skipped-noop", "failed"
    error: str | None = None


class MovePlanConflict(ValueError):
    """Raised when two planned moves collide on the same destination."""


def plan_moves(tracks: list[TrackRecord], template: str, root: Path) -> list[MovePlan]:
    plans: list[MovePlan] = []
    seen_dst: dict[Path, MovePlan] = {}
    for t in tracks:
        dst = render_target_path(template, t, root)
        plan = MovePlan(track=t, src=t.path, dst=dst)
        if plan.is_noop:
            plans.append(plan)
            continue
        prior = seen_dst.get(dst)
        if prior is not None:
            raise MovePlanConflict(
                f"two tracks planned for the same destination {dst}: "
                f"{prior.src} and {t.path}"
            )
        seen_dst[dst] = plan
        plans.append(plan)
    return plans


def execute_plan(plans: list[MovePlan], *, dry_run: bool = False) -> list[MoveResult]:
    """Run ``plans`` in order. Stops at the first failure and returns what happened."""
    results: list[MoveResult] = []
    for plan in plans:
        if plan.is_noop:
            results.append(MoveResult(plan=plan, status="skipped-noop"))
            continue
        if dry_run:
            results.append(MoveResult(plan=plan, status="moved"))
            continue
        try:
            _move_one(plan.src, plan.dst)
        except OSError as exc:
            results.append(MoveResult(plan=plan, status="failed", error=str(exc)))
            return results
        results.append(MoveResult(plan=plan, status="moved"))
    return results


def _move_one(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    if dst.exists():
        if dst.resolve() == src.resolve():
            return
        raise FileExistsError(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Path.replace is atomic within a filesystem on both POSIX and Windows
    # (when the target does not exist). If the move crosses filesystems we
    # get EXDEV and fall through to the copy-then-rename path.
    try:
        src.replace(dst)
        return
    except OSError as exc:
        if getattr(exc, "errno", None) not in {18}:  # EXDEV
            raise

    _copy_fsync_rename(src, dst)


def _copy_fsync_rename(src: Path, dst: Path) -> None:
    """Cross-device atomic-ish move: copy → fsync → rename into place → unlink src."""
    tmp = dst.with_name(dst.name + ".dj-auto-sort-tmp")
    try:
        shutil.copy2(src, tmp)
        with tmp.open("rb") as fh:
            os.fsync(fh.fileno())
        tmp.replace(dst)
    except OSError:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise
    # Destination is written; leaving the source as an orphan is a recoverable
    # state (library will see a duplicate next scan) rather than data loss, so
    # we don't re-raise if the source unlink fails.
    with contextlib.suppress(OSError):
        src.unlink()
