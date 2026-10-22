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
from PyQt6.QtGui import QColor

import icons
import theme
import os
import threading

class AdBlockDialog(QDialog):
    # Emitted from the update thread; Qt delivers it on the GUI thread.
    update_finished = pyqtSignal(bool)

    def __init__(self, filter_engine, current_url: str, tab_blocked_count: int, parent=None,
                 ad_logger=None, report_ad=None, accent=theme.ACCENTS[0][1], initial_tab: int = 0):
        super().__init__(parent)
        self.filter_engine = filter_engine
        self.current_url = current_url
        self.tab_blocked_count = tab_blocked_count
        self.ad_logger = ad_logger
        self.report_ad = report_ad
        self.accent = accent
        self.initial_tab = initial_tab
        self.settings_changed = False
        self.needs_reload = False
        self.update_finished.connect(self.on_update_finished)
        
        self.setWindowTitle("AdBlock Shield & Datenschutz")
        self.setMinimumSize(600, 500)
        self.resize(650, 520)

        self.setup_ui()

    def get_clean_host(self):
        url = self.current_url or ""
        if "://" in url:
            url = url.split("://")[1].split("/")[0]
        return url.split(":")[0]

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.pixmap("shield", self.accent, 32))
        head.addWidget(logo)
        title = QLabel("AdBlock Shield")
        title.setObjectName("dlgTitle")
        head.addWidget(title)
        head.addStretch()
        main_layout.addLayout(head)

        tabs = QTabWidget()
        tabs.addTab(self.create_overview_tab(), "Übersicht && Schutz")
        tabs.addTab(self.create_monitor_tab(), "Live-Monitor blockierter URLs")
        tabs.addTab(self.create_whitelist_tab(), "Ausnahmeliste (Whitelist)")
        if self.ad_logger:
            tabs.addTab(self.create_ad_log_tab(), "Werbe-Protokoll")

        main_layout.addWidget(tabs)
        tabs.setCurrentIndex(min(self.initial_tab, tabs.count() - 1))

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
        status_card.setObjectName("cardAccent" if is_enabled else "cardDanger")
        card_layout = QHBoxLayout(status_card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(14)
        badge = QLabel()
        badge.setPixmap(icons.pixmap("shield" if is_enabled else "shield-off",
                                     self.accent if is_enabled else theme.DANGER, 40))
        card_layout.addWidget(badge)
        texts = QVBoxLayout()
        status_title = QLabel("Werbe- und Trackingschutz ist AKTIV" if is_enabled else "Schutz für diese Seite ist PAUSIERT")
        status_title.setStyleSheet(f"font-family: Bahnschrift; font-size: 17px; font-weight: 600; "
                                   f"color: {theme.TEXT if is_enabled else theme.DANGER};")
        texts.addWidget(status_title)
        status_desc = QLabel(f"Aktuelle Seite: <b>{host or 'Neuer Tab'}</b>")
        status_desc.setObjectName("dlgSub")
        texts.addWidget(status_desc)
        card_layout.addLayout(texts, 1)

        layout.addWidget(status_card)

        # Stats Cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        for number, caption, name in ((self.tab_blocked_count, "Auf dieser Seite blockiert", "bigNumber"),
                                      (self.filter_engine.total_blocked, "Insgesamt blockiert", "bigNumberOk")):
            box = QFrame()
            box.setObjectName("card")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(18, 14, 18, 14)
            num = QLabel(f"{number:,}".replace(",", "."))
            num.setObjectName(name)
            cap = QLabel(caption)
            cap.setObjectName("dlgSub")
            bl.addWidget(num)
            bl.addWidget(cap)
            stats_layout.addWidget(box)

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

        # Twitch ad spoofing (off by default: it reports ads as watched with the viewer's login)
        self.spoof_check = QCheckBox("Twitch: blockierte Werbung als gesehen melden (Ad-Spoofing)")
        self.spoof_check.setChecked(self.filter_engine.ad_spoofing)
        self.spoof_check.setToolTip("Meldet Twitch mit deinem Konto Werbung als vollständig gesehen, die nie lief.\n"
                                    "Kann gegen die Nutzungsbedingungen von Twitch verstoßen. Wirkt sofort, ohne Neuladen.")
        self.spoof_check.toggled.connect(self.on_spoofing_toggled)
        ctrl_layout.addWidget(self.spoof_check)

        layout.addLayout(ctrl_layout)

        # Filter Update Button
        layout.addStretch()
        upd_layout = QHBoxLayout()
        self.update_btn = QPushButton("Filterlisten jetzt aktualisieren")
        self.update_btn.setIcon(icons.icon("reload", theme.TEXT, 16))
        self.update_btn.clicked.connect(self.on_update_clicked)
        self.update_status = QLabel("")
        self.update_status.setObjectName("dlgSub")
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
        self.needs_reload = True

    def on_global_toggled(self, checked: bool):
        self.filter_engine.is_enabled = checked
        self.filter_engine.save_config()
        self.settings_changed = True
        self.needs_reload = True

    def on_spoofing_toggled(self, checked: bool):
        self.filter_engine.ad_spoofing = checked
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
        lbl.setObjectName("dlgSub")
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

            time_item.setForeground(QColor(theme.MUTED))
            type_item.setForeground(QColor(self.accent))
            url_item.setForeground(QColor(theme.TEXT))

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
        lbl.setObjectName("dlgSub")
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
        problem_kinds = {"ad-visible", "manual", "stripped", "masked", "stalled", "adblock-warning", "backup-failed"}
        for row, e in enumerate(entries):
            items = [QTableWidgetItem(e.get("time", "")[5:]), QTableWidgetItem(e.get("site", "")),
                     QTableWidgetItem(e.get("summary", "")), QTableWidgetItem(e.get("incident") or "")]
            kind = e.get("kind")
            color = QColor(theme.DANGER if kind in problem_kinds else theme.MUTED if kind == "ad-visible-end" else theme.OK)
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
        lbl.setObjectName("dlgSub")
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
                    self.needs_reload = True
                    table.removeRow(table.row(selected[0]))
        btn_remove.clicked.connect(remove_selected)
        layout.addWidget(btn_remove)

        return widget
