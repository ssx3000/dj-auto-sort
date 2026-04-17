"""BPM detection. Essentia RhythmExtractor2013 preferred; librosa fallback.

Phase 3 implementation.
"""

from __future__ import annotations

from pathlib import Path


def detect_bpm(audio_path: Path) -> float:
    raise NotImplementedError("Phase 3")
