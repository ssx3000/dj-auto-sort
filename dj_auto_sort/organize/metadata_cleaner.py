"""Metadata cleanup: case normalization, junk-tag stripping, artist standardization.

Cleans the free-text fields on a :class:`TrackRecord` so downstream path
rendering produces consistent folder names. Does NOT touch analysis fields
(bpm/key/energy), file paths, or cue points.

Junk-tag stripping removes the common YouTube/rip tags that ship with many
downloaded tracks: ``[OFFICIAL VIDEO]``, ``(Official Audio)``, ``[HD]``,
``(Explicit)``, ``[Lyrics]``, ``(Free Download)``, etc. The patterns are
bracketed (``[...]`` / ``(...)``) so we never strip material that's part of
the actual title (e.g. Four Tet's "There Is Love In You").
"""

from __future__ import annotations

import re
from dataclasses import replace

from dj_auto_sort.core.track_record import TrackRecord

# Lowercase tag bodies we strip when they appear inside [] or (). Matched as
# whole-body equality after normalizing inner whitespace, so "Official Video"
# and "official   video" both hit.
_JUNK_TAG_BODIES = frozenset(
    {
        "official video",
        "official music video",
        "official audio",
        "official lyric video",
        "lyric video",
        "lyrics",
        "audio",
        "hd",
        "hq",
        "4k",
        "explicit",
        "clean",
        "free download",
        "free dl",
        "radio edit",  # keep remix/extended/etc — only kill the boring ones
    }
)

_BRACKET_RE = re.compile(r"\s*[\[\(]([^\[\]\(\)]*)[\]\)]\s*")
_WHITESPACE_RE = re.compile(r"\s+")
_FEAT_RE = re.compile(
    r"\b(feat\.?|ft\.?|featuring)\b\.?\s*",
    flags=re.IGNORECASE,
)


def clean(track: TrackRecord) -> TrackRecord:
    return replace(
        track,
        title=_clean_title(track.title),
        artist=_clean_artist(track.artist),
        album=_clean_text(track.album),
        genre=_clean_text(track.genre),
        mood=_clean_text(track.mood),
    )


def _clean_title(raw: str) -> str:
    stripped = _strip_junk_tags(raw)
    return _clean_text(stripped)


def _clean_artist(raw: str) -> str:
    if not raw:
        return ""
    # Normalize "feat" variants to "feat." regardless of input spelling so
    # "Artist FT other" and "artist featuring Other" collapse to the same
    # canonical form.
    normalized = _FEAT_RE.sub("feat. ", raw)
    return _clean_text(normalized)


def _clean_text(value: str) -> str:
    if not value:
        return ""
    collapsed = _WHITESPACE_RE.sub(" ", value).strip()
    return _title_case(collapsed)


def _strip_junk_tags(value: str) -> str:
    def _maybe_drop(match: re.Match[str]) -> str:
        body_normalized = _WHITESPACE_RE.sub(" ", match.group(1)).strip().lower()
        if body_normalized in _JUNK_TAG_BODIES:
            return " "
        return match.group(0)

    return _BRACKET_RE.sub(_maybe_drop, value)


# Small particles that stay lowercase inside a title unless they're the very
# first or last word. Intentionally conservative — DJs read these back as
# folder names, not prose.
_SMALL_WORDS = frozenset(
    {"a", "an", "the", "and", "but", "or", "nor", "for", "on", "at", "to", "of", "in"}
)


def _title_case(value: str) -> str:
    words = value.split(" ")
    out: list[str] = []
    for idx, word in enumerate(words):
        if not word:
            continue
        lower = word.lower()
        is_edge = idx == 0 or idx == len(words) - 1
        if lower in _SMALL_WORDS and not is_edge:
            out.append(lower)
            continue
        out.append(_capitalize_word(word))
    return " ".join(out)


def _capitalize_word(word: str) -> str:
    # Preserve leading/trailing punctuation (parens, brackets, quotes) and
    # only case the alphabetic core, so "(Alive" → "(Alive" not "(alive".
    leading_idx = 0
    while leading_idx < len(word) and not word[leading_idx].isalpha():
        leading_idx += 1
    trailing_idx = len(word)
    while trailing_idx > leading_idx and not word[trailing_idx - 1].isalpha():
        trailing_idx -= 1
    prefix = word[:leading_idx]
    core = word[leading_idx:trailing_idx]
    suffix = word[trailing_idx:]
    if not core:
        return word
    return prefix + _cap_core(core) + suffix


def _cap_core(core: str) -> str:
    # Preserve ALLCAPS acronyms up to 4 chars (DJ, MC, NYC, USSR) so
    # "DJ Snake" doesn't become "Dj Snake".
    if 1 <= len(core) <= 4 and core.isupper() and core.isalpha():
        return core
    # Handle hyphenated and apostrophe'd words piece-by-piece.
    if "-" in core:
        return "-".join(_cap_core(p) for p in core.split("-"))
    if "'" in core:
        head, _, tail = core.partition("'")
        # O'Brien, but don't uppercase 's in "Daft Punk's".
        tail_cased = tail.lower() if len(tail) <= 1 else tail[0].upper() + tail[1:].lower()
        return head[:1].upper() + head[1:].lower() + "'" + tail_cased
    return core[:1].upper() + core[1:].lower()
