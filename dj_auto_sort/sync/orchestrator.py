"""Top-level sync: read every source library, merge, analyze, organize, write.

The orchestrator is the one place that understands the full pipeline. Each
stage is factored into a small helper so the UI (phase 6) can drive it
interactively and tests can exercise pieces in isolation.

Pipeline
--------

1. **Read** every source adapter into canonical :class:`TrackRecord` lists.
2. **Merge** by resolved file path. When the same file appears in two source
   libraries we keep the richer metadata and union the ``source_libraries``
   set — the same heuristic :mod:`organize.dedup` uses to pick a keeper.
3. **Analyze** every track that's missing ``bpm``/``key_camelot``/``energy``
   (optional, controlled by the caller-supplied ``analyze`` callable). The
   callable is injected so tests and UI don't drag Essentia/librosa into
   every path; production wires :func:`_default_analyze` which calls the
   phase-3 analyzers.
4. **Clean** text fields (title case, junk-tag strip, feat. normalization).
5. **Dedup** — find duplicate groups. We *report* them on the :class:`SyncReport`
   but do not auto-delete; removing audio from disk is a separate user action.
6. **Organize** (optional) — when ``organize_root`` is given, plan + execute
   file moves so each track lives at its templated location. We update each
   TrackRecord's ``path`` to reflect where the move landed so the libraries
   we write next reference the new locations.
7. **Backup** every target library file that already exists (timestamped
   ``.bak-YYYYMMDD-HHMMSS`` sibling) before a single adapter writes.
8. **Write** to each target adapter.

Failures in one stage surface as errors on :class:`SyncReport` rather than
bubbling up — the orchestrator is the caller's safety net and the UI wants
to show "3 of 4 libraries updated, serato failed because X" instead of a
bare exception.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dj_auto_sort.adapters.base import LibraryAdapter
from dj_auto_sort.core.track_record import TrackRecord
from dj_auto_sort.organize.dedup import DuplicateGroup, find_duplicates
from dj_auto_sort.organize.metadata_cleaner import clean as clean_metadata
from dj_auto_sort.organize.moves import MoveResult, execute_plan, plan_moves

Analyzer = Callable[[TrackRecord], TrackRecord]


@dataclass
class SyncReport:
    tracks_read: int = 0
    tracks_analyzed: int = 0
    tracks_written: dict[str, int] = field(default_factory=dict)
    backups: list[Path] = field(default_factory=list)
    move_results: list[MoveResult] = field(default_factory=list)
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sync(
    *,
    sources: Iterable[tuple[LibraryAdapter, Path]] = (),
    targets: Iterable[tuple[LibraryAdapter, Path]] = (),
    analyze: Analyzer | None = None,
    organize_root: Path | None = None,
    folder_template: str = "{genre}/{artist} - {title}",
    backup: bool = True,
    dry_run: bool = False,
) -> SyncReport:
    report = SyncReport()

    tracks = _read_sources(sources, report)
    report.tracks_read = len(tracks)

    if analyze is not None:
        tracks = _analyze_missing(tracks, analyze, report)

    tracks = [clean_metadata(t) for t in tracks]

    report.duplicate_groups = find_duplicates(tracks)

    if organize_root is not None:
        tracks = _organize(tracks, folder_template, organize_root, dry_run, report)

    _write_targets(tracks, targets, backup=backup, dry_run=dry_run, report=report)

    return report


def _read_sources(
    sources: Iterable[tuple[LibraryAdapter, Path]],
    report: SyncReport,
) -> list[TrackRecord]:
    """Read each source adapter and merge by resolved file path."""
    merged: dict[Path, TrackRecord] = {}
    for adapter, root in sources:
        try:
            records = adapter.read_library(root)
        except (OSError, ValueError) as exc:
            report.errors.append(f"read {adapter.name} @ {root}: {exc}")
            continue
        for record in records:
            key = _path_key(record.path)
            existing = merged.get(key)
            if existing is None:
                merged[key] = record
            else:
                merged[key] = _merge_records(existing, record)
    return list(merged.values())


def _path_key(path: Path) -> Path:
    """Best-effort canonical key for a track path.

    ``Path.resolve`` requires the file to exist on Windows; adapters read
    library XMLs that often point at paths the scan machine can't see, so
    we fall back to the raw path if resolution fails.
    """
    try:
        return path.resolve()
    except OSError:
        return path


def _merge_records(a: TrackRecord, b: TrackRecord) -> TrackRecord:
    """Combine two records for the same path, preferring richer fields.

    String fields: non-empty wins; when both are non-empty we keep ``a`` since
    the caller ordered sources by trust.
    Analysis fields (bpm/key/energy): first non-None wins.
    ``source_libraries``: union.
    ``cues``: whichever list is longer (more cue info is almost always a
    richer library).
    """
    return TrackRecord(
        path=a.path,
        title=a.title or b.title,
        artist=a.artist or b.artist,
        album=a.album or b.album,
        genre=a.genre or b.genre,
        mood=a.mood or b.mood,
        bpm=a.bpm if a.bpm is not None else b.bpm,
        key_camelot=a.key_camelot or b.key_camelot,
        energy=a.energy if a.energy is not None else b.energy,
        duration_ms=a.duration_ms if a.duration_ms is not None else b.duration_ms,
        cues=a.cues if len(a.cues) >= len(b.cues) else b.cues,
        color_rgb=a.color_rgb if a.color_rgb is not None else b.color_rgb,
        rating=a.rating or b.rating,
        analyzed_with=a.analyzed_with or b.analyzed_with,
        source_libraries=set(a.source_libraries) | set(b.source_libraries),
    )


def _analyze_missing(
    tracks: list[TrackRecord],
    analyze: Analyzer,
    report: SyncReport,
) -> list[TrackRecord]:
    out: list[TrackRecord] = []
    for t in tracks:
        if _needs_analysis(t):
            try:
                enriched = analyze(t)
            except (OSError, RuntimeError, ValueError) as exc:
                report.errors.append(f"analyze {t.path}: {exc}")
                out.append(t)
                continue
            report.tracks_analyzed += 1
            out.append(enriched)
        else:
            out.append(t)
    return out


def _needs_analysis(t: TrackRecord) -> bool:
    # Gate on bpm + key only — the two fields every adapter persists. Energy
    # is not round-tripped by any DJ app's native format, so using it here
    # would force re-analysis of every track on every sync.
    return t.bpm is None or t.key_camelot is None


def _organize(
    tracks: list[TrackRecord],
    template: str,
    root: Path,
    dry_run: bool,
    report: SyncReport,
) -> list[TrackRecord]:
    try:
        plans = plan_moves(tracks, template, root)
    except ValueError as exc:
        report.errors.append(f"organize plan: {exc}")
        return tracks
    results = execute_plan(plans, dry_run=dry_run)
    report.move_results = results

    # Remap each track's path to where it now lives (or would live on a
    # real run). Dry-run also remaps so the libraries we write mirror the
    # post-organize layout the user is reviewing.
    by_src = {r.plan.src: r.plan.dst for r in results if r.status in ("moved", "skipped-noop")}
    remapped: list[TrackRecord] = []
    for t in tracks:
        new_path = by_src.get(t.path, t.path)
        if new_path == t.path:
            remapped.append(t)
        else:
            remapped.append(_replace_path(t, new_path))
    return remapped


def _replace_path(t: TrackRecord, new_path: Path) -> TrackRecord:
    return TrackRecord(
        path=new_path,
        title=t.title,
        artist=t.artist,
        album=t.album,
        genre=t.genre,
        mood=t.mood,
        bpm=t.bpm,
        key_camelot=t.key_camelot,
        energy=t.energy,
        duration_ms=t.duration_ms,
        cues=list(t.cues),
        color_rgb=t.color_rgb,
        rating=t.rating,
        analyzed_with=t.analyzed_with,
        source_libraries=set(t.source_libraries),
    )


def _write_targets(
    tracks: list[TrackRecord],
    targets: Iterable[tuple[LibraryAdapter, Path]],
    *,
    backup: bool,
    dry_run: bool,
    report: SyncReport,
) -> None:
    for adapter, root in targets:
        if backup and not dry_run:
            backup_path = _backup_library(adapter, root)
            if backup_path is not None:
                report.backups.append(backup_path)
        if dry_run:
            report.tracks_written[adapter.name] = len(tracks)
            continue
        try:
            adapter.write_library(root, tracks)
        except (OSError, ValueError) as exc:
            report.errors.append(f"write {adapter.name} @ {root}: {exc}")
            continue
        report.tracks_written[adapter.name] = len(tracks)


def _backup_library(adapter: LibraryAdapter, root: Path) -> Path | None:
    """Copy the adapter's library file to a timestamped sibling, if present.

    We locate the file the adapter would write using its own ``_xml_path`` /
    ``_db_path`` helper when available, and otherwise fall through to ``root``
    itself (for adapters whose library *is* a single file).

    Returns the backup path written, or None if there was nothing to back up.
    """
    target = _locate_adapter_file(adapter, root)
    if target is None or not target.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = target.with_name(f"{target.name}.bak-{stamp}")
    shutil.copy2(target, backup_path)
    return backup_path


def _locate_adapter_file(adapter: LibraryAdapter, root: Path) -> Path | None:
    """Ask the adapter where it would write, falling back to ``root``."""
    for attr in ("_xml_path", "_db_path"):
        fn = getattr(adapter, attr, None)
        if callable(fn):
            try:
                return Path(fn(root))
            except (OSError, ValueError):
                return None
    if root.is_file():
        return root
    return None
