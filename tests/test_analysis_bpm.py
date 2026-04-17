"""BPM analyzer tests.

These run without the ``tests/fixtures/audio/`` corpus by synthesizing click
tracks at known BPMs. The full-corpus accuracy suite (marked
``needs_fixtures_audio``) asserts tighter tolerances against real tracks.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from dj_auto_sort.analysis.bpm import BpmResult, detect_bpm


def _write_click_track(
    path: Path, *, bpm: float, duration_s: float = 16.0, sr: int = 44100
) -> None:
    """Write a kick-drum-like click track at ``bpm``.

    librosa's beat tracker works best with broadband onset energy (as in real
    percussion), not pure tones, so each "click" is a short exponentially
    decaying burst of filtered noise rather than a sine.
    """
    rng = np.random.default_rng(seed=0)  # deterministic fixture
    n_samples = int(sr * duration_s)
    signal = np.zeros(n_samples, dtype=np.float32)
    beat_period = 60.0 / bpm

    click_len = int(0.08 * sr)  # 80 ms decaying burst
    decay = np.exp(-np.linspace(0.0, 6.0, click_len, dtype=np.float32))
    noise = rng.standard_normal(click_len).astype(np.float32)
    click = (noise * decay * 0.5).astype(np.float32)

    beat_n = 0
    while True:
        start = int(beat_n * beat_period * sr)
        if start + click_len >= n_samples:
            break
        signal[start : start + click_len] += click
        beat_n += 1
    sf.write(str(path), signal, sr, subtype="PCM_16")


def test_result_carries_analyzer_name(tmp_path: Path) -> None:
    wav = tmp_path / "click.wav"
    _write_click_track(wav, bpm=120.0)
    result = detect_bpm(wav)
    assert isinstance(result, BpmResult)
    assert result.analyzer in {"essentia", "librosa"}
    assert result.bpm > 0


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect_bpm(tmp_path / "does-not-exist.wav")


@pytest.mark.parametrize("expected_bpm", [90.0, 120.0, 128.0, 140.0, 174.0])
def test_detect_bpm_hits_expected_or_octave(tmp_path: Path, expected_bpm: float) -> None:
    """Beat trackers often lock to half/double tempo; accept either as a pass.

    Tolerance is 2.0 BPM rather than the 0.5 BPM target from the plan because
    librosa's DP tempo estimator quantizes to a discrete tempo grid. The
    ±0.5 BPM target applies to the real-corpus accuracy suite (needs_fixtures_audio)
    where Essentia is expected to be installed.
    """
    wav = tmp_path / f"click_{int(expected_bpm)}.wav"
    _write_click_track(wav, bpm=expected_bpm)
    result = detect_bpm(wav)

    candidates = (expected_bpm, expected_bpm * 2.0, expected_bpm / 2.0)
    errors = [abs(result.bpm - c) for c in candidates]
    assert min(errors) < 2.0, (
        f"detected {result.bpm:.2f} BPM via {result.analyzer}, "
        f"expected {expected_bpm} (±half/double allowed, 2.0 BPM tolerance)"
    )
