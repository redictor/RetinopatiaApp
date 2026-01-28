from PyQt5 import QtWidgets, QtCore
from api_client import authenticate_user
from api_client import get_maintenance_status
from ui_dialogs import RoundedDialog

class LoginWindow(QtWidgets.QWidget):
    def __init__(self, on_success, on_open_register):
        super().__init__()
        self.on_success = on_success
        self.on_open_register = on_open_register

        self.setWindowTitle("Авторизация")
        self.setFixedSize(470, 370)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.initUI()

    def initUI(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setGeometry(0, 0, 470, 370)
        wrapper.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 20px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setSpacing(15)

        window_buttons_layout = QtWidgets.QHBoxLayout()
        window_buttons_layout.setSpacing(8)
        window_buttons_layout.setContentsMargins(10, 0, 10, 0)

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 18px;
                font-weight: bold;
            }
        """)

        drag_area = QtWidgets.QWidget()
        drag_area.setFixedHeight(40)
        drag_area.setStyleSheet("background-color: transparent;")
        drag_area.mousePressEvent = self.mousePressEvent
        drag_area.mouseMoveEvent = self.mouseMoveEvent

        minimize_button = QtWidgets.QPushButton("--")
        minimize_button.setFixedSize(30, 30)
        minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #FFA500;
                border: none;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #FF8C00; }
        """)
        minimize_button.clicked.connect(self.showMinimized)

        close_button = QtWidgets.QPushButton("✕")
        close_button.setFixedSize(30, 30)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                border: none;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #CC0000; }
        """)
        close_button.clicked.connect(self.close)

        window_buttons_layout.addWidget(app_label)
        window_buttons_layout.addStretch(1)
        window_buttons_layout.addWidget(drag_area, 1)
        window_buttons_layout.addWidget(minimize_button)
        window_buttons_layout.addWidget(close_button)

        layout.addLayout(window_buttons_layout)

        title_label = QtWidgets.QLabel("Вход в аккаунт")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        layout.addWidget(title_label)

        self.username_input = self.create_input("Логин")
        self.password_input = self.create_input("Пароль", True)

        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)

        login_button = QtWidgets.QPushButton("Войти")
        login_button.setFixedHeight(40)
        login_button.setStyleSheet(self.button_style("#0078D7"))
        login_button.clicked.connect(self.login)
        layout.addWidget(login_button)

        register_label = QtWidgets.QLabel('Нет аккаунта? <a href="#">Создайте новый</a>!')
        register_label.setAlignment(QtCore.Qt.AlignCenter)
        register_label.setStyleSheet("font-size: 12px; color: #0078D7;")
        register_label.linkActivated.connect(lambda _: self.on_open_register())
        layout.addWidget(register_label)

    def create_input(self, placeholder, is_password=False):
        input_field = QtWidgets.QLineEdit()
        input_field.setPlaceholderText(placeholder)
        if is_password:
            input_field.setEchoMode(QtWidgets.QLineEdit.Password)
        input_field.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 2px solid #0078D7; }
        """)
        return input_field

    def button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-size: 16px;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
        """

    def darken_color(self, color):
        return "#005499" if color == "#0078D7" else "#1e7e34"

    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            RoundedDialog.warning("Ошибка", "Одно из полей данных вашего аккаунта пустует.\nПожалуйста, заполните все поля до конца!")
            return

        try:
            st = get_maintenance_status()
            if st.get("enabled"):
                msg = st.get("message") or "Ведутся технические работы. Доступ запрещён."
                RoundedDialog.warning("Технические работы", "Сообщение от сервера: " + msg + "\n\nСейчас в приложении ведутся технические работы. В этот момент просмотр контента приложения, его использование или любые другие действия в нём недоступны. Приносим свои извенения, за доставленные неудобства!")
                return
        except Exception:
            pass

        if authenticate_user(username, password):
            RoundedDialog.info("Успешно", "Вы успешно авторизовались в своём аккаунте!")
            self.on_success(username)
            self.close()
        else:
            RoundedDialog.warning("Ошибка", "К сожалению, введённые вами данные для авторизации неверны.\nПожалуйста перепроверьте логин и пароль!")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos') and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()
