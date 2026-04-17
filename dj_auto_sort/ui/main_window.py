"""PySide6 main window. Phase 6 implementation.

Kept as a minimal runnable placeholder so the console entry point works end-to-end
during earlier phases (useful for smoke-testing the PySide6 install on Windows).
"""

from __future__ import annotations


def run(argv: list[str]) -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    app = QApplication(argv)
    window = QMainWindow()
    window.setWindowTitle("DJ Auto-Sort (scaffold)")
    window.setCentralWidget(QLabel("Phase 1 scaffold — UI lands in phase 6."))
    window.resize(480, 160)
    window.show()
    return app.exec()
