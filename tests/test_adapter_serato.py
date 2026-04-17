"""Round-trip tests for the Serato binary database adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_auto_sort.adapters.serato import (
    DATABASE_FILE,
    SERATO_DIR,
    SeratoAdapter,
    _read_chunks,
)
from dj_auto_sort.core.track_record import TrackRecord


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
        ),
        TrackRecord(
            path=Path(r"C:\Music\Hip-Hop\classic.flac"),
            title="Classic Cut",
            artist="MC",
            genre="Hip-Hop",
            bpm=92.5,
            key_camelot="4A",
            duration_ms=215000,
        ),
    ]


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    adapter = SeratoAdapter()
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
        assert r.bpm == pytest.approx(o.bpm, abs=0.01)
        assert r.key_camelot == o.key_camelot
        # ttim is "mm:ss" — whole-second precision only.
        if o.duration_ms is not None:
            assert r.duration_ms is not None
            assert abs(r.duration_ms - o.duration_ms) < 1000


def test_database_has_version_header(tmp_path: Path) -> None:
    adapter = SeratoAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    db_path = tmp_path / SERATO_DIR / DATABASE_FILE
    assert db_path.exists()
    chunks = _read_chunks(db_path.read_bytes())
    assert chunks[0][0] == "vrsn"
    # One otrk per track
    otrk_chunks = [tag for tag, _ in chunks if tag == "otrk"]
    assert len(otrk_chunks) == 2


def test_chunk_format_is_big_endian_lengths(tmp_path: Path) -> None:
    """Guard against accidental endianness regression — Serato requires BE."""
    adapter = SeratoAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    raw = (tmp_path / SERATO_DIR / DATABASE_FILE).read_bytes()
    # First chunk: "vrsn" then 4-byte BE length then payload
    assert raw[:4] == b"vrsn"
    size_be = int.from_bytes(raw[4:8], "big")
    assert 0 < size_be < 1000  # version string shouldn't be huge
    # Decoding the payload as UTF-16-BE should yield a printable string
    version_str = raw[8 : 8 + size_be].decode("utf-16-be")
    assert "Serato" in version_str


def test_unicode_roundtrips(tmp_path: Path) -> None:
    adapter = SeratoAdapter()
    track = TrackRecord(
        path=Path(r"C:\Music\Björk — Jóga.flac"),
        title="Jóga",
        artist="Björk",
        genre="Alternative",
        bpm=120.0,
    )
    adapter.write_library(tmp_path, [track])
    result = adapter.read_library(tmp_path)
    assert result[0].title == "Jóga"
    assert result[0].artist == "Björk"
    assert result[0].path == track.path


def test_validate_detects_missing(tmp_path: Path) -> None:
    adapter = SeratoAdapter()
    issues = adapter.validate(tmp_path)
    assert issues and "missing" in issues[0]


def test_validate_clean_after_write(tmp_path: Path) -> None:
    adapter = SeratoAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    assert adapter.validate(tmp_path) == []


def test_validate_detects_corruption(tmp_path: Path) -> None:
    adapter = SeratoAdapter()
    adapter.write_library(tmp_path, _sample_tracks())
    db_path = tmp_path / SERATO_DIR / DATABASE_FILE
    # Truncate mid-chunk to simulate corruption
    raw = db_path.read_bytes()
    db_path.write_bytes(raw[:-10] + b"\x00" * 5)
    issues = adapter.validate(tmp_path)
    assert issues
