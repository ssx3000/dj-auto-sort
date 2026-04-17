from __future__ import annotations

import sys


def main() -> int:
    """Console entry point. Launches the PySide6 GUI."""
    from dj_auto_sort.ui.main_window import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
