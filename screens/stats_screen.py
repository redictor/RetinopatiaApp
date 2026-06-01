import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
import app_logger

_log = app_logger.get("screens.stats")


class LineChartWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = []
        self._target_level = None
        self._best_values = []
        self._ids = []
        self._dates = []
        self.setMouseTracking(True)
        self._hover_index = None
        self._mouse_pos = None

    def set_series(self, values, best_values=None, dates=None, ids=None):
        self._values = list(values or [])
        self._best_values = list(best_values or [])
        self._dates = list(dates or [])
        self._ids = list(ids or [])
        self.update()

    def set_target_level(self, level):
        self._target_level = level
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QtGui.QColor("#ffffff"))
        r = self.rect().adjusted(48, 14, -14, -42)

        if len(self._values) < 2:
            p.setPen(QtGui.QPen(QtGui.QColor("#888"), 1))
            p.drawText(r, QtCore.Qt.AlignCenter, "Недостаточно данных для графика")
            return

        vals = self._values
        vmin, vmax = 1.0, 5.0

        def y_for(v: float) -> float:
            v = max(vmin, min(vmax, float(v)))
            return r.bottom() - ((v - vmin) / (vmax - vmin)) * r.height()

        def x_for(i: int) -> float:
            return r.left() + (i / (len(vals) - 1)) * r.width()

        grid_pen = QtGui.QPen(QtGui.QColor("#e9e9e9"), 1)
        p.setPen(grid_pen)
        for level in range(1, 6):
            y = y_for(level)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))

        p.setPen(QtGui.QPen(QtGui.QColor("#777"), 1))
        for level in range(1, 6):
            y = y_for(level)
            p.drawText(int(r.left()) - 26, int(y) + 5, str(level))

        pts = [QtCore.QPointF(x_for(i), y_for(v)) for i, v in enumerate(vals)]

        path = QtGui.QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)

        p.setPen(QtGui.QPen(QtGui.QColor("#0078D7"), 2))
        p.drawPath(path)

        p.setBrush(QtGui.QBrush(QtGui.QColor("#0078D7")))
        p.setPen(QtGui.QPen(QtGui.QColor("#0078D7"), 2))
        for i, v in enumerate(vals):
            p.drawEllipse(QtCore.QPointF(x_for(i), y_for(v)), 2, 2)

        if self._hover_index is not None and self._hover_index < len(vals):
            i = self._hover_index
            score = vals[i]
            score_text = str(int(score)) if float(score).is_integer() else f"{score:.1f}"

            raw_date = self._dates[i] if i < len(self._dates) else ""
            date_text = "Дата неизвестна"
            try:
                s = str(raw_date).replace("Z", "").replace(" ", "T")
                dt = datetime.datetime.fromisoformat(s)
                months = ["янв","фев","мар","апр","мая","июн","июл","авг","сен","окт","ноя","дек"]
                date_text = f"{dt.day} {months[dt.month - 1]} {dt.year} {dt.strftime('%H:%M')}"
            except Exception:
                if raw_date:
                    date_text = str(raw_date)

            train_id = self._ids[i] if i < len(self._ids) else i + 1
            text = f"Тренировка №{train_id}\nОценка: {score_text}/5\nДата: {date_text}"

            font = QtGui.QFont()
            font.setPointSize(9)
            font.setBold(True)
            p.setFont(font)

            metrics = QtGui.QFontMetrics(font)
            lines = text.split("\n")
            text_w = max(metrics.horizontalAdvance(line) for line in lines)
            text_h = metrics.height() * len(lines)

            box_w = text_w + 22
            box_h = text_h + 18

            px = int(x_for(i) + 12)
            py = int(y_for(score) - box_h - 12)

            if px + box_w > self.width() - 8:
                px = int(x_for(i) - box_w - 12)
            if py < 8:
                py = int(y_for(score) + 12)

            box_rect = QtCore.QRectF(px, py, box_w, box_h)
            p.setPen(QtGui.QPen(QtGui.QColor("#d0d0d0"), 1))
            p.setBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
            p.drawRoundedRect(box_rect, 10, 10)

            p.setPen(QtGui.QPen(QtGui.QColor("#222"), 1))
            ty = py + (box_h - metrics.height() * len(lines)) / 2 + metrics.ascent()
            for line in lines:
                p.drawText(px + 11, int(ty), line)
                ty += metrics.height()

        if self._target_level is not None:
            lvl = max(1, min(5, int(self._target_level)))
            y = y_for(lvl)
            pen2 = QtGui.QPen(QtGui.QColor("#00A65A"), 2)
            pen2.setStyle(QtCore.Qt.DashLine)
            p.setPen(pen2)
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))

            legend_y = int(r.bottom() + 28)
            font = QtGui.QFont()
            font.setPointSize(9)
            font.setBold(True)
            p.setFont(font)
            metrics = QtGui.QFontMetrics(font)

            blue_text = "Результаты"
            green_text = "Средний результат"
            item_gap = 42
            line_w = 34
            text_gap = 10

            blue_w = line_w + text_gap + metrics.horizontalAdvance(blue_text)
            green_w = line_w + text_gap + metrics.horizontalAdvance(green_text)
            total_w = blue_w + item_gap + green_w
            legend_x = int(r.left() + (r.width() - total_w) / 2)

            p.setPen(QtGui.QPen(QtGui.QColor("#0078D7"), 3))
            p.drawLine(legend_x, legend_y, legend_x + line_w, legend_y)
            p.setPen(QtGui.QPen(QtGui.QColor("#222"), 1))
            p.drawText(legend_x + line_w + text_gap, legend_y + 5, blue_text)

            legend_x += blue_w + item_gap
            green_pen = QtGui.QPen(QtGui.QColor("#00A65A"), 3)
            green_pen.setStyle(QtCore.Qt.DashLine)
            p.setPen(green_pen)
            p.drawLine(legend_x, legend_y, legend_x + line_w, legend_y)
            p.setPen(QtGui.QPen(QtGui.QColor("#222"), 1))
            p.drawText(legend_x + line_w + text_gap, legend_y + 5, green_text)

    def mouseMoveEvent(self, event):
        if len(self._values) < 2:
            self._hover_index = None
            self._mouse_pos = None
            self.update()
            return

        r = self.rect().adjusted(48, 14, -14, -48)
        vals = self._values
        vmin, vmax = 1.0, 5.0

        def x_for(i):
            return r.left() + (i / (len(vals) - 1)) * r.width()

        def y_for(v):
            v = max(vmin, min(vmax, float(v)))
            return r.bottom() - ((v - vmin) / (vmax - vmin)) * r.height()

        nearest = None
        nearest_dist = 999999
        for i, v in enumerate(vals):
            dx = event.x() - x_for(i)
            dy = event.y() - y_for(v)
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = i

        if nearest is not None and nearest_dist <= 8:
            self._hover_index = nearest
            self._mouse_pos = event.pos()
        else:
            self._hover_index = None
            self._mouse_pos = None
        self.update()

    def leaveEvent(self, event):
        self._hover_index = None
        self._mouse_pos = None
        self.update()


class StatsScreen(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.setStyleSheet("QLabel { border: none; background: transparent; }")
        l = QtWidgets.QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(12)

        title = QtWidgets.QLabel("Статистика")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #222;")
        l.addWidget(title)

        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(14)

        def card(t, v, h):
            c = QtWidgets.QFrame()
            c.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 16px; }
            QLabel { border: none; background: transparent; }
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

        c1, self.stats_total_lbl = card("Проведено тренировок", "-", "Количество решённых заданий")
        c2, self.stats_avg_score_lbl = card("QWS", "-/5", "Средняя оценка качества ваших знаний")
        c2.layout().insertWidget(1, self.stats_avg_score_lbl)
        c3, self.stats_avg_dice_lbl = card("AIS", "-", "Соответствие с областью внимания")

        cards.addWidget(c1)
        cards.addWidget(c2)
        cards.addWidget(c3)
        l.addLayout(cards)

        box = QtWidgets.QFrame()
        box.setStyleSheet("QFrame{background:#fff;border:none;border-radius:16px;}")
        bl = QtWidgets.QVBoxLayout(box)
        bl.setContentsMargins(14, 14, 14, 14)
        bl.setSpacing(10)

        t = QtWidgets.QLabel("Динамика результатов за последние 20 тренировок")
        t.setStyleSheet("font-size:14px;font-weight:900;color:#222;")
        bl.addWidget(t)

        self.stats_chart = LineChartWidget()
        self.stats_chart.setMinimumHeight(220)
        bl.addWidget(self.stats_chart, 1)

        l.addWidget(box, 1)

        for lab in self.findChildren(QtWidgets.QLabel):
            lab.setFrameShape(QtWidgets.QFrame.NoFrame)
            lab.setLineWidth(0)

    def apply_data(self, data):
        try:
            data = data or []

            scores = []
            dices = []
            dates = []
            ids = []

            for item in data:
                try:
                    scores.append(float(item.get("score", 0)))
                except (ValueError, TypeError):
                    pass
                try:
                    dices.append(float(item.get("dice", 0.0)))
                except (ValueError, TypeError):
                    pass
                dates.append(
                    item.get("created_at") or item.get("date") or item.get("ts") or "-"
                )
                ids.append(item.get("id") or "-")

            total = len(data)
            avg_score = sum(scores) / len(scores) if scores else 0.0
            avg_dice = sum(dices) / len(dices) if dices else 0.0

            self.stats_total_lbl.setText(str(total))
            self.stats_avg_score_lbl.setText(f"{avg_score:.1f}/5")
            self.stats_avg_dice_lbl.setText(f"{avg_dice:.2f}")
            self.stats_chart.set_series(scores[-20:], [], dates[-20:], ids[-20:])
            self.stats_chart.set_target_level(int(avg_score + 0.5) if scores else None)
        except Exception:
            _log.error("Ошибка применения данных на экран статистики", exc_info=True)
