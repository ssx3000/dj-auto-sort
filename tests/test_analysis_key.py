"""Key detection tests.

Synthesizes sustained triads at known tonics so CI passes without the real
audio corpus. The tighter-tolerance accuracy suite against real tracks lives
behind the ``needs_fixtures_audio`` marker.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from dj_auto_sort.analysis.key import KeyResult, detect_key, key_to_camelot


# MIDI note → frequency (A4 = 69 = 440 Hz).
def _midi_to_hz(note: int) -> float:
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def _write_triad_wav(
    path: Path,
    *,
    midi_notes: list[int],
    duration_s: float = 10.0,
    sr: int = 22050,
) -> None:
    """Write a sustained triad. Includes 2nd + 3rd harmonics so chroma sees
    a realistic harmonic profile rather than pure sines."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False, dtype=np.float32)
    signal = np.zeros_like(t)
    for note in midi_notes:
        f0 = _midi_to_hz(note)
        signal += np.sin(2 * np.pi * f0 * t)
        signal += 0.5 * np.sin(2 * np.pi * 2 * f0 * t)
        signal += 0.25 * np.sin(2 * np.pi * 3 * f0 * t)
    signal = (signal / np.max(np.abs(signal)) * 0.5).astype(np.float32)
    sf.write(str(path), signal, sr, subtype="PCM_16")


def test_key_to_camelot_reference_pair() -> None:
    # C major and A minor share the 8 cell on the Camelot wheel.
    assert key_to_camelot("C", "major") == "8B"
    assert key_to_camelot("A", "minor") == "8A"


def test_key_to_camelot_accepts_flats_and_sharps() -> None:
    assert key_to_camelot("F#", "major") == key_to_camelot("Gb", "major") == "2B"
    # Bb minor / A#m → cell 3A
    assert key_to_camelot("Bb", "minor") == key_to_camelot("A#", "minor") == "3A"
    # C#m / Dbm → cell 12A
    assert key_to_camelot("C#", "minor") == key_to_camelot("Db", "minor") == "12A"


def test_key_to_camelot_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        key_to_camelot("H", "major")
    with pytest.raises(ValueError):
        key_to_camelot("C", "dorian")


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect_key(tmp_path / "nope.wav")


# (label, midi notes, expected camelot, expected tonic, expected scale)
_TRIADS: list[tuple[str, list[int], str, str, str]] = [
    # C major triad: C4, E4, G4
    ("C_major", [60, 64, 67], "8B", "C", "major"),
    # A minor triad: A3, C4, E4
    ("A_minor", [57, 60, 64], "8A", "A", "minor"),
    # G major triad: G3, B3, D4
    ("G_major", [55, 59, 62], "9B", "G", "major"),
    # E minor triad: E3, G3, B3
    ("E_minor", [52, 55, 59], "9A", "E", "minor"),
]


@pytest.mark.parametrize(("label", "notes", "camelot", "tonic", "scale"), _TRIADS)
def test_detect_key_on_sustained_triad(
    tmp_path: Path,
    label: str,
    notes: list[int],
    camelot: str,
    tonic: str,
    scale: str,
) -> None:
    wav = tmp_path / f"{label}.wav"
    _write_triad_wav(wav, midi_notes=notes)
    result = detect_key(wav)

    assert isinstance(result, KeyResult)
    assert result.analyzer in {"essentia", "librosa"}
    assert result.tonic == tonic, (
        f"[{label}] got tonic={result.tonic} scale={result.scale} "
        f"camelot={result.key_camelot}, expected {tonic} {scale} ({camelot})"
    )
    assert result.scale == scale
    assert result.key_camelot == camelot
