import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from launcher.config import load_config, save_config
from launcher.installer import get_latest_version, get_recent_versions, install_latest, install_version

APP_NAME = "WWMRU"
WIN_W, WIN_H = 1536, 864


def res_path(*parts) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "resources"
    else:
        base = Path(__file__).resolve().parent.parent / "resources"
    return base / Path(*parts)


class Switch(QtWidgets.QCheckBox):
    pass


class UpdateCheckWorker(QtCore.QThread):
    done = QtCore.Signal(bool, str, str)

    def run(self):
        try:
            v, notes = get_latest_version()
            self.done.emit(True, v, notes)
        except Exception as e:
            self.done.emit(False, "unknown", str(e))


class RecentVersionsWorker(QtCore.QThread):
    done = QtCore.Signal(bool, list, str)

    def run(self):
        try:
            versions = get_recent_versions(limit=5)
            self.done.emit(True, versions, "")
        except Exception as e:
            self.done.emit(False, [], str(e))


class InstallWorker(QtCore.QThread):
    done = QtCore.Signal(bool, str, str)

    def __init__(self, game_root: str, tag: str | None = None):
        super().__init__()
        self.game_root = game_root
        self.tag = tag

    def run(self):
        if self.tag:
            ok, version, msg = install_version(self.game_root, self.tag)
        else:
            ok, version, msg = install_latest(self.game_root)
        self.done.emit(ok, version, msg)


class WWMRUWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setFixedSize(WIN_W, WIN_H)
        self.setWindowTitle(APP_NAME)

        self.cfg = load_config()
        self.latest_version = None

        qss_path = res_path("style.qss")
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

        root = QtWidgets.QWidget()
        self.setCentralWidget(root)

        self.bg = QtWidgets.QLabel(root)
        self.bg.setGeometry(0, 0, WIN_W, WIN_H)
        self._bg_pix = QtGui.QPixmap(str(res_path("bg.png")))
        self._apply_background()
        self.bg.lower()

        self.shell = QtWidgets.QFrame(root)
        self.shell.setObjectName("Shell")
        self.shell.setGeometry(220, 90, WIN_W - 440, WIN_H - 180)

        shell_layout = QtWidgets.QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(26, 22, 26, 22)
        shell_layout.setSpacing(16)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(14)

        title_box = QtWidgets.QVBoxLayout()
        self.lblTitle = QtWidgets.QLabel("WWMRU")
        self.lblTitle.setObjectName("Title")
        title_box.addWidget(self.lblTitle)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        self.lblVersion = QtWidgets.QLabel(f"Текущая версия: {self.cfg.get('installed_version','—')}")
        self.lblVersion.setObjectName("Sub")
        row.addWidget(self.lblVersion)

        self.btnRefresh = QtWidgets.QPushButton("Обновить")
        self.btnRefresh.setObjectName("GhostBtn")
        self.btnRefresh.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.btnRefresh.clicked.connect(self.check_updates)
        row.addWidget(self.btnRefresh)

        row.addStretch(1)
        title_box.addLayout(row)

        top.addLayout(title_box)
        top.addStretch(1)

        self.btnMin = QtWidgets.QPushButton("—")
        self.btnMin.setObjectName("WinBtn")
        self.btnMin.clicked.connect(self._hide_to_tray)

        self.btnClose = QtWidgets.QPushButton("×")
        self.btnClose.setObjectName("WinBtnClose")
        self.btnClose.clicked.connect(self._exit_app)

        top.addWidget(self.btnMin)
        top.addWidget(self.btnClose)
        shell_layout.addLayout(top)

        self.seg = QtWidgets.QFrame()
        self.seg.setObjectName("Segment")
        seg_layout = QtWidgets.QHBoxLayout(self.seg)
        seg_layout.setContentsMargins(6, 6, 6, 6)
        seg_layout.setSpacing(6)

        self.tabInstall = QtWidgets.QPushButton("Установка")
        self.tabInstall.setCheckable(True)
        self.tabInstall.setChecked(True)
        self.tabInstall.setObjectName("SegBtn")

        self.tabSettings = QtWidgets.QPushButton("Настройки")
        self.tabSettings.setCheckable(True)
        self.tabSettings.setObjectName("SegBtn")

        grp = QtWidgets.QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self.tabInstall, 0)
        grp.addButton(self.tabSettings, 1)
        grp.idClicked.connect(self.on_tab_changed)

        seg_layout.addWidget(self.tabInstall)
        seg_layout.addWidget(self.tabSettings)
        shell_layout.addWidget(self.seg)

        self.stack = QtWidgets.QStackedWidget()
        shell_layout.addWidget(self.stack, 1)

        self.page_install = self._build_install_page()
        self.page_settings = self._build_settings_page()
        self.stack.addWidget(self.page_install)
        self.stack.addWidget(self.page_settings)

        self._drag_offset = None

        self.tray = None
        self._init_tray()

        QtCore.QTimer.singleShot(120, self.check_updates)
        QtCore.QTimer.singleShot(200, self.load_recent_versions)

    def _apply_background(self):
        if self._bg_pix.isNull():
            return
        self.bg.setPixmap(
            self._bg_pix.scaled(
                self.width(),
                self.height(),
                QtCore.Qt.IgnoreAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg.setGeometry(0, 0, self.width(), self.height())
        self._apply_background()

    def _init_tray(self):
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = res_path("wwmru.ico")
        icon = QtGui.QIcon(str(icon_path))
        if icon.isNull():
            icon = self.windowIcon()

        self.tray = QtWidgets.QSystemTrayIcon(self)
        self.tray.setIcon(icon)
        self.tray.setToolTip("WWMRU")

        menu = QtWidgets.QMenu()
        act_show = menu.addAction("Открыть WWMRU")
        act_show.triggered.connect(self._tray_show)
        menu.addSeparator()
        act_exit = menu.addAction("Выход")
        act_exit.triggered.connect(self._tray_exit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self._tray_show()

    def _tray_show(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_exit(self):
        self._exit_app()

    def _hide_to_tray(self):
        self.hide()
        if self.tray:
            self.tray.showMessage("WWMRU", "Свернуто в трей", QtWidgets.QSystemTrayIcon.Information, 1200)

    def _exit_app(self):
        if self.tray:
            self.tray.hide()
        QtWidgets.QApplication.quit()

    def _build_install_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        card = QtWidgets.QFrame()
        card.setObjectName("Card")
        card_l = QtWidgets.QVBoxLayout(card)
        card_l.setContentsMargins(18, 16, 18, 18)
        card_l.setSpacing(12)

        title = QtWidgets.QLabel("Директория игры")
        title.setObjectName("CardTitle")
        card_l.addWidget(title)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        self.editGame = QtWidgets.QLineEdit()
        self.editGame.setObjectName("Input")
        self.editGame.setPlaceholderText("Выберите папку с игрой...")
        self.editGame.setText(self.cfg.get("game_root", ""))

        self.btnBrowse = QtWidgets.QPushButton("Обзор")
        self.btnBrowse.setObjectName("GhostBtn")
        self.btnBrowse.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
        self.btnBrowse.clicked.connect(self.on_pick_folder)

        row.addWidget(self.editGame, 1)
        row.addWidget(self.btnBrowse)
        card_l.addLayout(row)

        info = QtWidgets.QFrame()
        info.setObjectName("InfoBox")
        info_l = QtWidgets.QVBoxLayout(info)
        info_l.setContentsMargins(14, 12, 14, 12)
        info_l.setSpacing(6)

        info_title = QtWidgets.QHBoxLayout()
        icon = QtWidgets.QLabel("i")
        icon.setObjectName("InfoIcon")
        info_title.addWidget(icon)
        lbl = QtWidgets.QLabel("Перед установкой убедитесь, что:")
        lbl.setObjectName("InfoTitle")
        info_title.addWidget(lbl)
        info_title.addStretch(1)
        info_l.addLayout(info_title)

        bullets = QtWidgets.QLabel(
            "• Игра закрыта\n• Выбрана корректная директория игры\n• Достаточно свободного места на диске"
        )
        bullets.setObjectName("InfoText")
        info_l.addWidget(bullets)
        card_l.addWidget(info)

        self.btnInstall = QtWidgets.QPushButton("Установить русификатор")
        self.btnInstall.setObjectName("PrimaryBtn")
        self.btnInstall.clicked.connect(self.on_install_latest)
        card_l.addWidget(self.btnInstall)

        self.lblStatus = QtWidgets.QLabel("")
        self.lblStatus.setObjectName("StatusText")
        card_l.addWidget(self.lblStatus)

        lay.addWidget(card)
        lay.addStretch(1)
        return w

    def _build_settings_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        card = QtWidgets.QFrame()
        card.setObjectName("Card")
        card_l = QtWidgets.QVBoxLayout(card)
        card_l.setContentsMargins(18, 16, 18, 18)
        card_l.setSpacing(14)

        row1 = QtWidgets.QHBoxLayout()
        t1 = QtWidgets.QVBoxLayout()
        a = QtWidgets.QLabel("Создавать резервную копию")
        a.setObjectName("RowTitle")
        b = QtWidgets.QLabel("Сохранить оригинальные файлы только перед первой установкой")
        b.setObjectName("RowSub")
        t1.addWidget(a)
        t1.addWidget(b)
        row1.addLayout(t1, 1)

        self.swBackup = Switch()
        self.swBackup.setObjectName("Switch")
        self.swBackup.setChecked(bool(self.cfg.get("backup_enabled", True)))
        self.swBackup.stateChanged.connect(self.on_backup_toggle)
        row1.addWidget(self.swBackup)
        card_l.addLayout(row1)

        line = QtWidgets.QFrame()
        line.setObjectName("Divider")
        card_l.addWidget(line)

        rb_title = QtWidgets.QLabel("Откат версии")
        rb_title.setObjectName("CardTitle")
        card_l.addWidget(rb_title)

        rb_row = QtWidgets.QHBoxLayout()
        rb_row.setSpacing(10)

        self.cmbVersions = QtWidgets.QComboBox()
        self.cmbVersions.setObjectName("Input")

        self.btnInstallSelected = QtWidgets.QPushButton("Установить выбранную")
        self.btnInstallSelected.setObjectName("GhostBtn")
        self.btnInstallSelected.clicked.connect(self.on_install_selected)

        rb_row.addWidget(self.cmbVersions, 1)
        rb_row.addWidget(self.btnInstallSelected)
        card_l.addLayout(rb_row)

        self.lblRollbackStatus = QtWidgets.QLabel("")
        self.lblRollbackStatus.setObjectName("InfoText2")
        card_l.addWidget(self.lblRollbackStatus)

        line2 = QtWidgets.QFrame()
        line2.setObjectName("Divider")
        card_l.addWidget(line2)

        info_title = QtWidgets.QLabel("Информация")
        info_title.setObjectName("CardTitle")
        card_l.addWidget(info_title)

        info = QtWidgets.QLabel(
            "• Источник: GitHub Releases\n"
            "• Бэкап оригиналов: WWMRU/backup/original\n"
            "• Файлы: translate_words_map_en (+ diff при наличии)"
        )
        info.setObjectName("InfoText2")
        card_l.addWidget(info)

        lay.addWidget(card)
        lay.addStretch(1)

        self._fill_versions_combo(self.cfg.get("recent_versions", []))
        return w

    def on_tab_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def on_backup_toggle(self, _state: int):
        self.cfg["backup_enabled"] = bool(self.swBackup.isChecked())
        save_config(self.cfg)

    def on_pick_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Выбери папку игры (или папку уровнем выше)")
        if d:
            self.editGame.setText(d)
            self.cfg["game_root"] = d
            save_config(self.cfg)

    def check_updates(self):
        self.btnRefresh.setEnabled(False)
        self.btnRefresh.setText("Проверяю…")
        self.worker = UpdateCheckWorker()
        self.worker.done.connect(self.on_update_check_done)
        self.worker.start()

    def on_update_check_done(self, ok: bool, latest_version: str, notes_or_error: str):
        self.btnRefresh.setEnabled(True)
        self.btnRefresh.setText("Обновить")

        if not ok:
            self.latest_version = None
            self.lblStatus.setText(f"Не удалось проверить обновления: {notes_or_error}")
            return

        self.latest_version = latest_version
        installed = self.cfg.get("installed_version", "—")

        if installed == latest_version:
            self.btnInstall.setText("Переустановить русификатор")
            self.lblStatus.setText(f"Обновлений нет. Последняя версия: {latest_version}")
        else:
            self.btnInstall.setText(f"Установить версию {latest_version}")
            self.lblStatus.setText(f"Доступна версия: {latest_version}")
            if self.tray:
                self.tray.showMessage("WWMRU", f"Доступна версия {latest_version}", QtWidgets.QSystemTrayIcon.Information, 2200)

    def load_recent_versions(self):
        self.vers_worker = RecentVersionsWorker()
        self.vers_worker.done.connect(self.on_recent_versions_loaded)
        self.vers_worker.start()

    def on_recent_versions_loaded(self, ok: bool, versions: list, error: str):
        if not ok:
            self.lblRollbackStatus.setText(f"Не удалось загрузить релизы: {error}")
            return

        self.cfg["recent_versions"] = versions[:5]
        save_config(self.cfg)
        self._fill_versions_combo(self.cfg["recent_versions"])
        self.lblRollbackStatus.setText("")

    def _fill_versions_combo(self, versions: list):
        self.cmbVersions.blockSignals(True)
        self.cmbVersions.clear()
        current = self.cfg.get("installed_version", "—")

        if versions:
            for v in versions[:5]:
                label = f"{v} (установлено)" if v == current else v
                self.cmbVersions.addItem(label, v)
        else:
            self.cmbVersions.addItem("Нет данных", "")

        self.cmbVersions.blockSignals(False)

    def _get_game_root(self) -> str:
        return self.editGame.text().strip()

    def on_install_latest(self):
        game_root = self._get_game_root()
        if not game_root:
            self.lblStatus.setText("Укажи папку игры.")
            return

        self.cfg["game_root"] = game_root
        save_config(self.cfg)

        self.btnInstall.setEnabled(False)
        self.btnInstall.setText("Устанавливаю…")
        self.lblStatus.setText("Скачиваю и заменяю файлы…")

        self.inst_worker = InstallWorker(game_root, tag=None)
        self.inst_worker.done.connect(self.on_install_done)
        self.inst_worker.start()

    def on_install_selected(self):
        game_root = self._get_game_root()
        if not game_root:
            self.lblRollbackStatus.setText("Укажи папку игры на вкладке «Установка».")
            return

        tag = self.cmbVersions.currentData()
        if not tag:
            self.lblRollbackStatus.setText("Не выбрана версия.")
            return

        self.btnInstallSelected.setEnabled(False)
        self.lblRollbackStatus.setText(f"Устанавливаю {tag}…")

        self.rb_worker = InstallWorker(game_root, tag=str(tag))
        self.rb_worker.done.connect(self.on_rollback_done)
        self.rb_worker.start()

    def on_rollback_done(self, ok: bool, version: str, message: str):
        self.btnInstallSelected.setEnabled(True)
        self.lblRollbackStatus.setText(message)
        if ok:
            self.cfg["installed_version"] = version
            save_config(self.cfg)
            self.lblVersion.setText(f"Текущая версия: {version}")
            self._fill_versions_combo(self.cfg.get("recent_versions", []))
            self.check_updates()

    def on_install_done(self, ok: bool, version: str, message: str):
        self.btnInstall.setEnabled(True)
        self.btnInstall.setText("Установить русификатор")
        self.lblStatus.setText(message)

        if ok:
            self.cfg["installed_version"] = version
            save_config(self.cfg)
            self.lblVersion.setText(f"Текущая версия: {version}")
            if self.tray:
                self.tray.showMessage("WWMRU", f"Установлена версия {version}", QtWidgets.QSystemTrayIcon.Information, 2200)
            self.load_recent_versions()
            self.check_updates()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if 0 <= event.position().y() <= 90:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


def main():
    app = QtWidgets.QApplication(sys.argv)
    icon_path = res_path("wwmru.ico")
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    w = WWMRUWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
