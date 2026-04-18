"""Config persistence round-trip via an IniFormat QSettings in a tmp dir.

We never construct a default-scope QSettings here — that would write to the
real Windows registry and pollute the test environment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings

from dj_auto_sort.core.config import Config
from dj_auto_sort.core.config_store import (
    has_saved_config,
    load_config,
    save_config,
)


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_load_on_empty_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(_settings(tmp_path))
    assert cfg == Config()


def test_has_saved_config_false_before_any_save(tmp_path: Path) -> None:
    assert has_saved_config(_settings(tmp_path)) is False


def test_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    original = Config(
        music_root=Path("/music"),
        rekordbox_xml_path=Path("/rb/rekordbox.xml"),
        serato_root=Path("/ser"),
        virtualdj_database_path=Path("/vdj/database.xml"),
        organize_root=Path("/library"),
        folder_template="{artist}/{title}",
        backup_before_write=False,
        enabled_adapters={"rekordbox", "serato"},
    )
    save_config(original, settings)

    # Re-open via a fresh QSettings pointing at the same file — this is the
    # realistic "second launch" path and catches bugs that would slip past a
    # same-instance read.
    reopened = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert has_saved_config(reopened) is True
    loaded = load_config(reopened)

    assert loaded == original


def test_round_trip_handles_none_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    save_config(Config(), settings)
    loaded = load_config(settings)
    assert loaded.music_root is None
    assert loaded.rekordbox_xml_path is None
    assert loaded.serato_root is None
    assert loaded.virtualdj_database_path is None
    assert loaded.organize_root is None


def test_single_adapter_round_trips(tmp_path: Path) -> None:
    # QSettings collapses 1-element lists into a bare string on some backends;
    # this guards against a regression where the set becomes the string itself.
    settings = _settings(tmp_path)
    save_config(Config(enabled_adapters={"rekordbox"}), settings)
    loaded = load_config(settings)
    assert loaded.enabled_adapters == {"rekordbox"}


def test_empty_adapter_set_round_trips(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    save_config(Config(enabled_adapters=set()), settings)
    loaded = load_config(settings)
    assert loaded.enabled_adapters == set()


def test_backup_flag_round_trips_through_ini_string(tmp_path: Path) -> None:
    # IniFormat stores booleans as "true"/"false" — ensure we coerce back.
    settings = _settings(tmp_path)
    save_config(Config(backup_before_write=False), settings)
    reopened = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert load_config(reopened).backup_before_write is False
