"""Hidden test of the native frame: styles, client area, WM_NCHITTEST answers, edge strips."""
import ctypes, json, os, sys, time, traceback
from ctypes import wintypes
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
OUT = os.path.join(HERE, "out", "frame_out.txt")
sys.path.insert(0, APP)
os.chdir(APP)
os.environ["ADBLOCK_HIDDEN_WINDOW"] = "1"
os.environ.setdefault("ADBLOCK_REMOTE_DEBUG_PORT", "9333")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from main_window import MainWindow
import native_frame

lines = []
def out(s):
    lines.append(s)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))

app = QApplication(sys.argv)
w = MainWindow(os.path.join(HERE, "testdata"), initial_url=None)
w.setWindowFlags(w.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
w.resize(1360, 860)
w.move(-20000, -20000)
w.show()
edge_msgs = []

def check():
    try:
        hwnd = int(w.winId())
        user32 = ctypes.windll.user32
        out(f"frame styles present: {native_frame.has_frame(hwnd)}")
        wr = native_frame.window_rect(hwnd)
        cr = wintypes.RECT(); user32.GetClientRect(hwnd, ctypes.byref(cr))
        out(f"window {wr.right - wr.left}x{wr.bottom - wr.top} | client {cr.right}x{cr.bottom} (equal = no visible frame)")
        pt = wintypes.POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(pt))
        q = w.mapToGlobal(QPoint(0, 0))
        out(f"client origin native {pt.x},{pt.y} | Qt {q.x()},{q.y()} (equal = menus/popups placed correctly)")
        out(f"content margins (normal window): {w.contentsMargins().left()},{w.contentsMargins().top()} (0 = no dark border)")

        def hit(x, y):
            return user32.SendMessageW(hwnd, native_frame.WM_NCHITTEST, 0, (y & 0xFFFF) << 16 | (x & 0xFFFF))
        names = {1: "CLIENT", 2: "CAPTION", 10: "LEFT", 11: "RIGHT", 12: "TOP", 13: "TOPLEFT", 14: "TOPRIGHT",
                 15: "BOTTOM", 16: "BOTTOMLEFT", 17: "BOTTOMRIGHT"}
        L, T, R, B = wr.left, wr.top, wr.right, wr.bottom
        tb = w.title_bar
        tab_rect = tb.tab_bar.tabRect(0)
        tab_center = tb.tab_bar.mapToGlobal(tab_rect.center())
        close_btn = tb.btn_close.mapToGlobal(tb.btn_close.rect().center())
        new_btn = tb.btn_new.mapToGlobal(tb.btn_new.rect().center())
        empty_title = tb.mapToGlobal(QPoint(tb.width() - 300, 20))
        nav = w.nav_toolbar.mapToGlobal(QPoint(w.nav_toolbar.width() // 2, 25))
        side = w.side_bar.mapToGlobal(QPoint(27, 300))
        cases = [
            ("Ecke oben links", L + 2, T + 2, 13), ("Rand oben", (L + R) // 2, T + 2, 12),
            ("Ecke oben rechts", R - 2, T + 2, 14), ("Rand links (Seitenleiste)", L + 2, T + 400, 10),
            ("Rand rechts (Adressleiste)", R - 2, nav.y(), 11), ("Ecke unten links", L + 2, B - 2, 16),
            ("leere Titelleiste", empty_title.x(), empty_title.y(), 2),
            ("auf einem Tab", tab_center.x(), tab_center.y(), 1), ("Knopf Schließen", close_btn.x(), close_btn.y(), 1),
            ("Knopf Neuer Tab", new_btn.x(), new_btn.y(), 1), ("Adressleiste", nav.x(), nav.y(), 1),
            ("Seitenleiste", side.x(), side.y(), 1),
        ]
        ok = 0
        for name, x, y, want in cases:
            got = hit(x, y)
            ok += got == want
            out(f"  {'PASS' if got == want else 'FAIL'} {name:28} -> HT{names.get(got, got)}")
        out(f"hit tests: {ok}/{len(cases)}")
        # tab bottom flush with the navigation bar?
        tab_bottom = tb.tab_bar.mapTo(w, tab_rect.bottomLeft()).y()
        nav_top = w.nav_toolbar.mapTo(w, QPoint(0, 0)).y()
        out(f"selected tab bottom y={tab_bottom} | navigation bar top y={nav_top} (gap {nav_top - tab_bottom - 1}px)")
        w.grab().save(os.path.join(HERE, "out", "frame_chrome.png"))
    except Exception:
        out(traceback.format_exc())

def edges():
    out(f"edge messages from the page: {edge_msgs}")
    out("resizable flag sent to tab: " + str(w.get_current_tab().window_resizable))

QTimer.singleShot(9000, lambda: w.get_current_tab().edge_resize_requested.connect(lambda e: (edge_msgs.append(e), out("EDGE " + e))))
QTimer.singleShot(12000, check)
QTimer.singleShot(45000, edges)
QTimer.singleShot(46000, app.quit)
app.exec()
