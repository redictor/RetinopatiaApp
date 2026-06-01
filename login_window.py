from PyQt5 import QtWidgets, QtCore, QtGui
from api_client import authenticate_user
from api_client import get_maintenance_status
from ui_dialogs import RoundedDialog
import app_logger
import math

_log = app_logger.get("login")


class LoginWorker(QtCore.QThread):
    done = QtCore.pyqtSignal(bool, str, str)

    def __init__(self, username, password, remember):
        super().__init__()
        self.username = username
        self.password = password
        self.remember = remember

    def run(self):
        try:
            st = get_maintenance_status()
            if st.get("enabled"):
                msg = st.get("message") or "Ведутся технические работы. Доступ запрещён."
                _log.warning("Техработы на сервере при попытке входа: %s", msg)
                self.done.emit(False, "maintenance", msg)
                return
        except Exception:
            _log.debug("Не удалось проверить статус техработ при входе", exc_info=True)

        try:
            _log.debug("Попытка авторизации: %s", self.username)
            ok, error = authenticate_user(self.username, self.password, self.remember)
            if ok:
                _log.info("Успешная авторизация: %s", self.username)
            else:
                _log.warning("Ошибка авторизации: %s, причина=%s", self.username, error)
            self.done.emit(bool(ok), "auth", error)
        except Exception as e:
            _log.error("Необработанная ошибка при авторизации: %s", self.username, exc_info=True)
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


class IconLineEdit(QtWidgets.QWidget):
    """Input field with a left icon, label above, and optional right toggle button."""

    def __init__(self, label_text, placeholder, icon_path=None,
                 is_password=False, parent=None):
        super().__init__(parent)
        self.is_password = is_password

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        label = QtWidgets.QLabel(label_text)
        label.setStyleSheet("font-size: 13px; color: #444; font-weight: 500;")
        outer.addWidget(label)

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.field_container = QtWidgets.QWidget()
        self.field_container.setObjectName("fieldContainer")
        self.field_container.setStyleSheet("""
            QWidget#fieldContainer {
                background: white;
                border: 1.5px solid #dde3ec;
                border-radius: 9px;
            }
        """)

        container_row = QtWidgets.QHBoxLayout(self.field_container)
        container_row.setContentsMargins(12, 0, 12, 0)
        container_row.setSpacing(6)

        if icon_path:
            icon_label = QtWidgets.QLabel()
            icon_label.setFixedSize(18, 18)
            icon_label.setAlignment(QtCore.Qt.AlignCenter)
            pix = QtGui.QPixmap(icon_path)
            if not pix.isNull():
                icon_label.setPixmap(
                    pix.scaled(16, 16, QtCore.Qt.KeepAspectRatio,
                               QtCore.Qt.SmoothTransformation)
                )
            else:
                icon_label.setText("●")
                icon_label.setStyleSheet("color: #aaa; font-size: 10px;")
            container_row.addWidget(icon_label)

        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setFrame(False)
        self.input.setFixedHeight(44)
        if is_password:
            self.input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 14px;
                color: #222;
            }
        """)
        container_row.addWidget(self.input, 1)

        if is_password:
            self.eye_button = QtWidgets.QPushButton()
            self.eye_button.setFixedSize(24, 24)
            self.eye_button.setCursor(QtCore.Qt.PointingHandCursor)
            self.eye_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                }
            """)
            self._eye_icon_show = QtGui.QIcon("assets/icons/show-eye.svg")
            self._eye_icon_hide = QtGui.QIcon("assets/icons/hide-eye.svg")
            self.eye_button.setIcon(self._eye_icon_show)
            self.eye_button.setIconSize(QtCore.QSize(18, 18))
            self.eye_button.setCheckable(True)
            self.eye_button.toggled.connect(self._toggle_visibility)
            container_row.addWidget(self.eye_button)

        row.addWidget(self.field_container)
        outer.addLayout(row)

        self.input.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.input:
            if event.type() == QtCore.QEvent.FocusIn:
                self.field_container.setStyleSheet("""
                    QWidget#fieldContainer {
                        background: white;
                        border: 1.5px solid #0078D7;
                        border-radius: 9px;
                    }
                """)
            elif event.type() == QtCore.QEvent.FocusOut:
                self.field_container.setStyleSheet("""
                    QWidget#fieldContainer {
                        background: white;
                        border: 1.5px solid #dde3ec;
                        border-radius: 9px;
                    }
                """)
        return super().eventFilter(obj, event)

    def _toggle_visibility(self, checked):
        if checked:
            self.input.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.eye_button.setIcon(self._eye_icon_hide)
        else:
            self.input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.eye_button.setIcon(self._eye_icon_show)

    def text(self):
        return self.input.text()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.input.setEnabled(enabled)
        bg = "white" if enabled else "#f0f0f0"
        self.field_container.setStyleSheet(f"""
            QWidget#fieldContainer {{
                background: {bg};
                border: 1.5px solid #dde3ec;
                border-radius: 9px;
            }}
        """)


class LoginWindow(QtWidgets.QWidget):
    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.login_worker = None

        self.setWindowTitle("Авторизация")
        self.setFixedSize(460, 420)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.initUI()

    def initUI(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setObjectName("wrapper")
        wrapper.setGeometry(0, 0, 460, 420)
        wrapper.setStyleSheet("""
            #wrapper {
                background-color: #f7f9fc;
                border: 1.2px solid #c7d2e0;
                border-radius: 20px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 10, 16, 20)

        top_bar = QtWidgets.QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background: transparent;")
        top_bar.mousePressEvent = self._top_mouse_press
        top_bar.mouseMoveEvent = self._top_mouse_move
        top_bar.mouseReleaseEvent = self._top_mouse_release

        top = QtWidgets.QHBoxLayout(top_bar)
        top.setContentsMargins(6, 0, 6, 0)
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
                logo_pixmap.scaled(32, 32, QtCore.Qt.KeepAspectRatio,
                                   QtCore.Qt.SmoothTransformation)
            )
        else:
            logo_label.setText("◉")

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("""
            QLabel { color: #333; font-size: 18px; font-weight: bold; }
        """)

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(app_label)

        def window_button_style(kind):
            if kind == "close":
                border, hover_bg, hover_border, icon_color = \
                    "#ff9c9c", "#ffb1b1", "#ff7d7d", "#e42b2b"
            else:
                border, hover_bg, hover_border, icon_color = \
                    "#d2d9e7", "#dbe3f2", "#b2c1d9", "#5a667c"
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
            QPushButton:pressed {{ background-color: #e5e7eb; }}
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
        top.addWidget(minimize_button)
        top.addWidget(close_button)

        layout.addWidget(top_bar)

        layout.addStretch(1)

        title_label = QtWidgets.QLabel("Вход в аккаунт")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #1a1a2e;"
        )
        layout.addWidget(title_label)

        layout.addSpacing(14)

        form_widget = QtWidgets.QWidget()
        form_widget.setStyleSheet("background: transparent;")
        form_layout = QtWidgets.QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        self.username_input = IconLineEdit(
            "Логин",
            "Например, ivan_ivanov",
            icon_path="assets/icons/user.svg",
        )
        self.password_input = IconLineEdit(
            "Пароль",
            "Введите пароль",
            icon_path="assets/icons/lock.svg",
            is_password=True,
        )

        form_layout.addWidget(self.username_input)
        form_layout.addWidget(self.password_input)

        extras_row = QtWidgets.QHBoxLayout()
        extras_row.setContentsMargins(0, 0, 0, 0)

        self.remember_checkbox = QtWidgets.QCheckBox("Запомнить меня")
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                color: #444;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1.5px solid #0078D7;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #0078D7;
                border: 1.5px solid #0078D7;
                image: url(assets/icons/checkmark.svg);
            }
        """)
        self.remember_checkbox.setChecked(True)

        extras_row.addWidget(self.remember_checkbox)

        form_layout.addLayout(extras_row)

        self.login_button = SpinnerButton("Войти")
        self.login_button.setFixedHeight(44)
        self.login_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.login_button.setStyleSheet(self.button_style("#0078D7"))
        self.login_button.clicked.connect(self.login)
        form_layout.addWidget(self.login_button)

        layout.addWidget(form_widget)

        layout.addStretch(1)

        wrapper.show()

    def set_loading(self, loading: bool):
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
        self.login_button.setLoading(loading)

    def _top_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def _top_mouse_move(self, event):
        if hasattr(self, "old_pos") and self.old_pos \
                and event.buttons() & QtCore.Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()

    def _top_mouse_release(self, event):
        self.old_pos = None

    def button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-size: 15px;
                font-weight: 600;
                border-radius: 9px;
                letter-spacing: 0.5px;
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
        remember = self.remember_checkbox.isChecked()

        if not username or not password:
            RoundedDialog.warning(
                "Ошибка",
                "Одно из полей данных вашего аккаунта пустует.\n"
                "Пожалуйста, заполните все поля до конца!"
            )
            return

        self.set_loading(True)

        self.login_worker = LoginWorker(username, password, remember)
        self.login_worker.done.connect(
            lambda ok, mode, msg: self._login_finished(ok, mode, msg, username)
        )
        self.login_worker.finished.connect(self.login_worker.deleteLater)
        self.login_worker.start()

    def _login_finished(self, ok: bool, mode: str, msg: str, username: str):
        if ok:
            self.username_input.setEnabled(False)
            self.password_input.setEnabled(False)
            self.login_button.setSuccess()
            QtCore.QTimer.singleShot(
                1000, lambda: self._finish_success_login(username)
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
            elif msg == "access_expired":
                RoundedDialog.warning(
                    "Лицензия более недействительна",
                    "Срок действия доступа к приложению истёк.\n"
                    "Чтобы продолжить использование приложения рекомендуется "
                    "обратиться к администратору вашей организации!"
                )
            else:
                RoundedDialog.warning(
                    "Ошибка",
                    "К сожалению, введённые вами данные неверны.\n"
                    "Проверьте логин и пароль."
                )
            self.set_loading(False)

        QtCore.QTimer.singleShot(900, after_error)

    def _finish_success_login(self, username: str):
        RoundedDialog.info("Успешно", "Вы успешно авторизовались в своём аккаунте!")
        self.on_success(username)
        self.close()