"""PreviewView tests — render a SyncReport and clear it."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.dedup import DuplicateGroup
from dj_auto_sort.organize.moves import MovePlan, MoveResult
from dj_auto_sort.sync.orchestrator import SyncReport
from dj_auto_sort.ui.preview_view import PreviewView


def _make_report() -> SyncReport:
    t1 = TrackRecord(path=Path("/music/a.mp3"), title="A")
    t2 = TrackRecord(path=Path("/music/dupe/a.mp3"), title="A")
    plan = MovePlan(track=t1, src=Path("/music/a.mp3"), dst=Path("/library/House/A.mp3"))
    return SyncReport(
        tracks_read=2,
        tracks_analyzed=1,
        tracks_written={"rekordbox": 2, "serato": 2},
        backups=[Path("/rb/rekordbox.xml.bak-20260417-000000")],
        move_results=[MoveResult(plan=plan, status="moved")],
        duplicate_groups=[DuplicateGroup(tracks=(t1, t2), keeper=t1)],
        errors=["read serato @ /ser: missing file"],
    )


def test_counts_line_summarizes_report(qtbot) -> None:
    view = PreviewView()
    qtbot.addWidget(view)
    view.show_report(_make_report())
    text = view.counts_text()
    assert "Read 2" in text
    assert "Analyzed 1" in text
    assert "Wrote 4" in text
    assert "rekordbox=2" in text
    assert "serato=2" in text


def test_move_rows_populated(qtbot) -> None:
    view = PreviewView()
    qtbot.addWidget(view)
    view.show_report(_make_report())
    rows = view.move_rows()
    assert len(rows) == 1
    status, src, dst = rows[0]
    assert status == "moved"
    assert src.endswith("a.mp3")
    assert dst.endswith("A.mp3")


def test_duplicates_and_errors_populated(qtbot) -> None:
    view = PreviewView()
    qtbot.addWidget(view)
    view.show_report(_make_report())
    assert view.duplicate_group_count() == 1
    assert "missing file" in view.errors_text()


def test_clear_resets_view(qtbot) -> None:
    view = PreviewView()
    qtbot.addWidget(view)
    view.show_report(_make_report())
    view.clear()
    assert view.move_rows() == []
    assert view.duplicate_group_count() == 0
    assert view.errors_text() == ""
    assert "No run yet" in view.counts_text()


def test_empty_report_renders_without_crashing(qtbot) -> None:
    view = PreviewView()
    qtbot.addWidget(view)
    view.show_report(SyncReport())
    assert view.move_rows() == []
    assert view.duplicate_group_count() == 0
    assert view.errors_text() == ""
