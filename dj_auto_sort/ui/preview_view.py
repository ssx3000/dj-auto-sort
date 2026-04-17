"""Read-only summary of a :class:`SyncReport`.

Four panels stacked top-to-bottom:

* **Counts line** — tracks read / analyzed / written, so the user knows at a
  glance whether the run did what they expected.
* **Move plan** — src → dst table, one row per move (status colorized).
* **Duplicates** — tree of groups with the would-be keeper highlighted.
* **Errors** — plain text list; empty when a run is clean.

The view is passive: ``show_report`` overwrites everything, ``clear`` resets.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dj_auto_sort.sync.orchestrator import SyncReport

_STATUS_COLORS = {
    "moved": QColor("#2b8a3e"),
    "skipped-noop": QColor("#495057"),
    "failed": QColor("#c92a2a"),
}


class PreviewView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._counts_label = QLabel("No run yet.")
        self._counts_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._counts_label)

        moves_group = QGroupBox("Move plan")
        moves_layout = QVBoxLayout(moves_group)
        self._moves = QTreeWidget()
        self._moves.setHeaderLabels(["Status", "Source", "Destination"])
        self._moves.setRootIsDecorated(False)
        self._moves.setUniformRowHeights(True)
        moves_layout.addWidget(self._moves)
        layout.addWidget(moves_group, 2)

        dup_group = QGroupBox("Duplicate groups")
        dup_layout = QVBoxLayout(dup_group)
        self._dupes = QTreeWidget()
        self._dupes.setHeaderLabels(["Track", "Keeper?"])
        dup_layout.addWidget(self._dupes)
        layout.addWidget(dup_group, 2)

        err_group = QGroupBox("Errors")
        err_layout = QVBoxLayout(err_group)
        self._errors = QPlainTextEdit()
        self._errors.setReadOnly(True)
        err_layout.addWidget(self._errors)
        layout.addWidget(err_group, 1)

    def clear(self) -> None:
        self._counts_label.setText("No run yet.")
        self._moves.clear()
        self._dupes.clear()
        self._errors.clear()

    def show_report(self, report: SyncReport) -> None:
        written_total = sum(report.tracks_written.values())
        per_target = ", ".join(f"{k}={v}" for k, v in sorted(report.tracks_written.items()))
        self._counts_label.setText(
            f"Read {report.tracks_read}  ·  "
            f"Analyzed {report.tracks_analyzed}  ·  "
            f"Wrote {written_total}"
            + (f" ({per_target})" if per_target else "")
        )

        self._moves.clear()
        for r in report.move_results:
            item = QTreeWidgetItem([r.status, str(r.plan.src), str(r.plan.dst)])
            color = _STATUS_COLORS.get(r.status)
            if color is not None:
                item.setForeground(0, color)
            if r.error:
                item.setToolTip(0, r.error)
            self._moves.addTopLevelItem(item)
        for col in range(3):
            self._moves.resizeColumnToContents(col)

        self._dupes.clear()
        for group in report.duplicate_groups:
            parent = QTreeWidgetItem([f"Group of {len(group.tracks)}", ""])
            for t in group.tracks:
                is_keeper = t is group.keeper
                child = QTreeWidgetItem([str(t.path), "keep" if is_keeper else ""])
                if is_keeper:
                    child.setForeground(1, QColor("#2b8a3e"))
                parent.addChild(child)
            parent.setExpanded(True)
            self._dupes.addTopLevelItem(parent)
        self._dupes.resizeColumnToContents(0)

        self._errors.setPlainText("\n".join(report.errors))
        self._errors.setPlaceholderText("(no errors)")
        # QPlainTextEdit doesn't scroll to top automatically on setPlainText.
        self._errors.verticalScrollBar().setValue(0)

        # Make the counts line accessible to tooltips for assistive tech.
        self._counts_label.setToolTip(
            f"backups={len(report.backups)}, "
            f"moves={len(report.move_results)}, "
            f"duplicate_groups={len(report.duplicate_groups)}, "
            f"errors={len(report.errors)}"
        )
        # Keep the move-plan focus where the user expects when the view is
        # first populated.
        self._moves.scrollToTop()

    # Accessors used by tests — public so we don't poke private widgets.
    def counts_text(self) -> str:
        return self._counts_label.text()

    def move_rows(self) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        for i in range(self._moves.topLevelItemCount()):
            item = self._moves.topLevelItem(i)
            out.append((item.text(0), item.text(1), item.text(2)))
        return out

    def duplicate_group_count(self) -> int:
        return self._dupes.topLevelItemCount()

    def errors_text(self) -> str:
        return self._errors.toPlainText()
