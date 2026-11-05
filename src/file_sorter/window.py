from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_sorter.actions import (
    PreviewRow,
    apply_preview,
    build_preview,
    default_log_path,
    has_undo,
    latest_move_count,
    undo_latest,
)
from file_sorter.rules import Rules, load_rules


class MainWindow(QMainWindow):
    def __init__(
        self,
        rules_path: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("File Sorter")
        self.resize(900, 520)
        self._log_path = log_path or default_log_path()
        self._rows: list[PreviewRow] = []
        self._rules_error = ""
        try:
            self._rules: Rules | None = load_rules(rules_path)
        except ValueError as exc:
            self._rules = None
            self._rules_error = str(exc)

        self._folder_edit = QLineEdit(str(Path.home() / "Downloads"))
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        scan = QPushButton("Scan")
        scan.clicked.connect(self._scan)
        self._move_button = QPushButton("Move")
        self._move_button.clicked.connect(self._move)
        self._undo_button = QPushButton("Undo")
        self._undo_button.clicked.connect(self._undo)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self._folder_edit, stretch=1)
        folder_row.addWidget(browse)
        folder_row.addWidget(scan)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Include", "File", "Destination", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 320)
        self.table.itemChanged.connect(self._on_item_changed)

        action_row = QHBoxLayout()
        action_row.addWidget(self._move_button)
        action_row.addWidget(self._undo_button)
        action_row.addStretch(1)

        self._status = QLabel("Choose a folder and scan. Nothing moves until you confirm.")
        if self._rules_error:
            self._status.setText(self._rules_error)

        layout = QVBoxLayout()
        layout.addLayout(folder_row)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(action_row)
        layout.addWidget(self._status)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self._refresh_buttons()

    def _browse(self) -> None:
        current = self._folder_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder", current)
        if chosen:
            self._folder_edit.setText(chosen)

    def _scan(self) -> None:
        if self._rules is None:
            QMessageBox.warning(self, "Cannot scan", self._rules_error or "Rules are missing.")
            return
        folder = Path(self._folder_edit.text().strip())
        try:
            self._rows = build_preview(folder, self._rules)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Cannot scan", str(exc))
            return
        self._fill_table(folder)
        movable = sum(1 for row in self._rows if row.movable)
        skipped = len(self._rows) - movable
        self._status.setText(f"{movable} files can move. {skipped} skipped.")
        self._refresh_buttons()

    def _fill_table(self, folder: Path) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            include = QTableWidgetItem()
            include.setCheckState(
                Qt.CheckState.Checked if row.checked else Qt.CheckState.Unchecked
            )
            flags = Qt.ItemFlag.ItemIsUserCheckable
            if row.movable:
                flags |= Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            include.setFlags(flags)
            self.table.setItem(index, 0, include)

            name = QTableWidgetItem(row.source.name)
            destination = QTableWidgetItem(self._destination_text(row, folder))
            status = QTableWidgetItem(row.status)
            text_flags = (
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if row.movable
                else Qt.ItemFlag.NoItemFlags
            )
            for item in (name, destination, status):
                item.setFlags(text_flags)
            self.table.setItem(index, 1, name)
            self.table.setItem(index, 2, destination)
            self.table.setItem(index, 3, status)
        self.table.blockSignals(False)

    def _destination_text(self, row: PreviewRow, folder: Path) -> str:
        if row.destination is None:
            return ""
        try:
            return str(row.destination.relative_to(folder.resolve()))
        except ValueError:
            return str(row.destination)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        index = item.row()
        if index >= len(self._rows) or not self._rows[index].movable:
            return
        self._rows[index].checked = item.checkState() == Qt.CheckState.Checked
        self._refresh_buttons()

    def _move(self) -> None:
        chosen = [row for row in self._rows if row.checked and row.movable]
        if not chosen:
            return
        folder = Path(self._folder_edit.text().strip())
        answer = QMessageBox.question(
            self,
            "Move files",
            f"Move {len(chosen)} files into subfolders of {folder}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = apply_preview(self._rows, folder, self._log_path)
        if result.errors:
            details = "\n".join(f"{path.name}: {message}" for path, message in result.errors)
            QMessageBox.warning(self, "Some files were not moved", details)
        moved = len(result.moved)
        self._scan()
        self._status.setText(f"Moved {moved} files. {self._status.text()}")

    def _undo(self) -> None:
        count = latest_move_count(self._log_path)
        if count == 0:
            self._refresh_buttons()
            return
        answer = QMessageBox.question(
            self,
            "Undo",
            f"Put {count} files back?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = undo_latest(self._log_path)
        if result.errors:
            QMessageBox.warning(self, "Undo was incomplete", "\n".join(result.errors))
        restored = len(result.restored)
        self._scan()
        self._status.setText(f"Restored {restored} files. {self._status.text()}")

    def _refresh_buttons(self) -> None:
        selected = any(row.checked and row.movable for row in self._rows)
        self._move_button.setEnabled(selected)
        self._undo_button.setEnabled(has_undo(self._log_path))


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
