"""Runs the real MainWindow hidden (test profile) and writes composited screenshots:
Qt chrome (window.grab) + WebView2 page (CapturePreviewAsync) pasted into the page area."""
import json, os, sys, time, traceback
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "gx_shots")
TESTDATA = os.path.join(HERE, "testdata")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, APP)
os.chdir(APP)
os.environ["ADBLOCK_HIDDEN_WINDOW"] = "1"
os.environ.setdefault("ADBLOCK_REMOTE_DEBUG_PORT", "9333")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from PIL import Image
from main_window import MainWindow
import theme

LOG = os.path.join(OUT, "log.txt")
open(LOG, "w").close()


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


app = QApplication(sys.argv)
w = MainWindow(TESTDATA, initial_url=None)
w.setWindowFlags(w.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
w.resize(1360, 860)
w.move(-20000, -20000)
w.show()


def shot(name):
    try:
        tab = w.get_current_tab()
        page = os.path.join(OUT, name + "_page.png")
        if os.path.exists(page):
            os.remove(page)
        tab.capture_screenshot(page)
        QTimer.singleShot(1500, lambda: compose(name, page))
    except Exception:
        log(traceback.format_exc())


def compose(name, page):
    try:
        chrome = w.grab()
        dpr = chrome.devicePixelRatio()
        cpath = os.path.join(OUT, name + "_chrome.png")
        chrome.save(cpath)
        base = Image.open(cpath).convert("RGB")
        if os.path.exists(page):
            pos = w.page_stack.mapTo(w, QPoint(0, 0))
            size = (int(w.page_stack.width() * dpr), int(w.page_stack.height() * dpr))
            img = Image.open(page).convert("RGB").resize(size)
            base.paste(img, (int(pos.x() * dpr), int(pos.y() * dpr)))
        base.save(os.path.join(OUT, name + ".png"))
        log(f"shot {name} ok ({base.size[0]}x{base.size[1]}, dpr {dpr})")
    except Exception:
        log(traceback.format_exc())


def set_accent(color):
    w.ui.set("accent", color)
    w.on_design_changed()
    log("accent " + color)


def dialog_shots():
    try:
        from design_dialog import DesignDialog
        from adblock_dialog import AdBlockDialog
        d1 = DesignDialog(w.ui, lambda: None, w)
        d1.show()
        tab = w.get_current_tab()
        d2 = AdBlockDialog(w.filter_engine, tab.current_url_str, tab.blocked_count, w, ad_logger=w.ad_logger,
                           accent=w.ui["accent"])
        d2.resize(720, 560)
        d2.show()

        def grab():
            d1.grab().save(os.path.join(OUT, "dlg_design.png"))
            d2.grab().save(os.path.join(OUT, "dlg_shield.png"))
            d1.close(); d2.close()
            log("dialogs ok")
        QTimer.singleShot(800, grab)
    except Exception:
        log(traceback.format_exc())


def scroll(y):
    w.get_current_tab().wv.CoreWebView2.ExecuteScriptAsync(f"window.scrollTo(0, {y})")


def history_shot():
    try:
        from history_dialog import HistoryDialog
        d = HistoryDialog(w.bm_manager, w)
        d.show()
        QTimer.singleShot(600, lambda: (d.grab().save(os.path.join(OUT, "dlg_history.png")), d.close(), log("history ok")))
    except Exception:
        log(traceback.format_exc())


steps = [
    (12000, lambda: set_accent("#3d8bff")),
    (15000, lambda: shot("4_eisblau")),
    (18000, lambda: set_accent("#fa1e4e")),
    (19000, app.quit),
]
for ms, fn in steps:
    QTimer.singleShot(ms, fn)
app.exec()
