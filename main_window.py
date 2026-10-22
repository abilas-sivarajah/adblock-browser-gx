"""
Main window of AdBlock Browser GX: frameless window with tabs in the title bar, sidebar,
navigation bar and the Microsoft Edge WebView2 pages (BrowserTab) underneath.
"""

import ctypes
import os
import sys
import time

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPoint, QProcess, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QCursor, QGuiApplication, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QGraphicsDropShadowEffect, QHBoxLayout, QLineEdit, QMainWindow,
                             QMenu, QMessageBox, QProgressBar, QPushButton, QStackedWidget, QTabBar,
                             QToolButton, QVBoxLayout, QWidget)

import icons
import native_frame
import omnibox
import theme
from ad_logger import AdLogger
from adblock_dialog import AdBlockDialog
from bookmarks_history import BookmarksHistoryManager
from browser_tab import BrowserTab
from design_dialog import DesignDialog
from filter_engine import DEFAULT_FILTER_SOURCES, FilterEngine, host_of
from gx_widgets import SideBar, TabArea, TitleBar
from history_dialog import HistoryDialog
from start_page import write_start_page

APP_NAME = "AdBlock Browser GX"
EDGE = 6  # px at the window border that resize the window (inside the window, nothing visible)

# sidebar shortcuts: open the site, or switch to a tab that already shows it
SITE_SHORTCUTS = {
    "twitch": ("twitch.tv", "https://www.twitch.tv"),
    "youtube": ("youtube.com", "https://www.youtube.com"),
    "discord": ("discord.com", "https://discord.com/app"),
}


class MainWindow(QMainWindow):
    def __init__(self, data_dir: str, initial_url: str = None, hw_accel: bool = None):
        super().__init__()
        self.data_dir = data_dir
        self.setWindowTitle(APP_NAME)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1360, 880)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Page fullscreen state (video players etc.)
        self._page_fullscreen_tab = None
        self._chrome_visibility = []
        self._was_fullscreen = False
        self._was_maximized = False
        self._loading = False
        # ADBLOCK_HIDDEN_WINDOW: off-screen test mode, never change the real window state
        self._hidden_test_mode = bool(os.environ.get("ADBLOCK_HIDDEN_WINDOW"))

        # Core Engines
        self.filter_engine = FilterEngine(data_dir)
        self.bm_manager = BookmarksHistoryManager(data_dir)
        self.ad_logger = AdLogger(data_dir)
        self.ad_logger.environment.update(self._environment_info())
        self.ui = theme.UISettings(data_dir)
        # GPU mode of this session (command-line flag or saved setting); a changed setting needs a restart
        self.hw_accel = bool(self.ui["hardware_acceleration"] if hw_accel is None else hw_accel)
        self.icon_files = icons.IconFiles(os.path.join(data_dir, "ui_cache", "icons"))

        self.setup_ui()
        self.apply_theme()
        self.setup_shortcuts()
        QApplication.instance().installEventFilter(self)  # clicks into inputs: see _reclaim_keyboard

        # Open initial tab
        self.open_new_tab(initial_url)

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        root = QWidget(self)
        root.setObjectName("gxRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 1. title bar with the tabs
        self.title_bar = TitleBar(self)
        self.title_bar.logo_clicked.connect(lambda: self.show_main_menu(self.title_bar.logo))
        self.title_bar.new_tab_clicked.connect(lambda: self.open_new_tab())
        self.title_bar.tab_bar.context_menu_requested.connect(self.show_tab_menu)
        outer.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        # 2. sidebar
        self.side_bar = SideBar(self)
        self.side_bar.triggered.connect(self.on_sidebar)
        body.addWidget(self.side_bar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        body.addLayout(right, 1)

        # 3. navigation bar
        self.nav_toolbar = QWidget(self)
        self.nav_toolbar.setObjectName("navBar")
        self.nav_toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.nav_toolbar.setFixedHeight(50)
        nav = QHBoxLayout(self.nav_toolbar)
        nav.setContentsMargins(10, 7, 12, 7)
        nav.setSpacing(4)

        self.btn_back = self._nav_button("Zurück (Alt+Links)", self.navigate_back)
        self.btn_forward = self._nav_button("Vorwärts (Alt+Rechts)", self.navigate_forward)
        self.btn_reload = self._nav_button("Neu laden (F5)", self.reload_current)
        self.btn_home = self._nav_button("Startseite (Alt+Pos1)", self.navigate_home)
        for b in (self.btn_back, self.btn_forward, self.btn_reload, self.btn_home):
            nav.addWidget(b)
        nav.addSpacing(6)

        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.setPlaceholderText("Mit Google suchen oder Webadresse eingeben")
        self.address_bar.setFixedHeight(36)
        self.address_bar.returnPressed.connect(self.navigate_to_address)
        self.omnibox = omnibox.Omnibox(self.address_bar, self.bm_manager, self)
        self.omnibox.open_url.connect(self.open_address)
        self.addr_icon = QAction(self.address_bar)
        self.address_bar.addAction(self.addr_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.star_action = QAction(self.address_bar)
        self.star_action.setToolTip("Lesezeichen hinzufügen/entfernen (Strg+D)")
        self.star_action.triggered.connect(self.toggle_current_bookmark)
        self.address_bar.addAction(self.star_action, QLineEdit.ActionPosition.TrailingPosition)
        nav.addWidget(self.address_bar, 1)
        nav.addSpacing(8)

        self.btn_shield = QPushButton("0")
        self.btn_shield.setObjectName("shieldBtn")
        self.btn_shield.setToolTip("AdBlock Shield – Statistik, Ausnahmen, Werbe-Protokoll")
        self.btn_shield.setIconSize(QSize(17, 17))
        self.btn_shield.setFixedHeight(32)
        self.btn_shield.clicked.connect(lambda: self.open_shield_dialog())
        self.shield_glow = QGraphicsDropShadowEffect(self.btn_shield)
        self.shield_glow.setOffset(0, 0)
        self.shield_glow.setBlurRadius(18)
        self.btn_shield.setGraphicsEffect(self.shield_glow)
        nav.addWidget(self.btn_shield)

        self.btn_menu = self._nav_button("Menü", lambda: self.show_main_menu(self.btn_menu))
        nav.addWidget(self.btn_menu)
        right.addWidget(self.nav_toolbar)

        # 4. bookmarks bar
        self.bookmarks_bar = QWidget()
        self.bookmarks_bar.setObjectName("bookmarkBar")
        self.bookmarks_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.bm_layout = QHBoxLayout(self.bookmarks_bar)
        self.bm_layout.setContentsMargins(10, 3, 10, 3)
        self.bm_layout.setSpacing(2)
        right.addWidget(self.bookmarks_bar)
        self.update_bookmarks_bar()

        # 5. loading line (always 2 px high, so pages do not jump)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("gxProgress")
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        right.addWidget(self.progress_bar)

        # 6. pages
        self.page_stack = QStackedWidget(self)
        right.addWidget(self.page_stack, 1)
        self.tabs = TabArea(self.title_bar.tab_bar, self.page_stack)
        self.tabs.currentChanged.connect(self.on_current_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)


    def _nav_button(self, tip, slot):
        b = QToolButton(self)
        b.setObjectName("navBtn")
        b.setToolTip(tip)
        b.setIconSize(QSize(19, 19))
        b.setFixedSize(34, 34)
        b.clicked.connect(slot)
        return b

    # ------------------------------------------------------------------ theme
    def apply_theme(self):
        accent = self.ui["accent"]
        QApplication.instance().setStyleSheet(theme.build_stylesheet(accent, self.icon_files))
        self.title_bar.apply_theme(accent)
        self.side_bar.apply_theme(accent)
        self.side_bar.setVisible(bool(self.ui["sidebar"]))
        self.bookmarks_bar.setVisible(bool(self.ui["bookmarks_bar"]))
        self.btn_back.setIcon(icons.icon("back", theme.MUTED, 19, theme.TEXT))
        self.btn_forward.setIcon(icons.icon("forward", theme.MUTED, 19, theme.TEXT))
        self.btn_home.setIcon(icons.icon("home", theme.MUTED, 19, theme.TEXT))
        self.btn_menu.setIcon(icons.icon("menu", theme.MUTED, 19, theme.TEXT))
        self._set_reload_icon()
        self.shield_glow.setColor(QColor(accent))
        self.omnibox.set_accent(accent)
        for i in range(self.tabs.count()):
            self._refresh_tab_icon(self.tabs.widget(i))
        tab = self.get_current_tab()
        if tab:
            self.update_address_bar(tab.current_url_str)
            self.update_bookmark_star(tab.current_url_str)
            self.update_shield_badge(tab.blocked_count)

    def on_design_changed(self):
        self.apply_theme()
        # start pages pick up the new accent / animation setting
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.current_url_str == "about:start":
                tab.load_start_page()

    def write_start_page(self, folder: str):
        write_start_page(folder, self.filter_engine.total_blocked, self.ui["accent"],
                         self.ad_logger.counts(), bool(self.ui["animations"]))

    # ------------------------------------------------------------------ window frame (Windows)
    def showEvent(self, e):
        super().showEvent(e)
        self._apply_native_frame()

    def _apply_native_frame(self):
        try:
            native_frame.apply(int(self.winId()))
        except Exception:
            pass

    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = native_frame.message(int(message))
            if msg.message == native_frame.WM_NCCALCSIZE:
                return True, sip.voidptr(0)  # nothing of the native frame is drawn: all client area
            if msg.message == native_frame.WM_NCHITTEST:
                hit = self._hit_test(msg.lParam)
                if hit:
                    return True, sip.voidptr(hit)  # PyQt6 wants the LRESULT as voidptr
        # not handled. (Calling the base class from Python crashes PyQt6 6.11 - and
        # QWidget::nativeEvent only returns false anyway.)
        return False, sip.voidptr(0)

    def _hit_test(self, lparam) -> int:
        """Tells Windows where the borders and the caption (empty title bar) are."""
        if self.isFullScreen():
            return 0
        x, y = native_frame.lparam_point(lparam)
        if not self.isMaximized():
            r = native_frame.window_rect(int(self.winId()))
            b = round(EDGE * self.devicePixelRatioF())
            left, right = x < r.left + b, x >= r.right - b
            top, bottom = y < r.top + b, y >= r.bottom - b
            if top or bottom or left or right:
                return {(True, False, True, False): native_frame.HTTOPLEFT,
                        (True, False, False, True): native_frame.HTTOPRIGHT,
                        (False, True, True, False): native_frame.HTBOTTOMLEFT,
                        (False, True, False, True): native_frame.HTBOTTOMRIGHT,
                        (True, False, False, False): native_frame.HTTOP,
                        (False, True, False, False): native_frame.HTBOTTOM,
                        (False, False, True, False): native_frame.HTLEFT,
                        (False, False, False, True): native_frame.HTRIGHT}.get((top, bottom, left, right), 0)
        if self.title_bar.isVisible():
            if self.title_bar.is_drag_area(self.title_bar.mapFromGlobal(self._logical_point(x, y))):
                return native_frame.HTCAPTION
        return 0

    def _logical_point(self, x: int, y: int) -> QPoint:
        """Physical screen pixels -> Qt coordinates (Qt keeps each screen's native origin)."""
        for screen in QGuiApplication.screens():
            g, r = screen.geometry(), screen.devicePixelRatio()
            if g.x() <= x < g.x() + g.width() * r and g.y() <= y < g.y() + g.height() * r:
                return QPoint(int(g.x() + (x - g.x()) / r), int(g.y() + (y - g.y()) / r))
        r = self.devicePixelRatioF()
        return QPoint(int(x / r), int(y / r))

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.WindowStateChange:
            QTimer.singleShot(0, self._after_state_change)

    def _after_state_change(self):
        if not self.isFullScreen():
            self._apply_native_frame()  # Qt replaces the window styles while in fullscreen
        self._fit_maximized()
        self.title_bar.update_max_icon()
        self._broadcast_resizable()

    def _fit_maximized(self):
        """Maximised, the (invisible) frame reaches past the screen edge - keep content inside."""
        if self.isMaximized() and not self.isFullScreen():
            dpr = self.devicePixelRatioF()
            l, t, r, b = (round(v / dpr) for v in native_frame.maximized_overhang(int(self.winId())))
            self.setContentsMargins(l, t, r, b)
        else:
            self.setContentsMargins(0, 0, 0, 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.isMaximized():
            self._fit_maximized()

    def _resizable(self) -> bool:
        return not (self.isMaximized() or self.isFullScreen() or self._page_fullscreen_tab is not None)

    def _broadcast_resizable(self):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_window_resizable(self._resizable())

    def start_edge_resize(self, edge: str):
        """A page reported a press on its right/bottom edge strip (scripts/window_edges.js)."""
        handle = self.windowHandle()
        if not self._resizable() or handle is None:
            return
        # pages could post this message themselves: only act when the cursor really is at the edge
        pos, g = QCursor.pos(), self.frameGeometry()
        edges = []
        if edge in ("right", "corner") and 0 <= g.right() - pos.x() <= 16:
            edges.append(Qt.Edge.RightEdge)
        if edge in ("bottom", "corner") and 0 <= g.bottom() - pos.y() <= 16:
            edges.append(Qt.Edge.BottomEdge)
        if edges:
            combined = edges[0]
            for e in edges[1:]:
                combined |= e
            handle.startSystemResize(combined)

    # ------------------------------------------------------------------ shortcuts
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

    # ------------------------------------------------------------------ tabs
    def open_new_tab(self, url: str = None) -> BrowserTab:
        tab = BrowserTab(self.filter_engine, self, ad_logger=self.ad_logger, start_page_writer=self.write_start_page,
                         hw_accel=self.hw_accel)

        tab.title_changed.connect(lambda t: self.on_tab_title_changed(tab, t))
        tab.url_changed.connect(lambda u: self.on_tab_url_changed(tab, u))
        tab.load_progress.connect(lambda p: self.on_tab_load_progress(tab, p))
        tab.blocked_count_changed.connect(lambda c: self.on_tab_blocked_count_changed(tab, c))
        tab.new_tab_requested.connect(lambda u: self.open_new_tab(u))
        tab.shortcut_pressed.connect(self.handle_shortcut)
        tab.fullscreen_requested.connect(lambda on: self.on_tab_fullscreen_requested(tab, on))
        tab.close_requested.connect(lambda: self.close_tab(self.tabs.indexOf(tab)))
        tab.favicon_changed.connect(lambda ic: self.on_tab_favicon(tab, ic))
        tab.audio_changed.connect(lambda playing, muted: self.on_tab_audio(tab, playing, muted))
        tab.edge_resize_requested.connect(self.start_edge_resize)
        tab.set_window_resizable(self._resizable())
        tab.favicon = QIcon()
        tab.audio_state = (False, False)

        idx = self.tabs.addTab(tab, "Neuer Tab")
        self.tabs.setCurrentIndex(idx)
        self._refresh_tab_icon(tab)

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
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % self.tabs.count())

    def prev_tab(self):
        self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % self.tabs.count())

    def on_current_tab_changed(self, index: int):
        tab = self.get_current_tab()
        if not tab:
            return
        self.omnibox.hide()
        # the hidden tab's page may keep the keyboard focus - typing would go nowhere
        focused = native_frame.focused_window()
        if focused and not native_frame.is_visible(focused):
            self._reclaim_keyboard()
        self.update_address_bar(tab.current_url_str, force=True)
        self.update_shield_badge(tab.blocked_count)
        self.update_bookmark_star(tab.current_url_str)
        self.setWindowTitle(f"{tab.current_title_str} - {APP_NAME}")

    def on_tab_title_changed(self, tab: BrowserTab, title: str):
        idx = self.tabs.indexOf(tab)
        if idx != -1:
            self.tabs.setTabText(idx, title or "Unbenannt")
            self.tabs.setTabToolTip(idx, title)

        if tab == self.get_current_tab():
            self.setWindowTitle(f"{title} - {APP_NAME}" if title else APP_NAME)
            if tab.current_url_str and not tab.current_url_str.startswith("about:"):
                self.bm_manager.add_history(title, tab.current_url_str)

    def on_tab_url_changed(self, tab: BrowserTab, url: str):
        if url == "about:start":
            tab.favicon = QIcon()  # other pages: WebView2 reports their favicon (FaviconChanged)
        self._refresh_tab_icon(tab)
        if tab == self.get_current_tab():
            self.update_address_bar(url)
            self.update_bookmark_star(url)

    def on_tab_favicon(self, tab: BrowserTab, ic: QIcon):
        tab.favicon = ic
        self._refresh_tab_icon(tab)

    def _refresh_tab_icon(self, tab: BrowserTab):
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        if tab.current_url_str in ("", "about:start"):
            ic = icons.icon("logo", self.ui["accent"], 16)
        elif not tab.favicon.isNull():
            ic = tab.favicon
        else:
            ic = icons.icon("globe", theme.MUTED, 16)
        self.tabs.setTabIcon(idx, ic)

    def on_tab_audio(self, tab: BrowserTab, playing: bool, muted: bool):
        """Speaker button on the tab while it plays sound (click = mute), like Opera GX."""
        tab.audio_state = (playing, muted)
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        bar = self.tabs.tabBar()
        if not playing and not muted:
            bar.setTabButton(idx, QTabBar.ButtonPosition.LeftSide, None)
            return
        btn = bar.tabButton(idx, QTabBar.ButtonPosition.LeftSide)
        if not isinstance(btn, QToolButton):
            btn = QToolButton(bar)
            btn.setObjectName("navBtn")
            btn.setFixedSize(20, 20)
            btn.setIconSize(QSize(14, 14))
            btn.clicked.connect(lambda: tab.set_muted(not tab.is_muted()))
            bar.setTabButton(idx, QTabBar.ButtonPosition.LeftSide, btn)
        btn.setIcon(icons.icon("volume-x" if muted else "volume", theme.DANGER if muted else self.ui["accent"], 14))
        btn.setToolTip("Ton an" if muted else "Tab stummschalten")

    def show_tab_menu(self, index: int, pos):
        tab = self.tabs.widget(index)
        if tab is None:
            return
        menu = QMenu(self)
        menu.addAction(icons.icon("reload", theme.MUTED, 16), "Neu laden", tab.reload)
        menu.addAction(icons.icon("copy", theme.MUTED, 16), "Tab duplizieren",
                       lambda: self.open_new_tab(tab.current_url_str))
        muted = tab.is_muted()
        menu.addAction(icons.icon("volume" if muted else "volume-x", theme.MUTED, 16),
                       "Ton an" if muted else "Tab stummschalten", lambda: tab.set_muted(not muted))
        menu.addSeparator()
        menu.addAction("Andere Tabs schließen", lambda: self.close_other_tabs(tab))
        menu.addAction(icons.icon("x", theme.MUTED, 16), "Tab schließen", lambda: self.close_tab(self.tabs.indexOf(tab)))
        menu.exec(pos)

    def close_other_tabs(self, keep: BrowserTab):
        for i in reversed(range(self.tabs.count())):
            if self.tabs.widget(i) is not keep:
                self.close_tab(i)

    # ------------------------------------------------------------------ status widgets
    def on_tab_load_progress(self, tab: BrowserTab, progress: int):
        if tab != self.get_current_tab():
            return
        self._loading = progress < 100
        self.progress_bar.setValue(progress if self._loading else 0)
        self._set_reload_icon()

    def _set_reload_icon(self):
        if self._loading:
            self.btn_reload.setIcon(icons.icon("x", theme.MUTED, 19, theme.TEXT))
            self.btn_reload.setToolTip("Laden anhalten (Esc)")
        else:
            self.btn_reload.setIcon(icons.icon("reload", theme.MUTED, 19, theme.TEXT))
            self.btn_reload.setToolTip("Neu laden (F5)")

    def on_tab_blocked_count_changed(self, tab: BrowserTab, count: int):
        if tab == self.get_current_tab():
            self.update_shield_badge(count)

    def update_shield_badge(self, count: int):
        tab = self.get_current_tab()
        host = host_of(tab.current_url_str) if tab and "://" in tab.current_url_str else ""
        off = not self.filter_engine.is_enabled or self.filter_engine.is_domain_whitelisted(host)
        accent = self.ui["accent"]
        if off:
            self.btn_shield.setText("AUS")
            self.btn_shield.setIcon(icons.icon("shield-off", theme.DANGER, 17))
            self.shield_glow.setColor(QColor(theme.DANGER))
        else:
            self.btn_shield.setText(f"{count:,}".replace(",", "."))
            self.btn_shield.setIcon(icons.icon("shield", accent, 17))
            self.shield_glow.setColor(QColor(accent))
        self.btn_shield.setProperty("off", off)
        self.btn_shield.style().unpolish(self.btn_shield)
        self.btn_shield.style().polish(self.btn_shield)

    def update_address_bar(self, url_str: str, force: bool = False):
        # keep what the user is typing (YouTube, Twitch etc. change their URL while you type)
        if not force and self.address_bar.hasFocus() and self.address_bar.isModified():
            return
        accent = self.ui["accent"]
        if not url_str or url_str == "about:start":
            self.address_bar.setText("")
            self.addr_icon.setIcon(icons.icon("search", accent, 16))
            self.addr_icon.setToolTip("Startseite")
        else:
            self.address_bar.setText(url_str)
            self.address_bar.setCursorPosition(0)
            if url_str.startswith("https://"):
                self.addr_icon.setIcon(icons.icon("lock", theme.OK, 16))
                self.addr_icon.setToolTip("Verschlüsselte Verbindung")
            else:
                self.addr_icon.setIcon(icons.icon("globe", theme.MUTED, 16))
                self.addr_icon.setToolTip("Nicht verschlüsselt")

    # ------------------------------------------------------------------ navigation
    def navigate_to_address(self):
        text = self.address_bar.text().strip()
        if text:
            self.open_address(omnibox.resolve(text))

    def open_address(self, url: str):
        """Address bar: typed text (Enter) or a chosen suggestion."""
        tab = self.get_current_tab()
        if not tab:
            return
        self.address_bar.setModified(False)
        tab.load(url)
        tab.focus_page()

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
            if self._loading and not bypass_cache:
                tab.stop()
            else:
                tab.reload(bypass_cache)

    def stop_or_exit_fullscreen(self):
        tab = self.get_current_tab()
        if self.isFullScreen():
            self.toggle_fullscreen()
        elif tab and self._loading:
            tab.stop()

    def navigate_home(self):
        tab = self.get_current_tab()
        if tab:
            self.address_bar.setModified(False)
            tab.load_start_page()

    def load_url_in_current_tab(self, url_str: str):
        tab = self.get_current_tab()
        if tab:
            self.address_bar.setModified(False)
            tab.load(url_str)

    # ------------------------------------------------------------------ sidebar
    def on_sidebar(self, name: str):
        if name == "home":
            self.navigate_home()
        elif name in SITE_SHORTCUTS:
            self.open_or_switch(*SITE_SHORTCUTS[name])
        elif name == "bookmarks":
            self.show_bookmarks_menu()
        elif name == "history":
            self.open_history_dialog()
        elif name == "adlog":
            self.open_shield_dialog(initial_tab=3)
        elif name == "design":
            self.open_design_dialog()
        elif name == "shield":
            self.open_shield_dialog()

    def open_or_switch(self, host: str, url: str):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if host_of(tab.current_url_str).endswith(host):
                self.tabs.setCurrentIndex(i)
                return
        current = self.get_current_tab()
        if current and current.current_url_str in ("", "about:start"):
            current.load(url)
        else:
            self.open_new_tab(url)

    def show_bookmarks_menu(self):
        menu = QMenu(self)
        tab = self.get_current_tab()
        if tab and "://" in tab.current_url_str:
            starred = self.bm_manager.is_bookmarked(tab.current_url_str)
            menu.addAction(icons.icon("star-fill" if starred else "star", self.ui["accent"], 16),
                           "Lesezeichen entfernen" if starred else "Diese Seite merken\tStrg+D",
                           self.toggle_current_bookmark)
        menu.addAction("Lesezeichenleiste ausblenden" if self.bookmarks_bar.isVisible() else "Lesezeichenleiste anzeigen",
                       self.toggle_bookmarks_bar)
        menu.addSeparator()
        for b in self.bm_manager.get_bookmarks():
            menu.addAction(icons.icon("bookmark", theme.MUTED, 16), b["title"][:60],
                           lambda u=b["url"]: self.load_url_in_current_tab(u))
        btn = self.side_bar.buttons["bookmarks"][0]
        menu.exec(btn.mapToGlobal(btn.rect().topRight()))

    # ------------------------------------------------------------------ bookmarks
    def update_bookmarks_bar(self):
        while self.bm_layout.count():
            item = self.bm_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for b in self.bm_manager.get_bookmarks():
            btn = QPushButton(b["title"][:28])
            btn.setToolTip(b["url"])
            url_str = b["url"]
            btn.clicked.connect(lambda checked, u=url_str: self.load_url_in_current_tab(u))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, u=url_str, w=btn: self.show_bookmark_context_menu(w.mapToGlobal(pos), u))
            self.bm_layout.addWidget(btn)
        self.bm_layout.addStretch()

    def show_bookmark_context_menu(self, global_pos, url_str):
        menu = QMenu(self)
        del_act = menu.addAction(icons.icon("x", theme.MUTED, 16), "Lesezeichen löschen")
        if menu.exec(global_pos) == del_act:
            self.bm_manager.remove_bookmark(url_str)
            self.update_bookmarks_bar()

    def toggle_bookmarks_bar(self):
        visible = not self.bookmarks_bar.isVisible()
        self.bookmarks_bar.setVisible(visible)
        self.ui.set("bookmarks_bar", visible)

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
        if url and "://" in url and self.bm_manager.is_bookmarked(url):
            self.star_action.setIcon(icons.icon("star-fill", self.ui["accent"], 16))
        else:
            self.star_action.setIcon(icons.icon("star", theme.DIM, 16, theme.TEXT))
        self.star_action.setVisible(bool(url) and "://" in url)

    # ------------------------------------------------------------------ dialogs
    def open_shield_dialog(self, initial_tab: int = 0):
        tab = self.get_current_tab()
        url = tab.current_url_str if tab else ""
        count = tab.blocked_count if tab else 0
        dlg = AdBlockDialog(self.filter_engine, url, count, self, ad_logger=self.ad_logger,
                            report_ad=self.report_ad, accent=self.ui["accent"], initial_tab=initial_tab)
        dlg.exec()
        if dlg.settings_changed:
            flag = "true" if self.filter_engine.ad_spoofing else "false"
            js = "window.__abTwitchSetSpoofing&&window.__abTwitchSetSpoofing(" + flag + ")"
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                w.refresh_site_scripts()
                try:
                    if w.is_ready:
                        w.wv.CoreWebView2.ExecuteScriptAsync(js)
                except Exception:
                    pass
        if tab:
            if dlg.needs_reload and "://" in url:
                tab.reload()
            self.update_shield_badge(tab.blocked_count)

    def open_design_dialog(self):
        dlg = DesignDialog(self.ui, self.on_design_changed, self, hw_accel_active=self.hw_accel)
        dlg.exec()
        if dlg.restart_now:
            self.restart_browser()
        elif dlg.hw_accel_changed() and bool(self.ui["hardware_acceleration"]) != self.hw_accel:
            self.offer_restart("Browser-Neustart erforderlich",
                               "Die Änderung der Hardware-Beschleunigung wird erst nach einem Neustart wirksam.")

    def toggle_discord_stream_mode(self):
        # switches the mode of the running session, which only takes effect after a restart
        new_hw = not self.hw_accel
        self.ui.set("hardware_acceleration", new_hw)
        status = ("aktiviert (maximale GPU-Leistung)" if new_hw else
                  "deaktiviert (Discord-Stream-Modus – Netflix im Stream sichtbar)")
        self.offer_restart("Hardware-Beschleunigung geändert",
                           f"Die Hardware-Beschleunigung wird {status}.\n\n"
                           "Damit die Änderung wirksam wird, muss der Browser neu gestartet werden.")

    def offer_restart(self, title: str, text: str):
        reply = QMessageBox.question(self, title, text + "\n\nMöchtest du den Browser jetzt neu starten?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            self.restart_browser()

    def restart_browser(self):
        """New instance with the current page; command-line GPU flags are dropped, the saved setting applies."""
        tab = self.get_current_tab()
        url = tab.current_url_str if tab else ""
        args = [os.path.abspath(sys.argv[0])]
        if url.startswith(("http://", "https://")):
            args.append(url)
        app = QApplication.instance()
        # start it only after this instance has shut down its tabs and released the WebView2 profile
        app.aboutToQuit.connect(lambda: QProcess.startDetached(sys.executable, args))
        self.close()
        app.quit()

    def open_history_dialog(self):
        dlg = HistoryDialog(self.bm_manager, self)
        dlg.url_selected.connect(self.load_url_in_current_tab)
        dlg.exec()

    def show_find_in_page(self):
        tab = self.get_current_tab()
        if tab:
            tab.show_find_bar()

    def open_devtools(self):
        tab = self.get_current_tab()
        if tab:
            tab.open_devtools()

    # ------------------------------------------------------------------ fullscreen
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
                                       (self.title_bar, self.side_bar, self.nav_toolbar, self.bookmarks_bar,
                                        self.progress_bar, tab.find_bar)]
            for w, _ in self._chrome_visibility:
                w.hide()
            self._was_fullscreen = self.isFullScreen()
            if not self._was_fullscreen and not self._hidden_test_mode:
                self._was_maximized = self.isMaximized()
                self.showFullScreen()
            self._broadcast_resizable()
        else:
            if self._page_fullscreen_tab is not tab:
                return
            self._page_fullscreen_tab = None
            for w, visible in self._chrome_visibility:
                w.setVisible(visible)
            if not self._was_fullscreen and not self._hidden_test_mode:
                self.showMaximized() if self._was_maximized else self.showNormal()
            self._broadcast_resizable()

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

    def eventFilter(self, obj, ev):
        if (ev.type() == QEvent.Type.MouseButtonPress and isinstance(obj, QWidget) and obj.window() is self
                and obj.focusPolicy() & Qt.FocusPolicy.ClickFocus):
            self._reclaim_keyboard()
        return super().eventFilter(obj, ev)

    def _reclaim_keyboard(self):
        """WebView2 pages are native windows of another process. While one of them holds the Windows
        keyboard focus (e.g. after a reload), a click into the address bar does not take it back and
        typing still goes to the page - or nowhere, if that tab is hidden now. So take it explicitly."""
        hwnd = int(self.winId())
        focused = native_frame.focused_window()
        if focused and focused != hwnd:
            native_frame.set_focus(hwnd)

    def focus_address_bar(self):
        self.activateWindow()
        self._reclaim_keyboard()
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

    # ------------------------------------------------------------------ main menu
    def show_main_menu(self, anchor):
        m = QMenu(self)
        ic = lambda name: icons.icon(name, theme.MUTED, 16)
        m.addAction(ic("plus"), "Neuer Tab\tStrg+T", lambda: self.open_new_tab())
        m.addAction(ic("history"), "Verlauf\tStrg+H", self.open_history_dialog)
        m.addAction(ic("bookmark"), "Lesezeichenleiste ein/aus\tStrg+B", self.toggle_bookmarks_bar)
        m.addSeparator()
        m.addAction(ic("find"), "Suchen auf der Seite\tStrg+F", self.show_find_in_page)
        m.addAction(ic("zoom"), "Vergrößern\tStrg++", self.zoom_in)
        m.addAction("Verkleinern\tStrg+-", self.zoom_out)
        m.addAction("Zoom zurücksetzen\tStrg+0", self.zoom_reset)
        m.addSeparator()
        m.addAction(ic("code"), "Entwicklertools\tF12", self.open_devtools)
        m.addAction(ic("fullscreen"), "Vollbildmodus\tF11", self.toggle_fullscreen)
        m.addSeparator()
        m.addAction(icons.icon("palette", self.ui["accent"], 16), "GX Control – Design & System", self.open_design_dialog)
        stream_txt = "Discord-Stream-Modus (Netflix Fix)" + (" [Aktiv]" if not self.hw_accel else "")
        m.addAction(icons.icon("discord", self.ui["accent"] if not self.hw_accel else theme.MUTED, 16),
                    stream_txt, self.toggle_discord_stream_mode)
        m.addAction(icons.icon("shield", self.ui["accent"], 16), "AdBlock Shield", lambda: self.open_shield_dialog())
        m.addAction(ic("alert"), "Werbung auf dieser Seite melden", self.report_ad)
        m.addAction(ic("info"), "Über AdBlock Browser GX", self.show_about_dialog)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _environment_info(self) -> dict:
        lists = {}
        for src in DEFAULT_FILTER_SOURCES:
            path = os.path.join(self.filter_engine.filters_dir, src["filename"])
            if os.path.exists(path):
                lists[src["name"]] = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        return {"browser": "AdBlock Browser GX 3.0 (Claude-Variante)", "filterlisten": lists}

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
        accent = self.ui["accent"]
        QMessageBox.about(
            self,
            "Über AdBlock Browser GX",
            f"<h2 style='font-family:Bahnschrift'>AdBlock Browser <span style='color:{accent}'>GX</span></h2>"
            "<p>Gamer-Browser auf Basis von <b>Microsoft Edge WebView2</b> mit der "
            "<b>Brave AdBlock Rust-Engine</b>.</p>"
            "<ul>"
            "<li>Werbefrei: Twitch, YouTube, South Park</li>"
            "<li>EasyList, EasyPrivacy, EasyList Germany, Peter Lowe</li>"
            "<li>Element-Ausblendung, Popup-Blocker, Werbe-Protokoll</li>"
            "<li>GX Control: Akzentfarben, Seitenleiste, Neon-Startseite</li>"
            "</ul>"
        )
