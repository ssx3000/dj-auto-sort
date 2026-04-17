"""Application configuration.

Kept intentionally minimal in phase 1; settings UI fills this out in phase 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    music_root: Path | None = None
    rekordbox_xml_path: Path | None = None
    serato_root: Path | None = None  # folder containing _Serato_
    virtualdj_database_path: Path | None = None

    organize_root: Path | None = None  # destination root for organize step; None = skip
    folder_template: str = "{genre}/{artist} - {title}"
    backup_before_write: bool = True

    enabled_adapters: set[str] = field(default_factory=lambda: {"rekordbox", "serato", "virtualdj"})
