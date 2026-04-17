"""metadata_cleaner contract tests."""

from __future__ import annotations

from pathlib import Path

from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.metadata_cleaner import clean


def _track(**overrides) -> TrackRecord:
    defaults = {
        "path": Path("/src/x.mp3"),
        "title": "",
        "artist": "",
        "album": "",
        "genre": "",
    }
    defaults.update(overrides)
    return TrackRecord(**defaults)


def test_strips_common_youtube_junk_tags() -> None:
    t = clean(_track(title="Around The World [Official Video]"))
    assert t.title == "Around the World"


def test_strips_multiple_junk_tag_variants() -> None:
    raw = "Get Lucky (Official Audio) [HD] (Explicit)"
    assert clean(_track(title=raw)).title == "Get Lucky"


def test_preserves_non_junk_bracketed_content() -> None:
    # Remix/extended mixes are meaningful — don't strip them.
    raw = "Harder Better Faster Stronger (Alive 2007 Edit)"
    assert clean(_track(title=raw)).title == "Harder Better Faster Stronger (Alive 2007 Edit)"


def test_title_case_keeps_small_words_lower() -> None:
    t = clean(_track(title="a tale of two cities"))
    # First+last words always cap; small words in the middle stay lower.
    assert t.title == "A Tale of Two Cities"


def test_title_case_preserves_short_acronyms() -> None:
    t = clean(_track(artist="DJ SNAKE"))
    assert t.artist == "DJ Snake"


def test_feat_variants_normalized() -> None:
    for raw in [
        "Pharrell FEAT Daft Punk",
        "Pharrell ft. Daft Punk",
        "Pharrell featuring Daft Punk",
        "Pharrell Feat Daft Punk",
    ]:
        assert clean(_track(artist=raw)).artist == "Pharrell Feat. Daft Punk"


def test_collapses_internal_whitespace() -> None:
    t = clean(_track(title="One    More    Time"))
    assert t.title == "One More Time"


def test_empty_fields_stay_empty() -> None:
    t = clean(_track())
    assert t.title == ""
    assert t.artist == ""
    assert t.album == ""


def test_analysis_fields_not_touched() -> None:
    original = _track(title="foo", bpm=128.0, key_camelot="8A", energy=7)
    cleaned = clean(original)
    assert cleaned.bpm == 128.0
    assert cleaned.key_camelot == "8A"
    assert cleaned.energy == 7


def test_path_not_touched() -> None:
    original = _track(title="foo", path=Path("/src/real file name.mp3"))
    cleaned = clean(original)
    assert cleaned.path == original.path


def test_apostrophe_handling() -> None:
    t = clean(_track(artist="o'brien"))
    assert t.artist == "O'Brien"


def test_hyphenated_words() -> None:
    t = clean(_track(title="drum-and-bass roller"))
    assert t.title == "Drum-And-Bass Roller"
