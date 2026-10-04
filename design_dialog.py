"""
GX Control: accent colour and layout switches. Every change is applied immediately.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QToolButton, QVBoxLayout)

import icons
import theme


class DesignDialog(QDialog):
    def __init__(self, settings: theme.UISettings, on_change, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.on_change = on_change
        self.setWindowTitle("GX Control – Design")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        head = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setPixmap(icons.pixmap("logo", settings["accent"], 34))
        head.addWidget(self.logo)
        titles = QVBoxLayout()
        t = QLabel("GX Control")
        t.setObjectName("dlgTitle")
        s = QLabel("Gib deinem Browser deinen Look – Änderungen wirken sofort.")
        s.setObjectName("dlgSub")
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles, 1)
        root.addLayout(head)

        # accent colours
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)
        lbl = QLabel("AKZENTFARBE")
        lbl.setObjectName("dlgSub")
        cl.addWidget(lbl)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (name, color) in enumerate(theme.ACCENTS):
            b = QToolButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setFixedSize(QSize(44, 44))
            b.setToolTip(name)
            b.setStyleSheet(f"QToolButton#swatch {{ background: {color}; }}")
            b.setChecked(color.lower() == settings["accent"].lower())
            b.clicked.connect(lambda checked=False, c=color: self._set_accent(c))
            self.group.addButton(b)
            grid.addWidget(b, i // 4, i % 4, Qt.AlignmentFlag.AlignCenter)
        cl.addLayout(grid)
        self.accent_name = QLabel()
        self.accent_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.accent_name)
        root.addWidget(card)

        # layout switches
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(18, 16, 18, 16)
        c2.setSpacing(12)
        lbl2 = QLabel("DARSTELLUNG")
        lbl2.setObjectName("dlgSub")
        c2.addWidget(lbl2)
        for key, text in (("sidebar", "Seitenleiste anzeigen"),
                          ("bookmarks_bar", "Lesezeichenleiste anzeigen"),
                          ("animations", "Animierter Neon-Hintergrund auf der Startseite")):
            cb = QCheckBox(text)
            cb.setChecked(bool(settings[key]))
            cb.toggled.connect(lambda on, k=key: self._set(k, on))
            c2.addWidget(cb)
        root.addWidget(card2)

        btns = QHBoxLayout()
        btns.addStretch()
        done = QPushButton("Fertig")
        done.setObjectName("primaryBtn")
        done.clicked.connect(self.accept)
        btns.addWidget(done)
        root.addLayout(btns)
        self._update_name()

    def _update_name(self):
        current = self.settings["accent"].lower()
        name = next((n for n, c in theme.ACCENTS if c.lower() == current), current)
        self.accent_name.setText(f"<span style='color:{self.settings['accent']}; font-weight:600'>{name}</span>")

    def _set_accent(self, color):
        self.settings.set("accent", color)
        self.logo.setPixmap(icons.pixmap("logo", color, 34))
        self._update_name()
        self.on_change()

    def _set(self, key, value):
        self.settings.set(key, bool(value))
        self.on_change()
