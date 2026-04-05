from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt


class FileExistsDialog(QDialog):
    RENAME = 1
    OVERWRITE = 2
    SKIP = 3

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件已存在")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"文件已存在：\n{filename}"))
        layout.addWidget(QLabel("请选择操作："))

        btn_layout = QHBoxLayout()
        self.rename_btn = QPushButton("重命名")
        self.overwrite_btn = QPushButton("覆盖")
        self.skip_btn = QPushButton("跳过")
        self.rename_btn.clicked.connect(lambda: self.done(self.RENAME))
        self.overwrite_btn.clicked.connect(lambda: self.done(self.OVERWRITE))
        self.skip_btn.clicked.connect(lambda: self.done(self.SKIP))
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.overwrite_btn)
        btn_layout.addWidget(self.skip_btn)
        layout.addLayout(btn_layout)