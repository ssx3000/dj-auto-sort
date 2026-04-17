"""Genre and mood classification via MusicNN pretrained model (Essentia-TF).

Phase 3 implementation.
"""

from __future__ import annotations

from pathlib import Path


def detect_genre(audio_path: Path) -> tuple[str, str]:
    """Return (genre, mood)."""
    raise NotImplementedError("Phase 3")
