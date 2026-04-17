"""Virtual DJ library adapter.

Parses ``%APPDATA%\\VirtualDJ\\database.xml``. The format is::

    <VirtualDJ_Database Version="2024">
      <Song FilePath="C:\\Music\\track.mp3" FileSize="8500000">
        <Tags Author="Artist" Title="Title" Album="..." Genre="..."
              Bpm="0.46875" Key="8A"/>
        <Infos SongLength="240" Bitrate="320"/>
        <Scan Version="..." Bpm="0.46875"/>
        <Poi Pos="0.0" Type="cue" Num="0"/>
        <Poi Pos="15.5" Type="cue" Num="1" Name="Drop"/>
      </Song>
    </VirtualDJ_Database>

Note: VDJ stores BPM as *seconds per beat* (60 / bpm). We normalize on read
and denormalize on write so ``TrackRecord.bpm`` is always BPM in the usual sense.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from lxml import etree

from dj_auto_sort.adapters.base import LibraryAdapter
from dj_auto_sort.core.track_record import CuePoint, TrackRecord


def _vdj_bpm_encode(bpm: float) -> str:
    return f"{60.0 / bpm:.8f}"


def _vdj_bpm_decode(raw: str) -> float | None:
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    if val <= 0:
        return None
    return 60.0 / val


class VirtualDJAdapter(LibraryAdapter):
    name = "virtualdj"

    @property
    def supported_cue_count(self) -> int:
        return 16  # Virtual DJ supports 16 hot cues

    def read_library(self, root: Path) -> list[TrackRecord]:
        xml_path = self._xml_path(root)
        tree = etree.parse(str(xml_path))
        records: list[TrackRecord] = []
        for song in tree.iterfind(".//Song"):
            records.append(self._track_from_xml(song))
        return records

    def write_library(self, root: Path, tracks: Iterable[TrackRecord]) -> None:
        tracks = list(tracks)
        db = etree.Element("VirtualDJ_Database", Version="2024")
        for track in tracks:
            db.append(self._xml_from_track(track))
        xml_path = self._xml_path(root)
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        etree.ElementTree(db).write(
            str(xml_path),
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    def validate(self, root: Path) -> list[str]:
        issues: list[str] = []
        xml_path = self._xml_path(root)
        if not xml_path.exists():
            issues.append(f"missing virtualdj database at {xml_path}")
            return issues
        try:
            tree = etree.parse(str(xml_path))
        except etree.XMLSyntaxError as exc:
            issues.append(f"invalid XML: {exc}")
            return issues
        if tree.getroot().tag != "VirtualDJ_Database":
            issues.append(f"unexpected root element: {tree.getroot().tag}")
        return issues

    @staticmethod
    def _xml_path(root: Path) -> Path:
        if root.is_file():
            return root
        return root / "database.xml"

    def _track_from_xml(self, el: etree._Element) -> TrackRecord:
        path = Path(el.get("FilePath", "") or "")
        tags = el.find("Tags")
        infos = el.find("Infos")
        scan = el.find("Scan")

        tg = tags.attrib if tags is not None else {}
        bpm = _vdj_bpm_decode(tg.get("Bpm", ""))
        if bpm is None and scan is not None:
            bpm = _vdj_bpm_decode(scan.get("Bpm", ""))

        duration_ms: int | None = None
        if infos is not None and infos.get("SongLength"):
            duration_ms = int(float(infos.get("SongLength", "0")) * 1000)

        cues: list[CuePoint] = []
        for poi in el.iterfind("Poi"):
            if (poi.get("Type") or "cue") != "cue":
                continue
            pos = float(poi.get("Pos", "0") or 0)
            num = int(poi.get("Num", "0") or 0)
            cues.append(
                CuePoint(
                    index=num,
                    position_ms=int(pos * 1000),
                    label=poi.get("Name", "") or "",
                )
            )

        return TrackRecord(
            path=path,
            title=tg.get("Title", ""),
            artist=tg.get("Author", ""),
            album=tg.get("Album", ""),
            genre=tg.get("Genre", ""),
            bpm=bpm,
            key_camelot=tg.get("Key") or None,
            duration_ms=duration_ms,
            cues=cues,
            source_libraries={"virtualdj"},
        )

    def _xml_from_track(self, track: TrackRecord) -> etree._Element:
        song = etree.Element("Song", FilePath=str(track.path))
        tag_attrs: dict[str, str] = {}
        if track.artist:
            tag_attrs["Author"] = track.artist
        if track.title:
            tag_attrs["Title"] = track.title
        if track.album:
            tag_attrs["Album"] = track.album
        if track.genre:
            tag_attrs["Genre"] = track.genre
        if track.bpm is not None:
            tag_attrs["Bpm"] = _vdj_bpm_encode(track.bpm)
        if track.key_camelot:
            tag_attrs["Key"] = track.key_camelot
        if tag_attrs:
            etree.SubElement(song, "Tags", **tag_attrs)

        if track.duration_ms is not None:
            etree.SubElement(
                song,
                "Infos",
                SongLength=f"{track.duration_ms / 1000:.2f}",
            )
        if track.bpm is not None:
            etree.SubElement(song, "Scan", Bpm=_vdj_bpm_encode(track.bpm))

        for cue in track.cues[: self.supported_cue_count]:
            attrs = {
                "Pos": f"{cue.position_ms / 1000:.3f}",
                "Type": "cue",
                "Num": str(cue.index),
            }
            if cue.label:
                attrs["Name"] = cue.label
            etree.SubElement(song, "Poi", **attrs)
        return song
