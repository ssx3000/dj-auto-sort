"""Genre and mood classification via Essentia's MusicNN pretrained models.

This analyzer is **best-effort**: it needs both the ``analysis-full`` optional
extra (``essentia-tensorflow``) and a downloaded MusicNN graph file on disk.
When either is missing, ``is_available()`` returns False and the sync
orchestrator should skip genre classification rather than erroring.

Model files are published in Essentia's model zoo:
    https://essentia.upf.edu/models.html

The two MusicNN variants we target are:
    * ``msd-musicnn-1.pb``     — 50-class Million Song Dataset genre taxonomy
    * ``mtt-mood-musicnn-1.pb`` — multi-label mood (happy, sad, aggressive, …)

Set :data:`DEFAULT_GENRE_MODEL_PATH` / :data:`DEFAULT_MOOD_MODEL_PATH` at
startup (e.g. from :mod:`dj_auto_sort.core.config`) before calling
:func:`detect_genre`, or pass ``model_paths=`` explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_GENRE_MODEL_PATH: Path | None = None
DEFAULT_MOOD_MODEL_PATH: Path | None = None

_MUSICNN_SAMPLE_RATE = 16000


@dataclass(frozen=True)
class GenreResult:
    genre: str
    mood: str
    analyzer: str  # "essentia-musicnn"
    confidence: float | None = None


def is_available(
    *,
    genre_model_path: Path | None = None,
    mood_model_path: Path | None = None,
) -> bool:
    """Return True iff Essentia-TF imports AND both model files are on disk."""
    try:
        import essentia.standard  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    genre_p = genre_model_path or DEFAULT_GENRE_MODEL_PATH
    mood_p = mood_model_path or DEFAULT_MOOD_MODEL_PATH
    return bool(genre_p and genre_p.exists() and mood_p and mood_p.exists())


def detect_genre(
    audio_path: Path,
    *,
    genre_model_path: Path | None = None,
    mood_model_path: Path | None = None,
) -> GenreResult:
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    genre_p = genre_model_path or DEFAULT_GENRE_MODEL_PATH
    mood_p = mood_model_path or DEFAULT_MOOD_MODEL_PATH
    if not (genre_p and genre_p.exists() and mood_p and mood_p.exists()):
        raise ModuleNotFoundError(
            "MusicNN model files not available; download from "
            "https://essentia.upf.edu/models.html and set "
            "dj_auto_sort.analysis.genre.DEFAULT_GENRE_MODEL_PATH / "
            "DEFAULT_MOOD_MODEL_PATH (or pass model paths explicitly)."
        )

    try:
        from essentia.standard import (  # type: ignore[import-not-found]
            MonoLoader,
            TensorflowPredictMusiCNN,
        )
    except ImportError as exc:
        raise ModuleNotFoundError(
            "essentia-tensorflow is not installed; install the analysis-full extra."
        ) from exc

    audio = MonoLoader(
        filename=str(audio_path),
        sampleRate=_MUSICNN_SAMPLE_RATE,
        resampleQuality=4,
    )()

    # Each model returns (n_frames, n_classes); we collapse time by averaging
    # and pick the top class. Label maps ship alongside the models in the zoo
    # as JSON metadata; resolving them is left to the caller-level config in
    # the sync orchestrator so tests don't depend on the on-disk layout.
    genre_probs = TensorflowPredictMusiCNN(graphFilename=str(genre_p))(audio)
    mood_probs = TensorflowPredictMusiCNN(graphFilename=str(mood_p))(audio)

    genre_label, genre_conf = _top_label(genre_probs, _labels_for(genre_p))
    mood_label, _ = _top_label(mood_probs, _labels_for(mood_p))

    return GenreResult(
        genre=genre_label,
        mood=mood_label,
        analyzer="essentia-musicnn",
        confidence=genre_conf,
    )


def _top_label(probs, labels: list[str]) -> tuple[str, float]:
    import numpy as np

    arr = np.asarray(probs)
    mean = arr.mean(axis=0) if arr.ndim == 2 else arr
    idx = int(np.argmax(mean))
    return labels[idx], float(mean[idx])


def _labels_for(model_path: Path) -> list[str]:
    """Labels for a MusicNN model ship as ``<model>.json`` in the Essentia zoo.

    We read the JSON at call time rather than caching because model files
    are environment-specific and callers may swap them.
    """
    import json

    meta = model_path.with_suffix(".json")
    if not meta.exists():
        raise FileNotFoundError(f"missing label metadata {meta}")
    with meta.open(encoding="utf-8") as fh:
        data = json.load(fh)
    labels = data.get("classes") or data.get("labels")
    if not labels:
        raise ValueError(f"no label list in {meta}")
    return list(labels)
