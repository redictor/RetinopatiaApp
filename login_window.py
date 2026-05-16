from PyQt5 import QtWidgets, QtCore, QtGui
from api_client import authenticate_user
from api_client import get_maintenance_status
from ui_dialogs import RoundedDialog
import math

class LoginWorker(QtCore.QThread):
    done = QtCore.pyqtSignal(bool, str, str)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        try:
            st = get_maintenance_status()
            if st.get("enabled"):
                msg = st.get("message") or "Ведутся технические работы. Доступ запрещён."
                self.done.emit(False, "maintenance", msg)
                return
        except Exception:
            pass

        try:
            ok, error = authenticate_user(self.username, self.password)
            self.done.emit(bool(ok), "auth", error)
        except Exception as e:
            self.done.emit(False, "error", str(e))


class SpinnerButton(QtWidgets.QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self._loading = False
        self._success = False
        self._angle = 0
        self._error = False

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._rotate)

    def setLoading(self, loading: bool):
        self._loading = loading
        self._success = False
        self._error = False

        if loading:
            self.setText("Вход...")
            self.setEnabled(False)
            self._timer.start(16)
        else:
            self._timer.stop()
            self._angle = 0
            self.setText("Войти")
            self.setEnabled(True)

        self.update()
    
    def setError(self):
        self._timer.stop()
        self._loading = False
        self._success = False
        self._error = True
        self.setText("Войти")
        self.update()

    def setSuccess(self):
        self._timer.stop()
        self._loading = False
        self._success = True
        self.setText("Войти")
        self.update()

    def _rotate(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if not self._loading and not self._success and not self._error:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        text_width = self.fontMetrics().horizontalAdvance(self.text())
        cx = self.width() // 2 - text_width // 2 - 18
        cy = self.height() // 2

        if self._loading:
            rect = QtCore.QRectF(cx - 7, cy - 7, 14, 14)

            pen_bg = QtGui.QPen(QtGui.QColor(255, 255, 255, 70), 2.2)
            pen_bg.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen_bg)
            painter.drawArc(rect, 0, 360 * 16)

            pen_fg = QtGui.QPen(QtGui.QColor(255, 255, 255, 245), 2.2)
            pen_fg.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen_fg)

            start_angle = int(-self._angle * 16)
            span_angle = int(105 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        if self._success:
            pen = QtGui.QPen(
                QtGui.QColor(255, 255, 255),
                3,
                QtCore.Qt.SolidLine,
                QtCore.Qt.RoundCap,
                QtCore.Qt.RoundJoin
            )
            painter.setPen(pen)

            p1 = QtCore.QPoint(cx - 7, cy)
            p2 = QtCore.QPoint(cx - 2, cy + 6)
            p3 = QtCore.QPoint(cx + 9, cy - 7)

            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)

        if self._error:
            pen = QtGui.QPen(
                QtGui.QColor(255, 255, 255),
                3,
                QtCore.Qt.SolidLine,
                QtCore.Qt.RoundCap
            )
            painter.setPen(pen)

            painter.drawLine(cx - 7, cy - 7, cx + 7, cy + 7)
            painter.drawLine(cx + 7, cy - 7, cx - 7, cy + 7)

class LoginWindow(QtWidgets.QWidget):
    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.login_worker = None

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
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 35)

        top_bar = QtWidgets.QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background: transparent;")

        top_bar.mousePressEvent = self._top_mouse_press
        top_bar.mouseMoveEvent = self._top_mouse_move
        top_bar.mouseReleaseEvent = self._top_mouse_release

        top = QtWidgets.QHBoxLayout(top_bar)
        top.setContentsMargins(10, 0, 10, 0)
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
                logo_pixmap.scaled(
                    32, 32,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
            )
        else:
            logo_label.setText("◉")

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 18px;
                font-weight: bold;
            }
        """)

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(app_label)

        drag_area = QtWidgets.QWidget()
        drag_area.setStyleSheet("background: transparent;")
        drag_area.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        def window_button_style(kind):
            if kind == "close":
                border = "#ff9c9c"
                hover_bg = "#ffb1b1"
                hover_border = "#ff7d7d"
                icon_color = "#e42b2b"
            else:
                border = "#d2d9e7"
                hover_bg = "#dbe3f2"
                hover_border = "#b2c1d9"
                icon_color = "#5a667c"

            return f"""
            QPushButton {{
                background-color: white;
                border: 1px solid {border};
                border-radius: 8px;
                padding: 0px;
                color: {icon_color};
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                border: 1px solid {hover_border};
            }}
            QPushButton:pressed {{
                background-color: #e5e7eb;
            }}
            """
        
        def set_icon(button, path):
            icon = QtGui.QIcon(path)
            button.setIcon(icon)
            button.setIconSize(QtCore.QSize(16, 16))
            button.setText("")

        minimize_button = QtWidgets.QPushButton()
        minimize_button.setFixedSize(32, 32)
        minimize_button.setCursor(QtCore.Qt.PointingHandCursor)
        minimize_button.setStyleSheet(window_button_style("minimize"))
        set_icon(minimize_button, "assets/icons/minimize.svg")
        minimize_button.clicked.connect(self.showMinimized)

        close_button = QtWidgets.QPushButton()
        close_button.setFixedSize(32, 32)
        close_button.setCursor(QtCore.Qt.PointingHandCursor)
        close_button.setStyleSheet(window_button_style("close"))
        set_icon(close_button, "assets/icons/close.svg")
        close_button.clicked.connect(self.close)

        top.addWidget(brand)
        top.addStretch(1)
        top.addWidget(drag_area, 1)
        top.addWidget(minimize_button)
        top.addWidget(close_button)

        layout.addWidget(top_bar)

        title_label = QtWidgets.QLabel("Вход в аккаунт")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 25px; font-weight: bold; color: #333;")
        layout.addWidget(title_label)

        self.username_input = self.create_input("Логин")
        self.password_input = self.create_input("Пароль", True)

        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)

        self.login_button = SpinnerButton("Войти")
        self.login_button.setFixedHeight(40)
        self.login_button.setStyleSheet(self.button_style("#0078D7"))
        self.login_button.clicked.connect(self.login)
        layout.addWidget(self.login_button)

        spacer = QtWidgets.QLabel()
        spacer.setFixedHeight(20)
        layout.addWidget(spacer)

        wrapper.show()

    def set_loading(self, loading: bool):
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
        self.login_button.setLoading(loading)

    def _top_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def _top_mouse_move(self, event):
        if hasattr(self, "old_pos") and self.old_pos and event.buttons() & QtCore.Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()

    def _top_mouse_release(self, event):
        self.old_pos = None

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
            QLineEdit:disabled {
                background-color: #eeeeee;
                color: #888;
            }
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
            QPushButton:disabled {{
                background-color: {color};
                color: white;
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

        self.set_loading(True)

        self.login_worker = LoginWorker(username, password)
        self.login_worker.done.connect(lambda ok, mode, msg: self._login_finished(ok, mode, msg, username))
        self.login_worker.finished.connect(self.login_worker.deleteLater)
        self.login_worker.start()

    def _login_finished(self, ok: bool, mode: str, msg: str, username: str):
        if ok:
            self.username_input.setEnabled(False)
            self.password_input.setEnabled(False)
            self.login_button.setSuccess()

            QtCore.QTimer.singleShot(
                1000,
                lambda: self._finish_success_login(username)
            )
            return
        
        self.login_button.setError()

        def after_error():
            if mode == "maintenance":
                RoundedDialog.warning(
                    "Технические работы",
                    "Сообщение от сервера: " + msg +
                    "\n\nСейчас в приложении ведутся технические работы. "
                    "В этот момент просмотр контента приложения, его использование "
                    "или любые другие действия в нём недоступны."
                )
            if msg == "access_expired":
                RoundedDialog.warning(
                    "Лицензия более недействительна",
                    "Срок действия доступа к приложению истёк.\n"
                    "Чтобы продолжить использование приложения рекомендуется обратиться к администратору вашей организации!"
                )
            else:
                RoundedDialog.warning(
                    "Ошибка",
                    "К сожалению, введённые вами данные неверны.\nПроверьте логин и пароль."
                )

            self.set_loading(False)

        QtCore.QTimer.singleShot(900, after_error)

    def _finish_success_login(self, username: str):
        RoundedDialog.info("Успешно", "Вы успешно авторизовались в своём аккаунте!")
        self.on_success(username)
        self.close()

