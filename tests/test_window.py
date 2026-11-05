from pathlib import Path

from PySide6.QtWidgets import QApplication

from file_sorter.window import MainWindow


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
    assert window.table.item(0, 1).text() == "file.crdownload"
    assert window.table.item(0, 0).checkState().name == "Unchecked"
    assert window.table.item(1, 1).text() == "photo.png"
    assert window.table.item(1, 2).text() == str(Path("Images") / "photo.png")
    assert (folder / "photo.png").exists()
    assert not (folder / "Images").exists()
    window.close()
