from PyQt5 import QtWidgets, QtCore, QtGui


class CheckmarkIcon(QtWidgets.QWidget):
    def __init__(self, color="#1273D1", parent=None):
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()

        pen = QtGui.QPen(self._color)
        pen.setWidthF(2.4)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)

        path = QtGui.QPainterPath()
        path.moveTo(w * 0.20, h * 0.52)
        path.lineTo(w * 0.42, h * 0.74)
        path.lineTo(w * 0.82, h * 0.28)
        painter.drawPath(path)
        painter.end()


class LanguageDialog(QtWidgets.QDialog):
    LANGUAGES = [
        ("ru", "RU", "Русский", "#1273D1"),
        ("en", "EN", "English", "#1273D1"),
        ("zh", "中", "中文", "#1273D1"),
    ]

    UI_TEXT = {
        "ru": {
            "title": "Выберите язык",
            "subtitle": "Choose language · 选择语言",
            "desc": {"ru": "Язык системы", "en": "Английский", "zh": "Китайский"},
            "continue": "Продолжить",
        },
        "en": {
            "title": "Choose language",
            "subtitle": "Выберите язык · 选择语言",
            "desc": {"ru": "Russian", "en": "System language", "zh": "Chinese"},
            "continue": "Continue",
        },
        "zh": {
            "title": "选择语言",
            "subtitle": "Выберите язык · Choose language",
            "desc": {"ru": "俄语", "en": "英语", "zh": "系统语言"},
            "continue": "继续",
        },
    }

    CJK_FONT = "'Microsoft YaHei UI', 'Microsoft YaHei', 'Noto Sans SC', 'PingFang SC'"

    ACCENT = "#1273D1"
    SELECTED_BG = "#F0F7FF"
    HOVER_BG = "#F5F7FA"
    IDLE_BADGE_BG = "#EEF1F5"
    IDLE_BADGE_FG = "#5A6472"

    def __init__(self, parent=None):
        parent = parent or QtWidgets.QApplication.activeWindow()
        super().__init__(parent)
        self._parent_for_center = parent
        self._drag_pos = None

        import i18n
        saved = i18n.get_saved_language()

        self.selected_code = (
            saved if saved in i18n.SUPPORTED_LANGUAGES
            else i18n.DEFAULT_LANGUAGE
        )
        self._ui = self.UI_TEXT[self.selected_code]
        self._row_widgets = {}

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        card = QtWidgets.QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background-color: #ffffff;
                border-radius: 14px;
                border: 1px solid #D7DCE2;
            }
        """)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(45)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QtGui.QColor(20, 30, 45, 55))
        card.setGraphicsEffect(shadow)
        card.mousePressEvent = self._header_mouse_press
        card.mouseMoveEvent = self._header_mouse_move
        card.mouseReleaseEvent = self._header_mouse_release

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(card)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QtWidgets.QVBoxLayout()
        head.setContentsMargins(26, 16, 26, 18)
        head.setSpacing(0)

        title = QtWidgets.QLabel(self._ui["title"])
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 20px; font-weight: 650; color: #1C2430;"
                            "background: transparent; border: none;")
        head.addWidget(title)

        subtitle = QtWidgets.QLabel(self._ui["subtitle"])
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 15px; font-weight: 600; color: #6B7683;"
                               "background: transparent; border: none; font-weight: normal;")
        head.addWidget(subtitle)
        layout.addLayout(head)

        rows = QtWidgets.QVBoxLayout()
        rows.setContentsMargins(14, 0, 14, 8)
        rows.setSpacing(2)
        for code, badge, name, color in self.LANGUAGES:
            desc = self._ui["desc"][code]
            rows.addWidget(self._build_row(code, badge, name, desc, color))
        layout.addLayout(rows)

        layout.addSpacing(8)

        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #ECEFF3; border: none;")
        layout.addWidget(line)

        footer = QtWidgets.QHBoxLayout()
        footer.setContentsMargins(26, 10, 26, 10)
        footer.addStretch(1)
        self.continue_btn = QtWidgets.QPushButton(self._ui["continue"])
        self.continue_btn.setFixedHeight(40)
        self.continue_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #1273D1;
                color: white;
                border: none;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 20px;
            }
            QPushButton:hover { background-color: #0F65B8; }
            QPushButton:pressed { background-color: #0D5AA4; }
        """)
        self.continue_btn.clicked.connect(self.accept)
        footer.addWidget(self.continue_btn)
        layout.addLayout(footer)

        self._highlight_selected()

        self.setFixedWidth(460)
        self.adjustSize()
        QtCore.QTimer.singleShot(0, self._center_on_parent)

        # --- fade-in при появлении окна ---
        self.setWindowOpacity(0)

        self._fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(450)
        self._fade_anim.setStartValue(0)
        self._fade_anim.setEndValue(1)

    def showEvent(self, event):
        super().showEvent(event)
        if self._fade_anim.state() != QtCore.QPropertyAnimation.Running:
            self._fade_anim.start()

    def _build_row(self, code, badge, name, desc, color) -> QtWidgets.QWidget:
        row = QtWidgets.QPushButton()
        row.setCursor(QtCore.Qt.PointingHandCursor)
        row.setFixedHeight(58)
        row.setObjectName(f"row_{code}")

        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(14)

        badge_lbl = QtWidgets.QLabel(badge)
        badge_lbl.setFixedSize(40, 32)
        badge_lbl.setAlignment(QtCore.Qt.AlignCenter)
        badge_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        h.addWidget(badge_lbl)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(2)

        is_cjk = code == "zh"
        cjk_font = self.CJK_FONT if is_cjk else "'Segoe UI'"

        name_lbl = QtWidgets.QLabel(name)
        name_lbl.setStyleSheet(
            f"font-size: {16 if is_cjk else 14}px; font-weight: 700; color: #1C2430;"
            f"font-family: {cjk_font};"
            "background: transparent; border: none;"
        )
        name_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        desc_lbl = QtWidgets.QLabel(desc)
        desc_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 400; color: #8B95A1;"
            f"font-family: {self.CJK_FONT};"
            "background: transparent; border: none;"
        )
        desc_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        text_col.addWidget(name_lbl)
        text_col.addWidget(desc_lbl)
        h.addLayout(text_col)

        h.addStretch(1)

        check = CheckmarkIcon(self.ACCENT)
        check.setFixedSize(20, 20)
        check.setVisible(code == self.selected_code)
        h.addWidget(check)

        row.clicked.connect(lambda _, c=code: self._select(c))
        self._row_widgets[code] = (row, badge_lbl, check, color)
        return row

    def _select(self, code: str):
        self.selected_code = code
        self._highlight_selected()

    def _highlight_selected(self):
        for code, (row, badge_lbl, check, color) in self._row_widgets.items():
            is_sel = code == self.selected_code
            check.setVisible(is_sel)

            row.setStyleSheet(f"""
                QPushButton#row_{code} {{
                    background-color: {self.SELECTED_BG if is_sel else "transparent"};
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                }}
                QPushButton#row_{code}:hover {{
                    background-color: {self.SELECTED_BG if is_sel else self.HOVER_BG};
                }}
            """)

            is_cjk = code == "zh"
            badge_font = self.CJK_FONT if is_cjk else "'Segoe UI'"
            badge_lbl.setStyleSheet(f"""
                background-color: {color if is_sel else self.IDLE_BADGE_BG};
                color: {"#ffffff" if is_sel else self.IDLE_BADGE_FG};
                border-radius: 7px;
                font-size: {15 if is_cjk else 13}px;
                font-weight: 800;
                font-family: {badge_font};
            """)

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
    def ask_language(parent=None) -> str:
        dlg = LanguageDialog(parent)
        dlg.exec_()
        return dlg.selected_code