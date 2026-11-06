import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from file_sorter.window import COL_DESTINATION, COL_FILE, COL_INCLUDE, COL_MODIFIED, COL_SIZE, MainWindow


def test_window_opens_without_scanning(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(log_path=tmp_path / "runs.json")
    window.show()
    app.processEvents()

    assert window.isVisible()
    assert window.table.rowCount() == 0
    assert not window._move_button.isEnabled()
    window.close()


def test_scan_fills_the_table_and_moves_nothing(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "photo.png").write_bytes(b"png")
    (folder / "file.crdownload").write_bytes(b"partial")
    app = QApplication.instance() or QApplication([])
    window = MainWindow(log_path=tmp_path / "runs.json")
    window._folder_edit.setText(str(folder))

    window._scan()

    assert window.table.rowCount() == 2
    assert window.table.item(0, COL_FILE).text() == "file.crdownload"
    assert window.table.item(0, COL_INCLUDE).checkState().name == "Unchecked"
    assert window.table.item(1, COL_FILE).text() == "photo.png"
    assert window.table.item(1, COL_SIZE).text() == "3 B"
    modified = window.table.item(1, COL_MODIFIED).text()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", modified)
    assert window.table.item(1, COL_DESTINATION).text() == str(Path("Images") / "photo.png")
    assert (folder / "photo.png").exists()
    assert not (folder / "Images").exists()
    window.close()


def test_hide_skipped_drops_partial_downloads_from_the_table(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "photo.png").write_bytes(b"png")
    (folder / "file.crdownload").write_bytes(b"partial")
    app = QApplication.instance() or QApplication([])
    window = MainWindow(log_path=tmp_path / "runs.json")
    window.show()
    window._folder_edit.setText(str(folder))
    window._scan()

    window._hide_skipped.setChecked(True)
    app.processEvents()

    assert window.table.rowCount() == 1
    assert window.table.item(0, COL_FILE).text() == "photo.png"
    assert (folder / "file.crdownload").read_bytes() == b"partial"
    assert (folder / "photo.png").exists()
    assert not (folder / "Images").exists()
    window.close()


def test_clearing_a_category_unchecks_its_rows(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "photo.png").write_bytes(b"png")
    (folder / "file.crdownload").write_bytes(b"partial")
    app = QApplication.instance() or QApplication([])
    window = MainWindow(log_path=tmp_path / "runs.json")
    window.show()
    window._folder_edit.setText(str(folder))
    window._scan()
    app.processEvents()

    images = window._category_boxes["Images"]
    images.setCheckState(Qt.CheckState.Unchecked)
    images.clicked.emit()
    app.processEvents()

    assert window.table.item(1, COL_INCLUDE).checkState().name == "Unchecked"
    assert not window._move_button.isEnabled()
    assert (folder / "photo.png").exists()
    assert not (folder / "Images").exists()
    window.close()


def test_mixed_checks_in_a_category_show_partial(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "a.png").write_bytes(b"a")
    (folder / "b.png").write_bytes(b"b")
    app = QApplication.instance() or QApplication([])
    window = MainWindow(log_path=tmp_path / "runs.json")
    window.show()
    window._folder_edit.setText(str(folder))
    window._scan()

    window.table.item(0, COL_INCLUDE).setCheckState(Qt.CheckState.Unchecked)
    app.processEvents()

    assert window._category_boxes["Images"].checkState().name == "PartiallyChecked"
    assert window._move_button.isEnabled()
    assert (folder / "a.png").exists()
    window.close()
