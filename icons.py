"""
Line icons (24x24, stroke based) rendered in any colour - for buttons (QIcon) and for
stylesheets (SVG files in the UI cache, used via url(...)).
"""

import hashlib
import os

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_P = {
    "back": '<path d="M15 18l-6-6 6-6"/>',
    "forward": '<path d="M9 18l6-6-6-6"/>',
    "reload": '<path d="M20 11a8 8 0 1 0-2.3 6.1"/><path d="M20 4v7h-7"/>',
    "x": '<path d="M18 6L6 18M6 6l12 12"/>',
    "home": '<path d="M3.5 10.5L12 3.5l8.5 7"/><path d="M5.5 9v11.5h4.5v-6h4v6h4.5V9"/>',
    "star": '<path d="M12 3.2l2.7 5.5 6 .9-4.35 4.25 1.03 6-5.38-2.83-5.38 2.83 1.03-6L3.3 9.6l6-.9z"/>',
    "star-fill": '<path fill="{c}" d="M12 3.2l2.7 5.5 6 .9-4.35 4.25 1.03 6-5.38-2.83-5.38 2.83 1.03-6L3.3 9.6l6-.9z"/>',
    "shield": '<path d="M12 2.8l7.5 2.9v5.6c0 4.8-3.2 8.9-7.5 10.2-4.3-1.3-7.5-5.4-7.5-10.2V5.7z"/><path d="M8.8 12.2l2.2 2.2 4.3-4.6"/>',
    "shield-off": '<path d="M12 2.8l7.5 2.9v5.6c0 4.8-3.2 8.9-7.5 10.2-4.3-1.3-7.5-5.4-7.5-10.2V5.7z"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.6 3.8 5.6 3.8 9s-1.2 6.4-3.8 9c-2.6-2.6-3.8-5.6-3.8-9S9.4 5.6 12 3z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5l-4.5-4.5"/>',
    "bookmark": '<path d="M18 21l-6-4.5L6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2z"/>',
    "history": '<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6"/><path d="M3 4v4h4"/><path d="M12 7.5V12l3 2"/>',
    "log": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h1M4 12h1M4 18h1"/>',
    "alert": '<path d="M12 3.5L21.5 20h-19z"/><path d="M12 10v4.5M12 17.4v.1"/>',
    "palette": '<path d="M12 3a9 9 0 0 0 0 18c1.1 0 1.8-.8 1.8-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-1 .8-1.7 1.8-1.7H17a4.5 4.5 0 0 0 4.5-4.5C21.5 6.4 17.2 3 12 3z"/><circle cx="7.5" cy="11" r="1.2"/><circle cx="10.5" cy="7.2" r="1.2"/><circle cx="15" cy="7.4" r="1.2"/>',
    "twitch": '<path d="M5 3.5h15.5v10.5L16 18.5h-4l-3 3H7.5v-3h-3V6z"/><path d="M11 8v4.5M15.5 8v4.5"/>',
    "youtube": '<rect x="2.5" y="5.5" width="19" height="13" rx="4"/><path d="M10.2 9.2l4.6 2.8-4.6 2.8z"/>',
    "discord": '<path d="M8.5 6.3C7 6.6 5.6 7.1 4.6 7.8 3 10.2 2.4 13 2.6 16c1.4 1.1 3 1.8 4.6 2.3l1-1.6"/><path d="M15.5 6.3c1.5.3 2.9.8 3.9 1.5 1.6 2.4 2.2 5.2 2 8.2-1.4 1.1-3 1.8-4.6 2.3l-1-1.6"/><path d="M7.5 16.2c2.9 1.3 6.1 1.3 9 0M8 7.8c2.6-.9 5.4-.9 8 0"/><circle cx="9.3" cy="12.5" r="1.1"/><circle cx="14.7" cy="12.5" r="1.1"/>',
    "volume": '<path d="M11 5.5L6.5 9H3.5v6h3L11 18.5z"/><path d="M15 9.2a4 4 0 0 1 0 5.6M17.8 6.5a8 8 0 0 1 0 11"/>',
    "volume-x": '<path d="M11 5.5L6.5 9H3.5v6h3L11 18.5z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>',
    "min": '<path d="M6 12h12"/>',
    "max": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "restore": '<rect x="5" y="9" width="10" height="10" rx="1.5"/><path d="M9 9V6.5A1.5 1.5 0 0 1 10.5 5H17.5A1.5 1.5 0 0 1 19 6.5V13.5A1.5 1.5 0 0 1 17.5 15H15"/>',
    "find": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.8-4.8"/>',
    "chevron-up": '<path d="M6 15l6-6 6 6"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "code": '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"/>',
    "fullscreen": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
    "zoom": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.8-4.8M7.5 10.5h6M10.5 7.5v6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.6v.1"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
}

# GX brand mark: shield with a filled accent chevron
LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M12 1.8l8.4 3.2v6.3c0 5.4-3.6 10-8.4 11.5C7.2 21.3 3.6 16.7 3.6 11.3V5z" fill="{c}" fill-opacity=".16" '
        'stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>'
        '<path d="M7.6 9.2l4.4 3 4.4-3v3.6l-4.4 3-4.4-3z" fill="{c}"/></svg>')

# switch knobs for QCheckBox indicators (34 x 18)
_KNOBS = {
    "knob": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 34 18"><circle cx="9" cy="9" r="6" fill="{c}"/></svg>',
    "knob-on": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 34 18"><circle cx="25" cy="9" r="6" fill="{c}"/></svg>',
}


def svg(name: str, color: str, stroke: float = 1.9) -> str:
    if name == "logo":
        return LOGO.replace("{c}", color)
    if name in _KNOBS:
        return _KNOBS[name].replace("{c}", color)
    body = _P[name].replace("{c}", color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


def pixmap(name: str, color: str, size: int = 18, scale: float = 2.0) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg(name, color).encode("utf-8")))
    vb = renderer.viewBoxF()
    w = size * vb.width() / vb.height() if vb.height() else size
    pm = QPixmap(int(w * scale), int(size * scale))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p, QRectF(0, 0, pm.width(), pm.height()))
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, color: str, size: int = 18, active_color: str | None = None) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal)
    ic.addPixmap(pixmap(name, active_color or color, size), QIcon.Mode.Active)
    return ic


class IconFiles:
    """Writes tinted SVGs into a cache folder so stylesheets can reference them."""

    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

    def __call__(self, name: str, color: str) -> str:
        data = svg(name, color)
        path = os.path.join(self.folder, f"{name}-{hashlib.md5(data.encode()).hexdigest()[:10]}.svg")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
        return path.replace("\\", "/")
