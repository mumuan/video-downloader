# main.py
import os
import sys

# --- PyInstaller frozen mode: point Playwright to bundled browsers ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    bundled_browsers = os.path.join(sys._MEIPASS, 'ms-playwright')
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = bundled_browsers

from PyQt6.QtWidgets import QApplication
from src.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
