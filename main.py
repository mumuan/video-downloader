# main.py
import os
import sys
import faulthandler
# Only enable faulthandler if stderr is available (not available in console=False GUI apps)
if sys.stderr is not None:
    faulthandler.enable()

from PyQt6.QtWidgets import QApplication
from src.i18n import init_i18n
from src.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Initialize i18n before creating windows
    init_i18n()

    # Determine resource base directory
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Load stylesheet
    style_path = os.path.join(base_dir, "styles.qss")
    if not os.path.exists(style_path):
        style_path = os.path.join(base_dir, "src", "styles.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
