"""Round-trip tests for the Virtual DJ XML adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from dj_auto_sort.adapters.virtualdj import VirtualDJAdapter
from dj_auto_sort.core.track_record import CuePoint, TrackRecord


def _sample_tracks() -> list[TrackRecord]:
    return [
        TrackRecord(
            path=Path(r"C:\Music\House\artist - title.mp3"),
            title="Title One",
            artist="Artist One",
            album="Album",
            genre="House",
            bpm=128.0,
            key_camelot="8A",
            duration_ms=240000,
            cues=[
                CuePoint(index=0, position_ms=0, label=""),
                CuePoint(index=1, position_ms=15500, label="Drop"),
                CuePoint(index=2, position_ms=45000, label="Break"),
            ],
        ),
        TrackRecord(
            path=Path(r"C:\Music\DnB\another.flac"),
            title="Neurofunk Roller",
            artist="Producer",
            genre="Drum & Bass",
            bpm=174.0,
            key_camelot="5A",
            duration_ms=300000,
        ),
    ]


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    adapter = VirtualDJAdapter()
    original = _sample_tracks()
    adapter.write_library(tmp_path, original)
    roundtripped = adapter.read_library(tmp_path)

    assert len(roundtripped) == len(original)
    for o, r in zip(original, roundtripped, strict=True):
        assert r.path == o.path
        assert r.title == o.title
        assert r.artist == o.artist
        assert r.album == o.album
        assert r.genre == o.genre
        assert r.bpm == pytest.approx(o.bpm, abs=1e-4)
        assert r.key_camelot == o.key_camelot
        if o.duration_ms is not None:
            assert r.duration_ms == pytest.approx(o.duration_ms, abs=20)
        assert len(r.cues) == len(o.cues)
        for oc, rc in zip(o.cues, r.cues, strict=True):
            assert rc.index == oc.index
            assert rc.label == oc.label


def test_bpm_is_stored_as_seconds_per_beat(tmp_path: Path) -> None:
    adapter = VirtualDJAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    tree = etree.parse(str(tmp_path / "database.xml"))
    tags_el = tree.find(".//Song/Tags")
    assert tags_el is not None
    # 60 / 128 ≈ 0.46875
    assert pytest.approx(float(tags_el.get("Bpm")), abs=1e-6) == 60.0 / 128.0


def test_cues_clamped_to_supported_count(tmp_path: Path) -> None:
    adapter = VirtualDJAdapter()
    track = TrackRecord(
        path=Path(r"C:\Music\a.mp3"),
        cues=[CuePoint(index=i, position_ms=i * 1000) for i in range(24)],
    )
    adapter.write_library(tmp_path, [track])
    result = adapter.read_library(tmp_path)
    assert len(result[0].cues) == adapter.supported_cue_count  # 16


def test_validate_detects_missing(tmp_path: Path) -> None:
    adapter = VirtualDJAdapter()
    issues = adapter.validate(tmp_path)
    assert issues and "missing" in issues[0]


def test_validate_clean_after_write(tmp_path: Path) -> None:
    adapter = VirtualDJAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    assert adapter.validate(tmp_path) == []


def test_root_element_shape(tmp_path: Path) -> None:
    adapter = VirtualDJAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    tree = etree.parse(str(tmp_path / "database.xml"))
    root = tree.getroot()
    assert root.tag == "VirtualDJ_Database"
    assert len(root.findall("Song")) == 2
