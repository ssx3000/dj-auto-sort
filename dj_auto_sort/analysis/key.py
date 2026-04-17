"""Musical key detection with Camelot-wheel output.

Essentia's ``KeyExtractor`` is used when available (it bundles several
well-tuned profile variants). Otherwise we fall back to a self-contained
Krumhansl-Schmuckler pitch-class profile correlation on top of a librosa
chromagram, which is accurate enough for DJ-wheel use (tonic ± adjacent
Camelot cell is the practical bar).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Pitch class → index (sharp form is canonical; flat spellings map to the
# same pitch class). Essentia returns sharp-and-flat variants inconsistently
# across profiles, so we accept both.
_PITCH_INDEX: dict[str, int] = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11,
}

_PITCH_NAME_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# (pitch_index, scale) → Camelot code. Built from the standard Camelot wheel:
# 8B=C major and 8A=A minor are the reference pair; other cells follow the
# circle of fifths (add 7 semitones per step clockwise for majors, same offset
# for minors — relative minor sits in the same cell with the "A" letter).
_CAMELOT: dict[tuple[int, str], str] = {
    (0, "major"): "8B",   (9, "minor"): "8A",
    (7, "major"): "9B",   (4, "minor"): "9A",
    (2, "major"): "10B",  (11, "minor"): "10A",
    (9, "major"): "11B",  (6, "minor"): "11A",
    (4, "major"): "12B",  (1, "minor"): "12A",
    (11, "major"): "1B",  (8, "minor"): "1A",
    (6, "major"): "2B",   (3, "minor"): "2A",
    (1, "major"): "3B",   (10, "minor"): "3A",
    (8, "major"): "4B",   (5, "minor"): "4A",
    (3, "major"): "5B",   (0, "minor"): "5A",
    (10, "major"): "6B",  (7, "minor"): "6A",
    (5, "major"): "7B",   (2, "minor"): "7A",
}

# Krumhansl-Schmuckler profiles, starting from the tonic pitch class.
_KS_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_KS_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


@dataclass(frozen=True)
class KeyResult:
    key_camelot: str  # e.g., "8B"
    tonic: str  # e.g., "C"
    scale: str  # "major" or "minor"
    analyzer: str  # "essentia" or "librosa"
    confidence: float | None = None

    @property
    def key_name(self) -> str:
        return f"{self.tonic} {self.scale}"


def key_to_camelot(tonic: str, scale: str) -> str:
    """Map a (tonic, scale) pair like ``("C", "major")`` to Camelot, e.g. ``"8B"``.

    Accepts both sharp (``F#``) and flat (``Gb``) spellings. Scale must be
    ``"major"`` or ``"minor"``.
    """
    if scale not in ("major", "minor"):
        raise ValueError(f"scale must be 'major' or 'minor', got {scale!r}")
    pitch = tonic.strip()
    if pitch not in _PITCH_INDEX:
        raise ValueError(f"unknown tonic {tonic!r}")
    return _CAMELOT[(_PITCH_INDEX[pitch], scale)]


def detect_key(audio_path: Path) -> KeyResult:
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    essentia_result = _try_essentia(audio_path)
    if essentia_result is not None:
        return essentia_result
    return _detect_key_librosa(audio_path)


def _try_essentia(audio_path: Path) -> KeyResult | None:
    try:
        from essentia.standard import (  # type: ignore[import-not-found]
            KeyExtractor,
            MonoLoader,
        )
    except ImportError:
        return None

    audio = MonoLoader(filename=str(audio_path))()
    tonic, scale, strength = KeyExtractor()(audio)
    return KeyResult(
        key_camelot=key_to_camelot(tonic, scale),
        tonic=tonic,
        scale=scale,
        analyzer="essentia",
        confidence=float(strength),
    )


def _detect_key_librosa(audio_path: Path) -> KeyResult:
    import librosa

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = np.asarray(chroma).mean(axis=1)

    best: tuple[int, str, float] | None = None
    for shift in range(12):
        # Rotate profile so its tonic aligns with pitch class `shift`
        major_rot = np.roll(_KS_MAJOR, shift)
        minor_rot = np.roll(_KS_MINOR, shift)
        score_maj = float(np.corrcoef(chroma_mean, major_rot)[0, 1])
        score_min = float(np.corrcoef(chroma_mean, minor_rot)[0, 1])
        if best is None or score_maj > best[2]:
            best = (shift, "major", score_maj)
        if score_min > best[2]:
            best = (shift, "minor", score_min)

    assert best is not None  # loop runs 12 times
    shift, scale, score = best
    tonic = _PITCH_NAME_SHARP[shift]
    return KeyResult(
        key_camelot=key_to_camelot(tonic, scale),
        tonic=tonic,
        scale=scale,
        analyzer="librosa",
        confidence=score,
    )
