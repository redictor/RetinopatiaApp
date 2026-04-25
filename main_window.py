import os
import sys
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
from PyQt5 import QtWidgets, QtCore, QtGui
from api_client import delete_user_soft, logout, get_maintenance_status, get_updates, save_training_record, get_training_history, reset_training_history, get_profile
from ui_dialogs import DeleteAccountDialog, RoundedDialog
from ui_dialogs import ApiWorker
import numpy as np
import cv2
import json
import random
import subprocess
import tempfile
import datetime
from main import current_v

class ToggleSwitch(QtWidgets.QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(46, 24)

        self._offset = 1.0 if self.isChecked() else 0.0

        self._anim = QtCore.QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self.toggled.connect(self._start_anim)

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = float(value)
        self.update()

    offset = QtCore.pyqtProperty(float, fget=get_offset, fset=set_offset)

    def _start_anim(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.isEnabled():
            self.setChecked(not self.isChecked())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()

        if not self.isEnabled():
            bg = QtGui.QColor("#b9c6d3")
        elif self.isChecked():
            bg = QtGui.QColor("#0078D7")
        else:
            bg = QtGui.QColor("#cfcfcf")

        p.setBrush(bg)
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(rect, 12, 12)

        margin = 3
        d = rect.height() - margin * 2

        x_min = margin
        x_max = rect.width() - d - margin
        x = x_min + (x_max - x_min) * self._offset

        p.setBrush(QtGui.QColor("#ffffff"))
        p.drawEllipse(QtCore.QRectF(x, margin, d, d))


class ModeSwitch(QtWidgets.QAbstractButton):
    modeChanged = QtCore.pyqtSignal(bool)  # False = кисть, True = ластик

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(132, 30)

        self._offset = 1.0 if self.isChecked() else 0.0

        self._anim = QtCore.QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self.toggled.connect(self._on_toggled)

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = float(value)
        self.update()

    offset = QtCore.pyqtProperty(float, fget=get_offset, fset=set_offset)

    def _on_toggled(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()
        self.modeChanged.emit(bool(checked))

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.isEnabled():
            self.setChecked(not self.isChecked())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        bg = QtGui.QColor("#eef2f7") if self.isEnabled() else QtGui.QColor("#d7dde5")

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 15, 15)

        margin = 3
        half_w = (rect.width() - margin * 2) / 2
        knob_x = margin + half_w * self._offset

        knob = QtCore.QRectF(knob_x, margin, half_w, rect.height() - margin * 2)
        p.setBrush(QtGui.QColor("#0078D7") if self.isEnabled() else QtGui.QColor("#b9c6d3"))
        p.drawRoundedRect(knob, 12, 12)

        font = QtGui.QFont()
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)

        left_rect = QtCore.QRectF(margin, margin, half_w, rect.height() - margin * 2)
        right_rect = QtCore.QRectF(margin + half_w, margin, half_w, rect.height() - margin * 2)

        p.setPen(QtGui.QColor("#ffffff") if not self.isChecked() else QtGui.QColor("#333333"))
        p.drawText(left_rect, QtCore.Qt.AlignCenter, "Кисть")

        p.setPen(QtGui.QColor("#ffffff") if self.isChecked() else QtGui.QColor("#333333"))
        p.drawText(right_rect, QtCore.Qt.AlignCenter, "Ластик")

class MouseHintIcon(QtWidgets.QWidget):
    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setFixedSize(28, 32)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        pen = QtGui.QPen(QtGui.QColor("#222"), 1.6)
        p.setPen(pen)
        p.setBrush(QtCore.Qt.NoBrush)

        body = QtCore.QRectF(5, 3, 18, 26)
        p.drawRoundedRect(body, 9, 9)

        p.drawLine(14, 4, 14, 12)
        p.drawLine(5, 14, 23, 14)

        if self.mode == "left":
            p.setBrush(QtGui.QColor("#222"))
            p.drawPie(QtCore.QRectF(5, 3, 18, 18), 90 * 16, 90 * 16)

        elif self.mode == "right":
            p.setBrush(QtGui.QColor("#222"))
            p.drawPie(QtCore.QRectF(5, 3, 18, 18), 0, 90 * 16)

        elif self.mode == "wheel":
            p.setBrush(QtGui.QColor("#222"))
            p.drawRoundedRect(QtCore.QRectF(12, 6, 4, 9), 2, 2)
        
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
            x = x_for(i)
            y = y_for(v)
            p.drawEllipse(QtCore.QPointF(x, y), 2, 2)

        if self._hover_index is not None and self._hover_index < len(vals):
            i = self._hover_index
            score = vals[i]
            score_text = str(int(score)) if float(score).is_integer() else f"{score:.1f}"

            raw_date = self._dates[i] if i < len(self._dates) else ""

            date_text = "Дата неизвестна"

            try:
                s = str(raw_date).replace("Z", "").replace(" ", "T")
                dt = datetime.datetime.fromisoformat(s)

                months = [
                    "янв", "фев", "мар", "апр", "мая", "июн",
                    "июл", "авг", "сен", "окт", "ноя", "дек"
                ]

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
            total_text_height = metrics.height() * len(lines)
            ty = py + (box_h - total_text_height) / 2 + metrics.ascent()

            for line in lines:
                text_rect = QtCore.QRectF(px + 5, ty - metrics.ascent(), box_w - 10, metrics.height())
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
        self._stats_timer.start(60000)

        self._account_status = {"is_verified": False, "created_at": None}
        QtCore.QTimer.singleShot(0, self._load_account_status)
    
    def _ru_plural(self, n: int, one: str, few: str, many: str) -> str:
        n = abs(int(n))
        if 11 <= (n % 100) <= 14:
            return many
        if n % 10 == 1:
            return one
        if 2 <= (n % 10) <= 4:
            return few
        return many

    def _apply_updates_home(self, updates):
        if self._updates_layout is None:
            return

        updates = sorted(
            updates or [],
            key=lambda u: int(u.get("id", 0) or 0),
            reverse=True
        )

        while self._updates_layout.count():
            item = self._updates_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not updates:
            empty = QtWidgets.QLabel("Обновлений пока нет.")
            empty.setStyleSheet("QLabel { font-size: 12px; color: #777; padding: 10px; }")
            self._updates_layout.addWidget(empty)
            self._updates_layout.addStretch(1)
            return

        for i, upd in enumerate(updates):
            version = str(upd.get("version", "-"))
            text = str(upd.get("description") or upd.get("body") or "")

            card = QtWidgets.QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #f8f8f8;
                    border: 1px solid #e6e6e6;
                    border-radius: 12px;
                }
            """)

            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)

            top_row = QtWidgets.QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(8)

            t1 = QtWidgets.QLabel(f"{version}")
            t1.setStyleSheet("QLabel { font-size: 12px; font-weight: 800; color: #222; border: none;}")

            top_row.addWidget(t1)
            top_row.addStretch(1)

            if i == 0:
                new_badge = QtWidgets.QLabel("Новое")
                new_badge.setAlignment(QtCore.Qt.AlignCenter)
                new_badge.setStyleSheet("""
                    QLabel {
                        background: #fff7d6;
                        color: #9a6a00;
                        border: 1px solid #f2d27a;
                        border-radius: 9px;
                        font-size: 10px;
                        font-weight: 900;
                        padding: 3px 8px;
                    }
                """)
                top_row.addWidget(new_badge)

            cl.addLayout(top_row)

            t2 = QtWidgets.QLabel(text)
            t2.setWordWrap(True)
            t2.setStyleSheet("QLabel { font-size: 11px; color: #666; border: none;}")
            cl.addWidget(t2)

            self._updates_layout.addWidget(card)

        self._updates_layout.addStretch(1)

    def _apply_stats_data(self, data):
        data = data or []

        total = len(data)

        if total == 0:
            if hasattr(self, "home_last_activity_lbl"):
                self.home_last_activity_lbl.setText("")
            if hasattr(self, "home_eff_lbl"):
                self.home_eff_lbl.setText("-%")
            if hasattr(self, "home_total_lbl"):
                self.home_total_lbl.setText("0")
            return

        last_time = "-"

        for item in reversed(data):
            ts = (
                item.get("created_at")
                or item.get("date")
                or item.get("ts")
            )
            if ts:
                last_time = ts
                break

        scores = []
        for item in data:
            try:
                scores.append(float(item.get("score", 0)))
            except Exception:
                pass

        avg_score = sum(scores) / len(scores) if scores else 0.0
        eff = int(round(avg_score / 5 * 100)) if scores else 0

        if hasattr(self, "home_last_activity_lbl"):
            self.home_last_activity_lbl.setText(self._format_ago(last_time) if last_time != "-" else "-")
        if hasattr(self, "home_eff_lbl"):
            self.home_eff_lbl.setText(f"{eff}%")
        if hasattr(self, "home_total_lbl"):
            self.home_total_lbl.setText(str(total))

    def _apply_stats_page_data(self, data):
        data = data or []

        scores = []
        dices = []
        dates = []
        ids = []

        for item in data:
            try:
                scores.append(float(item.get("score", 0)))
            except Exception:
                pass

            try:
                dices.append(float(item.get("dice", 0.0)))
            except Exception:
                pass

            dates.append(
                item.get("created_at")
                or item.get("date")
                or item.get("ts")
                or "-"
            )

            ids.append(item.get("id") or "-")

        total = len(data)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_dice = sum(dices) / len(dices) if dices else 0.0

        if hasattr(self, "stats_total_lbl"):
            self.stats_total_lbl.setText(str(total))

        if hasattr(self, "stats_avg_score_lbl"):
            self.stats_avg_score_lbl.setText(f"{avg_score:.1f}/5")

        if hasattr(self, "stats_avg_dice_lbl"):
            self.stats_avg_dice_lbl.setText(f"{avg_dice:.2f}")

        if hasattr(self, "stats_chart"):
            self.stats_chart.set_series(scores[-20:], [], dates[-20:], ids[-20:])
            self.stats_chart.set_target_level(int(avg_score + 0.5) if scores else None)

    def _format_ago(self, ts_iso: str) -> str:
        if not ts_iso or ts_iso == "-":
            return "-"

        try:
            s = str(ts_iso).replace("Z", "").replace(" ", "T")
            t = datetime.datetime.fromisoformat(s)
        except Exception:
            return "-"

        now = datetime.datetime.now()
        delta = now - t
        secs = int(delta.total_seconds())
        if secs < 0:
            secs = 0

        mins = secs // 60
        if mins < 60:
            m = max(1, mins)
            return f"{m} {self._ru_plural(m, 'минуту', 'минуты', 'минут')} назад"

        hours = mins // 60
        if hours < 24:
            return f"{hours} {self._ru_plural(hours, 'час', 'часа', 'часов')} назад"

        days = hours // 24
        return f"{days} {self._ru_plural(days, 'день', 'дня', 'дней')} назад"

    def _refresh_stats_and_home(self):
        w = ApiWorker(get_training_history, 2000)
        w.ok.connect(self._apply_stats_data)
        w.ok.connect(self._apply_stats_page_data)
        w.fail.connect(lambda err: print("Ошибка загрузки статистики:", err))
        w.finished.connect(w.deleteLater)
        w.start()
        self._stats_worker = w

    def _on_maint_ok(self, st: dict):
        if st.get("enabled"):
            self._maint_forced = True
            self._maint_timer.stop()
            msg = st.get("message") or "Ведутся технические работы. Доступ временно запрещён."
            RoundedDialog.warning("Технические работы", "Сообщение от сервера: " + msg + "\n\n...")
            try:
                logout()
            except Exception:
                pass
            self.close()
            if self.on_logout:
                self.on_logout()

    def _check_maintenance(self):
        if self._maint_forced:
            return

        from api_client import get_maintenance_status
        from ui_dialogs import ApiWorker  # куда положишь класс

        w = ApiWorker(get_maintenance_status)
        w.ok.connect(self._on_maint_ok)
        w.fail.connect(lambda _: None)
        w.finished.connect(w.deleteLater)
        w.start()

        self._maint_worker = w  

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
                logo_pixmap.scaled(
                    32, 32,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
            )
        else:
            logo_label.setText("◉")
            logo_label.setStyleSheet("""
                QLabel {
                    color: #0078D7;
                    font-size: 18px;
                    font-weight: 900;
                }
            """)

        app_label = QtWidgets.QLabel("RetinopatiaApp")
        app_label.setStyleSheet("""
            QLabel {
                color: #222;
                font-size: 18px;
                font-weight: 600;
            }
        """)

        brand_layout.addWidget(logo_label)
        brand_layout.addWidget(app_label)

        drag_area = QtWidgets.QWidget()
        drag_area.setStyleSheet("background: transparent;")
        drag_area.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

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

        top.addWidget(brand)
        top.addStretch(1)
        top.addWidget(drag_area, 1)
        top.addWidget(minimize_button)
        top.addWidget(close_button)

        root.addWidget(top_bar)

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
        self._check_update()

    def _ver_tuple(self, v: str):
        s = (v or "").strip().lower()
        if s.startswith("v."):
            s = s[2:]
        elif s.startswith("v"):
            s = s[1:]
        parts = s.split(".")
        nums = []
        for p in parts:
            try:
                nums.append(int(p))
            except:
                nums.append(0)
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums[:3])

    def _check_update(self):
        try:
            updates = get_updates()
            if not updates:
                return

            latest = max(updates, key=lambda u: int(u.get("id", 0) or 0))
            latest_ver = str(latest.get("version", "")).strip()
            if not latest_ver:
                return

            if self._ver_tuple(latest_ver) > self._ver_tuple(current_v):
                RoundedDialog.info(
                    "Доступно обновление",
                    f"Установлена версия: {current_v}\n"
                    f"Доступна версия: {latest_ver}"
                )

        except Exception:
            return

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
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "training_history.json")

    def _stats_load(self) -> list:
        try:
            data = get_training_history(limit=2000) or []
            print("Статистика загружена:", len(data))
            return data
        except Exception as e:
            print("Ошибка _stats_load:", e)
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
        except Exception as e:
            print("Ошибка сохранения статистики:", e)

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

        c1, self.home_last_activity_lbl = stat_card("Последняя активность", "-", "Дата последней тренировки")
        c2, self.home_eff_lbl = stat_card("Эффективность", "-%", "Средняя точность ответов")
        c3, self.home_total_lbl = stat_card("Проведено тренировок", "-", "Количество решённых заданий")

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

        self._updates_layout = il

        loading = QtWidgets.QLabel("Загрузка обновлений…")
        loading.setStyleSheet("QLabel { font-size: 12px; color: #777; padding: 10px; }")
        il.addWidget(loading)

        worker = ApiWorker(get_updates)
        worker.ok.connect(self._apply_updates_home)
        worker.fail.connect(lambda _: self._apply_updates_home([]))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self._updates_worker = worker

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

        c1, self.stats_total_lbl = card("Проведено тренировок", "-", "Количество решённых заданий")
        c2, self.stats_avg_score_lbl = card("QWS", "—/5", "Средняя оценка качества ваших знаний")
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

        scores = []
        dices = []
        dates = []
        ids = []

        for item in data:
            try:
                scores.append(float(item.get("score", 0)))
            except Exception:
                pass

            try:
                dices.append(float(item.get("dice", 0.0)))
            except Exception:
                pass

            dates.append(
                item.get("created_at")
                or item.get("date")
                or item.get("ts")
                or "-"
            )

            ids.append(item.get("id") or "-")

        total = len(data)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_dice = sum(dices) / len(dices) if dices else 0.0
        chart_scores = scores[-20:]
        chart_dates = dates[-20:]

        self.stats_total_lbl.setText(str(total))
        self.stats_avg_score_lbl.setText(f"{avg_score:.1f}/5")
        self.stats_avg_dice_lbl.setText(f"{avg_dice:.2f}")

        self.stats_chart.set_series(chart_scores, [], chart_dates, ids[-20:])
        self.stats_chart.set_target_level(int(avg_score + 0.5) if scores else None)

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
                badge = QtWidgets.QLabel()
                badge.setFixedSize(34, 34)
                badge.setAlignment(QtCore.Qt.AlignCenter)

                pixmap = QtGui.QPixmap("assets/icons/ai.png")
                if not pixmap.isNull():
                    badge.setStyleSheet("QLabel{background:#0078D7;border-radius:17px;border:none;}")
                    badge.setPixmap(
                        pixmap.scaled(
                            25, 25,
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation
                        )
                    )
                else:
                    badge.setText("ИИ")
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

                    res = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=60
                    )

                    if res.returncode != 0:
                        err = (res.stderr or res.stdout or "").strip() or "Неизвестная ошибка"
                        self.fail.emit(err)
                        return

                    data = json.loads(res.stdout.strip())
                    self.done.emit(data)

                except subprocess.TimeoutExpired:
                    self.fail.emit("Превышено время ожидания анализа (60 сек).")
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
                self.show_user_mask = True
                self.alpha_cam = 0.33

                self.brush = 18
                self.eraser = False
                self.paint_enabled = False

                self._dragging = False
                self._last_pos = None
                self.zoom = 1.0
                self.pan = QtCore.QPointF(0, 0)
                self._panning = False
                self._pan_start = None

                self.setMinimumSize(1, 1)
                self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

            def clear_all(self):
                self.base_rgb = None
                self.view_rgb = None
                self.user_mask = None
                self.ai_heat = None
                self.show_ai = False
                self.show_user_mask = True
                self.alpha_cam = 0.33
                self.paint_enabled = False
                self.zoom = 1.0
                self.pan = QtCore.QPointF(0, 0)
                self._panning = False
                self._pan_start = None
                self.update()

            def set_image(self, rgb: np.ndarray):
                self.base_rgb = rgb
                self.user_mask = np.zeros((rgb.shape[0], rgb.shape[1]), dtype=np.uint8)
                self.ai_heat = None
                self.show_ai = False
                self.show_user_mask = True
                self.alpha_cam = 0.33
                self.zoom = 1.0
                self.pan = QtCore.QPointF(0, 0)
                self._recompose()
                self.update()

            def set_ai_heat(self, heat224: np.ndarray, alpha_cam: float = 0.33):
                self.ai_heat = heat224
                self.show_ai = True
                self.alpha_cam = float(alpha_cam)
                self._recompose()
                self.update()

            def set_show_ai(self, flag: bool):
                self.show_ai = bool(flag)
                self._recompose()
                self.update()

            def set_show_user_mask(self, flag: bool):
                self.show_user_mask = bool(flag)
                self._recompose()
                self.update()

            def set_ai_alpha(self, value: int):
                self.alpha_cam = max(0.0, min(1.0, int(value) / 100.0))
                self._recompose()
                self.update()

            def set_brush(self, v: int):
                self.brush = max(3, int(v))

            def set_eraser(self, flag: bool):
                self.eraser = bool(flag)

            def set_paint_enabled(self, flag: bool):
                self.paint_enabled = bool(flag)

            def has_user_paint(self) -> bool:
                return self.user_mask is not None and int(self.user_mask.sum()) > 0

            def _recompose(self):
                if self.base_rgb is None:
                    self.view_rgb = None
                    return

                out = self.base_rgb.copy()

                if self.show_user_mask and self.user_mask is not None:
                    out = _overlay_user_mask(out, (self.user_mask > 0).astype(np.float32), alpha=0.28)

                if self.show_ai and self.ai_heat is not None:
                    out = _blend_heatmap_on_rgb(out, self.ai_heat, alpha=self.alpha_cam)

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

                w = int(w * self.zoom)
                h = int(h * self.zoom)

                x0 = int((aw - w) / 2 + self.pan.x())
                y0 = int((ah - h) / 2 + self.pan.y())

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
                    p.drawText(self.rect(), QtCore.Qt.AlignCenter, "Область изображения")
                    return

                x0, y0, w, h = self._label_rect_for_image()
                H, W = self.view_rgb.shape[:2]
                qimg = QtGui.QImage(self.view_rgb.data, W, H, 3 * W, QtGui.QImage.Format_RGB888)
                pix = QtGui.QPixmap.fromImage(qimg.copy())

                p.drawPixmap(QtCore.QRect(x0, y0, w, h), pix)

            def wheelEvent(self, event):
                if self.base_rgb is None:
                    return

                old_zoom = self.zoom

                if event.angleDelta().y() > 0:
                    self.zoom *= 1.12
                else:
                    self.zoom /= 1.12

                self.zoom = max(1.0, min(5.0, self.zoom))

                self._clamp_pan()
                self.update()


            def mousePressEvent(self, e: QtGui.QMouseEvent):
                if self.base_rgb is None:
                    return

                if e.button() == QtCore.Qt.RightButton:
                    self._panning = True
                    self._pan_start = e.pos()
                    self.setCursor(QtCore.Qt.ClosedHandCursor)
                    return

                if not self.paint_enabled:
                    return

                if e.button() != QtCore.Qt.LeftButton:
                    return

                p = self._widget_pos_to_image_xy(e.pos())
                if p is None:
                    return

                self._dragging = True
                self._last_pos = p
                self._paint_at(p[0], p[1])
                self._recompose()
                self.update()


            def mouseMoveEvent(self, e: QtGui.QMouseEvent):
                if self.base_rgb is None:
                    return

                if self._panning and self._pan_start is not None:
                    delta = e.pos() - self._pan_start
                    self.pan += QtCore.QPointF(delta.x(), delta.y())
                    self._clamp_pan()
                    self._pan_start = e.pos()
                    self.update()
                    return

                if not self.paint_enabled or not self._dragging:
                    return

                p = self._widget_pos_to_image_xy(e.pos())
                if p is None:
                    return

                x1, y1 = self._last_pos
                x2, y2 = p

                cv2.line(
                    self.user_mask,
                    (x1, y1),
                    (x2, y2),
                    color=(0 if self.eraser else 1),
                    thickness=int(self.brush * 2)
                )

                self._last_pos = p
                self._recompose()
                self.update()


            def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
                if e.button() == QtCore.Qt.RightButton:
                    self._panning = False
                    self._pan_start = None
                    self.setCursor(QtCore.Qt.ArrowCursor)
                    return

                if e.button() == QtCore.Qt.LeftButton:
                    self._dragging = False
                    self._last_pos = None

            def _clamp_pan(self):
                if self.zoom <= 1.0:
                    self.pan = QtCore.QPointF(0, 0)
                    return

                x0, y0, w, h = self._label_rect_for_image()
                aw, ah = self.width(), self.height()

                max_x = max(0, (w - aw) / 2)
                max_y = max(0, (h - ah) / 2)

                self.pan.setX(max(-max_x, min(max_x, self.pan.x())))
                self.pan.setY(max(-max_y, min(max_y, self.pan.y())))

        class TrainingPage(QtWidgets.QWidget):
            def __init__(self, mainwin: "MainWindow"):
                super().__init__()
                self._mw = mainwin
                self.setFocusPolicy(QtCore.Qt.StrongFocus)

                self.samples_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "samples"
                )
                self.image_path = None

                self._worker = None
                self._dlg = None
                self.step = 0

                self._build()
                self._set_step(0)

            def _select_stage(self, stage: int):
                if stage < 0 or stage > 4:
                    return
                self.stage_combo.setCurrentIndex(stage)

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

                def hint_item(mode: str, text: str):
                    w = QtWidgets.QWidget()
                    w.setStyleSheet("background: transparent; border: none;")

                    row = QtWidgets.QHBoxLayout(w)
                    row.setContentsMargins(0, 0, 0, 0)
                    row.setSpacing(7)

                    icon = MouseHintIcon(mode)
                    icon.setFixedSize(34, 38)

                    label = QtWidgets.QLabel(text)
                    label.setStyleSheet("""
                        QLabel {
                            font-size: 11px;
                            color: #555;
                            font-weight: 900;
                            border: none;
                            background: transparent;
                        }
                    """)

                    row.addWidget(icon)
                    row.addWidget(label)
                    return w

                hint_bar = QtWidgets.QWidget()
                hint_bar.setFixedHeight(42)
                hint_bar.setStyleSheet("background: transparent; border: none;")

                hl = QtWidgets.QHBoxLayout(hint_bar)
                hl.setContentsMargins(10, 5, 10, 5)
                hl.setSpacing(12)

                hl.addStretch(1)
                hl.addWidget(hint_item("left", "Кисть"))
                hl.addWidget(hint_item("right", "Передвижение"))
                hl.addWidget(hint_item("wheel", "Приближение"))
                hl.addStretch(1)

                ll.addWidget(self.canvas, 1)
                ll.addWidget(hint_bar)

                grid.addWidget(left, 1)

                right = QtWidgets.QFrame()
                right.setFixedWidth(420)
                right.setStyleSheet("QFrame{background:#fff;border:1px solid #e6e6e6;border-radius:16px;}")
                rl = QtWidgets.QVBoxLayout(right)
                rl.setContentsMargins(14, 14, 14, 14)
                rl.setSpacing(10)

                head = QtWidgets.QLabel("Панель тренировки")
                head.setStyleSheet("QLabel{font-size:14px;font-weight:900;border:none;background:transparent;}")
                rl.addWidget(head)

                self.btn_start = QtWidgets.QPushButton("Начать тренировку")
                self.btn_start.setFixedHeight(46)
                self.btn_start.clicked.connect(self._start_training)
                rl.addWidget(self.btn_start)

                self.controls_box = QtWidgets.QFrame()
                self.controls_box.setStyleSheet("QFrame{background:#ffffff;border:1px solid #eeeeee;border-radius:14px;}")
                cb = QtWidgets.QVBoxLayout(self.controls_box)
                cb.setContentsMargins(12, 12, 12, 12)
                cb.setSpacing(10)

                row_paint = QtWidgets.QHBoxLayout()

                lbl_paint = QtWidgets.QLabel("Разметка")
                lbl_paint.setStyleSheet("QLabel{font-weight:900;color:#222;border:none;background:transparent;}")

                self.chk_paint = ToggleSwitch()
                self.chk_paint.setChecked(True)
                self.chk_paint.toggled.connect(
                    lambda checked: self.canvas.set_paint_enabled(checked)
                )

                row_paint.addWidget(lbl_paint)
                row_paint.addStretch(1)
                row_paint.addWidget(self.chk_paint)
                cb.addLayout(row_paint)


                row_mode = QtWidgets.QHBoxLayout()

                lbl_mode = QtWidgets.QLabel("Инструмент")
                lbl_mode.setStyleSheet("QLabel{font-weight:900;color:#222;border:none;background:transparent;}")

                self.mode_switch = ModeSwitch()
                self.mode_switch.setChecked(False)
                self.mode_switch.modeChanged.connect(
                    lambda eraser: self.canvas.set_eraser(eraser)
                )

                row_mode.addWidget(lbl_mode)
                row_mode.addStretch(1)
                row_mode.addWidget(self.mode_switch)
                cb.addLayout(row_mode)

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

                self.layers_box = QtWidgets.QFrame()
                self.layers_box.setStyleSheet("""
                    QFrame {
                        background:#ffffff;
                        border:1px solid #eeeeee;
                        border-radius:14px;
                    }
                """)

                layers_l = QtWidgets.QVBoxLayout(self.layers_box)
                layers_l.setContentsMargins(12, 12, 12, 12)
                layers_l.setSpacing(8)

                layers_title = QtWidgets.QLabel("Слои изображения")
                layers_title.setStyleSheet("QLabel{font-size:13px;font-weight:900;border:none;background:transparent;}")
                layers_l.addWidget(layers_title)

                row_layer_user = QtWidgets.QHBoxLayout()

                lbl_layer_user = QtWidgets.QLabel("Ваша разметка")
                lbl_layer_user.setStyleSheet("QLabel{font-weight:800;color:#222;border:none;background:transparent;}")

                self.chk_layer_user = ToggleSwitch()
                self.chk_layer_user.setChecked(True)
                self.chk_layer_user.toggled.connect(
                    lambda checked: self.canvas.set_show_user_mask(checked)
                )

                row_layer_user.addWidget(lbl_layer_user)
                row_layer_user.addStretch(1)
                row_layer_user.addWidget(self.chk_layer_user)
                layers_l.addLayout(row_layer_user)


                row_layer_ai = QtWidgets.QHBoxLayout()

                lbl_layer_ai = QtWidgets.QLabel("Слой ИИ")
                lbl_layer_ai.setStyleSheet("QLabel{font-weight:800;color:#222;border:none;background:transparent;}")

                self.chk_layer_ai = ToggleSwitch()
                self.chk_layer_ai.setChecked(True)
                self.chk_layer_ai.toggled.connect(
                    lambda checked: self.canvas.set_show_ai(checked)
                )

                row_layer_ai.addWidget(lbl_layer_ai)
                row_layer_ai.addStretch(1)
                row_layer_ai.addWidget(self.chk_layer_ai)
                layers_l.addLayout(row_layer_ai)

                alpha_row = QtWidgets.QHBoxLayout()
                alpha_lbl = QtWidgets.QLabel("Прозрачность ИИ")
                alpha_lbl.setStyleSheet("QLabel{font-size:12px;font-weight:800;border:none;background:transparent;}")
                alpha_row.addWidget(alpha_lbl)

                self.ai_alpha_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
                self.ai_alpha_slider.setRange(0, 100)
                self.ai_alpha_slider.setValue(33)
                self.ai_alpha_slider.valueChanged.connect(self.canvas.set_ai_alpha)
                alpha_row.addWidget(self.ai_alpha_slider, 1)

                layers_l.addLayout(alpha_row)

                legend_box = QtWidgets.QFrame()
                legend_box.setStyleSheet("""
                    QFrame {
                        background:#f8fbff;
                        border:1px solid #e2eefc;
                        border-radius:12px;
                    }
                """)

                legend_l = QtWidgets.QVBoxLayout(legend_box)
                legend_l.setContentsMargins(10, 8, 10, 8)
                legend_l.setSpacing(6)

                legend_title = QtWidgets.QLabel("Обозначения слоёв")
                legend_title.setStyleSheet("""
                    QLabel {
                        font-size:12px;
                        font-weight:900;
                        color:#222;
                        border:none;
                        background:transparent;
                    }
                """)
                legend_l.addWidget(legend_title)

                def layer_legend_item(color: str, title: str, desc: str):
                    row = QtWidgets.QHBoxLayout()
                    row.setSpacing(8)

                    mark = QtWidgets.QLabel()
                    mark.setFixedSize(28, 6)
                    mark.setStyleSheet(f"""
                        QLabel {{
                            background:{color};
                            border:none;
                            border-radius:3px;
                        }}
                    """)

                    text = QtWidgets.QLabel(f"<b>{title}</b> - {desc}")
                    text.setWordWrap(True)
                    text.setStyleSheet("""
                        QLabel {
                            font-size:11px;
                            color:#555;
                            border:none;
                            background:transparent;
                        }
                    """)

                    row.addWidget(mark)
                    row.addWidget(text, 1)
                    return row

                legend_l.addLayout(layer_legend_item("#00A65A", "Ваша разметка", "область, которую вы выделили вручную"))
                legend_l.addLayout(layer_legend_item("#ff3b30", "Тёплые зоны", "участки, на которые модель обращает наибольшее внимание при анализе"))
                legend_l.addLayout(layer_legend_item("#0078D7", "Холодные зоны", "участки, которые обладают наименьшим вниманием ИИ"))

                rl.addWidget(self.layers_box)
                self.result_frame = QtWidgets.QFrame()
                self.result_frame.setStyleSheet("""
                    QFrame { background:#f7fbff; border:1px solid #d6e7ff; border-radius:14px; }
                """)
                rf = QtWidgets.QVBoxLayout(self.result_frame)
                rf.setContentsMargins(12, 12, 12, 12)
                rf.setSpacing(8)

                rl.addWidget(self.result_frame)
                rl.addWidget(legend_box)

                self.result_title = QtWidgets.QLabel("Результат")
                self.result_title.setStyleSheet("QLabel{font-size:13px;font-weight:900;color:#0b2a4a;border:none;background:transparent;}")
                rf.addWidget(self.result_title)

                row = QtWidgets.QHBoxLayout()
                row.setSpacing(10)

                self.score_badge = QtWidgets.QLabel("-/5")
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

                self.btn_copy_result = QtWidgets.QPushButton("Скопировать результат")
                self.btn_copy_result.setFixedHeight(34)
                self.btn_copy_result.clicked.connect(self._copy_result)
                rf.addWidget(self.btn_copy_result)

                self.result_frame.setVisible(False)

                rl.addStretch(1)

                grid.addWidget(right)
                root.addLayout(grid, 1)

                self._kill_text_frames(self)

            def _kill_text_frames(self, root: QtWidgets.QWidget):
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
                self.mode_switch.setEnabled(can_edit)
                self.brush_slider.setEnabled(can_edit)

                self.btn_confirm_focus.setEnabled(step == 1)
                self.btn_ai.setEnabled(step == 2)

                if self.step == 0:
                    self.step_hint.setText("Этап 1/4. Начните тренировку, нажав на кнопку \"Начать обучение\".")
                    self.controls_box.setVisible(False)
                    self.result_frame.setVisible(False)
                    self.layers_box.setVisible(False)
                    self.canvas.set_paint_enabled(False)
                    self.btn_start.setEnabled(True)
                elif self.step == 1:
                    self.step_hint.setText("Этап 2/4. Выберите стадию диабетической ретинопатии и отметьте подозрительные области на изображении.")
                    self.controls_box.setVisible(True)
                    self.layers_box.setVisible(False)
                    self.result_frame.setVisible(False)
                    self.canvas.set_paint_enabled(True)
                    self.btn_start.setEnabled(False)
                    self.btn_confirm_focus.setEnabled(True)
                    self.btn_ai.setEnabled(False)
                elif self.step == 2:
                    self.step_hint.setText("Этап 3/4. Подтвердите выполненную разметку, нажав на кнопку \"Проверить результат\"")
                    self.controls_box.setVisible(True)
                    self.layers_box.setVisible(False)
                    self.result_frame.setVisible(False)
                    self.canvas.set_paint_enabled(False) 
                    self.btn_confirm_focus.setEnabled(False)
                    self.btn_ai.setEnabled(True)
                else:
                    self.step_hint.setText("Этап 4/4. Отлично! Результаты успешно проверены.")
                    self.btn_start.setEnabled(True)
                    self.controls_box.setVisible(False)
                    self.layers_box.setVisible(True)
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

                self.result_frame.setVisible(False)
                self.ai_out.setText("")
                self.result_hint.setText("")
                self.score_badge.setText("-/5")

                self.chk_layer_user.setChecked(True)
                self.chk_layer_ai.setChecked(True)
                self.ai_alpha_slider.setValue(33)
                self.canvas.set_show_user_mask(True)
                self.canvas.set_show_ai(False)
                self.canvas.set_ai_alpha(33)

                self.chk_paint.setEnabled(True)
                self.mode_switch.setEnabled(True)
                self.brush_slider.setEnabled(True)

                self.chk_paint.setChecked(True)
                self.mode_switch.setChecked(False)
                self.canvas.set_eraser(False)
                self.canvas.set_paint_enabled(True)

                self.btn_confirm_focus.setEnabled(True)
                self.btn_ai.setEnabled(False)

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
                self.score_badge.setText("-/5")
                self._set_step(0)

            def _run_ai_async(self):
                if not self.image_path or self.canvas.base_rgb is None:
                    RoundedDialog.warning("Ошибка", "Сначала начните тренировку")
                    return

                if self.step < 2:
                    RoundedDialog.warning("Сначала подтвердите фокус", "Нажмите «Далее: подтвердить фокус» перед запуском ИИ.")
                    return

                self._dlg = LoadingDialog(self, "ИИ анализирует снимок и сравнивает с вашим фокусом…")
                self._dlg.show()
                out_png = os.path.join(tempfile.gettempdir(), "retino_heatmap.png")

                self.btn_ai.setEnabled(False)
                self.stage_combo.setEnabled(False)
                self.chk_paint.setEnabled(False)
                self.mode_switch.setEnabled(False)
                self.brush_slider.setEnabled(False)

                self._worker = InferenceWorker(self.image_path, out_png)
                self._worker.done.connect(lambda data: self._on_ai_done(data, out_png))
                self._worker.fail.connect(self._on_ai_fail)
                self._worker.finished.connect(self._on_ai_finally)
                self._worker.start()

            def _on_ai_done(self, data: dict, out_png: str):
                try:
                    stage_id = int(data.get("stage_id", 0))
                    pmax = float(data.get("p_max", 0.0))

                    heat_u8 = cv2.imdecode(np.fromfile(out_png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                    if heat_u8 is None:
                        raise RuntimeError("Не удалось прочитать heatmap.png")
                    heat = heat_u8.astype(np.float32) / 255.0

                    um = (self.canvas.user_mask > 0).astype(np.uint8)
                    um_224 = cv2.resize(um, (224, 224), interpolation=cv2.INTER_NEAREST).astype(bool)
                    am_224 = _ai_mask_from_heatmap(heat, top_frac=0.30)

                    sim = _dice(um_224, am_224)        
                    area_score = _score_1to5_from_similarity(sim)

                    user_stage = self.stage_combo.currentIndex()
                    ai_stage = stage_id
                    diff_stage = abs(user_stage - ai_stage)
                    stage_score = max(1, 5 - diff_stage)

                    w_stage = 0.8
                    w_area  = 0.2
                    final_score = int(round(w_stage * stage_score + w_area * area_score))
                    final_score = max(1, min(5, final_score))

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

                    self.chk_layer_user.setChecked(True)
                    self.chk_layer_ai.setChecked(True)
                    self.ai_alpha_slider.setValue(33)
                    self.canvas.set_ai_heat(heat, alpha_cam=0.33)

                    ai_txt = STAGE_NAMES[ai_stage]
                    user_txt = STAGE_NAMES[user_stage]

                    self.ai_out.setText(
                        f"Автоматический анализ определил: {ai_txt}.\n"
                        f"Ваш ответ: {user_txt}."
                    )
                    self.ai_out.setStyleSheet("QLabel{font-size:11px;font-weight:900;border:none;background:transparent;}")
                    self.result_hint.setText(
                        f"Совпадение области внимания: {sim:.2f} • "
                        f"Уверенность модели: {pmax:.2f}"
                    )
                    self.result_hint.setStyleSheet("QLabel{font-size:11px;font-weight:900;border:none;background:transparent;}")
                    self.score_badge.setText(f"{final_score}/5")
                    self.result_frame.setVisible(True)

                    self._set_step(3)

                except Exception as e:
                    self._on_ai_fail(str(e))

            # def on_restart():
            #     self._reset_training()

            # def on_stats():
            #     try:
            #         self._mw.set_page(2)
            #     except Exception:
            #         pass

            # body = (
            #     f"ИИ определил: {ai_txt}.\n"
            #     f"Ваш ответ: {user_txt}.\n\n"
            #     f"Совпадение области внимания: {sim:.2f}.\n"
            #     f"Итоговая оценка: {final_score}/5."
            # )

            def _on_ai_fail(self, err: str):
                RoundedDialog.warning("Ошибка", f"ИИ анализ не удался:\n{err}")

            def _copy_result(self):
                text = (
                    self.ai_out.text().strip()
                    + "\n"
                    + self.result_hint.text().strip()
                ).strip()

                if not text:
                    RoundedDialog.warning("Нет результата", "Сначала проверьте результат через ИИ.")
                    return

                QtWidgets.QApplication.clipboard().setText(text)
                RoundedDialog.info("Готово", "Результат скопирован в буфер обмена.")

            def _on_ai_finally(self):
                if self._dlg is not None:
                    self._dlg.close()
                    self._dlg = None

                self.stage_combo.setEnabled(True)
                self.chk_paint.setEnabled(False)
                self.mode_switch.setEnabled(False)
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

        self.settings_verify_icon = check         
        self.settings_verified_text = verified_text

        verified_row.addWidget(check)
        verified_row.addWidget(verified_text)
        verified_row.addStretch(1)

        info_col.addLayout(verified_row)
        pl.addLayout(info_col, 1)

        l.addWidget(profile)

        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setSpacing(6)
        status_layout.setContentsMargins(0, 0, 0, 0)

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

        last_v = self._latest_version()
        footer = QtWidgets.QLabel(f"by redictor, 2026 • MIT License • {current_v}")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #8a8a8a;")
        l.addWidget(footer)

        return w

    def _latest_version(self) -> str:
        try:
            updates = get_updates() or []
            if not updates:
                return "unknown version"
            latest = max(updates, key=lambda u: int(u.get("id", 0) or 0))
            return str(latest.get("version", "unknown version"))
        except Exception:
            return "unknown version"

    def _on_reset_training(self):
        dlg = RoundedDialog(
            self,
            "Сбросить всю статистику тренировок?\n\n"
            "Это действие нельзя отменить."
        )

        dlg.set_confirm_text("Сбросить")
        dlg.set_cancel_text("Отмена")
        dlg.set_danger(True) 

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

    def _load_account_status(self):
        try:
            profile = get_profile() or {}
            created_at = profile.get("created_at")
            is_verified = False

            if created_at:
                s = str(created_at).replace("Z", "").replace(" ", "T")
                created = datetime.datetime.fromisoformat(s)
                is_verified = (datetime.datetime.now() - created).total_seconds() >= 24 * 60 * 60

            self._account_status = {
                "is_verified": is_verified,
                "created_at": created_at
            }

            self._apply_account_status_ui()
        except Exception as e:
            print("Ошибка загрузки статуса аккаунта:", e)

    def _apply_account_status_ui(self):
        st = self._account_status or {}
        is_verified = bool(st.get("is_verified", False))

        if not hasattr(self, "settings_verify_icon") or not hasattr(self, "settings_verified_text"):
            return

        if is_verified:
            self.settings_verify_icon.setText("✓")
            self.settings_verify_icon.setStyleSheet("""
                QLabel {
                    background-color: #22c55e;
                    color: white;
                    border-radius: 9px;
                    font-size: 12px;
                    font-weight: 800;
                }
            """)
            self.settings_verified_text.setText("Аккаунт верифицирован")
            self.settings_verified_text.setStyleSheet("font-size: 13px; color: #16a34a; font-weight: 700;")
        else:
            self.settings_verify_icon.setText("!")
            self.settings_verify_icon.setStyleSheet("""
                QLabel {
                    background-color: #f59e0b;
                    color: white;
                    border-radius: 9px;
                    font-size: 12px;
                    font-weight: 800;
                }
            """)
            self.settings_verified_text.setText("Аккаунт будет автоматически верифицирован через 24 часа после регистрации")
            self.settings_verified_text.setStyleSheet("font-size: 13px; color: #d97706; font-weight: 700;")

    def _logout(self):
        from ui_dialogs import ConfirmDialog
        from api_client import logout

        ok = ConfirmDialog.ask(
            "Выход из аккаунта",
            "Вы действительно хотите выйти из аккаунта?",
            confirm_text="Выйти",
            cancel_text="Отмена",
            danger=False
        )

        if not ok:
            return

        try:
            logout()  
        except Exception:
            pass

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
            RoundedDialog.info("Готово", "Аккаунт был успешно удалён")
            logout()
            self.close()
            self.on_logout()
        else:
            RoundedDialog.warning("Ошибка", "Не удалось удалить ваш аккаунт, попробуйте позже")
