import os
import sys
import datetime
import json
import functools
import i18n

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

from PyQt5 import QtWidgets, QtCore, QtGui
from ui_theme import AccentTheme, ACCENTS, BLUE

from api_client import (
    logout, get_maintenance_status, get_training_history,
    save_training_record, get_profile, get_updates,
)
from dialogs.ui_dialogs import RoundedDialog, ApiWorker, DevPanelDialog, ConfirmDialog
from ui_styles import create_window_buttons
from ui_theme import AccentTheme, ACCENTS, BLUE, blend, current_accent
import app_logger
from main import current_v
from screens.home_screen import HomeScreen
from screens.training_screen import TrainingScreen
from screens.stats_screen import StatsScreen
from screens.settings_screen import SettingsScreen
from screens.history_screen import HistoryScreen

_log = app_logger.get("window")

class LanguageSpinner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.angle = 0

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.angle = (self.angle + 9) % 360
        self.update()

    def start(self):
        self.timer.start(25)

    def stop(self):
        self.timer.stop()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = QtCore.QRectF(5, 5, 24, 24)

        pen = QtGui.QPen(QtGui.QColor("#D0E9FB"), 3)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)

        pen.setColor(QtGui.QColor(current_accent()))
        p.setPen(pen)
        p.drawArc(
            rect,
            -self.angle * 16,
            110 * 16
        )
        p.end()

class LanguageLoadingOverlay(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            LanguageLoadingOverlay {
                background: rgba(245, 250, 255, 190);
                border-radius: 20px;
            }
        """)

        self.setGeometry(parent.rect())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(12)

        self.spinner = LanguageSpinner()
        layout.addWidget(
            self.spinner,
            alignment=QtCore.Qt.AlignCenter
        )

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("""
            color: #172033;
            background: transparent;
            font-family: "Segoe UI";
            font-size: 14px;
            font-weight: 600;
        """)
        layout.addWidget(self.label)

        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

        self.fade = QtCore.QPropertyAnimation(
            self.opacity_effect, b"opacity", self
        )
        self.fade.setDuration(350)
        self.fade.setEasingCurve(
            QtCore.QEasingCurve.InOutCubic
        )

        self.hide()

    def animate_opacity(self, start, end, duration=350):
        self.fade.stop()
        self.fade.setDuration(duration)
        self.fade.setStartValue(start)
        self.fade.setEndValue(end)
        self.fade.start()

class AnimatedMenuButton(QtWidgets.QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

        self._bg_color = QtGui.QColor("#ffffff")
        self._border_color = QtGui.QColor("#e4ebf3")

        self._hover_anim = QtCore.QVariantAnimation(self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setEasingCurve(
            QtCore.QEasingCurve.InOutSine
        )
        self._hover_anim.valueChanged.connect(
            self._update_hover_color
        )

        self._apply_style()

    def _apply_style(self):
        bg = self._bg_color.name()
        border = self._border_color.name()

        accent = getattr(self, "_accent_color", "#0078D7")

        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: 16px;
                padding-right: 14px;
                font-size: 16px;
                color: #222222;
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}

            QPushButton:checked {{
                background: {accent};
                color: white;
                border: 1px solid {accent};
            }}
        """)
    
    def _update_hover_color(self, color):
        self._bg_color = color
        self._border_color = QtGui.QColor(
            blend("#ffffff", getattr(self, "_accent_color", BLUE), .30)
            if color.lightness() < 254 else "#e4ebf3"
        )
        self._apply_style()

    def _animate_hover(self, target):
        self._hover_anim.stop()

        if not getattr(self, "_animations_enabled", True):
            self._update_hover_color(QtGui.QColor(target))
            return

        self._hover_anim.setStartValue(self._bg_color)
        self._hover_anim.setEndValue(QtGui.QColor(target))
        self._hover_anim.start()

    def enterEvent(self, event):
        self._animate_hover(blend("#ffffff", getattr(self, "_accent_color", BLUE), .065))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover("#ffffff")
        super().leaveEvent(event)

class MainWindow(QtWidgets.QWidget):
    def __init__(self, username: str, on_logout):
        super().__init__()
        self.username = username
        self.on_logout = on_logout
        self.old_pos = None

        self._ui_settings = QtCore.QSettings(
            "redictor", "RetinopatiaApp"
        )

        stored_accent = str(self._ui_settings.value(
            "accent_color", "#0078D7"
        ))
        self._accent_color = next(
            (candidate for candidate in ACCENTS
             if candidate.lower() == stored_accent.lower()), BLUE
        )

        self._animations_enabled = self._ui_settings.value(
            "animations_enabled", True, type=bool
        )

        self.setWindowTitle("RetinopatiaApp")
        self.setFixedSize(1400, 890)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self._maint_forced = False
        self._sync_in_progress = False
        self._dev_mode_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "jsons",
            "dev_mode.json"
        )
        self.dev_mode = False
        self._save_dev_mode(False)
        self._last_debug_data = {}
        self._last_profile = None
        self._dev_panel = None
        self._logo_click_count = 0
        self._logo_click_timer = QtCore.QTimer(self)
        self._logo_click_timer.setSingleShot(True)
        self._logo_click_timer.timeout.connect(self._reset_logo_clicks)
        self._save_record_workers = set()

        self._build_ui()

        app = QtWidgets.QApplication.instance()

        self._theme = app._retina_theme
        self._apply_accent_color(self._accent_color)
        self._apply_accent_color(self._accent_color)
        self._set_animations_enabled(self._animations_enabled)

        self._color_overlay = LanguageLoadingOverlay(self)
        self._color_overlay.label.setText("")
        self._color_blur = None
        self._color_blur_animation = None
        self._color_busy = False
        self._queued_accent = None
        self._language_overlay = LanguageLoadingOverlay(self)
        self._language_blur = None
        self._language_busy = False

        self._sync_timer = QtCore.QTimer(self)
        self._sync_timer.timeout.connect(self._sync_all_data)
        self._sync_timer.start(10000)

        QtCore.QTimer.singleShot(300, self._sync_all_data)

    def _build_ui(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setObjectName("mainWrapper")
        wrapper.setGeometry(0, 0, 1400, 890)
        wrapper.setStyleSheet("""
            QWidget#mainWrapper {
                background-color: #f5f5f5;
                border: 1.2px solid #c7d2e0;
                border-radius: 20px;
            }
        """)

        root = QtWidgets.QVBoxLayout(wrapper)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        top_bar = QtWidgets.QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background: transparent;")
        top_bar.mousePressEvent = self._top_mouse_press
        top_bar.mouseMoveEvent = self._top_mouse_move
        top_bar.mouseReleaseEvent = self._top_mouse_release

        top = QtWidgets.QHBoxLayout(top_bar)
        top.setContentsMargins(0, 0, 0, 0)
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
                logo_pixmap.scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            )
        else:
            logo_label.setText("◉")
            logo_label.setStyleSheet("QLabel { color: #0078D7; font-size: 18px; font-weight: 900; }")

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("QLabel { color: #222; font-size: 18px; font-weight: 600; }")

        self.dev_badge = QtWidgets.QLabel("DEV")
        self.dev_badge.setStyleSheet("""
            QLabel {
                color: #ff8c00;
                background: transparent;
                font-size: 11px;
                font-weight: 900;
            }
        """)
        self.dev_badge.setVisible(self.dev_mode)
        self.dev_badge.setCursor(QtCore.Qt.ArrowCursor)
        self.dev_badge.mousePressEvent = self._on_dev_badge_click

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(app_label)

        drag_area = QtWidgets.QWidget()
        drag_area.setStyleSheet("background: transparent;")
        drag_area.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        minimize_button, close_button = create_window_buttons(self)

        top.addWidget(brand)
        top.addWidget(self.dev_badge)
        top.addStretch(1)
        top.addWidget(drag_area, 1)
        top.addWidget(minimize_button)
        top.addWidget(close_button)
        root.addWidget(top_bar)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)

        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(290)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #dfe7f1;
                border-radius: 16px;
            }
        """)

        side_layout = QtWidgets.QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)
        side_layout.addSpacing(6)

        self.btn_home = self.menu_button(" " + i18n.t("nav.home"), "assets/icons/home.png")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self.set_page(0))
        side_layout.addWidget(self.btn_home)

        self.btn_training = self.menu_button(" " + i18n.t("nav.training"), "assets/icons/training.png")
        self.btn_training.clicked.connect(lambda: self.set_page(1))
        side_layout.addWidget(self.btn_training)

        self.btn_stats = self.menu_button(" " + i18n.t("nav.stats"), "assets/icons/stats.png")
        self.btn_stats.clicked.connect(lambda: self.set_page(2))
        side_layout.addWidget(self.btn_stats)

        self.btn_history = self.menu_button(" " + i18n.t("nav.history"), "assets/icons/history.png")
        self.btn_history.clicked.connect(lambda: self.set_page(3))
        side_layout.addWidget(self.btn_history)

        side_layout.addStretch(1)

        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e6e6e6;")
        side_layout.addWidget(line)

        self.btn_settings = self.menu_button(" " + i18n.t("nav.settings"), "assets/icons/settings.png")
        self.btn_settings.setChecked(False)
        self.btn_settings.clicked.connect(lambda: self.set_page(4))
        side_layout.addWidget(self.btn_settings)

        self._nav_buttons = [
            self.btn_home,
            self.btn_training,
            self.btn_stats,
            self.btn_history,
            self.btn_settings,
        ]

        self._nav_indicator = QtWidgets.QFrame(sidebar)
        self._nav_indicator.setObjectName("navIndicator")
        self._nav_indicator.setFixedSize(4, 32)
        self._nav_indicator.setStyleSheet("""
            QFrame#navIndicator {
                background-color: #0078D7;
                border: none;
                border-radius: 2px;
            }
        """)
        self._nav_indicator.setAttribute(
            QtCore.Qt.WA_TransparentForMouseEvents, True
        )
        self._nav_indicator.raise_()

        self._nav_animation = QtCore.QPropertyAnimation(
            self._nav_indicator, b"pos", self
        )
        self._nav_animation.setDuration(230)
        self._nav_animation.setEasingCurve(
            QtCore.QEasingCurve.InOutCubic
        )

        content = QtWidgets.QFrame()
        content.setObjectName("contentFrame")
        content.setStyleSheet("""
            QFrame#contentFrame {
                background-color: #ffffff;
                border: 1px solid #dfe7f1;
                border-radius: 16px;
            }
        """)

        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        self.home_screen = HomeScreen(self.username)
        self.training_screen = TrainingScreen(on_save_record=self._stats_append)
        self.stats_screen = StatsScreen()
        self.history_screen = HistoryScreen()
        self.settings_screen = SettingsScreen(self.username)

        self.home_screen.btn_start_training.clicked.connect(lambda: self.set_page(1))
        self.home_screen.btn_open_stats.clicked.connect(lambda: self.set_page(2))
        self.home_screen.btn_open_history.clicked.connect(lambda: self.set_page(3))
        self.home_screen.btn_open_settings.clicked.connect(lambda: self.set_page(4))

        self.settings_screen.logout_requested.connect(self._do_logout)
        self.settings_screen.stats_reset.connect(self._sync_all_data)

        self.settings_screen.refresh_requested.connect(self._sync_all_data)
        self.settings_screen.dev_mode_trigger.connect(self._toggle_dev_mode)

        self.settings_screen.accent_changed.connect(
            self._request_accent_color
        )
        self.settings_screen.animations_changed.connect(
            self._set_animations_enabled
        )

        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self.home_screen)
        self.pages.addWidget(self.training_screen)
        self.pages.addWidget(self.stats_screen)
        self.pages.addWidget(self.history_screen)
        self.pages.addWidget(self.settings_screen)
        self.pages.setStyleSheet("""
            QWidget { background: transparent; }
            QLabel  { background: transparent; }
        """)
        content_layout.addWidget(self.pages)

        body.addWidget(sidebar)
        body.addWidget(content, 1)
        root.addLayout(body)

        QtCore.QTimer.singleShot(
            0,
            lambda: self._move_nav_indicator(0, animate=False)
        )

        QtCore.QTimer.singleShot(1200, self._check_update)
    
    def change_app_language(self, code):
        if self._language_busy or self._color_busy:
            return

        if code == i18n.get_current_language():
            return

        messages = {
            "ru": (
                "Изменение языка",
                "Применить русский язык к интерфейсу?"
            ),
            "en": (
                "Change language",
                "Apply English to the interface?"
            ),
            "zh": (
                "更改语言",
                "将界面语言更改为中文？"
            ),
        }

        title, message = messages[code]

        dialog = ConfirmDialog(
            title,
            message,
            confirm_text={"ru": "Да", "en": "Yes", "zh": "是"}[code],
            cancel_text={"ru": "Нет", "en": "No", "zh": "否"}[code],
            button_width=90
        )

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        self._language_busy = True
        if not self._animations_enabled:
            self._finish_language_change(code)
            return

        overlay = self._language_overlay
        overlay.setGeometry(self.rect())

        overlay.label.setText({
            "ru": "Применение языка...",
            "en": "Applying language...",
            "zh": "正在应用语言...",
        }[code])

        wrapper = self.findChild(
            QtWidgets.QWidget, "mainWrapper"
        )

        if wrapper is not None:
            self._language_blur = QtWidgets.QGraphicsBlurEffect(wrapper)
            self._language_blur.setBlurRadius(0)
            wrapper.setGraphicsEffect(self._language_blur)

        overlay.raise_()
        overlay.show()
        overlay.spinner.start()
        overlay.animate_opacity(0, 1, 300)

        self._blur_animation = QtCore.QPropertyAnimation(
            self._language_blur, b"blurRadius", self
        ) if self._language_blur else None

        if self._blur_animation:
            self._blur_animation.setDuration(650)
            self._blur_animation.setStartValue(0)
            self._blur_animation.setEndValue(17)
            self._blur_animation.start()

        QtCore.QTimer.singleShot(
            1350,
            lambda: self._finish_language_change(code)
        )


    def _finish_language_change(self, code):
        try:
            screens = (
                self.home_screen, self.training_screen,
                self.stats_screen, self.history_screen
            )
            for screen in screens:
                i18n.capture_widget_texts(screen)

            i18n.set_language(code)

            for screen in screens:
                i18n.retranslate_widget_texts(screen)
            self.training_screen.retranslate_ui()
            self.stats_screen.retranslate_chart()
            self.home_screen.apply_profile(self._last_profile)
            if self.home_screen._cached_stats is not None:
                self.home_screen.apply_stats(self.home_screen._cached_stats)
            if self.home_screen._cached_updates is not None:
                self.home_screen.apply_updates(self.home_screen._cached_updates)
            if self.history_screen._cached_history is not None:
                self.history_screen.apply_data(self.history_screen._cached_history)

            _log.info(
                "Язык переключён: requested=%s, current=%s, home=%s",
                code,
                i18n.get_current_language(),
                i18n.t("nav.home")
            )

            self.btn_home.setText(" " + i18n.t("nav.home"))
            self.btn_training.setText(" " + i18n.t("nav.training"))
            self.btn_stats.setText(" " + i18n.t("nav.stats"))
            self.btn_history.setText(" " + i18n.t("nav.history"))
            self.btn_settings.setText(" " + i18n.t("nav.settings"))

            old = self.settings_screen
            self.pages.removeWidget(old)
            old.hide()
            old.deleteLater()

            self.settings_screen = SettingsScreen(self.username)
            self.pages.insertWidget(4, self.settings_screen)

            self.settings_screen.logout_requested.connect(self._do_logout)
            self.settings_screen.stats_reset.connect(self._sync_all_data)
            self.settings_screen.refresh_requested.connect(self._sync_all_data)
            self.settings_screen.dev_mode_trigger.connect(self._toggle_dev_mode)
            self.settings_screen.accent_changed.connect(self._request_accent_color)
            self.settings_screen.animations_changed.connect(self._set_animations_enabled)
            self.settings_screen.accent_select.set_accent(self._accent_color)
            self.settings_screen.accent_select.set_selection(self._accent_color)
            self.settings_screen.accent_select.set_animated(self._animations_enabled)
            self.settings_screen.animations_toggle.set_animated(self._animations_enabled)
            self._theme.apply_all()

            if self._last_profile is not None:
                self.settings_screen.apply_profile(self._last_profile)

            self.set_page(4)

        except Exception:
            _log.exception("Ошибка применения языка")
            RoundedDialog.warning(
                "Error",
                "Could not apply the selected language."
            )

        finally:
            self._end_language_loading()

    def _end_language_loading(self):
        if not self._animations_enabled and not self._language_overlay.isVisible():
            self._language_busy = False
            return
        overlay = self._language_overlay

        if self._blur_animation:
            self._blur_animation.stop()
            self._blur_animation = None

        if self._language_blur:
            self._blur_animation = QtCore.QPropertyAnimation(
                self._language_blur, b"blurRadius", self
            )
            self._blur_animation.setDuration(660)
            self._blur_animation.setStartValue(
                self._language_blur.blurRadius()
            )
            self._blur_animation.setEndValue(0)
            self._blur_animation.start()

        overlay.animate_opacity(1, 0, 650)

        QtCore.QTimer.singleShot(
            680,
            self._cleanup_language_loading
        )

    def _cleanup_language_loading(self):
        self._language_overlay.spinner.stop()
        self._language_overlay.hide()

        wrapper = self.findChild(
            QtWidgets.QWidget, "mainWrapper"
        )

        if wrapper is not None:
            wrapper.setGraphicsEffect(None)

        self._language_blur = None
        self._blur_animation = None
        self._language_busy = False

    def _move_nav_indicator(self, index, animate=True):
        if not 0 <= index < len(self._nav_buttons):
            return

        button = self._nav_buttons[index]
        indicator = self._nav_indicator

        target = QtCore.QPoint(
            button.x() - 7,
            button.y() + (button.height() - indicator.height()) // 2
        )

        if (
            self._nav_animation.state() == QtCore.QAbstractAnimation.Running
            and self._nav_animation.endValue() == target
        ):
            return

        if indicator.pos() == target:
            return

        self._nav_animation.stop()

        if not animate or not self._animations_enabled:
            indicator.move(target)
            return

        self._nav_animation.setStartValue(indicator.pos())
        self._nav_animation.setEndValue(target)
        self._nav_animation.start()

    def _request_accent_color(self, color):
        if color not in ACCENTS or color == self._accent_color and not self._color_busy:
            return
        if self._color_busy or self._language_busy:
            self._queued_accent = color
            return
        if not self._animations_enabled or not self.isVisible():
            self._apply_accent_color(color)
            return

        self._color_busy = True
        old_color = self._accent_color
        total = 3000
        fade_in = round(total * .25)
        fade_color = round(total * .30)
        fade_out = round(total * .45)

        overlay = self._color_overlay
        overlay.setGeometry(self.rect())
        overlay.label.setText({
            "ru": "Применение цвета интерфейса...",
            "en": "Applying interface color...",
            "zh": "正在应用界面颜色...",
        }.get(i18n.get_current_language(), "Применение цвета интерфейса..."))

        wrapper = self.findChild(QtWidgets.QWidget, "mainWrapper")
        self._color_blur = None
        if wrapper is not None:
            self._color_blur = QtWidgets.QGraphicsBlurEffect(wrapper)
            self._color_blur.setBlurRadius(0)
            wrapper.setGraphicsEffect(self._color_blur)

        overlay.raise_()
        overlay.show()
        overlay.spinner.start()
        overlay.animate_opacity(0, 1, fade_in)

        if self._color_blur is not None:
            animation = QtCore.QPropertyAnimation(
                self._color_blur, b"blurRadius", self
            )
            animation.setDuration(fade_in)
            animation.setStartValue(0)
            animation.setEndValue(16)
            animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
            self._color_blur_animation = animation
            animation.start()

        def recolor_under_blur():
            for n in range(1, 7):
                QtCore.QTimer.singleShot(
                    round(fade_color * n / 6),
                    lambda step=n: self._apply_accent_color(
                        color if step == 6 else blend(old_color, color, step / 6),
                        persist=(step == 6)
                    )
                )

        def finish_blur():
            if self._color_blur is not None:
                animation = QtCore.QPropertyAnimation(
                    self._color_blur, b"blurRadius", self
                )
                animation.setDuration(fade_out)
                animation.setStartValue(self._color_blur.blurRadius())
                animation.setEndValue(0)
                animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
                self._color_blur_animation = animation
                animation.start()
            overlay.animate_opacity(1, 0, fade_out)
            QtCore.QTimer.singleShot(
                fade_out + 30, self._cleanup_color_transition
            )

        QtCore.QTimer.singleShot(fade_in, recolor_under_blur)
        QtCore.QTimer.singleShot(fade_in + fade_color, finish_blur)

    def _apply_accent_color(self, color, persist=True):
        if not QtGui.QColor(color).isValid():
            return
        self._accent_color = color
        if persist:
            self._ui_settings.setValue("accent_color", color)
        self._theme.set_color(color)

        for button in self._nav_buttons:
            button._accent_color = color
            button._apply_style()

        self._nav_indicator.setStyleSheet(f"""
            QFrame#navIndicator {{
                background-color: {color};
                border: none;
                border-radius: 2px;
            }}
        """)
        self._theme.apply_all()
        if hasattr(self.training_screen, "_set_copy_icon"):
            self.training_screen._set_copy_icon()
        if hasattr(self.settings_screen, "accent_select"):
            self.settings_screen.accent_select.set_accent(color)

    def _cleanup_color_transition(self):
        self._color_overlay.spinner.stop()
        self._color_overlay.hide()
        wrapper = self.findChild(QtWidgets.QWidget, "mainWrapper")
        if wrapper is not None:
            wrapper.setGraphicsEffect(None)
        self._color_blur = None
        self._color_blur_animation = None
        self._color_busy = False
        pending = self._queued_accent
        self._queued_accent = None
        if pending in ACCENTS and pending != self._accent_color:
            self._request_accent_color(pending)

    def _set_animations_enabled(self, enabled):
        self._animations_enabled = bool(enabled)
        self._ui_settings.setValue(
            "animations_enabled",
            self._animations_enabled
        )

        if not self._animations_enabled:
            animation = getattr(self, "_page_fade_anim", None)
            page = getattr(self, "_page_fade_widget", None)

            if animation is not None:
                animation.stop()

            if page is not None:
                page.setGraphicsEffect(None)

            self._page_fade_anim = None
            self._page_fade_widget = None

            self._nav_animation.stop()
            self._move_nav_indicator(
                self.pages.currentIndex(), animate=False
            )

        for button in self._nav_buttons:
            button._animations_enabled = self._animations_enabled
            button._hover_anim.stop()
            if not self._animations_enabled:
                button._bg_color = QtGui.QColor("#ffffff")
                button._border_color = QtGui.QColor("#e4ebf3")
                button._apply_style()

        if hasattr(self.settings_screen, "accent_select"):
            self.settings_screen.accent_select.set_animated(self._animations_enabled)
            self.settings_screen.animations_toggle.set_animated(self._animations_enabled)
            self.settings_screen.language_switch.set_animated(self._animations_enabled)

    def set_page(self, index: int):
        if index < 0 or index >= self.pages.count():
            return

        old_anim = getattr(self, "_page_fade_anim", None)
        old_page = getattr(self, "_page_fade_widget", None)

        if old_anim is not None:
            old_anim.stop()

        if old_page is not None:
            old_page.setGraphicsEffect(None)

        self._page_fade_anim = None
        self._page_fade_widget = None

        current_index = self.pages.currentIndex()

        if self.pages.currentIndex() != index:
            self.pages.setCurrentIndex(index)
            self._move_nav_indicator(index)

        self.btn_home.setChecked(index == 0)
        self.btn_training.setChecked(index == 1)
        self.btn_stats.setChecked(index == 2)
        self.btn_history.setChecked(index == 3)
        self.btn_settings.setChecked(index == 4)

        if current_index == index:
            return

        if getattr(self, "_language_busy", False):
            return

        if not self._animations_enabled:
            return

        page = self.pages.currentWidget()

        effect = QtWidgets.QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)

        animation = QtCore.QPropertyAnimation(
            effect, b"opacity", self
        )
        animation.setDuration(450)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(
            QtCore.QEasingCurve.OutCubic
        )

        self._page_fade_anim = animation
        self._page_fade_widget = page

        def finish_animation():
            if self._page_fade_anim is animation:
                page.setGraphicsEffect(None)
                self._page_fade_anim = None
                self._page_fade_widget = None

        animation.finished.connect(finish_animation)
        animation.start()

    def menu_button(self, text: str, icon_path: str) -> QtWidgets.QPushButton:
        btn = AnimatedMenuButton(text)

        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setIconSize(QtCore.QSize(24, 24))
        btn.setFixedHeight(54)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setCheckable(True)

        return btn

    def _top_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def _top_mouse_move(self, event):
        if event.buttons() & QtCore.Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def _top_mouse_release(self, event):
        self.old_pos = None

    def _on_maint_ok(self, st: dict):
        if st.get("enabled"):
            self._maint_forced = True
            self._sync_timer.stop()
            msg = st.get("message") or "Ведутся технические работы. Доступ временно запрещён."
            _log.warning("Технические работы на сервере: %s", msg)
            RoundedDialog.warning(
                i18n.t("login.maintenance_title"),
                i18n.t("login.server_message") + str(msg) +
                "\n\n" + i18n.t("login.maintenance_text")
            )
            self.pages.setEnabled(False)
            worker = ApiWorker(logout)
            self._maint_logout_worker = worker
            worker.finished.connect(self._finish_maintenance_logout)
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def _finish_maintenance_logout(self):
        if self.on_logout:
            self.on_logout()
        else:
            self.close()

    def _sync_all_data(self):
        if self._sync_in_progress:
            return
        self._sync_in_progress = True

        self._pending_sync_tasks = 4

        def _task_done(*_args):
            self._pending_sync_tasks -= 1
            if self._pending_sync_tasks <= 0:
                self._sync_in_progress = False

        if not self._maint_forced:
            w1 = ApiWorker(get_maintenance_status)
            w1.ok.connect(self._on_maint_ok)
            w1.ok.connect(_task_done)
            w1.fail.connect(lambda err: (_log.debug("Ошибка проверки статуса техработ: %s", err), _task_done()))
            w1.finished.connect(w1.deleteLater)
            w1.start()
            self._maint_worker = w1
        else:
            _task_done()

        w2 = ApiWorker(get_training_history, 2000)
        w2.ok.connect(self.home_screen.apply_stats)
        w2.ok.connect(self.stats_screen.apply_data)
        w2.ok.connect(self.history_screen.apply_data)
        w2.ok.connect(_task_done)
        w2.fail.connect(lambda err: (_log.warning("Ошибка загрузки статистики: %s", err), _task_done()))
        w2.finished.connect(w2.deleteLater)
        w2.start()
        self._stats_worker = w2

        w3 = ApiWorker(get_updates)
        w3.ok.connect(self.home_screen.apply_updates)
        w3.ok.connect(_task_done)
        w3.fail.connect(lambda err: (_log.debug("Ошибка загрузки обновлений: %s", err), _task_done()))
        w3.finished.connect(w3.deleteLater)
        w3.start()
        self._updates_worker = w3

        w4 = ApiWorker(get_profile)
        w4.ok.connect(self._on_profile_loaded)
        w4.ok.connect(_task_done)
        w4.fail.connect(lambda err: (_log.warning("Ошибка загрузки профиля: %s", err), _task_done()))
        w4.finished.connect(w4.deleteLater)
        w4.start()
        self._profile_worker = w4

    def _stats_append(self, rec: dict):
        self._last_debug_data = {
            "user_stage": rec.get("user_stage"),
            "ai_stage": rec.get("ai_stage"),
            "score": rec.get("score"),
            "dice": rec.get("dice"),
            "p_max": rec.get("p_max"),
        }
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        fn = functools.partial(
            save_training_record,
            user_stage=int(rec.get("user_stage", 0)),
            ai_stage=int(rec.get("ai_stage", 0)),
            score=int(rec.get("score", 0)),
            dice=float(rec.get("dice", 0.0)),
            p_max=float(rec.get("p_max", 0.0)),
            ts=ts,
        )
        w = ApiWorker(fn)
        w.ok.connect(self._on_training_save_result)
        w.fail.connect(self._on_training_save_error)
        self._save_record_workers.add(w)
        w.finished.connect(lambda worker=w: self._save_record_workers.discard(worker))
        w.finished.connect(w.deleteLater)
        w.start()

    def _on_training_save_result(self, result):
        if result is True:
            QtCore.QTimer.singleShot(250, self._sync_all_data)
        else:
            self._on_training_save_error("Server rejected training record")

    def _on_training_save_error(self, error):
        _log.warning("Ошибка сохранения записи тренировки: %s", error)
        if self.isVisible() and not self._maint_forced:
            RoundedDialog.warning(
                i18n.t("main_window.save_error_title"),
                i18n.t("main_window.save_error_text")
            )

    def _ver_tuple(self, v: str):
        s = (v or "").strip().lower()
        if s.startswith("v."):
            s = s[2:]
        elif s.startswith("v"):
            s = s[1:]
        nums = []
        for p in s.split("."):
            try:
                nums.append(int(p))
            except (ValueError, TypeError):
                nums.append(0)
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums[:3])

    def _check_update(self):
        w = ApiWorker(get_updates)
        w.ok.connect(self._on_update_check_done)
        w.fail.connect(lambda err: _log.debug("Ошибка проверки обновлений: %s", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._check_update_worker = w

    def _on_update_check_done(self, updates):
        try:
            if not updates:
                return
            latest = max(
                updates,
                key=lambda u: (
                    self._ver_tuple(str(u.get("version") or "")),
                    int(u.get("id") or 0)
                )
            )
            latest_ver = str(latest.get("version", "")).strip()
            if not latest_ver:
                return
            if self._ver_tuple(latest_ver) > self._ver_tuple(current_v):
                _log.info("Доступно обновление: текущая=%s, новая=%s", current_v, latest_ver)
                RoundedDialog.info(
                    i18n.t("main_window.update_available"),
                    i18n.t(
                        "main_window.installed_version",
                        current_v=current_v
                    ) +
                    i18n.t(
                        "main_window.available_version",
                        latest_ver=latest_ver
                    )
                )
        except Exception:
            _log.debug("Ошибка при проверке обновлений", exc_info=True)

    def _on_profile_loaded(self, profile):
        try:
            self._last_profile = profile
            self.home_screen.apply_profile(profile)
            self.settings_screen.apply_profile(profile)
        except Exception:
            _log.error("Ошибка применения профиля к экранам", exc_info=True)

    def _load_dev_mode(self) -> bool:
        try:
            with open(self._dev_mode_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return bool(data.get("enabled", False))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False

    def _save_dev_mode(self, enabled: bool):
        try:
            os.makedirs(os.path.dirname(self._dev_mode_file), exist_ok=True)
            with open(self._dev_mode_file, "w", encoding="utf-8") as f:
                json.dump({"enabled": enabled}, f, ensure_ascii=False)
        except OSError:
            _log.warning("Не удалось сохранить состояние режима разработчика")

    def _reset_logo_clicks(self):
        self._logo_click_count = 0

    def _toggle_dev_mode(self):
        self.dev_mode = not self.dev_mode
        self._save_dev_mode(self.dev_mode)
        self.dev_badge.setVisible(self.dev_mode)
        state_text = "включён" if self.dev_mode else "выключен"
        _log.info("Режим разработчика %s", state_text)
        if not self.dev_mode and self._dev_panel is not None:
            self._dev_panel.hide()

    def _on_dev_badge_click(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._toggle_dev_panel()

    def _toggle_dev_panel(self):
        if not self.dev_mode:
            return
        if self._dev_panel is None:
            self._dev_panel = DevPanelDialog(self, self.username, self._last_debug_data, on_logout=self._do_logout)
        if self._dev_panel.isVisible():
            self._dev_panel.hide()
        else:
            self._dev_panel.refresh(self._last_debug_data)
            self._dev_panel.show()
            self._dev_panel.raise_()
            self._dev_panel.activateWindow()

    def _do_logout(self):
        if self.on_logout:
            self.on_logout()
        else:
            self.close()