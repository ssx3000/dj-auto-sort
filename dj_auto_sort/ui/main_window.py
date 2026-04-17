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
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from dj_auto_sort.sync.orchestrator import SyncReport
from dj_auto_sort.ui.preview_view import PreviewView
from dj_auto_sort.ui.settings_view import SettingsView
from dj_auto_sort.ui.sync_worker import SyncWorker


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        worker_factory: Callable[[], SyncWorker] = SyncWorker,
    ) -> None:
        super().__init__()
        self._worker_factory = worker_factory
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

    # --- public surface for tests --------------------------------------------------

    def trigger_run(self) -> None:
        """Kick off a sync immediately (bypasses the button, for tests)."""
        self._on_run_clicked()

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
        self.statusBar().showMessage(f"Sync failed: {message}")
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


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    window = MainWindow()
    window.show()
    return app.exec()


__all__ = ["MainWindow", "run"]
