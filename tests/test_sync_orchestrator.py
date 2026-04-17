"""Sync orchestrator tests.

These cover the seven pipeline stages end-to-end using the real phase-2
adapters (no mocks) and a tmp filesystem, so we exercise the same code
paths production will run.

The analysis step is injected via a fake callable so we don't pull
Essentia/librosa into the test suite; the analyzer contract is just
``TrackRecord -> TrackRecord``.
"""

from __future__ import annotations

from pathlib import Path

from dj_auto_sort.adapters.rekordbox import RekordboxAdapter
from dj_auto_sort.adapters.serato import SeratoAdapter
from dj_auto_sort.adapters.virtualdj import VirtualDJAdapter
from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.sync.orchestrator import sync


def _seed_audio(tmp_path: Path, rel: str, payload: bytes = b"audio") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(payload)
    return p


def _seed_vdj(root: Path, tracks: list[TrackRecord]) -> None:
    VirtualDJAdapter().write_library(root, tracks)


def _seed_rekordbox(root: Path, tracks: list[TrackRecord]) -> None:
    RekordboxAdapter().write_library(root, tracks)


def _seed_serato(root: Path, tracks: list[TrackRecord]) -> None:
    SeratoAdapter().write_library(root, tracks)


def test_sync_reads_source_and_writes_target(tmp_path: Path) -> None:
    src_audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    rb_root = tmp_path / "rb"
    _seed_vdj(
        vdj_root,
        [TrackRecord(path=src_audio, title="A", artist="Artist", genre="House", bpm=128.0, key_camelot="8A")],
    )

    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
    )

    assert report.tracks_read == 1
    assert report.tracks_written == {"rekordbox": 1}
    # Read the target back and confirm the track landed.
    out = RekordboxAdapter().read_library(rb_root)
    assert len(out) == 1
    assert out[0].title == "A"
    assert out[0].artist == "Artist"


def test_sync_merges_same_path_across_sources(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "music/x.mp3")
    vdj_root = tmp_path / "vdj"
    ser_root = tmp_path / "ser"
    # VDJ has the bpm; Serato has genre. Neither alone has both.
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="X", artist="Y", bpm=124.0)])
    _seed_serato(ser_root, [TrackRecord(path=audio, title="X", artist="Y", genre="Techno")])

    rb_root = tmp_path / "rb"
    sync(
        sources=[(VirtualDJAdapter(), vdj_root), (SeratoAdapter(), ser_root)],
        targets=[(RekordboxAdapter(), rb_root)],
    )

    out = RekordboxAdapter().read_library(rb_root)
    assert len(out) == 1
    merged = out[0]
    assert merged.bpm == 124.0
    assert merged.genre == "Techno"


def test_sync_analyzes_only_tracks_missing_fields(tmp_path: Path) -> None:
    full = _seed_audio(tmp_path, "music/full.mp3")
    partial = _seed_audio(tmp_path, "music/partial.mp3")
    vdj_root = tmp_path / "vdj"
    _seed_vdj(
        vdj_root,
        [
            TrackRecord(path=full, title="full", bpm=128.0, key_camelot="8A", energy=7),
            TrackRecord(path=partial, title="partial", bpm=128.0),  # missing key + energy
        ],
    )

    analyzed: list[Path] = []

    def fake_analyze(t: TrackRecord) -> TrackRecord:
        analyzed.append(t.path)
        return TrackRecord(
            path=t.path,
            title=t.title,
            artist=t.artist,
            album=t.album,
            genre=t.genre,
            bpm=t.bpm or 100.0,
            key_camelot=t.key_camelot or "1A",
            energy=t.energy if t.energy is not None else 5,
        )

    rb_root = tmp_path / "rb"
    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
        analyze=fake_analyze,
    )

    assert report.tracks_analyzed == 1
    assert analyzed == [partial]


def test_sync_backs_up_existing_target_before_write(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    rb_root = tmp_path / "rb"
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="A")])
    # Pre-seed target so there's something to back up.
    _seed_rekordbox(rb_root, [TrackRecord(path=audio, title="OLD")])
    original_xml = (rb_root / "rekordbox.xml").read_bytes()

    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
    )

    assert len(report.backups) == 1
    backup = report.backups[0]
    assert backup.exists()
    assert backup.read_bytes() == original_xml
    # And the live file has been rewritten with the new content.
    assert b"OLD" not in (rb_root / "rekordbox.xml").read_bytes()


def test_sync_no_backup_when_target_missing(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="A")])

    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), tmp_path / "rb")],
    )
    assert report.backups == []


def test_sync_backup_disabled(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    rb_root = tmp_path / "rb"
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="A")])
    _seed_rekordbox(rb_root, [TrackRecord(path=audio, title="OLD")])

    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
        backup=False,
    )
    assert report.backups == []


def test_sync_dry_run_does_not_touch_disk(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    rb_root = tmp_path / "rb"
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="A")])

    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
        dry_run=True,
    )
    assert report.tracks_written == {"rekordbox": 1}
    assert not (rb_root / "rekordbox.xml").exists()


def test_sync_organize_moves_files_and_updates_library_paths(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "staging/a.mp3", payload=b"ZZZ")
    vdj_root = tmp_path / "vdj"
    rb_root = tmp_path / "rb"
    library_root = tmp_path / "library"
    _seed_vdj(
        vdj_root,
        [TrackRecord(path=audio, title="Song", artist="Artist", genre="House")],
    )

    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
        organize_root=library_root,
        folder_template="{genre}/{artist} - {title}",
    )

    expected_dst = library_root / "House" / "Artist - Song.mp3"
    assert expected_dst.read_bytes() == b"ZZZ"
    assert not audio.exists()
    assert [r.status for r in report.move_results] == ["moved"]

    out = RekordboxAdapter().read_library(rb_root)
    assert out[0].path == expected_dst


def test_sync_reports_errors_but_keeps_going(tmp_path: Path) -> None:
    # Source directory with no library file → read_library raises.
    broken_root = tmp_path / "broken"
    broken_root.mkdir()

    audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="A")])

    rb_root = tmp_path / "rb"
    report = sync(
        sources=[
            (RekordboxAdapter(), broken_root),  # will fail
            (VirtualDJAdapter(), vdj_root),  # will succeed
        ],
        targets=[(RekordboxAdapter(), rb_root)],
    )

    assert any("rekordbox" in e for e in report.errors)
    # The good source still made it through.
    assert report.tracks_read == 1
    assert (rb_root / "rekordbox.xml").exists()


def test_sync_detects_duplicates_in_report(tmp_path: Path) -> None:
    a = _seed_audio(tmp_path, "music/a.mp3", payload=b"SAMEBYTES")
    b = _seed_audio(tmp_path, "dupes/a.mp3", payload=b"SAMEBYTES")
    vdj_root = tmp_path / "vdj"
    _seed_vdj(
        vdj_root,
        [
            TrackRecord(path=a, title="A", duration_ms=180000),
            TrackRecord(path=b, title="A", duration_ms=180000),
        ],
    )

    rb_root = tmp_path / "rb"
    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[(RekordboxAdapter(), rb_root)],
    )
    assert len(report.duplicate_groups) == 1
    paths = {t.path for t in report.duplicate_groups[0].tracks}
    assert paths == {a, b}


def test_sync_writes_multiple_targets(tmp_path: Path) -> None:
    audio = _seed_audio(tmp_path, "music/a.mp3")
    vdj_root = tmp_path / "vdj"
    _seed_vdj(vdj_root, [TrackRecord(path=audio, title="A")])

    rb_root = tmp_path / "rb"
    ser_root = tmp_path / "ser"
    vdj_out = tmp_path / "vdj_out"
    report = sync(
        sources=[(VirtualDJAdapter(), vdj_root)],
        targets=[
            (RekordboxAdapter(), rb_root),
            (SeratoAdapter(), ser_root),
            (VirtualDJAdapter(), vdj_out),
        ],
    )
    assert report.tracks_written == {"rekordbox": 1, "serato": 1, "virtualdj": 1}
    # All three target files exist.
    assert (rb_root / "rekordbox.xml").exists()
    assert (ser_root / "_Serato_" / "database V2").exists()
    assert (vdj_out / "database.xml").exists()
