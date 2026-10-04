"""
GX window chrome: title bar with tabs, window buttons, sidebar.
The window itself is frameless; dragging/snapping/resizing go through the window manager
(QWindow.startSystemMove / startSystemResize).
"""

from PyQt6.QtCore import QObject, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QSizePolicy, QStackedWidget, QTabBar, QToolButton,
                             QVBoxLayout, QWidget)

import icons
import theme


def toggle_maximized(window):
    window.showNormal() if window.isMaximized() else window.showMaximized()


def start_move(widget):
    handle = widget.window().windowHandle()
    if handle is not None:
        handle.startSystemMove()


class GXTabBar(QTabBar):
    """Tabs inside the title bar. Empty space drags the window, middle click closes a tab."""
    context_menu_requested = pyqtSignal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tabBar")
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setDocumentMode(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setIconSize(QSize(16, 16))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def mousePressEvent(self, e):
        idx = self.tabAt(e.position().toPoint())
        if e.button() == Qt.MouseButton.MiddleButton and idx >= 0:
            self.tabCloseRequested.emit(idx)
            return
        if e.button() == Qt.MouseButton.RightButton and idx >= 0:
            self.context_menu_requested.emit(idx, e.globalPosition().toPoint())
            return
        if e.button() == Qt.MouseButton.LeftButton and idx < 0:
            start_move(self)
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.tabAt(e.position().toPoint()) < 0:
            toggle_maximized(self.window())
            return
        super().mouseDoubleClickEvent(e)


class TabArea(QObject):
    """Tab bar in the title bar + page stack below - with the QTabWidget methods the
    main window uses. Pages are found through the tab's data, so moving tabs is free."""
    currentChanged = pyqtSignal(int)
    tabCloseRequested = pyqtSignal(int)

    def __init__(self, bar: GXTabBar, stack: QStackedWidget):
        super().__init__(bar)
        self.bar, self.stack = bar, stack
        self._pages = {}
        bar.currentChanged.connect(self._on_current)
        bar.tabCloseRequested.connect(self.tabCloseRequested)

    def _on_current(self, index):
        w = self.widget(index)
        if w is not None:
            self.stack.setCurrentWidget(w)
        self.currentChanged.emit(index)

    def addTab(self, widget, text) -> int:
        key = id(widget)
        self._pages[key] = widget
        self.stack.addWidget(widget)
        index = self.bar.addTab(text)
        self.bar.setTabData(index, key)
        return index

    def removeTab(self, index):
        w = self.widget(index)
        self.bar.removeTab(index)
        if w is not None:
            self.stack.removeWidget(w)
            self._pages.pop(id(w), None)

    def widget(self, index):
        if index < 0 or index >= self.bar.count():
            return None
        return self._pages.get(self.bar.tabData(index))

    def indexOf(self, widget) -> int:
        for i in range(self.bar.count()):
            if self.bar.tabData(i) == id(widget):
                return i
        return -1

    def count(self):
        return self.bar.count()

    def currentIndex(self):
        return self.bar.currentIndex()

    def currentWidget(self):
        return self.widget(self.bar.currentIndex())

    def setCurrentIndex(self, index):
        self.bar.setCurrentIndex(index)
        w = self.widget(index)
        if w is not None:
            self.stack.setCurrentWidget(w)

    def setTabText(self, index, text):
        self.bar.setTabText(index, text)

    def setTabToolTip(self, index, text):
        self.bar.setTabToolTip(index, text)

    def setTabIcon(self, index, ic):
        self.bar.setTabIcon(index, ic)

    def tabBar(self):
        return self.bar


class TitleBar(QWidget):
    logo_clicked = pyqtSignal()
    new_tab_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.logo = QToolButton(self)
        self.logo.setObjectName("gxLogo")
        self.logo.setIconSize(QSize(24, 24))
        self.logo.setToolTip("Menü")
        self.logo.clicked.connect(self.logo_clicked)
        lay.addWidget(self.logo)

        self.tab_bar = GXTabBar(self)
        lay.addWidget(self.tab_bar)

        self.btn_new = QToolButton(self)
        self.btn_new.setObjectName("newTabBtn")
        self.btn_new.setToolTip("Neuer Tab (Strg+T)")
        self.btn_new.setFixedSize(30, 30)
        self.btn_new.clicked.connect(self.new_tab_clicked)
        lay.addWidget(self.btn_new, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)

        self.btn_min = self._win_button("winBtn", "Minimieren", lambda: self.window().showMinimized())
        self.btn_max = self._win_button("winBtn", "Maximieren", lambda: toggle_maximized(self.window()))
        self.btn_close = self._win_button("winClose", "Schließen", lambda: self.window().close())
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)

    def _win_button(self, name, tip, slot):
        b = QToolButton(self)
        b.setObjectName(name)
        b.setToolTip(tip)
        b.setFixedSize(46, 40)
        b.setIconSize(QSize(16, 16))
        b.clicked.connect(slot)
        return b

    def apply_theme(self, accent):
        self.logo.setIcon(icons.icon("logo", accent, 24))
        self.btn_new.setIcon(icons.icon("plus", theme.MUTED, 18, theme.TEXT))
        self.btn_min.setIcon(icons.icon("min", theme.MUTED, 16, theme.TEXT))
        self.btn_close.setIcon(icons.icon("x", theme.MUTED, 16, "#ffffff"))
        self.update_max_icon()

    def update_max_icon(self):
        maximized = self.window().isMaximized()
        self.btn_max.setIcon(icons.icon("restore" if maximized else "max", theme.MUTED, 16, theme.TEXT))
        self.btn_max.setToolTip("Wiederherstellen" if maximized else "Maximieren")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            start_move(self)
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        toggle_maximized(self.window())


# name, tooltip, icon colour (None = theme colour) - brand colours like Opera GX's sidebar
SIDEBAR_ITEMS = [
    ("home", "home", "Startseite", None),
    ("twitch", "twitch", "Twitch", "#a970ff"),
    ("youtube", "youtube", "YouTube", "#ff3355"),
    ("discord", "discord", "Discord", "#7c86ff"),
    None,
    ("bookmarks", "bookmark", "Lesezeichen", None),
    ("history", "history", "Verlauf (Strg+H)", None),
    ("adlog", "log", "Werbe-Protokoll", None),
    "stretch",
    ("design", "palette", "GX Control – Design & Akzentfarbe", None),
    ("shield", "shield", "AdBlock Shield", None),
]


class SideBar(QWidget):
    triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sideBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(54)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(4)
        self.buttons = {}
        for item in SIDEBAR_ITEMS:
            if item is None:
                sep = QFrame(self)
                sep.setObjectName("sideSep")
                sep.setFixedHeight(1)
                lay.addWidget(sep)
                continue
            if item == "stretch":
                lay.addStretch(1)
                continue
            name, icon_name, tip, color = item
            b = QToolButton(self)
            b.setObjectName("sideBtn")
            b.setToolTip(tip)
            b.setIconSize(QSize(21, 21))
            b.setFixedSize(54, 40)
            b.clicked.connect(lambda checked=False, n=name: self.triggered.emit(n))
            lay.addWidget(b)
            self.buttons[name] = (b, icon_name, color)

    def apply_theme(self, accent):
        for b, icon_name, color in self.buttons.values():
            b.setIcon(icons.icon(icon_name, color or theme.MUTED, 21, color or accent))
