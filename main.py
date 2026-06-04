import os
import sys
import time
import app_logger

venv_dir = os.path.dirname(os.path.dirname(sys.executable))
current_v = "0.7.0"

qt_plugins = os.path.join(
    venv_dir,
    "Lib",
    "site-packages",
    "PyQt5",
    "Qt5",
    "plugins"
)

platforms = os.path.join(qt_plugins, "platforms")

from PyQt5 import QtWidgets, QtCore, QtGui
from ui_dialogs import ConfirmDialog, RoundedDialog
from login_window import LoginWindow
from api_client import check_saved_session, get_saved_session_username, clear_saved_session

class StartupWorker(QtCore.QThread):
    step = QtCore.pyqtSignal(int, str) 
    done = QtCore.pyqtSignal()

    def run(self):
        self.step.emit(15, "Запуск…")
        self.msleep(520)

        self.step.emit(45, "Проверка соединения…")
        self.msleep(800)

        self.step.emit(75, "Проверка сессии…")
        try:
            get_saved_session_username()
        except Exception:
            pass
        self.msleep(800)

        self.step.emit(100, "Готово")
        self.msleep(360)
        self.done.emit()


class StartupWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.current_widget = None
        self.fade_in_anim = None
        self.fade_out_anim = None

        self.loading_label = None
        self.pct_label = None
        self.progress = None
        self._bar_anim = None

        self.setWindowTitle("RetinopatiaApp")
        self.setFixedSize(470, 370)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.show_loading()

    def fade_to_widget(self, new_widget):
        old_widget = self.current_widget
        self.current_widget = new_widget

        new_widget.show()
        new_widget.raise_()

        fade_in_effect = QtWidgets.QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(fade_in_effect)
        fade_in_effect.setOpacity(0)

        self.fade_in_anim = QtCore.QPropertyAnimation(fade_in_effect, b"opacity")
        self.fade_in_anim.setDuration(450)
        self.fade_in_anim.setStartValue(0)
        self.fade_in_anim.setEndValue(1)
        self.fade_in_anim.start()

        if old_widget:
            fade_out_effect = QtWidgets.QGraphicsOpacityEffect(old_widget)
            old_widget.setGraphicsEffect(fade_out_effect)
            fade_out_effect.setOpacity(1)

            self.fade_out_anim = QtCore.QPropertyAnimation(fade_out_effect, b"opacity")
            self.fade_out_anim.setDuration(450)
            self.fade_out_anim.setStartValue(1)
            self.fade_out_anim.setEndValue(0)
            self.fade_out_anim.finished.connect(old_widget.deleteLater)
            self.fade_out_anim.start()

    def show_loading(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setObjectName("wrapper")
        wrapper.setGeometry(0, 0, 470, 370)
        wrapper.setStyleSheet("""
            #wrapper {
                background-color: #f5f5f5;
                border: 1.2px solid #c7d2e0;
                border-radius: 20px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setSpacing(0)
        layout.setContentsMargins(40, 28, 40, 16)

        layout.addStretch(1)

        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignCenter)

        logo_pixmap = QtGui.QPixmap("assets/logo.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaled(
                    76, 76,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
            )
        else:
            logo_label.setText("◉")
            logo_label.setStyleSheet("QLabel { color:#0078D7; font-size:44px; font-weight:900; }")

        layout.addWidget(logo_label)
        layout.addSpacing(16)

        # --- название ---
        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setAlignment(QtCore.Qt.AlignCenter)
        app_label.setStyleSheet("QLabel { color:#222; font-size:25px; font-weight:bold; }")
        layout.addWidget(app_label)
        layout.addSpacing(22)

        # --- строка статуса: текст слева, проценты справа ---
        status_row = QtWidgets.QWidget()
        status_row.setStyleSheet("background: transparent;")
        status_layout = QtWidgets.QHBoxLayout(status_row)
        status_layout.setContentsMargins(2, 0, 2, 0)
        status_layout.setSpacing(8)

        self.loading_label = QtWidgets.QLabel("Запуск…")
        self.loading_label.setStyleSheet("QLabel { color:#7b828d; font-size:13px; }")

        self.pct_label = QtWidgets.QLabel("0%")
        self.pct_label.setStyleSheet("QLabel { color:#0078D7; font-size:13px; font-weight:600; }")

        status_layout.addWidget(self.loading_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self.pct_label)
        layout.addWidget(status_row)
        layout.addSpacing(9)

        # --- прогресс-бар (детерминированный) ---
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #e3e6ea;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #0078D7;
            }
        """)
        layout.addWidget(self.progress)

        layout.addStretch(1)

        # --- версия снизу ---
        version_label = QtWidgets.QLabel(f"v{current_v}")
        version_label.setAlignment(QtCore.Qt.AlignCenter)
        version_label.setStyleSheet("QLabel { color:#aab0bb; font-size:11px; }")
        layout.addWidget(version_label)

        self.fade_to_widget(wrapper)

    def set_progress(self, value, text=None):
        """Плавно подводит бар к value (0..100) и обновляет статус/проценты."""
        if self.progress is None:
            return
        if text and self.loading_label is not None:
            self.loading_label.setText(text)
        if self.pct_label is not None:
            self.pct_label.setText(f"{int(value)}%")

        self._bar_anim = QtCore.QPropertyAnimation(self.progress, b"value")
        self._bar_anim.setDuration(360)
        self._bar_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._bar_anim.setStartValue(self.progress.value())
        self._bar_anim.setEndValue(int(value))
        self._bar_anim.start()


_log = app_logger.get("main")


class AppController:
    def __init__(self):
        self.startup_window = None
        self.login_window = None
        self.main_window = None
        self.startup_fade_out = None
        self.startup_worker = None
        self._startup_t0 = 0.0

    def start(self):
        _log.info("RetinopatiaApp v%s запускается", current_v)
        self.startup_window = StartupWindow()
        self.startup_window.show()

        self._startup_t0 = time.monotonic()
        self.startup_worker = StartupWorker()
        self.startup_worker.step.connect(self.startup_window.set_progress)
        self.startup_worker.done.connect(self._on_startup_done)
        self.startup_worker.finished.connect(self.startup_worker.deleteLater)
        self.startup_worker.start()

    def _on_startup_done(self):
        elapsed_ms = (time.monotonic() - self._startup_t0) * 1000
        wait = max(0, int(2600 - elapsed_ms))
        QtCore.QTimer.singleShot(wait, self.after_startup_loading)

    def after_startup_loading(self):
        saved_username = get_saved_session_username()
        _log.debug("Проверка сохранённой сессии, username=%s", saved_username)

        def continue_flow():
            if self.startup_window is not None:
                self.startup_window.close()
                self.startup_window = None

            if saved_username:
                if ConfirmDialog.ask(
                    "Найдена прошлая сессия",
                    f"В последний раз вы входили в приложение через аккаунт {saved_username}. Хотите продолжить работу в этом аккаунте или авторизироваться в другом?\n",
                    confirm_text="В этот аккаунт",
                    cancel_text="В другой аккаунт",
                    danger=False,
                ):
                    ok, username, reason = check_saved_session()
                    if ok:
                        _log.info("Автовход по сохранённой сессии: %s", username)
                        self.on_login_success(username)
                        return

                    _log.warning("Сохранённая сессия недействительна: reason=%s", reason)
                    if reason == "access_expired":
                        RoundedDialog.warning(
                            "Лицензия более недействительна",
                            "Срок действия доступа к приложению истёк.\n"
                            "Чтобы продолжить использование приложения рекомендуется обратиться к администратору вашей организации!",
                        )
                    else:
                        RoundedDialog.warning(
                            "Сессия истекла",
                            "Предыдущая сессия более недействительна, пожалуйста войдите заново!",
                        )
                else:
                    _log.debug("Пользователь отказался от автовхода, сессия сброшена")
                    clear_saved_session()

            self.show_login()

        if self.startup_window is not None:
            effect = QtWidgets.QGraphicsOpacityEffect(self.startup_window)
            self.startup_window.setGraphicsEffect(effect)

            anim = QtCore.QPropertyAnimation(effect, b"opacity")
            anim.setDuration(400)
            anim.setStartValue(1)
            anim.setEndValue(0)
            anim.finished.connect(continue_flow)
            anim.start()
            self.startup_fade_out = anim
        else:
            continue_flow()

    def show_login(self):
        _log.debug("Открытие окна авторизации")
        if self.main_window is not None:
            self.main_window.close()
            self.main_window = None

        self.login_window = LoginWindow(on_success=self.on_login_success)
        self.login_window.show()

    def on_login_success(self, username: str):
        _log.info("Успешная авторизация: %s", username)
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None

        from main_window import MainWindow
        self.main_window = MainWindow(username, on_logout=self.show_login)
        self.main_window.show()


def main():
    app_logger.setup()
    app_logger.install_excepthook()

    app = QtWidgets.QApplication(sys.argv)
    controller = AppController()
    controller.start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()