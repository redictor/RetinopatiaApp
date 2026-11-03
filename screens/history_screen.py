import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from dialogs.ui_dialogs import RoundedDialog
import i18n

class HistoryScreen(QtWidgets.QWidget):
    STAGES = [
        "0 стадия - Нет ретинопатии",
        "1 стадия - Начальная",
        "2 стадия - Умеренная",
        "3 стадия - Тяжёлая",
        "4 стадия - Пролиферативная",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards_layout = None
        self._cached_history = None
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        title = QtWidgets.QLabel(i18n.t("history.title"))
        title.setStyleSheet("font-size:24px;font-weight:900;color:#202020;")
        root.addWidget(title)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 0px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #cfd8e3;
                border-radius: 4px;
                min-height: 36px;
            }

            QScrollBar::handle:vertical:hover {
                background: #b8c4d3;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: transparent;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
            }
        """)

        inner = QtWidgets.QWidget()
        self.cards_layout = QtWidgets.QVBoxLayout(inner)
        self.cards_layout.setContentsMargins(0, 0, 8, 0)
        self.cards_layout.setSpacing(12)

        scroll.setWidget(inner)
        self.scroll = scroll

        self.scroll_anim = QtCore.QPropertyAnimation(
            scroll.verticalScrollBar(),
            b"value",
            self
        )

        self.scroll_anim.setDuration(300)
        self.scroll_anim.setEasingCurve(
            QtCore.QEasingCurve.OutQuart
        )

        scroll.viewport().installEventFilter(self)

        scroll.verticalScrollBar().setSingleStep(4)
        scroll.verticalScrollBar().setPageStep(60)

        root.addWidget(scroll, 1)

    def apply_data(self, data):
        self._cached_history = list(data or [])
        self._clear()

        data = list(data or [])
        data.sort(key=lambda x: int(x.get("training_number", 0) or 0), reverse=True)

        if not data:
            empty_box = QtWidgets.QFrame()
            empty_box.setStyleSheet("""
                QFrame {
                    background: #ffffff;
                    border: 1px solid #e6eaf0;
                    border-radius: 14px;
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)

            eb = QtWidgets.QVBoxLayout(empty_box)
            eb.setContentsMargins(20, 40, 20, 40)

            empty = QtWidgets.QLabel(i18n.t("history.no_data"))
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setStyleSheet("font-size:16px;color:#777;font-weight:800;")

            eb.addWidget(empty)

            self.cards_layout.addWidget(empty_box)
            self.cards_layout.addStretch(1)
            return

        for item in data:
            self.cards_layout.addWidget(self._card(item))

        self.cards_layout.addStretch(1)

    def _animate_history_card(self, card, delay=0):
        effect = QtWidgets.QGraphicsOpacityEffect(card)
        effect.setOpacity(0.0)
        card.setGraphicsEffect(effect)

        animation = QtCore.QPropertyAnimation(
            effect, b"opacity", self
        )
        animation.setDuration(480)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(
            QtCore.QEasingCurve.InOutSine
        )

        self._card_animations.append(animation)
        generation = self._history_anim_generation

        def start_animation():
            if generation != self._history_anim_generation:
                return
            animation.start()

        def finish_animation():
            if generation != self._history_anim_generation:
                return

            card.setGraphicsEffect(None)

            if animation in self._card_animations:
                self._card_animations.remove(animation)

        animation.finished.connect(finish_animation)
        QtCore.QTimer.singleShot(delay, start_animation)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Wheel:
            bar = self.scroll.verticalScrollBar()

            current = bar.value()

            delta = event.angleDelta().y()

            target = current - delta

            target = max(
                bar.minimum(),
                min(bar.maximum(), target)
            )

            self.scroll_anim.stop()
            self.scroll_anim.setStartValue(current)
            self.scroll_anim.setEndValue(target)
            self.scroll_anim.start()

            return True

        return super().eventFilter(obj, event)

    def _clear(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _card(self, item):
        training_id = item.get("training_number", "-")
        try:
            score_letter = self._score_letter(float(item.get("score", 0)))
        except (TypeError, ValueError):
            score_letter = "-"
        correct_stage = self._stage(item.get("ai_stage"))
        date = self._date(item.get("ts"))

        card = QtWidgets.QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e6eaf0;
                border-radius: 14px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(18)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(4)

        title = QtWidgets.QLabel(
            i18n.t("history.training_number", training_id=training_id)
        )
        title.setStyleSheet("font-size: 15px; font-weight: 900; color: #111827;")

        date_label = QtWidgets.QLabel(date)
        date_label.setStyleSheet("font-size: 12px; color: #6b7280;")

        left.addWidget(title)
        left.addWidget(date_label)
        layout.addLayout(left, 2)

        self._grade_badge(layout, i18n.t("history.result"), score_letter)
        self._info(layout, i18n.t("history.final_stage"), correct_stage)

        return card
    
    def _show_comment(self, comment):
        comment = str(comment or "").strip()
        if not comment:
            return

        RoundedDialog.info(
            i18n.t("history.teacher_comment"),
            comment
        )

    def _info(self, layout, title, value, big=False):
        box = QtWidgets.QVBoxLayout()
        box.setSpacing(3)

        t = QtWidgets.QLabel(title)
        t.setStyleSheet("font-size: 11px; font-weight: 800; color: #8a94a6;")

        v = QtWidgets.QLabel(str(value))
        v.setWordWrap(True)

        if big:
            v.setStyleSheet("font-size: 22px; font-weight: 900; color: #0078D7;")
        else:
            v.setStyleSheet("font-size: 13px; font-weight: 800; color: #1f2937;")

        box.addWidget(t)
        box.addWidget(v)

        layout.addLayout(box, 1)

    def _grade_badge(self, layout, title, letter):
        box = QtWidgets.QVBoxLayout()
        box.setSpacing(3)

        t = QtWidgets.QLabel(title)
        t.setStyleSheet("font-size: 11px; font-weight: 800; color: #8a94a6;")

        color = self._letter_color(letter)

        badge = QtWidgets.QLabel(letter)
        badge.setFixedSize(40, 40)
        badge.setAlignment(QtCore.Qt.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 900;
                color: {color};
                border: 3px solid {color};
                border-radius: 20px;
                background: transparent;
            }}
        """)

        box.addWidget(t)
        box.addWidget(badge, 0, QtCore.Qt.AlignLeft)

        layout.addLayout(box, 1)

    def _score_letter(self, score):
        letters = {1: "F", 2: "D", 3: "C", 4: "B", 5: "A"}
        try:
            s = round(float(score))
        except (TypeError, ValueError):
            s = 1
        s = max(1, min(5, s))
        return letters[s]

    def _letter_color(self, letter):
        return {
            "A": "#1e9e4f",
            "B": "#5bab2f",
            "C": "#d9a400",
            "D": "#e07b00",
            "E": "#e0521f",
            "F": "#d92b2b",
        }.get(letter, "#777777")

    def _stage(self, value):
        try:
            stage = int(value)
            if 0 <= stage <= 4:
                return i18n.t(f"stages.{stage}")
        except (ValueError, TypeError):
            pass

        return "-"

    def _date(self, value):
        if not value:
            return i18n.t("history.unknown_date")

        try:
            dt = datetime.datetime.fromisoformat(str(value).replace("Z", "").replace("T", " "))
            return dt.strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError):
            return i18n.t("history.unknown_date")