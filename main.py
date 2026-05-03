import os
import sys

venv_dir = os.path.dirname(os.path.dirname(sys.executable))
current_v = "0.4.0"

qt_plugins = os.path.join(
    venv_dir,
    "Lib",
    "site-packages",
    "PyQt5",
    "Qt5",
    "plugins"
)

platforms = os.path.join(qt_plugins, "platforms")

# Only debug info!
# os.environ["QT_PLUGIN_PATH"] = qt_plugins
# os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms
# os.environ["QT_QPA_PLATFORM"] = "windows"

# print("[QT FIX] VENV DIR =", venv_dir)
# print("[QT FIX] QT_PLUGIN_PATH =", qt_plugins)
# print("[QT FIX] PLATFORMS_PATH =", platforms)

from PyQt5 import QtWidgets
from ui_dialogs import ConfirmDialog, RoundedDialog
from login_window import LoginWindow
from registration_window import RegistrationWindow
from api_client import check_saved_session, get_saved_session_username, clear_saved_session

class AppController:
    def __init__(self):
        self.login_window = None
        self.reg_window = None
        self.main_window = None

    def start(self):
            saved_username = get_saved_session_username()

            if saved_username:
                if ConfirmDialog.ask(
                    "Найдена прошлая сессия",
                    f"В последний раз вы входили в приложение через аккаунт {saved_username}. Хотите продолжить работу в этом аккаунте или авторизироваться в другом?\n",
                    confirm_text="В этот аккаунт",
                    cancel_text="В другой аккаунт",
                    danger=False
                ):
                    ok, username = check_saved_session()
                    if ok:
                        self.on_login_success(username)
                        return

                    RoundedDialog.warning(
                        "Сессия истекла",
                        "Прошлая сессия больше недействительна. Войдите заново."
                    )
                else:
                    clear_saved_session()

            self.show_login()

    def show_login(self):
        if self.reg_window is not None:
            self.reg_window.close()
            self.reg_window = None
        if self.main_window is not None:
            self.main_window.close()
            self.main_window = None

        self.login_window = LoginWindow(
            on_success=self.on_login_success,
            on_open_register=self.show_register,
        )
        self.login_window.show()

    def show_register(self):
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None

        self.reg_window = RegistrationWindow(on_back=self.show_login)
        self.reg_window.show()

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
