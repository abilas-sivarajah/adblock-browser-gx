"""Runs the real MainWindow hidden; after 20 s puts youtube.com on the exception list the way the
shield dialog does (without saving), re-registers the site scripts and reloads the tab."""
import os, sys, traceback
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
os.chdir(APP)
os.environ.setdefault("ADBLOCK_HIDDEN_WINDOW", "1")
os.environ.setdefault("ADBLOCK_REMOTE_DEBUG_PORT", "9333")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from main_window import MainWindow

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "manual_harness.log")
os.makedirs(os.path.dirname(LOG), exist_ok=True)
app = QApplication(sys.argv)
w = MainWindow(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata"), initial_url="https://www.heise.de/")
w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
w.setWindowFlags(w.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
w.move(-20000, -20000)
w.show()


def report():
    try:
        folder = w.get_current_tab().report_ad_manually()
        open(LOG, "w").write("REPORT OK " + str(folder))
    except Exception:
        open(LOG, "w").write(traceback.format_exc())


QTimer.singleShot(15000, report)
QTimer.singleShot(22000, app.quit)
app.exec()
