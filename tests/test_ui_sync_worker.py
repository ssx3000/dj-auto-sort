"""SyncWorker tests — signal emission and config→adapter-pairs mapping.

We run the worker synchronously by calling ``run()`` directly; the QThread
wiring is exercised in the main-window smoke test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from dj_auto_sort.adapters.rekordbox import RekordboxAdapter
from dj_auto_sort.adapters.serato import SeratoAdapter
from dj_auto_sort.adapters.virtualdj import VirtualDJAdapter
from dj_auto_sort.core.config import Config
from dj_auto_sort.sync.orchestrator import SyncReport
from dj_auto_sort.ui.sync_worker import SyncWorker, _adapter_pairs


def test_run_emits_started_then_finished_with_report(qtbot) -> None:
    report = SyncReport(tracks_read=3, tracks_written={"rekordbox": 3})

    def fake_sync(**_kwargs) -> SyncReport:
        return report

    worker = SyncWorker(sync_fn=fake_sync)
    worker.configure(Config(rekordbox_xml_path=Path("/rb/rb.xml")), dry_run=True)

    finished_payloads: list[SyncReport] = []
    worker.finished.connect(finished_payloads.append)

    with (
        qtbot.waitSignal(worker.started, timeout=500),
        qtbot.waitSignal(worker.finished, timeout=500),
    ):
        worker.run()

    assert finished_payloads == [report]


def test_run_emits_failed_on_exception(qtbot) -> None:
    def boom(**_kwargs) -> SyncReport:
        raise RuntimeError("disk gone")

    worker = SyncWorker(sync_fn=boom)
    worker.configure(Config(rekordbox_xml_path=Path("/rb/rb.xml")), dry_run=True)

    messages: list[str] = []
    worker.failed.connect(messages.append)

    with qtbot.waitSignal(worker.failed, timeout=500):
        worker.run()

    assert len(messages) == 1
    assert "RuntimeError" in messages[0]
    assert "disk gone" in messages[0]


def test_run_unconfigured_fails_fast(qtbot) -> None:
    worker = SyncWorker()
    messages: list[str] = []
    worker.failed.connect(messages.append)
    with qtbot.waitSignal(worker.failed, timeout=500):
        worker.run()
    assert "not configured" in messages[0]


def test_run_passes_config_fields_to_sync(qtbot) -> None:
    captured: dict[str, object] = {}

    def capture(**kwargs) -> SyncReport:
        captured.update(kwargs)
        return SyncReport()

    worker = SyncWorker(sync_fn=capture)
    cfg = Config(
        rekordbox_xml_path=Path("/rb/rb.xml"),
        organize_root=Path("/lib"),
        folder_template="{title}",
        backup_before_write=False,
    )
    worker.configure(cfg, dry_run=True)
    worker.run()

    assert captured["organize_root"] == Path("/lib")
    assert captured["folder_template"] == "{title}"
    assert captured["backup"] is False
    assert captured["dry_run"] is True
    sources = list(captured["sources"])
    assert len(sources) == 1
    assert isinstance(sources[0][0], RekordboxAdapter)


def test_adapter_pairs_respects_enabled_set() -> None:
    cfg = Config(
        rekordbox_xml_path=Path("/rb/rb.xml"),
        serato_root=Path("/ser"),
        virtualdj_database_path=Path("/vdj/database.xml"),
        enabled_adapters={"serato"},
    )
    pairs = _adapter_pairs(cfg)
    assert len(pairs) == 1
    assert isinstance(pairs[0][0], SeratoAdapter)


def test_adapter_pairs_skips_enabled_but_unconfigured() -> None:
    cfg = Config(
        serato_root=Path("/ser"),
        enabled_adapters={"rekordbox", "serato", "virtualdj"},  # all enabled
    )
    pairs = _adapter_pairs(cfg)
    assert len(pairs) == 1
    assert isinstance(pairs[0][0], SeratoAdapter)


def test_adapter_pairs_all_configured() -> None:
    cfg = Config(
        rekordbox_xml_path=Path("/rb"),
        serato_root=Path("/ser"),
        virtualdj_database_path=Path("/vdj"),
    )
    pairs = _adapter_pairs(cfg)
    types = [type(a) for a, _ in pairs]
    assert RekordboxAdapter in types
    assert SeratoAdapter in types
    assert VirtualDJAdapter in types
