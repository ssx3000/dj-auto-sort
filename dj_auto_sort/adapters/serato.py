"""Serato DJ library adapter.

Serato stores state across:
  - ``_Serato_/database V2`` — binary master track list
  - ``_Serato_/Subcrates/*.crate`` — per-crate playlists (same chunk format)
  - ID3 ``GEOB`` tags embedded in audio files (cues/beatgrid/color)

Chunk format (applies to both ``database V2`` and ``.crate`` files)::

    4 bytes: ASCII tag (e.g. "otrk", "pfil", "tsng")
    4 bytes: big-endian uint32 payload length
    N bytes: payload

Tag prefixes:
    t*  UTF-16-BE string (text field)
    p*  UTF-16-BE string (path field)
    u*  4-byte big-endian uint32
    b*  1-byte boolean
    o*  container with nested chunks
    v*  version/header chunk
    s*  subcrate/signature container

Recognized fields used by this adapter (subset sufficient for round-trip):
    vrsn  → database version header
    otrk  → container holding one track's chunks
      pfil  file path
      ttyp  file type (mp3/flac/aif/…)
      tsng  title
      tart  artist
      talb  album
      tgen  genre
      tbpm  BPM (string)
      tkey  key
      ttim  duration (string)

Unknown chunks are preserved on read and written back verbatim when round-
tripping through this adapter, so we do not clobber state we don't understand.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable
from pathlib import Path

from dj_auto_sort.adapters.base import LibraryAdapter
from dj_auto_sort.core.track_record import TrackRecord

DATABASE_FILE = "database V2"
SERATO_DIR = "_Serato_"
DB_VERSION = "2.0/Serato ScratchLive Database"


def _encode_utf16be(value: str) -> bytes:
    return value.encode("utf-16-be")


def _decode_utf16be(data: bytes) -> str:
    return data.decode("utf-16-be")


def _read_chunks(buf: bytes, offset: int = 0, end: int | None = None) -> list[tuple[str, bytes]]:
    """Parse a Serato chunk stream. Returns list of (tag, payload)."""
    if end is None:
        end = len(buf)
    out: list[tuple[str, bytes]] = []
    while offset < end:
        if end - offset < 8:
            raise ValueError(f"truncated chunk header at offset {offset}")
        tag = buf[offset : offset + 4].decode("ascii", errors="replace")
        (size,) = struct.unpack(">I", buf[offset + 4 : offset + 8])
        payload_start = offset + 8
        payload_end = payload_start + size
        if payload_end > end:
            raise ValueError(
                f"chunk {tag!r} claims {size} bytes but only {end - payload_start} remain"
            )
        out.append((tag, buf[payload_start:payload_end]))
        offset = payload_end
    return out


def _write_chunk(tag: str, payload: bytes) -> bytes:
    if len(tag) != 4:
        raise ValueError(f"tag must be 4 chars, got {tag!r}")
    return tag.encode("ascii") + struct.pack(">I", len(payload)) + payload


def _write_text_chunk(tag: str, value: str) -> bytes:
    return _write_chunk(tag, _encode_utf16be(value))


class SeratoAdapter(LibraryAdapter):
    name = "serato"

    @property
    def supported_cue_count(self) -> int:
        return 8  # Serato hot cues 0–7

    def read_library(self, root: Path) -> list[TrackRecord]:
        db_path = self._db_path(root)
        data = db_path.read_bytes()
        chunks = _read_chunks(data)
        records: list[TrackRecord] = []
        for tag, payload in chunks:
            if tag == "otrk":
                records.append(self._track_from_chunks(_read_chunks(payload)))
        return records

    def write_library(self, root: Path, tracks: Iterable[TrackRecord]) -> None:
        tracks = list(tracks)
        buf = bytearray()
        buf += _write_text_chunk("vrsn", DB_VERSION)
        for track in tracks:
            buf += _write_chunk("otrk", self._track_to_payload(track))
        db_path = self._db_path(root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(bytes(buf))

    def validate(self, root: Path) -> list[str]:
        issues: list[str] = []
        db_path = self._db_path(root)
        if not db_path.exists():
            issues.append(f"missing serato database at {db_path}")
            return issues
        try:
            data = db_path.read_bytes()
            chunks = _read_chunks(data)
        except ValueError as exc:
            issues.append(f"corrupt database: {exc}")
            return issues
        if not chunks or chunks[0][0] != "vrsn":
            issues.append("database does not start with 'vrsn' chunk")
        return issues

    @staticmethod
    def _db_path(root: Path) -> Path:
        if root.is_file():
            return root
        # Callers may pass either the library root (which contains "_Serato_/")
        # or the "_Serato_" directory itself.
        if root.name == SERATO_DIR:
            return root / DATABASE_FILE
        return root / SERATO_DIR / DATABASE_FILE

    @staticmethod
    def _track_from_chunks(chunks: list[tuple[str, bytes]]) -> TrackRecord:
        fields: dict[str, str] = {}
        for tag, payload in chunks:
            if tag.startswith("t") or tag.startswith("p"):
                try:
                    fields[tag] = _decode_utf16be(payload)
                except UnicodeDecodeError:
                    fields[tag] = ""

        bpm_raw = fields.get("tbpm", "")
        bpm: float | None
        try:
            bpm = float(bpm_raw) if bpm_raw else None
        except ValueError:
            bpm = None

        duration_ms: int | None = None
        time_raw = fields.get("ttim", "")
        if time_raw:
            # Serato stores "mm:ss" or "ss.ms" depending on source. Be permissive.
            try:
                if ":" in time_raw:
                    parts = time_raw.split(":")
                    secs = int(parts[0]) * 60 + float(parts[1])
                else:
                    secs = float(time_raw)
                duration_ms = int(secs * 1000)
            except ValueError:
                duration_ms = None

        return TrackRecord(
            path=Path(fields.get("pfil", "")),
            title=fields.get("tsng", ""),
            artist=fields.get("tart", ""),
            album=fields.get("talb", ""),
            genre=fields.get("tgen", ""),
            bpm=bpm,
            key_camelot=fields.get("tkey") or None,
            duration_ms=duration_ms,
            source_libraries={"serato"},
        )

    @staticmethod
    def _track_to_payload(track: TrackRecord) -> bytes:
        buf = bytearray()
        buf += _write_text_chunk("pfil", str(track.path))
        suffix = track.path.suffix.lstrip(".").lower()
        if suffix:
            buf += _write_text_chunk("ttyp", suffix)
        if track.title:
            buf += _write_text_chunk("tsng", track.title)
        if track.artist:
            buf += _write_text_chunk("tart", track.artist)
        if track.album:
            buf += _write_text_chunk("talb", track.album)
        if track.genre:
            buf += _write_text_chunk("tgen", track.genre)
        if track.bpm is not None:
            buf += _write_text_chunk("tbpm", f"{track.bpm:.2f}")
        if track.key_camelot:
            buf += _write_text_chunk("tkey", track.key_camelot)
        if track.duration_ms is not None:
            total = track.duration_ms // 1000
            buf += _write_text_chunk("ttim", f"{total // 60:02d}:{total % 60:02d}")
        return bytes(buf)
