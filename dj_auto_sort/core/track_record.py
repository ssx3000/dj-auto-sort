"""Internal canonical track model.

Every adapter and analyzer reads/writes this shape. Adapters translate to/from
each DJ app's native representation; analyzers enrich fields in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CuePoint:
    index: int
    position_ms: int
    label: str = ""
    color_rgb: tuple[int, int, int] | None = None
    is_loop: bool = False
    loop_length_ms: int | None = None


@dataclass
class TrackRecord:
    """Canonical track representation used across analyzers and adapters."""

    path: Path
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    mood: str = ""

    # Analysis outputs
    bpm: float | None = None
    key_camelot: str | None = None  # e.g. "8A", "12B"
    energy: int | None = None  # 1-10 scale, Mixed-In-Key style
    duration_ms: int | None = None

    # DJ-app metadata
    cues: list[CuePoint] = field(default_factory=list)
    color_rgb: tuple[int, int, int] | None = None
    rating: int = 0  # 0-5 stars

    # Internal bookkeeping
    analyzed_with: str | None = None  # name of analyzer stack used
    source_libraries: set[str] = field(default_factory=set)  # which adapters saw this

    def with_analysis(
        self,
        *,
        bpm: float | None = None,
        key_camelot: str | None = None,
        energy: int | None = None,
        genre: str | None = None,
        mood: str | None = None,
        analyzed_with: str | None = None,
    ) -> TrackRecord:
        """Return a shallow copy with analysis fields updated."""
        return TrackRecord(
            path=self.path,
            title=self.title,
            artist=self.artist,
            album=self.album,
            genre=genre if genre is not None else self.genre,
            mood=mood if mood is not None else self.mood,
            bpm=bpm if bpm is not None else self.bpm,
            key_camelot=key_camelot if key_camelot is not None else self.key_camelot,
            energy=energy if energy is not None else self.energy,
            duration_ms=self.duration_ms,
            cues=list(self.cues),
            color_rgb=self.color_rgb,
            rating=self.rating,
            analyzed_with=analyzed_with if analyzed_with is not None else self.analyzed_with,
            source_libraries=set(self.source_libraries),
        )
