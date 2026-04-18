"""Build the Windows .exe via PyInstaller, optionally wrap in an Inno Setup installer.

Examples:
    python packaging/build.py
    python packaging/build.py --clean
    python packaging/build.py --sign
    python packaging/build.py --clean --installer
    python packaging/build.py --clean --installer --sign

Code-signing reads these env vars when ``--sign`` is passed:
    SIGNTOOL_CERT_PATH      path to the .pfx certificate
    SIGNTOOL_CERT_PASSWORD  password for the .pfx (read from env only)
    SIGNTOOL_TIMESTAMP_URL  timestamp authority (default: DigiCert)
    SIGNTOOL_EXE            override path to signtool.exe

Installer compilation reads:
    INNO_ISCC_EXE           override path to ISCC.exe (default: ISCC.exe on PATH)

Without ``--sign``, we just build an unsigned .exe — fine for local testing.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_ROOT / "dj-auto-sort.spec"
ISS_FILE = PROJECT_ROOT / "packaging" / "installer.iss"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
EXE_PATH = DIST_DIR / "dj-auto-sort.exe"
DEFAULT_TIMESTAMP = "http://timestamp.digicert.com"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _project_version() -> str:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


def _installer_path(version: str) -> Path:
    return DIST_DIR / f"dj-auto-sort-setup-{version}.exe"


def _clean() -> None:
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            print(f"clean: {d}", flush=True)
            shutil.rmtree(d)


def _build() -> None:
    if not SPEC_FILE.exists():
        raise SystemExit(f"spec file missing: {SPEC_FILE}")
    _run([sys.executable, "-m", "PyInstaller", str(SPEC_FILE), "--noconfirm"])
    if not EXE_PATH.exists():
        raise SystemExit(f"build did not produce {EXE_PATH}")
    print(f"built: {EXE_PATH} ({EXE_PATH.stat().st_size / 1_048_576:.1f} MB)")


def _sign(target: Path) -> None:
    cert = os.environ.get("SIGNTOOL_CERT_PATH")
    password = os.environ.get("SIGNTOOL_CERT_PASSWORD")
    if not cert or not password:
        raise SystemExit(
            "code-signing requires SIGNTOOL_CERT_PATH and SIGNTOOL_CERT_PASSWORD env vars"
        )
    signtool = os.environ.get("SIGNTOOL_EXE", "signtool.exe")
    timestamp = os.environ.get("SIGNTOOL_TIMESTAMP_URL", DEFAULT_TIMESTAMP)
    _run(
        [
            signtool,
            "sign",
            "/fd",
            "SHA256",
            "/tr",
            timestamp,
            "/td",
            "SHA256",
            "/f",
            cert,
            "/p",
            password,
            str(target),
        ]
    )
    _run([signtool, "verify", "/pa", str(target)])


def _build_installer(version: str) -> Path:
    if not ISS_FILE.exists():
        raise SystemExit(f"Inno Setup script missing: {ISS_FILE}")
    if not EXE_PATH.exists():
        raise SystemExit(f"installer needs {EXE_PATH} to exist — build the .exe first")
    iscc = os.environ.get("INNO_ISCC_EXE", "ISCC.exe")
    _run([iscc, f"/DAppVersion={version}", str(ISS_FILE)])
    out = _installer_path(version)
    if not out.exists():
        raise SystemExit(f"Inno Setup did not produce {out}")
    print(f"installer: {out} ({out.stat().st_size / 1_048_576:.1f} MB)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the dj-auto-sort Windows .exe")
    parser.add_argument("--clean", action="store_true", help="Remove build/ and dist/ first")
    parser.add_argument("--sign", action="store_true", help="Sign artifacts after building")
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Wrap the .exe in an Inno Setup installer",
    )
    args = parser.parse_args()

    if args.clean:
        _clean()
    _build()
    if args.sign:
        _sign(EXE_PATH)
    if args.installer:
        installer = _build_installer(_project_version())
        if args.sign:
            _sign(installer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
