from __future__ import annotations

from dataclasses import dataclass
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

    @property
    def movable(self) -> bool:
        return self.status == STATUS_READY


def scan_folder(folder: Path) -> list[ScannedFile]:
    root = folder.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    found: list[ScannedFile] = []
    for entry in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if _is_unlisted_directory(entry):
            continue
        if not entry.is_file() and not entry.is_symlink():
            continue
        found.append(ScannedFile(path=entry, status=status_for(entry)))
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


def _is_unlisted_directory(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_in_use(path: Path) -> bool:
    try:
        with path.open("rb"):
            pass
    except PermissionError:
        return True
    except OSError as exc:
        return getattr(exc, "winerror", None) in {32, 33}
    return False
