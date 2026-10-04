"""
Main Window for AdBlock Browser using Microsoft Edge WebView2.
Modern Chromium-styled tabbed browser with integrated Brave AdBlock engine,
Full Widevine DRM, PlayReady, H.264, AAC and hardware accelerated video support.
"""

import os
import re
import time
import urllib.parse
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLineEdit, QPushButton, QToolBar,
    QProgressBar, QLabel, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut

from filter_engine import FilterEngine, host_of
from browser_tab import BrowserTab
from bookmarks_history import BookmarksHistoryManager
from adblock_dialog import AdBlockDialog
from ad_logger import AdLogger
from filter_engine import DEFAULT_FILTER_SOURCES
from history_dialog import HistoryDialog

class MainWindow(QMainWindow):
    def __init__(self, data_dir: str, initial_url: str = None):
        super().__init__()
        self.data_dir = data_dir
        self.setWindowTitle("AdBlock Browser")
        self.resize(1280, 850)

        # Set application icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Page fullscreen state (video players etc.)
        self._page_fullscreen_tab = None
        self._chrome_visibility = []
        self._was_fullscreen = False
        self._was_maximized = False
        # ADBLOCK_HIDDEN_WINDOW: off-screen test mode, never change the real window state
        self._hidden_test_mode = bool(os.environ.get("ADBLOCK_HIDDEN_WINDOW"))

        # Core Engines
        self.filter_engine = FilterEngine(data_dir)
        self.bm_manager = BookmarksHistoryManager(data_dir)
        self.ad_logger = AdLogger(data_dir)
        self.ad_logger.environment.update(self._environment_info())

        # Setup modern dark stylesheet
        self.setup_stylesheet()

        # Build UI
        self.setup_ui()
        self.setup_shortcuts()

        # Open initial tab
        self.open_new_tab(initial_url)

    def setup_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QToolBar {
                background-color: #0f172a;
                border: none;
                spacing: 6px;
                padding: 4px 10px;
            }
            QTabWidget::pane {
                border: none;
                background-color: #0f172a;
            }
            QTabBar {
                background-color: #0b1120;
                qproperty-drawBase: 0;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                max-width: 220px;
                min-width: 100px;
                font-size: 13px;
                border: 1px solid #334155;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #0f172a;
                color: #f8fafc;
                border-top: 2px solid #38bdf8;
                font-weight: 500;
            }
            QTabBar::tab:hover:!selected {
                background-color: #334155;
                color: #cbd5e1;
            }
            QLineEdit#addressBar {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 18px;
                padding: 6px 14px;
                font-size: 13px;
                selection-background-color: #0284c7;
            }
            QLineEdit#addressBar:focus {
                border-color: #38bdf8;
                background-color: #0f172a;
            }
            QToolButton, QPushButton {
                background-color: transparent;
                color: #cbd5e1;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QToolButton:hover, QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            QToolButton:pressed, QPushButton:pressed {
                background-color: #1e293b;
            }
            QProgressBar {
                border: none;
                background-color: transparent;
                height: 2px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
            }
            #shieldBtn {
                background-color: rgba(16, 185, 129, 0.15);
                border: 1px solid #10b981;
                border-radius: 14px;
                color: #34d399;
                font-weight: 600;
                padding: 4px 10px;
                font-size: 12px;
            }
            #shieldBtn:hover {
                background-color: rgba(16, 185, 129, 0.3);
            }
            #bookmarkBar {
                background-color: #0f172a;
                border-bottom: 1px solid #1e293b;
                padding: 2px 10px;
            }
            #bookmarkBar QPushButton {
                font-size: 12px;
                padding: 4px 8px;
                color: #94a3b8;
            }
            #bookmarkBar QPushButton:hover {
                color: #f8fafc;
                background-color: #1e293b;
            }
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 0;
            }
        """)

    def setup_ui(self):
        # Central widget with tabs
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.root_layout = QVBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # 1. Main Navigation Toolbar
        self.nav_toolbar = QToolBar("Navigation", self)
        self.nav_toolbar.setMovable(False)
        self.addToolBar(self.nav_toolbar)

        # Back
        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("Zurück (Alt+Links)")
        self.btn_back.clicked.connect(self.navigate_back)
        self.nav_toolbar.addWidget(self.btn_back)

        # Forward
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip("Vorwärts (Alt+Rechts)")
        self.btn_forward.clicked.connect(self.navigate_forward)
        self.nav_toolbar.addWidget(self.btn_forward)

        # Reload
        self.btn_reload = QPushButton("🔄")
        self.btn_reload.setToolTip("Neu laden (F5)")
        self.btn_reload.clicked.connect(self.reload_current)
        self.nav_toolbar.addWidget(self.btn_reload)

        # Home
        self.btn_home = QPushButton("🏠")
        self.btn_home.setToolTip("Startseite (Alt+Pos1)")
        self.btn_home.clicked.connect(self.navigate_home)
        self.nav_toolbar.addWidget(self.btn_home)

        # Address bar
        self.ssl_label = QLabel(" 🔒 ")
        self.ssl_label.setStyleSheet("color: #10b981; font-size: 13px;")
        self.nav_toolbar.addWidget(self.ssl_label)

        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.setPlaceholderText("Webadresse oder Suchbegriff eingeben...")
        self.address_bar.returnPressed.connect(self.navigate_to_address)
        self.nav_toolbar.addWidget(self.address_bar)

        # Bookmark star button
        self.btn_star = QPushButton("☆")
        self.btn_star.setToolTip("Lesezeichen hinzufügen/entfernen (Strg+D)")
        self.btn_star.clicked.connect(self.toggle_current_bookmark)
        self.nav_toolbar.addWidget(self.btn_star)

        # AdBlock Shield button
        self.btn_shield = QPushButton("🛡️ 0")
        self.btn_shield.setObjectName("shieldBtn")
        self.btn_shield.setToolTip("AdBlock Shield & Datenschutz-Einstellungen")
        self.btn_shield.clicked.connect(self.open_shield_dialog)
        self.nav_toolbar.addWidget(self.btn_shield)

        # Menu button
        self.btn_menu = QPushButton("☰")
        self.btn_menu.setToolTip("Menü")
        self.btn_menu.clicked.connect(self.show_main_menu)
        self.nav_toolbar.addWidget(self.btn_menu)

        # 2. Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.root_layout.addWidget(self.progress_bar)

        # 3. Bookmarks Bar
        self.bookmarks_bar = QWidget()
        self.bookmarks_bar.setObjectName("bookmarkBar")
        self.bm_layout = QHBoxLayout(self.bookmarks_bar)
        self.bm_layout.setContentsMargins(10, 2, 10, 2)
        self.bm_layout.setSpacing(6)
        self.root_layout.addWidget(self.bookmarks_bar)
        self.update_bookmarks_bar()

        # 4. Tab Widget
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self.on_current_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # Add "+" button on tab bar
        self.btn_new_tab = QPushButton(" + ")
        self.btn_new_tab.setToolTip("Neuer Tab (Strg+T)")
        self.btn_new_tab.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px 10px; color: #94a3b8;")
        self.btn_new_tab.clicked.connect(lambda: self.open_new_tab())
        self.tabs.setCornerWidget(self.btn_new_tab, Qt.Corner.TopLeftCorner)

        self.root_layout.addWidget(self.tabs)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.open_new_tab())
        QShortcut(QKeySequence("Ctrl+W"), self, lambda: self.close_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Ctrl+Tab"), self, self.next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self.prev_tab)
        QShortcut(QKeySequence("Ctrl+L"), self, self.focus_address_bar)
        QShortcut(QKeySequence("Alt+D"), self, self.focus_address_bar)
        QShortcut(QKeySequence("Ctrl+R"), self, self.reload_current)
        QShortcut(QKeySequence("F5"), self, self.reload_current)
        QShortcut(QKeySequence("Ctrl+F5"), self, lambda: self.reload_current(bypass_cache=True))
        QShortcut(QKeySequence("Escape"), self, self.stop_or_exit_fullscreen)
        QShortcut(QKeySequence("Alt+Left"), self, self.navigate_back)
        QShortcut(QKeySequence("Alt+Right"), self, self.navigate_forward)
        QShortcut(QKeySequence("Alt+Home"), self, self.navigate_home)
        QShortcut(QKeySequence("Ctrl+H"), self, self.open_history_dialog)
        QShortcut(QKeySequence("Ctrl+D"), self, self.toggle_current_bookmark)
        QShortcut(QKeySequence("Ctrl+B"), self, self.toggle_bookmarks_bar)
        QShortcut(QKeySequence("Ctrl+F"), self, self.show_find_in_page)
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("F12"), self, self.open_devtools)
        QShortcut(QKeySequence("Ctrl++"), self, self.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.zoom_reset)

    # --- Tab Management ---
    def open_new_tab(self, url: str = None) -> BrowserTab:
        tab = BrowserTab(self.filter_engine, self, ad_logger=self.ad_logger)

        # Connect tab signals
        tab.title_changed.connect(lambda t: self.on_tab_title_changed(tab, t))
        tab.url_changed.connect(lambda u: self.on_tab_url_changed(tab, u))
        tab.load_progress.connect(lambda p: self.on_tab_load_progress(tab, p))
        tab.blocked_count_changed.connect(lambda c: self.on_tab_blocked_count_changed(tab, c))
        tab.new_tab_requested.connect(lambda u: self.open_new_tab(u))
        tab.shortcut_pressed.connect(self.handle_shortcut)
        tab.fullscreen_requested.connect(lambda on: self.on_tab_fullscreen_requested(tab, on))
        tab.close_requested.connect(lambda: self.close_tab(self.tabs.indexOf(tab)))

        idx = self.tabs.addTab(tab, "Neuer Tab")
        self.tabs.setCurrentIndex(idx)

        if url and url != "about:start":
            tab.load(url)
        else:
            tab.load_start_page()

        return tab

    def close_tab(self, index: int):
        if index < 0:
            return
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            if self._page_fullscreen_tab is widget:
                self.on_tab_fullscreen_requested(widget, False)
            self.tabs.removeTab(index)
            widget.dispose()
            widget.deleteLater()
        else:
            tab = self.get_current_tab()
            if tab:
                tab.load_start_page()

    def get_current_tab(self) -> BrowserTab:
        return self.tabs.currentWidget()

    def next_tab(self):
        idx = (self.tabs.currentIndex() + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(idx)

    def prev_tab(self):
        idx = (self.tabs.currentIndex() - 1) % self.tabs.count()
        self.tabs.setCurrentIndex(idx)

    def on_current_tab_changed(self, index: int):
        tab = self.get_current_tab()
        if not tab:
            return
        self.update_address_bar(tab.current_url_str)
        self.update_shield_badge(tab.blocked_count)
        self.update_bookmark_star(tab.current_url_str)

    def on_tab_title_changed(self, tab: BrowserTab, title: str):
        idx = self.tabs.indexOf(tab)
        if idx != -1:
            short_title = title if len(title) <= 22 else title[:20] + "..."
            self.tabs.setTabText(idx, short_title or "Unbenannt")
            self.tabs.setTabToolTip(idx, title)

        if tab == self.get_current_tab():
            self.setWindowTitle(f"{title} - AdBlock Browser" if title else "AdBlock Browser")
            if tab.current_url_str and not tab.current_url_str.startswith("about:"):
                self.bm_manager.add_history(title, tab.current_url_str)

    def on_tab_url_changed(self, tab: BrowserTab, url: str):
        if tab == self.get_current_tab():
            self.update_address_bar(url)
            self.update_bookmark_star(url)

    def on_tab_load_progress(self, tab: BrowserTab, progress: int):
        if tab == self.get_current_tab():
            if progress < 100:
                self.progress_bar.show()
                self.progress_bar.setValue(progress)
                self.btn_reload.setText("✕")
                self.btn_reload.setToolTip("Laden anhalten (Esc)")
            else:
                self.progress_bar.hide()
                self.btn_reload.setText("🔄")
                self.btn_reload.setToolTip("Neu laden (F5)")

    def on_tab_blocked_count_changed(self, tab: BrowserTab, count: int):
        if tab == self.get_current_tab():
            self.update_shield_badge(count)

    def update_shield_badge(self, count: int):
        tab = self.get_current_tab()
        host = host_of(tab.current_url_str) if tab and "://" in tab.current_url_str else ""

        is_whitelisted = self.filter_engine.is_domain_whitelisted(host)
        if not self.filter_engine.is_enabled or is_whitelisted:
            self.btn_shield.setText("🛡️ AUS")
            self.btn_shield.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.15);
                border: 1px solid #ef4444;
                border-radius: 14px;
                color: #f87171;
                font-weight: 600;
                padding: 4px 10px;
                font-size: 12px;
            """)
        else:
            self.btn_shield.setText(f"🛡️ {count}")
            self.btn_shield.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                border: 1px solid #10b981;
                border-radius: 14px;
                color: #34d399;
                font-weight: 600;
                padding: 4px 10px;
                font-size: 12px;
            """)

    def update_address_bar(self, url_str: str):
        if not url_str or url_str == "about:start":
            self.address_bar.setText("")
            self.ssl_label.setText(" 🏠 ")
            self.ssl_label.setStyleSheet("color: #38bdf8;")
        else:
            self.address_bar.setText(url_str)
            if url_str.startswith("https://"):
                self.ssl_label.setText(" 🔒 ")
                self.ssl_label.setStyleSheet("color: #10b981;")
            else:
                self.ssl_label.setText(" 🌐 ")
                self.ssl_label.setStyleSheet("color: #94a3b8;")

    # --- Navigation ---
    def navigate_to_address(self):
        tab = self.get_current_tab()
        if not tab:
            return

        text = self.address_bar.text().strip()
        if not text:
            return

        if text.startswith(("http://", "https://", "about:", "file://", "edge://")):
            dest = text
        elif re.match(r"^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?(/.*)?$", text):
            dest = "http://" + text
        elif "." in text and " " not in text:
            dest = "https://" + text
        else:
            dest = "https://duckduckgo.com/?q=" + urllib.parse.quote(text)

        tab.load(dest)

    def navigate_back(self):
        tab = self.get_current_tab()
        if tab:
            tab.back()

    def navigate_forward(self):
        tab = self.get_current_tab()
        if tab:
            tab.forward()

    def reload_current(self, bypass_cache: bool = False):
        tab = self.get_current_tab()
        if tab:
            if self.progress_bar.isVisible() and not bypass_cache:
                tab.stop()
            else:
                tab.reload(bypass_cache)

    def stop_or_exit_fullscreen(self):
        tab = self.get_current_tab()
        if self.isFullScreen():
            self.toggle_fullscreen()
        elif tab and self.progress_bar.isVisible():
            tab.stop()

    def navigate_home(self):
        tab = self.get_current_tab()
        if tab:
            tab.load_start_page()

    # --- Bookmarks ---
    def update_bookmarks_bar(self):
        while self.bm_layout.count():
            item = self.bm_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bookmarks = self.bm_manager.get_bookmarks()
        for b in bookmarks:
            btn = QPushButton(b["title"])
            url_str = b["url"]
            btn.clicked.connect(lambda checked, u=url_str: self.load_url_in_current_tab(u))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, u=url_str: self.show_bookmark_context_menu(pos, u))
            self.bm_layout.addWidget(btn)

        self.bm_layout.addStretch()

    def load_url_in_current_tab(self, url_str: str):
        tab = self.get_current_tab()
        if tab:
            tab.load(url_str)

    def show_bookmark_context_menu(self, pos, url_str):
        menu = QMenu(self)
        del_act = menu.addAction("Lesezeichen löschen")
        action = menu.exec(self.bookmarks_bar.mapToGlobal(pos))
        if action == del_act:
            self.bm_manager.remove_bookmark(url_str)
            self.update_bookmarks_bar()

    def toggle_bookmarks_bar(self):
        self.bookmarks_bar.setVisible(not self.bookmarks_bar.isVisible())

    def toggle_current_bookmark(self):
        tab = self.get_current_tab()
        if not tab:
            return
        url = tab.current_url_str
        title = tab.current_title_str or url
        if not url or url.startswith("about:"):
            return

        self.bm_manager.toggle_bookmark(title, url)
        self.update_bookmark_star(url)
        self.update_bookmarks_bar()

    def update_bookmark_star(self, url: str):
        if self.bm_manager.is_bookmarked(url):
            self.btn_star.setText("★")
            self.btn_star.setStyleSheet("color: #facc15; font-size: 15px;")
        else:
            self.btn_star.setText("☆")
            self.btn_star.setStyleSheet("color: #cbd5e1; font-size: 15px;")

    # --- Shield Dialog ---
    def open_shield_dialog(self):
        tab = self.get_current_tab()
        url = tab.current_url_str if tab else ""
        count = tab.blocked_count if tab else 0
        dlg = AdBlockDialog(self.filter_engine, url, count, self, ad_logger=self.ad_logger,
                            report_ad=self.report_ad)
        dlg.exec()
        if dlg.settings_changed:
            for i in range(self.tabs.count()):
                self.tabs.widget(i).refresh_site_scripts()
        if tab:
            if dlg.settings_changed and "://" in url:
                tab.reload()
            self.update_shield_badge(tab.blocked_count)

    # --- History & Find ---
    def open_history_dialog(self):
        dlg = HistoryDialog(self.bm_manager, self)
        dlg.url_selected.connect(self.load_url_in_current_tab)
        dlg.exec()

    def show_find_in_page(self):
        tab = self.get_current_tab()
        if tab:
            tab.show_find_bar()

    # --- DevTools & Zoom ---
    def open_devtools(self):
        tab = self.get_current_tab()
        if tab:
            tab.open_devtools()

    def toggle_fullscreen(self):
        tab = self._page_fullscreen_tab
        if tab is not None:
            # Leave the page's own fullscreen (e.g. video player) the way the page expects
            tab.wv.CoreWebView2.ExecuteScriptAsync("document.exitFullscreen && document.exitFullscreen()")
            return
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    def on_tab_fullscreen_requested(self, tab: BrowserTab, on: bool):
        """A page element (e.g. the video player) entered or left HTML5 fullscreen."""
        if on:
            if self._page_fullscreen_tab is not None or tab is not self.get_current_tab():
                return
            self._page_fullscreen_tab = tab
            self._chrome_visibility = [(w, w.isVisible()) for w in
                                       (self.nav_toolbar, self.bookmarks_bar, self.tabs.tabBar(), tab.find_bar)]
            for w, _ in self._chrome_visibility:
                w.hide()
            self.progress_bar.hide()
            self._was_fullscreen = self.isFullScreen()
            if not self._was_fullscreen and not self._hidden_test_mode:
                self._was_maximized = self.isMaximized()
                self.showFullScreen()
        else:
            if self._page_fullscreen_tab is not tab:
                return
            self._page_fullscreen_tab = None
            for w, visible in self._chrome_visibility:
                w.setVisible(visible)
            if not self._was_fullscreen and not self._hidden_test_mode:
                self.showMaximized() if self._was_maximized else self.showNormal()

    def handle_shortcut(self, action: str):
        """Shortcuts reported by a tab while the web page has keyboard focus."""
        actions = {
            "new_tab": lambda: self.open_new_tab(),
            "close_tab": lambda: self.close_tab(self.tabs.currentIndex()),
            "next_tab": self.next_tab,
            "prev_tab": self.prev_tab,
            "focus_address": self.focus_address_bar,
            "bookmark": self.toggle_current_bookmark,
            "history": self.open_history_dialog,
            "toggle_bookmarks_bar": self.toggle_bookmarks_bar,
            "home": self.navigate_home,
            "fullscreen": self.toggle_fullscreen,
        }
        fn = actions.get(action)
        if fn:
            fn()

    def focus_address_bar(self):
        self.activateWindow()
        self.address_bar.setFocus()
        self.address_bar.selectAll()

    def closeEvent(self, event):
        self.filter_engine.save_config()
        for i in range(self.tabs.count()):
            self.tabs.widget(i).dispose()
        super().closeEvent(event)

    def zoom_in(self):
        tab = self.get_current_tab()
        if tab:
            tab.set_zoom(min(tab.get_zoom() + 0.1, 3.0))

    def zoom_out(self):
        tab = self.get_current_tab()
        if tab:
            tab.set_zoom(max(tab.get_zoom() - 0.1, 0.3))

    def zoom_reset(self):
        tab = self.get_current_tab()
        if tab:
            tab.set_zoom(1.0)

    # --- Main Menu ---
    def show_main_menu(self):
        menu = QMenu(self)

        new_tab_act = menu.addAction("Neuer Tab\tStrg+T")
        new_tab_act.triggered.connect(lambda: self.open_new_tab())

        history_act = menu.addAction("Verlauf\tStrg+H")
        history_act.triggered.connect(self.open_history_dialog)

        bm_bar_act = menu.addAction("Lesezeichenleiste ein/aus\tStrg+B")
        bm_bar_act.triggered.connect(self.toggle_bookmarks_bar)

        menu.addSeparator()

        find_act = menu.addAction("Suchen auf der Seite\tStrg+F")
        find_act.triggered.connect(self.show_find_in_page)

        zoom_in_act = menu.addAction("Vergrößern\tStrg++")
        zoom_in_act.triggered.connect(self.zoom_in)

        zoom_out_act = menu.addAction("Verkleinern\tStrg+-")
        zoom_out_act.triggered.connect(self.zoom_out)

        zoom_reset_act = menu.addAction("Zoom zurücksetzen\tStrg+0")
        zoom_reset_act.triggered.connect(self.zoom_reset)

        menu.addSeparator()

        devtools_act = menu.addAction("Entwicklertools\tF12")
        devtools_act.triggered.connect(self.open_devtools)

        fullscreen_act = menu.addAction("Vollbildmodus\tF11")
        fullscreen_act.triggered.connect(self.toggle_fullscreen)

        menu.addSeparator()

        shield_act = menu.addAction("🛡️ AdBlock Einstellungen...")
        shield_act.triggered.connect(self.open_shield_dialog)

        report_act = menu.addAction("⚠️ Werbung auf dieser Seite melden")
        report_act.triggered.connect(self.report_ad)

        about_act = menu.addAction("Über AdBlock Browser")
        about_act.triggered.connect(self.show_about_dialog)

        menu.exec(self.btn_menu.mapToGlobal(self.btn_menu.rect().bottomRight()))

    def _environment_info(self) -> dict:
        lists = {}
        for src in DEFAULT_FILTER_SOURCES:
            path = os.path.join(self.filter_engine.filters_dir, src["filename"])
            if os.path.exists(path):
                lists[src["name"]] = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        return {"browser": "AdBlock Browser 2.2 (Claude-Variante)", "filterlisten": lists}

    def report_ad(self):
        tab = self.get_current_tab()
        if not tab or "://" not in tab.current_url_str:
            QMessageBox.information(self, "Werbung melden", "Auf dieser Seite gibt es nichts zu melden.")
            return
        folder = tab.report_ad_manually()
        if folder:
            QMessageBox.information(
                self, "Werbung melden",
                "Danke! Gespeichert mit Bildschirmfoto und den letzten Netzwerk-Anfragen:\n\n" + folder)

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "Über AdBlock Browser",
            "<h3>AdBlock Browser v2.1 (Powered by Edge WebView2)</h3>"
            "<p>Ein schneller, moderner Desktop-Browser mit integrierter "
            "<b>Brave AdBlock Rust-Engine</b> und nativer <b>Microsoft Edge WebView2</b>-Engine.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Vollständige Unterstützung für <b>Widevine DRM</b> und <b>H.264 / AAC</b></li>"
            "<li>SouthPark.de, YouTube, Netflix und Streaming laufen einwandfrei</li>"
            "<li>Filterung von EasyList, EasyPrivacy und EasyList Germany</li>"
            "<li>Kosmetische Filterung (Ausblenden von Werbeflächen)</li>"
            "<li>YouTube Werbe-Blockierung &amp; Überspringen</li>"
            "<li>Live-Statistiken &amp; Monitor blockierter Anfragen</li>"
            "<li>Ausnahmeliste (Whitelist) für einzelne Webseiten</li>"
            "<li>Tabs, Lesezeichen, Verlauf &amp; Entwicklertools</li>"
            "</ul>"
        )
