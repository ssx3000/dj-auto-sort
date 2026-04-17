"""Shared pytest fixtures.

Every fixture here should be cheap — heavy audio corpora live behind the
`needs_fixtures_audio` marker so base-install CI stays fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    return FIXTURES_ROOT


@pytest.fixture(scope="session")
def audio_fixtures_root(fixtures_root: Path) -> Path:
    path = fixtures_root / "audio"
    if not any(path.glob("*.wav")) and not any(path.glob("*.mp3")):
        pytest.skip("audio corpus not present; see tests/fixtures/audio/README.md")
    return path


@pytest.fixture(scope="session")
def rekordbox_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "rekordbox"


@pytest.fixture(scope="session")
def serato_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "serato"


@pytest.fixture(scope="session")
def virtualdj_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "virtualdj"
