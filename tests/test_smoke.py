"""Phase 1 smoke tests — verify the package imports and the canonical model works."""

from __future__ import annotations

from pathlib import Path

import dj_auto_sort
from dj_auto_sort.core.track_record import CuePoint, TrackRecord


def test_package_version():
    assert dj_auto_sort.__version__


def test_track_record_defaults():
    t = TrackRecord(path=Path("song.mp3"))
    assert t.path == Path("song.mp3")
    assert t.bpm is None
    assert t.cues == []
    assert t.source_libraries == set()


def test_track_record_with_analysis_is_immutable_copy():
    t = TrackRecord(path=Path("song.mp3"))
    t2 = t.with_analysis(bpm=128.0, key_camelot="8A", energy=7, analyzed_with="essentia")
    assert t.bpm is None  # original untouched
    assert t2.bpm == 128.0
    assert t2.key_camelot == "8A"
    assert t2.energy == 7
    assert t2.analyzed_with == "essentia"


def test_cue_point_is_hashable_frozen():
    cue = CuePoint(index=0, position_ms=1500, label="intro", color_rgb=(255, 0, 0))
    assert hash(cue)  # frozen dataclass should be hashable


def test_adapters_declare_cue_counts():
    from dj_auto_sort.adapters.rekordbox import RekordboxAdapter
    from dj_auto_sort.adapters.serato import SeratoAdapter
    from dj_auto_sort.adapters.virtualdj import VirtualDJAdapter

    assert RekordboxAdapter().supported_cue_count == 8
    assert SeratoAdapter().supported_cue_count == 8
    assert VirtualDJAdapter().supported_cue_count == 16
