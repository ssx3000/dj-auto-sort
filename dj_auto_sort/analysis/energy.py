"""Energy scoring on a 1-10 Mixed-In-Key-style scale.

We combine three features into a single 0..1 raw score, then quantize to 1-10:

  * **loudness** — RMS in dBFS, mapped linearly from −60 dB (silent) to −6 dB (hot)
  * **activity** — onset rate (onsets per second), saturating around 6/s
  * **brightness** — spectral centroid in Hz, saturating around 4 kHz

The weights (0.5 / 0.3 / 0.2) favor loudness since it's the dominant signal in
DJ-context energy ratings, with onset activity and spectral brightness as
secondary cues. The full-corpus accuracy suite will tune these weights against
the ground-truth MIK scores in ``tests/fixtures/audio/ground_truth.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

_LOUDNESS_WEIGHT = 0.5
_ACTIVITY_WEIGHT = 0.3
_BRIGHTNESS_WEIGHT = 0.2

_DB_FLOOR = -60.0
_DB_CEILING = -6.0
_CENTROID_CEILING_HZ = 4000.0
_ONSETS_PER_SEC_CEILING = 6.0


@dataclass(frozen=True)
class EnergyResult:
    energy: int  # 1-10
    raw_score: float  # 0..1 before quantization
    analyzer: str


def detect_energy(audio_path: Path) -> EnergyResult:
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    import librosa

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    if y.size == 0:
        return EnergyResult(energy=1, raw_score=0.0, analyzer="librosa")

    loudness = _loudness_component(y)
    activity = _activity_component(y, sr)
    brightness = _brightness_component(y, sr)

    raw = (
        _LOUDNESS_WEIGHT * loudness
        + _ACTIVITY_WEIGHT * activity
        + _BRIGHTNESS_WEIGHT * brightness
    )
    raw_clamped = float(np.clip(raw, 0.0, 1.0))
    energy = 1 + int(round(raw_clamped * 9))  # [0,1] → [1,10]
    return EnergyResult(energy=energy, raw_score=raw_clamped, analyzer="librosa")


def _loudness_component(y: np.ndarray) -> float:
    import librosa

    rms = librosa.feature.rms(y=y)[0]
    rms_mean = float(np.mean(rms))
    db = 20.0 * float(np.log10(rms_mean + 1e-9))
    return float(np.clip((db - _DB_FLOOR) / (_DB_CEILING - _DB_FLOOR), 0.0, 1.0))


def _activity_component(y: np.ndarray, sr: int) -> float:
    import librosa

    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    duration = len(y) / sr if sr > 0 else 1.0
    if duration <= 0:
        return 0.0
    onset_rate = len(onsets) / duration
    return float(np.clip(onset_rate / _ONSETS_PER_SEC_CEILING, 0.0, 1.0))


def _brightness_component(y: np.ndarray, sr: int) -> float:
    import librosa

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = float(np.mean(centroid))
    return float(np.clip(centroid_mean / _CENTROID_CEILING_HZ, 0.0, 1.0))
