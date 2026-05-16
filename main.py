import os
import sys

venv_dir = os.path.dirname(os.path.dirname(sys.executable))
current_v = "0.5.0"

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


class StartupWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.current_widget = None
        self.fade_in_anim = None
        self.fade_out_anim = None

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
        wrapper.setGeometry(0, 0, 470, 370)
        wrapper.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 20px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 30, 30, 30)

        layout.addStretch(1)

        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignCenter)

        logo_pixmap = QtGui.QPixmap("assets/logo.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaled(
                    72, 72,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
            )
        else:
            logo_label.setText("◉")
            logo_label.setStyleSheet("""
                QLabel {
                    color: #0078D7;
                    font-size: 44px;
                    font-weight: 900;
                }
            """)

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setAlignment(QtCore.Qt.AlignCenter)
        app_label.setStyleSheet("""
            QLabel {
                color: #222;
                font-size: 26px;
                font-weight: bold;
            }
        """)

        loading_label = QtWidgets.QLabel("Загрузка приложения...")
        loading_label.setAlignment(QtCore.Qt.AlignCenter)
        loading_label.setStyleSheet("""
            QLabel {
                color: #777;
                font-size: 13px;
            }
        """)

        progress = QtWidgets.QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedHeight(12)
        progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #ddd;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #0078D7;
            }
        """)

        layout.addWidget(logo_label)
        layout.addWidget(app_label)
        layout.addWidget(loading_label)
        layout.addWidget(progress)

        layout.addStretch(1)

        self.fade_to_widget(wrapper)


class AppController:
    def __init__(self):
        self.startup_window = None
        self.login_window = None
        self.main_window = None
        self.startup_fade_out = None

    def start(self):
        self.startup_window = StartupWindow()
        self.startup_window.show()

        QtCore.QTimer.singleShot(2700, self.after_startup_loading)

    def after_startup_loading(self):
        saved_username = get_saved_session_username()

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
                    danger=False
                ):
                    ok, username, reason = check_saved_session()
                    if ok:
                        self.on_login_success(username)
                        return

                    if reason == "access_expired":
                        RoundedDialog.warning(
                            "Лицензия более недействительна",
                            "Срок действия доступа к приложению истёк.\n"
                            "Чтобы продолжить использование приложения рекомендуется обратиться к администратору вашей организации!"
                        )
                    else:
                        RoundedDialog.warning(
                            "Сессия истекла",
                            "Предыдущая сессия более недействительна, пожалуйста войдите заново!"
                        )

                    RoundedDialog.warning(
                        "Сессия истекла",
                        "Предыдущая сессия более недействительна, пожалуйста войдите заново!"
                    )
                else:
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
        if self.main_window is not None:
            self.main_window.close()
            self.main_window = None

        self.login_window = LoginWindow(
            on_success=self.on_login_success,
        )
        self.login_window.show()

    def on_login_success(self, username: str):
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None

        from main_window import MainWindow
        self.main_window = MainWindow(username, on_logout=self.show_login)
        self.main_window.show()

def main():
    app = QtWidgets.QApplication(sys.argv)
    controller = AppController()
    controller.start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()