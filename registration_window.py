# registration_window.py
from PyQt5 import QtWidgets, QtCore
from api_client import register_user, get_maintenance_status
from ui_dialogs import DeleteAccountDialog, RoundedDialog

class RegistrationWindow(QtWidgets.QWidget):
    def __init__(self, on_back):
        super().__init__()
        self.on_back = on_back

        self.setWindowTitle("Регистрация")
        self.setFixedSize(440, 390)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.init_ui()

    def init_ui(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setGeometry(0, 0, 440, 390)
        wrapper.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 20px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 18)

        window_buttons_layout = QtWidgets.QHBoxLayout()
        window_buttons_layout.setSpacing(8)
        window_buttons_layout.setContentsMargins(10, 0, 10, 0)

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("""
            QLabel {
                color: #222;
                font-size: 17px;
                font-weight: 600;
            }
        """)
        app_label.mousePressEvent = self.mousePressEvent
        app_label.mouseMoveEvent = self.mouseMoveEvent

        drag_area = QtWidgets.QWidget()
        drag_area.setFixedHeight(40)
        drag_area.setStyleSheet("background-color: transparent;")
        drag_area.mousePressEvent = self.mousePressEvent
        drag_area.mouseMoveEvent = self.mouseMoveEvent

        minimize_button = QtWidgets.QPushButton("─")
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

        title = QtWidgets.QLabel("Регистрация")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        self.username_input = self.create_input("Логин")
        self.password_input = self.create_input("Пароль", True)
        self.password_repeat_input = self.create_input("Повтор пароля", True)

        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.password_repeat_input)

        register_button = QtWidgets.QPushButton("Зарегистрироваться")
        register_button.setFixedHeight(40)
        register_button.setStyleSheet(self.button_style("#0078D7"))
        register_button.clicked.connect(self.handle_registration)
        layout.addWidget(register_button)

        switch_to_login_label = QtWidgets.QLabel('Есть аккаунт? <a href="#">Войдите</a>!')
        switch_to_login_label.setAlignment(QtCore.Qt.AlignCenter)
        switch_to_login_label.setStyleSheet("font-size: 12px; color: #0078D7;")
        switch_to_login_label.linkActivated.connect(lambda _: self.handle_back())
        layout.addWidget(switch_to_login_label)

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
        if color == "#0078D7":
            return "#005499"
        return color

    def handle_registration(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        password_repeat = self.password_repeat_input.text().strip()

        if not username or not password or not password_repeat:
            RoundedDialog.warning("Ошибка", "Одно из полей данных вашего будущего аккаунта пустует.\nПожалуйста, заполните все поля до конца!")
            return
        
        try:
            st = get_maintenance_status()
            if st.get("enabled"):
                msg = st.get("message") or "Ведутся технические работы. Регистрация временно недоступна."
                RoundedDialog.warning("Технические работы", "Сообщение от сервера: " + msg + "\n\nСейчас в приложении ведутся технические работы. В этот момент просмотр контента приложения, его использование или любые другие действия в нём недоступны. Приносим свои извенения, за доставленные неудобства!")
                return
        except Exception:
            pass

        if password != password_repeat:
            RoundedDialog.warning("Ошибка", "Введённые вами пароли не совпадают.\nПожалуйста, исправьте ваши пароли!")
            return

        if register_user(username, password):
            RoundedDialog.info("Успех", "Вы успешно зарегистрировались!")
            self.handle_back()
        else:
            RoundedDialog.warning(
                "Логин занят",
                "Этот логин уже используется.\nПожалуйста, выберите другой."
            )

    def handle_back(self):
        self.on_back()
        self.close()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos') and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()
