"""Render a target path for a TrackRecord from a configurable template.

Template tokens (resolved case-insensitively, missing/blank tokens -> 'Unknown'):
  {genre} {artist} {album} {title} {bpm} {key} {energy} {mood}

The template defines the path *relative to* ``root``; the source file's
extension is always appended to the rendered leaf, so callers don't have to
remember to include it in the template.

Example::

    render_target_path(
        "{genre}/{artist} - {title}",
        track,
        root=Path("/music/sorted"),
    )
    # -> /music/sorted/House/Daft Punk - Around The World.mp3
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Formatter

from dj_auto_sort.core.track_record import TrackRecord

_UNKNOWN = "Unknown"

# Windows-forbidden chars plus control chars. Forward slash is allowed between
# template tokens as a path separator but must be stripped from *values* so a
# title like "AC/DC - Thunderstruck" doesn't invent a directory.
_UNSAFE_IN_VALUE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_VALID_TOKENS = {"genre", "artist", "album", "title", "bpm", "key", "energy", "mood"}


def render_target_path(template: str, track: TrackRecord, root: Path) -> Path:
    if not template.strip():
        raise ValueError("template rendered to an empty path")
    tokens = _token_values(track)
    rendered_parts: list[str] = []
    for raw_part in template.split("/"):
        if not raw_part.strip():
            continue
        rendered_parts.append(_render_part(raw_part, tokens))
    if not rendered_parts:
        raise ValueError("template rendered to an empty path")

    ext = track.path.suffix  # includes the leading dot, or '' if none
    leaf = rendered_parts[-1] + ext
    return root.joinpath(*rendered_parts[:-1], leaf)


def _render_part(part: str, tokens: dict[str, str]) -> str:
    formatter = Formatter()
    out: list[str] = []
    for literal, field_name, _format_spec, _conversion in formatter.parse(part):
        if literal:
            out.append(literal)
        if field_name is None:
            continue
        key = field_name.lower()
        if key not in _VALID_TOKENS:
            raise ValueError(
                f"unknown template token {{{field_name}}}; valid: "
                + ", ".join(sorted(_VALID_TOKENS))
            )
        out.append(tokens[key])
    joined = "".join(out).strip()
    return _sanitize(joined)


def _sanitize(value: str) -> str:
    cleaned = _UNSAFE_IN_VALUE.sub("_", value).strip(" .")
    return cleaned or _UNKNOWN


def _token_values(track: TrackRecord) -> dict[str, str]:
    def txt(v: str) -> str:
        return v.strip() or _UNKNOWN

    return {
        "genre": txt(track.genre),
        "artist": txt(track.artist),
        "album": txt(track.album),
        "title": txt(track.title) if track.title.strip() else track.path.stem,
        "mood": txt(track.mood),
        "bpm": f"{int(round(track.bpm))}" if track.bpm else _UNKNOWN,
        "key": track.key_camelot.strip() if track.key_camelot else _UNKNOWN,
        "energy": str(track.energy) if track.energy is not None else _UNKNOWN,
    }
