"""humanize_error translates disk/permission errors into user-facing text."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from dj_auto_sort.ui.sync_worker import humanize_error


def test_file_not_found_mentions_path_and_settings() -> None:
    exc = FileNotFoundError(2, "No such file", "C:/missing/rekordbox.xml")
    msg = humanize_error(exc)
    assert "C:/missing/rekordbox.xml" in msg
    assert "Settings" in msg


def test_permission_denied_mentions_path_and_dj_program() -> None:
    exc = PermissionError(13, "Permission denied", "C:/Serato/database V2")
    msg = humanize_error(exc)
    assert "C:/Serato/database V2" in msg
    assert "DJ program" in msg


def test_is_a_directory_points_at_file_vs_folder_confusion() -> None:
    exc = IsADirectoryError(21, "Is a directory", "C:/music")
    msg = humanize_error(exc)
    assert "C:/music" in msg
    assert "folder" in msg.lower()


def test_unknown_exception_falls_back_to_type_and_message() -> None:
    msg = humanize_error(RuntimeError("something weird"))
    assert "RuntimeError" in msg
    assert "something weird" in msg


def test_file_not_found_without_filename_falls_back() -> None:
    # No filename attribute means we can't give useful guidance; the raw
    # message still goes through rather than being swallowed.
    msg = humanize_error(FileNotFoundError("generic not found"))
    assert "FileNotFoundError" in msg
