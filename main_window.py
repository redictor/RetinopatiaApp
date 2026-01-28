import os
import sys
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
from PyQt5 import QtWidgets, QtCore, QtGui
from api_client import delete_user_soft, logout, get_maintenance_status, get_updates, save_training_record, get_training_history, reset_training_history
from ui_dialogs import DeleteAccountDialog, RoundedDialog
import numpy as np
import datetime
import cv2

class LineChartWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = []
        self._target_level = None
        self._best_values = []

    def set_series(self, values, best_values):
        self._values = list(values or [])
        self._best_values = list(best_values or [])
        self.update()
        
    def set_target_level(self, level):
        self._target_level = level
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # фон
        p.fillRect(self.rect(), QtGui.QColor("#ffffff"))

        # рабочая область (оставляем место слева под цифры 1..5)
        r = self.rect().adjusted(48, 14, -14, -20)

        # если данных мало
        if len(self._values) < 2:
            p.setPen(QtGui.QPen(QtGui.QColor("#888"), 1))
            p.drawText(r, QtCore.Qt.AlignCenter, "Недостаточно данных для графика")
            return

        vals = self._values
        best = self._best_values if len(self._best_values) == len(vals) else None

        # фикс шкала 1..5
        vmin, vmax = 1.0, 5.0

        def y_for(v: float) -> float:
            v = max(vmin, min(vmax, float(v)))
            return r.bottom() - ((v - vmin) / (vmax - vmin)) * r.height()

        def x_for(i: int) -> float:
            return r.left() + (i / (len(vals) - 1)) * r.width()

        # сетка 5 линий (1..5)
        grid_pen = QtGui.QPen(QtGui.QColor("#e9e9e9"), 1)
        p.setPen(grid_pen)
        for level in range(1, 6):
            y = y_for(level)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))

        # подписи 1..5 слева
        p.setPen(QtGui.QPen(QtGui.QColor("#777"), 1))
        for level in range(1, 6):
            y = y_for(level)
            p.drawText(int(r.left()) - 26, int(y) + 5, str(level))

        # сглаженный путь (плавные углы) через quadTo
        def smooth_path(series):
            pts = [QtCore.QPointF(x_for(i), y_for(v)) for i, v in enumerate(series)]
            path = QtGui.QPainterPath(pts[0])

            for i in range(1, len(pts) - 1):
                mid = QtCore.QPointF(
                    (pts[i].x() + pts[i + 1].x()) / 2.0,
                    (pts[i].y() + pts[i + 1].y()) / 2.0,
                )
                path.quadTo(pts[i], mid)

            path.quadTo(pts[-2], pts[-1])
            return path

        # основная линия (score)
        p.setPen(QtGui.QPen(QtGui.QColor("#0078D7"), 2))
        p.drawPath(smooth_path(vals))

        if self._target_level is not None:
            lvl = max(1, min(5, int(self._target_level)))
            y = y_for(lvl)
            pen2 = QtGui.QPen(QtGui.QColor("#00A65A"), 2)
            pen2.setStyle(QtCore.Qt.DashLine)
            p.setPen(pen2)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))

class MainWindow(QtWidgets.QWidget):
    def __init__(self, username: str, on_logout):
        super().__init__()
        self._account_verified = True
        self.username = username
        self.on_logout = on_logout

        self.old_pos = None

        self.setWindowTitle("RetinopatiaApp")
        self.setFixedSize(1200, 760)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self._build_ui()

        self._maint_forced = False
        self._maint_timer = QtCore.QTimer(self)
        self._maint_timer.timeout.connect(self._check_maintenance)
        self._maint_timer.start(15000)

        self._stats_timer = QtCore.QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats_and_home)
        self._stats_timer.start(20000)  # 20 секунд

        self._account_status = {"is_verified": False, "email": None}
    
    def _format_ago(self, ts_iso: str) -> str:
        if not ts_iso or ts_iso == "—":
            return "—"
        try:
            # ts приходит типа 2026-01-18T12:34:56
            dt = datetime.datetime.fromisoformat(ts_iso.replace("Z", ""))
        except Exception:
            return ts_iso  # если формат странный — покажем как есть

        now = datetime.datetime.now()
        diff = now - dt
        sec = int(diff.total_seconds())
        if sec < 0:
            sec = 0

        if sec < 20:
            return "только что"
        if sec < 60:
            return f"{sec} сек назад"

        mins = sec // 60
        if mins < 60:
            return f"{mins} мин назад"

        hours = mins // 60
        if hours < 24:
            return f"{hours} час{'а' if 2 <= hours % 10 <= 4 and not (12 <= hours <= 14) else ''} назад"

        days = hours // 24
        if days < 30:
            return f"{days} дн{'я' if days % 10 in (2,3,4) and not (12 <= days <= 14) else 'ей'} назад"

        months = days // 30
        if months < 12:
            return f"{months} мес назад"

        years = months // 12
        return f"{years} г назад"

    def _refresh_stats_and_home(self):
        # 1) грузим историю с сервера
        try:
            data = self._stats_load()
        except Exception:
            data = []

        total = len(data)
        if total:
            avg_score = sum(d.get("score", 0) for d in data) / total
            avg_dice = sum(float(d.get("dice", 0.0)) for d in data) / total

            # "эффективность" — по сути средняя оценка в %
            eff = (avg_score / 5.0) * 100.0

            last_ts = data[-1].get("ts", "—")
        else:
            avg_score = 0.0
            avg_dice = 0.0
            eff = 0.0
            last_ts = "—"
        
        if hasattr(self, "stats_chart"):
            tail = data[-50:]
            scores = [float(d.get("score", 0)) for d in tail]

            # синяя линия
            self.stats_chart.set_series(scores, [])  # или просто set_series(scores, None) если у тебя так

            # зелёная цель = округлённая средняя (1..5)
            if scores:
                avg = sum(scores) / len(scores)
                target = int(round(avg))
                target = max(1, min(5, target))
                self.stats_chart.set_target_level(target)
            else:
                self.stats_chart.set_target_level(None)

        # 2) обновляем главную (если лейблы уже созданы)
        if hasattr(self, "home_total_lbl"):
            self.home_total_lbl.setText(str(total) if total else "—")
        if hasattr(self, "home_eff_lbl"):
            self.home_eff_lbl.setText(f"{eff:.0f}%" if total else "—%")
        if not data:
            last_ts_raw = None
        else:
            last_ts_raw = data[-1].get("ts")
        last_ts = self._format_ago(last_ts_raw)
        if hasattr(self, "home_last_activity_lbl"):
            self.home_last_activity_lbl.setText(last_ts if total else "—")

        # 3) обновляем страницу статистики (если создали лейблы/таблицу)
        if hasattr(self, "stats_total_lbl"):
            self.stats_total_lbl.setText(str(total) if total else "0")
        if hasattr(self, "stats_avg_score_lbl"):
            self.stats_avg_score_lbl.setText(f"{avg_score:.2f}/5" if total else "—/5")
        if hasattr(self, "stats_avg_dice_lbl"):
            self.stats_avg_dice_lbl.setText(f"{avg_dice:.2f}" if total else "—")

        if hasattr(self, "stats_table"):
            tail = data[-50:]
            self.stats_table.setRowCount(len(tail))
            for r, d in enumerate(tail):
                ts = d.get("ts", "—")
                us = int(d.get("user_stage", 0))
                ai = int(d.get("ai_stage", 0))
                sc = int(d.get("score", 0))
                dc = float(d.get("dice", 0.0))
                pm = float(d.get("p_max", 0.0))

                self.stats_table.setItem(r, 0, QtWidgets.QTableWidgetItem(ts))
                self.stats_table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(us)))
                self.stats_table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(ai)))
                self.stats_table.setItem(r, 3, QtWidgets.QTableWidgetItem(f"{sc}/5"))
                self.stats_table.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{dc:.2f}"))
                self.stats_table.setItem(r, 5, QtWidgets.QTableWidgetItem(f"{pm:.2f}"))

    def _check_maintenance(self):
        # мониторим только в главном окне
        if self._maint_forced:
            return

        try:
            st = get_maintenance_status()
            if st.get("enabled"):
                self._maint_forced = True
                self._maint_timer.stop()

                msg = st.get("message") or "Ведутся технические работы. Доступ временно запрещён."

                # ВАЖНО: после закрытия диалога (ОК или крестик) выкидываем на авторизацию
                RoundedDialog.warning(
                    "Технические работы",
                    "Сообщение от сервера: " + msg + "\n\nСейчас в приложении ведутся технические работы. В этот момент просмотр контента приложения, его использование или любые другие действия в нём недоступны. Приносим свои извенения, за доставленные неудобства!"
                )

                try:
                    logout()
                except Exception:
                    pass

                self.close()
                if self.on_logout:
                    self.on_logout()

        except Exception:
            # если сервер недоступен — можешь ничего не делать
            pass

    def _build_ui(self):
        wrapper = QtWidgets.QWidget(self)
        wrapper.setGeometry(0, 0, 1200, 760)
        wrapper.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 20px;
            }
        """)

        root = QtWidgets.QVBoxLayout(wrapper)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("""
            QLabel {
                color: #222;
                font-size: 18px;
                font-weight: 600;
            }
        """)
        app_label.mousePressEvent = self._top_mouse_press
        app_label.mouseMoveEvent = self._top_mouse_move
        app_label.mouseReleaseEvent = self._top_mouse_release

        drag_area = QtWidgets.QWidget()
        drag_area.setFixedHeight(36)
        drag_area.setStyleSheet("background: transparent;")
        drag_area.mousePressEvent = self._top_mouse_press
        drag_area.mouseMoveEvent = self._top_mouse_move
        drag_area.mouseReleaseEvent = self._top_mouse_release

        minimize_button = QtWidgets.QPushButton("─")
        minimize_button.setFixedSize(30, 30)
        minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #FFA500;
                border: none;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #FF8C00; }
        """)
        minimize_button.clicked.connect(self.showMinimized)

        close_button = QtWidgets.QPushButton("✕")
        close_button.setFixedSize(30, 30)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                border: none;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #CC0000; }
        """)
        close_button.clicked.connect(self.close)

        top.addWidget(app_label)
        top.addStretch(1)
        top.addWidget(drag_area, 1)
        top.addWidget(minimize_button)
        top.addWidget(close_button)

        root.addLayout(top)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)

        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 16px;
            }
        """)

        side_layout = QtWidgets.QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)

        side_layout.addSpacing(6)

        self.btn_home = self.menu_button("Главная", "assets/icons/home.png")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self.set_page(0))
        side_layout.addWidget(self.btn_home)

        self.btn_training = self.menu_button("Обучение", "assets/icons/training.png")
        self.btn_training.clicked.connect(lambda: self.set_page(1))
        side_layout.addWidget(self.btn_training)

        self.btn_stats = self.menu_button("Статистика", "assets/icons/stats.png")
        self.btn_stats.clicked.connect(lambda: self.set_page(2))
        side_layout.addWidget(self.btn_stats)


        side_layout.addStretch(1)

        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e6e6e6;")
        side_layout.addWidget(line)

        self.btn_settings = self.menu_button("Настройки", "assets/icons/settings.png")
        self.btn_settings.setChecked(False)
        self.btn_settings.clicked.connect(lambda: self.set_page(3))
        side_layout.addWidget(self.btn_settings)

        content = QtWidgets.QFrame()
        content.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 16px;
            }
        """)

        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self._page_home())       
        self.pages.addWidget(self._page_training())   
        self.pages.addWidget(self._page_stats())      
        self.pages.addWidget(self._page_settings())
        self.pages.setStyleSheet("""
            QWidget {
                background: transparent;
            }
            QLabel {
                background: transparent;
            }
        """)
        content_layout.addWidget(self.pages)

        body.addWidget(sidebar)
        body.addWidget(content, 1)
        root.addLayout(body)
        QtCore.QTimer.singleShot(0, self._refresh_stats_and_home)


    def _nav_button_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-size: 14px;
                    font-weight: 600;
                    text-align: left;
                    padding-left: 12px;
                }
                QPushButton:hover { background-color: #005499; }
            """
        return """
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
                text-align: left;
                padding-left: 12px;
            }
            QPushButton:hover { background-color: #e9e9e9; }
        """

    def set_page(self, index: int):
        self.pages.setCurrentIndex(index)
        self.btn_home.setChecked(index == 0)
        self.btn_training.setChecked(index == 1)
        self.btn_stats.setChecked(index == 2)
        self.btn_settings.setChecked(index == 3)

    def _stats_path(self) -> str:
        # локальный файл рядом с main_window.py
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "training_history.json")

    def _stats_load(self) -> list:
        try:
            return get_training_history(limit=2000) or []
        except Exception:
            return []

    def _stats_append(self, rec: dict):
        import datetime
        rec = dict(rec)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            save_training_record(
                user_stage=rec.get("user_stage", 0),
                ai_stage=rec.get("ai_stage", 0),
                score=rec.get("score", 0),
                dice=rec.get("dice", 0.0),
                p_max=rec.get("p_max", 0.0),
                ts=ts,
            )
        except Exception:
            pass


    def _page_home(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setStyleSheet("""
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        l = QtWidgets.QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(16)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(12)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(4)

        title = QtWidgets.QLabel(f"Добро пожаловать, {self.username}!")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #222;")
        left.addWidget(title)

        subtitle = QtWidgets.QLabel("Тренируйтесь определять диабетическую ретинопатию и её стадию по снимкам.")
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
            # avatar.setStyleSheet("""
            #     QLabel {
            #         border: 2px solid #d6d6d6;
            #         border-radius: 28px;
            #         background: transparent;
            #     }
            # """)
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
            QLabel {
                border: none;
                background: transparent;
            }
            """)
            cl = QtWidgets.QVBoxLayout(c)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(6)

            t = QtWidgets.QLabel(title_text)
            t.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #777;
                    font-weight: 700;
                    border: none;
                    background: transparent;
                    padding: 0;
                    margin: 0;
                }
            """)

            v = QtWidgets.QLabel(value_text)
            v.setStyleSheet("""
                QLabel {
                    font-size: 20px;
                    color: #222;
                    font-weight: 900;
                    border: none;
                    background: transparent;
                    padding: 0;
                    margin: 0;
                }
            """)

            h = QtWidgets.QLabel(hint_text)
            h.setWordWrap(True)
            h.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #888;
                    border: none;
                    background: transparent;
                    padding: 0;
                    margin: 0;
                }
            """)

            cl.addWidget(t)
            cl.addWidget(v)
            cl.addWidget(h)
            return c, v

        c1, self.home_last_activity_lbl = stat_card("Последняя активность", "—", "Появится после первой тренировки")
        c2, self.home_eff_lbl = stat_card("Эффективность", "—%", "Средняя точность ответов")
        c3, self.home_total_lbl = stat_card("Проведено тренировок", "—", "Количество решённых заданий")

        cards.addWidget(c1)
        cards.addWidget(c2)
        cards.addWidget(c3)


        l.addLayout(cards)

        actions_title = QtWidgets.QLabel("Быстрые действия")
        actions_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 800;
                color: #222;
                border: none;
                background: transparent;
            }
        """)
        l.addWidget(actions_title)

        actions_box = QtWidgets.QFrame()
        actions_box.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 16px;
            }
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

        btn_start_training = big_action("Начать обучение", "assets/icons/training.png", primary=True)
        btn_start_training.clicked.connect(lambda: self.set_page(1))

        btn_open_stats = big_action("Открыть статистику", "assets/icons/stats.png", primary=False)
        btn_open_stats.clicked.connect(lambda: self.set_page(2))

        btn_open_settings = big_action("Настройки", "assets/icons/settings.png", primary=False)
        btn_open_settings.clicked.connect(lambda: self.set_page(3))

        ab.addWidget(btn_start_training)
        ab.addWidget(btn_open_stats)
        ab.addWidget(btn_open_settings)

        l.addWidget(actions_box)

        updates = QtWidgets.QFrame()
        updates.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 16px;
            }
        """)

        ul = QtWidgets.QVBoxLayout(updates)
        ul.setContentsMargins(16, 14, 16, 14)
        ul.setSpacing(10)

        updates_title = QtWidgets.QLabel("Что нового")
        updates_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 800;
                color: #222;
                border: none;
                background: transparent;
            }
        """)
        ul.addWidget(updates_title)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #d7d7d7;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        inner = QtWidgets.QWidget()
        il = QtWidgets.QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(4)

        try:
            updates_data = [(u["version"], u["body"]) for u in get_updates()]
        except Exception:
            updates_data = [("offline", "Не удалось загрузить обновления с сервера.")]

        for t, d in updates_data:
            item = QtWidgets.QFrame()
            item.setStyleSheet("QFrame { background-color: transparent; border: none; }")
            it = QtWidgets.QVBoxLayout(item)
            it.setContentsMargins(12, 10, 12, 10)
            it.setSpacing(4)

            tt = QtWidgets.QLabel(t)
            tt.setStyleSheet("QLabel { font-size: 13px; font-weight: 900; color: #222; }")

            dd = QtWidgets.QLabel(d)
            dd.setWordWrap(True)
            dd.setStyleSheet("QLabel { font-size: 12px; color: #666; }")

            it.addWidget(tt)
            it.addWidget(dd)
            il.addWidget(item)

        il.addStretch(1)
        scroll.setWidget(inner)
        # scroll.setFixedHeight(170)

        ul.addWidget(scroll, 1)
        l.addWidget(updates, 1)

        return w

    def _page_stats(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setStyleSheet("QLabel { border: none; background: transparent; }")
        l = QtWidgets.QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(12)

        title = QtWidgets.QLabel("Статистика")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #222;")
        l.addWidget(title)

        data = self._stats_load()

        # summary cards
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(14)

        def card(t, v, h):
            c = QtWidgets.QFrame()
            c.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 16px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
            """)
            cl = QtWidgets.QVBoxLayout(c)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(6)

            tt = QtWidgets.QLabel(t)
            tt.setStyleSheet("font-size:12px;color:#777;font-weight:800;")
            vv = QtWidgets.QLabel(v)
            vv.setStyleSheet("font-size:20px;color:#222;font-weight:900;")
            hh = QtWidgets.QLabel(h)
            hh.setWordWrap(True)
            hh.setStyleSheet("font-size:11px;color:#888;font-weight:700;")

            cl.addWidget(tt)
            cl.addWidget(vv)
            cl.addWidget(hh)
            return c, vv

        total = len(data)
        avg_score = (sum(d.get("score", 0) for d in data) / total) if total else 0.0
        avg_dice = (sum(d.get("dice", 0.0) for d in data) / total) if total else 0.0

        c1, self.stats_total_lbl = card("Проведено тренировок", "—", "Количество решённых заданий")
        c2, self.stats_avg_score_lbl = card("QWS", "—/5", "Средняя оценка качества ваших знаний")
        c3, self.stats_avg_dice_lbl = card("AIS", "—", "Соответствие с областью внимания")

        cards.addWidget(c1)
        cards.addWidget(c2)
        cards.addWidget(c3)
        l.addLayout(cards)

        # table history
        # chart history
        box = QtWidgets.QFrame()
        box.setStyleSheet("QFrame{background:#fff;border:none;border-radius:16px;}")
        bl = QtWidgets.QVBoxLayout(box)
        bl.setContentsMargins(14, 14, 14, 14)
        bl.setSpacing(10)

        t = QtWidgets.QLabel("Динамика результатов")
        t.setStyleSheet("font-size:14px;font-weight:900;color:#222;")
        bl.addWidget(t)

        self.stats_chart = LineChartWidget()
        self.stats_chart.setMinimumHeight(220)
        bl.addWidget(self.stats_chart, 1)

        l.addWidget(box, 1)

        for lab in w.findChildren(QtWidgets.QLabel):
            lab.setFrameShape(QtWidgets.QFrame.NoFrame)
            lab.setLineWidth(0)

        return w
    
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


    def _page_training(self) -> QtWidgets.QWidget:
        import os
        import sys
        import json
        import random
        import subprocess
        import tempfile
        import datetime

        from ui_dialogs import RoundedDialog

        STAGE_NAMES = [
            "0 стадия - Нет ретинопатии",
            "1 стадия - Начальная",
            "2 стадия - Умеренная",
            "3 стадия - Тяжёлая",
            "4 стадия - Профилеративная"
        ]

        def _imread_unicode(path: str):
            data = np.fromfile(path, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            return img

        def _np_rgb_to_qpix(rgb: np.ndarray) -> QtGui.QPixmap:
            h, w = rgb.shape[:2]
            qimg = QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format_RGB888)
            return QtGui.QPixmap.fromImage(qimg.copy())

        def _blend_heatmap_on_rgb(rgb: np.ndarray, heat: np.ndarray, alpha: float = 0.35) -> np.ndarray:
            heat_u8 = (heat * 255).astype(np.uint8)
            heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)  # BGR
            heat_color = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
            heat_color = cv2.resize(heat_color, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
            out = rgb.astype(np.float32) * (1 - alpha) + heat_color.astype(np.float32) * alpha
            return np.clip(out, 0, 255).astype(np.uint8)

        def _overlay_user_mask(rgb: np.ndarray, mask01: np.ndarray, alpha: float = 0.30) -> np.ndarray:
            if mask01 is None:
                return rgb
            m = cv2.resize(mask01, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
            m = (m > 0.5).astype(np.float32)[..., None]
            green = np.zeros_like(rgb, dtype=np.float32)
            green[..., 1] = 255.0
            out = rgb.astype(np.float32) * (1 - alpha * m) + green * (alpha * m)
            return np.clip(out, 0, 255).astype(np.uint8)

        def _dice(a: np.ndarray, b: np.ndarray) -> float:
            a = a.astype(bool)
            b = b.astype(bool)
            inter = (a & b).sum()
            denom = a.sum() + b.sum()
            if denom == 0:
                return 0.0
            return float(2 * inter / denom)

        def _ai_mask_from_heatmap(heat224: np.ndarray, top_frac: float = 0.30) -> np.ndarray:
            h = heat224.astype(np.float32)
            h = (h - h.min()) / (h.max() - h.min() + 1e-6)
            thr = np.quantile(h, 1.0 - top_frac)
            return (h >= thr)

        def _score_1to5_from_similarity(sim: float) -> int:
            if sim >= 0.80: return 5
            if sim >= 0.60: return 4
            if sim >= 0.40: return 3
            if sim >= 0.20: return 2
            return 1

        class LoadingDialog(QtWidgets.QDialog):
            def __init__(self, parent, text="ИИ выполняет анализ…"):
                super().__init__(parent)
                self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
                self.setWindowModality(QtCore.Qt.ApplicationModal)
                self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

                outer = QtWidgets.QFrame(self)
                outer.setObjectName("outer")
                outer.setStyleSheet("QFrame#outer{background:#fff;border-radius:18px;}")

                root = QtWidgets.QVBoxLayout(self)
                root.setContentsMargins(0, 0, 0, 0)
                root.addWidget(outer)

                lay = QtWidgets.QVBoxLayout(outer)
                lay.setContentsMargins(18, 16, 18, 16)
                lay.setSpacing(10)

                row = QtWidgets.QHBoxLayout()
                badge = QtWidgets.QLabel("ИИ")
                badge.setFixedSize(34, 34)
                badge.setAlignment(QtCore.Qt.AlignCenter)
                badge.setStyleSheet("QLabel{background:#0078D7;color:#fff;border-radius:17px;font-weight:900;border:none;}")
                self.lbl = QtWidgets.QLabel(text)
                self.lbl.setStyleSheet("QLabel{font-size:14px;font-weight:900;color:#222;border:none;}")
                row.addWidget(badge)
                row.addWidget(self.lbl, 1)
                lay.addLayout(row)

                pb = QtWidgets.QProgressBar()
                pb.setRange(0, 0)
                pb.setFixedHeight(10)
                pb.setTextVisible(False)
                pb.setStyleSheet("""
                    QProgressBar{border:none;background:#eaeaea;border-radius:5px;}
                    QProgressBar::chunk{background:#0078D7;border-radius:5px;}
                """)
                lay.addWidget(pb)

                hint = QtWidgets.QLabel("Пожалуйста, подождите…")
                hint.setStyleSheet("QLabel{font-size:12px;color:#666;border:none;}")
                lay.addWidget(hint)

                self.setFixedWidth(420)
                self.adjustSize()
                if parent is not None:
                    pg = parent.frameGeometry()
                    self.move(pg.center().x() - self.width() // 2, pg.center().y() - self.height() // 2)
                else:
                    screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
                    self.move(screen.center().x() - self.width() // 2, screen.center().y() - self.height() // 2)

        class InferenceWorker(QtCore.QThread):
            done = QtCore.pyqtSignal(dict)
            fail = QtCore.pyqtSignal(str)

            def __init__(self, image_path: str, out_png: str):
                super().__init__()
                self.image_path = image_path
                self.out_png = out_png

            def run(self):
                try:
                    py = sys.executable
                    cmd = [py, "infer_torch.py", self.image_path, self.out_png]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode != 0:
                        err = (res.stderr or res.stdout or "").strip() or "Неизвестная ошибка"
                        self.fail.emit(err)
                        return
                    data = json.loads(res.stdout.strip())
                    self.done.emit(data)
                except Exception as e:
                    self.fail.emit(str(e))

        class PaintCanvas(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()
                self.base_rgb = None
                self.view_rgb = None
                self.user_mask = None
                self.ai_heat = None
                self.show_ai = False

                self.brush = 18
                self.eraser = False
                self.paint_enabled = False

                self._dragging = False
                self._last_pos = None

                self.setMinimumSize(1, 1)
                self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

            def clear_all(self):
                self.base_rgb = None
                self.view_rgb = None
                self.user_mask = None
                self.ai_heat = None
                self.show_ai = False
                self.paint_enabled = False
                self.update()

            def set_image(self, rgb: np.ndarray):
                self.base_rgb = rgb
                self.user_mask = np.zeros((rgb.shape[0], rgb.shape[1]), dtype=np.uint8)
                self.ai_heat = None
                self.show_ai = False
                self._recompose(alpha_cam=0.33)
                self.update()

            def set_ai_heat(self, heat224: np.ndarray, alpha_cam: float):
                self.ai_heat = heat224
                self.show_ai = True
                self._recompose(alpha_cam=alpha_cam)
                self.update()

            def set_show_ai(self, flag: bool, alpha_cam: float):
                self.show_ai = bool(flag)
                self._recompose(alpha_cam=alpha_cam)
                self.update()

            def set_brush(self, v: int):
                self.brush = max(3, int(v))

            def set_eraser(self, flag: bool):
                self.eraser = bool(flag)

            def set_paint_enabled(self, flag: bool):
                self.paint_enabled = bool(flag)

            def has_user_paint(self) -> bool:
                return self.user_mask is not None and int(self.user_mask.sum()) > 0

            def _recompose(self, alpha_cam: float):
                if self.base_rgb is None:
                    self.view_rgb = None
                    return
                out = self.base_rgb.copy()
                out = _overlay_user_mask(out, (self.user_mask > 0).astype(np.float32), alpha=0.28)
                if self.show_ai and self.ai_heat is not None:
                    out = _blend_heatmap_on_rgb(out, self.ai_heat, alpha=alpha_cam)
                self.view_rgb = out

            def _label_rect_for_image(self):
                if self.base_rgb is None:
                    return 0, 0, 1, 1
                H, W = self.base_rgb.shape[:2]
                aw, ah = self.width(), self.height()
                if aw <= 1 or ah <= 1:
                    return 0, 0, 1, 1
                img_ar = W / H
                area_ar = aw / ah
                if area_ar > img_ar:
                    h = ah
                    w = int(h * img_ar)
                else:
                    w = aw
                    h = int(w / img_ar)
                x0 = (aw - w) // 2
                y0 = (ah - h) // 2
                return x0, y0, w, h

            def _widget_pos_to_image_xy(self, pos: QtCore.QPoint):
                if self.base_rgb is None:
                    return None
                x0, y0, w, h = self._label_rect_for_image()
                px, py = pos.x(), pos.y()
                if px < x0 or py < y0 or px >= x0 + w or py >= y0 + h:
                    return None
                nx = (px - x0) / max(1, w)
                ny = (py - y0) / max(1, h)
                H, W = self.base_rgb.shape[:2]
                ix = int(nx * W)
                iy = int(ny * H)
                ix = max(0, min(W - 1, ix))
                iy = max(0, min(H - 1, iy))
                return ix, iy

            def _paint_at(self, ix: int, iy: int):
                if self.user_mask is None:
                    return
                v = 0 if self.eraser else 1
                cv2.circle(self.user_mask, (ix, iy), int(self.brush), int(v), thickness=-1)

            def mousePressEvent(self, e: QtGui.QMouseEvent):
                if not self.paint_enabled or self.base_rgb is None:
                    return
                if e.button() != QtCore.Qt.LeftButton:
                    return
                p = self._widget_pos_to_image_xy(e.pos())
                if p is None:
                    return
                self._dragging = True
                self._last_pos = p
                self._paint_at(p[0], p[1])
                self._recompose(alpha_cam=0.33)
                self.update()

            def mouseMoveEvent(self, e: QtGui.QMouseEvent):
                if not self.paint_enabled or not self._dragging or self.base_rgb is None:
                    return
                p = self._widget_pos_to_image_xy(e.pos())
                if p is None:
                    return
                x1, y1 = self._last_pos
                x2, y2 = p
                cv2.line(self.user_mask, (x1, y1), (x2, y2), color=(0 if self.eraser else 1), thickness=int(self.brush * 2))
                self._last_pos = p
                self._recompose(alpha_cam=0.33)
                self.update()

            def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
                if e.button() == QtCore.Qt.LeftButton:
                    self._dragging = False
                    self._last_pos = None

            def paintEvent(self, event):
                p = QtGui.QPainter(self)
                p.setRenderHint(QtGui.QPainter.Antialiasing, True)
                p.fillRect(self.rect(), QtGui.QColor("#fafafa"))

                if self.view_rgb is None:
                    p.setPen(QtGui.QPen(QtGui.QColor("#888"), 1))
                    p.drawText(self.rect(), QtCore.Qt.AlignCenter, "Загрузите изображение")
                    return

                x0, y0, w, h = self._label_rect_for_image()
                H, W = self.view_rgb.shape[:2]
                qimg = QtGui.QImage(self.view_rgb.data, W, H, 3 * W, QtGui.QImage.Format_RGB888)
                pix = QtGui.QPixmap.fromImage(qimg.copy())

                p.drawPixmap(QtCore.QRect(x0, y0, w, h), pix)


        class TrainingPage(QtWidgets.QWidget):
            def __init__(self, mainwin: "MainWindow"):
                super().__init__()
                self._mw = mainwin

                self.samples_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "samples"
                )
                self.image_path = None

                self._worker = None
                self._dlg = None

                # этапы
                # 0 = до старта, 1 = разметка+стадия, 2 = подтверждение фокуса, 3 = результат
                self.step = 0

                self._build()
                self._set_step(0)

            def _build(self):
                self.setStyleSheet("""
                    QLabel { border:none; background:transparent; color:#222; font-size:12px; }
                    QLineEdit, QComboBox {
                        border: 1px solid #e2e2e2;
                        border-radius: 10px;
                        padding: 8px;
                        background: #fff;
                        color: #222;
                        font-weight: 800;
                    }
                    QPushButton {
                        background: #0078D7;
                        color: #fff;
                        border: none;
                        border-radius: 12px;
                        padding: 10px 12px;
                        font-weight: 900;
                    }
                    QPushButton:hover { background:#005499; }
                    QPushButton:disabled { background:#b9c6d3; }

                    QProgressBar { border:none; background:#eaeaea; border-radius:7px; height:14px; }
                    QProgressBar::chunk { background:#0078D7; border-radius:7px; }
                    QSlider::groove:horizontal { height:6px; background:#e8e8e8; border-radius:3px; }
                    QSlider::handle:horizontal { width:14px; margin:-6px 0; border-radius:7px; background:#0078D7; }
                """)

                root = QtWidgets.QVBoxLayout(self)
                root.setContentsMargins(0, 0, 0, 0)
                root.setSpacing(12)

                title = QtWidgets.QLabel("Обучение")
                title.setStyleSheet("QLabel{font-size:22px;font-weight:900;}")
                root.addWidget(title)

                # прогресс этапов
                self.step_bar = QtWidgets.QProgressBar()
                self.step_bar.setRange(0, 3)
                self.step_bar.setValue(0)
                self.step_bar.setTextVisible(False)
                root.addWidget(self.step_bar)

                self.step_hint = QtWidgets.QLabel("")
                self.step_hint.setWordWrap(True)
                self.step_hint.setStyleSheet("QLabel{color:#555;font-weight:800;}")
                root.addWidget(self.step_hint)

                grid = QtWidgets.QHBoxLayout()
                grid.setSpacing(12)

                # left card (canvas)
                left = QtWidgets.QFrame()
                left.setStyleSheet("QFrame{background:#fafafa;border:1px solid #e6e6e6;border-radius:16px;}")
                ll = QtWidgets.QVBoxLayout(left)
                ll.setContentsMargins(12, 12, 12, 12)
                ll.setSpacing(10)

                self.canvas = PaintCanvas()
                ll.addWidget(self.canvas, 1)

                grid.addWidget(left, 1)

                # right card (controls)
                right = QtWidgets.QFrame()
                right.setFixedWidth(420)
                right.setStyleSheet("QFrame{background:#fff;border:1px solid #e6e6e6;border-radius:16px;}")
                rl = QtWidgets.QVBoxLayout(right)
                rl.setContentsMargins(14, 14, 14, 14)
                rl.setSpacing(10)

                head = QtWidgets.QLabel("Панель тренировки")
                head.setStyleSheet("QLabel{font-size:14px;font-weight:900;border:none;background:transparent;}")
                rl.addWidget(head)

                # --- кнопка старт ---
                self.btn_start = QtWidgets.QPushButton("Начать тренировку")
                self.btn_start.setFixedHeight(46)
                self.btn_start.clicked.connect(self._start_training)
                rl.addWidget(self.btn_start)

                # блок управления (скрыт до старта)
                self.controls_box = QtWidgets.QFrame()
                self.controls_box.setStyleSheet("QFrame{background:#ffffff;border:1px solid #eeeeee;border-radius:14px;}")
                cb = QtWidgets.QVBoxLayout(self.controls_box)
                cb.setContentsMargins(12, 12, 12, 12)
                cb.setSpacing(10)

                # инструменты
                tools = QtWidgets.QHBoxLayout()
                tools.setSpacing(10)

                self.chk_paint = QtWidgets.QCheckBox("Рисовать область")
                self.chk_paint.setChecked(True)
                self.chk_paint.stateChanged.connect(lambda _: self.canvas.set_paint_enabled(self.chk_paint.isChecked()))
                self.chk_paint.setStyleSheet("QCheckBox{font-weight:900;color:#222;} QCheckBox::indicator{width:16px;height:16px;}")
                tools.addWidget(self.chk_paint)

                self.chk_eraser = QtWidgets.QCheckBox("Ластик")
                self.chk_eraser.setChecked(False)
                self.chk_eraser.stateChanged.connect(lambda _: self.canvas.set_eraser(self.chk_eraser.isChecked()))
                self.chk_eraser.setStyleSheet("QCheckBox{font-weight:900;color:#222;} QCheckBox::indicator{width:16px;height:16px;}")
                tools.addWidget(self.chk_eraser)

                tools.addStretch(1)
                cb.addLayout(tools)

                br = QtWidgets.QHBoxLayout()
                br.setSpacing(10)

                lb = QtWidgets.QLabel("Размер кисти")
                lb.setStyleSheet("QLabel{font-size:12px;font-weight:900;border:none;background:transparent;}")
                br.addWidget(lb)

                self.brush_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
                self.brush_slider.setRange(3, 50)
                self.brush_slider.setValue(18)
                self.brush_slider.valueChanged.connect(lambda v: self.canvas.set_brush(v))
                br.addWidget(self.brush_slider, 1)

                cb.addLayout(br)

                stl = QtWidgets.QLabel("Выберите стадию диабетической ретинопатии:")
                stl.setStyleSheet("QLabel{font-size:12px;font-weight:900;border:none;background:transparent;}")
                cb.addWidget(stl)

                self.stage_combo = QtWidgets.QComboBox()
                self.stage_combo.addItems(STAGE_NAMES)
                self.stage_combo.setFixedHeight(40)
                cb.addWidget(self.stage_combo)

                self.btn_confirm_focus = QtWidgets.QPushButton("Подтвердить выбранные данные")
                self.btn_confirm_focus.setFixedHeight(44)
                self.btn_confirm_focus.clicked.connect(self._confirm_focus)
                cb.addWidget(self.btn_confirm_focus)

                self.btn_ai = QtWidgets.QPushButton("Проверить результат")
                self.btn_ai.setFixedHeight(46)
                self.btn_ai.clicked.connect(self._run_ai_async)
                cb.addWidget(self.btn_ai)

                rl.addWidget(self.controls_box)

                # результат карточкой (скрыт пока нет результата)
                self.result_frame = QtWidgets.QFrame()
                self.result_frame.setStyleSheet("""
                    QFrame { background:#f7fbff; border:1px solid #d6e7ff; border-radius:14px; }
                """)
                rf = QtWidgets.QVBoxLayout(self.result_frame)
                rf.setContentsMargins(12, 12, 12, 12)
                rf.setSpacing(8)

                self.result_title = QtWidgets.QLabel("Результат")
                self.result_title.setStyleSheet("QLabel{font-size:13px;font-weight:900;color:#0b2a4a;border:none;background:transparent;}")
                rf.addWidget(self.result_title)

                row = QtWidgets.QHBoxLayout()
                row.setSpacing(10)

                self.score_badge = QtWidgets.QLabel("—/5")
                self.score_badge.setAlignment(QtCore.Qt.AlignCenter)
                self.score_badge.setFixedSize(64, 44)
                self.score_badge.setStyleSheet("""
                    QLabel{background:#0078D7;color:#fff;border-radius:12px;font-size:16px;font-weight:900;}
                """)
                row.addWidget(self.score_badge)

                self.ai_out = QtWidgets.QLabel("")
                self.ai_out.setWordWrap(True)
                self.ai_out.setStyleSheet("QLabel{font-size:12px;font-weight:800;color:#0b2a4a;}")
                row.addWidget(self.ai_out, 1)

                rf.addLayout(row)

                self.result_hint = QtWidgets.QLabel("")
                self.result_hint.setWordWrap(True)
                self.result_hint.setStyleSheet("QLabel{font-size:11px;color:#3f5d7a;font-weight:700;}")
                rf.addWidget(self.result_hint)

                self.result_frame.setVisible(False)
                rl.addWidget(self.result_frame)

                rl.addStretch(1)

                grid.addWidget(right)
                root.addLayout(grid, 1)

                self._kill_text_frames(self)

            def _kill_text_frames(self, root: QtWidgets.QWidget):
                # убираем именно рамки/фокус у текста, но НЕ трогаем QFrame карточки
                for lab in root.findChildren(QtWidgets.QLabel):
                    lab.setFrameShape(QtWidgets.QFrame.NoFrame)
                    lab.setLineWidth(0)
                    lab.setMidLineWidth(0)
                    lab.setFocusPolicy(QtCore.Qt.NoFocus)

            def _set_step(self, step: int):
                self.step = step
                self.step_bar.setValue(self.step)
                can_edit = (step == 1)
            
                self.stage_combo.setEnabled(can_edit)
                self.chk_paint.setEnabled(can_edit)
                self.chk_eraser.setEnabled(can_edit)
                self.brush_slider.setEnabled(can_edit)

                self.btn_confirm_focus.setEnabled(step == 1)
                self.btn_ai.setEnabled(step == 2)

                if self.step == 0:
                    self.step_hint.setText("Этап 1/4. Начните тренировку, нажав на кнопку \"Начать обучение\".")
                    self.controls_box.setVisible(False)
                    self.result_frame.setVisible(False)
                    self.canvas.set_paint_enabled(False)
                    self.btn_start.setEnabled(True)
                elif self.step == 1:
                    self.step_hint.setText("Этап 2/4. Выберите стадию диабетической ретинопатии и отметьте подозрительные области на изображении.")
                    self.controls_box.setVisible(True)
                    self.result_frame.setVisible(False)
                    self.canvas.set_paint_enabled(True)
                    self.btn_start.setEnabled(False)
                    self.btn_confirm_focus.setEnabled(True)
                    self.btn_ai.setEnabled(False)
                elif self.step == 2:
                    self.step_hint.setText("Этап 3/4. Подтвердите выполненную разметку, нажав на кнопку \"Проверить результат\"")
                    self.controls_box.setVisible(True)
                    self.result_frame.setVisible(False)
                    self.canvas.set_paint_enabled(False)  # блокируем рисование на этапе проверки
                    self.btn_confirm_focus.setEnabled(False)
                    self.btn_ai.setEnabled(True)
                else:
                    self.step_hint.setText("Этап 4/4. Отлично! Результаты успешно проверены.")
                    self.btn_start.setEnabled(True)
                    self.controls_box.setVisible(False)
                    self.result_frame.setVisible(True)
                    self.canvas.set_paint_enabled(False)
                    self.btn_confirm_focus.setEnabled(False)
                    self.btn_ai.setEnabled(False)

            def _pick_random_image(self, folder: str):
                exts = (".png", ".jpg", ".jpeg", ".bmp")
                files = []
                for root, _, fnames in os.walk(folder):
                    for f in fnames:
                        if f.lower().endswith(exts):
                            files.append(os.path.join(root, f))
                if not files:
                    return None
                return random.choice(files)

            def _start_training(self):
                if not os.path.isdir(self.samples_dir):
                    RoundedDialog.warning(
                        "Ошибка",
                        "Папка samples не найдена.\nДобавьте изображения в папку samples в корне проекта."
                    )
                    return
            
                imgp = self._pick_random_image(self.samples_dir)
                if not imgp:
                    RoundedDialog.warning("Нет изображений", "В выбранной папке не найдены изображения (png/jpg/jpeg/bmp).")
                    return

                bgr = _imread_unicode(imgp)
                if bgr is None:
                    RoundedDialog.warning("Ошибка", "Не удалось открыть изображение.")
                    return

                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                self.image_path = imgp
                self.canvas.set_image(rgb)

                # очистим результат
                self.result_frame.setVisible(False)
                self.ai_out.setText("")
                self.result_hint.setText("")
                self.score_badge.setText("—/5")

                # --- вернуть управление кистью при новом старте ---
                self.chk_paint.setEnabled(True)
                self.chk_eraser.setEnabled(True)
                self.brush_slider.setEnabled(True)

                # по умолчанию: рисование включено, ластик выключен
                self.chk_paint.setChecked(True)
                self.chk_eraser.setChecked(False)
                self.canvas.set_eraser(False)
                self.canvas.set_paint_enabled(True)

                # кнопки этапов тоже вернуть
                self.btn_confirm_focus.setEnabled(True)
                self.btn_ai.setEnabled(False)

                # этап 2
                self._set_step(1)

            def _confirm_focus(self):
                if not self.image_path or self.canvas.base_rgb is None:
                    RoundedDialog.warning("Нет изображения", "Сначала начните тренировку и загрузите изображение.")
                    return
                if not self.canvas.has_user_paint():
                    RoundedDialog.warning("Нужно выделить область", "Перед продолжением выделите область кистью.")
                    return
                self._set_step(2)

            def _reset_training(self):
                self.image_path = None
                self.canvas.clear_all()
                self.result_frame.setVisible(False)
                self.ai_out.setText("")
                self.result_hint.setText("")
                self.score_badge.setText("—/5")
                self._set_step(0)

            def _run_ai_async(self):
                if not self.image_path or self.canvas.base_rgb is None:
                    RoundedDialog.warning("Ошибка", "Сначала начните тренировку.")
                    return

                # проверка: фокус должен быть подтверждён
                if self.step < 2:
                    RoundedDialog.warning("Сначала подтвердите фокус", "Нажмите «Далее: подтвердить фокус» перед запуском ИИ.")
                    return

                self._dlg = LoadingDialog(self, "ИИ анализирует снимок и сравнивает с вашим фокусом…")
                self._dlg.show()

                out_png = os.path.join(tempfile.gettempdir(), "retino_heatmap.png")

                # блокируем элементы на время анализа
                self.btn_ai.setEnabled(False)
                self.stage_combo.setEnabled(False)
                self.chk_paint.setEnabled(False)
                self.chk_eraser.setEnabled(False)
                self.brush_slider.setEnabled(False)

                self._worker = InferenceWorker(self.image_path, out_png)
                self._worker.done.connect(lambda data: self._on_ai_done(data, out_png))
                self._worker.fail.connect(self._on_ai_fail)
                self._worker.finished.connect(self._on_ai_finally)
                self._worker.start()

            def _on_ai_done(self, data: dict, out_png: str):
                stage_id = int(data.get("stage_id", 0))
                pmax = float(data.get("p_max", 0.0))

                heat_u8 = cv2.imdecode(np.fromfile(out_png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                if heat_u8 is None:
                    raise RuntimeError("Не удалось прочитать heatmap.png")

                heat = heat_u8.astype(np.float32) / 255.0

                # пользов. маска -> 224
                um = (self.canvas.user_mask > 0).astype(np.uint8)
                um_224 = cv2.resize(um, (224, 224), interpolation=cv2.INTER_NEAREST).astype(bool)

                # маска ИИ
                am_224 = _ai_mask_from_heatmap(heat, top_frac=0.30)

                sim = _dice(um_224, am_224)          # 0..1
                area_score = _score_1to5_from_similarity(sim)

                user_stage = self.stage_combo.currentIndex()
                ai_stage = stage_id
                diff_stage = abs(user_stage - ai_stage)
                stage_score = max(1, 5 - diff_stage)

                w_stage = 0.8
                w_area  = 0.2
                final_score = int(round(w_stage * stage_score + w_area * area_score))
                final_score = max(1, min(5, final_score))

                # сохранить в статистику
                try:
                    self._mw._stats_append({
                        "user_stage": int(user_stage),
                        "ai_stage": int(ai_stage),
                        "score": int(final_score),
                        "dice": float(sim),
                        "p_max": float(pmax),
                    })
                except Exception:
                    pass

                # показать теплокарту на канвасе (уже после результата — можно включить)
                self.canvas.set_ai_heat(heat, alpha_cam=0.33)

                # профессиональный текст
                ai_txt = STAGE_NAMES[ai_stage]
                user_txt = STAGE_NAMES[user_stage]

                self.ai_out.setText(
                    f"Автоматический анализ определил: {ai_txt}.\n"
                    f"Ваш ответ: {user_txt}."
                )
                self.ai_out.setStyleSheet("QLabel{font-size:11px;font-weight:900;border:none;background:transparent;}")
                self.result_hint.setText(
                    f"Совпадение области внимания (Dice): {sim:.2f} • "
                    f"Уверенность модели: {pmax:.2f} • "
                    f"Оценка: {final_score}/5"
                )
                self.result_hint.setStyleSheet("QLabel{font-size:11px;font-weight:900;border:none;background:transparent;}")
                self.score_badge.setText(f"{final_score}/5")
                self.result_frame.setVisible(True)

                # этап 4 — блокируем рисование и даём варианты
                self._set_step(3)

                def on_restart():
                    self._reset_training()

                def on_stats():
                    try:
                        self._mw.set_page(2)
                    except Exception:
                        pass

                body = (
                    f"ИИ определил: {ai_txt}.\n"
                    f"Ваш ответ: {user_txt}.\n\n"
                    f"Совпадение области внимания: {sim:.2f}.\n"
                    f"Итоговая оценка: {final_score}/5."
                )

            def _on_ai_fail(self, err: str):
                RoundedDialog.warning("Ошибка", f"ИИ анализ не удался:\n{err}")

            def _on_ai_finally(self):
                if self._dlg is not None:
                    self._dlg.close()
                    self._dlg = None

                # разблокируем базовое управление
                self.stage_combo.setEnabled(True)

                # но рисование уже запрещено (после анализа), пока не нажмут “Заново”
                self.chk_paint.setEnabled(False)
                self.chk_eraser.setEnabled(False)
                self.brush_slider.setEnabled(False)

        return TrainingPage(self)


    def menu_button(self, text: str, icon_path: str):
        btn = QtWidgets.QPushButton(text)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setIconSize(QtCore.QSize(20, 20))
        btn.setFixedHeight(44)
        btn.setCursor(QtCore.Qt.PointingHandCursor)

        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 14px;
                padding-right: 12px;
                font-size: 14px;
                border: none;
                border-radius: 10px;
                color: #222;
            }
            QPushButton:hover {
                background-color: #f3f3f3;
            }
            QPushButton:checked {
                background-color: #0078D7;
                color: white;
            }
        """)
        btn.setCheckable(True)
        return btn

    def _page_settings(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setStyleSheet("background: transparent;")
        l = QtWidgets.QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)

        title = QtWidgets.QLabel("Настройки")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #222;")
        l.addWidget(title)

        profile = QtWidgets.QWidget()
        pl = QtWidgets.QHBoxLayout(profile)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(12)

        avatar = QtWidgets.QLabel()
        avatar.setFixedSize(52, 52)

        pix = QtGui.QPixmap("assets/icons/avatar.png")  # <-- путь к файлу
        pix = pix.scaled(
            avatar.size(),
            QtCore.Qt.KeepAspectRatioByExpanding,
            QtCore.Qt.SmoothTransformation
        )

        avatar.setPixmap(pix)
        avatar.setAlignment(QtCore.Qt.AlignCenter)

        pl.addWidget(avatar)

        info_col = QtWidgets.QVBoxLayout()
        info_col.setSpacing(4)

        name = QtWidgets.QLabel(self.username)
        name.setStyleSheet("font-size: 16px; font-weight: 700; color: #222;")
        info_col.addWidget(name)

        verified_row = QtWidgets.QHBoxLayout()
        verified_row.setSpacing(6)

        check = QtWidgets.QLabel("✓")
        check.setFixedSize(18, 18)
        check.setAlignment(QtCore.Qt.AlignCenter)
        check.setStyleSheet("""
            QLabel {
                background-color: #22c55e;
                color: white;
                border-radius: 9px;
                font-size: 12px;
                font-weight: 800;
            }
        """)

        verified_text = QtWidgets.QLabel("Аккаунт верифицирован")
        verified_text.setStyleSheet("font-size: 13px; color: #16a34a; font-weight: 700;")

        self.settings_verify_icon = check          # QLabel / кружок / галка
        self.settings_verified_text = verified_text # QLabel с текстом статуса
        
        info_lbl = QtWidgets.QLabel("(❔)")
        info_lbl.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        info_lbl.setToolTip(
            "Поздравляем! Ваш аккаунт был подтверждён"
        )
        info_lbl.setStyleSheet("""
            QLabel {
                color: #9aa4b2;
                font-size: 13px;
            }
        """)

        verified_row.addWidget(check)
        verified_row.addWidget(verified_text)
        verified_row.addWidget(info_lbl)
        verified_row.addStretch(1)

        info_col.addLayout(verified_row)
        pl.addLayout(info_col, 1)

        l.addWidget(profile)

        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setSpacing(6)
        status_layout.setContentsMargins(0, 0, 0, 0)

        status_layout.addLayout(status_layout)


        change_pwd_btn = QtWidgets.QPushButton("Сменить пароль")
        change_pwd_btn.setFixedHeight(38)
        change_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        change_pwd_btn.clicked.connect(self._change_password)
        l.addWidget(change_pwd_btn, alignment=QtCore.Qt.AlignLeft)
        
        logout_btn = QtWidgets.QPushButton("Выйти из аккаунта")
        logout_btn.setFixedHeight(38)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #222;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #e7e7e7; }
        """)
        logout_btn.clicked.connect(self._logout)
        l.addWidget(logout_btn, alignment=QtCore.Qt.AlignLeft)


        l.addStretch(1)

        danger_title = QtWidgets.QLabel("Опасная зона")
        danger_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #222;")
        l.addWidget(danger_title)

        danger_text = QtWidgets.QLabel(
            "Удаление аккаунта необратимо.\n"
            "Будут удалены прогресс обучения, статистика, результаты тестов и любые сохранённые данные.\n"
            "После удаления этот логин останется недоступен навсегда."
        )
        danger_text.setWordWrap(True)
        danger_text.setStyleSheet("font-size: 12px; color: #666;")
        l.addWidget(danger_text)

        # reset_btn = QtWidgets.QPushButton("Сбросить статистику тренировок")
        # reset_btn.setFixedHeight(40)
        # reset_btn.setStyleSheet("""
        #     QPushButton {
        #         background-color: #ffecec;
        #         color: #a30000;
        #         border: 1px solid #ffb3b3;
        #         border-radius: 8px;
        #     }
        #     QPushButton:hover {
        #         background-color: #ffd6d6;
        #     }
        # """)
        # reset_btn.clicked.connect(self._on_reset_training)

        # l.addWidget(reset_btn)

        delete_btn = QtWidgets.QPushButton("Удалить аккаунт")
        delete_btn.setFixedHeight(44)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #CC0000; }
        """)
        delete_btn.clicked.connect(self._delete_account)
        l.addWidget(delete_btn)

        footer = QtWidgets.QLabel("by redictorb, 2026 • MIT License")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #8a8a8a;")
        l.addWidget(footer)

        return w
    def _on_reset_training(self):
        dlg = RoundedDialog(
            self,
            "Сбросить всю статистику тренировок?\n\n"
            "Это действие нельзя отменить."
        )

        dlg.set_confirm_text("Сбросить")
        dlg.set_cancel_text("Отмена")
        dlg.set_danger(True)  # если есть красный режим

        if dlg.exec_() != dlg.Accepted:
            return

        ok = reset_training_history()

        if ok:
            done = RoundedDialog(
                self,
                "Статистика тренировок успешно сброшена."
            )
            done.set_confirm_text("Ок")
            done.exec_()

            self._refresh_stats_and_home()
        else:
            err = RoundedDialog(
                self,
                "Не удалось сбросить статистику.\nПопробуйте позже."
            )
            err.set_confirm_text("Понятно")
            err.exec_()

    def _apply_account_status_ui(self):
        st = self._account_status or {}
        is_verified = bool(st.get("is_verified", False))

    def _logout(self):
        from ui_dialogs import RoundedDialog

        RoundedDialog.warning(
            "Выход из аккаунта",
            "Вы действительно хотите выйти из аккаунта?"
        )

        self.close()
        if self.on_logout:
            self.on_logout()

    def _change_password(self):
        from ui_dialogs import ChangePasswordDialog
        ChangePasswordDialog.run(self, self.username)

    def _delete_account(self):
        ok = DeleteAccountDialog.run(self, self.username)
        if not ok:
            return

        if delete_user_soft("delete my account"):
            RoundedDialog.info("Готово", "Аккаунт удалён.")
            logout()
            self.close()
            self.on_logout()
        else:
            RoundedDialog.warning("Ошибка", "Не удалось удалить (возможно, вы не авторизованы).")


    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()