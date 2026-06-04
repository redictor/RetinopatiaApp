import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from ui_dialogs import RoundedDialog

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
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        title = QtWidgets.QLabel("История тренировок")
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

            empty = QtWidgets.QLabel("Нет данных об истории тренировок")
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setStyleSheet("font-size:16px;color:#777;font-weight:800;")

            eb.addWidget(empty)

            self.cards_layout.addWidget(empty_box)
            self.cards_layout.addStretch(1)
            return

        for item in data:
            self.cards_layout.addWidget(self._card(item))

        self.cards_layout.addStretch(1)

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
        training_id = item.get("training_number", "—")
        score = item.get("score", "—")
        correct_stage = self._stage(item.get("ai_stage"))
        teacher_comment = (
            item.get("teacher_comment")
            or item.get("comment")
            or f"Тестовый комментарий к тренировке №{training_id}."
        )
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

        title = QtWidgets.QLabel(f"Тренировка №{training_id}")
        title.setStyleSheet("font-size: 15px; font-weight: 900; color: #111827;")

        date_label = QtWidgets.QLabel(date)
        date_label.setStyleSheet("font-size: 12px; color: #6b7280;")

        left.addWidget(title)
        left.addWidget(date_label)

        layout.addLayout(left, 2)

        self._info(layout, "Результат", f"{score}/5", big=True)
        self._info(layout, "Верная стадия", correct_stage)

        info_btn = QtWidgets.QPushButton()
        info_btn.setIcon(QtGui.QIcon("assets/icons/info.png"))
        info_btn.setIconSize(QtCore.QSize(20, 20))
        info_btn.setFixedSize(38, 38)
        info_btn.setCursor(QtCore.Qt.PointingHandCursor)
        info_btn.setEnabled(bool(teacher_comment.strip()))
        info_btn.setStyleSheet("""
            QPushButton {
                background: #eef6ff;
                border: 1px solid #cfe6ff;
                border-radius: 19px;
            }
            QPushButton:hover {
                background: #dff0ff;
                border: 1px solid #9dd0ff;
            }
            QPushButton:disabled {
                background: #f3f4f6;
                border: 1px solid #e5e7eb;
            }
        """)
        info_btn.clicked.connect(lambda: self._show_comment(teacher_comment))
        layout.addWidget(info_btn)

        return card
    
    def _show_comment(self, comment):
        comment = str(comment or "").strip()
        if not comment:
            return

        RoundedDialog.info(
            "Комментарий учителя",
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

    def _stage(self, value):
        try:
            return self.STAGES[int(value)]
        except Exception:
            return "—"

    def _date(self, value):
        if not value:
            return "Дата неизвестна"

        try:
            dt = datetime.datetime.fromisoformat(str(value).replace("Z", "").replace("T", " "))
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return str(value).replace("T", " ")