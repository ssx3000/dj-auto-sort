"""First-run dialog behaviour.

The dialog itself is trivial, so these tests focus on the MainWindow
integration: the dialog should fire when QSettings is empty and stay quiet
after a save has happened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QDialog

from dj_auto_sort.core.config import Config
from dj_auto_sort.core.config_store import save_config
from dj_auto_sort.sync.orchestrator import SyncReport
from dj_auto_sort.ui.main_window import MainWindow


class _FakeWorker(QObject):
    started = Signal()
    finished = Signal(object)
    failed = Signal(str)

    def configure(self, _cfg: Config, *, dry_run: bool) -> None:
        self._dry_run = dry_run

    def run(self) -> None:
        self.started.emit()
        self.finished.emit(SyncReport())


def _ini(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_first_run_dialog_fires_when_settings_empty(qtbot, tmp_path: Path) -> None:
    created: list[QDialog] = []

    def dialog_factory(parent):
        dlg = QDialog(parent)
        # Skip modal exec; we only care that the factory was called.
        dlg.exec = lambda: 0  # type: ignore[method-assign]
        created.append(dlg)
        return dlg

    settings = _ini(tmp_path)
    window = MainWindow(
        worker_factory=_FakeWorker,
        settings_provider=lambda: settings,
        first_run_dialog_factory=dialog_factory,
    )
    qtbot.addWidget(window)

    assert window.maybe_show_first_run() is True
    assert len(created) == 1


def test_first_run_dialog_skipped_when_config_exists(qtbot, tmp_path: Path) -> None:
    settings = _ini(tmp_path)
    save_config(Config(rekordbox_xml_path=Path("/rb.xml")), settings)

    created: list[QDialog] = []

    def dialog_factory(parent):
        dlg = QDialog(parent)
        dlg.exec = lambda: 0  # type: ignore[method-assign]
        created.append(dlg)
        return dlg

    window = MainWindow(
        worker_factory=_FakeWorker,
        settings_provider=lambda: settings,
        first_run_dialog_factory=dialog_factory,
    )
    qtbot.addWidget(window)

    assert window.maybe_show_first_run() is False
    assert created == []


def test_saved_config_is_restored_on_construction(qtbot, tmp_path: Path) -> None:
    settings = _ini(tmp_path)
    save_config(
        Config(
            rekordbox_xml_path=Path("/persisted/rb.xml"),
            folder_template="{year}/{artist}",
            backup_before_write=False,
        ),
        settings,
    )

    window = MainWindow(
        worker_factory=_FakeWorker,
        settings_provider=lambda: settings,
    )
    qtbot.addWidget(window)

    cfg = window.settings_view.get_config()
    assert cfg.rekordbox_xml_path == Path("/persisted/rb.xml")
    assert cfg.folder_template == "{year}/{artist}"
    assert cfg.backup_before_write is False


def test_settings_edit_is_autosaved(qtbot, tmp_path: Path) -> None:
    settings = _ini(tmp_path)

    window = MainWindow(
        worker_factory=_FakeWorker,
        settings_provider=lambda: settings,
    )
    qtbot.addWidget(window)

    # Simulate the user editing a path — config_changed fires, MainWindow persists.
    window.settings_view.set_config(Config(organize_root=Path("/out")))

    # Reopen settings from disk and confirm the edit made it through.
    reopened = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    from dj_auto_sort.core.config_store import load_config

    assert load_config(reopened).organize_root == Path("/out")
