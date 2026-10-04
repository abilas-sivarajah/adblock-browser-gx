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
    # Enable hardware acceleration and modern web features
    app = QApplication(sys.argv)
    app.setApplicationName("AdBlock Browser")
    app.setApplicationDisplayName("AdBlock Browser")
    app.setOrganizationName("AdBlockDev")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    data_dir = get_app_data_dir()
    initial_url = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    window = MainWindow(data_dir, initial_url=initial_url)
    if os.environ.get("ADBLOCK_HIDDEN_WINDOW"):
        # Test mode: off-screen, no focus, no taskbar entry (does not disturb fullscreen apps/games)
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        window.setWindowFlags(window.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        window.move(-20000, -20000)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
