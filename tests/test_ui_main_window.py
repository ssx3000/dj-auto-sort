"""MainWindow smoke tests.

We inject a fake SyncWorker factory so the window doesn't actually touch
disk; the goal here is to verify that a click on Run:
  1. invokes the worker,
  2. routes the emitted report into the preview view,
  3. re-enables the Run button afterwards.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject, Signal

from dj_auto_sort.core.config import Config
from dj_auto_sort.sync.orchestrator import SyncReport
from dj_auto_sort.ui.main_window import MainWindow


class _FakeWorker(QObject):
    """Minimal SyncWorker stand-in that emits a canned report synchronously."""

    started = Signal()
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, report: SyncReport | None = None, error: str | None = None) -> None:
        super().__init__()
        self._report = report or SyncReport(tracks_read=5, tracks_written={"rekordbox": 5})
        self._error = error

    def configure(self, _config: Config, *, dry_run: bool) -> None:
        self._dry_run = dry_run

    def run(self) -> None:
        self.started.emit()
        if self._error is not None:
            self.failed.emit(self._error)
        else:
            self.finished.emit(self._report)


def test_run_click_routes_report_into_preview(qtbot) -> None:
    def factory() -> _FakeWorker:
        return _FakeWorker()

    window = MainWindow(worker_factory=factory)
    qtbot.addWidget(window)
    window.settings_view.set_config(Config(rekordbox_xml_path=Path("/rb/rb.xml")))

    window.trigger_run()
    qtbot.waitUntil(window.run_button.isEnabled, timeout=2000)

    counts = window.preview_view.counts_text()
    assert "Read 5" in counts
    assert "Wrote 5" in counts
    assert "Read 5" in window.statusBar().currentMessage()


def test_run_click_shows_failure_in_statusbar(qtbot, monkeypatch) -> None:
    def factory() -> _FakeWorker:
        return _FakeWorker(error="boom")

    # Swallow the modal dialog so the test doesn't block on user input.
    from dj_auto_sort.ui import main_window

    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *a, **kw: None)

    window = MainWindow(worker_factory=factory)
    qtbot.addWidget(window)
    window.trigger_run()
    qtbot.waitUntil(window.run_button.isEnabled, timeout=2000)

    assert "boom" in window.statusBar().currentMessage()


def test_second_click_while_running_is_ignored(qtbot) -> None:
    # Worker that parks in run() until we release it, so we can double-click.
    class Parked(QObject):
        started = Signal()
        finished = Signal(object)
        failed = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self.run_calls = 0

        def configure(self, _cfg, *, dry_run: bool) -> None:
            pass

        def run(self) -> None:
            self.run_calls += 1
            # Don't emit — the window stays "busy".

    created: list[Parked] = []

    def factory() -> Parked:
        w = Parked()
        created.append(w)
        return w

    window = MainWindow(worker_factory=factory)
    qtbot.addWidget(window)
    window.trigger_run()
    qtbot.waitUntil(lambda: created and created[0].run_calls == 1, timeout=2000)

    # Second click while the first worker is parked — no new worker should be made.
    window.trigger_run()
    assert len(created) == 1

    # Release the parked worker so the background QThread can terminate
    # cleanly for teardown — otherwise Qt waits on a running thread forever.
    created[0].finished.emit(SyncReport())
    qtbot.waitUntil(window.run_button.isEnabled, timeout=2000)


def test_dry_run_default_is_safe(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.dry_run.isChecked() is True
