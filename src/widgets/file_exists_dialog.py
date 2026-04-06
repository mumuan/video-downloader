from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QWidget
import enum
from src.i18n import _


class FileExistsDialog(QDialog):
    class Result(enum.IntEnum):
        RENAME = 1
        OVERWRITE = 2
        SKIP = 3

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setObjectName("file_exists_dialog")
        self.setWindowTitle(_("File exists"))
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        content = QWidget()
        content.setObjectName("dialog_content")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        title = QLabel(_("File exists"))
        title.setObjectName("dialog_title")
        content_layout.addWidget(title)

        message = QLabel(f'{_("File already exists in target directory:")}\n"{filename}"\n\n{_("Choose operation:")}')
        message.setObjectName("dialog_message")
        message.setWordWrap(True)
        content_layout.addWidget(message)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.rename_btn = QPushButton(_("Rename"))
        self.rename_btn.setObjectName("dialog_btn")
        self.overwrite_btn = QPushButton(_("Overwrite"))
        self.overwrite_btn.setObjectName("dialog_btn")
        self.overwrite_btn.setProperty("class", "primary")
        self.overwrite_btn.setStyleSheet("background: #3b82f6; color: #ffffff; border: none;")
        self.skip_btn = QPushButton(_("Skip"))
        self.skip_btn.setObjectName("dialog_btn")

        self.rename_btn.clicked.connect(lambda: self.done(self.Result.RENAME))
        self.overwrite_btn.clicked.connect(lambda: self.done(self.Result.OVERWRITE))
        self.skip_btn.clicked.connect(lambda: self.done(self.Result.SKIP))

        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.overwrite_btn)
        btn_layout.addWidget(self.skip_btn)

        content_layout.addLayout(btn_layout)
        layout.addWidget(content)
