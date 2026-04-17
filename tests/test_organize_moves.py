"""Atomic move planner + executor tests.

The safety properties we care about:
  * Planning is pure: it produces a deterministic list without touching disk.
  * Execution never drops data mid-move (src vanishes only after dst exists).
  * Collisions are detected before a single file is touched.
  * Dry-run produces the same plan as a real run without touching disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.moves import (
    MovePlanConflict,
    execute_plan,
    plan_moves,
)


def _seed(tmp_path: Path, rel: str, payload: bytes = b"audio-bytes") -> Path:
    p = tmp_path / "src" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(payload)
    return p


def _track(path: Path, **overrides) -> TrackRecord:
    defaults = {
        "title": "Title",
        "artist": "Artist",
        "genre": "House",
    }
    defaults.update(overrides)
    return TrackRecord(path=path, **defaults)


def test_plan_is_pure_no_disk_changes(tmp_path: Path) -> None:
    src = _seed(tmp_path, "a.mp3")
    dst_root = tmp_path / "out"
    assert not dst_root.exists()
    plans = plan_moves([_track(src)], "{genre}/{artist} - {title}", dst_root)
    assert len(plans) == 1
    assert plans[0].src == src
    assert plans[0].dst == dst_root / "House" / "Artist - Title.mp3"
    # No side effects from planning.
    assert not dst_root.exists()
    assert src.exists()


def test_execute_moves_file_atomically(tmp_path: Path) -> None:
    src = _seed(tmp_path, "a.mp3", payload=b"XYZ")
    dst_root = tmp_path / "out"
    plans = plan_moves([_track(src)], "{genre}/{title}", dst_root)
    results = execute_plan(plans)

    assert len(results) == 1
    assert results[0].status == "moved"
    assert not src.exists()
    expected_dst = dst_root / "House" / "Title.mp3"
    assert expected_dst.read_bytes() == b"XYZ"


def test_dry_run_touches_nothing(tmp_path: Path) -> None:
    src = _seed(tmp_path, "a.mp3")
    dst_root = tmp_path / "out"
    plans = plan_moves([_track(src)], "{title}", dst_root)
    results = execute_plan(plans, dry_run=True)

    assert [r.status for r in results] == ["moved"]
    assert src.exists()
    assert not dst_root.exists()


def test_conflicting_destinations_raise_before_any_move(tmp_path: Path) -> None:
    a = _seed(tmp_path, "a.mp3", payload=b"A")
    b = _seed(tmp_path, "b.mp3", payload=b"B")
    # Both tracks share title+genre → same rendered dst.
    tracks = [_track(a), _track(b)]
    with pytest.raises(MovePlanConflict):
        plan_moves(tracks, "{genre}/{title}", tmp_path / "out")
    # Both originals still there; nothing partial.
    assert a.exists() and b.exists()


def test_noop_when_src_equals_dst(tmp_path: Path) -> None:
    # Put the file where the template would render it, so move is a no-op.
    dst_root = tmp_path / "library"
    final = dst_root / "House" / "Title.mp3"
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"ok")
    plans = plan_moves([_track(final)], "{genre}/{title}", dst_root)
    results = execute_plan(plans)

    assert [r.status for r in results] == ["skipped-noop"]
    assert final.read_bytes() == b"ok"


def test_execute_stops_at_first_failure_and_reports(tmp_path: Path) -> None:
    # First move is fine, second collides with a pre-existing unrelated file.
    a = _seed(tmp_path, "a.mp3", payload=b"A")
    b = _seed(tmp_path, "b.mp3", payload=b"B")
    dst_root = tmp_path / "out"

    # Pre-create the exact destination the second track wants, with a
    # different body, so execute hits FileExistsError.
    squatter_dir = dst_root / "House"
    squatter_dir.mkdir(parents=True)
    (squatter_dir / "B.mp3").write_bytes(b"someone-else")

    tracks = [
        _track(a, title="A"),
        _track(b, title="B"),
    ]
    plans = plan_moves(tracks, "{genre}/{title}", dst_root)
    results = execute_plan(plans)

    # First move succeeded; second failed; execution stopped.
    assert len(results) == 2
    assert results[0].status == "moved"
    assert results[1].status == "failed"
    # The successful move fully completed — src gone, dst in place.
    assert not a.exists()
    assert (dst_root / "House" / "A.mp3").read_bytes() == b"A"
    # The pre-existing file at the failure destination was preserved.
    assert (dst_root / "House" / "B.mp3").read_bytes() == b"someone-else"
    # And the second source is untouched, so no data was lost.
    assert b.read_bytes() == b"B"


def test_missing_source_reports_failure_without_crashing(tmp_path: Path) -> None:
    ghost = tmp_path / "src" / "does-not-exist.mp3"
    # Build a plan manually so we bypass the "file must exist" implicit assumption.
    track = _track(ghost)
    plans = plan_moves([track], "{title}", tmp_path / "out")
    results = execute_plan(plans)
    assert results[0].status == "failed"
    assert "does-not-exist.mp3" in (results[0].error or "")
