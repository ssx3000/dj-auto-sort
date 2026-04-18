# DJ Auto-Sort

Windows desktop tool that auto-categorizes and auto-sorts music libraries for **Rekordbox**, **Serato DJ**, and **Virtual DJ**.

Analyzes BPM, key, energy, and genre/mood; cleans metadata; organizes folders and playlists; keeps all three DJ apps' libraries consistent.

This a proof of concept and has not been tested. If you using this as is, you are running this at your own risk. 

I don't mind if you use this as a foundation towards what you need. If you make something better than this, good. 

Finally, I want to give thanks to https://www.twitch.tv/spontaneousmixx & https://www.twitch.tv/djchickenw33d for the concept

## What it does

Point the tool at your Rekordbox, Serato, and/or Virtual DJ library folders and it will:

1. Read each library through the matching adapter in [`dj_auto_sort/adapters/`](dj_auto_sort/adapters/).
2. Analyze every track for BPM, key (Camelot wheel), energy (1–10), and genre/mood.
3. Clean inconsistent metadata tags and propose a tidier folder tree.
4. Show a **dry-run preview** in the UI before touching anything — dry-run is the default.
5. **Back up originals**, then write consistent metadata and playlists back to every configured app so all three stay in sync.

Your source audio files are never deleted or rewritten in place without a backup first.

## Features

- **Library I/O** — Rekordbox, Serato DJ, and Virtual DJ (read + write) via pluggable adapters in [`dj_auto_sort/adapters/`](dj_auto_sort/adapters/).
- **Analysis** — BPM, Camelot-wheel key, 1–10 energy rating, and genre/mood classification. Uses librosa by default; enables Essentia + MusicNN when the `[analysis-full]` extra is installed. See [`dj_auto_sort/analysis/`](dj_auto_sort/analysis/).
- **Organize & sync** — folder-tree reorganization, fingerprint-based dedup, metadata cleaner, per-run backup, and a cross-app sync orchestrator that keeps all three libraries consistent. See [`dj_auto_sort/organize/`](dj_auto_sort/organize/) and [`dj_auto_sort/sync/`](dj_auto_sort/sync/).
- **Desktop UI** — PySide6 app with a settings view, preview pane, threaded sync worker, persistent settings, and a first-run dialog.

## Status

Phases 1–7 complete: scaffold, adapters, analyzers, organize, sync, PySide6 UI, and PyInstaller packaging. See plan at `C:\Users\sxl50\.claude\plans\i-want-to-create-quiet-llama.md`.

## Quick start (development)

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

To enable the full analysis stack (Essentia + MusicNN):

```bash
pip install -e ".[dev,analysis-full]"
```

If the Essentia wheel fails to install on your Python version, the app falls back to librosa-based analyzers.

## Running

```bash
dj-auto-sort
```

## Build a Windows executable

```bash
pip install -e ".[dev,packaging]"
python packaging/build.py --clean
```

Produces `dist/dj-auto-sort.exe` (one-file, windowed). To sign the output, set
`SIGNTOOL_CERT_PATH` + `SIGNTOOL_CERT_PASSWORD` and pass `--sign`.

To wrap the `.exe` in a Windows installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(requires `ISCC.exe` on `PATH`, or set `INNO_ISCC_EXE`) and pass `--installer`:

```bash
python packaging/build.py --clean --installer
```

Produces `dist/dj-auto-sort-setup-<version>.exe`. Combine with `--sign` to sign
both the inner `.exe` and the installer.

## Testing scopes

1. **Library parsing** — golden-file round-trip for Rekordbox/Serato/Virtual DJ
2. **Audio analysis accuracy** — curated corpus with tolerance-based assertions
3. **File/folder ops** — tmpdir tests with no-data-loss guarantees
4. **Cross-DJ-app sync** — write via one adapter, read via another, assert equivalence
