"""Run :func:`dj_auto_sort.sync.orchestrator.sync` off the UI thread.

Sync touches disk, can take seconds-to-minutes on a real library, and may
trigger audio analysis; we MUST run it on a worker thread or the window
freezes for the whole run.

We use the QObject-moved-to-QThread pattern (rather than ``QThread.run``
subclassing) because it composes better with Qt signals and keeps all the
sync business logic in a plain object that's easy to unit-test without a
Qt event loop.

The caller owns the QThread's lifetime — :class:`SyncWorker` just emits.

The worker also builds the ``sources``/``targets`` tuple lists from a
:class:`Config`, so the main window doesn't have to know which adapter class
pairs with which config field.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from dj_auto_sort.adapters.base import LibraryAdapter
from dj_auto_sort.adapters.rekordbox import RekordboxAdapter
from dj_auto_sort.adapters.serato import SeratoAdapter
from dj_auto_sort.adapters.virtualdj import VirtualDJAdapter
from dj_auto_sort.core.config import Config
from dj_auto_sort.sync.orchestrator import Analyzer, SyncReport, sync

SyncFn = Callable[..., SyncReport]


class SyncWorker(QObject):
    """Runs one sync on demand and emits the result or failure."""

    started = Signal()
    finished = Signal(object)  # SyncReport
    failed = Signal(str)

    def __init__(
        self,
        *,
        sync_fn: SyncFn = sync,
        analyzer: Analyzer | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sync_fn = sync_fn
        self._analyzer = analyzer
        self._config: Config | None = None
        self._dry_run = False

    def configure(self, config: Config, *, dry_run: bool) -> None:
        """Called on the UI thread before the QThread starts."""
        self._config = config
        self._dry_run = dry_run

    def run(self) -> None:
        """Slot. Runs on the worker thread."""
        if self._config is None:
            self.failed.emit("worker not configured")
            return
        self.started.emit()
        try:
            pairs = _adapter_pairs(self._config)
            report = self._sync_fn(
                sources=pairs,
                targets=pairs,
                analyze=self._analyzer,
                organize_root=self._config.organize_root,
                folder_template=self._config.folder_template,
                backup=self._config.backup_before_write,
                dry_run=self._dry_run,
            )
        except Exception as exc:  # noqa: BLE001 — UI wants every failure surfaced
            self.failed.emit(humanize_error(exc))
            return
        self.finished.emit(report)


def humanize_error(exc: BaseException) -> str:
    """Translate common disk/permission errors into guidance for DJ users.

    Keeps the underlying ``ExceptionType: message`` form as a fallback so we
    don't silently swallow useful detail for classes we haven't hand-tuned.
    """
    filename = getattr(exc, "filename", None)
    if isinstance(exc, FileNotFoundError) and filename:
        return (
            f"Couldn't find a library file at:\n\n{filename}\n\n"
            "Check the path in the Settings panel and try again."
        )
    if isinstance(exc, PermissionError) and filename:
        return (
            f"Permission denied opening:\n\n{filename}\n\n"
            "Make sure the DJ program isn't holding the file open, then try again."
        )
    if isinstance(exc, IsADirectoryError) and filename:
        return (
            f"Expected a file but got a folder:\n\n{filename}\n\n"
            "Point the Settings field at the library file itself, not its parent folder."
        )
    return f"{type(exc).__name__}: {exc}"


def _adapter_pairs(config: Config) -> list[tuple[LibraryAdapter, Path]]:
    """Map enabled adapter names to (adapter, root) tuples.

    Adapters whose path isn't configured are skipped silently — the main
    window's Run button is responsible for guarding against a fully empty
    configuration. Partial configs (e.g. only Rekordbox) are legitimate.

    The Rekordbox and VDJ adapters accept either the XML file or its parent
    directory; we hand through whatever the user pasted.
    """
    out: list[tuple[LibraryAdapter, Path]] = []
    if "rekordbox" in config.enabled_adapters and config.rekordbox_xml_path is not None:
        out.append((RekordboxAdapter(), config.rekordbox_xml_path))
    if "serato" in config.enabled_adapters and config.serato_root is not None:
        out.append((SeratoAdapter(), config.serato_root))
    if "virtualdj" in config.enabled_adapters and config.virtualdj_database_path is not None:
        out.append((VirtualDJAdapter(), config.virtualdj_database_path))
    return out
