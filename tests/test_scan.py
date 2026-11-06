import ctypes
from ctypes import wintypes
from pathlib import Path

import pytest

from file_sorter.scan import (
    STATUS_HIDDEN,
    STATUS_IN_USE,
    STATUS_LINK,
    STATUS_OFFICE_LOCK,
    STATUS_PARTIAL,
    STATUS_READY,
    STATUS_SKIPPED,
    scan_folder,
)


def test_subfolder_is_not_listed(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    nested = folder / "sub"
    nested.mkdir(parents=True)
    (nested / "secret.pdf").write_bytes(b"%PDF")
    (folder / "photo.png").write_bytes(b"png")

    names = [item.path.name for item in scan_folder(folder)]

    assert names == ["photo.png"]


def test_partial_junk_lock_and_hidden_files_are_not_movable(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "file.crdownload").write_bytes(b"partial")
    (folder / "desktop.ini").write_text("x", encoding="utf-8")
    (folder / "thumbs.db").write_bytes(b"db")
    (folder / "~$doc.docx").write_bytes(b"lock")
    (folder / ".secret").write_text("hidden", encoding="utf-8")
    (folder / "photo.png").write_bytes(b"png")

    by_name = {item.path.name: item for item in scan_folder(folder)}

    assert by_name["file.crdownload"].status == STATUS_PARTIAL
    assert by_name["desktop.ini"].status == STATUS_SKIPPED
    assert by_name["thumbs.db"].status == STATUS_SKIPPED
    assert by_name["~$doc.docx"].status == STATUS_OFFICE_LOCK
    assert by_name[".secret"].status == STATUS_HIDDEN
    assert by_name["photo.png"].status == STATUS_READY
    assert by_name["photo.png"].movable
    assert not any(
        by_name[name].movable
        for name in ("file.crdownload", "desktop.ini", "thumbs.db", "~$doc.docx", ".secret")
    )


def test_file_symlink_is_not_movable(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    real = folder / "real.txt"
    real.write_text("x", encoding="utf-8")
    link = folder / "link.txt"
    try:
        link.symlink_to(real)
    except OSError as exc:
        pytest.skip(str(exc))

    by_name = {item.path.name: item for item in scan_folder(folder)}

    assert by_name["link.txt"].status == STATUS_LINK
    assert not by_name["link.txt"].movable
    assert by_name["real.txt"].movable


def test_scan_records_size_and_modified_time(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "photo.png").write_bytes(b"png")

    item = scan_folder(folder)[0]

    assert item.size_bytes == 3
    assert item.modified is not None


def test_scan_keeps_a_file_when_stat_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    target = folder / "photo.png"
    target.write_bytes(b"png")
    original = Path.stat

    def guarded(self: Path, *args: object, **kwargs: object):
        if self == target:
            raise OSError("denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", guarded)

    item = scan_folder(folder)[0]

    assert item.path.name == "photo.png"
    assert item.status == STATUS_READY
    assert item.size_bytes is None
    assert item.modified is None


def test_exclusively_locked_file_is_not_movable(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    target = folder / "locked.txt"
    target.write_text("x", encoding="utf-8")
    handle = _lock_exclusively(target)
    if handle is None:
        pytest.skip("could not lock the file")
    try:
        rows = scan_folder(folder)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

    assert rows[0].status == STATUS_IN_USE
    assert not rows[0].movable


def _lock_exclusively(path: Path) -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,
        0,
        None,
        3,
        0x80,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if handle is None or int(handle) == int(invalid):
        return None
    return int(handle)
