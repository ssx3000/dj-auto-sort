"""Packaging smoke tests — cheap regression checks that don't need PyInstaller.

Running the actual build is slow and pulls in heavy deps, so we cover it
manually. These tests only catch the dumb breakage (entry point gone, spec
file unparseable, build helper import-broken).
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_ROOT / "dj-auto-sort.spec"
BUILD_HELPER = PROJECT_ROOT / "packaging" / "build.py"
INSTALLER_SCRIPT = PROJECT_ROOT / "packaging" / "installer.iss"


def test_entry_point_is_callable() -> None:
    from dj_auto_sort.main import main

    assert callable(main)


def test_spec_file_parses_as_python() -> None:
    assert SPEC_FILE.exists(), f"missing spec file: {SPEC_FILE}"
    ast.parse(SPEC_FILE.read_text(encoding="utf-8"), filename=str(SPEC_FILE))


def test_spec_file_targets_one_file_windowed_exe() -> None:
    text = SPEC_FILE.read_text(encoding="utf-8")
    assert 'name="dj-auto-sort"' in text
    assert "console=False" in text, "GUI build must not spawn a console window"


def test_build_helper_parses_as_python() -> None:
    assert BUILD_HELPER.exists(), f"missing build helper: {BUILD_HELPER}"
    ast.parse(BUILD_HELPER.read_text(encoding="utf-8"), filename=str(BUILD_HELPER))


def test_pyproject_declares_packaging_extra() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "packaging = [" in pyproject
    assert "pyinstaller" in pyproject


def test_installer_script_exists_and_has_required_sections() -> None:
    assert INSTALLER_SCRIPT.exists(), f"missing Inno Setup script: {INSTALLER_SCRIPT}"
    text = INSTALLER_SCRIPT.read_text(encoding="utf-8")
    for section in ("[Setup]", "[Files]", "[Icons]", "[Languages]"):
        assert section in text, f"installer.iss missing {section} section"
    # Inno Setup 6 constants — confirms we're using the modern auto-privileges idiom.
    assert "{autopf}" in text
    # AppId must be stable across versions for upgrades to work; easy to regress.
    assert "AppId=" in text


def test_installer_script_references_built_exe() -> None:
    text = INSTALLER_SCRIPT.read_text(encoding="utf-8")
    assert "dj-auto-sort.exe" in text, "installer must bundle the PyInstaller output"
    assert "dj-auto-sort-setup-" in text, "installer output name must include product prefix"


def test_build_helper_wires_installer_flag() -> None:
    text = BUILD_HELPER.read_text(encoding="utf-8")
    assert '"--installer"' in text, "build.py must expose --installer CLI flag"
    assert "ISCC" in text, "build.py must invoke Inno Setup's ISCC compiler"
