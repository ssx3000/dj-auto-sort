"""Abstract base class every DJ-app library adapter must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from dj_auto_sort.core.track_record import TrackRecord


class LibraryAdapter(ABC):
    """Read from and write to a DJ app's native library."""

    name: str

    @abstractmethod
    def read_library(self, root: Path) -> list[TrackRecord]:
        """Parse the DJ app's library at `root` and return canonical records."""

    @abstractmethod
    def write_library(self, root: Path, tracks: Iterable[TrackRecord]) -> None:
        """Write records into the DJ app's library at `root`.

        Implementations MUST back up the existing library before writing when
        `Config.backup_before_write` is set (handled by the sync orchestrator).
        """

    @abstractmethod
    def validate(self, root: Path) -> list[str]:
        """Return a list of human-readable issues found at `root`; empty if OK."""

    @property
    @abstractmethod
    def supported_cue_count(self) -> int:
        """Max number of hot cues this app supports per track."""
