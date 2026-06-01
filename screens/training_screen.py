import os
import sys
import json
import random
import subprocess
import tempfile

import numpy as np
import cv2
from PyQt5 import QtWidgets, QtCore, QtGui

from ui_dialogs import RoundedDialog
import app_logger

_log = app_logger.get("screens.training")


STAGE_NAMES = [
    "0 стадия - Нет ретинопатии",
    "1 стадия - Начальная",
    "2 стадия - Умеренная",
    "3 стадия - Тяжёлая",
    "4 стадия - Профилеративная",
]

def _imread_unicode(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _blend_heatmap_on_rgb(rgb: np.ndarray, heat: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    heat_u8 = (heat * 255).astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
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
    return h >= thr


def _score_1to5_from_similarity(sim: float) -> int:
    if sim >= 0.80:
        return 5
    if sim >= 0.60:
        return 4
    if sim >= 0.40:
        return 3
    if sim >= 0.20:
        return 2
    return 1

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
    modeChanged = QtCore.pyqtSignal(bool)

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

class InferenceWorker(QtCore.QThread):
    done = QtCore.pyqtSignal(dict)
    fail = QtCore.pyqtSignal(str)

    def __init__(self, image_path: str, out_png: str):
        super().__init__()
        self.image_path = image_path
        self.out_png = out_png

    def run(self):
        _log.debug("Запуск инференса: %s", self.image_path)
        try:
            py = sys.executable
            cmd = [py, "infer_torch.py", self.image_path, self.out_png]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
            )
            if res.returncode != 0:
                err = (res.stderr or res.stdout or "").strip() or "Неизвестная ошибка"
                _log.error(
                    "infer_torch завершился с ошибкой (code=%d): %s",
                    res.returncode, err,
                )
                self.fail.emit(err)
                return
            data = json.loads(res.stdout.strip())
            _log.debug(
                "Инференс завершён: stage_id=%s, p_max=%.3f",
                data.get("stage_id"), data.get("p_max", 0),
            )
            self.done.emit(data)
        except subprocess.TimeoutExpired:
            _log.error("Инференс превысил таймаут (60 с): %s", self.image_path)
            self.fail.emit("Превышено время ожидания анализа (60 сек).")
        except Exception as e:
            _log.error("Необработанная ошибка InferenceWorker", exc_info=True)
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
        ix = max(0, min(W - 1, int(nx * W)))
        iy = max(0, min(H - 1, int(ny * H)))
        return ix, iy

    def _paint_at(self, ix: int, iy: int):
        if self.user_mask is None:
            return
        v = 0 if self.eraser else 1
        cv2.circle(self.user_mask, (ix, iy), int(self.brush), int(v), thickness=-1)

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
        if not self.paint_enabled or e.button() != QtCore.Qt.LeftButton:
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
            thickness=int(self.brush * 2),
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

class ShimmerBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self._pos = -0.4

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self._pos += 0.018
        if self._pos > 1.0:
            self._pos = -0.4
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        r = self.rect()
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor("#E0E0E0"))
        p.drawRoundedRect(r, 4, 4)

        w = int(r.width() * 0.38)
        x = int(r.width() * self._pos)

        grad = QtGui.QLinearGradient(x, 0, x + w, 0)
        grad.setColorAt(0.0, QtGui.QColor(0, 120, 215, 0))
        grad.setColorAt(0.45, QtGui.QColor("#1f8bf0"))
        grad.setColorAt(0.70, QtGui.QColor("#0078D7"))
        grad.setColorAt(1.0, QtGui.QColor(0, 120, 215, 0))

        p.setBrush(grad)
        p.drawRoundedRect(QtCore.QRect(x, 0, w, r.height()), 4, 4)

class LoadingDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self._parent_for_center = parent.window() if parent is not None else None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        outer = QtWidgets.QFrame(self)
        outer.setObjectName("outer")
        outer.setStyleSheet("""
            QFrame#outer {
                background-color: #F0F0F0;
                border-radius: 18px;
                border: 1px solid #D6D6D6;
            }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)

        lay = QtWidgets.QVBoxLayout(outer)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)

        badge = QtWidgets.QLabel()
        badge.setFixedSize(34, 34)
        badge.setAlignment(QtCore.Qt.AlignCenter)

        pixmap = QtGui.QPixmap("assets/icons/ai.png")
        if not pixmap.isNull():
            badge.setStyleSheet(
                "QLabel { background-color: #0078D7; border-radius: 17px; border: none; }"
            )
            badge.setPixmap(
                pixmap.scaled(
                    22, 22,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
            )

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)

        title = QtWidgets.QLabel("Анализ снимка")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 800;
                color: #222;
                border: none;
                background: transparent;
            }
        """)

        subtitle = QtWidgets.QLabel("ИИ обрабатывает изображение и формирует вердикт")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #666;
                border: none;
                background: transparent;
            }
        """)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addWidget(badge)
        header.addLayout(title_box, 1)
        lay.addLayout(header)

        lay.addLayout(header)

        lay.addSpacing(12)

        pb = ShimmerBar()
        lay.addWidget(pb)

        lay.addSpacing(12)

        self.setFixedWidth(460)
        self.adjustSize()

        QtCore.QTimer.singleShot(0, self._center_on_parent)

    def _center_on_parent(self):
        parent = self._parent_for_center

        if parent is not None:
            pg = parent.frameGeometry()
        else:
            pg = QtWidgets.QApplication.primaryScreen().availableGeometry()

        self.move(
            pg.center().x() - self.width() // 2,
            pg.center().y() - self.height() // 2
        )

class TrainingScreen(QtWidgets.QWidget):
    def __init__(self, on_save_record, parent=None):
        super().__init__(parent)
        self._on_save_record = on_save_record
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.samples_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "samples",
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
                border: 1px solid #e2e2e2; border-radius: 10px;
                padding: 8px; background: #fff; color: #222; font-weight: 800;
            }
            QPushButton {
                background: #0078D7; color: #fff; border: none;
                border-radius: 12px; padding: 10px 12px; font-weight: 900;
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
                QLabel { font-size:11px; color:#555; font-weight:900; border:none; background:transparent; }
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
        self.chk_paint.toggled.connect(lambda checked: self.canvas.set_paint_enabled(checked))
        row_paint.addWidget(lbl_paint)
        row_paint.addStretch(1)
        row_paint.addWidget(self.chk_paint)
        cb.addLayout(row_paint)

        row_mode = QtWidgets.QHBoxLayout()
        lbl_mode = QtWidgets.QLabel("Инструмент")
        lbl_mode.setStyleSheet("QLabel{font-weight:900;color:#222;border:none;background:transparent;}")
        self.mode_switch = ModeSwitch()
        self.mode_switch.setChecked(False)
        self.mode_switch.modeChanged.connect(lambda eraser: self.canvas.set_eraser(eraser))
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
            QFrame { background:#ffffff; border:1px solid #eeeeee; border-radius:14px; }
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
        self.chk_layer_user.toggled.connect(lambda checked: self.canvas.set_show_user_mask(checked))
        row_layer_user.addWidget(lbl_layer_user)
        row_layer_user.addStretch(1)
        row_layer_user.addWidget(self.chk_layer_user)
        layers_l.addLayout(row_layer_user)

        row_layer_ai = QtWidgets.QHBoxLayout()
        lbl_layer_ai = QtWidgets.QLabel("Слой ИИ")
        lbl_layer_ai.setStyleSheet("QLabel{font-weight:800;color:#222;border:none;background:transparent;}")
        self.chk_layer_ai = ToggleSwitch()
        self.chk_layer_ai.setChecked(True)
        self.chk_layer_ai.toggled.connect(lambda checked: self.canvas.set_show_ai(checked))
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
            QFrame { background:#f8fbff; border:1px solid #e2eefc; border-radius:12px; }
        """)
        legend_l = QtWidgets.QVBoxLayout(legend_box)
        legend_l.setContentsMargins(10, 8, 10, 8)
        legend_l.setSpacing(6)

        legend_title = QtWidgets.QLabel("Обозначения слоёв")
        legend_title.setStyleSheet("font-size:12px;font-weight:900;color:#222;border:none;background:transparent;")
        legend_l.addWidget(legend_title)

        def layer_legend_item(color: str, title: str, desc: str):
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            mark = QtWidgets.QLabel()
            mark.setFixedSize(28, 6)
            mark.setStyleSheet(f"QLabel {{ background:{color}; border:none; border-radius:3px; }}")
            text = QtWidgets.QLabel(f"<b>{title}</b> - {desc}")
            text.setWordWrap(True)
            text.setStyleSheet("font-size:11px;color:#555;border:none;background:transparent;")
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

        rl.addWidget(self.result_frame)
        rl.addWidget(legend_box)
        rl.addStretch(1)

        grid.addWidget(right)
        root.addLayout(grid, 1)

        for lab in self.findChildren(QtWidgets.QLabel):
            lab.setFrameShape(QtWidgets.QFrame.NoFrame)
            lab.setLineWidth(0)
            lab.setMidLineWidth(0)
            lab.setFocusPolicy(QtCore.Qt.NoFocus)

    def _set_step(self, step: int):
        self.step = step
        self.step_bar.setValue(self.step)

        self.stage_combo.setEnabled(step == 1)
        self.chk_paint.setEnabled(step == 1)
        self.mode_switch.setEnabled(step == 1)
        self.brush_slider.setEnabled(step == 1)
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
            _log.warning("Папка samples не найдена: %s", self.samples_dir)
            RoundedDialog.warning(
                "Ошибка",
                "Папка samples не найдена.\nДобавьте изображения в папку samples в корне проекта.",
            )
            return

        imgp = self._pick_random_image(self.samples_dir)
        if not imgp:
            _log.warning("В папке samples нет изображений: %s", self.samples_dir)
            RoundedDialog.warning("Нет изображений", "В выбранной папке не найдены изображения (png/jpg/jpeg/bmp).")
            return

        _log.debug("Выбрано изображение для тренировки: %s", imgp)
        bgr = _imread_unicode(imgp)
        if bgr is None:
            _log.error("Не удалось прочитать изображение: %s", imgp)
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

        self._dlg = LoadingDialog(self)
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
                raise RuntimeError(f"Не удалось прочитать файл тепловой карты: {out_png}")
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

            final_score = int(round(0.8 * stage_score + 0.2 * area_score))
            final_score = max(1, min(5, final_score))

            _log.info(
                "Результат тренировки: user_stage=%d, ai_stage=%d, dice=%.3f, score=%d/5",
                user_stage, ai_stage, sim, final_score,
            )

            try:
                self._on_save_record({
                    "user_stage": int(user_stage),
                    "ai_stage": int(ai_stage),
                    "score": int(final_score),
                    "dice": float(sim),
                    "p_max": float(pmax),
                })
            except Exception:
                _log.error("Не удалось передать запись тренировки на сохранение", exc_info=True)

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
            _log.error("Ошибка обработки результатов ИИ анализа", exc_info=True)
            self._on_ai_fail(str(e))

    def _on_ai_fail(self, err: str):
        _log.error("ИИ анализ завершился ошибкой: %s", err)
        RoundedDialog.warning("Ошибка анализа", "ИИ не смог обработать снимок.\nПопробуйте ещё раз или выберите другое изображение.")

    def _copy_result(self):
        text = (self.ai_out.text().strip() + "\n" + self.result_hint.text().strip()).strip()
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
