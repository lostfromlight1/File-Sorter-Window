from pathlib import Path

import pytest

from file_sorter.actions import (
    apply_preview,
    build_preview,
    default_log_path,
    move_summary,
    path_key,
    undo_latest,
    undo_summary,
    unique_destination,
)
from file_sorter.rules import Category, Rules, load_rules


def test_preview_routes_known_and_unknown_files(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    (root / "photo.png").write_bytes(b"png")
    (root / "notes.txt").write_bytes(b"txt")

    by_name = {row.source.name: row for row in build_preview(root, load_rules())}

    assert by_name["photo.png"].destination == root / "Images" / "photo.png"
    assert by_name["notes.txt"].destination == root / "Others" / "notes.txt"
    assert by_name["photo.png"].checked
    assert by_name["notes.txt"].checked


def test_existing_destination_keeps_both_names(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    destination_dir = root / "Documents" / "PDF"
    destination_dir.mkdir(parents=True)
    (destination_dir / "report.pdf").write_bytes(b"old")
    (root / "report.pdf").write_bytes(b"new")

    rows = build_preview(root, load_rules())

    assert rows[0].destination == destination_dir / "report (1).pdf"
    assert (destination_dir / "report.pdf").read_bytes() == b"old"


def test_two_claims_for_the_same_name_keep_both(tmp_path: Path) -> None:
    directory = tmp_path / "PDF"
    reserved: set[str] = set()
    first = unique_destination(directory, "report.pdf", reserved)
    reserved.add(path_key(first))
    second = unique_destination(directory, "report.pdf", reserved)

    assert first.name == "report.pdf"
    assert second.name == "report (1).pdf"


def test_apply_moves_only_checked_rows_and_undo_restores_them(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    (root / "photo.png").write_bytes(b"png")
    (root / "report.pdf").write_bytes(b"pdf")
    (root / "notes.txt").write_bytes(b"txt")
    (root / "skip.crdownload").write_bytes(b"partial")
    nested = root / "sub"
    nested.mkdir()
    (nested / "secret.pdf").write_bytes(b"secret")
    rows = build_preview(root, load_rules())
    for row in rows:
        if row.source.name == "notes.txt" or not row.movable:
            row.checked = False
    log_path = tmp_path / "outside" / "runs.json"

    result = apply_preview(rows, root, log_path)

    assert (root / "Images" / "photo.png").read_bytes() == b"png"
    assert (root / "Documents" / "PDF" / "report.pdf").read_bytes() == b"pdf"
    assert (root / "notes.txt").read_bytes() == b"txt"
    assert (root / "skip.crdownload").read_bytes() == b"partial"
    assert (nested / "secret.pdf").read_bytes() == b"secret"
    assert root.resolve() not in log_path.resolve().parents
    assert len(result.moved) == 2

    undo_latest(log_path)

    assert (root / "photo.png").read_bytes() == b"png"
    assert (root / "report.pdf").read_bytes() == b"pdf"
    assert not (root / "Images").exists()
    assert not (root / "Documents").exists()
    assert not (root / "Others").exists()


def test_undo_does_not_remove_a_folder_that_already_had_files(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    images = root / "Images"
    images.mkdir()
    (images / "keep.txt").write_text("keep", encoding="utf-8")
    (root / "photo.png").write_bytes(b"png")
    rows = build_preview(root, load_rules())
    log_path = tmp_path / "outside" / "runs.json"

    apply_preview(rows, root, log_path)
    undo_latest(log_path)

    assert (images / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (root / "photo.png").read_bytes() == b"png"


def test_undo_keeps_a_new_file_that_reused_the_original_name(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    (root / "photo.png").write_bytes(b"png")
    rows = build_preview(root, load_rules())
    log_path = tmp_path / "outside" / "runs.json"
    apply_preview(rows, root, log_path)
    (root / "photo.png").write_bytes(b"new")

    undo_latest(log_path)

    assert (root / "photo.png").read_bytes() == b"new"
    assert (root / "photo (1).png").read_bytes() == b"png"


def test_category_that_escapes_the_folder_is_rejected(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    (root / "notes.txt").write_text("x", encoding="utf-8")
    rules = Rules(
        categories=(Category(folder="../outside", extensions=frozenset({"txt"})),),
        fallback="Others",
    )

    with pytest.raises(ValueError):
        build_preview(root, rules)


def test_preview_keeps_category_and_leaves_partial_downloads_uncategorized(
    tmp_path: Path,
) -> None:
    root = _inbox(tmp_path)
    (root / "photo.png").write_bytes(b"png")
    (root / "file.crdownload").write_bytes(b"partial")

    by_name = {row.source.name: row for row in build_preview(root, load_rules())}

    assert by_name["photo.png"].category == "Images"
    assert by_name["photo.png"].size_bytes == 3
    assert by_name["file.crdownload"].category == ""
    assert not by_name["file.crdownload"].checked


def test_move_summary_ignores_unchecked_rows_and_counts_renames(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    pdf_dir = root / "Documents" / "PDF"
    pdf_dir.mkdir(parents=True)
    (pdf_dir / "a.pdf").write_bytes(b"old")
    (root / "a.pdf").write_bytes(b"new")
    (root / "photo.png").write_bytes(b"png")
    (root / "shot.png").write_bytes(b"png")
    (root / "notes.txt").write_bytes(b"txt")
    rows = build_preview(root, load_rules())
    for row in rows:
        if row.source.name == "notes.txt":
            row.checked = False

    text = move_summary(rows, root, _category_order())

    assert text.startswith(f"Move 3 files into subfolders of {root}?")
    assert text.index("Images: 2") < text.index("Documents/PDF: 1")
    assert "Others" not in text
    assert "1 file will be renamed because that name already exists." in text


def test_undo_summary_lists_the_log_without_restoring(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    (root / "photo.png").write_bytes(b"png")
    (root / "report.pdf").write_bytes(b"pdf")
    rows = build_preview(root, load_rules())
    log_path = tmp_path / "outside" / "runs.json"
    apply_preview(rows, root, log_path)

    text = undo_summary(log_path)

    assert "Put 2 files back?" in text
    assert "photo.png -> photo.png" in text
    assert "report.pdf -> report.pdf" in text
    assert (root / "Images" / "photo.png").read_bytes() == b"png"
    assert not (root / "photo.png").exists()


def test_undo_summary_caps_the_listed_names(tmp_path: Path) -> None:
    root = _inbox(tmp_path)
    for index in range(16):
        (root / f"file{index:02d}.png").write_bytes(b"x")
    rows = build_preview(root, load_rules())
    log_path = tmp_path / "outside" / "runs.json"
    apply_preview(rows, root, log_path)

    text = undo_summary(log_path)

    assert "Put 16 files back?" in text
    assert text.count(" -> ") == 15
    assert text.endswith("and 1 more")
    assert (root / "Images" / "file00.png").exists()
    assert not (root / "file00.png").exists()


def test_default_log_lives_outside_downloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    log_path = default_log_path()

    assert log_path == tmp_path / "local" / "FileSorter" / "runs.json"
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        assert downloads.resolve() not in log_path.resolve().parents


def _category_order() -> list[str]:
    rules = load_rules()
    return [category.folder for category in rules.categories] + [rules.fallback]


def _inbox(tmp_path: Path) -> Path:
    folder = tmp_path / "inbox"
    folder.mkdir()
    return folder
