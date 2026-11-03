import re
from PyQt5 import QtCore, QtGui, QtWidgets

BLUE = '#0078D7'
ACCENTS = (BLUE, '#0891B2', '#7455D9')
CURRENT_ACCENT = BLUE

def current_accent():
    return CURRENT_ACCENT

SHADES = {
    '#0078d7': 1.0, '#005499': .72, '#0067bd': .83,
    '#1273d1': 1.0, '#1f8bf0': 1.04,
    '#0784dc': 1.04, '#1479cf': 1.0, '#0b79d0': 1.0,
    '#d6e7ff': .16, '#cfe0f5': .18, '#dce9fb': .13,
    '#eef3fb': .06, '#f8fbff': .035, '#e7f2ff': .09,
    '#b8d9ff': .28, '#e8f4fc': .07, '#d5eafa': .13,
    '#f7fbff': .04,
    '#c9e2f7': .22, '#e3f2ff': .09, '#d9eaff': .13,
    '#f0f7ff': .05, '#edf6ff': .065, '#eaf4ff': .08,
    '#e2eefc': .10, '#c6def6': .24,
}
HEX = re.compile(r'#[0-9a-fA-F]{6}\b')

def blend(a, b, strength):
    a, b = QtGui.QColor(a), QtGui.QColor(b)
    t = max(0.0, min(1.0, strength))
    return QtGui.QColor(
        round(a.red() * (1-t) + b.red()*t),
        round(a.green() * (1-t) + b.green()*t),
        round(a.blue() * (1-t) + b.blue()*t),
    ).name()

def recolor_qss(source, accent):
    if accent == BLUE or not source:
        return source
    dark = QtGui.QColor(accent).darker(140).name()
    def replace(match):
        key = match.group().lower()
        factor = SHADES.get(key)
        if factor is None:
            return match.group()
        if key in ('#005499', '#0067bd'):
            return dark
        if factor >= 0.7:
            return accent
        return blend('#ffffff', accent, factor)
    return HEX.sub(replace, source)


class AccentTheme(QtCore.QObject):
    def __init__(self, app, accent=BLUE):
        super().__init__(app)
        self.app = app
        self.accent = accent if accent in ACCENTS else BLUE
        self._applying = False
        app.installEventFilter(self)
        self.set_color(self.accent)

    def set_color(self, color):
        if not QtGui.QColor(color).isValid():
            return
        global CURRENT_ACCENT
        self.accent = color
        CURRENT_ACCENT = color
        self.apply_all()

    def apply_all(self):
        if self._applying:
            return
        self._applying = True
        try:
            for w in self.app.allWidgets():
                self._update_widget(w)
            pal = self.app.palette()
            pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(self.accent))
            pal.setColor(QtGui.QPalette.Link, QtGui.QColor(self.accent))
            self.app.setPalette(pal)
        finally:
            self._applying = False

    def _update_widget(self, widget):
        try:
            current = widget.styleSheet()
            previous = widget.property('_retina_applied_qss')
            if previous is None or current != previous:
                widget.setProperty('_retina_base_qss', current)
            base = widget.property('_retina_base_qss') or ''
            themed = recolor_qss(base, self.accent)
            if current != themed:
                widget.setProperty('_retina_applied_qss', themed)
                widget.setStyleSheet(themed)
            else:
                widget.setProperty('_retina_applied_qss', current)
            if hasattr(widget, 'set_accent'):
                widget.set_accent(self.accent)
            widget.update()
        except RuntimeError: 
            pass

    def eventFilter(self, obj, event):
        if self._applying or not isinstance(obj, QtWidgets.QWidget):
            return False
        if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.StyleChange):
            self._applying = True
            try:
                self._update_widget(obj)
            finally:
                self._applying = False
        return False