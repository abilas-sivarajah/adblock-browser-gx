"""
GX theme: dark surfaces with one neon accent colour (selectable in "GX Control").
Builds the application-wide Qt stylesheet and stores the design settings.
"""

import json
import os

ACCENTS = [
    ("GX Rot", "#fa1e4e"),
    ("Neon Pink", "#ff2bd6"),
    ("Ultra Violett", "#9d5cff"),
    ("Cyber Cyan", "#00e5ff"),
    ("Toxic Grün", "#39ff6a"),
    ("Lava Orange", "#ff7a1a"),
    ("Eis Blau", "#3d8bff"),
    ("Gold Rush", "#ffc400"),
]

# surfaces from deepest (window) to raised (hover)
BG0 = "#0b0910"   # title bar, window
BG1 = "#13111b"   # nav bar, sidebar, selected tab
BG2 = "#1b1826"   # inputs, cards
BG3 = "#26212f"   # hover
LINE = "#2d2839"
TEXT = "#f2eff8"
MUTED = "#a7a0b8"
DIM = "#6e6782"
OK = "#2ee88a"
DANGER = "#ff4d5e"

FONT_UI = '"Segoe UI Variable Text", "Segoe UI", sans-serif'
FONT_GX = '"Bahnschrift", "Segoe UI", sans-serif'

DEFAULTS = {
    "accent": ACCENTS[0][1],
    "sidebar": True,
    "bookmarks_bar": True,
    "animations": True,
    "hardware_acceleration": True,
}


def rgb_tuple(hex_color: str):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(hex_color: str, alpha: float) -> str:
    """Qt stylesheet colour; Qt wants the alpha as 0-255 (not 0-1 like CSS)."""
    r, g, b = rgb_tuple(hex_color)
    return f"rgba({r}, {g}, {b}, {round(alpha * 255)})"


def on_accent(hex_color: str) -> str:
    """Readable text colour on top of the accent."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#0b0910" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


class UISettings:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "ui_settings.json")
        self.values = dict(DEFAULTS)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.values.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self.values[key]

    def set(self, key, value):
        self.values[key] = value
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.values, f, indent=2)
        except OSError:
            pass


def build_stylesheet(accent: str, icon_path) -> str:
    """icon_path(name, colour) -> file path usable in url(...)."""
    A = accent
    return f"""
* {{
    font-family: {FONT_UI};
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QMainWindow, #gxRoot {{ background: {BG0}; }}
QToolTip {{
    background: {BG2}; color: {TEXT}; border: 1px solid {rgba(A, .6)};
    border-radius: 6px; padding: 5px 8px;
}}

/* ---------- title bar with tabs ---------- */
#titleBar {{ background: {BG0}; }}
#gxLogo {{ background: transparent; border: none; padding: 0 6px 0 10px; }}
QTabBar#tabBar {{ background: transparent; border: none; }}
QTabBar#tabBar::tab {{
    background: transparent; color: {MUTED};
    font-family: {FONT_GX}; font-size: 13px;
    height: 34px; min-width: 110px; max-width: 230px;
    padding: 0 6px 0 12px; margin: 6px 3px 0 0;
    border-top-left-radius: 10px; border-top-right-radius: 10px;
    border: none;
}}
QTabBar#tabBar::tab:hover:!selected {{ background: {BG2}; color: {TEXT}; }}
/* selected tab: same colour as the navigation bar below (seamless), accent cap clipped by the
   rounded corners - a border-top would curve down the sides */
QTabBar#tabBar::tab:selected {{
    color: {TEXT};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {A}, stop:0.058 {A}, stop:0.059 {BG1}, stop:1 {BG1});
}}
QTabBar#tabBar::close-button {{
    image: url({icon_path("x", DIM)}); subcontrol-position: right; margin: 2px;
    width: 14px; height: 14px; border-radius: 4px;
}}
QTabBar#tabBar::close-button:hover {{ image: url({icon_path("x", TEXT)}); background: {rgba(A, .35)}; }}
QTabBar#tabBar QToolButton {{ background: {BG0}; border: none; border-radius: 6px; }}
QTabBar#tabBar QToolButton:hover {{ background: {BG2}; }}
#newTabBtn {{ background: transparent; border: none; border-radius: 8px; margin-top: 6px; }}
#newTabBtn:hover {{ background: {rgba(A, .2)}; }}
#winBtn, #winClose {{ background: transparent; border: none; border-radius: 0; }}
#winBtn:hover {{ background: {BG3}; }}
#winClose:hover {{ background: #e81123; }}

/* ---------- navigation bar ---------- */
#navBar {{ background: {BG1}; border-bottom: 1px solid {LINE}; }}
#navBtn {{ background: transparent; border: none; border-radius: 8px; padding: 5px; }}
#navBtn:hover {{ background: {BG3}; }}
#navBtn:pressed {{ background: {rgba(A, .25)}; }}
#navBtn:disabled {{ background: transparent; }}
QLineEdit#addressBar {{
    background: {BG2}; color: {TEXT};
    border: 1px solid {LINE}; border-radius: 17px;
    padding: 6px 8px; font-size: 13px;
    selection-background-color: {rgba(A, .55)};
}}
QLineEdit#addressBar:hover {{ border-color: {rgba(A, .45)}; }}
QLineEdit#addressBar:focus {{ border: 1px solid {A}; background: {BG0}; }}
#omniBox {{ background: {BG1}; border: 1px solid {rgba(A, .5)}; border-radius: 14px; }}
QListWidget#omniList {{ background: transparent; border: none; outline: 0; }}
#shieldBtn {{
    background: {rgba(A, .14)}; color: {TEXT};
    border: 1px solid {rgba(A, .75)}; border-radius: 15px;
    font-family: {FONT_GX}; font-size: 13px; font-weight: 600;
    padding: 4px 12px 4px 8px;
}}
#shieldBtn:hover {{ background: {rgba(A, .3)}; }}
#shieldBtn[off="true"] {{ background: {rgba(DANGER, .12)}; border-color: {DANGER}; color: {DANGER}; }}
QProgressBar#gxProgress {{ background: transparent; border: none; }}
QProgressBar#gxProgress::chunk {{ background: {A}; }}

/* ---------- sidebar ---------- */
#sideBar {{ background: {BG1}; border-right: 1px solid {LINE}; }}
#sideBtn {{
    background: transparent; border: none; border-radius: 10px;
    margin: 0 6px; padding: 8px;
}}
#sideBtn:hover {{ background: {rgba(A, .16)}; }}
#sideBtn:pressed {{ background: {rgba(A, .32)}; }}
#sideSep {{ background: {LINE}; margin: 6px 14px; }}

/* ---------- bookmarks bar ---------- */
#bookmarkBar {{ background: {BG1}; border-bottom: 1px solid {LINE}; }}
#bookmarkBar QPushButton {{
    background: transparent; border: none; border-radius: 7px;
    color: {MUTED}; font-size: 12px; padding: 4px 10px;
}}
#bookmarkBar QPushButton:hover {{ background: {BG3}; color: {TEXT}; }}

/* ---------- find bar ---------- */
#findBar {{ background: {BG1}; border-bottom: 1px solid {LINE}; }}
#findBar QLabel {{ color: {MUTED}; }}

/* ---------- menus ---------- */
QMenu {{
    background: {BG1}; border: 1px solid {LINE}; border-radius: 12px; padding: 6px;
}}
QMenu::item {{ padding: 8px 26px 8px 14px; border-radius: 7px; color: {TEXT}; }}
QMenu::item:selected {{ background: {rgba(A, .22)}; color: {TEXT}; }}
QMenu::item:disabled {{ color: {DIM}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}

/* ---------- dialogs ---------- */
QDialog, QMessageBox {{ background: {BG0}; }}
QLabel {{ background: transparent; }}
#dlgTitle {{ font-family: {FONT_GX}; font-size: 20px; font-weight: 600; color: {TEXT}; }}
#dlgSub {{ color: {MUTED}; }}
#card {{ background: {BG1}; border: 1px solid {LINE}; border-radius: 14px; }}
#cardAccent {{ background: {rgba(A, .10)}; border: 1px solid {rgba(A, .55)}; border-radius: 14px; }}
#cardDanger {{ background: {rgba(DANGER, .10)}; border: 1px solid {rgba(DANGER, .55)}; border-radius: 14px; }}
#bigNumber {{ font-family: {FONT_GX}; font-size: 30px; font-weight: 700; color: {A}; }}
#bigNumberOk {{ font-family: {FONT_GX}; font-size: 30px; font-weight: 700; color: {OK}; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 12px; background: {BG1}; top: -1px; }}
QTabWidget > QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 9px 16px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
    font-family: {FONT_GX}; font-size: 13px;
}}
QTabWidget > QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {A}; }}
QTabWidget > QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QPushButton {{
    background: {BG2}; color: {TEXT}; border: 1px solid {LINE};
    border-radius: 9px; padding: 8px 16px;
}}
QPushButton:hover {{ border-color: {A}; background: {BG3}; }}
QPushButton:pressed {{ background: {rgba(A, .25)}; }}
QPushButton:disabled {{ color: {DIM}; border-color: {LINE}; }}
QPushButton#primaryBtn {{ background: {A}; color: {on_accent(A)}; border: none; font-weight: 600; }}
QPushButton#primaryBtn:hover {{ background: {rgba(A, .85)}; }}
QPushButton#dangerBtn {{ background: {rgba(DANGER, .15)}; border-color: {rgba(DANGER, .6)}; color: {DANGER}; }}
QLineEdit {{
    background: {BG2}; border: 1px solid {LINE}; border-radius: 9px; padding: 7px 10px;
    selection-background-color: {rgba(A, .55)};
}}
QLineEdit:focus {{ border-color: {A}; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{
    width: 34px; height: 18px; border-radius: 9px; background: {BG3}; border: 1px solid {LINE};
    image: url({icon_path("knob", MUTED)});
}}
QCheckBox::indicator:checked {{
    background: {A}; border-color: {A};
    image: url({icon_path("knob-on", on_accent(A))});
}}
QTableWidget, QListWidget {{
    background: {BG1}; border: 1px solid {LINE}; border-radius: 10px;
    gridline-color: {LINE}; alternate-background-color: {BG2};
    selection-background-color: {rgba(A, .3)}; selection-color: {TEXT};
}}
QListWidget::item {{ padding: 5px 10px; border-radius: 8px; margin: 1px 4px; }}
QListWidget::item:hover {{ background: {BG3}; }}
QListWidget::item:selected {{ background: {rgba(A, .25)}; }}
QHeaderView::section {{
    background: {BG0}; color: {MUTED}; border: none; border-bottom: 1px solid {LINE};
    padding: 8px; font-family: {FONT_GX}; font-weight: 600;
}}
QTableCornerButton::section {{ background: {BG0}; border: none; }}

/* ---------- scrollbars ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {BG3}; border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {A}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- GX Control ---------- */
#swatch {{ border: 2px solid transparent; border-radius: 22px; }}
#swatch:hover {{ border-color: {TEXT}; }}
#swatch:checked {{ border: 3px solid {TEXT}; }}
"""
