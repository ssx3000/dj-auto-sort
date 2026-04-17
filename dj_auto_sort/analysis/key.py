"""Musical key detection. Essentia KeyExtractor -> Camelot notation.

Phase 3 implementation.
"""

from __future__ import annotations

from pathlib import Path


def detect_key(audio_path: Path) -> str:
    """Return Camelot notation, e.g. '8A', '12B'."""
    raise NotImplementedError("Phase 3")
