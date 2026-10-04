"""
AdBlock Shield Dialog and Live Request Monitor.
Displays statistics, site whitelist toggle, global toggle, filter update button, and blocked requests list.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QWidget, QFrame, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import os
import threading

class AdBlockDialog(QDialog):
    # Emitted from the update thread; Qt delivers it on the GUI thread.
    update_finished = pyqtSignal(bool)

    def __init__(self, filter_engine, current_url: str, tab_blocked_count: int, parent=None,
                 ad_logger=None, report_ad=None):
        super().__init__(parent)
        self.filter_engine = filter_engine
        self.current_url = current_url
        self.tab_blocked_count = tab_blocked_count
        self.ad_logger = ad_logger
        self.report_ad = report_ad
        self.settings_changed = False
        self.update_finished.connect(self.on_update_finished)
        
        self.setWindowTitle("AdBlock Shield & Datenschutz")
        self.setMinimumSize(600, 500)
        self.resize(650, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background: #1e293b;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #334155;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }
            QTableWidget {
                background-color: #1e293b;
                color: #e2e8f0;
                gridline-color: #334155;
                border: none;
                border-radius: 6px;
                selection-background-color: #38bdf8;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 8px;
                border: 1px solid #334155;
                font-weight: 600;
            }
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #475569;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #1e293b;
            }
            QCheckBox {
                color: #f8fafc;
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #64748b;
                background: #1e293b;
            }
            QCheckBox::indicator:checked {
                background: #10b981;
                border-color: #10b981;
            }
        """)

        self.setup_ui()

    def get_clean_host(self):
        url = self.current_url or ""
        if "://" in url:
            url = url.split("://")[1].split("/")[0]
        return url.split(":")[0]

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        tabs = QTabWidget()
        tabs.addTab(self.create_overview_tab(), "Übersicht & Schutz")
        tabs.addTab(self.create_monitor_tab(), "Live-Monitor blockierter URLs")
        tabs.addTab(self.create_whitelist_tab(), "Ausnahmeliste (Whitelist)")
        if self.ad_logger:
            tabs.addTab(self.create_ad_log_tab(), "Werbe-Protokoll")

        main_layout.addWidget(tabs)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

    def create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        # Shield status card
        host = self.get_clean_host()
        is_whitelisted = self.filter_engine.is_domain_whitelisted(host)
        is_enabled = self.filter_engine.is_enabled and not is_whitelisted

        status_card = QFrame()
        status_card.setStyleSheet(f"""
            QFrame {{
                background: {'rgba(16, 185, 129, 0.15)' if is_enabled else 'rgba(239, 68, 68, 0.15)'};
                border: 1px solid {'#10b981' if is_enabled else '#ef4444'};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        card_layout = QVBoxLayout(status_card)
        
        status_title = QLabel("🛡️ Werbe- und Trackingschutz ist AKTIV" if is_enabled else "⚠️ Schutz für diese Seite ist PAUSIERT")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        status_title.setFont(font)
        status_title.setStyleSheet(f"color: {'#34d399' if is_enabled else '#f87171'};")
        card_layout.addWidget(status_title)

        status_desc = QLabel(f"Aktuelle Seite: <b>{host or 'Neuer Tab'}</b>")
        status_desc.setStyleSheet("color: #cbd5e1; margin-top: 4px;")
        card_layout.addWidget(status_desc)

        layout.addWidget(status_card)

        # Stats Cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        # Tab stats
        tab_box = QFrame()
        tab_box.setStyleSheet("background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 12px;")
        tb_layout = QVBoxLayout(tab_box)
        tb_num = QLabel(str(self.tab_blocked_count))
        tb_num.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        tb_num.setStyleSheet("color: #38bdf8;")
        tb_lbl = QLabel("Auf dieser Seite blockiert")
        tb_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        tb_layout.addWidget(tb_num)
        tb_layout.addWidget(tb_lbl)
        stats_layout.addWidget(tab_box)

        # Total stats
        total_box = QFrame()
        total_box.setStyleSheet("background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 12px;")
        tot_layout = QVBoxLayout(total_box)
        tot_num = QLabel(str(self.filter_engine.total_blocked))
        tot_num.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        tot_num.setStyleSheet("color: #10b981;")
        tot_lbl = QLabel("Insgesamt blockiert")
        tot_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        tot_layout.addWidget(tot_num)
        tot_layout.addWidget(tot_lbl)
        stats_layout.addWidget(total_box)

        layout.addLayout(stats_layout)

        # Controls
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setSpacing(10)

        # Site toggle
        if host:
            self.site_check = QCheckBox(f"Werbeblocker auf '{host}' aktivieren")
            self.site_check.setChecked(not is_whitelisted)
            self.site_check.toggled.connect(self.on_site_toggled)
            ctrl_layout.addWidget(self.site_check)

        # Global toggle
        self.global_check = QCheckBox("Werbeblocker global einschalten")
        self.global_check.setChecked(self.filter_engine.is_enabled)
        self.global_check.toggled.connect(self.on_global_toggled)
        ctrl_layout.addWidget(self.global_check)

        layout.addLayout(ctrl_layout)

        # Filter Update Button
        layout.addStretch()
        upd_layout = QHBoxLayout()
        self.update_btn = QPushButton("🔄 Filterlisten jetzt aktualisieren")
        self.update_btn.clicked.connect(self.on_update_clicked)
        self.update_status = QLabel("")
        self.update_status.setStyleSheet("color: #94a3b8;")
        upd_layout.addWidget(self.update_btn)
        upd_layout.addWidget(self.update_status)
        upd_layout.addStretch()
        layout.addLayout(upd_layout)

        return widget

    def on_site_toggled(self, checked: bool):
        host = self.get_clean_host()
        if not host:
            return
        wl = self.filter_engine.whitelist
        if checked:
            # also drop parent-domain entries (e.g. "southpark.de" for "www.southpark.de")
            for w in [w for w in wl if host == w or host.endswith("." + w)]:
                wl.remove(w)
        else:
            wl.add(host)
        self.filter_engine.save_config()
        self.settings_changed = True

    def on_global_toggled(self, checked: bool):
        self.filter_engine.is_enabled = checked
        self.filter_engine.save_config()
        self.settings_changed = True

    def on_update_clicked(self):
        self.update_btn.setEnabled(False)
        self.update_status.setText("Aktualisiere Filterlisten...")

        def run_update():
            ok = self.filter_engine.update_filter_lists()
            self.update_finished.emit(ok)

        threading.Thread(target=run_update, daemon=True).start()

    def on_update_finished(self, ok: bool):
        self.update_btn.setEnabled(True)
        if ok:
            self.update_status.setText("✓ Filterlisten erfolgreich aktualisiert!")
        else:
            self.update_status.setText("⚠ Download fehlgeschlagen – vorhandene Listen werden weiter benutzt.")

    def create_monitor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        lbl = QLabel("Live-Aufzeichnung der zuletzt blockierten Werbe- und Tracker-Anfragen:")
        lbl.setStyleSheet("color: #94a3b8; margin-bottom: 8px;")
        layout.addWidget(lbl)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Uhrzeit", "Typ", "Blockierte URL / Domain"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)

        blocks = list(reversed(self.filter_engine.recent_blocks))
        table.setRowCount(len(blocks))

        for row, item in enumerate(blocks):
            time_item = QTableWidgetItem(item.get("time", ""))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item = QTableWidgetItem(item.get("type", "").upper())
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            url_item = QTableWidgetItem(item.get("url", ""))

            time_item.setForeground(QColor("#94a3b8"))
            type_item.setForeground(QColor("#38bdf8"))
            url_item.setForeground(QColor("#f87171"))

            table.setItem(row, 0, time_item)
            table.setItem(row, 1, type_item)
            table.setItem(row, 2, url_item)

        layout.addWidget(table)
        return widget

    def create_ad_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        lbl = QLabel("Was der Blocker bei Video-Werbung erlebt hat. Rot = Werbung kam durch "
                     "(Vorfall mit Bildschirmfoto und Netzwerk-Anfragen gespeichert).")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #94a3b8; margin-bottom: 8px;")
        layout.addWidget(lbl)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Zeit", "Seite", "Ereignis", "Vorfall-Ordner"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)

        entries = self.ad_logger.recent_entries()
        table.setRowCount(len(entries))
        problem_kinds = {"ad-visible", "manual", "stripped", "masked", "adblock-warning", "backup-failed"}
        for row, e in enumerate(entries):
            items = [QTableWidgetItem(e.get("time", "")[5:]), QTableWidgetItem(e.get("site", "")),
                     QTableWidgetItem(e.get("summary", "")), QTableWidgetItem(e.get("incident") or "")]
            kind = e.get("kind")
            color = QColor("#f87171" if kind in problem_kinds else "#94a3b8" if kind == "ad-visible-end" else "#34d399")
            items[2].setForeground(color)
            for col, item in enumerate(items):
                item.setToolTip(e.get("url", ""))
                table.setItem(row, col, item)
        layout.addWidget(table)

        btns = QHBoxLayout()
        open_btn = QPushButton("📂 Protokoll-Ordner öffnen")
        open_btn.clicked.connect(lambda: os.startfile(self.ad_logger.dir))
        btns.addWidget(open_btn)
        if self.report_ad:
            report_btn = QPushButton("⚠️ Werbung auf dieser Seite melden")
            report_btn.clicked.connect(self._report_and_close)
            btns.addWidget(report_btn)
        btns.addStretch()
        layout.addLayout(btns)
        return widget

    def _report_and_close(self):
        self.accept()
        self.report_ad()

    def create_whitelist_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)

        lbl = QLabel("Webseiten auf der Ausnahmeliste (Werbeblocker ist hier pausiert):")
        lbl.setStyleSheet("color: #94a3b8; margin-bottom: 8px;")
        layout.addWidget(lbl)

        table = QTableWidget()
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["Domain"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)

        whitelist_list = list(self.filter_engine.whitelist)
        table.setRowCount(len(whitelist_list))
        for row, domain in enumerate(whitelist_list):
            item = QTableWidgetItem(domain)
            table.setItem(row, 0, item)

        layout.addWidget(table)

        btn_remove = QPushButton("Ausgewählte Domain von der Ausnahmeliste entfernen")
        def remove_selected():
            selected = table.selectedItems()
            if selected:
                d = selected[0].text()
                if d in self.filter_engine.whitelist:
                    self.filter_engine.whitelist.remove(d)
                    self.filter_engine.save_config()
                    self.settings_changed = True
                    table.removeRow(table.row(selected[0]))
        btn_remove.clicked.connect(remove_selected)
        layout.addWidget(btn_remove)

        return widget
