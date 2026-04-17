"""Build the Windows .exe via PyInstaller.

Examples:
    python packaging/build.py
    python packaging/build.py --clean
    python packaging/build.py --sign

Code-signing reads these env vars when ``--sign`` is passed:
    SIGNTOOL_CERT_PATH      path to the .pfx certificate
    SIGNTOOL_CERT_PASSWORD  password for the .pfx (read from env only)
    SIGNTOOL_TIMESTAMP_URL  timestamp authority (default: DigiCert)
    SIGNTOOL_EXE            override path to signtool.exe

Without ``--sign``, we just build an unsigned .exe — fine for local testing.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_ROOT / "dj-auto-sort.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
EXE_PATH = DIST_DIR / "dj-auto-sort.exe"
DEFAULT_TIMESTAMP = "http://timestamp.digicert.com"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


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


def _sign() -> None:
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
            str(EXE_PATH),
        ]
    )
    _run([signtool, "verify", "/pa", str(EXE_PATH)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the dj-auto-sort Windows .exe")
    parser.add_argument("--clean", action="store_true", help="Remove build/ and dist/ first")
    parser.add_argument("--sign", action="store_true", help="Sign the .exe after building")
    args = parser.parse_args()

    if args.clean:
        _clean()
    _build()
    if args.sign:
        _sign()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
