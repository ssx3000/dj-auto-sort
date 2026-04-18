"""Top-level PySide6 main window.

Composition:

* A vertical splitter with :class:`SettingsView` on top and :class:`PreviewView`
  below, so the user can see both at once on a wide monitor and collapse the
  settings once they're stable.
* A toolbar row with a Dry-run checkbox and a Run button.
* A status bar that shows the current phase ("Reading sources…", etc.) —
  the worker only emits started/finished, so the status updates are coarse
  for now; richer progress lands when the analyzers grow a callback.

Threading: we move a :class:`SyncWorker` onto a :class:`QThread` and connect
the thread's ``started`` signal to ``worker.run``. The worker emits
``finished`` or ``failed`` back on the UI thread via Qt's default
queued-connection semantics.

Persistence: on construction we load the saved :class:`Config` via
:mod:`config_store` and push it into the settings panel; every subsequent
edit is persisted immediately via ``SettingsView.config_changed``. The
first-run dialog fires only when no config has ever been saved.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from dj_auto_sort.core import config_store
from dj_auto_sort.sync.orchestrator import SyncReport
from dj_auto_sort.ui.first_run_dialog import FirstRunDialog
from dj_auto_sort.ui.preview_view import PreviewView
from dj_auto_sort.ui.settings_view import SettingsView
from dj_auto_sort.ui.sync_worker import SyncWorker


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        worker_factory: Callable[[], SyncWorker] = SyncWorker,
        settings_provider: Callable[[], object] | None = None,
        first_run_dialog_factory: Callable[[QWidget], QDialog] | None = None,
    ) -> None:
        super().__init__()
        self._worker_factory = worker_factory
        # settings_provider returns the QSettings instance used for persistence;
        # tests inject one pointing at an IniFormat file in a tmp dir to avoid
        # touching the Windows registry.
        self._settings_provider = settings_provider or config_store.default_settings
        self._first_run_dialog_factory = first_run_dialog_factory or FirstRunDialog
        self.setWindowTitle("DJ Auto-Sort")
        self.resize(1100, 760)

        self.settings_view = SettingsView()
        self.preview_view = PreviewView()

        central = QWidget()
        root = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.settings_view)
        splitter.addWidget(self.preview_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        toolbar = QHBoxLayout()
        self.dry_run = QCheckBox("Dry run (don't touch disk)")
        self.dry_run.setChecked(True)  # safe default: preview before committing
        self.run_button = QPushButton("Run sync")
        self.run_button.clicked.connect(self._on_run_clicked)
        toolbar.addWidget(self.dry_run)
        toolbar.addStretch(1)
        toolbar.addWidget(self.run_button)
        root.addLayout(toolbar)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Configure libraries, then click Run sync.")

        self._thread: QThread | None = None
        self._worker: SyncWorker | None = None

        self._load_saved_config()
        # Autosave on every edit — QSettings writes are cheap and this matches
        # the user's mental model ("I typed a path, it's safe now").
        self.settings_view.config_changed.connect(self._persist_config)

    # --- public surface for tests --------------------------------------------------

    def trigger_run(self) -> None:
        """Kick off a sync immediately (bypasses the button, for tests)."""
        self._on_run_clicked()

    def maybe_show_first_run(self) -> bool:
        """Show the welcome dialog if no config has ever been saved.

        Returns True if the dialog was shown. Called by :func:`run` right
        after the window is visible so the onboarding modal appears on top
        of a populated settings form.
        """
        if config_store.has_saved_config(self._settings_provider()):
            return False
        dialog = self._first_run_dialog_factory(self)
        dialog.exec()
        return True

    # --- persistence --------------------------------------------------------------

    def _load_saved_config(self) -> None:
        saved = config_store.load_config(self._settings_provider())
        # Block config_changed during bulk load — we don't want the autosave
        # handler to fire once per field and thrash QSettings.
        self.settings_view.blockSignals(True)
        try:
            self.settings_view.set_config(saved)
        finally:
            self.settings_view.blockSignals(False)

    @Slot()
    def _persist_config(self) -> None:
        config_store.save_config(self.settings_view.get_config(), self._settings_provider())

    # --- slots ---------------------------------------------------------------------

    @Slot()
    def _on_run_clicked(self) -> None:
        if self._thread is not None:
            # A run is already in flight; ignore the click rather than stacking.
            return
        config = self.settings_view.get_config()
        self.preview_view.clear()
        self.run_button.setEnabled(False)
        self.statusBar().showMessage("Running sync…")

        self._thread = QThread(self)
        self._worker = self._worker_factory()
        self._worker.configure(config, dry_run=self.dry_run.isChecked())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        # Tear down the thread once the worker emits either outcome.
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    @Slot(object)
    def _on_finished(self, report: SyncReport) -> None:
        self.preview_view.show_report(report)
        summary = (
            f"Read {report.tracks_read} · "
            f"Wrote {sum(report.tracks_written.values())} · "
            f"{len(report.errors)} errors"
        )
        self.statusBar().showMessage(summary)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"Sync failed: {_first_line(message)}")
        QMessageBox.critical(self, "Sync failed", message)

    @Slot()
    def _cleanup_thread(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self.run_button.setEnabled(True)


def _first_line(message: str) -> str:
    return message.splitlines()[0] if message else ""


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setOrganizationName(config_store.ORGANIZATION)
    app.setApplicationName(config_store.APPLICATION)
    window = MainWindow()
    window.show()
    window.maybe_show_first_run()
    return app.exec()


__all__ = ["MainWindow", "run"]
