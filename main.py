import os
import sys

venv_dir = os.path.dirname(os.path.dirname(sys.executable))

qt_plugins = os.path.join(
    venv_dir,
    "Lib",
    "site-packages",
    "PyQt5",
    "Qt5",
    "plugins"
)

platforms = os.path.join(qt_plugins, "platforms")

os.environ["QT_PLUGIN_PATH"] = qt_plugins
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms
os.environ["QT_QPA_PLATFORM"] = "windows"

print("[QT FIX] VENV DIR =", venv_dir)
print("[QT FIX] QT_PLUGIN_PATH =", qt_plugins)
print("[QT FIX] PLATFORMS_PATH =", platforms)
from PyQt5 import QtWidgets
from login_window import LoginWindow
from registration_window import RegistrationWindow

class AppController:
    def __init__(self):
        self.login_window = None
        self.reg_window = None
        self.main_window = None

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
    controller.show_login()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
