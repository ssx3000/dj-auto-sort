"""Rekordbox library adapter (XML export/import path).

Rekordbox 6+ uses an encrypted SQLite ``master.db`` we deliberately do not touch.
We read/write via Rekordbox's XML export format (File > Export Collection in xml).

The XML structure is roughly::

    <DJ_PLAYLISTS Version="1.0.0">
      <PRODUCT Name="rekordbox" Version="..." Company="Pioneer DJ"/>
      <COLLECTION Entries="N">
        <TRACK TrackID="1" Name="..." Artist="..." Album="..." Genre="..."
               TotalTime="240" AverageBpm="128.00" Tonality="8A"
               Location="file://localhost/C:/Music/track.mp3">
          <POSITION_MARK Name="Drop" Type="0" Start="15.5" Num="0"/>
        </TRACK>
      </COLLECTION>
      <PLAYLISTS><NODE Type="0" Name="ROOT" Count="0"/></PLAYLISTS>
    </DJ_PLAYLISTS>
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from lxml import etree

from dj_auto_sort.adapters.base import LibraryAdapter
from dj_auto_sort.core.track_record import CuePoint, TrackRecord


def _location_to_path(location: str) -> Path:
    """Convert a Rekordbox ``Location`` URI (``file://localhost/C:/...``) to a Path."""
    parsed = urlparse(location)
    raw = unquote(parsed.path)
    # On Windows, Rekordbox emits "/C:/Music/track.mp3" — strip the leading slash.
    if len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)


def _path_to_location(path: Path) -> str:
    """Convert a Path to a Rekordbox ``Location`` URI."""
    as_posix = path.as_posix()
    # Windows paths like "C:/Music/track.mp3" → "file://localhost/C:/Music/track.mp3"
    if len(as_posix) >= 2 and as_posix[1] == ":":
        as_posix = "/" + as_posix
    return "file://localhost" + quote(as_posix, safe="/:")


class RekordboxAdapter(LibraryAdapter):
    name = "rekordbox"

    @property
    def supported_cue_count(self) -> int:
        return 8  # Rekordbox hot cues A–H

    def read_library(self, root: Path) -> list[TrackRecord]:
        xml_path = self._xml_path(root)
        tree = etree.parse(str(xml_path))
        records: list[TrackRecord] = []
        for track_el in tree.iterfind(".//COLLECTION/TRACK"):
            records.append(self._track_from_xml(track_el))
        return records

    def write_library(self, root: Path, tracks: Iterable[TrackRecord]) -> None:
        tracks = list(tracks)
        root_el = etree.Element("DJ_PLAYLISTS", Version="1.0.0")
        etree.SubElement(
            root_el,
            "PRODUCT",
            Name="rekordbox",
            Version="6.0.0",
            Company="Pioneer DJ",
        )
        collection = etree.SubElement(root_el, "COLLECTION", Entries=str(len(tracks)))
        for i, track in enumerate(tracks, start=1):
            collection.append(self._xml_from_track(track, track_id=i))
        playlists = etree.SubElement(root_el, "PLAYLISTS")
        etree.SubElement(playlists, "NODE", Type="0", Name="ROOT", Count="0")

        xml_path = self._xml_path(root)
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        tree = etree.ElementTree(root_el)
        tree.write(
            str(xml_path),
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    def validate(self, root: Path) -> list[str]:
        issues: list[str] = []
        xml_path = self._xml_path(root)
        if not xml_path.exists():
            issues.append(f"missing rekordbox xml at {xml_path}")
            return issues
        try:
            tree = etree.parse(str(xml_path))
        except etree.XMLSyntaxError as exc:
            issues.append(f"invalid XML: {exc}")
            return issues
        if tree.getroot().tag != "DJ_PLAYLISTS":
            issues.append(f"unexpected root element: {tree.getroot().tag}")
        return issues

    @staticmethod
    def _xml_path(root: Path) -> Path:
        """Rekordbox XML exports are arbitrary-named; accept either a file or dir."""
        if root.is_file():
            return root
        return root / "rekordbox.xml"

    @staticmethod
    def _track_from_xml(el: etree._Element) -> TrackRecord:
        def attr(name: str, default: str = "") -> str:
            return el.get(name, default) or default

        bpm_raw = attr("AverageBpm")
        bpm = float(bpm_raw) if bpm_raw else None
        total_time = attr("TotalTime")
        duration_ms = int(float(total_time) * 1000) if total_time else None

        cues: list[CuePoint] = []
        for mark in el.iterfind("POSITION_MARK"):
            start = float(mark.get("Start", "0") or 0)
            num_raw = mark.get("Num", "0") or "0"
            num = int(num_raw)
            cues.append(
                CuePoint(
                    index=num,
                    position_ms=int(start * 1000),
                    label=mark.get("Name", "") or "",
                )
            )

        return TrackRecord(
            path=_location_to_path(attr("Location")),
            title=attr("Name"),
            artist=attr("Artist"),
            album=attr("Album"),
            genre=attr("Genre"),
            bpm=bpm,
            key_camelot=attr("Tonality") or None,
            duration_ms=duration_ms,
            cues=cues,
            source_libraries={"rekordbox"},
        )

    def _xml_from_track(self, track: TrackRecord, *, track_id: int) -> etree._Element:
        attrs: dict[str, str] = {
            "TrackID": str(track_id),
            "Name": track.title,
            "Artist": track.artist,
            "Album": track.album,
            "Genre": track.genre,
            "Location": _path_to_location(track.path),
        }
        if track.bpm is not None:
            attrs["AverageBpm"] = f"{track.bpm:.2f}"
        if track.key_camelot:
            attrs["Tonality"] = track.key_camelot
        if track.duration_ms is not None:
            attrs["TotalTime"] = str(round(track.duration_ms / 1000))

        el = etree.Element("TRACK", **attrs)
        # Clamp cues to what Rekordbox supports
        for cue in track.cues[: self.supported_cue_count]:
            etree.SubElement(
                el,
                "POSITION_MARK",
                Name=cue.label,
                Type="0",
                Start=f"{cue.position_ms / 1000:.3f}",
                Num=str(cue.index),
            )
        return el
