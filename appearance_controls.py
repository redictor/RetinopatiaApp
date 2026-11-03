from PyQt5 import QtCore, QtGui, QtWidgets
from ui_theme import ACCENTS, BLUE, blend

class SlidingSegments(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(object)

    def __init__(self, choices, selected=0, width=356, parent=None):
        super().__init__(parent)
        self.choices = list(choices)
        self.index = max(0, min(int(selected), len(self.choices) - 1))
        self._offset = float(self.index)
        self._animated = True
        self._accent = BLUE
        self._pending = None
        self.setFixedSize(width, 38)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._slide = QtCore.QVariantAnimation(self)
        self._slide.setDuration(260)
        self._slide.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        self._slide.valueChanged.connect(self._move_slider)
        self._slide.finished.connect(self._finish_slide)

    def set_accent(self, color):
        self._accent = color
        self.update()

    def set_animated(self, enabled):
        self._animated = bool(enabled)
        if not self._animated and self._slide.state() == QtCore.QAbstractAnimation.Running:
            self._slide.stop()
            self._offset = float(self.index)
            self.update()
            self._emit_pending()

    def set_selection(self, value):
        self._slide.stop()
        for i, (_, code) in enumerate(self.choices):
            if code == value or (isinstance(code, str) and isinstance(value, str)
                                 and code.lower() == value.lower()):
                self.index = i
                self._offset = float(i)
                self._pending = None
                self.update()
                return

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            slot = (self.width() - 4) / len(self.choices)
            index = max(0, min(len(self.choices) - 1, int((event.x() - 2) / slot)))
            self.choose(index)
        super().mousePressEvent(event)

    def choose(self, index):
        if index == self.index:
            return
        self.index = index
        self._pending = self.choices[index][1]
        self._slide.stop()
        if not self._animated:
            self._offset = float(index)
            self.update()
            self._emit_pending()
            return
        self._slide.setStartValue(self._offset)
        self._slide.setEndValue(float(index))
        self._slide.start()

    def _move_slider(self, value):
        self._offset = float(value)
        self.update()

    def _finish_slide(self):
        self._emit_pending()

    def _emit_pending(self):
        if self._pending is not None:
            value = self._pending
            self._pending = None
            self.changed.emit(value)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self.choices)
        slot = (w - 4) / n
        p.setPen(QtGui.QPen(QtGui.QColor('#dbe5ef'), 1))
        p.setBrush(QtGui.QColor('#f8fafc'))
        p.drawRoundedRect(QtCore.QRectF(.5, .5, w-1, h-1), 18, 18)
        p.setPen(QtGui.QPen(QtGui.QColor(blend('#ffffff', self._accent, .27)), 1))
        p.setBrush(QtGui.QColor(blend('#ffffff', self._accent, .17)))
        p.drawRoundedRect(QtCore.QRectF(2 + slot * self._offset, 2, slot, h-4), 16, 16)
        font = QtGui.QFont(self.font())
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        for i, (label, color) in enumerate(self.choices):
            label_w = metrics.horizontalAdvance(label)
            dot_d = 9
            gap = 7
            group_w = label_w + dot_d + gap
            cx = 2 + slot * (i + .5)
            x = cx - group_w / 2
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(color))
            p.drawEllipse(QtCore.QRectF(x, (h-dot_d)/2, dot_d, dot_d))
            p.setPen(QtGui.QColor('#172033'))
            text_rect = QtCore.QRectF(x + dot_d + gap, 0, label_w + 2, h)
            p.drawText(text_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
        p.end()

class AccentSelector(SlidingSegments):
    def __init__(self, names, current=BLUE, parent=None):
        super().__init__(list(zip(names, ACCENTS)), width=356, parent=parent)
        self.set_selection(current)

class AnimationSelector(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(bool)

    def __init__(self, labels=None, enabled=True, parent=None):
        super().__init__(parent)
        self._checked = bool(enabled)
        self._accent = BLUE
        self._knob_x = 26.0 if enabled else 3.0
        self.setFixedSize(56, 32)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._slide = QtCore.QVariantAnimation(self)
        self._slide.setDuration(240)
        self._slide.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._slide.valueChanged.connect(self._update_knob)

    def set_accent(self, color):
        self._accent = color
        self.update()

    def set_animated(self, enabled):
        if not enabled and self._slide.state() == QtCore.QAbstractAnimation.Running:
            self._slide.stop()
            self._knob_x = 26.0 if self._checked else 3.0
            self.update()

    def set_selection(self, enabled):
        self._slide.stop()
        self._checked = bool(enabled)
        self._knob_x = 26.0 if self._checked else 3.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._slide.stop()
            self._checked = not self._checked
            if self._checked:
                self._slide.setStartValue(self._knob_x)
                self._slide.setEndValue(26.0)
                self._slide.start()
            else:
                self._knob_x = 3.0
                self.update()
            self.changed.emit(self._checked)
        super().mousePressEvent(event)

    def _update_knob(self, value):
        self._knob_x = float(value)
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        off_color = QtGui.QColor('#cbd5e1')
        on_color = QtGui.QColor(self._accent)
        progress = max(0.0, min(1.0, (self._knob_x - 3.0) / 23.0))
        bg = QtGui.QColor(
            round(off_color.red() * (1-progress) + on_color.red()*progress),
            round(off_color.green() * (1-progress) + on_color.green()*progress),
            round(off_color.blue() * (1-progress) + on_color.blue()*progress),
        )
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QtCore.QRectF(0, 0, 56, 32), 16, 16)
        p.setBrush(QtGui.QColor('#ffffff'))
        p.drawEllipse(QtCore.QRectF(self._knob_x, 3, 26, 26))
        p.end()