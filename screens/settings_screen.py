import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal
from api_client import reset_training_history, logout
from ui_dialogs import RoundedDialog, ConfirmDialog, ChangePasswordDialog, ApiWorker
import app_logger
from main import current_v

_log = app_logger.get("screens.settings")


class SettingsScreen(QtWidgets.QWidget):
    logout_requested = pyqtSignal()
    stats_reset = pyqtSignal()

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self._account_status = {"is_verified": False, "created_at": None}
        self._reset_worker = None
        self._build()

    def _build(self):
        self.setStyleSheet("background: transparent;")
        l = QtWidgets.QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)

        title = QtWidgets.QLabel("Настройки")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #222;")
        l.addWidget(title)

        profile = QtWidgets.QFrame()
        profile.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #e8e8e8; border-radius: 18px; }
            QLabel { border: none; background: transparent; }
        """)

        pl = QtWidgets.QHBoxLayout(profile)
        pl.setContentsMargins(18, 16, 18, 16)
        pl.setSpacing(14)

        avatar = QtWidgets.QLabel()
        avatar.setFixedSize(64, 64)
        avatar.setAlignment(QtCore.Qt.AlignCenter)
        pix = QtGui.QPixmap("assets/icons/avatar.png")
        if not pix.isNull():
            pix = pix.scaled(avatar.size(), QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
            avatar.setPixmap(pix)
        else:
            avatar.setText("👤")
            avatar.setStyleSheet("QLabel { background-color: #f1f5f9; border-radius: 32px; font-size: 30px; }")
        pl.addWidget(avatar)

        info_col = QtWidgets.QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(5)

        self.settings_header_name_lbl = QtWidgets.QLabel(self.username)
        self.settings_header_name_lbl.setStyleSheet("font-size:22px;font-weight:900;color:#111827;")
        info_col.addWidget(self.settings_header_name_lbl)

        self.settings_header_login_lbl = QtWidgets.QLabel(f"@{self.username}")
        self.settings_header_login_lbl.setStyleSheet("font-size:13px;font-weight:700;color:#6b7280;")
        info_col.addWidget(self.settings_header_login_lbl)

        verified_row = QtWidgets.QHBoxLayout()
        verified_row.setSpacing(6)
        verified_row.setContentsMargins(0, 4, 0, 0)

        check = QtWidgets.QLabel("✓")
        check.setFixedSize(18, 18)
        check.setAlignment(QtCore.Qt.AlignCenter)
        check.setStyleSheet("""
            QLabel { background-color: #22c55e; color: white; border-radius: 9px; font-size: 12px; font-weight: 800; }
        """)

        verified_text = QtWidgets.QLabel("Аккаунт верифицирован")
        verified_text.setStyleSheet("font-size: 13px; color: #16a34a; font-weight: 700;")

        self.settings_verify_icon = check
        self.settings_verified_text = verified_text

        verified_row.addWidget(check)
        verified_row.addWidget(verified_text)
        verified_row.addStretch(1)

        info_col.addLayout(verified_row)
        pl.addLayout(info_col, 1)
        l.addWidget(profile)

        org_box = QtWidgets.QFrame()
        org_box.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 18px; }
            QLabel { border: none; background: transparent; }
        """)

        org_layout = QtWidgets.QVBoxLayout(org_box)
        org_layout.setContentsMargins(20, 18, 20, 18)
        org_layout.setSpacing(14)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)

        org_title = QtWidgets.QLabel("Организация")
        org_title.setStyleSheet("font-size:16px;font-weight:900;color:#111827;")

        self.settings_license_badge = QtWidgets.QLabel("Учебная лицензия")
        self.settings_license_badge.setStyleSheet("""
            QLabel {
                background-color: #e0f2fe; color: #0369a1;
                border-radius: 10px; padding: 4px 10px;
                font-size: 11px; font-weight: 900;
            }
        """)

        title_row.addWidget(org_title)
        title_row.addStretch(1)
        title_row.addWidget(self.settings_license_badge)
        org_layout.addLayout(title_row)

        def org_item(title, value):
            wrapper = QtWidgets.QWidget()
            wrapper.setStyleSheet("background: transparent; border: none;")
            item_layout = QtWidgets.QVBoxLayout(wrapper)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(3)

            title_lbl = QtWidgets.QLabel(title)
            title_lbl.setStyleSheet("font-size:11px;color:#6b7280;font-weight:800;")

            value_lbl = QtWidgets.QLabel(value)
            value_lbl.setWordWrap(True)
            value_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            value_lbl.setStyleSheet("font-size:14px;color:#111827;font-weight:900;")

            item_layout.addWidget(title_lbl)
            item_layout.addWidget(value_lbl)
            return wrapper, value_lbl

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(46)
        grid.setVerticalSpacing(16)

        org_name_widget, self.settings_org_lbl = org_item("Название", "Не назначена")
        course_widget, self.settings_course_lbl = org_item("Курс и Группа", "Не указано")
        access_widget, self.settings_access_lbl = org_item("Доступ до", "Не указано")
        support_widget, self.settings_support_lbl = org_item("Поддержка", "Не указано")

        grid.addWidget(org_name_widget, 0, 0)
        grid.addWidget(course_widget, 0, 1)
        grid.addWidget(access_widget, 1, 0)
        grid.addWidget(support_widget, 1, 1)

        org_layout.addLayout(grid)
        l.addWidget(org_box)

        change_pwd_btn = QtWidgets.QPushButton("Сменить пароль")
        change_pwd_btn.setFixedHeight(38)
        change_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3; color: #222; border: none;
                border-radius: 10px; font-size: 13px; font-weight: 700; padding: 0 14px;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        change_pwd_btn.clicked.connect(self._change_password)
        l.addWidget(change_pwd_btn, alignment=QtCore.Qt.AlignLeft)

        logout_btn = QtWidgets.QPushButton("Выйти из аккаунта")
        logout_btn.setFixedHeight(38)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3; color: #222; border: none;
                border-radius: 10px; font-size: 13px; font-weight: 700; padding: 0 14px;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        logout_btn.clicked.connect(self._logout_action)
        l.addWidget(logout_btn, alignment=QtCore.Qt.AlignLeft)

        l.addStretch(1)

        footer = QtWidgets.QLabel(f"by redictor, 2026 • MIT License • {current_v}")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #8a8a8a;")
        l.addWidget(footer)

    def _change_password(self):
        ChangePasswordDialog.run(self, self.username)

    def _logout_action(self):
        ok = ConfirmDialog.ask(
            "Выход из аккаунта",
            "Вы действительно хотите выйти из аккаунта?",
            confirm_text="Выйти",
            cancel_text="Отмена",
            danger=False,
        )
        if not ok:
            return
        try:
            logout()
            _log.info("Пользователь вышел из аккаунта: %s", self.username)
        except Exception:
            _log.warning("Ошибка при выходе из аккаунта", exc_info=True)
        self.logout_requested.emit()

    def _on_reset_training(self):
        ok = ConfirmDialog.ask(
            "Сброс статистики",
            "Сбросить всю статистику тренировок?\n\nЭто действие нельзя отменить.",
            confirm_text="Сбросить",
            cancel_text="Отмена",
            danger=True
        )
        if not ok:
            return

        w = ApiWorker(reset_training_history)
        w.ok.connect(self._on_reset_ok)
        w.fail.connect(lambda _: RoundedDialog.warning("Ошибка", "Не удалось сбросить статистику.\nПопробуйте позже."))
        w.finished.connect(w.deleteLater)
        w.start()
        self._reset_worker = w

    def _on_reset_ok(self, result: bool):
        if result:
            _log.info("Статистика тренировок сброшена: %s", self.username)
            RoundedDialog.info("Готово", "Статистика тренировок успешно сброшена.")
            self.stats_reset.emit()
        else:
            _log.warning("Сброс статистики не удался (сервер вернул False)")
            RoundedDialog.warning("Ошибка", "Не удалось сбросить статистику.\nПопробуйте позже.")

    def apply_profile(self, profile):
        try:
            profile = profile or {}
            display_name = profile.get("display_name") or self.username

            self.settings_header_name_lbl.setText(display_name)
            self.settings_header_login_lbl.setText(f"@{self.username}")
            self.settings_org_lbl.setText(profile.get("organization_name") or "Не назначена")
            self.settings_course_lbl.setText(profile.get("course_group") or "Не указано")
            self.settings_access_lbl.setText(profile.get("access_expires_at") or "Не указано")
            self.settings_support_lbl.setText(profile.get("support_contact") or "Не указано")
            self.settings_license_badge.setText(profile.get("license_type") or "Учебная лицензия")

            created_at = profile.get("created_at")
            is_verified = False
            if created_at:
                s = str(created_at).replace("Z", "").replace(" ", "T")
                created = datetime.datetime.fromisoformat(s)
                is_verified = (datetime.datetime.now() - created).total_seconds() >= 24 * 60 * 60

            self._account_status = {"is_verified": is_verified, "created_at": created_at}
            self._apply_account_status_ui()
        except Exception:
            _log.error("Ошибка применения профиля в настройках", exc_info=True)

    def _apply_account_status_ui(self):
        is_verified = bool(self._account_status.get("is_verified", False))

        if is_verified:
            self.settings_verify_icon.setText("✓")
            self.settings_verify_icon.setStyleSheet("""
                QLabel { background-color: #22c55e; color: white; border-radius: 9px; font-size: 12px; font-weight: 800; }
            """)
            self.settings_verified_text.setText("Аккаунт верифицирован")
            self.settings_verified_text.setStyleSheet("font-size: 13px; color: #16a34a; font-weight: 700;")
        else:
            self.settings_verify_icon.setText("!")
            self.settings_verify_icon.setStyleSheet("""
                QLabel { background-color: #f59e0b; color: white; border-radius: 9px; font-size: 12px; font-weight: 800; }
            """)
            self.settings_verified_text.setText("Аккаунт будет автоматически верифицирован через 24 часа после регистрации")
            self.settings_verified_text.setStyleSheet("font-size: 13px; color: #d97706; font-weight: 700;")
