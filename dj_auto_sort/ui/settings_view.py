"""Settings panel: edit :class:`Config` through the UI.

The widget is a thin shell over the dataclass. ``get_config`` reads the
current form state, ``set_config`` pushes a Config back into the widgets,
and ``config_changed`` fires on any edit so the main window can live-enable
the Run button when enough fields are filled in.

Paths use QLineEdit + Browse button rather than a tree picker because DJ
library locations are machine-specific and users almost always paste them
from Explorer.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dj_auto_sort.core.config import Config

_ADAPTERS = ("rekordbox", "serato", "virtualdj")


class SettingsView(QWidget):
    """Form for editing a :class:`Config`."""

    config_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        paths_group = QGroupBox("Library locations")
        paths_form = QFormLayout(paths_group)
        self._music_root = _PathEdit(directory=True)
        self._rekordbox_xml = _PathEdit(directory=False, filter_="XML (*.xml)")
        self._serato_root = _PathEdit(directory=True)
        self._virtualdj_db = _PathEdit(directory=False, filter_="XML (*.xml)")
        self._organize_root = _PathEdit(directory=True)
        paths_form.addRow("Music root:", self._music_root)
        paths_form.addRow("Rekordbox XML:", self._rekordbox_xml)
        paths_form.addRow("Serato root:", self._serato_root)
        paths_form.addRow("Virtual DJ database:", self._virtualdj_db)
        paths_form.addRow("Organize into:", self._organize_root)
        layout.addWidget(paths_group)

        template_group = QGroupBox("Organize")
        template_form = QFormLayout(template_group)
        self._template = QLineEdit()
        self._template.setPlaceholderText("{genre}/{artist} - {title}")
        template_form.addRow("Folder template:", self._template)
        self._backup = QCheckBox("Back up libraries before writing")
        template_form.addRow(self._backup)
        layout.addWidget(template_group)

        adapters_group = QGroupBox("Sync these libraries")
        adapters_layout = QVBoxLayout(adapters_group)
        self._adapter_boxes: dict[str, QCheckBox] = {}
        for name in _ADAPTERS:
            box = QCheckBox(name)
            self._adapter_boxes[name] = box
            adapters_layout.addWidget(box)
        layout.addWidget(adapters_group)
        layout.addStretch(1)

        self.set_config(Config())

        for edit in (
            self._music_root,
            self._rekordbox_xml,
            self._serato_root,
            self._virtualdj_db,
            self._organize_root,
        ):
            edit.changed.connect(self.config_changed.emit)
        self._template.textChanged.connect(lambda _: self.config_changed.emit())
        self._backup.toggled.connect(lambda _: self.config_changed.emit())
        for box in self._adapter_boxes.values():
            box.toggled.connect(lambda _: self.config_changed.emit())

    def get_config(self) -> Config:
        return Config(
            music_root=self._music_root.path(),
            rekordbox_xml_path=self._rekordbox_xml.path(),
            serato_root=self._serato_root.path(),
            virtualdj_database_path=self._virtualdj_db.path(),
            organize_root=self._organize_root.path(),
            folder_template=self._template.text().strip() or Config().folder_template,
            backup_before_write=self._backup.isChecked(),
            enabled_adapters={n for n, b in self._adapter_boxes.items() if b.isChecked()},
        )

    def set_config(self, config: Config) -> None:
        self._music_root.set_path(config.music_root)
        self._rekordbox_xml.set_path(config.rekordbox_xml_path)
        self._serato_root.set_path(config.serato_root)
        self._virtualdj_db.set_path(config.virtualdj_database_path)
        self._organize_root.set_path(config.organize_root)
        self._template.setText(config.folder_template)
        self._backup.setChecked(config.backup_before_write)
        for name, box in self._adapter_boxes.items():
            box.setChecked(name in config.enabled_adapters)


class _PathEdit(QWidget):
    """QLineEdit + Browse button. Resolves to Path or None."""

    changed = Signal()

    def __init__(
        self,
        *,
        directory: bool,
        filter_: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._directory = directory
        self._filter = filter_
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        self._edit.textChanged.connect(lambda _: self.changed.emit())
        self._browse = QPushButton("Browse…")
        self._browse.clicked.connect(self._on_browse)
        row.addWidget(self._edit, 1)
        row.addWidget(self._browse)
        self._picker: Callable[[], str] | None = None

    def set_picker(self, picker: Callable[[], str]) -> None:
        # Tests inject a fake picker so no modal dialog appears.
        self._picker = picker

    def path(self) -> Path | None:
        text = self._edit.text().strip()
        return Path(text) if text else None

    def set_path(self, path: Path | None) -> None:
        self._edit.setText(str(path) if path is not None else "")

    def _on_browse(self) -> None:
        if self._picker is not None:
            chosen = self._picker()
        elif self._directory:
            chosen = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, "Select file", "", self._filter)
        if chosen:
            self._edit.setText(chosen)
