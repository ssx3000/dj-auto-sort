"""Deduplication contract tests."""

from __future__ import annotations

from pathlib import Path

from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.dedup import find_duplicates


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _track(path: Path, *, duration_ms: int = 180000, **extras) -> TrackRecord:
    return TrackRecord(path=path, duration_ms=duration_ms, **extras)


def test_identical_files_flagged_as_duplicates(tmp_path: Path) -> None:
    data = b"RIFF" + b"\x42" * 1024 + b"WAVEfmt "
    a = tmp_path / "a" / "song.wav"
    b = tmp_path / "b" / "song.wav"
    _write(a, data)
    _write(b, data)

    groups = find_duplicates([_track(a), _track(b)])
    assert len(groups) == 1
    assert {t.path for t in groups[0].tracks} == {a, b}


def test_same_size_different_bytes_not_a_duplicate(tmp_path: Path) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    _write(a, b"\x01" * 2048)
    _write(b, b"\x02" * 2048)
    assert find_duplicates([_track(a), _track(b)]) == []


def test_different_sizes_dont_even_hash(tmp_path: Path) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    _write(a, b"\x01" * 1024)
    _write(b, b"\x01" * 2048)
    assert find_duplicates([_track(a), _track(b)]) == []


def test_missing_file_is_skipped_not_raised(tmp_path: Path) -> None:
    a = tmp_path / "a.wav"
    _write(a, b"\x01" * 1024)
    ghost = tmp_path / "does-not-exist.wav"
    # No exception, and no duplicate group for a single real file.
    assert find_duplicates([_track(a), _track(ghost)]) == []


def test_keeper_prefers_richer_metadata(tmp_path: Path) -> None:
    data = b"\x07" * 4096
    sparse_path = tmp_path / "downloads" / "track.mp3"
    rich_path = tmp_path / "library" / "track.mp3"
    _write(sparse_path, data)
    _write(rich_path, data)

    sparse = _track(sparse_path)
    rich = _track(
        rich_path,
        title="Title",
        artist="Artist",
        album="Album",
        genre="Genre",
        bpm=128.0,
        key_camelot="8A",
        energy=7,
    )
    groups = find_duplicates([sparse, rich])
    assert len(groups) == 1
    assert groups[0].keeper is rich
    assert groups[0].redundant == (sparse,)


def test_keeper_tie_breaks_to_shortest_path(tmp_path: Path) -> None:
    data = b"\x09" * 2048
    short = tmp_path / "a.mp3"
    long_ = tmp_path / "a" / "deeply" / "nested" / "a.mp3"
    _write(short, data)
    _write(long_, data)
    groups = find_duplicates([_track(long_), _track(short)])
    assert len(groups) == 1
    assert groups[0].keeper.path == short


def test_duration_bucket_separates_different_length_tracks(tmp_path: Path) -> None:
    # Same file size, different durations → different buckets, no hash done,
    # no duplicates reported.
    data = b"\x03" * 1024
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    _write(a, data)
    _write(b, data)
    groups = find_duplicates(
        [_track(a, duration_ms=180000), _track(b, duration_ms=240000)]
    )
    assert groups == []
