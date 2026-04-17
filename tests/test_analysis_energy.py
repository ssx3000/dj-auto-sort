"""Energy analyzer tests.

We don't pin exact 1-10 scores — the calibration will shift as we tune against
the real corpus — but we pin relative ordering (silence < quiet tone < loud
broadband with onsets) and the 1-10 bounds.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from dj_auto_sort.analysis.energy import EnergyResult, detect_energy


def _write(path: Path, signal: np.ndarray, sr: int = 44100) -> None:
    sf.write(str(path), signal.astype(np.float32), sr, subtype="PCM_16")


def _silence(duration_s: float = 8.0, sr: int = 44100) -> np.ndarray:
    return np.zeros(int(sr * duration_s), dtype=np.float32)


def _quiet_tone(duration_s: float = 8.0, sr: int = 44100) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False, dtype=np.float32)
    return (0.02 * np.sin(2 * np.pi * 110.0 * t)).astype(np.float32)  # -34 dBFS-ish


def _loud_broadband_with_onsets(
    duration_s: float = 8.0, sr: int = 44100, bpm: float = 140.0
) -> np.ndarray:
    """Loud noise bed with percussive onsets at ``bpm`` — proxy for peak-time material."""
    rng = np.random.default_rng(seed=1)
    n = int(sr * duration_s)
    bed = rng.standard_normal(n).astype(np.float32) * 0.15
    beat_period = 60.0 / bpm
    click_len = int(0.05 * sr)
    decay = np.exp(-np.linspace(0, 5, click_len, dtype=np.float32))
    click = rng.standard_normal(click_len).astype(np.float32) * decay * 0.9
    i = 0
    while True:
        start = int(i * beat_period * sr)
        if start + click_len >= n:
            break
        bed[start : start + click_len] += click
        i += 1
    return np.clip(bed, -1.0, 1.0)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect_energy(tmp_path / "missing.wav")


def test_silence_bottoms_out_at_energy_1(tmp_path: Path) -> None:
    wav = tmp_path / "silence.wav"
    _write(wav, _silence())
    result = detect_energy(wav)
    assert isinstance(result, EnergyResult)
    assert result.energy == 1
    assert result.raw_score == pytest.approx(0.0, abs=1e-6)
    assert result.analyzer == "librosa"


def test_loud_broadband_scores_above_quiet_tone(tmp_path: Path) -> None:
    quiet = tmp_path / "quiet.wav"
    loud = tmp_path / "loud.wav"
    _write(quiet, _quiet_tone())
    _write(loud, _loud_broadband_with_onsets())

    quiet_result = detect_energy(quiet)
    loud_result = detect_energy(loud)

    assert loud_result.energy > quiet_result.energy
    assert loud_result.raw_score > quiet_result.raw_score


def test_energy_is_clamped_to_1_to_10(tmp_path: Path) -> None:
    """Pathologically hot signal must still land within [1, 10]."""
    sr = 44100
    # Full-scale broadband noise — as loud, bright, and busy as it gets.
    rng = np.random.default_rng(seed=2)
    signal = rng.standard_normal(sr * 6).astype(np.float32) * 0.95
    wav = tmp_path / "hot.wav"
    _write(wav, signal, sr)
    result = detect_energy(wav)
    assert 1 <= result.energy <= 10
    assert 0.0 <= result.raw_score <= 1.0
