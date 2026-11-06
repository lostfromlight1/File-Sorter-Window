from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PARTIAL_SUFFIXES = {".crdownload", ".part", ".tmp", ".download"}
JUNK_NAMES = {"desktop.ini", "thumbs.db"}

STATUS_READY = "Ready"
STATUS_PARTIAL = "Partial download"
STATUS_SKIPPED = "Skipped"
STATUS_OFFICE_LOCK = "Office lock file"
STATUS_HIDDEN = "Hidden file"
STATUS_LINK = "Link"
STATUS_IN_USE = "In use"


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    status: str
    size_bytes: int | None = None
    modified: datetime | None = None

    @property
    def movable(self) -> bool:
        return self.status == STATUS_READY


def scan_folder(folder: Path) -> list[ScannedFile]:
    root = folder.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    found: list[ScannedFile] = []
    with os.scandir(root) as listing:
        entries = sorted(listing, key=lambda entry: entry.name.lower())
        for entry in entries:
            if not _is_top_level_file(entry):
                continue
            path = Path(entry.path)
            size_bytes, modified = _file_facts(path)
            found.append(
                ScannedFile(
                    path=path,
                    status=status_for(path),
                    size_bytes=size_bytes,
                    modified=modified,
                )
            )
    return found


def status_for(path: Path) -> str:
    if path.is_symlink():
        return STATUS_LINK
    name = path.name
    if name.lower() in JUNK_NAMES:
        return STATUS_SKIPPED
    if name.startswith("~$"):
        return STATUS_OFFICE_LOCK
    if name.startswith("."):
        return STATUS_HIDDEN
    if path.suffix.lower() in PARTIAL_SUFFIXES:
        return STATUS_PARTIAL
    if _is_in_use(path):
        return STATUS_IN_USE
    return STATUS_READY


def _file_facts(path: Path) -> tuple[int | None, datetime | None]:
    try:
        info = path.stat()
    except OSError:
        return None, None
    return info.st_size, datetime.fromtimestamp(info.st_mtime)


def _is_top_level_file(entry: os.DirEntry[str]) -> bool:
    try:
        if entry.is_symlink():
            try:
                return not entry.is_dir(follow_symlinks=True)
            except OSError:
                return True
        if entry.is_dir(follow_symlinks=False):
            return False
        return entry.is_file(follow_symlinks=False)
    except OSError:
        return True


def _is_in_use(path: Path) -> bool:
    try:
        with path.open("rb"):
            pass
    except PermissionError:
        return True
    except OSError as exc:
        return getattr(exc, "winerror", None) in {32, 33}
    return False
