"""
GX Control: accent colour and layout switches. Every change is applied immediately,
except hardware acceleration (WebView2 browser arguments), which needs a restart.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QToolButton, QVBoxLayout, QWidget)

import icons
import theme


class DesignDialog(QDialog):
    def __init__(self, settings: theme.UISettings, on_change, parent=None, hw_accel_active=True):
        super().__init__(parent)
        self.settings = settings
        self.on_change = on_change
        self.restart_now = False                 # "Jetzt neu starten" clicked
        self._hw_active = hw_accel_active        # GPU mode of the running session
        self._hw_at_open = bool(settings["hardware_acceleration"])
        self.setWindowTitle("GX Control – Design & System")
        self.setMinimumWidth(480)

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

        # system & streaming switches
        card3 = QFrame()
        card3.setObjectName("card")
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(18, 16, 18, 16)
        c3.setSpacing(10)
        lbl3 = QLabel("SYSTEM & STREAMING")
        lbl3.setObjectName("dlgSub")
        c3.addWidget(lbl3)

        self.cb_hw = QCheckBox("Hardware-Beschleunigung aktivieren")
        self.cb_hw.setChecked(bool(settings["hardware_acceleration"]))
        self.cb_hw.toggled.connect(self._toggle_hw_accel)
        c3.addWidget(self.cb_hw)

        tip = QLabel("Tipp: Deaktivieren (Discord-Streaming-Modus), wenn beim Screen-Sharing von Netflix, "
                     "Prime Video etc. auf Discord das Bild für Freunde schwarz bleibt. Videos laufen dann "
                     "evtl. in geringerer Auflösung.")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        c3.addWidget(tip)

        self.restart_box = QWidget()
        rb_layout = QHBoxLayout(self.restart_box)
        rb_layout.setContentsMargins(0, 4, 0, 0)
        rb_layout.setSpacing(10)

        self.lbl_restart_hint = QLabel("* Neustart erforderlich, damit die Änderung wirksam wird.")
        self.lbl_restart_hint.setStyleSheet(f"color: {theme.DANGER}; font-size: 11px; font-weight: bold;")
        rb_layout.addWidget(self.lbl_restart_hint, 1)

        self.btn_restart_now = QPushButton("Jetzt neu starten")
        self.btn_restart_now.setFixedHeight(28)
        self.btn_restart_now.clicked.connect(self._restart_now)
        rb_layout.addWidget(self.btn_restart_now)

        # also visible when an earlier change is still waiting for the restart
        self.restart_box.setVisible(self._hw_at_open != self._hw_active)
        c3.addWidget(self.restart_box)
        root.addWidget(card3)

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

    def _toggle_hw_accel(self, on: bool):
        self.settings.set("hardware_acceleration", bool(on))
        self.restart_box.setVisible(bool(on) != self._hw_active)

    def _restart_now(self):
        self.restart_now = True
        self.accept()

    def hw_accel_changed(self) -> bool:
        """Hardware acceleration switched in this dialog (the caller offers the restart)."""
        return bool(self.settings["hardware_acceleration"]) != self._hw_at_open
