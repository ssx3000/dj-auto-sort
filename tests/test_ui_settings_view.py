"""SettingsView tests — Config round-trip and change notifications.

We poke the public QWidget surface (line edits, checkboxes) rather than the
private widget handles so the tests stay valid if the form is restyled.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from dj_auto_sort.core.config import Config
from dj_auto_sort.ui.settings_view import SettingsView


def test_settings_round_trips_config(qtbot) -> None:
    view = SettingsView()
    qtbot.addWidget(view)

    cfg = Config(
        music_root=Path("/music"),
        rekordbox_xml_path=Path("/rb/rekordbox.xml"),
        serato_root=Path("/ser"),
        virtualdj_database_path=Path("/vdj/database.xml"),
        organize_root=Path("/library"),
        folder_template="{artist}/{title}",
        backup_before_write=False,
        enabled_adapters={"rekordbox", "serato"},
    )
    view.set_config(cfg)
    out = view.get_config()

    assert out.music_root == Path("/music")
    assert out.rekordbox_xml_path == Path("/rb/rekordbox.xml")
    assert out.serato_root == Path("/ser")
    assert out.virtualdj_database_path == Path("/vdj/database.xml")
    assert out.organize_root == Path("/library")
    assert out.folder_template == "{artist}/{title}"
    assert out.backup_before_write is False
    assert out.enabled_adapters == {"rekordbox", "serato"}


def test_defaults_mirror_config_defaults(qtbot) -> None:
    view = SettingsView()
    qtbot.addWidget(view)
    out = view.get_config()
    default = Config()
    # No paths set on a fresh view.
    assert out.music_root is None
    assert out.rekordbox_xml_path is None
    assert out.serato_root is None
    assert out.virtualdj_database_path is None
    assert out.organize_root is None
    assert out.folder_template == default.folder_template
    assert out.backup_before_write == default.backup_before_write
    assert out.enabled_adapters == default.enabled_adapters


def test_config_changed_fires_on_edits(qtbot) -> None:
    view = SettingsView()
    qtbot.addWidget(view)

    with qtbot.waitSignal(view.config_changed, timeout=500):
        view.set_config(Config(music_root=Path("/new"), folder_template="{title}"))


def test_blank_template_falls_back_to_default(qtbot) -> None:
    view = SettingsView()
    qtbot.addWidget(view)
    view.set_config(Config(folder_template="   "))
    assert view.get_config().folder_template == Config().folder_template
