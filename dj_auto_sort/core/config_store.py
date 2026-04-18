"""Persist :class:`Config` across app launches via QSettings.

QSettings uses the Windows registry by default; we accept an injected
``QSettings`` in every function so tests can point at an ``IniFormat`` file
in a tmp dir and avoid touching the real registry.

Paths are serialized as strings (``""`` for None) because QSettings/QVariant
does not round-trip ``pathlib.Path`` reliably across platforms. ``set``s are
stored as sorted lists for the same reason.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from dj_auto_sort.core.config import Config

ORGANIZATION = "NovaGrid"
APPLICATION = "DJ Auto-Sort"

_PATH_KEYS = (
    "music_root",
    "rekordbox_xml_path",
    "serato_root",
    "virtualdj_database_path",
    "organize_root",
)


def default_settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


def save_config(config: Config, settings: QSettings | None = None) -> None:
    s = settings or default_settings()
    s.setValue("music_root", _path_to_str(config.music_root))
    s.setValue("rekordbox_xml_path", _path_to_str(config.rekordbox_xml_path))
    s.setValue("serato_root", _path_to_str(config.serato_root))
    s.setValue("virtualdj_database_path", _path_to_str(config.virtualdj_database_path))
    s.setValue("organize_root", _path_to_str(config.organize_root))
    s.setValue("folder_template", config.folder_template)
    s.setValue("backup_before_write", config.backup_before_write)
    s.setValue("enabled_adapters", sorted(config.enabled_adapters))
    s.sync()


def load_config(settings: QSettings | None = None) -> Config:
    s = settings or default_settings()
    default = Config()
    return Config(
        music_root=_str_to_path(s.value("music_root", "")),
        rekordbox_xml_path=_str_to_path(s.value("rekordbox_xml_path", "")),
        serato_root=_str_to_path(s.value("serato_root", "")),
        virtualdj_database_path=_str_to_path(s.value("virtualdj_database_path", "")),
        organize_root=_str_to_path(s.value("organize_root", "")),
        folder_template=str(s.value("folder_template", default.folder_template)),
        backup_before_write=_coerce_bool(
            s.value("backup_before_write", default.backup_before_write)
        ),
        enabled_adapters=_coerce_adapter_set(s.value("enabled_adapters", None), default),
    )


def has_saved_config(settings: QSettings | None = None) -> bool:
    """True if any config key has ever been written. Drives the first-run prompt."""
    s = settings or default_settings()
    return any(s.contains(key) for key in _all_keys())


def _all_keys() -> tuple[str, ...]:
    return (
        *_PATH_KEYS,
        "folder_template",
        "backup_before_write",
        "enabled_adapters",
    )


def _path_to_str(path: Path | None) -> str:
    return str(path) if path is not None else ""


def _str_to_path(value: object) -> Path | None:
    text = str(value) if value is not None else ""
    text = text.strip()
    return Path(text) if text else None


def _coerce_bool(value: object) -> bool:
    # QSettings returns booleans as "true"/"false" strings on some platforms.
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _coerce_adapter_set(value: object, default: Config) -> set[str]:
    if value is None:
        return set(default.enabled_adapters)
    if isinstance(value, str):
        # QSettings collapses a single-element list into a bare string.
        return {value} if value else set()
    if isinstance(value, (list, tuple)):
        return {str(v) for v in value if v}
    return set(default.enabled_adapters)


__all__ = [
    "APPLICATION",
    "ORGANIZATION",
    "default_settings",
    "has_saved_config",
    "load_config",
    "save_config",
]
