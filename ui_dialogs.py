from PyQt5 import QtWidgets, QtCore, QtGui
from api_client import change_password

class RoundedDialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str, kind: str = "info"):
        parent = QtWidgets.QApplication.activeWindow()
        super().__init__(parent)
        self._parent_for_center = parent

        self._drag_pos = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        outer = QtWidgets.QFrame(self)
        outer.setObjectName("outer")
        outer.setStyleSheet("""
            QFrame#outer {
                background-color: #F0F0F0;  
                border-radius: 18px;
                border: 1px solid #D6D6D6;
            }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

        layout = QtWidgets.QVBoxLayout(outer)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QtWidgets.QWidget()
        header.setFixedHeight(42)
        header.mousePressEvent = self._header_mouse_press
        header.mouseMoveEvent = self._header_mouse_move
        header.mouseReleaseEvent = self._header_mouse_release

        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        icon = QtWidgets.QLabel()
        icon.setFixedSize(34, 34)
        icon.setAlignment(QtCore.Qt.AlignCenter)
        icon.mousePressEvent = self._header_mouse_press
        icon.mouseMoveEvent = self._header_mouse_move
        icon.mouseReleaseEvent = self._header_mouse_release

        if kind == "warning":
            icon.setStyleSheet(
                "background-color: #FF4444; border-radius: 17px;"
            )
            pixmap = QtGui.QPixmap("assets/icons/warning.png")
        else:
            icon.setStyleSheet(
                "background-color: #0078D7; border-radius: 17px;"
            )
            pixmap = QtGui.QPixmap("assets/icons/info.png")

        icon.setPixmap(
            pixmap.scaled(
                20, 20,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        )

        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #222;")
        title_lbl.mousePressEvent = self._header_mouse_press
        title_lbl.mouseMoveEvent = self._header_mouse_move
        title_lbl.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2f2f2;
                border: none;
                border-radius: 14px;
                color: #444;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #e8e8e8; }
        """)
        close_btn.clicked.connect(self.reject)

        header_layout.addWidget(icon)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        text_lbl = QtWidgets.QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("font-size: 13px; color: #444;")
        layout.addWidget(text_lbl)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        ok_btn = QtWidgets.QPushButton("ОК")
        ok_btn.setFixedSize(120, 36)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #005499; }
        """)
        ok_btn.clicked.connect(self.accept)

        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self.setFixedWidth(420)
        self.adjustSize()
        QtCore.QTimer.singleShot(0, self._center_on_parent)

    def _center_on_parent(self):
        parent = self._parent_for_center
        if parent is None:
            # fallback если вдруг нет окна
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            self.move(screen.center().x() - self.width() // 2,
                    screen.center().y() - self.height() // 2)
            return

        pg = parent.frameGeometry()
        self.move(
            pg.center().x() - self.width() // 2,
            pg.center().y() - self.height() // 2
        )

    def _header_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _header_mouse_move(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def _header_mouse_release(self, event):
        self._drag_pos = None

    @staticmethod
    def info(title: str, text: str):
        d = RoundedDialog(title, text, "info")
        d.exec_()

    @staticmethod
    def warning(title: str, text: str):
        d = RoundedDialog(title, text, "warning")
        d.exec_()

class ConfirmDialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str, confirm_text: str = "Да", cancel_text: str = "Отмена", danger: bool = False):
        parent = QtWidgets.QApplication.activeWindow()
        super().__init__(parent)
        self._parent_for_center = parent

        self._drag_pos = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        outer = QtWidgets.QFrame(self)
        outer.setObjectName("outer")
        outer.setStyleSheet("""
            QFrame#outer {
                background-color: #ffffff;
                border-radius: 18px;
            }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

        layout = QtWidgets.QVBoxLayout(outer)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QtWidgets.QWidget()
        header.setFixedHeight(42)
        header.mousePressEvent = self._header_mouse_press
        header.mouseMoveEvent = self._header_mouse_move
        header.mouseReleaseEvent = self._header_mouse_release

        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        icon = QtWidgets.QLabel()
        icon.setFixedSize(34, 34)
        icon.setAlignment(QtCore.Qt.AlignCenter)
        icon.mousePressEvent = self._header_mouse_press
        icon.mouseMoveEvent = self._header_mouse_move
        icon.mouseReleaseEvent = self._header_mouse_release

        if danger:
            icon.setStyleSheet("background-color: #FF4444; color: white; border-radius: 17px; font-weight: 900;")
            icon.setText("!")
        else:
            icon.setStyleSheet("background-color: #0078D7; color: white; border-radius: 17px; font-weight: 900;")
            icon.setText("?")

        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #222;")
        title_lbl.mousePressEvent = self._header_mouse_press
        title_lbl.mouseMoveEvent = self._header_mouse_move
        title_lbl.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2f2f2;
                border: none;
                border-radius: 14px;
                color: #444;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #e8e8e8; }
        """)
        close_btn.clicked.connect(self.reject)

        header_layout.addWidget(icon)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        text_lbl = QtWidgets.QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("font-size: 13px; color: #444;")
        layout.addWidget(text_lbl)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QtWidgets.QPushButton(cancel_text)
        cancel_btn.setFixedSize(140, 36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QtWidgets.QPushButton(confirm_text)
        confirm_btn.setFixedSize(140, 36)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#FF4444' if danger else '#0078D7'};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton:hover {{ background-color: {'#CC0000' if danger else '#005499'}; }}
        """)
        confirm_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        self.setFixedWidth(440)
        self.adjustSize()
        QtCore.QTimer.singleShot(0, self._center_on_parent)

    def _center_on_parent(self):
        parent = self._parent_for_center
        if parent is None:
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            self.move(screen.center().x() - self.width() // 2,
                      screen.center().y() - self.height() // 2)
            return

        pg = parent.frameGeometry()
        self.move(pg.center().x() - self.width() // 2,
                  pg.center().y() - self.height() // 2)

    def _header_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _header_mouse_move(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def _header_mouse_release(self, event):
        self._drag_pos = None

    @staticmethod
    def ask(title: str, text: str, confirm_text: str = "Да", cancel_text: str = "Отмена", danger: bool = False) -> bool:
        d = ConfirmDialog(title, text, confirm_text=confirm_text, cancel_text=cancel_text, danger=danger)
        return d.exec_() == QtWidgets.QDialog.Accepted

class DeleteAccountDialog(QtWidgets.QDialog):
    def __init__(self, parent, username: str):
        super().__init__(parent)

        self.username = username
        self._confirmed = False
        self._drag_pos = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setModal(True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(QtCore.Qt.AlignCenter)

        self.card = QtWidgets.QFrame()
        self.card.setFixedSize(560, 420)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 18px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self.card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QtWidgets.QWidget()
        header.setFixedHeight(42)
        header.setStyleSheet("background: transparent;")
        header.mousePressEvent = self._header_mouse_press
        header.mouseMoveEvent = self._header_mouse_move
        header.mouseReleaseEvent = self._header_mouse_release

        top = QtWidgets.QHBoxLayout(header)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        title = QtWidgets.QLabel("Удаление аккаунта")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #222;")
        title.mousePressEvent = self._header_mouse_press
        title.mouseMoveEvent = self._header_mouse_move
        title.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2f2f2;
                border: none;
                border-radius: 15px;
                color: #444;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #e8e8e8; }
        """)
        close_btn.clicked.connect(self.reject)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(close_btn)

        layout.addWidget(header)

        warn = QtWidgets.QLabel(
            "Внимание! Это действие необратимо.\n\n"
            "По удалению вашего аккаунта вместе с ним будут удалены:\n"
            "• данные и информация о вашем аккаунте\n"
            "• прогресс обучения и вся статистика\n"
            "В последствии восстановление аккаунта невозможно!\n"
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("font-size: 13px; color: #444;")
        layout.addWidget(warn)

        self.user_input = QtWidgets.QLineEdit()
        self.user_input.setPlaceholderText("Ваш логин")
        self.user_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #ddd;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
                color: #222;
            }
            QLineEdit:focus { border: 2px solid #0078D7; }
        """)
        layout.addWidget(self.user_input)

        self.phrase_input = QtWidgets.QLineEdit()
        self.phrase_input.setPlaceholderText("Введите: delete my account")
        self.phrase_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #ddd;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
                color: #222;
            }
            QLineEdit:focus { border: 2px solid #0078D7; }
        """)
        layout.addWidget(self.phrase_input)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(10)

        cancel = QtWidgets.QPushButton("Отмена")
        cancel.setFixedHeight(40)
        cancel.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #e9e9e9; }
        """)
        cancel.clicked.connect(self.reject)

        delete_btn = QtWidgets.QPushButton("Удалить аккаунт")
        delete_btn.setFixedHeight(40)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #CC0000; }
        """)
        delete_btn.clicked.connect(self._try_confirm)

        btns.addWidget(cancel)
        btns.addWidget(delete_btn)
        layout.addLayout(btns)

        root.addWidget(self.card)

    def _header_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.card.mapToGlobal(QtCore.QPoint(0, 0))

    def _header_mouse_move(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            new_top_left = event.globalPos() - self._drag_pos
            self.card.move(self.mapFromGlobal(new_top_left))

    def _header_mouse_release(self, event):
        self._drag_pos = None

    def _try_confirm(self):
        from ui_dialogs import RoundedDialog
        if self.user_input.text().strip() != self.username:
            RoundedDialog.warning("Ошибка", "Логин введён неверно.")
            return
        if self.phrase_input.text().strip() != "delete my account":
            RoundedDialog.warning("Ошибка", "Фраза подтверждения введена неверно.")
            return
        self._confirmed = True
        self.accept()

    @staticmethod
    def run(parent, username: str) -> bool:
        d = DeleteAccountDialog(parent, username)
        if parent is not None:
            d.setFixedSize(parent.size())
        return d.exec_() == QtWidgets.QDialog.Accepted and d._confirmed
    
class ChangePasswordDialog(QtWidgets.QDialog):
    def __init__(self, parent, username: str):
        super().__init__(parent)

        self.username = username
        self._drag_pos = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setModal(True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(QtCore.Qt.AlignCenter)

        self.card = QtWidgets.QFrame()
        self.card.setFixedSize(520, 360)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 18px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self.card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QtWidgets.QWidget()
        header.setFixedHeight(42)
        header.mousePressEvent = self._header_mouse_press
        header.mouseMoveEvent = self._header_mouse_move
        header.mouseReleaseEvent = self._header_mouse_release

        top = QtWidgets.QHBoxLayout(header)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        title = QtWidgets.QLabel("Смена пароля")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #222;")
        title.mousePressEvent = self._header_mouse_press
        title.mouseMoveEvent = self._header_mouse_move
        title.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2f2f2;
                border: none;
                border-radius: 15px;
                color: #444;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #e8e8e8; }
        """)
        close_btn.clicked.connect(self.reject)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(close_btn)

        layout.addWidget(header)

        hint = QtWidgets.QLabel("Введите текущий пароль и задайте новый.")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(hint)

        self.old_input = QtWidgets.QLineEdit()
        self.old_input.setPlaceholderText("Текущий пароль")
        self.old_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.old_input.setStyleSheet(self._input_style())
        layout.addWidget(self.old_input)

        self.new_input = QtWidgets.QLineEdit()
        self.new_input.setPlaceholderText("Новый пароль")
        self.new_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.new_input.setStyleSheet(self._input_style())
        layout.addWidget(self.new_input)

        self.repeat_input = QtWidgets.QLineEdit()
        self.repeat_input.setPlaceholderText("Повтор нового пароля")
        self.repeat_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.repeat_input.setStyleSheet(self._input_style())
        layout.addWidget(self.repeat_input)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(10)

        cancel = QtWidgets.QPushButton("Отмена")
        cancel.setFixedHeight(40)
        cancel.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #e9e9e9; }
        """)
        cancel.clicked.connect(self.reject)

        save_btn = QtWidgets.QPushButton("Сохранить")
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #005499; }
        """)
        save_btn.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

        root.addWidget(self.card)

        self.repeat_input.returnPressed.connect(self._save)

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #ddd;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
                color: #222;
            }
            QLineEdit:focus { border: 2px solid #0078D7; }
        """

    def _header_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.card.mapToGlobal(QtCore.QPoint(0, 0))

    def _header_mouse_move(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            new_top_left = event.globalPos() - self._drag_pos
            self.card.move(self.mapFromGlobal(new_top_left))

    def _header_mouse_release(self, event):
        self._drag_pos = None

    def _save(self):
        from ui_dialogs import RoundedDialog

        old_pw = self.old_input.text().strip()
        new_pw = self.new_input.text().strip()
        rep_pw = self.repeat_input.text().strip()

        if not old_pw or not new_pw or not rep_pw:
            RoundedDialog.warning("Ошибка", "Заполните все поля.")
            return

        if len(new_pw) < 4:
            RoundedDialog.warning("Ошибка", "Новый пароль слишком короткий (минимум 4 символа).")
            return

        if new_pw != rep_pw:
            RoundedDialog.warning("Ошибка", "Новый пароль и повтор не совпадают.")
            return

        if not change_password(self.username, old_pw, new_pw):
            RoundedDialog.warning("Ошибка", "Текущий пароль введён неверно (или вы не авторизованы).")
            return

        RoundedDialog.info("Готово", "Пароль успешно изменён.")
        self.accept()

    @staticmethod
    def run(parent, username: str) -> bool:
        d = ChangePasswordDialog(parent, username)
        if parent is not None:
            d.setFixedSize(parent.size())
        return d.exec_() == QtWidgets.QDialog.Accepted