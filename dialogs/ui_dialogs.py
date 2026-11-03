import os
from PyQt5 import QtWidgets, QtCore, QtGui
from api_client import change_password
from ui_styles import window_button_style, set_icon
import app_logger
import i18n

_log = app_logger.get("dialogs")

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

        close_btn = QtWidgets.QPushButton()
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet(window_button_style("close"))
        set_icon(close_btn, "assets/icons/close.svg")
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

        ok_btn = QtWidgets.QPushButton(i18n.t("dialogs.ok"))
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

        self.setFixedWidth(500)
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
    def __init__(
        self,
        title: str,
        text: str,
        confirm_text: str = "Да",
        cancel_text: str = "Отмена",
        danger: bool = False,
        button_width: int = 140
    ):
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

        if danger:
            icon.setStyleSheet(
                "background-color: #FF4444; border-radius: 17px;"
            )
            pm = QtGui.QPixmap("assets/icons/warning.png")
        else:
            icon.setStyleSheet(
                "background-color: #0078D7; border-radius: 17px;"
            )
            pm = QtGui.QPixmap("assets/icons/info.png")
        
        icon.setPixmap(pm.scaled(20, 20, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #222;")
        title_lbl.mousePressEvent = self._header_mouse_press
        title_lbl.mouseMoveEvent = self._header_mouse_move
        title_lbl.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton()
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet(window_button_style("close"))
        set_icon(close_btn, "assets/icons/close.svg")
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
        cancel_btn.setFixedSize(button_width, 36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: 1px solid #D6D6D6;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QtWidgets.QPushButton(confirm_text)
        confirm_btn.setFixedSize(button_width, 36)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#FF4444' if danger else '#0078D7'};
                color: white;
                border: 1px solid #D6D6D6;
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

        self.setFixedWidth(520)
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
    def ask(
        title,
        text,
        confirm_text="Да",
        cancel_text="Отмена",
        danger=False,
        button_width=140
    ):
        d = ConfirmDialog(
            title,
            text,
            confirm_text,
            cancel_text,
            danger,
            button_width=button_width
        )
        return d.exec_() == QtWidgets.QDialog.Accepted

class DeleteAccountDialog(QtWidgets.QDialog):
    def __init__(self, parent, username: str):
        super().__init__(parent)

        self.username = username
        self._confirmed = False
        self._drag_pos = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setModal(False)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(QtCore.Qt.AlignCenter)

        self.card = QtWidgets.QFrame()
        self.card.setFixedSize(660, 500)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #F0F0F0;  
                border-radius: 18px;
                border: 1px solid #D6D6D6;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self.card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QtWidgets.QWidget()
        header.setFixedHeight(42)
        header.setStyleSheet("background: transparent;")
        header.mousePressEvent = self._header_mouse_press
        header.mouseMoveEvent = self._header_mouse_move
        header.mouseReleaseEvent = self._header_mouse_release

        top = QtWidgets.QHBoxLayout(header)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        icon = QtWidgets.QLabel()
        icon.setFixedSize(34, 34)
        icon.setAlignment(QtCore.Qt.AlignCenter)
        icon.setStyleSheet(
            "background-color: #FF4444; border-radius: 17px;"
        )

        pixmap = QtGui.QPixmap("assets/icons/delete-account.png")
        icon.setPixmap(
            pixmap.scaled(
                20, 20,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        )

        icon.mousePressEvent = self._header_mouse_press
        icon.mouseMoveEvent = self._header_mouse_move
        icon.mouseReleaseEvent = self._header_mouse_release

        top.addWidget(icon)

        title = QtWidgets.QLabel(i18n.t("delete_account.title"))
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #222; border: none;")
        title.mousePressEvent = self._header_mouse_press
        title.mouseMoveEvent = self._header_mouse_move
        title.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton()
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet(window_button_style("close"))
        set_icon(close_btn, "assets/icons/close.svg")
        close_btn.clicked.connect(self.reject)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(close_btn)

        layout.addWidget(header)

        warn = QtWidgets.QLabel(i18n.t("delete_account.warning"))
        warn.setWordWrap(True)
        warn.setStyleSheet("font-size: 13px; color: #444; border: none;")
        layout.addWidget(warn)

        self.user_input = QtWidgets.QLineEdit()
        self.user_input.setPlaceholderText(i18n.t("delete_account.username"))
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
        self.phrase_input.setPlaceholderText(i18n.t("delete_account.phrase"))
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

        cancel = QtWidgets.QPushButton(i18n.t("dialogs.cancel"))
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

        delete_btn = QtWidgets.QPushButton(i18n.t("delete_account.delete_button"))
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
        from dialogs.ui_dialogs import RoundedDialog
        if self.user_input.text().strip() != self.username:
            RoundedDialog.warning(i18n.t("dialogs.error"), i18n.t("delete_account.bad_username"))
            return
        if self.phrase_input.text().strip() != "delete my account":
            RoundedDialog.warning(i18n.t("dialogs.error"), i18n.t("delete_account.bad_phrase"))
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
        self._change_worker = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setModal(False)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(QtCore.Qt.AlignCenter)

        self.card = QtWidgets.QFrame()
        self.card.setFixedWidth(540)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #F0F0F0;  
                border-radius: 18px;
                border: 1px solid #D6D6D6;
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

        icon = QtWidgets.QLabel()
        icon.setFixedSize(34, 34)
        icon.setAlignment(QtCore.Qt.AlignCenter)
        icon.setStyleSheet(
            "background-color: #0078D7; border-radius: 17px;"
        )

        pixmap = QtGui.QPixmap("assets/icons/reset-password.png")
        icon.setPixmap(
            pixmap.scaled(
                20, 20,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        )

        icon.mousePressEvent = self._header_mouse_press
        icon.mouseMoveEvent = self._header_mouse_move
        icon.mouseReleaseEvent = self._header_mouse_release

        top.addWidget(icon)

        title = QtWidgets.QLabel(i18n.t("password.title"))
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #222; border: none;")
        title.mousePressEvent = self._header_mouse_press
        title.mouseMoveEvent = self._header_mouse_move
        title.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton()
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet(window_button_style("close"))
        set_icon(close_btn, "assets/icons/close.svg")
        close_btn.clicked.connect(self.reject)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(close_btn)

        layout.addWidget(header)

        hint = QtWidgets.QLabel(i18n.t("password.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #666; border: none; margin-bottom: -4px;")
        layout.addWidget(hint)
        layout.addSpacing(2)

        self.old_input = QtWidgets.QLineEdit()
        self.old_input.setPlaceholderText(i18n.t("password.current"))
        self.old_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.old_input.setStyleSheet(self._input_style())
        layout.addWidget(self.old_input)

        self.new_input = QtWidgets.QLineEdit()
        self.new_input.setPlaceholderText(i18n.t("password.new"))
        self.new_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.new_input.setStyleSheet(self._input_style())
        layout.addWidget(self.new_input)

        self.repeat_input = QtWidgets.QLineEdit()
        self.repeat_input.setPlaceholderText(i18n.t("password.repeat"))
        self.repeat_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.repeat_input.setStyleSheet(self._input_style())
        layout.addWidget(self.repeat_input)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(10)

        self._cancel_btn = QtWidgets.QPushButton(i18n.t("dialogs.cancel"))
        self._cancel_btn.setFixedHeight(40)
        self._cancel_btn.setStyleSheet("""
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
        self._cancel_btn.clicked.connect(self.reject)

        self._save_btn = QtWidgets.QPushButton(i18n.t("password.save"))
        self._save_btn.setFixedHeight(40)
        self._save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #005499; }
            QPushButton:disabled { background-color: #b9c6d3; }
        """)
        self._save_btn.clicked.connect(self._save)

        btns.addWidget(self._cancel_btn)
        btns.addWidget(self._save_btn)
        layout.addLayout(btns)

        root.addWidget(self.card)
        self.card.adjustSize()

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

    def _set_loading(self, loading: bool):
        self.old_input.setEnabled(not loading)
        self.new_input.setEnabled(not loading)
        self.repeat_input.setEnabled(not loading)
        self._save_btn.setEnabled(not loading)
        self._cancel_btn.setEnabled(not loading)
        self._save_btn.setText(
            i18n.t("password.saving")
            if loading
            else i18n.t("password.save")
        )

    def _save(self):
        old_pw = self.old_input.text().strip()
        new_pw = self.new_input.text().strip()
        rep_pw = self.repeat_input.text().strip()

        if not old_pw or not new_pw or not rep_pw:
            RoundedDialog.warning(
                i18n.t("dialogs.error"),
                i18n.t("password.fill_all")
            )
            return

        if len(new_pw) < 4:
            RoundedDialog.warning(
                i18n.t("dialogs.error"),
                i18n.t("password.too_short")
            )
            return

        if new_pw != rep_pw:
            RoundedDialog.warning(
                i18n.t("dialogs.error"),
                i18n.t("password.mismatch")
            )
            return

        self._set_loading(True)

        import functools
        fn = functools.partial(change_password, self.username, old_pw, new_pw)
        self._change_worker = ApiWorker(fn)
        self._change_worker.ok.connect(self._on_change_ok)
        self._change_worker.fail.connect(self._on_change_fail)
        self._change_worker.finished.connect(self._change_worker.deleteLater)
        self._change_worker.start()

    def _on_change_ok(self, result: bool):
        self._set_loading(False)
        if result:
            RoundedDialog.info(
                i18n.t("dialogs.done"),
                i18n.t("password.success")
            )
            self.accept()
        else:
            RoundedDialog.warning(
                i18n.t("dialogs.error"),
                i18n.t("password.wrong_current")
            )

    def _on_change_fail(self, err: str):
        self._set_loading(False)
        RoundedDialog.warning(
            i18n.t("dialogs.error"),
            i18n.t("password.server_error")
        )

    @staticmethod
    def run(parent, username: str) -> bool:
        d = ChangePasswordDialog(parent, username)
        if parent is not None:
            d.setFixedSize(parent.size())
        return d.exec_() == QtWidgets.QDialog.Accepted
    
class ApiWorker(QtCore.QThread):
    ok = QtCore.pyqtSignal(object)
    fail = QtCore.pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        fn_name = getattr(self._fn, "__name__", repr(self._fn))
        try:
            res = self._fn(*self._args, **self._kwargs)
            self.ok.emit(res)
        except Exception as e:
            _log.debug("ApiWorker ошибка [%s]: %s", fn_name, e, exc_info=True)
            self.fail.emit(str(e))

class DevPanelDialog(QtWidgets.QDialog):
    def __init__(self, parent, username: str, debug_data: dict, on_logout=None):
        super().__init__(parent)
        self._on_logout = on_logout
        self._username = username

        self.setWindowTitle("Панель разработчика")
        self.resize(760, 640)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        info_lbl = QtWidgets.QLabel(f"Пользователь: {username}")
        layout.addWidget(info_lbl)

        debug_title = QtWidgets.QLabel("Данные последнего инференса")
        debug_title_font = debug_title.font()
        debug_title_font.setBold(True)
        debug_title.setFont(debug_title_font)
        layout.addWidget(debug_title)

        self._debug_output = QtWidgets.QLabel("")
        self._debug_output.setWordWrap(True)
        self._debug_output.setStyleSheet("font-family: Consolas, monospace;")
        layout.addWidget(self._debug_output)
        self._set_debug_text(debug_data)

        logs_title = QtWidgets.QLabel("Последние строки лога")
        logs_title_font = logs_title.font()
        logs_title_font.setBold(True)
        logs_title.setFont(logs_title_font)
        layout.addWidget(logs_title)

        self._logs_view = QtWidgets.QPlainTextEdit()
        self._logs_view.setReadOnly(True)
        self._logs_view.setPlainText(self._read_last_log_lines())
        self._logs_view.setStyleSheet("font-family: Consolas, monospace; font-size: 10px;")
        layout.addWidget(self._logs_view, 1)
        scrollbar = self._logs_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        btn_reset_session = QtWidgets.QPushButton("Сбросить сохранённую сессию")
        btn_reset_session.clicked.connect(self._reset_session)
        layout.addWidget(btn_reset_session)

    def _read_last_log_lines(self) -> str:
        try:
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "logs"
            )
            if not os.path.isdir(logs_dir):
                return "Папка logs не найдена."
            files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
            if not files:
                return "Файлы логов не найдены."
            files.sort()
            latest = os.path.join(logs_dir, files[-1])
            with open(latest, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            return "".join(lines[-60:])
        except Exception:
            return "Не удалось прочитать логи."

    def _set_debug_text(self, debug_data: dict):
        if debug_data:
            debug_text = "\n".join(f"{k}: {v}" for k, v in debug_data.items())
        else:
            debug_text = "Пока нет данных. Пройдите тренировку с проверкой ИИ."
        self._debug_output.setText(debug_text)

    def refresh(self, debug_data: dict):
        self._set_debug_text(debug_data)
        self._logs_view.setPlainText(self._read_last_log_lines())
        scrollbar = self._logs_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _reset_session(self):
        try:
            from api_client import logout
            logout()
        except Exception:
            pass
        self.hide()
        if self._on_logout:
            self._on_logout()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

class SecretKeyDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self._parent_for_center = parent.window() if parent is not None else None
        self._drag_pos = None
        self._confirmed_word = None

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
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

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
        icon.setStyleSheet("background-color: #222222; border-radius: 17px;")
        icon.setText("🔒")
        icon.mousePressEvent = self._header_mouse_press
        icon.mouseMoveEvent = self._header_mouse_move
        icon.mouseReleaseEvent = self._header_mouse_release

        title_lbl = QtWidgets.QLabel("Введите секретный ключ")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #222; border:none; background:transparent;")
        title_lbl.mousePressEvent = self._header_mouse_press
        title_lbl.mouseMoveEvent = self._header_mouse_move
        title_lbl.mouseReleaseEvent = self._header_mouse_release

        close_btn = QtWidgets.QPushButton()
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet(window_button_style("close"))
        set_icon(close_btn, "assets/icons/close.svg")
        close_btn.clicked.connect(self.reject)

        header_layout.addWidget(icon)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch(1)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        hint = QtWidgets.QLabel("Доступ к скрытым инструментам разработчика.")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #666; border:none; background:transparent;")
        layout.addWidget(hint)

        self.key_input = QtWidgets.QLineEdit()
        self.key_input.setPlaceholderText("Секретный ключ")
        self.key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key_input.setStyleSheet("""
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
        self.key_input.returnPressed.connect(self._try_confirm)
        layout.addWidget(self.key_input)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QtWidgets.QPushButton("Отмена")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3; color: #222; border: none;
                border-radius: 10px; font-size: 14px; font-weight: 700;
            }
            QPushButton:hover { background-color: #e9e9e9; }
        """)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QtWidgets.QPushButton("Подтвердить")
        confirm_btn.setFixedHeight(40)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7; color: white; border: none;
                border-radius: 10px; font-size: 14px; font-weight: 800;
            }
            QPushButton:hover { background-color: #005499; }
        """)
        confirm_btn.clicked.connect(self._try_confirm)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        self.setFixedWidth(420)
        self.adjustSize()
        QtCore.QTimer.singleShot(0, self._center_on_parent)
        QtCore.QTimer.singleShot(0, self.key_input.setFocus)

    def _try_confirm(self):
        self._confirmed_word = self.key_input.text().strip()
        self.accept()

    def _header_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _header_mouse_move(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def _header_mouse_release(self, event):
        self._drag_pos = None

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

    @staticmethod
    def ask_word(parent) -> str:
        d = SecretKeyDialog(parent)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            return d._confirmed_word or ""
        return ""