"""BPM detection.

Essentia's ``RhythmExtractor2013`` is preferred when installed (better accuracy
on complex electronic material, plus a confidence score). If Essentia isn't
available on this Python/Windows combo, we transparently fall back to
``librosa.beat.beat_track``, which ships with the base install.

The function returns a :class:`BpmResult` so downstream code can record which
analyzer produced the estimate (and, when available, its confidence) into
``TrackRecord.analyzed_with``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BpmResult:
    bpm: float
    analyzer: str  # "essentia" or "librosa"
    confidence: float | None = None


def detect_bpm(audio_path: Path) -> BpmResult:
    """Estimate the BPM of ``audio_path``.

    Tries Essentia first, falls back to librosa. Raises ``FileNotFoundError``
    if the audio file does not exist so callers don't silently get 0.0.
    """
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    essentia_result = _try_essentia(audio_path)
    if essentia_result is not None:
        return essentia_result
    return _detect_bpm_librosa(audio_path)


def _try_essentia(audio_path: Path) -> BpmResult | None:
    try:
        from essentia.standard import (  # type: ignore[import-not-found]
            MonoLoader,
            RhythmExtractor2013,
        )
    except ImportError:
        return None

    audio = MonoLoader(filename=str(audio_path))()
    bpm, _beats, confidence, _, _ = RhythmExtractor2013(method="multifeature")(audio)
    return BpmResult(bpm=float(bpm), analyzer="essentia", confidence=float(confidence))


def _detect_bpm_librosa(audio_path: Path) -> BpmResult:
    import librosa

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    tempo, _beats = librosa.beat.beat_track(y=y, sr=sr)
    # librosa ≥0.10 returns a 0-d or 1-element ndarray.
    bpm = float(tempo.item() if hasattr(tempo, "item") else tempo)
    return BpmResult(bpm=bpm, analyzer="librosa")
