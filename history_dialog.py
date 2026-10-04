"""
History and Bookmarks Dialogs for AdBlock Browser.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class HistoryDialog(QDialog):
    url_selected = pyqtSignal(str)

    def __init__(self, bm_history_manager, parent=None):
        super().__init__(parent)
        self.bm_manager = bm_history_manager
        self.setWindowTitle("Verlauf - AdBlock Browser")
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Im Verlauf suchen...")
        self.search_input.textChanged.connect(self.populate_list)
        layout.addWidget(self.search_input)

        # List
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)

        # Actions
        btn_bar = QHBoxLayout()
        clear_btn = QPushButton("Verlauf leeren")
        clear_btn.setObjectName("dangerBtn")
        clear_btn.clicked.connect(self.on_clear_clicked)
        btn_bar.addWidget(clear_btn)

        btn_bar.addStretch()
        open_btn = QPushButton("Öffnen")
        open_btn.setObjectName("primaryBtn")
        open_btn.clicked.connect(self.on_open_clicked)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(open_btn)
        btn_bar.addWidget(close_btn)

        layout.addLayout(btn_bar)

        self.populate_list()

    def populate_list(self):
        query = self.search_input.text()
        entries = self.bm_manager.get_history(query)
        self.list_widget.clear()

        for entry in entries:
            title = entry.get("title", "")
            url = entry.get("url", "")
            time_str = entry.get("time", "")
            item = QListWidgetItem(f"[{time_str}]  {title}\n{url}")
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.list_widget.addItem(item)

    def on_open_clicked(self):
        item = self.list_widget.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.url_selected.emit(url)
            self.accept()

    def on_item_double_clicked(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        self.url_selected.emit(url)
        self.accept()

    def on_clear_clicked(self):
        res = QMessageBox.question(self, "Verlauf löschen", "Möchtest du den gesamten Browserverlauf wirklich löschen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            self.bm_manager.clear_history()
            self.populate_list()
