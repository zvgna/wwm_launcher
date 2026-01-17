import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from launcher.config import load_config, save_config
from launcher.installer import install_from_github


APP_NAME = "WWM AutoRussifier"

TARGET_HINT = (
    "Нужен путь к корневой папке, где лежит 'Where Winds Meet' (или сама папка 'Where Winds Meet').\n"
    "Целевые файлы:\n"
    r"Where Winds Meet\Package\HD\oversea\locale\translate_words_map_en\n"
    r"Where Winds Meet\Package\HD\oversea\locale\translate_words_map_en_diff (опционально)"
)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setFixedSize(900, 520)

        self.cfg = load_config()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("WWM AutoRussifier")
        title.setStyleSheet("font-size: 26px; font-weight: 700;")

        hint = QtWidgets.QLabel(TARGET_HINT)
        hint.setWordWrap(True)

        self.path_edit = QtWidgets.QLineEdit(self.cfg.get("game_root", ""))
        self.path_edit.setPlaceholderText(r"Путь: D:\Steam\steamapps\common  или  D:\Steam\steamapps\common\Where Winds Meet")

        btn_pick = QtWidgets.QPushButton("Выбрать папку…")
        btn_pick.clicked.connect(self.pick_dir)

        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(btn_pick)

        self.owner_edit = QtWidgets.QLineEdit(self.cfg.get("github_owner", "YOUR_OWNER"))
        self.owner_edit.setPlaceholderText("GitHub owner (ник или org)")

        self.repo_edit = QtWidgets.QLineEdit(self.cfg.get("github_repo", "wwm_localization"))
        self.repo_edit.setPlaceholderText("GitHub repo с релизами")

        btn_install = QtWidgets.QPushButton("Скачать и заменить файлы локализации")
        btn_install.clicked.connect(self.install_update)

        self.status = QtWidgets.QLabel("Готово.")
        self.status.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(path_row)
        layout.addWidget(self.owner_edit)
        layout.addWidget(self.repo_edit)
        layout.addWidget(btn_install)
        layout.addWidget(self.status, 1)

    def pick_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку игры (или папку уровнем выше)")
        if d:
            self.path_edit.setText(d)

    def install_update(self):
        self.cfg["game_root"] = self.path_edit.text().strip()
        self.cfg["github_owner"] = self.owner_edit.text().strip()
        self.cfg["github_repo"] = self.repo_edit.text().strip()
        save_config(self.cfg)

        if not self.cfg["game_root"]:
            self.status.setText("Укажи путь к папке игры.")
            return
        if not self.cfg["github_owner"] or not self.cfg["github_repo"]:
            self.status.setText("Укажи GitHub owner/repo.")
            return
