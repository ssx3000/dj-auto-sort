"""Genre/mood analyzer contract tests.

Unconditional tests here cover the probe / graceful-skip path. The real
MusicNN accuracy suite lives behind the ``needs_essentia`` marker and runs
only in environments where ``essentia-tensorflow`` plus the model files
are installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_auto_sort.analysis import genre as genre_mod
from dj_auto_sort.analysis.genre import GenreResult, detect_genre, is_available


def test_is_available_false_when_no_models_configured() -> None:
    # With defaults unset (the normal development state), the analyzer
    # must report unavailable rather than attempting to run.
    genre_mod.DEFAULT_GENRE_MODEL_PATH = None
    genre_mod.DEFAULT_MOOD_MODEL_PATH = None
    assert is_available() is False


def test_detect_genre_raises_when_unavailable(tmp_path: Path) -> None:
    audio = tmp_path / "silence.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")  # content irrelevant; we
    # expect to fail on model-availability check before opening the file

    genre_mod.DEFAULT_GENRE_MODEL_PATH = None
    genre_mod.DEFAULT_MOOD_MODEL_PATH = None
    with pytest.raises(ModuleNotFoundError, match="MusicNN"):
        detect_genre(audio)


def test_missing_audio_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect_genre(tmp_path / "does-not-exist.wav")


def test_is_available_false_when_models_point_to_missing_files(tmp_path: Path) -> None:
    genre_mod.DEFAULT_GENRE_MODEL_PATH = tmp_path / "nope-genre.pb"
    genre_mod.DEFAULT_MOOD_MODEL_PATH = tmp_path / "nope-mood.pb"
    try:
        assert is_available() is False
    finally:
        genre_mod.DEFAULT_GENRE_MODEL_PATH = None
        genre_mod.DEFAULT_MOOD_MODEL_PATH = None


def test_generic_result_shape() -> None:
    # Smoke-test the dataclass itself so callers can rely on it in Phase 5.
    r = GenreResult(genre="house", mood="happy", analyzer="essentia-musicnn", confidence=0.82)
    assert r.genre == "house"
    assert r.mood == "happy"
    assert r.analyzer == "essentia-musicnn"
    assert r.confidence == pytest.approx(0.82)


@pytest.mark.needs_essentia
def test_genre_detection_on_real_model(tmp_path: Path) -> None:
    """Placeholder for the real MusicNN accuracy run.

    Enabled once someone wires DEFAULT_{GENRE,MOOD}_MODEL_PATH to downloaded
    graph files and the audio corpus ships.
    """
    pytest.skip("requires MusicNN model files and audio corpus")
