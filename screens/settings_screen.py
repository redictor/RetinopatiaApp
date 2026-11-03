import datetime
import i18n
from dialogs.language_dialog import LanguageDialog
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal
from api_client import reset_training_history, logout
from dialogs.ui_dialogs import RoundedDialog, ConfirmDialog, ChangePasswordDialog, ApiWorker, SecretKeyDialog
import app_logger
from main import current_v
from appearance_controls import AccentSelector, AnimationSelector
from ui_theme import current_accent, blend

_log = app_logger.get("screens.settings")

class AnimatedLanguageSwitcher(QtWidgets.QWidget):
    language_requested = QtCore.pyqtSignal(str)

    CLOSED_W = 79
    OPEN_W = 236
    HEIGHT = 38

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed
        )

        self._left = self._make_button()
        self._middle = self._make_button()
        self._current = self._make_button()

        self._current.setIcon(self._globe_icon())
        self._current.setIconSize(QtCore.QSize(17, 17))

        self._current.clicked.connect(self._toggle)
        self._left.clicked.connect(
            lambda checked=False: self._choose(self._other_codes[0])
        )
        self._middle.clicked.connect(
            lambda checked=False: self._choose(self._other_codes[1])
        )

        self._animation = QtCore.QVariantAnimation(self)
        self._animation.valueChanged.connect(self._change_width)

        self._globe_opacity = 1.0

        self._globe_animation = QtCore.QVariantAnimation(self)
        self._globe_animation.valueChanged.connect(
            self._set_globe_opacity
        )

        self.setFixedSize(self.CLOSED_W, self.HEIGHT)
        self._refresh_labels()
        self._position_buttons()

    def _make_button(self):
        button = QtWidgets.QPushButton(self)
        button.setCursor(QtCore.Qt.PointingHandCursor)

        button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #172033;
                border: none;
                border-radius: 18px;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: 650;
            }
            QPushButton:hover {
                background: #E8F4FC;
            }
            QPushButton:pressed {
                background: #D5EAFA;
            }
        """)

        return button

    def _globe_icon(self):
        pixmap = QtGui.QPixmap(18, 18)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(
            QtGui.QPen(QtGui.QColor("#111827"), 1.5)
        )

        painter.drawEllipse(QtCore.QRectF(2, 2, 14, 14))
        painter.drawEllipse(QtCore.QRectF(6.5, 2, 5, 14))
        painter.drawLine(
            QtCore.QPointF(2, 9),
            QtCore.QPointF(16, 9)
        )
        painter.end()

        return QtGui.QIcon(pixmap)

    def _set_globe_opacity(self, value):
        opacity = max(0.0, min(1.0, float(value)))
        self._globe_opacity = opacity

        if opacity <= 0.001:
            self._current.setIcon(QtGui.QIcon())
            self._current.setIconSize(QtCore.QSize(0, 0))
            return

        pixmap = QtGui.QPixmap(18, 18)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setOpacity(opacity)
        painter.drawPixmap(
            0, 0,
            self._globe_icon().pixmap(18, 18)
        )
        painter.end()

        icon_size = max(1, round(17 * opacity))

        self._current.setIcon(QtGui.QIcon(pixmap))
        self._current.setIconSize(
            QtCore.QSize(icon_size, icon_size)
        )

    def _refresh_labels(self):
        names = {
            "ru": "RU",
            "en": "EN",
            "zh": "中文"
        }

        current = i18n.get_current_language()

        self._other_codes = [
            code for code in ("zh", "ru", "en")
            if code != current
        ]

        self._left.setText(names[self._other_codes[0]])
        self._middle.setText(names[self._other_codes[1]])
        self._current.setText(" " + names[current])

        self._set_globe_opacity(
            0.0 if self._expanded else 1.0
        )
        self._current.show()
        self._current.raise_()

    def _position_buttons(self):
        x = self.width() - 78
        h = self.HEIGHT - 2

        self._left.setGeometry(x - 157, 1, 81, h)
        self._middle.setGeometry(x - 76, 1, 76, h)
        self._current.setGeometry(x, 1, 77, h)

        self._current.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_buttons()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        painter.setPen(
            QtGui.QPen(QtGui.QColor(blend("#ffffff", current_accent(), .22)), 1)
        )
        painter.setBrush(QtGui.QColor("#FFFFFF"))

        painter.drawRoundedRect(
            QtCore.QRectF(
                0.5, 0.5,
                self.width() - 1,
                self.height() - 1
            ),
            19, 19
        )
        painter.end()

    def _change_width(self, width):
        self.setFixedWidth(int(width))

    def collapse(self):
        self._animation.stop()
        self._expanded = False
        self._globe_animation.stop()
        self._set_globe_opacity(1.0)
        self.setFixedWidth(self.CLOSED_W)
        self._position_buttons()

    def _toggle(self):
        self._animate(not self._expanded)

    def set_animated(self, enabled):
        self._animations_enabled = bool(enabled)
        if not enabled:
            self._animation.stop()
            self._globe_animation.stop()
            self.collapse()

    def _animate(self, expanded):
        self._expanded = expanded
        if not self._animations_enabled:
            self._animation.stop()
            self._globe_animation.stop()
            self.setFixedWidth(self.OPEN_W if expanded else self.CLOSED_W)
            self._set_globe_opacity(0.0 if expanded else 1.0)
            self._position_buttons()
            return

        self._globe_animation.stop()

        self._globe_animation.setStartValue(
            self._globe_opacity
        )
        self._globe_animation.setEndValue(
            0.0 if expanded else 1.0
        )

        self._globe_animation.setDuration(
            180 if expanded else 250
        )

        self._globe_animation.setEasingCurve(
            QtCore.QEasingCurve.InOutCubic
        )

        self._globe_animation.start()

        self._animation.stop()
        self._animation.setStartValue(self.width())
        self._animation.setEndValue(
            self.OPEN_W if expanded else self.CLOSED_W
        )

        self._animation.setDuration(
            350 if expanded else 280
        )

        self._animation.setEasingCurve(
            QtCore.QEasingCurve.OutBack
            if expanded
            else QtCore.QEasingCurve.InOutCubic
        )

        self._animation.start()

    def _choose(self, code):
        if code == i18n.get_current_language():
            self._animate(False)
            return

        self._animate(False)

        if not self._animations_enabled:
            self.language_requested.emit(code)
        else:
            QtCore.QTimer.singleShot(
                310,
                lambda: self.language_requested.emit(code)
            )

class SettingsScreen(QtWidgets.QWidget):
    logout_requested = pyqtSignal()
    stats_reset = pyqtSignal()
    refresh_requested = QtCore.pyqtSignal()
    dev_mode_trigger = pyqtSignal()
    accent_changed = pyqtSignal(str)
    animations_changed = pyqtSignal(bool)

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self._account_status = {"is_verified": False, "created_at": None}
        self._reset_worker = None
        self._logout_worker = None
        self._build()

    def _build(self):
        self.setStyleSheet("background: transparent;")
        l = QtWidgets.QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)

        title = QtWidgets.QLabel(i18n.t("settings.title"))
        title.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #222;"
        )

        header_row = QtWidgets.QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        header_row.addWidget(title)
        header_row.addStretch(1)

        self.language_switch = AnimatedLanguageSwitcher(self)
        self.language_switch.language_requested.connect(
            self._request_language_change
        )
        self.language_switch.set_animated(
            QtCore.QSettings("redictor", "RetinopatiaApp").value(
                "animations_enabled", True, type=bool
            )
        )
        header_row.addWidget(self.language_switch)

        l.addLayout(header_row)


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

        verified_text = QtWidgets.QLabel(i18n.t("settings.account_verified"))
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

        org_title = QtWidgets.QLabel(i18n.t("settings.organization"))
        org_title.setStyleSheet("font-size:16px;font-weight:900;color:#111827;")

        self.settings_license_badge = QtWidgets.QLabel(i18n.t("settings.academic_license"))
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

        org_name_widget, self.settings_org_lbl = org_item(
            i18n.t("settings.org_name"),
            i18n.t("settings.not_assigned_f")
        )
        course_widget, self.settings_course_lbl = org_item(
            i18n.t("settings.course_group"),
            i18n.t("settings.not_specified")
        )
        access_widget, self.settings_access_lbl = org_item(
            i18n.t("settings.access_until"),
            i18n.t("settings.not_specified")
        )
        support_widget, self.settings_support_lbl = org_item(
            i18n.t("settings.teacher"),
            i18n.t("settings.not_assigned_m")
        )

        grid.addWidget(org_name_widget, 0, 0)
        grid.addWidget(course_widget, 0, 1)
        grid.addWidget(access_widget, 1, 0)
        grid.addWidget(support_widget, 1, 1)

        org_layout.addLayout(grid)
        l.addWidget(org_box)

        prefs = QtCore.QSettings("redictor", "RetinopatiaApp")
        lang = i18n.get_current_language()
        labels = {
            "ru": ("Внешний вид", "Акцентный цвет", "Плавные анимации",
                   ("Синий", "Бирюзовый", "Фиолетовый")),
            "en": ("Appearance", "Accent color", "Smooth animations",
                   ("Blue", "Cyan", "Purple")),
            "zh": ("外观", "主题色", "平滑动画",
                   ("蓝色", "青色", "紫色")),
        }
        heading, color_label, anim_label, names = labels.get(
            lang, labels["ru"]
        )

        appearance_box = QtWidgets.QFrame()
        appearance_box.setObjectName("appearanceBox")
        appearance_box.setStyleSheet("""
            QFrame#appearanceBox {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
            }
            QLabel { border: none; background: transparent; }
        """)
        appearance_layout = QtWidgets.QVBoxLayout(appearance_box)
        appearance_layout.setContentsMargins(16, 12, 16, 12)
        appearance_layout.setSpacing(12)

        appearance_title = QtWidgets.QLabel(heading)
        appearance_title.setStyleSheet(
            "font-size: 15px; font-weight: 800; color: #1f2937;"
        )
        appearance_layout.addWidget(appearance_title)

        def row_label(text):
            widget = QtWidgets.QLabel(text)
            widget.setStyleSheet("font-size: 13px; color: #374151;")
            return widget

        color_row = QtWidgets.QHBoxLayout()
        color_row.addWidget(row_label(color_label))
        color_row.addStretch(1)
        self.accent_select = AccentSelector(
            names, prefs.value("accent_color", "#0078D7")
        )
        self.accent_select.changed.connect(self.accent_changed.emit)
        color_row.addWidget(self.accent_select)
        appearance_layout.addLayout(color_row)

        animation_row = QtWidgets.QHBoxLayout()
        animation_row.addWidget(row_label(anim_label))
        animation_row.addStretch(1)
        enabled = prefs.value("animations_enabled", True, type=bool)
        self.animations_toggle = AnimationSelector(enabled=enabled)
        self.animations_toggle.set_animated(enabled)
        self.accent_select.set_animated(enabled)
        self.animations_toggle.changed.connect(self._animations_selection_changed)
        animation_row.addWidget(self.animations_toggle)
        appearance_layout.addLayout(animation_row)

        l.addWidget(appearance_box)

        change_pwd_btn = QtWidgets.QPushButton(i18n.t("settings.change_password"))
        change_pwd_btn.setFixedHeight(38)
        change_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3; color: #222; border: none;
                border-radius: 10px; font-size: 13px; font-weight: 700; padding: 0 14px;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        change_pwd_btn.clicked.connect(self._change_password)

        logout_btn = QtWidgets.QPushButton(i18n.t("settings.logout"))
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

        self.btn_refresh_data = QtWidgets.QPushButton(i18n.t("settings.update_data"))
        self.btn_refresh_data.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_refresh_data.setFixedHeight(38)
        self.btn_refresh_data.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3; color: #222; border: none;
                border-radius: 10px; font-size: 13px; font-weight: 700; padding: 0 14px;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        self.btn_refresh_data.clicked.connect(self.refresh_requested.emit)

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.setSpacing(10)
        actions_row.addWidget(change_pwd_btn)
        actions_row.addWidget(logout_btn)
        actions_row.addWidget(self.btn_refresh_data)
        actions_row.addStretch(1)
        l.addLayout(actions_row)

        l.addStretch(1)

        footer = QtWidgets.QLabel(f"by redictor, 2026 • Custom Non-Commercial License • {current_v}")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #8a8a8a;")
        l.addWidget(footer)

        self._footer_click_count = 0
        self._footer_click_timer = QtCore.QTimer(self)
        self._footer_click_timer.setSingleShot(True)
        self._footer_click_timer.timeout.connect(self._reset_footer_clicks)
        footer.mousePressEvent = self._on_footer_click

        self._konami_sequence = [
            QtCore.Qt.Key_Up, QtCore.Qt.Key_Down,
            QtCore.Qt.Key_Up, QtCore.Qt.Key_Up,
            QtCore.Qt.Key_Down, QtCore.Qt.Key_Left,
        ]
        self._konami_progress = 0
        self._konami_active = False
        self._konami_timer = QtCore.QTimer(self)
        self._konami_timer.setSingleShot(True)
        self._konami_timer.timeout.connect(self._reset_konami)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def _animations_selection_changed(self, enabled):
        enabled = bool(enabled)
        self.animations_toggle.set_animated(enabled)
        self.accent_select.set_animated(enabled)
        self.animations_changed.emit(enabled)

    def _reset_footer_clicks(self):
        self._footer_click_count = 0

    def _request_language_change(self, code):
        window = self.window()
        if hasattr(window, "change_app_language"):
            window.change_app_language(code)

    def hideEvent(self, event):
        switch = getattr(self, "language_switch", None)

        if switch is not None:
            switch.collapse()

        super().hideEvent(event)

    def _on_footer_click(self, event):
        self._footer_click_count += 1
        self._footer_click_timer.start(3000)
        if self._footer_click_count >= 7:
            self._footer_click_count = 0
            self._footer_click_timer.stop()
            self._konami_active = True
            self._konami_progress = 0
            self.setFocus()
            self._konami_timer.start(5000)

    def _reset_konami(self):
        self._konami_active = False
        self._konami_progress = 0

    def keyPressEvent(self, event):
        if self._konami_active:
            expected = self._konami_sequence[self._konami_progress]
            if event.key() == expected:
                self._konami_progress += 1
                self._konami_timer.start(5000)
                if self._konami_progress >= len(self._konami_sequence):
                    self._konami_active = False
                    self._konami_progress = 0
                    self._open_secret_dialog()
                event.accept()
                return
            else:
                self._konami_active = False
                self._konami_progress = 0
        super().keyPressEvent(event)

    def _open_secret_dialog(self):
        word = SecretKeyDialog.ask_word(self.window())
        if word.strip().lower() == "redictor":
            self.dev_mode_trigger.emit()

    def _change_password(self):
        ChangePasswordDialog.run(self.window(), self.username)

    def _logout_action(self):
        ok = ConfirmDialog.ask(
            i18n.t("settings.logout_confirm_title"),
            i18n.t("settings.logout_confirm_text"),
            confirm_text=i18n.t("settings.logout"),
            cancel_text=i18n.t("settings.cancel"),
            danger=False,
        )
        if not ok:
            return
        if self._logout_worker is not None and self._logout_worker.isRunning():
            return
        worker = ApiWorker(logout)
        self._logout_worker = worker
        worker.finished.connect(self._on_logout_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_logout_finished(self):
        _log.info("Пользователь вышел из аккаунта: %s", self.username)
        self.logout_requested.emit()

    def _on_reset_training(self):
        ok = ConfirmDialog.ask(
            i18n.t("settings.reset_stats"),
            i18n.t("settings.reset_confirm_text"),
            confirm_text=i18n.t("settings.reset_button"),
            cancel_text=i18n.t("settings.cancel"),
            danger=True
        )
        if not ok:
            return

        w = ApiWorker(reset_training_history)
        w.ok.connect(self._on_reset_ok)
        w.fail.connect(lambda _: RoundedDialog.warning(
            i18n.t("settings.error"),
            i18n.t("settings.reset_error")
        ))
        w.finished.connect(w.deleteLater)
        w.start()
        self._reset_worker = w

    def _on_reset_ok(self, result: bool):
        if result:
            _log.info("Статистика тренировок сброшена: %s", self.username)
            RoundedDialog.info(
                i18n.t("settings.done"),
                i18n.t("settings.reset_success")
            )
            self.stats_reset.emit()
        else:
            _log.warning("Сброс статистики не удался (сервер вернул False)")
            RoundedDialog.warning(
                i18n.t("settings.error"),
                i18n.t("settings.reset_error")
            )

    def apply_profile(self, profile):
        try:
            profile = profile or {}
            display_name = profile.get("display_name") or self.username

            self.settings_header_name_lbl.setText(display_name)
            self.settings_header_login_lbl.setText(f"@{self.username}")
            self.settings_org_lbl.setText(
                profile.get("organization_name") or i18n.t("settings.not_assigned_f")
            )
            self.settings_course_lbl.setText(
                profile.get("course_group") or i18n.t("settings.not_specified")
            )
            self.settings_access_lbl.setText(
                profile.get("access_expires_at") or i18n.t("settings.not_specified")
            )
            self.settings_support_lbl.setText(
                profile.get("teacher_display_name") or i18n.t("settings.not_assigned_m")
            )
            license_type = profile.get("license_type")

            self.settings_license_badge.setText(
                i18n.t("settings.academic_license")
                if not license_type or license_type == "Учебная лицензия"
                else license_type
            )

            created_at = profile.get("created_at")
            is_verified = False
            if created_at:
                s = str(created_at).replace("Z", "+00:00").replace(" ", "T")
                created = datetime.datetime.fromisoformat(s)
                now = datetime.datetime.now(created.tzinfo)
                is_verified = (now - created).total_seconds() >= 24 * 60 * 60

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
            self.settings_verified_text.setText(
                i18n.t("settings.account_verified")
            )
            self.settings_verified_text.setStyleSheet("font-size: 13px; color: #16a34a; font-weight: 700;")
        else:
            self.settings_verify_icon.setText("!")
            self.settings_verify_icon.setStyleSheet("""
                QLabel { background-color: #f59e0b; color: white; border-radius: 9px; font-size: 12px; font-weight: 800; }
            """)
            self.settings_verified_text.setText(
                i18n.t("settings.verification_pending")
            )
            self.settings_verified_text.setStyleSheet("font-size: 13px; color: #d97706; font-weight: 700;")