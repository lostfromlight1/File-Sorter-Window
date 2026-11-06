from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
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
    move_summary,
    undo_latest,
    undo_summary,
)
from file_sorter.rules import Rules, load_rules

COL_INCLUDE = 0
COL_FILE = 1
COL_SIZE = 2
COL_MODIFIED = 3
COL_DESTINATION = 4
COL_STATUS = 5
_CATEGORY_COLUMNS = 4


def format_size(size_bytes: int | None) -> str:
    if size_bytes is None or size_bytes < 0:
        return ""
    value = float(size_bytes)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def format_modified(modified: datetime | None) -> str:
    if modified is None:
        return ""
    return modified.strftime("%Y-%m-%d %H:%M")


class MainWindow(QMainWindow):
    def __init__(
        self,
        rules_path: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("File Sorter")
        self.resize(980, 560)
        self._log_path = log_path or default_log_path()
        self._rows: list[PreviewRow] = []
        self._visible: list[int] = []
        self._category_boxes: dict[str, QCheckBox] = {}
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

        self._category_layout = QGridLayout()
        self._category_layout.setContentsMargins(0, 0, 0, 0)
        self._hide_skipped = QCheckBox("Hide skipped")
        self._hide_skipped.toggled.connect(self._on_hide_skipped)
        filter_row = QHBoxLayout()
        filter_row.addLayout(self._category_layout, stretch=1)
        filter_row.addWidget(self._hide_skipped)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Include", "File", "Size", "Modified", "Destination", "Status"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(COL_FILE, 200)
        self.table.setColumnWidth(COL_SIZE, 80)
        self.table.setColumnWidth(COL_MODIFIED, 140)
        self.table.setColumnWidth(COL_DESTINATION, 280)
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
        layout.addLayout(filter_row)
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
        self._rebuild_category_checks()
        self._fill_table(folder)
        movable = sum(1 for row in self._rows if row.movable)
        skipped = len(self._rows) - movable
        self._status.setText(f"{movable} files can move. {skipped} skipped.")
        self._refresh_buttons()

    def _fill_table(self, folder: Path) -> None:
        self._visible = self._visible_indexes()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._visible))
        for table_row, index in enumerate(self._visible):
            row = self._rows[index]
            include = QTableWidgetItem()
            include.setCheckState(
                Qt.CheckState.Checked if row.checked else Qt.CheckState.Unchecked
            )
            flags = Qt.ItemFlag.ItemIsUserCheckable
            if row.movable:
                flags |= Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            include.setFlags(flags)
            self.table.setItem(table_row, COL_INCLUDE, include)

            name = QTableWidgetItem(row.source.name)
            size = QTableWidgetItem(format_size(row.size_bytes))
            modified = QTableWidgetItem(format_modified(row.modified))
            destination = QTableWidgetItem(self._destination_text(row, folder))
            status = QTableWidgetItem(row.status)
            text_flags = (
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if row.movable
                else Qt.ItemFlag.NoItemFlags
            )
            for item in (name, size, modified, destination, status):
                item.setFlags(text_flags)
            self.table.setItem(table_row, COL_FILE, name)
            self.table.setItem(table_row, COL_SIZE, size)
            self.table.setItem(table_row, COL_MODIFIED, modified)
            self.table.setItem(table_row, COL_DESTINATION, destination)
            self.table.setItem(table_row, COL_STATUS, status)
        self.table.blockSignals(False)

    def _visible_indexes(self) -> list[int]:
        indexes: list[int] = []
        for index, row in enumerate(self._rows):
            if self._hide_skipped.isChecked() and not row.movable:
                continue
            indexes.append(index)
        return indexes

    def _destination_text(self, row: PreviewRow, folder: Path) -> str:
        if row.destination is None:
            return ""
        try:
            return str(row.destination.relative_to(folder.resolve()))
        except ValueError:
            return str(row.destination)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != COL_INCLUDE:
            return
        table_row = item.row()
        if table_row >= len(self._visible):
            return
        row = self._rows[self._visible[table_row]]
        if not row.movable:
            return
        row.checked = item.checkState() == Qt.CheckState.Checked
        self._sync_category_checks()
        self._refresh_buttons()

    def _on_hide_skipped(self, _checked: bool) -> None:
        if not self._rows:
            return
        self._fill_table(Path(self._folder_edit.text().strip()))

    def _on_category_clicked(self, category: str) -> None:
        box = self._category_boxes.get(category)
        if box is None:
            return
        check = box.checkState() != Qt.CheckState.Unchecked
        for row in self._rows:
            if row.movable and row.category == category:
                row.checked = check
        self._fill_table(Path(self._folder_edit.text().strip()))
        self._sync_category_checks()
        self._refresh_buttons()

    def _rebuild_category_checks(self) -> None:
        self._clear_category_checks()
        present = {row.category for row in self._rows if row.movable and row.category}
        placed = 0
        for category in self._category_order():
            if category not in present:
                continue
            box = QCheckBox(category)
            box.setTristate(True)
            box.clicked.connect(
                lambda _checked=False, name=category: self._on_category_clicked(name)
            )
            row = placed // _CATEGORY_COLUMNS
            column = placed % _CATEGORY_COLUMNS
            self._category_layout.addWidget(box, row, column)
            self._category_boxes[category] = box
            placed += 1
        self._sync_category_checks()

    def _clear_category_checks(self) -> None:
        while self._category_layout.count():
            item = self._category_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._category_boxes.clear()

    def _sync_category_checks(self) -> None:
        for category, box in self._category_boxes.items():
            rows = [
                row for row in self._rows if row.movable and row.category == category
            ]
            if not rows:
                continue
            checked = sum(1 for row in rows if row.checked)
            if checked == len(rows):
                state = Qt.CheckState.Checked
            elif checked == 0:
                state = Qt.CheckState.Unchecked
            else:
                state = Qt.CheckState.PartiallyChecked
            box.blockSignals(True)
            box.setCheckState(state)
            box.blockSignals(False)

    def _category_order(self) -> list[str]:
        if self._rules is None:
            return []
        ordered: list[str] = []
        names = [category.folder for category in self._rules.categories]
        names.append(self._rules.fallback)
        for name in names:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _move(self) -> None:
        chosen = [row for row in self._rows if row.checked and row.movable]
        if not chosen:
            return
        folder = Path(self._folder_edit.text().strip())
        answer = QMessageBox.question(
            self,
            "Move files",
            move_summary(self._rows, folder, self._category_order()),
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
        if latest_move_count(self._log_path) == 0:
            self._refresh_buttons()
            return
        answer = QMessageBox.question(
            self,
            "Undo",
            undo_summary(self._log_path),
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
