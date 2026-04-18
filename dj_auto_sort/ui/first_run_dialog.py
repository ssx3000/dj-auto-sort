"""First-run onboarding dialog.

Shown once, when :func:`config_store.has_saved_config` returns False. Kept
as a single modal dialog (not a QWizard) because the user still has to fill
in library paths by hand in the Settings panel — a multi-page wizard would
just duplicate that form. This dialog only orients them.

The "don't show again" behaviour is implicit: as soon as the user edits any
setting, :class:`MainWindow` persists it, and the next launch skips the
dialog automatically.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_WELCOME_TEXT = (
    "<h3>Welcome to DJ Auto-Sort</h3>"
    "<p>This tool reads your Rekordbox, Serato, and Virtual DJ libraries, "
    "analyzes BPM/key/energy/genre, organizes your files, and keeps the "
    "three libraries in sync.</p>"
    "<p><b>To get started:</b></p>"
    "<ol>"
    "<li>Point the <i>Library locations</i> fields at your DJ software's "
    "library files (use <b>Browse…</b> if you're not sure where they live).</li>"
    "<li>Tick at least one library under <i>Sync these libraries</i>.</li>"
    "<li>Leave <b>Dry run</b> checked and click <b>Run sync</b> to preview "
    "what will change — nothing is written to disk in dry-run mode.</li>"
    "<li>When the preview looks right, uncheck Dry run and run again.</li>"
    "</ol>"
    "<p>Your settings are saved automatically, so this welcome won't appear "
    "again once you've made a change.</p>"
)


class FirstRunDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome")
        self.setModal(True)

        layout = QVBoxLayout(self)
        label = QLabel(_WELCOME_TEXT)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.resize(520, 360)


__all__ = ["FirstRunDialog"]
