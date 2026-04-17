# Audio accuracy corpus

This folder holds the ground-truth audio corpus used by phase-3 analysis tests.

## Not in git

Audio files (`*.wav`, `*.mp3`, `*.flac`) are excluded by `.gitignore`. Populate
locally before running audio-analysis tests. On CI we restore from a private
bucket or use Git LFS.

## Ground-truth schema

`ground_truth.json` is the source of truth. Keys are filenames (relative to this
folder); values are the expected analysis output:

```json
{
  "001_house_128_8a.wav": {
    "bpm": 128.0,
    "key_camelot": "8A",
    "energy": 6,
    "genre": "house",
    "mood": "uplifting",
    "notes": "reference: Mixed In Key 10 analysis"
  }
}
```

## Coverage targets

Aim for ~30 tracks spanning: house, techno, DnB, hip-hop, ambient, trap, funk,
disco. At least 2 tracks per genre. Tolerances:

- BPM: ±0.5
- Key: ±1 Camelot step
- Energy: ±1
