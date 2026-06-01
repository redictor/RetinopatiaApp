import os
import sys
import datetime
import functools

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

from PyQt5 import QtWidgets, QtCore, QtGui

from api_client import (
    logout, get_maintenance_status, get_training_history,
    save_training_record, get_profile, get_updates,
)
from ui_dialogs import RoundedDialog, ApiWorker
from ui_styles import create_window_buttons
import app_logger
from main import current_v
from screens.home_screen import HomeScreen
from screens.training_screen import TrainingScreen
from screens.stats_screen import StatsScreen
from screens.settings_screen import SettingsScreen

_log = app_logger.get("window")


class MainWindow(QtWidgets.QWidget):
    def __init__(self, username: str, on_logout):
        super().__init__()
        self.username = username
        self.on_logout = on_logout
        self.old_pos = None

        self.setWindowTitle("RetinopatiaApp")
        self.setFixedSize(1200, 760)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self._build_ui()

        self._maint_forced = False
        self._maint_timer = QtCore.QTimer(self)
        self._maint_timer.timeout.connect(self._check_maintenance)
        self._maint_timer.start(15000)

        self._stats_timer = QtCore.QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats_and_home)
        self._stats_timer.start(60000)

        QtCore.QTimer.singleShot(300, self._load_account_status_async)

    def _build_ui(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setObjectName("mainWrapper")
        wrapper.setGeometry(0, 0, 1200, 760)
        wrapper.setStyleSheet("""
            QWidget#mainWrapper {
                background-color: #f5f5f5;
                border: 1.2px solid #c7d2e0;
                border-radius: 20px;
            }
        """)

        root = QtWidgets.QVBoxLayout(wrapper)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        top_bar = QtWidgets.QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background: transparent;")
        top_bar.mousePressEvent = self._top_mouse_press
        top_bar.mouseMoveEvent = self._top_mouse_move
        top_bar.mouseReleaseEvent = self._top_mouse_release

        top = QtWidgets.QHBoxLayout(top_bar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        brand = QtWidgets.QWidget()
        brand.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        brand_layout = QtWidgets.QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(8)

        logo_label = QtWidgets.QLabel()
        logo_label.setFixedSize(36, 36)
        logo_label.setAlignment(QtCore.Qt.AlignCenter)
        logo_pixmap = QtGui.QPixmap("assets/logo.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            )
        else:
            logo_label.setText("◉")
            logo_label.setStyleSheet("QLabel { color: #0078D7; font-size: 18px; font-weight: 900; }")

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("QLabel { color: #222; font-size: 18px; font-weight: 600; }")

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(app_label)

        drag_area = QtWidgets.QWidget()
        drag_area.setStyleSheet("background: transparent;")
        drag_area.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        minimize_button, close_button = create_window_buttons(self)

        top.addWidget(brand)
        top.addStretch(1)
        top.addWidget(drag_area, 1)
        top.addWidget(minimize_button)
        top.addWidget(close_button)
        root.addWidget(top_bar)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)

        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame { background-color: #ffffff; border-radius: 16px; }
        """)

        side_layout = QtWidgets.QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)
        side_layout.addSpacing(6)

        self.btn_home = self.menu_button("Главная", "assets/icons/home.png")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self.set_page(0))
        side_layout.addWidget(self.btn_home)

        self.btn_training = self.menu_button("Обучение", "assets/icons/training.png")
        self.btn_training.clicked.connect(lambda: self.set_page(1))
        side_layout.addWidget(self.btn_training)

        self.btn_stats = self.menu_button("Статистика", "assets/icons/stats.png")
        self.btn_stats.clicked.connect(lambda: self.set_page(2))
        side_layout.addWidget(self.btn_stats)

        side_layout.addStretch(1)

        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e6e6e6;")
        side_layout.addWidget(line)

        self.btn_settings = self.menu_button("Настройки", "assets/icons/settings.png")
        self.btn_settings.setChecked(False)
        self.btn_settings.clicked.connect(lambda: self.set_page(3))
        side_layout.addWidget(self.btn_settings)

        content = QtWidgets.QFrame()
        content.setStyleSheet("""
            QFrame { background-color: #ffffff; border-radius: 16px; }
        """)

        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        self.home_screen = HomeScreen(self.username)
        self.training_screen = TrainingScreen(on_save_record=self._stats_append)
        self.stats_screen = StatsScreen()
        self.settings_screen = SettingsScreen(self.username)

        self.home_screen.btn_start_training.clicked.connect(lambda: self.set_page(1))
        self.home_screen.btn_open_stats.clicked.connect(lambda: self.set_page(2))
        self.home_screen.btn_open_settings.clicked.connect(lambda: self.set_page(3))

        self.settings_screen.logout_requested.connect(self._do_logout)
        self.settings_screen.stats_reset.connect(self._refresh_stats_and_home)

        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self.home_screen)
        self.pages.addWidget(self.training_screen)
        self.pages.addWidget(self.stats_screen)
        self.pages.addWidget(self.settings_screen)
        self.pages.setStyleSheet("""
            QWidget { background: transparent; }
            QLabel  { background: transparent; }
        """)
        content_layout.addWidget(self.pages)

        body.addWidget(sidebar)
        body.addWidget(content, 1)
        root.addLayout(body)

        QtCore.QTimer.singleShot(0, self._refresh_stats_and_home)
        QtCore.QTimer.singleShot(1200, self._check_update)

    def set_page(self, index: int):
        self.pages.setCurrentIndex(index)
        self.btn_home.setChecked(index == 0)
        self.btn_training.setChecked(index == 1)
        self.btn_stats.setChecked(index == 2)
        self.btn_settings.setChecked(index == 3)

    def menu_button(self, text: str, icon_path: str) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(text)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setIconSize(QtCore.QSize(20, 20))
        btn.setFixedHeight(44)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left; padding-left: 14px; padding-right: 12px;
                font-size: 14px; border: none; border-radius: 10px; color: #222;
            }
            QPushButton:hover  { background-color: #f3f3f3; }
            QPushButton:checked { background-color: #0078D7; color: white; }
        """)
        btn.setCheckable(True)
        return btn

    def _top_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def _top_mouse_move(self, event):
        if event.buttons() & QtCore.Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def _top_mouse_release(self, event):
        self.old_pos = None

    def _on_maint_ok(self, st: dict):
        if st.get("enabled"):
            self._maint_forced = True
            self._maint_timer.stop()
            msg = st.get("message") or "Ведутся технические работы. Доступ временно запрещён."
            _log.warning("Технические работы на сервере: %s", msg)
            RoundedDialog.warning("Технические работы", "Сообщение от сервера: " + msg + "\n\n...")
            try:
                logout()
            except Exception:
                _log.debug("Ошибка при выходе во время техработ", exc_info=True)
            self.close()
            if self.on_logout:
                self.on_logout()

    def _check_maintenance(self):
        if self._maint_forced:
            return
        w = ApiWorker(get_maintenance_status)
        w.ok.connect(self._on_maint_ok)
        w.fail.connect(lambda err: _log.debug("Ошибка проверки статуса техработ: %s", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._maint_worker = w

    def _refresh_stats_and_home(self):
        w = ApiWorker(get_training_history, 2000)
        w.ok.connect(self.home_screen.apply_stats)
        w.ok.connect(self.stats_screen.apply_data)
        w.fail.connect(lambda err: _log.warning("Ошибка загрузки статистики: %s", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._stats_worker = w

    def _stats_append(self, rec: dict):
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        fn = functools.partial(
            save_training_record,
            user_stage=int(rec.get("user_stage", 0)),
            ai_stage=int(rec.get("ai_stage", 0)),
            score=int(rec.get("score", 0)),
            dice=float(rec.get("dice", 0.0)),
            p_max=float(rec.get("p_max", 0.0)),
            ts=ts,
        )
        w = ApiWorker(fn)
        w.fail.connect(lambda err: _log.warning("Ошибка сохранения записи тренировки: %s", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._save_record_worker = w

    def _ver_tuple(self, v: str):
        s = (v or "").strip().lower()
        if s.startswith("v."):
            s = s[2:]
        elif s.startswith("v"):
            s = s[1:]
        nums = []
        for p in s.split("."):
            try:
                nums.append(int(p))
            except (ValueError, TypeError):
                nums.append(0)
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums[:3])

    def _check_update(self):
        w = ApiWorker(get_updates)
        w.ok.connect(self._on_update_check_done)
        w.fail.connect(lambda err: _log.debug("Ошибка проверки обновлений: %s", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._check_update_worker = w

    def _on_update_check_done(self, updates):
        try:
            if not updates:
                return
            latest = max(updates, key=lambda u: int(u.get("id", 0) or 0))
            latest_ver = str(latest.get("version", "")).strip()
            if not latest_ver:
                return
            if self._ver_tuple(latest_ver) > self._ver_tuple(current_v):
                _log.info("Доступно обновление: текущая=%s, новая=%s", current_v, latest_ver)
                RoundedDialog.info(
                    "Доступно обновление",
                    f"Установлена версия: {current_v}\n"
                    f"Доступна версия: {latest_ver}",
                )
        except Exception:
            _log.debug("Ошибка при проверке обновлений", exc_info=True)

    def _load_account_status_async(self):
        w = ApiWorker(get_profile)
        w.ok.connect(self._on_profile_loaded)
        w.fail.connect(lambda err: _log.warning("Ошибка загрузки профиля: %s", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._profile_worker = w

    def _on_profile_loaded(self, profile):
        try:
            self.home_screen.apply_profile(profile)
            self.settings_screen.apply_profile(profile)
        except Exception:
            _log.error("Ошибка применения профиля к экранам", exc_info=True)

    def _do_logout(self):
        self.close()
        if self.on_logout:
            self.on_logout()