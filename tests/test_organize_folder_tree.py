"""folder_tree path-rendering contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.folder_tree import render_target_path


def _track(**overrides) -> TrackRecord:
    defaults = {
        "path": Path("/src/input.mp3"),
        "title": "Around The World",
        "artist": "Daft Punk",
        "album": "Homework",
        "genre": "House",
        "bpm": 121.0,
        "key_camelot": "5A",
        "energy": 7,
    }
    defaults.update(overrides)
    return TrackRecord(**defaults)


def test_basic_genre_artist_title_template(tmp_path: Path) -> None:
    track = _track()
    out = render_target_path("{genre}/{artist} - {title}", track, tmp_path)
    assert out == tmp_path / "House" / "Daft Punk - Around The World.mp3"


def test_extension_preserved_from_source(tmp_path: Path) -> None:
    track = _track(path=Path("/src/song.flac"))
    out = render_target_path("{genre}/{title}", track, tmp_path)
    assert out.suffix == ".flac"


def test_missing_fields_become_unknown(tmp_path: Path) -> None:
    track = _track(genre="", artist="")
    out = render_target_path("{genre}/{artist}/{title}", track, tmp_path)
    assert out == tmp_path / "Unknown" / "Unknown" / "Around The World.mp3"


def test_title_falls_back_to_filename_stem(tmp_path: Path) -> None:
    track = _track(title="", path=Path("/src/mystery-track.wav"))
    out = render_target_path("{title}", track, tmp_path)
    assert out == tmp_path / "mystery-track.wav"


def test_forbidden_chars_in_values_are_replaced(tmp_path: Path) -> None:
    track = _track(title='AC/DC: Thunder"struck*?', artist="AC/DC")
    out = render_target_path("{artist}/{title}", track, tmp_path)
    # Forward slashes in VALUES become underscores so a title never invents
    # a new directory. The template-level separator is unaffected.
    assert out == tmp_path / "AC_DC" / "AC_DC_ Thunder_struck__.mp3"


def test_numeric_tokens(tmp_path: Path) -> None:
    track = _track(bpm=128.4, energy=9, key_camelot="8A")
    out = render_target_path(
        "{bpm}-{key}-{energy}/{title}",
        track,
        tmp_path,
    )
    # 128.4 rounds to 128.
    assert out == tmp_path / "128-8A-9" / "Around The World.mp3"


def test_unknown_token_raises(tmp_path: Path) -> None:
    track = _track()
    with pytest.raises(ValueError, match="unknown template token"):
        render_target_path("{lol}/{title}", track, tmp_path)


def test_case_insensitive_tokens(tmp_path: Path) -> None:
    track = _track()
    out = render_target_path("{GENRE}/{Artist}", track, tmp_path)
    assert out == tmp_path / "House" / "Daft Punk.mp3"


def test_empty_template_rejected(tmp_path: Path) -> None:
    track = _track()
    with pytest.raises(ValueError, match="empty path"):
        render_target_path("", track, tmp_path)
