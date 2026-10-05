"""
Entry point for AdBlock Browser.
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QUrl
from main_window import MainWindow

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def get_app_data_dir() -> str:
    """Returns directory for storing browser profiles, cache, and filter lists."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # ADBLOCK_DATA_DIR: separate profile (tests, or a second instance next to the normal one)
    data_dir = os.environ.get("ADBLOCK_DATA_DIR") or os.path.join(base_dir, "browser_data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def main():
    # GPU flags override the saved setting for this session only (Discord streaming mode)
    initial_url = None
    hw_accel = None
    for arg in sys.argv[1:]:
        arg_lower = arg.lower()
        if arg_lower in ("--discord", "--discord-mode", "--disable-gpu", "--no-gpu"):
            hw_accel = False
        elif arg_lower in ("--enable-gpu", "--gpu"):
            hw_accel = True
        elif not arg.startswith("-") and initial_url is None:
            initial_url = arg

    app = QApplication(sys.argv)
    app.setApplicationName("AdBlock Browser")
    app.setApplicationDisplayName("AdBlock Browser")
    app.setOrganizationName("AdBlockDev")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    data_dir = get_app_data_dir()
    window = MainWindow(data_dir, initial_url=initial_url, hw_accel=hw_accel)
    if os.environ.get("ADBLOCK_HIDDEN_WINDOW"):
        # Test mode: off-screen, no focus, no taskbar entry (does not disturb fullscreen apps/games)
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        window.setWindowFlags(window.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        window.move(-20000, -20000)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
