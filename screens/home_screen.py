import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from dialogs.ui_dialogs import ApiWorker
from api_client import get_updates
import app_logger
import i18n

_log = app_logger.get("screens.home")

class HomeScreen(QtWidgets.QWidget):
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self._updates_layout = None
        self._updates_worker = None
        self._cached_stats = None
        self._cached_updates = None
        self._build()

    def _ru_plural(self, n: int, one: str, few: str, many: str) -> str:
        n = abs(int(n))
        if 11 <= (n % 100) <= 14:
            return many
        if n % 10 == 1:
            return one
        if 2 <= (n % 10) <= 4:
            return few
        return many

    def _home_greeting(self, name: str) -> str:
        hour = datetime.datetime.now().hour

        if 5 <= hour < 12:
            key = "home.greeting_morning"
        elif 12 <= hour < 18:
            key = "home.greeting_day"
        elif 18 <= hour < 23:
            key = "home.greeting_evening"
        else:
            key = "home.greeting_night"

        return f"{i18n.t(key)}, {name}!"

    def _format_ago(self, ts_iso: str) -> str:
        if not ts_iso or ts_iso == "-":
            return "-"

        try:
            s = str(ts_iso).replace("Z", "").replace(" ", "T")
            dt = datetime.datetime.fromisoformat(s)
            now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
            seconds = max(0, int((now - dt).total_seconds()))
        except (ValueError, TypeError):
            return "-"

        minutes = seconds // 60

        if minutes < 60:
            n = max(1, minutes)
            return i18n.t("home.minutes_ago", minutes=n)

        hours = minutes // 60

        if hours < 24:
            return i18n.t("home.hours_ago", hours=hours)

        return i18n.t("home.days_ago", days=hours // 24)

    def _build(self):
        self.setStyleSheet("QLabel { border: none; background: transparent; }")
        l = QtWidgets.QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(16)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(12)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(4)

        self.home_title_label = QtWidgets.QLabel(self._home_greeting(self.username))
        self.home_title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #222;")
        left.addWidget(self.home_title_label)

        subtitle = QtWidgets.QLabel(i18n.t("home.subtitle"))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #555;")
        left.addWidget(subtitle)
        top.addLayout(left, 1)

        avatar = QtWidgets.QLabel()
        avatar.setFixedSize(56, 56)
        pixmap = QtGui.QPixmap("assets/icons/avatar.png")
        if pixmap.isNull():
            avatar.setStyleSheet("""
                QLabel {
                    background-color: #f0f0f0;
                    border: 2px solid #d6d6d6;
                    border-radius: 28px;
                }
            """)
        else:
            pixmap = pixmap.scaled(56, 56, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
            avatar.setPixmap(pixmap)
        avatar.setAlignment(QtCore.Qt.AlignCenter)
        top.addWidget(avatar)

        l.addLayout(top)

        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(14)

        def stat_card(title_text, value_text, hint_text):
            c = QtWidgets.QFrame()
            c.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 16px;
            }
            QLabel { border: none; background: transparent; }
            """)
            cl = QtWidgets.QVBoxLayout(c)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(6)

            t = QtWidgets.QLabel(title_text)
            t.setStyleSheet("font-size:12px;color:#777;font-weight:700;border:none;background:transparent;padding:0;margin:0;")

            v = QtWidgets.QLabel(value_text)
            v.setStyleSheet("font-size:20px;color:#222;font-weight:900;border:none;background:transparent;padding:0;margin:0;")

            h = QtWidgets.QLabel(hint_text)
            h.setWordWrap(True)
            h.setStyleSheet("font-size:11px;color:#888;border:none;background:transparent;padding:0;margin:0;")

            cl.addWidget(t)
            cl.addWidget(v)
            cl.addWidget(h)
            return c, v

        c1, self.home_last_activity_lbl = stat_card(
            i18n.t("home.last_activity"), "-", i18n.t("home.last_training_date")
        )
        c2, self.home_eff_lbl = stat_card(
            i18n.t("home.efficiency"), "-%", i18n.t("home.avg_accuracy")
        )
        c3, self.home_total_lbl = stat_card(
            i18n.t("home.trainings_done"), "-", i18n.t("home.tasks_solved")
        )

        cards.addWidget(c1)
        cards.addWidget(c2)
        cards.addWidget(c3)
        l.addLayout(cards)

        actions_title = QtWidgets.QLabel(i18n.t("home.quick_actions"))
        actions_title.setStyleSheet("font-size:14px;font-weight:800;color:#222;border:none;background:transparent;")
        l.addWidget(actions_title)

        actions_box = QtWidgets.QFrame()
        actions_box.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 16px; }
        """)

        ab = QtWidgets.QHBoxLayout(actions_box)
        ab.setContentsMargins(14, 14, 14, 14)
        ab.setSpacing(10)

        def big_action(text, icon_path, primary=False):
            btn = QtWidgets.QPushButton(text)
            btn.setIcon(QtGui.QIcon(icon_path))
            btn.setIconSize(QtCore.QSize(18, 18))
            btn.setFixedHeight(44)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#0078D7' if primary else '#f3f3f3'};
                    color: {'white' if primary else '#222'};
                    border: none;
                    border-radius: 12px;
                    font-size: 14px;
                    font-weight: 800;
                    padding: 0 14px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {'#005499' if primary else '#e7e7e7'};
                }}
            """)
            return btn

        self.btn_start_training = big_action(i18n.t("home.start_training"), "assets/icons/training.png", primary=True)
        self.btn_open_stats = big_action(i18n.t("home.open_stats"), "assets/icons/stats.png", primary=False)
        self.btn_open_history = big_action(i18n.t("home.open_history"), "assets/icons/history.png", primary=False)
        self.btn_open_settings = big_action(i18n.t("home.settings"), "assets/icons/settings.png", primary=False)

        ab.addWidget(self.btn_start_training)
        ab.addWidget(self.btn_open_stats)
        ab.addWidget(self.btn_open_history)
        ab.addWidget(self.btn_open_settings)

        l.addWidget(actions_box)

        updates_frame = QtWidgets.QFrame()
        updates_frame.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 16px; }
        """)

        ul = QtWidgets.QVBoxLayout(updates_frame)
        ul.setContentsMargins(16, 14, 16, 14)
        ul.setSpacing(10)

        updates_title = QtWidgets.QLabel(i18n.t("home.updates_list"))
        updates_title.setStyleSheet("font-size:14px;font-weight:800;color:#222;border:none;background:transparent;")
        ul.addWidget(updates_title)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical { width: 10px; background: transparent; }
            QScrollBar::handle:vertical { background: #d7d7d7; border-radius: 5px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        inner = QtWidgets.QWidget()
        il = QtWidgets.QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(4)
        self._updates_layout = il

        loading = QtWidgets.QLabel(i18n.t("home.loading_updates"))
        loading.setStyleSheet("QLabel { font-size: 12px; color: #777; padding: 10px; }")
        il.addWidget(loading)

        il.addStretch(1)
        scroll.setWidget(inner)

        self.updates_scroll = scroll

        self.updates_scroll_anim = QtCore.QPropertyAnimation(
            scroll.verticalScrollBar(),
            b"value",
            self
        )
        self.updates_scroll_anim.setDuration(580)
        self.updates_scroll_anim.setEasingCurve(QtCore.QEasingCurve.OutQuart)

        scroll.viewport().installEventFilter(self)

        ul.addWidget(scroll, 1)
        l.addWidget(updates_frame, 1)

    def eventFilter(self, obj, event):
        if obj == self.updates_scroll.viewport() and event.type() == QtCore.QEvent.Wheel:
            bar = self.updates_scroll.verticalScrollBar()

            current = bar.value()
            delta = event.angleDelta().y()

            target = current - delta
            target = max(bar.minimum(), min(bar.maximum(), target))

            self.updates_scroll_anim.stop()
            self.updates_scroll_anim.setStartValue(current)
            self.updates_scroll_anim.setEndValue(target)
            self.updates_scroll_anim.start()

            return True

        return super().eventFilter(obj, event)

    def apply_stats(self, data):
        self._cached_stats = list(data or [])
        try:
            data = data or []
            total = len(data)

            if total == 0:
                self.home_last_activity_lbl.setText("-")
                self.home_eff_lbl.setText("-%")
                self.home_total_lbl.setText("0")
                return

            last_time = "-"
            for item in reversed(data):
                ts = item.get("created_at") or item.get("date") or item.get("ts")
                if ts:
                    last_time = ts
                    break

            scores = []
            for item in data:
                try:
                    scores.append(float(item.get("score", 0)))
                except (ValueError, TypeError):
                    pass

            avg_score = sum(scores) / len(scores) if scores else 0.0
            eff = int(round(avg_score / 5 * 100)) if scores else 0
            eff_letter = self._eff_letter(eff) if scores else "-"

            self.home_last_activity_lbl.setText(self._format_ago(last_time) if last_time != "-" else "-")
            self.home_eff_lbl.setText(eff_letter)
            self.home_total_lbl.setText(str(total))
        except Exception:
            _log.error("Ошибка применения статистики на главный экран", exc_info=True)

    def _eff_letter(self, pct):
        if pct >= 90:
            return "A"
        if pct >= 80:
            return "B"
        if pct >= 70:
            return "C"
        if pct >= 60:
            return "D"
        if pct >= 50:
            return "E"
        return "F"

    def apply_updates(self, updates):
        self._cached_updates = list(updates or [])
        if self._updates_layout is None:
            return

        import re

        def update_sort_key(upd):
            version = str(upd.get("version") or "")
            numbers = [int(n) for n in re.findall(r"\d+", version)]
            numbers = (numbers + [0, 0, 0])[:3]

            try:
                update_id = int(upd.get("id") or 0)
            except (TypeError, ValueError):
                update_id = 0

            return (*numbers, update_id)

        updates = sorted(
            updates or [],
            key=update_sort_key,
            reverse=True
        )

        while self._updates_layout.count():
            item = self._updates_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not updates:
            empty = QtWidgets.QLabel(i18n.t("home.no_updates"))
            empty.setStyleSheet("QLabel { font-size: 12px; color: #777; padding: 10px; }")
            self._updates_layout.addWidget(empty)
            self._updates_layout.addStretch(1)
            return

        for i, upd in enumerate(updates):
            version = str(upd.get("version", "-"))
            language = i18n.get_current_language()
            text = str(
                upd.get(f"description_{language}")
                or upd.get(f"body_{language}")
                or upd.get(f"text_{language}")
                or upd.get("description")
                or upd.get("body")
                or upd.get("text")
                or ""
            )

            card = QtWidgets.QFrame()
            card.setStyleSheet("""
                QFrame { background: #f8f8f8; border: 1px solid #e6e6e6; border-radius: 12px; }
            """)

            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)

            top_row = QtWidgets.QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(8)

            t1 = QtWidgets.QLabel(version)
            t1.setStyleSheet("QLabel { font-size: 12px; font-weight: 800; color: #222; border: none; }")
            top_row.addWidget(t1)
            top_row.addStretch(1)

            if i == 0:
                badge = QtWidgets.QLabel(i18n.t("home.new_badge"))
                badge.setAlignment(QtCore.Qt.AlignCenter)
                badge.setStyleSheet("""
                    QLabel {
                        background: #fff7d6; color: #9a6a00;
                        border: 1px solid #f2d27a; border-radius: 9px;
                        font-size: 10px; font-weight: 900; padding: 3px 8px;
                    }
                """)
                top_row.addWidget(badge)

            cl.addLayout(top_row)

            t2 = QtWidgets.QLabel(text)
            t2.setWordWrap(True)
            t2.setStyleSheet("QLabel { font-size: 11px; color: #666; border: none; }")
            cl.addWidget(t2)

            self._updates_layout.addWidget(card)

        self._updates_layout.addStretch(1)

    def apply_profile(self, profile):
        try:
            profile = profile or {}
            display_name = profile.get("display_name") or self.username
            self.home_title_label.setText(self._home_greeting(display_name))
        except Exception:
            _log.error("Ошибка применения профиля на главный экран", exc_info=True)
