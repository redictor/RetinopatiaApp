import os
import sys
import json
import random
import subprocess
import tempfile
import i18n

import numpy as np
import cv2
from PyQt5 import QtWidgets, QtCore, QtGui

from dialogs.ui_dialogs import RoundedDialog
import app_logger

_log = app_logger.get("screens.training")


def stage_name(stage: int) -> str:
    return i18n.t(f"stages.{stage}")

def _imread_unicode(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)



def _fundus_mask_from_rgb(rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    foreground = (blurred > 15).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    foreground = cv2.morphologyEx(
        foreground, cv2.MORPH_CLOSE, kernel
    )

    n, labels, stats, centroids = cv2.connectedComponentsWithStats(
        foreground, 8
    )

    height, width = gray.shape
    candidates = []

    for component in range(1, n):
        area = int(stats[component, cv2.CC_STAT_AREA])

        if area < 0.10 * height * width:
            continue

        cx, cy = centroids[component]
        distance = (
            ((cx - width / 2) / width) ** 2
            + ((cy - height / 2) / height) ** 2
        )

        candidates.append(
            (area / (1.0 + 4.0 * distance), component)
        )

    if not candidates:
        return foreground.astype(bool)

    selected = max(candidates)[1]
    component_mask = (labels == selected).astype(np.uint8)

    contours, _ = cv2.findContours(
        component_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    filled = np.zeros_like(component_mask)
    cv2.drawContours(filled, contours, -1, 1, cv2.FILLED)

    return filled.astype(bool)


def _blend_heatmap_on_rgb(
    rgb: np.ndarray,
    heat: np.ndarray,
    alpha: float = 0.35
) -> np.ndarray:
    heat_resized = cv2.resize(
        heat,
        (rgb.shape[1], rgb.shape[0]),
        interpolation=cv2.INTER_LINEAR
    )

    fundus_mask = _fundus_mask_from_rgb(rgb).astype(np.float32)

    heat_u8 = (
        np.clip(heat_resized, 0, 1) * 255
    ).astype(np.uint8)

    heat_color = cv2.applyColorMap(
        heat_u8, cv2.COLORMAP_JET
    )
    heat_color = cv2.cvtColor(
        heat_color, cv2.COLOR_BGR2RGB
    )

    weight = float(alpha) * fundus_mask[..., None]

    out = (
        rgb.astype(np.float32) * (1 - weight)
        + heat_color.astype(np.float32) * weight
    )

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


def _dice(a: np.ndarray, b: np.ndarray, tolerance_px: int = 6) -> float:
    a = a.astype(np.uint8)
    b = b.astype(np.uint8)
    if tolerance_px > 0:
        kernel = np.ones((tolerance_px * 2 + 1, tolerance_px * 2 + 1), np.uint8)
        a = cv2.dilate(a, kernel)
        b = cv2.dilate(b, kernel)
    a = a.astype(bool)
    b = b.astype(bool)
    inter = (a & b).sum()
    denom = a.sum() + b.sum()
    if denom == 0:
        return 0.0
    return float(2 * inter / denom)

def _ai_mask_from_heatmap(
    heat224: np.ndarray,
    top_frac: float = 0.30,
    valid_mask: np.ndarray | None = None
) -> np.ndarray:
    h = heat224.astype(np.float32)

    if valid_mask is None:
        valid_mask = np.ones(h.shape, dtype=bool)
    else:
        valid_mask = valid_mask.astype(bool)

    result = np.zeros(h.shape, dtype=bool)
    valid_values = h[valid_mask]

    if valid_values.size == 0 or top_frac <= 0:
        return result

    h_min = float(valid_values.min())
    h_max = float(valid_values.max())

    if h_max - h_min < 1e-6:
        return result

    normalized = (h - h_min) / (h_max - h_min)

    top_frac = max(0.02, min(0.60, float(top_frac)))

    threshold = np.quantile(
        normalized[valid_mask],
        1.0 - top_frac
    )

    result[valid_mask] = (
        normalized[valid_mask] >= threshold
    )

    return result

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
        p.end()


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
        p.drawText(left_rect, QtCore.Qt.AlignCenter, i18n.t("training.tool_brush"))
        p.setPen(QtGui.QColor("#ffffff") if self.isChecked() else QtGui.QColor("#333333"))
        p.drawText(right_rect, QtCore.Qt.AlignCenter, i18n.t("training.tool_eraser"))
        p.end()


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
        p.end()

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
            app_dir = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )

            py = sys.executable
            script = os.path.join(app_dir, "ai", "infer_torch.py")

            cmd = [py, script, self.image_path, self.out_png]

            res = subprocess.run(
                cmd,
                cwd=app_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
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
            _log.error("Инференс превысил таймаут (120 с): %s", self.image_path)
            self.fail.emit(i18n.t("training.analysis_timeout"))
        except Exception as e:
            _log.error("Необработанная ошибка InferenceWorker", exc_info=True)
            self.fail.emit(str(e))

class PaintCanvas(QtWidgets.QWidget):
    MAX_UNDO_STEPS = 30

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
        self._undo_stack = []
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

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
        self._undo_stack = []
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
        self._undo_stack = []
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

    def _push_undo_snapshot(self):
        if self.user_mask is None:
            return
        self._undo_stack.append(self.user_mask.copy())
        if len(self._undo_stack) > self.MAX_UNDO_STEPS:
            self._undo_stack.pop(0)

    def undo(self):
        if not self._undo_stack:
            return
        self.user_mask = self._undo_stack.pop()
        self._recompose()
        self.update()

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
            p.drawText(
                self.rect(),
                QtCore.Qt.AlignCenter,
                i18n.t("training.image_area_placeholder")
            )
            p.end()
            return
        x0, y0, w, h = self._label_rect_for_image()
        H, W = self.view_rgb.shape[:2]
        qimg = QtGui.QImage(self.view_rgb.data, W, H, 3 * W, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg.copy())
        p.drawPixmap(QtCore.QRect(x0, y0, w, h), pix)
        p.end()

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
        self.setFocus()
        self._push_undo_snapshot()
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

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Z and event.modifiers() & QtCore.Qt.ControlModifier:
            self.undo()
            event.accept()
            return
        super().keyPressEvent(event)

class ShimmerBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self._pos = -0.4

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

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
        p.end()

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

        title = QtWidgets.QLabel(i18n.t("training.analysis_title"))
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 800;
                color: #222;
                border: none;
                background: transparent;
            }
        """)

        subtitle = QtWidgets.QLabel(i18n.t("training.analysis_subtitle"))
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

        self.setFixedWidth(500)
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

        # self.samples_dir = os.path.join(
        #     os.path.dirname(os.path.abspath(__file__)),
        #     "..",
        #     "samples",
        # )
        self.samples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "samples",
            "colored_images"
        )
        self.image_path = None
        self._last_result_stages = None
        self._worker = None
        self._dlg = None
        self.step = 0
        self._decks = {}
        self._deck = []
        self._used = []
        self._build()
        self._set_step(0)

    def retranslate_ui(self):
        """Refresh only language-dependent labels; keep canvas/mask/current stage."""
        self.step_hint.setText(i18n.t(f"training.step_{min(self.step + 1, 4)}"))
        if self._last_result_stages is not None:
            ai_stage, user_stage = self._last_result_stages
            self.result_ai_line.setText(i18n.t(
                "training.ai_determined", ai_txt=stage_name(ai_stage)
            ))
            self.result_user_line.setText(i18n.t(
                "training.your_answer", user_txt=stage_name(user_stage)
            ))
        self.mode_switch.update()
        self.canvas.update()

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
            QSlider::handle:horizontal:disabled { background:#b9c6d3; }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        title = QtWidgets.QLabel(i18n.t("nav.training"))
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
        hl.addWidget(hint_item("left", i18n.t("training.tool_brush")))
        hl.addWidget(hint_item("right", i18n.t("training.move_tool")))
        hl.addWidget(hint_item("right", i18n.t("training.move_tool")))
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

        head = QtWidgets.QLabel(i18n.t("training.panel_title"))
        head.setStyleSheet("QLabel{font-size:14px;font-weight:900;border:none;background:transparent;}")
        rl.addWidget(head)

        self.btn_start = QtWidgets.QPushButton(i18n.t("training.start_button"))
        self.btn_start.setFixedHeight(46)
        self.btn_start.clicked.connect(self._start_training)
        rl.addWidget(self.btn_start)

        self.controls_box = QtWidgets.QFrame()
        self.controls_box.setStyleSheet("QFrame{background:#ffffff;border:1px solid #eeeeee;border-radius:14px;}")
        cb = QtWidgets.QVBoxLayout(self.controls_box)
        cb.setContentsMargins(12, 12, 12, 12)
        cb.setSpacing(10)

        row_paint = QtWidgets.QHBoxLayout()
        lbl_paint = QtWidgets.QLabel(i18n.t("training.marking_label"))
        lbl_paint.setStyleSheet("QLabel{font-weight:900;color:#222;border:none;background:transparent;}")
        self.chk_paint = ToggleSwitch()
        self.chk_paint.setChecked(True)
        self.chk_paint.toggled.connect(lambda checked: self.canvas.set_paint_enabled(checked))
        row_paint.addWidget(lbl_paint)
        row_paint.addStretch(1)
        row_paint.addWidget(self.chk_paint)
        cb.addLayout(row_paint)

        row_mode = QtWidgets.QHBoxLayout()
        lbl_mode = QtWidgets.QLabel(i18n.t("training.tool_label"))
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
        lb = QtWidgets.QLabel(i18n.t("training.brush_size"))
        lb.setStyleSheet("QLabel{font-size:12px;font-weight:900;border:none;background:transparent;}")
        br.addWidget(lb)
        self.brush_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.brush_slider.setRange(3, 50)
        self.brush_slider.setValue(18)
        self.brush_slider.valueChanged.connect(lambda v: self.canvas.set_brush(v))
        br.addWidget(self.brush_slider, 1)
        cb.addLayout(br)

        stl = QtWidgets.QLabel(i18n.t("training.select_stage_prompt"))
        stl.setStyleSheet("QLabel{font-size:12px;font-weight:900;border:none;background:transparent;}")
        cb.addWidget(stl)

        self.stage_combo = QtWidgets.QComboBox()
        self.stage_combo.addItems(
            [i18n.t(f"stages.{stage}") for stage in range(5)]
        )
        self.stage_combo.setFixedHeight(40)
        cb.addWidget(self.stage_combo)

        self.btn_confirm_focus = QtWidgets.QPushButton(i18n.t("training.confirm_button"))
        self.btn_confirm_focus.setFixedHeight(44)
        self.btn_confirm_focus.clicked.connect(self._confirm_focus)
        cb.addWidget(self.btn_confirm_focus)

        self.btn_ai = QtWidgets.QPushButton(i18n.t("training.check_result_button"))
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

        layers_title = QtWidgets.QLabel(i18n.t("training.layers_title"))
        layers_title.setStyleSheet("QLabel{font-size:13px;font-weight:900;border:none;background:transparent;}")
        layers_l.addWidget(layers_title)

        row_layer_user = QtWidgets.QHBoxLayout()
        lbl_layer_user = QtWidgets.QLabel(i18n.t("training.your_markup"))
        lbl_layer_user.setStyleSheet("QLabel{font-weight:800;color:#222;border:none;background:transparent;}")
        self.chk_layer_user = ToggleSwitch()
        self.chk_layer_user.setChecked(True)
        self.chk_layer_user.toggled.connect(lambda checked: self.canvas.set_show_user_mask(checked))
        row_layer_user.addWidget(lbl_layer_user)
        row_layer_user.addStretch(1)
        row_layer_user.addWidget(self.chk_layer_user)
        layers_l.addLayout(row_layer_user)

        row_layer_ai = QtWidgets.QHBoxLayout()
        lbl_layer_ai = QtWidgets.QLabel(i18n.t("training.ai_markup"))
        lbl_layer_ai.setStyleSheet("QLabel{font-weight:800;color:#222;border:none;background:transparent;}")
        self.chk_layer_ai = ToggleSwitch()
        self.chk_layer_ai.setChecked(True)
        self.chk_layer_ai.toggled.connect(lambda checked: self.canvas.set_show_ai(checked))
        self.chk_layer_ai.toggled.connect(lambda checked: self.ai_alpha_slider.setEnabled(checked))
        row_layer_ai.addWidget(lbl_layer_ai)
        row_layer_ai.addStretch(1)
        row_layer_ai.addWidget(self.chk_layer_ai)
        layers_l.addLayout(row_layer_ai)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_lbl = QtWidgets.QLabel(i18n.t("training.ai_markup_opacity"))
        alpha_lbl.setStyleSheet("QLabel{font-size:12px;font-weight:800;border:none;background:transparent;}")
        alpha_row.addWidget(alpha_lbl)
        self.ai_alpha_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.ai_alpha_slider.setRange(0, 100)
        self.ai_alpha_slider.setValue(33)
        self.ai_alpha_slider.valueChanged.connect(self.canvas.set_ai_alpha)
        alpha_row.addWidget(self.ai_alpha_slider, 1)
        layers_l.addLayout(alpha_row)

        legend_header = QtWidgets.QHBoxLayout()
        legend_header.setSpacing(6)

        legend_header_title = QtWidgets.QLabel(i18n.t("training.layers_legend"))
        legend_header_title.setStyleSheet("font-size:12px;font-weight:900;color:#222;border:none;background:transparent;")
        legend_header.addWidget(legend_header_title)
        legend_header.addStretch(1)

        self.legend_toggle_btn = QtWidgets.QPushButton()
        self.legend_toggle_btn.setFixedSize(22, 22)
        self.legend_toggle_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.legend_toggle_btn.setCheckable(True)
        self._legend_icon_svg = """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14">
                <circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="2"/>
                <text x="12" y="16.5" font-size="12" font-weight="900" text-anchor="middle" fill="{color}" font-family="Arial, sans-serif">?</text>
            </svg>
        """
        self._set_legend_icon("#0078D7")
        self.legend_toggle_btn.setStyleSheet("""
            QPushButton { background:#eef3fb; border:1px solid #cfe0f5; border-radius:11px; }
            QPushButton:hover { background:#dce9fb; }
            QPushButton:checked { background:#0078D7; border:1px solid #0078D7; }
        """)
        self.legend_toggle_btn.clicked.connect(self._toggle_legend)
        legend_header.addWidget(self.legend_toggle_btn)

        layers_l.addLayout(legend_header)

        legend_box = QtWidgets.QFrame()
        legend_box.setStyleSheet("""
            QFrame { background:#f8fbff; border:1px solid #e2eefc; border-radius:12px; }
        """)
        legend_l = QtWidgets.QVBoxLayout(legend_box)
        legend_l.setContentsMargins(10, 8, 10, 8)
        legend_l.setSpacing(6)

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

        legend_l.addLayout(layer_legend_item(
            "#00A65A",
            i18n.t("training.your_markup"),
            i18n.t("training.manual_area_desc")
        ))

        legend_l.addLayout(layer_legend_item(
            "#ff3b30",
            i18n.t("training.warm_zones"),
            i18n.t("training.warm_zones_desc")
        ))

        legend_l.addLayout(layer_legend_item(
            "#0078D7",
            i18n.t("training.cold_zones"),
            i18n.t("training.cold_zones_desc")
        ))

        self.legend_wrapper = QtWidgets.QWidget()
        legend_wrapper_l = QtWidgets.QVBoxLayout(self.legend_wrapper)
        legend_wrapper_l.setContentsMargins(0, 0, 0, 0)
        legend_wrapper_l.addWidget(legend_box)
        self.legend_wrapper.setMaximumHeight(0)
        self.legend_wrapper.setMinimumHeight(0)
        layers_l.addWidget(self.legend_wrapper)

        self._legend_expanded = False
        self._legend_anim = QtCore.QPropertyAnimation(self.legend_wrapper, b"maximumHeight", self)
        self._legend_anim.setDuration(380)
        self._legend_anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)

        rl.addWidget(self.layers_box)

        self.result_frame = QtWidgets.QFrame()
        self.result_frame.setStyleSheet("""
            QFrame { background:#f7fbff; border:1px solid #d6e7ff; border-radius:16px; }
        """)
        rf = QtWidgets.QVBoxLayout(self.result_frame)
        rf.setContentsMargins(16, 16, 16, 16)
        rf.setSpacing(12)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(8)

        self.result_title = QtWidgets.QLabel(i18n.t("training.result_title"))
        self.result_title.setStyleSheet("QLabel{font-size:15px;font-weight:900;color:#0b2a4a;border:none;background:transparent;}")
        title_row.addWidget(self.result_title)
        title_row.addStretch(1)

        self.btn_copy_result = QtWidgets.QPushButton()
        self.btn_copy_result.setFixedSize(30, 30)
        self.btn_copy_result.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_copy_result.setToolTip(i18n.t("training.copy_result"))
        self.btn_copy_result.setStyleSheet("""
            QPushButton { background:#eef3fb; border:1px solid #cfe0f5; border-radius:15px; }
            QPushButton:hover { background:#dce9fb; }
        """)
        self._set_copy_icon()
        self.btn_copy_result.clicked.connect(self._copy_result)
        title_row.addWidget(self.btn_copy_result)

        rf.addLayout(title_row)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(14)

        self.score_badge = QtWidgets.QLabel("-")
        self.score_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.score_badge.setFixedSize(64, 64)
        self.score_badge.setStyleSheet("""
            QLabel{background:#ffffff;color:#777;border:4px solid #777;border-radius:32px;font-size:26px;font-weight:900;}
        """)
        top_row.addWidget(self.score_badge)

        info_col = QtWidgets.QVBoxLayout()
        info_col.setSpacing(4)

        self.result_ai_line = QtWidgets.QLabel("")
        self.result_ai_line.setWordWrap(True)
        self.result_ai_line.setStyleSheet("QLabel{font-size:12px;font-weight:800;color:#0b2a4a;border:none;background:transparent;}")
        info_col.addWidget(self.result_ai_line)

        self.result_user_line = QtWidgets.QLabel("")
        self.result_user_line.setWordWrap(True)
        self.result_user_line.setStyleSheet("QLabel{font-size:12px;font-weight:700;color:#3f5d7a;border:none;background:transparent;}")
        info_col.addWidget(self.result_user_line)

        top_row.addLayout(info_col, 1)
        rf.addLayout(top_row)

        divider = QtWidgets.QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color:#d6e7ff;border:none;")
        rf.addWidget(divider)

        match_col = QtWidgets.QVBoxLayout()
        match_col.setSpacing(4)

        match_title = QtWidgets.QLabel(i18n.t("training.attention_match"))
        match_title.setStyleSheet("QLabel{font-size:12px;font-weight:800;color:#6d87a3;border:none;background:transparent;}")
        match_col.addWidget(match_title)

        self.result_match_value = QtWidgets.QLabel("-")
        self.result_match_value.setStyleSheet("QLabel{font-size:20px;font-weight:900;color:#0b2a4a;border:none;background:transparent;}")
        match_col.addWidget(self.result_match_value)

        rf.addLayout(match_col)

        self.ai_out = self.result_ai_line
        self.result_hint = QtWidgets.QLabel("")
        self.result_hint.setVisible(False)
        rf.addWidget(self.result_hint)

        self.result_frame.setVisible(False)

        rl.addWidget(self.result_frame)
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
            self.step_hint.setText(i18n.t("training.step_1"))
            self.controls_box.setVisible(False)
            self.result_frame.setVisible(False)
            self.layers_box.setVisible(False)
            self.canvas.set_paint_enabled(False)
            self.btn_start.setEnabled(True)
        elif self.step == 1:
            self.step_hint.setText(i18n.t("training.step_2"))
            self.controls_box.setVisible(True)
            self.layers_box.setVisible(False)
            self.result_frame.setVisible(False)
            self.canvas.set_paint_enabled(True)
            self.btn_start.setEnabled(False)
            self.btn_confirm_focus.setEnabled(True)
            self.btn_ai.setEnabled(False)
        elif self.step == 2:
            self.step_hint.setText(i18n.t("training.step_3"))
            self.controls_box.setVisible(True)
            self.layers_box.setVisible(False)
            self.result_frame.setVisible(False)
            self.canvas.set_paint_enabled(False)
            self.btn_confirm_focus.setEnabled(False)
            self.btn_ai.setEnabled(True)
        else:
            self.step_hint.setText(i18n.t("training.step_4"))
            self.btn_start.setEnabled(True)
            self.controls_box.setVisible(False)
            self.layers_box.setVisible(True)
            self.result_frame.setVisible(True)
            self.canvas.set_paint_enabled(False)
            self.btn_confirm_focus.setEnabled(False)
            self.btn_ai.setEnabled(False)

    def _pick_random_image(self, folder: str):
            exts = (".png", ".jpg", ".jpeg", ".bmp")
            class_names = ["No_DR", "Mild", "Moderate", "Severe", "Proliferate_DR"]

            if not self._decks:
                for cls in class_names:
                    cls_dir = os.path.join(folder, cls)
                    files = []
                    if os.path.isdir(cls_dir):
                        for f in os.listdir(cls_dir):
                            if f.lower().endswith(exts):
                                files.append(os.path.join(cls_dir, f))
                    random.shuffle(files)
                    self._decks[cls] = files

            available = [c for c in class_names if self._decks.get(c)]
            if not available:
                for cls in class_names:
                    cls_dir = os.path.join(folder, cls)
                    files = []
                    if os.path.isdir(cls_dir):
                        for f in os.listdir(cls_dir):
                            if f.lower().endswith(exts):
                                files.append(os.path.join(cls_dir, f))
                    random.shuffle(files)
                    self._decks[cls] = files
                available = [c for c in class_names if self._decks.get(c)]
                if not available:
                    return None

            cls = random.choice(available)
            return self._decks[cls].pop()

    def _start_training(self):
        if not os.path.isdir(self.samples_dir):
            _log.warning("Папка samples не найдена: %s", self.samples_dir)
            RoundedDialog.warning(
                i18n.t("training.no_folder_title"),
                i18n.t("training.no_folder_text")
            )
            return

        imgp = self._pick_random_image(self.samples_dir)
        if not imgp:
            _log.warning("В папке samples нет изображений: %s", self.samples_dir)
            RoundedDialog.warning(
                i18n.t("training.no_images_title"),
                i18n.t("training.no_images_text")
            )
            return

        _log.debug("Выбрано изображение для тренировки: %s", imgp)
        bgr = _imread_unicode(imgp)
        if bgr is None:
            _log.error("Не удалось прочитать изображение: %s", imgp)
            RoundedDialog.warning(
                i18n.t("training.no_folder_title"),
                i18n.t("training.no_image_open")
            )
            return

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.image_path = imgp
        self._last_result_stages = None
        self.canvas.set_image(rgb)

        self.result_frame.setVisible(False)
        self.result_ai_line.setText("")
        self.result_user_line.setText("")
        self.result_match_value.setText("-")
        self.score_badge.setText("-")
        self.score_badge.setStyleSheet("""
            QLabel{background:#ffffff;color:#777;border:4px solid #777;border-radius:32px;font-size:26px;font-weight:900;}
        """)

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
            RoundedDialog.warning(
                i18n.t("training.no_image"),
                i18n.t("training.start_and_load_image")
            )
            return
        if not self.canvas.has_user_paint():
            RoundedDialog.warning(
                i18n.t("training.need_select_area"),
                i18n.t("training.paint_area_first")
            )
            return
        self._set_step(2)

    def _reset_training(self):
        self._last_result_stages = None
        self.image_path = None
        self.canvas.clear_all()
        self.result_frame.setVisible(False)
        self.result_ai_line.setText("")
        self.result_user_line.setText("")
        self.result_match_value.setText("-")
        self.score_badge.setText("-")
        self.score_badge.setStyleSheet("""
            QLabel{background:#ffffff;color:#777;border:4px solid #777;border-radius:32px;font-size:26px;font-weight:900;}
        """)
        self._set_step(0)

    def _set_copy_icon(self):
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        pen = QtGui.QPen(QtGui.QColor("#0078D7"), 1.4)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(QtCore.QRectF(5, 1, 9, 11), 2, 2)
        painter.drawRoundedRect(QtCore.QRectF(1, 4, 9, 11), 2, 2)
        painter.end()
        self.btn_copy_result.setIcon(QtGui.QIcon(pixmap))
        self.btn_copy_result.setIconSize(QtCore.QSize(16, 16))

    def _set_legend_icon(self, color: str):
        pixmap = QtGui.QPixmap(20, 20)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(1, 1, 18, 18)
        font = QtGui.QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "?")
        painter.end()
        self.legend_toggle_btn.setIcon(QtGui.QIcon(pixmap))
        self.legend_toggle_btn.setIconSize(QtCore.QSize(14, 14))

    def _toggle_legend(self):
        self._legend_expanded = self.legend_toggle_btn.isChecked()

        try:
            self._legend_anim.finished.disconnect(self._on_legend_collapsed)
        except TypeError:
            pass

        self._legend_anim.stop()
        self._legend_anim.setStartValue(self.legend_wrapper.height())

        if self._legend_expanded:
            self.legend_wrapper.setMaximumHeight(16777215)
            target_height = self.legend_wrapper.sizeHint().height()
            self.legend_wrapper.setMaximumHeight(self.legend_wrapper.height())
        else:
            target_height = 0
            self._legend_anim.finished.connect(self._on_legend_collapsed)

        self._legend_anim.setEndValue(target_height)
        self._set_legend_icon("#ffffff" if self._legend_expanded else "#0078D7")
        self._legend_anim.start()

    def _on_legend_collapsed(self):
        self.legend_wrapper.setMaximumHeight(0)
        try:
            self._legend_anim.finished.disconnect(self._on_legend_collapsed)
        except TypeError:
            pass

    def _run_ai_async(self):
        if not self.image_path or self.canvas.base_rgb is None:
            RoundedDialog.warning(
                i18n.t("training.no_folder_title"),
                i18n.t("training.first_start_training")
            )
            return
        if self.step < 2:
            RoundedDialog.warning(
                i18n.t("training.first_confirm_focus"),
                i18n.t("training.confirm_before_ai")
            )
            return

        self._dlg = LoadingDialog(self)
        self._dlg.show()
        out_png = os.path.join(
            tempfile.gettempdir(),
            f"retino_heatmap_{os.getpid()}_{QtCore.QDateTime.currentMSecsSinceEpoch()}.png"
        )

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
            um_224 = cv2.resize(
                um, (224, 224),
                interpolation=cv2.INTER_NEAREST
            ).astype(bool)

            fundus_mask = _fundus_mask_from_rgb(self.canvas.base_rgb)

            valid_224 = cv2.resize(
                fundus_mask.astype(np.uint8),
                (224, 224),
                interpolation=cv2.INTER_NEAREST
            ).astype(bool)

            um_224 &= valid_224

            valid_pixels = int(valid_224.sum())

            user_frac = (
                float(um_224.sum()) / valid_pixels
                if valid_pixels else 0.0
            )

            am_224 = _ai_mask_from_heatmap(
                heat,
                top_frac=user_frac,
                valid_mask=valid_224
            )

            sim = _dice(um_224, am_224)

            _log.debug(
                "AIS: fundus_pixels=%d, user_frac=%.3f, dice=%.3f",
                valid_pixels, user_frac, sim
            )

            area_score = _score_1to5_from_similarity(sim)

            user_stage = self.stage_combo.currentIndex()
            ai_stage = stage_id

            class_to_stage = {
                "No_DR": 0,
                "Mild": 1,
                "Moderate": 2,
                "Severe": 3,
                "Proliferate_DR": 4,
            }

            class_name = os.path.basename(
                os.path.dirname(self.image_path)
            )

            if class_name not in class_to_stage:
                raise ValueError(
                    f"Неизвестная категория изображения: {class_name}"
                )

            true_stage = class_to_stage[class_name]

            diff_stage = abs(user_stage - true_stage)
            stage_score = max(1, 5 - diff_stage)

            _log.info(
                "Оценивание: эталон=%d, ответ=%d, ИИ=%d",
                true_stage, user_stage, ai_stage
            )

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

            self._last_result_stages = (ai_stage, user_stage)
            ai_txt = stage_name(ai_stage)
            user_txt = stage_name(user_stage)

            self.result_ai_line.setText(
                i18n.t("training.ai_determined", ai_txt=ai_txt)
            )
            self.result_user_line.setText(
                i18n.t("training.your_answer", user_txt=user_txt)
            )

            match_pct = max(0, min(100, round(sim * 100)))
            self.result_match_value.setText(f"{match_pct}%")

            score_letter = self._score_letter(final_score)
            letter_color = self._letter_color(score_letter)
            self.score_badge.setText(score_letter)
            self.score_badge.setStyleSheet(
                f"QLabel{{background:#ffffff;color:{letter_color};"
                f"border:4px solid {letter_color};border-radius:32px;font-size:26px;font-weight:900;}}"
            )
            self.result_frame.setVisible(True)
            self._set_step(3)

        except Exception as e:
            _log.error("Ошибка обработки результатов ИИ анализа", exc_info=True)
            self._on_ai_fail(str(e))

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

    def _on_ai_fail(self, err: str):
        _log.error("ИИ анализ завершился ошибкой: %s", err)
        RoundedDialog.warning(
            i18n.t("training.analysis_error_title"),
            i18n.t("training.analysis_error_text")
        )

    def _copy_result(self):
        parts = [
            self.result_ai_line.text().strip(),
            self.result_user_line.text().strip(),
            f"{i18n.t('training.attention_match')}: {self.result_match_value.text()}",
        ]
        text = "\n".join(p for p in parts if p)
        if not text:
            RoundedDialog.warning(
                i18n.t("training.no_result"),
                i18n.t("training.first_check_ai")
            )
            return
        QtWidgets.QApplication.clipboard().setText(text)
        RoundedDialog.info(
            i18n.t("training.done_title"),
            i18n.t("training.result_copied")
        )

    def _on_ai_finally(self):
        if self._dlg is not None:
            self._dlg.close()
            self._dlg = None
        self.stage_combo.setEnabled(True)
        self.chk_paint.setEnabled(False)
        self.mode_switch.setEnabled(False)
        self.brush_slider.setEnabled(False)
