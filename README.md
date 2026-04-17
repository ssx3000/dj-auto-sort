# DJ Auto-Sort

Windows desktop tool that auto-categorizes and auto-sorts music libraries for **Rekordbox**, **Serato DJ**, and **Virtual DJ**.

Analyzes BPM, key, energy, and genre/mood; cleans metadata; organizes folders and playlists; keeps all three DJ apps' libraries consistent.

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

## Testing scopes

1. **Library parsing** — golden-file round-trip for Rekordbox/Serato/Virtual DJ
2. **Audio analysis accuracy** — curated corpus with tolerance-based assertions
3. **File/folder ops** — tmpdir tests with no-data-loss guarantees
4. **Cross-DJ-app sync** — write via one adapter, read via another, assert equivalence
