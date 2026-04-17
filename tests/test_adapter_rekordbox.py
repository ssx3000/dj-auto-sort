"""Round-trip tests for the Rekordbox XML adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from dj_auto_sort.adapters.rekordbox import RekordboxAdapter
from dj_auto_sort.core.track_record import CuePoint, TrackRecord


def _sample_tracks() -> list[TrackRecord]:
    return [
        TrackRecord(
            path=Path("C:/Music/House/artist - title.mp3"),
            title="Title One",
            artist="Artist One",
            album="Album",
            genre="House",
            bpm=128.0,
            key_camelot="8A",
            duration_ms=240000,
            cues=[
                CuePoint(index=0, position_ms=0, label="Intro"),
                CuePoint(index=1, position_ms=15500, label="Drop"),
            ],
        ),
        TrackRecord(
            path=Path("C:/Music/Techno/some - other track.mp3"),
            title="Title Two — Feat. Artist",
            artist="Artist Two",
            album="",
            genre="Techno",
            bpm=132.5,
            key_camelot="12B",
            duration_ms=360500,
        ),
    ]


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    adapter = RekordboxAdapter()
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
        assert r.bpm == pytest.approx(o.bpm)
        assert r.key_camelot == o.key_camelot
        # TotalTime is stored as whole seconds, so tolerate rounding.
        if o.duration_ms is not None:
            assert r.duration_ms is not None
            assert abs(r.duration_ms - o.duration_ms) < 1000
        assert len(r.cues) == len(o.cues)
        for oc, rc in zip(o.cues, r.cues, strict=True):
            assert rc.index == oc.index
            assert rc.label == oc.label
            assert abs(rc.position_ms - oc.position_ms) < 10


def test_written_xml_matches_rekordbox_shape(tmp_path: Path) -> None:
    adapter = RekordboxAdapter()
    adapter.write_library(tmp_path, _sample_tracks())

    xml_path = tmp_path / "rekordbox.xml"
    tree = etree.parse(str(xml_path))
    root = tree.getroot()
    assert root.tag == "DJ_PLAYLISTS"
    assert root.get("Version") == "1.0.0"

    product = root.find("PRODUCT")
    assert product is not None and product.get("Name") == "rekordbox"

    collection = root.find("COLLECTION")
    assert collection is not None
    assert collection.get("Entries") == "2"
    tracks = collection.findall("TRACK")
    assert len(tracks) == 2
    assert tracks[0].get("Location", "").startswith("file://localhost/C:/")


def test_cues_clamped_to_supported_count(tmp_path: Path) -> None:
    adapter = RekordboxAdapter()
    track = TrackRecord(
        path=Path("C:/Music/a.mp3"),
        cues=[CuePoint(index=i, position_ms=i * 1000) for i in range(12)],
    )
    adapter.write_library(tmp_path, [track])
    result = adapter.read_library(tmp_path)
    assert len(result[0].cues) == adapter.supported_cue_count


def test_validate_detects_missing_file(tmp_path: Path) -> None:
    adapter = RekordboxAdapter()
    issues = adapter.validate(tmp_path)
    assert issues
    assert "missing" in issues[0]


def test_validate_clean_after_write(tmp_path: Path) -> None:
    adapter = RekordboxAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    assert adapter.validate(tmp_path) == []


def test_unicode_and_special_chars_roundtrip(tmp_path: Path) -> None:
    adapter = RekordboxAdapter()
    track = TrackRecord(
        path=Path("C:/Music/Iñtërnâtiônàlizætiøn.mp3"),
        title="Café del Mar — ÜberMix™",
        artist="Björk & Sigur Rós",
        genre="Chill/Ambient",
        bpm=90.25,
    )
    adapter.write_library(tmp_path, [track])
    result = adapter.read_library(tmp_path)
    assert result[0].title == track.title
    assert result[0].artist == track.artist
    assert result[0].path == track.path
