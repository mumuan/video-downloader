# main.py
import os
import sys

from PyQt6.QtWidgets import QApplication
from src.i18n import init_i18n
from src.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Initialize i18n before creating windows
    init_i18n()

    # 在 PyInstaller 打包模式下，__file__ 为空，使用 _MEIPASS 定位资源
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    style_path = os.path.join(base_dir, "src", "styles.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
