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

    if getattr(sys, "frozen", False):
        os.environ["PATH"] = base_dir + os.pathsep + os.environ.get("PATH", "")
        vlc_plugin_path = os.path.join(base_dir, "plugins")
        if os.path.isdir(vlc_plugin_path):
            os.environ["VLC_PLUGIN_PATH"] = vlc_plugin_path
        playwright_browsers_path = os.path.join(base_dir, "ms-playwright")
        if os.path.isdir(playwright_browsers_path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = playwright_browsers_path

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
